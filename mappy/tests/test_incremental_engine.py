import os

from qgis.core import QgsFeature, QgsField, QgsGeometry, QgsPointXY, QgsProject, QgsVectorLayer
from qgis.PyQt.QtCore import QVariant

from mappy.engine import EngineConfig, IncrementalMapEngine, topology_db
from mappy.engine.incremental_engine import TOPOLOGY_NAME
from mappy.tests import ExtendedUnitTesting

OUTPUT = "/tmp/zzz_incremental_engine_test.gpkg"


class TestIncrementalEngine(ExtendedUnitTesting):
    def setUp(self):
        self._engines = []

    def tearDown(self):
        for engine in self._engines:
            engine.close()
        project = QgsProject.instance()
        stale = [layer_id for layer_id, layer in project.mapLayers().items() if OUTPUT in layer.dataProvider().dataSourceUri()]
        project.removeMapLayers(stale)
        self.clean_up([OUTPUT, topology_db.sidecar_path_for(OUTPUT)])

    def _make_engine(self):
        self.clean_up([OUTPUT, topology_db.sidecar_path_for(OUTPUT)])

        lines = QgsVectorLayer("LineString?crs=EPSG:4326", "zzz_incr_lines", "memory")
        for wkt in ("LINESTRING(0 0, 2 0, 2 1, 0 1, 0 0)", "LINESTRING(1 0, 1 1)"):
            f = QgsFeature(lines.fields())
            f.setGeometry(QgsGeometry.fromWkt(wkt))
            lines.dataProvider().addFeature(f)
        lines.updateExtents()
        QgsProject.instance().addMapLayer(lines)

        points = QgsVectorLayer("Point?crs=EPSG:4326", "zzz_incr_points", "memory")
        points.dataProvider().addAttributes([QgsField("unit_name", QVariant.String)])
        points.updateFields()
        for xy, unit in (((0.5, 0.5), "UNIT_A"), ((1.5, 0.5), "UNIT_B")):
            f = QgsFeature(points.fields())
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(*xy)))
            f["unit_name"] = unit
            points.dataProvider().addFeature(f)
        points.updateExtents()
        QgsProject.instance().addMapLayer(points)

        config = EngineConfig(
            lines=lines,
            points=points,
            output=OUTPUT,
            out_polygons_layer_name="zzz_incr_final_map",
            units_field="unit_name",
        )
        engine = IncrementalMapEngine(config)
        self._engines.append(engine)
        return engine, lines, points

    def test_recompute_map_still_produces_the_polygon_layer(self):
        """The inherited full-recompute behavior is untouched by the
        topology-building addition."""
        engine, _lines, _points = self._make_engine()
        engine.recompute_map()

        polygons = engine.get_polygons_layer()
        self.assertEqual(polygons.featureCount(), 2)

    def test_recompute_map_builds_two_faces(self):
        engine, _lines, _points = self._make_engine()
        engine.recompute_map()

        conn = engine._topology_connection()
        face_ids = topology_db.list_face_ids(conn, TOPOLOGY_NAME)
        self.assertEqual(len(face_ids), 2)

        geoms = [QgsGeometry.fromWkt(topology_db.get_face_geometry_wkt(conn, TOPOLOGY_NAME, fid)) for fid in face_ids]
        self.assertAlmostEqual(sum(g.area() for g in geoms), 2.0, places=6)

    def test_recompute_map_records_edge_source_per_line_feature(self):
        engine, lines, _points = self._make_engine()
        line_fids = [f.id() for f in lines.getFeatures()]
        engine.recompute_map()

        conn = engine._topology_connection()
        for fid in line_fids:
            edges = topology_db.edges_for_line(conn, fid)
            self.assertTrue(len(edges) >= 1, f"line fid {fid} has no recorded edges")

    def test_recompute_map_handles_a_line_crossing_multiple_existing_lines(self):
        """Regression test for a real crash: a line whose insertion gets
        split into more than one edge in a single TopoGeo_AddLineString
        call (SpatiaLite returns those as one row holding a comma-separated
        string, not one row per edge -- see topology_db.add_linestring)."""
        lines = QgsVectorLayer("LineString?crs=EPSG:4326", "zzz_incr_grid_lines", "memory")
        for wkt in (
            "LINESTRING(0 0, 3 0, 3 1, 0 1, 0 0)",
            "LINESTRING(1 0, 1 1)",
            "LINESTRING(2 0, 2 1)",
            "LINESTRING(0 0.5, 3 0.5)",  # crosses both dividers above at once
        ):
            f = QgsFeature(lines.fields())
            f.setGeometry(QgsGeometry.fromWkt(wkt))
            lines.dataProvider().addFeature(f)
        lines.updateExtents()
        QgsProject.instance().addMapLayer(lines)

        points = QgsVectorLayer("Point?crs=EPSG:4326", "zzz_incr_grid_points", "memory")
        points.dataProvider().addAttributes([QgsField("unit_name", QVariant.String)])
        points.updateFields()
        QgsProject.instance().addMapLayer(points)

        config = EngineConfig(
            lines=lines,
            points=points,
            output=OUTPUT,
            out_polygons_layer_name="zzz_incr_grid_final_map",
            units_field="unit_name",
        )
        engine = IncrementalMapEngine(config)
        self._engines.append(engine)

        engine.recompute_map()  # must not raise

        conn = engine._topology_connection()
        self.assertEqual(len(topology_db.list_face_ids(conn, TOPOLOGY_NAME)), 6)

    def test_recompute_map_is_idempotent_not_cumulative(self):
        engine, _lines, _points = self._make_engine()
        engine.recompute_map()
        engine.recompute_map()

        conn = engine._topology_connection()
        face_ids = topology_db.list_face_ids(conn, TOPOLOGY_NAME)
        self.assertEqual(len(face_ids), 2)

    def test_validate_topology_reports_in_sync_after_build(self):
        engine, _lines, _points = self._make_engine()
        engine.recompute_map()

        report = engine.validate_topology()
        self.assertTrue(report.in_sync)
        self.assertEqual(report.issues, [])

    def test_invalidate_drops_the_topology(self):
        engine, _lines, _points = self._make_engine()
        engine.recompute_map()

        engine.invalidate()

        conn = engine._topology_connection()
        self.assertEqual(topology_db.list_face_ids(conn, TOPOLOGY_NAME), [])

    def test_topology_survives_a_simulated_restart(self):
        engine, _lines, _points = self._make_engine()
        engine.recompute_map()

        # simulate the plugin/QGIS restarting: drop every Python reference
        # to the engine and its connection, then open a completely fresh
        # connection to the same sidecar file
        del engine

        fresh_conn = topology_db.get_connection(topology_db.sidecar_path_for(OUTPUT))
        try:
            face_ids = topology_db.list_face_ids(fresh_conn, TOPOLOGY_NAME)
            self.assertEqual(len(face_ids), 2)
        finally:
            fresh_conn.close()

    def test_sidecar_path_is_next_to_the_output_geopackage(self):
        engine, _lines, _points = self._make_engine()
        engine.recompute_map()

        expected = topology_db.sidecar_path_for(OUTPUT)
        self.assertTrue(os.path.exists(expected))
