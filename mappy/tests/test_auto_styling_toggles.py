from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsCategorizedSymbolRenderer,
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
)

from mappy.engine import EngineConfig, ProcessingMapEngine
from mappy.tests import ExtendedUnitTesting


class TestAutoStylingToggles(ExtendedUnitTesting):
    """auto_color_polygons/auto_color_points/auto_label_polygons/
    auto_label_points let a user turn off this plugin's automatic
    categorized-coloring/labeling independently for the output polygons and
    the indicator points, instead of it running unconditionally on every
    assign_unit()/recompute_map()."""

    def _make_engine(self, **config_overrides):
        points = QgsVectorLayer("Point?crs=EPSG:4326", "zzz_toggle_points", "memory")
        points.dataProvider().addAttributes([QgsField("unit_name", QVariant.String)])
        points.updateFields()
        QgsProject.instance().addMapLayer(points)

        polygons = QgsVectorLayer("Polygon?crs=EPSG:4326", "zzz_toggle_final_map", "memory")
        polygons.dataProvider().addAttributes([QgsField("unit_name", QVariant.String)])
        polygons.updateFields()
        QgsProject.instance().addMapLayer(polygons)

        f1 = QgsFeature(polygons.fields())
        f1.setGeometry(QgsGeometry.fromWkt("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"))
        polygons.dataProvider().addFeature(f1)

        pf = QgsFeature(points.fields())
        pf.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(0.5, 0.5)))
        points.dataProvider().addFeature(pf)
        points.updateExtents()

        config = EngineConfig(
            points=points,
            units_field="unit_name",
            output="/tmp/zzz_engine_auto_styling_toggles_test.gpkg",
            out_polygons_layer_name="zzz_toggle_final_map",
            **config_overrides,
        )
        engine = ProcessingMapEngine(config)
        return engine, points, polygons

    def _assign(self, engine, polygons):
        from unittest.mock import patch

        with patch.object(engine, "get_polygons_layer", return_value=polygons):
            matched = polygons.getFeature(1)
            target = engine.find_indicator_for_polygon(matched)
            engine.assign_unit(matched, target, QgsPointXY(0.5, 0.5), "Basalt")

    def test_defaults_are_all_enabled(self):
        config = EngineConfig()
        self.assertTrue(config.auto_color_polygons)
        self.assertTrue(config.auto_color_points)
        self.assertTrue(config.auto_label_polygons)
        self.assertTrue(config.auto_label_points)

    def test_all_enabled_styles_and_labels_both_layers(self):
        engine, points, polygons = self._make_engine()
        self._assign(engine, polygons)

        self.assertIsInstance(polygons.renderer(), QgsCategorizedSymbolRenderer)
        self.assertIsInstance(points.renderer(), QgsCategorizedSymbolRenderer)
        self.assertIsNotNone(polygons.labeling())
        self.assertIsNotNone(points.labeling())

    def test_auto_color_polygons_disabled_leaves_polygon_renderer_untouched(self):
        engine, points, polygons = self._make_engine(auto_color_polygons=False)

        self._assign(engine, polygons)

        self.assertNotIsInstance(polygons.renderer(), QgsCategorizedSymbolRenderer)
        # points styling is independent -- still happens
        self.assertIsInstance(points.renderer(), QgsCategorizedSymbolRenderer)

    def test_auto_color_points_disabled_leaves_points_renderer_untouched(self):
        engine, points, polygons = self._make_engine(auto_color_points=False)

        self._assign(engine, polygons)

        self.assertNotIsInstance(points.renderer(), QgsCategorizedSymbolRenderer)
        # polygon styling is independent -- still happens
        self.assertIsInstance(polygons.renderer(), QgsCategorizedSymbolRenderer)

    def test_auto_label_polygons_disabled_skips_polygon_labels(self):
        engine, points, polygons = self._make_engine(auto_label_polygons=False)

        self._assign(engine, polygons)

        self.assertIsNone(polygons.labeling())
        self.assertIsNotNone(points.labeling())

    def test_auto_label_points_disabled_skips_point_labels(self):
        engine, points, polygons = self._make_engine(auto_label_points=False)

        self._assign(engine, polygons)

        self.assertIsNone(points.labeling())
        self.assertIsNotNone(polygons.labeling())

    def test_color_data_stays_synced_even_with_both_color_toggles_off(self):
        # disabling the *rendering* toggles must not disable the underlying
        # persisted color bookkeeping -- other features (AssignUnitDialog's
        # swatches, the other layer's own styling) still depend on it
        engine, points, polygons = self._make_engine(auto_color_polygons=False, auto_color_points=False)

        from unittest.mock import patch

        with patch.object(engine, "get_polygons_layer", return_value=polygons):
            matched = polygons.getFeature(1)
            target = engine.find_indicator_for_polygon(matched)
            engine.assign_unit(matched, target, QgsPointXY(0.5, 0.5), "Basalt", color="#123456")

        colors = {f["unit_name"]: f["color"] for f in points.getFeatures()}
        self.assertEqual(colors["Basalt"], "#123456")
