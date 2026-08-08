import tempfile
from pathlib import Path

from mappy.engine import topology_db
from mappy.tests import ExtendedUnitTesting

TOPO = "mappy_topo_test"


class TestTopologyDb(ExtendedUnitTesting):
    def _new_connection(self):
        tmpdir = tempfile.mkdtemp()
        path = str(Path(tmpdir) / "topo.sqlite")
        conn = topology_db.get_connection(path)
        topology_db.ensure_topology(conn, TOPO)
        return conn, path

    def test_sidecar_path_derivation(self):
        self.assertEqual(topology_db.sidecar_path_for("/x/project.gpkg"), "/x/project.mappy-topology.sqlite")

    def test_ensure_topology_is_idempotent(self):
        conn, _ = self._new_connection()
        # calling again must not raise (e.g. "topology already exists")
        topology_db.ensure_topology(conn, TOPO)

    def test_two_squares_split_by_shared_edge(self):
        conn, _ = self._new_connection()

        outer = topology_db.add_linestring(conn, TOPO, "LINESTRING(0 0, 2 0, 2 1, 0 1, 0 0)")
        divider = topology_db.add_linestring(conn, TOPO, "LINESTRING(1 0, 1 1)")
        self.assertEqual(len(outer), 1)
        self.assertEqual(len(divider), 1)

        # re-adding identical geometry is idempotent: same edge id back
        again = topology_db.add_linestring(conn, TOPO, "LINESTRING(1 0, 1 1)")
        self.assertEqual(again, divider)

        rows = conn.execute(f"SELECT face_id FROM {TOPO}_face WHERE face_id <> 0").fetchall()
        face_ids = sorted(r[0] for r in rows)
        self.assertEqual(len(face_ids), 2)

        geoms = [topology_db.get_face_geometry_wkt(conn, TOPO, fid) for fid in face_ids]
        self.assertTrue(all(g is not None for g in geoms))

        issues = topology_db.validate_topology(conn, TOPO)
        self.assertEqual(issues, [])

    def test_removing_shared_edge_merges_faces(self):
        conn, _ = self._new_connection()

        topology_db.add_linestring(conn, TOPO, "LINESTRING(0 0, 2 0, 2 1, 0 1, 0 0)")
        divider_edges = topology_db.add_linestring(conn, TOPO, "LINESTRING(1 0, 1 1)")

        before = conn.execute(f"SELECT face_id FROM {TOPO}_face WHERE face_id <> 0").fetchall()
        self.assertEqual(len(before), 2)

        merged_face_id = topology_db.remove_edge(conn, TOPO, divider_edges[0])
        assert merged_face_id is not None

        after = conn.execute(f"SELECT face_id FROM {TOPO}_face WHERE face_id <> 0").fetchall()
        self.assertEqual([r[0] for r in after], [merged_face_id])

        # the merged face's geometry now covers both original squares
        from qgis.core import QgsGeometry

        merged_wkt = topology_db.get_face_geometry_wkt(conn, TOPO, merged_face_id)
        merged_geom = QgsGeometry.fromWkt(merged_wkt)
        self.assertAlmostEqual(merged_geom.area(), 2.0, places=6)

    def test_a_line_crossing_multiple_existing_edges_returns_all_new_edge_ids(self):
        """Regression test: TopoGeo_AddLineString returns a *single row*
        holding a comma-separated string of edge ids (e.g. "10, 12, 14")
        when one call ends up creating more than one edge, not one row per
        id -- found via a real crash in production usage (a line crossing
        two existing dividers at once), not caught by any earlier test
        here since every prior scenario only ever created one edge per
        call."""
        conn, _ = self._new_connection()

        topology_db.add_linestring(conn, TOPO, "LINESTRING(0 0, 3 0, 3 1, 0 1, 0 0)")
        topology_db.add_linestring(conn, TOPO, "LINESTRING(1 0, 1 1)")
        topology_db.add_linestring(conn, TOPO, "LINESTRING(2 0, 2 1)")

        # crosses both existing dividers in a single call
        edges = topology_db.add_linestring(conn, TOPO, "LINESTRING(0 0.5, 3 0.5)")

        self.assertEqual(len(edges), 3)
        self.assertTrue(all(isinstance(e, int) for e in edges))
        self.assertEqual(len(set(edges)), 3)  # all distinct

        face_ids = topology_db.list_face_ids(conn, TOPO)
        self.assertEqual(len(face_ids), 6)  # 3 squares each now split top/bottom

    def test_removing_a_dangle_returns_none(self):
        conn, _ = self._new_connection()

        topology_db.add_linestring(conn, TOPO, "LINESTRING(0 0, 2 0, 2 1, 0 1, 0 0)")
        dangle_edges = topology_db.add_linestring(conn, TOPO, "LINESTRING(0.2 0.2, 0.5 0.5)")

        result = topology_db.remove_edge(conn, TOPO, dangle_edges[0])
        self.assertIsNone(result)

    def test_drop_topology_then_recreate(self):
        conn, _ = self._new_connection()
        topology_db.add_linestring(conn, TOPO, "LINESTRING(0 0, 1 0)")

        topology_db.drop_topology(conn, TOPO)
        # dropping again (already gone) must not raise
        topology_db.drop_topology(conn, TOPO)

        topology_db.ensure_topology(conn, TOPO)
        rows = conn.execute(f"SELECT edge_id FROM {TOPO}_edge").fetchall()
        self.assertEqual(rows, [])
