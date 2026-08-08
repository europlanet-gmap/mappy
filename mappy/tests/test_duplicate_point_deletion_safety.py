from qgis.core import QgsFeature, QgsField, QgsGeometry, QgsPointXY, QgsProject, QgsVectorLayer
from qgis.PyQt.QtCore import QVariant

from mappy.engine import EngineConfig, EngineError, ProcessingMapEngine, RecomputeCancelled
from mappy.tests import ExtendedUnitTesting

OUTPUT = "/tmp/zzz_duplicate_point_safety_test.gpkg"


class TestDuplicatePointDeletionSafety(ExtendedUnitTesting):
    """EngineConfig.remove_duplicate_indicator_points (off by default) and
    MapEngine.confirm_destructive_step: recompute_map() must never delete
    points from the user's points layer as a surprise -- see
    drop_duplicate_points_per_polygon in layers.py for the full rationale."""

    def tearDown(self):
        # ProcessingMapEngine (unlike IncrementalMapEngine) holds no
        # external resources of its own -- no close() to call
        project = QgsProject.instance()
        stale = [layer_id for layer_id, layer in project.mapLayers().items() if OUTPUT in layer.dataProvider().dataSourceUri()]
        project.removeMapLayers(stale)
        self.clean_up([OUTPUT])

    def _make_engine(self, remove_duplicate_indicator_points=False):
        self.clean_up([OUTPUT])

        # a single square polygon with two points inside it -- the second
        # point is a per-polygon "duplicate" by drop_duplicate_points_per_polygon's
        # own definition
        lines = QgsVectorLayer("LineString?crs=EPSG:4326", "zzz_dup_lines", "memory")
        f = QgsFeature(lines.fields())
        f.setGeometry(QgsGeometry.fromWkt("LINESTRING(0 0, 1 0, 1 1, 0 1, 0 0)"))
        lines.dataProvider().addFeature(f)
        lines.updateExtents()
        QgsProject.instance().addMapLayer(lines)

        points = QgsVectorLayer("Point?crs=EPSG:4326", "zzz_dup_points", "memory")
        points.dataProvider().addAttributes([QgsField("unit_name", QVariant.String)])
        points.updateFields()
        for xy, unit in (((0.3, 0.3), "UNIT_A"), ((0.7, 0.7), "UNIT_A_DUPLICATE")):
            pf = QgsFeature(points.fields())
            pf.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(*xy)))
            pf["unit_name"] = unit
            points.dataProvider().addFeature(pf)
        points.updateExtents()
        QgsProject.instance().addMapLayer(points)

        config = EngineConfig(
            lines=lines,
            points=points,
            output=OUTPUT,
            out_polygons_layer_name="zzz_dup_final_map",
            units_field="unit_name",
            remove_duplicate_indicator_points=remove_duplicate_indicator_points,
        )
        engine = ProcessingMapEngine(config)
        return engine, points

    def test_duplicate_points_survive_recompute_by_default(self):
        engine, points = self._make_engine(remove_duplicate_indicator_points=False)
        engine.recompute_map()

        self.assertEqual(points.featureCount(), 2, "opt-in is off -- nothing should have been deleted")

    def test_opting_in_without_a_confirm_hook_still_deletes(self):
        """Matches drop_duplicate_points_per_polygon's own documented
        behavior: confirm=None (direct engine use, no GUI wired up) skips
        asking and proceeds -- this engine was constructed directly, not
        through Mappy._make_engine_of_class, so confirm_destructive_step is
        never set."""
        engine, points = self._make_engine(remove_duplicate_indicator_points=True)
        engine.recompute_map()

        self.assertEqual(points.featureCount(), 1)

    def test_opting_in_with_a_declined_confirmation_deletes_nothing(self):
        engine, points = self._make_engine(remove_duplicate_indicator_points=True)
        engine.confirm_destructive_step = lambda message: False

        with self.assertRaises(RecomputeCancelled):
            engine.recompute_map()

        self.assertEqual(points.featureCount(), 2)

    def test_opting_in_with_an_accepted_confirmation_deletes(self):
        engine, points = self._make_engine(remove_duplicate_indicator_points=True)
        seen_messages = []
        engine.confirm_destructive_step = lambda message: (seen_messages.append(message), True)[1]

        engine.recompute_map()

        self.assertEqual(points.featureCount(), 1)
        self.assertEqual(len(seen_messages), 1)
        self.assertIn("1", seen_messages[0])

    def test_confirm_destructive_step_defaults_to_none(self):
        """MapEngine.__init__ leaves this unset for any engine not
        constructed through Mappy -- the GUI is what wires a real dialog on
        top (see Mappy._make_engine_of_class)."""
        engine, _points = self._make_engine()
        self.assertIsNone(engine.confirm_destructive_step)


class TestDuplicatePointsGuardThreshold(ExtendedUnitTesting):
    """drop_duplicate_points_per_polygon refuses outright, without ever
    consulting `confirm`, when the deletion is both large in absolute count
    and a large share of the whole points layer -- the signature of a
    misconfigured recompute (e.g. the wrong lines layer selected)."""

    def _make_polygon_grid(self, n):
        polys = QgsVectorLayer("Polygon", "polys", "memory")
        pr = polys.dataProvider()
        for i in range(n):
            f = QgsFeature()
            f.setGeometry(QgsGeometry.fromWkt(f"POLYGON(({i * 2} 0, {i * 2 + 1} 0, {i * 2 + 1} 1, {i * 2} 1, {i * 2} 0))"))
            pr.addFeature(f)
        polys.updateExtents()
        return polys

    def test_refuses_when_deletion_count_and_fraction_are_both_large(self):
        from mappy.engine.layers import drop_duplicate_points_per_polygon

        polys = self._make_polygon_grid(1)  # one polygon, (0,0)-(1,1)

        pts = QgsVectorLayer("Point", "pts", "memory")
        pr = pts.dataProvider()
        # 6 points all inside the single polygon -> 5 "duplicates" out of 6
        # points total (83%), comfortably past both guard thresholds
        for i in range(6):
            f = QgsFeature()
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(0.1 + i * 0.1, 0.5)))
            pr.addFeature(f)
        pts.updateExtents()

        confirm_calls = []
        with self.assertRaises(EngineError):
            drop_duplicate_points_per_polygon(pts, polys, confirm=lambda message: confirm_calls.append(message) or True)

        self.assertEqual(pts.featureCount(), 6, "nothing should have been deleted")
        self.assertEqual(confirm_calls, [], "the guard must refuse before ever asking for confirmation")

    def test_small_scale_duplicate_stays_below_the_guard(self):
        """A single duplicate pair is exactly the ordinary case this
        function exists to clean up -- it must not trip the guard."""
        from mappy.engine.layers import drop_duplicate_points_per_polygon

        polys = self._make_polygon_grid(1)

        pts = QgsVectorLayer("Point", "pts", "memory")
        pr = pts.dataProvider()
        for xy in ((0.3, 0.3), (0.7, 0.7)):
            f = QgsFeature()
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(*xy)))
            pr.addFeature(f)
        pts.updateExtents()

        deleted = drop_duplicate_points_per_polygon(pts, polys)

        self.assertEqual(len(deleted), 1)
        self.assertEqual(pts.featureCount(), 1)


class TestDuplicatePointsEditBufferStaging(ExtendedUnitTesting):
    """When points_layer is already mid-edit-session when called, the
    deletion must be staged into that existing session rather than
    force-committed -- committing here would also finalize whatever
    unrelated pending edits the caller doesn't know about."""

    def test_deletion_is_left_uncommitted_if_the_layer_was_already_editable(self):
        from mappy.engine.layers import drop_duplicate_points_per_polygon

        polys = QgsVectorLayer("Polygon", "polys", "memory")
        pr = polys.dataProvider()
        f = QgsFeature()
        f.setGeometry(QgsGeometry.fromWkt("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"))
        pr.addFeature(f)
        polys.updateExtents()

        pts = QgsVectorLayer("Point", "pts", "memory")
        pr = pts.dataProvider()
        for xy in ((0.3, 0.3), (0.7, 0.7)):
            pf = QgsFeature()
            pf.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(*xy)))
            pr.addFeature(pf)
        pts.updateExtents()

        pts.startEditing()
        deleted = drop_duplicate_points_per_polygon(pts, polys)

        self.assertEqual(len(deleted), 1)
        self.assertTrue(pts.isEditable(), "the pre-existing edit session must still be open, not force-committed")
        self.assertTrue(pts.isModified())

        pts.rollBack()
        self.assertEqual(pts.featureCount(), 2, "rolling back the never-committed session must restore the point")
