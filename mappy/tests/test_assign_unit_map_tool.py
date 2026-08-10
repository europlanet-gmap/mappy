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

from mappy.tests import ExtendedUnitTesting


class TestAssignUnitMapToolClicks(ExtendedUnitTesting):
    """GUI-glue behavior of the assign-unit map tool: a plain click drives
    Mappy.assign_unit_at_point() (immediate single-polygon dialog, same as
    before multi-polygon selections existed); Ctrl+click instead builds a
    multi-polygon selection via Mappy.add_polygon_to_assign_selection(),
    and a right-click applies one dialog pick to all of it via
    Mappy.finish_assign_unit_selection() (see
    test_assign_unit_to_selection.py for that dialog-driving behavior, and
    test_engine_assign_unit.py for what assign_unit() actually writes)."""

    def _make_setup(self):
        from mappy.qgismappy import Mappy

        mappy = Mappy.instance
        dock = mappy.config_dock

        # tests run against the shared dock singleton -- start every test
        # from the documented default (auto-recompute off) regardless of
        # what an earlier test in this run left it as
        dock.get_widget_by_name("auto_recompute_on_assign_unit").setChecked(False)

        points = QgsVectorLayer("Point?crs=EPSG:4326", "zzz_gui_points", "memory")
        points.dataProvider().addAttributes([QgsField("unit_name", QVariant.String)])
        points.updateFields()
        QgsProject.instance().addMapLayer(points)

        polygons = QgsVectorLayer("Polygon?crs=EPSG:4326", "zzz_gui_final_map", "memory")
        polygons.dataProvider().addAttributes([QgsField("unit_name", QVariant.String)])
        polygons.updateFields()
        QgsProject.instance().addMapLayer(polygons)

        f1 = QgsFeature(polygons.fields())
        f1.setGeometry(QgsGeometry.fromWkt("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"))
        f1["unit_name"] = "UNIT_A"
        polygons.dataProvider().addFeature(f1)

        f2 = QgsFeature(polygons.fields())
        f2.setGeometry(QgsGeometry.fromWkt("POLYGON((2 0, 3 0, 3 1, 2 1, 2 0))"))
        f2["unit_name"] = "UNIT_A"
        polygons.dataProvider().addFeature(f2)

        pf = QgsFeature(points.fields())
        pf.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(0.5, 0.5)))
        pf["unit_name"] = "UNIT_A"
        points.dataProvider().addFeature(pf)
        points.updateExtents()

        mappy.iface.mapCanvas().mapSettings().destinationCrs.return_value = polygons.crs()

        dock.get_widget_by_name("points").setLayer(points)
        dock.get_widget_by_name("units_field").setLayer(points)
        dock.get_widget_by_name("units_field").setField("unit_name")

        from mappy.mappy_utils import restoreWidgetContent

        restoreWidgetContent(dock.get_widget_by_name("output"), "/tmp/zzz_gui_assign_unit_test.gpkg")
        dock.get_widget_by_name("out_polygons_layer_name").setText("zzz_gui_final_map")

        polygons.removeSelection()
        return mappy, points, polygons

    # -- plain click: immediate single-polygon assign --------------------

    def test_plain_click_opens_dialog_with_engine_supplied_context(self):
        mappy, points, polygons = self._make_setup()
        matched_feature = next(polygons.getFeatures())
        target_feature = next(points.getFeatures())

        with (
            patch.object(mappy.engine, "get_polygons_layer", return_value=polygons),
            patch.object(mappy.engine, "find_polygon_at_point", return_value=matched_feature) as find_polygon,
            patch.object(mappy.engine, "find_indicator_for_polygon", return_value=target_feature) as find_indicator,
            patch.object(mappy.engine, "list_existing_units", return_value=["UNIT_A"]) as list_units,
            patch.object(mappy.engine, "get_color_table", return_value={"UNIT_A": "#aaaaaa"}) as color_table,
            patch.object(mappy.engine, "assign_unit") as assign_unit,
            patch(
                "mappy.assign_unit_dialog.AssignUnitDialog.getUnit", return_value=("UNIT_B", "#123456", {}, True)
            ) as get_unit,
        ):
            mappy.assign_unit_at_point(QgsPointXY(0.5, 0.5))

        find_polygon.assert_called_once()
        find_indicator.assert_called_once_with(matched_feature, near_point=QgsPointXY(0.5, 0.5))
        list_units.assert_called_once()
        color_table.assert_called_once()
        get_unit.assert_called_once_with(mappy.iface.mainWindow(), ["UNIT_A"], "UNIT_A", {"UNIT_A": "#aaaaaa"})

        assign_unit.assert_called_once_with(
            matched_feature, target_feature, QgsPointXY(0.5, 0.5), "UNIT_B", color="#123456", changed_colors={}
        )

    def test_plain_click_with_no_polygon_at_location_skips_dialog_and_assign(self):
        mappy, points, polygons = self._make_setup()

        with (
            patch.object(mappy.engine, "get_polygons_layer", return_value=polygons),
            patch.object(mappy.engine, "find_polygon_at_point", return_value=None),
            patch("mappy.assign_unit_dialog.AssignUnitDialog.getUnit") as get_unit,
            patch.object(mappy.engine, "assign_unit") as assign_unit,
        ):
            mappy.assign_unit_at_point(QgsPointXY(10, 10))

        get_unit.assert_not_called()
        assign_unit.assert_not_called()

    def test_plain_click_cancelling_the_dialog_does_not_call_assign_unit(self):
        mappy, points, polygons = self._make_setup()
        matched_feature = next(polygons.getFeatures())

        with (
            patch.object(mappy.engine, "get_polygons_layer", return_value=polygons),
            patch.object(mappy.engine, "find_polygon_at_point", return_value=matched_feature),
            patch.object(mappy.engine, "find_indicator_for_polygon", return_value=None),
            patch.object(mappy.engine, "list_existing_units", return_value=[]),
            patch.object(mappy.engine, "get_color_table", return_value={}),
            patch.object(mappy.engine, "assign_unit") as assign_unit,
            patch("mappy.assign_unit_dialog.AssignUnitDialog.getUnit", return_value=("", None, {}, False)),
        ):
            mappy.assign_unit_at_point(QgsPointXY(0.5, 0.5))

        assign_unit.assert_not_called()

    def test_plain_click_engine_error_on_missing_map_shows_alert_box(self):
        mappy, points, polygons = self._make_setup()
        from mappy.engine import EngineError

        with (
            patch.object(mappy.engine, "get_polygons_layer", side_effect=EngineError("The map hasn't been generated yet.")),
            patch.object(mappy, "alert_box") as alert_box,
        ):
            mappy.assign_unit_at_point(QgsPointXY(0.5, 0.5))

        alert_box.assert_called_once_with("Error", "The map hasn't been generated yet.")

    def test_plain_click_pushes_recompute_hint_when_auto_recompute_disabled(self):
        mappy, points, polygons = self._make_setup()
        matched_feature = next(polygons.getFeatures())
        target_feature = next(points.getFeatures())

        with (
            patch.object(mappy.engine, "get_polygons_layer", return_value=polygons),
            patch.object(mappy.engine, "find_polygon_at_point", return_value=matched_feature),
            patch.object(mappy.engine, "find_indicator_for_polygon", return_value=target_feature),
            patch.object(mappy.engine, "list_existing_units", return_value=["UNIT_A"]),
            patch.object(mappy.engine, "get_color_table", return_value={}),
            patch.object(mappy.engine, "assign_unit"),
            patch("mappy.assign_unit_dialog.AssignUnitDialog.getUnit", return_value=("UNIT_B", "#123456", {}, True)),
        ):
            mappy.assign_unit_at_point(QgsPointXY(0.5, 0.5))

        mappy.iface.messageBar().pushInfo.assert_called_with(
            "Mappy", "Unit assigned. Recompute the map to update the point/polygon join, dangle cleanup, etc."
        )

    # -- Ctrl+click: build a multi-polygon selection ----------------------

    def test_ctrl_click_adds_the_clicked_polygon_to_selection(self):
        mappy, points, polygons = self._make_setup()
        feature_a = polygons.getFeature(1)

        with (
            patch.object(mappy.engine, "get_polygons_layer", return_value=polygons),
            patch.object(mappy.engine, "find_polygon_at_point", return_value=feature_a),
            patch.object(mappy.engine, "assign_unit") as assign_unit,
            patch("mappy.assign_unit_dialog.AssignUnitDialog.getUnit") as get_unit,
        ):
            mappy.add_polygon_to_assign_selection(QgsPointXY(0.5, 0.5))

        self.assertEqual(polygons.selectedFeatureIds(), [feature_a.id()])
        # no immediate dialog/assign -- only building the selection
        get_unit.assert_not_called()
        assign_unit.assert_not_called()

    def test_ctrl_click_toggles_an_already_selected_polygon_off(self):
        mappy, points, polygons = self._make_setup()
        feature_a, feature_b = polygons.getFeature(1), polygons.getFeature(2)
        polygons.selectByIds([feature_a.id(), feature_b.id()])

        with (
            patch.object(mappy.engine, "get_polygons_layer", return_value=polygons),
            patch.object(mappy.engine, "find_polygon_at_point", return_value=feature_a),
        ):
            mappy.add_polygon_to_assign_selection(QgsPointXY(0.5, 0.5))

        self.assertEqual(polygons.selectedFeatureIds(), [feature_b.id()])

    def test_ctrl_click_on_empty_space_is_a_noop(self):
        mappy, points, polygons = self._make_setup()
        feature_a = polygons.getFeature(1)
        polygons.select(feature_a.id())

        with (
            patch.object(mappy.engine, "get_polygons_layer", return_value=polygons),
            patch.object(mappy.engine, "find_polygon_at_point", return_value=None),
        ):
            mappy.add_polygon_to_assign_selection(QgsPointXY(10, 10))

        self.assertEqual(polygons.selectedFeatureIds(), [feature_a.id()])

    def test_ctrl_click_engine_error_shows_alert_box(self):
        mappy, points, polygons = self._make_setup()
        from mappy.engine import EngineError

        with (
            patch.object(mappy.engine, "get_polygons_layer", side_effect=EngineError("The map hasn't been generated yet.")),
            patch.object(mappy, "alert_box") as alert_box,
        ):
            mappy.add_polygon_to_assign_selection(QgsPointXY(0.5, 0.5))

        alert_box.assert_called_once_with("Error", "The map hasn't been generated yet.")

    # -- right-click: close the Ctrl+click selection ----------------------

    def test_right_click_with_nothing_selected_is_a_noop(self):
        mappy, points, polygons = self._make_setup()

        with (
            patch.object(mappy.engine, "get_polygons_layer", return_value=polygons),
            patch.object(mappy, "assign_unit_to_selection") as bulk_assign,
        ):
            mappy.finish_assign_unit_selection()

        bulk_assign.assert_not_called()

    def test_right_click_applies_the_current_selection(self):
        mappy, points, polygons = self._make_setup()
        feature_a, feature_b = polygons.getFeature(1), polygons.getFeature(2)
        polygons.selectByIds([feature_a.id(), feature_b.id()])

        with (
            patch.object(mappy.engine, "get_polygons_layer", return_value=polygons),
            patch.object(mappy, "assign_unit_to_selection") as bulk_assign,
        ):
            mappy.finish_assign_unit_selection()

        bulk_assign.assert_called_once()
        called_layer, called_features = bulk_assign.call_args[0]
        self.assertIs(called_layer, polygons)
        self.assertEqual({f.id() for f in called_features}, {feature_a.id(), feature_b.id()})

    # -- deactivating the tool abandons an unfinished selection -----------

    def test_deactivating_the_tool_clears_an_unfinished_selection(self):
        mappy, points, polygons = self._make_setup()
        feature_a = polygons.getFeature(1)
        polygons.select(feature_a.id())

        with patch.object(mappy.engine, "get_polygons_layer", return_value=polygons):
            mappy.on_assign_unit_tool_deactivated()

        self.assertEqual(polygons.selectedFeatureCount(), 0)
        self.assertFalse(mappy.assign_unit_action.isChecked())
