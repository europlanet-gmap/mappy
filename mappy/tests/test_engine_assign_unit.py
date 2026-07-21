from unittest.mock import patch

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
)

from mappy.engine import EngineConfig, ProcessingMapEngine
from mappy.tests import ExtendedUnitTesting


class TestEngineAssignUnit(ExtendedUnitTesting):
    """Engine-level behavior of ProcessingMapEngine.assign_unit and its
    supporting query methods -- exercised directly against the engine, with
    no Mappy/dock/iface/AssignUnitDialog involved (that GUI glue is covered
    separately in test_assign_unit_map_tool.py)."""

    def _make_engine(self):
        points = QgsVectorLayer("Point?crs=EPSG:4326", "zzz_engine_points", "memory")
        points.dataProvider().addAttributes([QgsField("unit_name", QVariant.String)])
        points.updateFields()
        QgsProject.instance().addMapLayer(points)

        # mirrors the real final_map layer, which carries a copy of the
        # units_field attribute from the join done at map construction time
        polygons = QgsVectorLayer("Polygon?crs=EPSG:4326", "zzz_engine_final_map", "memory")
        polygons.dataProvider().addAttributes([QgsField("unit_name", QVariant.String)])
        polygons.updateFields()
        QgsProject.instance().addMapLayer(polygons)

        f1 = QgsFeature(polygons.fields())
        f1.setGeometry(QgsGeometry.fromWkt("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"))
        f1["unit_name"] = "UNIT_A"
        polygons.dataProvider().addFeature(f1)

        f2 = QgsFeature(polygons.fields())
        f2.setGeometry(QgsGeometry.fromWkt("POLYGON((2 0, 3 0, 3 1, 2 1, 2 0))"))
        polygons.dataProvider().addFeature(f2)

        # existing indicator point inside polygon 1, already labeled UNIT_A
        pf = QgsFeature(points.fields())
        pf.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(0.5, 0.5)))
        pf["unit_name"] = "UNIT_A"
        points.dataProvider().addFeature(pf)
        points.updateExtents()

        config = EngineConfig(
            points=points,
            units_field="unit_name",
            output="/tmp/zzz_engine_assign_unit_test.gpkg",
            out_polygons_layer_name="zzz_engine_final_map",
        )
        engine = ProcessingMapEngine(config)

        return engine, points, polygons

    def test_updates_existing_point_in_clicked_polygon(self):
        engine, points, polygons = self._make_engine()

        with (
            patch.object(engine, "get_polygons_layer", return_value=polygons),
            patch.object(engine, "recompute_map") as recompute,
        ):
            matched = engine.find_polygon_at_point(QgsPointXY(0.5, 0.5))
            target = engine.find_indicator_for_polygon(matched, near_point=QgsPointXY(0.5, 0.5))
            engine.assign_unit(matched, target, QgsPointXY(0.5, 0.5), "UNIT_B", color="#123456")

        # auto-recompute is disabled by default, so assigning a unit must
        # not trigger a full map regeneration
        recompute.assert_not_called()
        values = [f["unit_name"] for f in points.getFeatures()]
        self.assertEqual(values, ["UNIT_B"])

        # the clicked polygon's own attribute is updated directly, in sync
        # with the point, even without a full recompute
        poly_values = [
            f["unit_name"]
            for f in polygons.getFeatures()
            if f.geometry().intersects(QgsGeometry.fromPointXY(QgsPointXY(0.5, 0.5)))
        ]
        self.assertEqual(poly_values, ["UNIT_B"])
        self.assertFalse(polygons.isEditable())

    def test_creates_new_point_when_polygon_has_none(self):
        engine, points, polygons = self._make_engine()

        with (
            patch.object(engine, "get_polygons_layer", return_value=polygons),
            patch.object(engine, "recompute_map") as recompute,
        ):
            matched = engine.find_polygon_at_point(QgsPointXY(2.5, 0.5))
            target = engine.find_indicator_for_polygon(matched, near_point=QgsPointXY(2.5, 0.5))
            engine.assign_unit(matched, target, QgsPointXY(2.5, 0.5), "UNIT_C", color="#654321")

        recompute.assert_not_called()
        values = sorted(f["unit_name"] for f in points.getFeatures())
        self.assertEqual(values, ["UNIT_A", "UNIT_C"])
        self.assertEqual(points.featureCount(), 2)

    def test_recomputes_map_when_setting_enabled(self):
        engine, points, polygons = self._make_engine()
        engine.config.auto_recompute_on_assign_unit = True

        with (
            patch.object(engine, "get_polygons_layer", return_value=polygons),
            patch.object(engine, "recompute_map") as recompute,
        ):
            matched = engine.find_polygon_at_point(QgsPointXY(0.5, 0.5))
            target = engine.find_indicator_for_polygon(matched, near_point=QgsPointXY(0.5, 0.5))
            engine.assign_unit(matched, target, QgsPointXY(0.5, 0.5), "UNIT_B", color="#123456")

        recompute.assert_called_once()

    def test_recoloring_a_different_unit_during_the_dialog_still_propagates(self):
        # regression test: a color changed for a unit other than the one
        # finally confirmed (e.g. the caller tweaked an existing unit's
        # color while the user was browsing before picking a different one)
        # must still be written to the points layer, not dropped
        engine, points, polygons = self._make_engine()

        with (
            patch.object(engine, "get_polygons_layer", return_value=polygons),
            patch.object(engine, "recompute_map"),
        ):
            matched = engine.find_polygon_at_point(QgsPointXY(2.5, 0.5))
            target = engine.find_indicator_for_polygon(matched, near_point=QgsPointXY(2.5, 0.5))
            engine.assign_unit(
                matched, target, QgsPointXY(2.5, 0.5), "UNIT_D", color="#dddddd", changed_colors={"UNIT_A": "#aaaaaa"}
            )

        colors = {f["unit_name"]: f["color"] for f in points.getFeatures()}
        self.assertEqual(colors["UNIT_D"], "#dddddd")
        self.assertEqual(colors["UNIT_A"], "#aaaaaa")

    def test_recoloring_the_confirmed_existing_unit_actually_sticks(self):
        # regression test: writing the chosen color to points_layer *before*
        # calling sync_unit_colors made sync_unit_colors's baseline already
        # reflect the new color, while the polygon layer's renderer (not yet
        # touched) still showed the old one -- that mismatch was misread as
        # a manual Symbology override on the polygon layer, which then "won"
        # and silently reverted the just-applied change back to the old color.
        engine, points, polygons = self._make_engine()

        with (
            patch.object(engine, "get_polygons_layer", return_value=polygons),
            patch.object(engine, "recompute_map"),
        ):
            matched = engine.find_polygon_at_point(QgsPointXY(0.5, 0.5))
            target = engine.find_indicator_for_polygon(matched, near_point=QgsPointXY(0.5, 0.5))
            engine.assign_unit(matched, target, QgsPointXY(0.5, 0.5), "UNIT_A", color="#ff0000")

        with (
            patch.object(engine, "get_polygons_layer", return_value=polygons),
            patch.object(engine, "recompute_map"),
        ):
            matched = engine.find_polygon_at_point(QgsPointXY(0.5, 0.5))
            target = engine.find_indicator_for_polygon(matched, near_point=QgsPointXY(0.5, 0.5))
            engine.assign_unit(matched, target, QgsPointXY(0.5, 0.5), "UNIT_A", color="#0000ff")

        for f in points.getFeatures():
            self.assertEqual(f["color"], "#0000ff")

        renderer = polygons.renderer()
        index = renderer.categoryIndexForValue("UNIT_A")
        categories = renderer.categories()
        category = categories[index]
        symbol = category.symbol()
        self.assertEqual(symbol.color().name(), "#0000ff")

    def test_click_outside_any_polygon_does_nothing(self):
        engine, points, polygons = self._make_engine()

        with patch.object(engine, "get_polygons_layer", return_value=polygons):
            matched = engine.find_polygon_at_point(QgsPointXY(10, 10))

        self.assertIsNone(matched)
        self.assertEqual(points.featureCount(), 1)
