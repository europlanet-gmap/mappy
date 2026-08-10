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

from mappy.engine import EngineError
from mappy.tests import ExtendedUnitTesting


class TestAssignUnitToSelection(ExtendedUnitTesting):
    """Bulk-assign path: pressing the Assign Unit button while the polygon
    layer already has a selection applies one dialog pick to every selected
    polygon instead of waiting for a canvas click. Single-polygon,
    click-driven behavior is covered separately in
    test_assign_unit_map_tool.py."""

    def _make_setup(self):
        from mappy.qgismappy import Mappy

        mappy = Mappy.instance
        dock = mappy.config_dock
        dock.get_widget_by_name("auto_recompute_on_assign_unit").setChecked(False)

        points = QgsVectorLayer("Point?crs=EPSG:4326", "zzz_bulk_points", "memory")
        points.dataProvider().addAttributes([QgsField("unit_name", QVariant.String)])
        points.updateFields()
        QgsProject.instance().addMapLayer(points)

        polygons = QgsVectorLayer("Polygon?crs=EPSG:4326", "zzz_bulk_final_map", "memory")
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

        pf1 = QgsFeature(points.fields())
        pf1.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(0.5, 0.5)))
        pf1["unit_name"] = "UNIT_A"
        points.dataProvider().addFeature(pf1)
        points.updateExtents()

        dock.get_widget_by_name("points").setLayer(points)
        dock.get_widget_by_name("units_field").setLayer(points)
        dock.get_widget_by_name("units_field").setField("unit_name")

        from mappy.mappy_utils import restoreWidgetContent

        restoreWidgetContent(dock.get_widget_by_name("output"), "/tmp/zzz_gui_assign_unit_bulk_test.gpkg")
        dock.get_widget_by_name("out_polygons_layer_name").setText("zzz_bulk_final_map")

        polygons.selectAll()
        return mappy, points, polygons

    def test_toggle_with_selection_runs_bulk_assign_not_the_map_tool(self):
        mappy, points, polygons = self._make_setup()

        with (
            patch.object(mappy.engine, "get_polygons_layer", return_value=polygons),
            patch.object(mappy, "assign_unit_to_selection") as bulk_assign,
        ):
            mappy.toggle_assign_unit_tool(True)

        bulk_assign.assert_called_once()
        called_layer, called_features = bulk_assign.call_args[0]
        self.assertIs(called_layer, polygons)
        self.assertEqual({f.id() for f in called_features}, {f.id() for f in polygons.getFeatures()})
        # a one-shot bulk action, not a lingering "waiting for a click" mode
        self.assertFalse(mappy.assign_unit_action.isChecked())

    def test_toggle_without_selection_still_activates_the_map_tool(self):
        # iface.mapCanvas() is a MagicMock in this headless test env, which
        # a real QgsMapTool subclass refuses as a parent -- patch the tool
        # class itself to verify the code path taken, not real Qt canvas
        # machinery (out of scope here; see test_assign_unit_map_tool.py
        # for the click-driven flow this falls back to).
        mappy, points, polygons = self._make_setup()
        polygons.removeSelection()
        mappy.assign_unit_tool = None

        with (
            patch.object(mappy.engine, "get_polygons_layer", return_value=polygons),
            patch.object(mappy, "assign_unit_to_selection") as bulk_assign,
            patch("mappy.assign_unit_map_tool.AssignUnitMapTool") as tool_cls,
        ):
            mappy.toggle_assign_unit_tool(True)

        bulk_assign.assert_not_called()
        tool_cls.assert_called_once_with(mappy.iface.mapCanvas(), mappy)
        mappy.iface.mapCanvas().setMapTool.assert_called_once_with(tool_cls.return_value)

        mappy.toggle_assign_unit_tool(False)
        mappy.assign_unit_tool = None

    def test_opens_dialog_once_and_writes_every_selected_polygon(self):
        mappy, points, polygons = self._make_setup()
        features = list(polygons.getFeatures())

        with (
            patch.object(mappy.engine, "list_existing_units", return_value=["UNIT_A"]),
            patch.object(mappy.engine, "get_color_table", return_value={"UNIT_A": "#aaaaaa"}),
            patch.object(mappy.engine, "find_indicator_for_polygon", return_value=None),
            patch.object(mappy.engine, "assign_unit") as assign_unit,
            patch(
                "mappy.assign_unit_dialog.AssignUnitDialog.getUnit", return_value=("UNIT_B", "#123456", {}, True)
            ) as get_unit,
        ):
            mappy.assign_unit_to_selection(polygons, features)

        get_unit.assert_called_once()
        self.assertEqual(assign_unit.call_count, 2)
        assigned_polygon_ids = {call.args[0].id() for call in assign_unit.call_args_list}
        self.assertEqual(assigned_polygon_ids, {f.id() for f in features})
        for call in assign_unit.call_args_list:
            self.assertEqual(call.args[3], "UNIT_B")
            self.assertEqual(call.kwargs, {"color": "#123456", "changed_colors": {}})

    def test_creates_indicator_inside_the_polygon_when_none_exists(self):
        mappy, points, polygons = self._make_setup()
        feature = next(polygons.getFeatures())

        with (
            patch.object(mappy.engine, "list_existing_units", return_value=[]),
            patch.object(mappy.engine, "get_color_table", return_value={}),
            patch.object(mappy.engine, "find_indicator_for_polygon", return_value=None),
            patch.object(mappy.engine, "assign_unit") as assign_unit,
            patch("mappy.assign_unit_dialog.AssignUnitDialog.getUnit", return_value=("UNIT_C", None, {}, True)),
        ):
            mappy.assign_unit_to_selection(polygons, [feature])

        click_point = assign_unit.call_args.args[2]
        self.assertTrue(feature.geometry().contains(QgsGeometry.fromPointXY(click_point)))

    def test_prefills_dialog_only_when_selection_shares_one_unit(self):
        mappy, points, polygons = self._make_setup()
        features = list(polygons.getFeatures())

        with (
            patch.object(mappy.engine, "list_existing_units", return_value=["UNIT_A"]),
            patch.object(mappy.engine, "get_color_table", return_value={}),
            patch.object(mappy.engine, "find_indicator_for_polygon", return_value=None),
            patch.object(mappy.engine, "assign_unit"),
            patch(
                "mappy.assign_unit_dialog.AssignUnitDialog.getUnit", return_value=("", None, {}, False)
            ) as get_unit,
        ):
            mappy.assign_unit_to_selection(polygons, features)

        get_unit.assert_called_once_with(
            mappy.iface.mainWindow(), ["UNIT_A"], "UNIT_A", {}, title="Assign unit to 2 selected polygons"
        )

    def test_does_not_prefill_when_selection_has_mixed_units(self):
        mappy, points, polygons = self._make_setup()
        features = list(polygons.getFeatures())
        features[1]["unit_name"] = "UNIT_B"
        polygons.dataProvider().changeAttributeValues({features[1].id(): {1: "UNIT_B"}})

        with (
            patch.object(mappy.engine, "list_existing_units", return_value=["UNIT_A", "UNIT_B"]),
            patch.object(mappy.engine, "get_color_table", return_value={}),
            patch.object(mappy.engine, "find_indicator_for_polygon", return_value=None),
            patch.object(mappy.engine, "assign_unit"),
            patch(
                "mappy.assign_unit_dialog.AssignUnitDialog.getUnit", return_value=("", None, {}, False)
            ) as get_unit,
        ):
            mappy.assign_unit_to_selection(polygons, features)

        self.assertIsNone(get_unit.call_args.args[2])

    def test_cancelling_the_dialog_does_not_call_assign_unit(self):
        mappy, points, polygons = self._make_setup()
        features = list(polygons.getFeatures())

        with (
            patch.object(mappy.engine, "list_existing_units", return_value=[]),
            patch.object(mappy.engine, "get_color_table", return_value={}),
            patch.object(mappy.engine, "find_indicator_for_polygon", return_value=None),
            patch.object(mappy.engine, "assign_unit") as assign_unit,
            patch("mappy.assign_unit_dialog.AssignUnitDialog.getUnit", return_value=("", None, {}, False)),
        ):
            mappy.assign_unit_to_selection(polygons, features)

        assign_unit.assert_not_called()

    def test_recompute_runs_once_not_once_per_polygon(self):
        mappy, points, polygons = self._make_setup()
        dock = mappy.config_dock
        dock.get_widget_by_name("auto_recompute_on_assign_unit").setChecked(True)
        features = list(polygons.getFeatures())

        seen_auto_recompute_during_loop = []

        def record_and_noop(*args, **kwargs):
            seen_auto_recompute_during_loop.append(mappy.engine.config.auto_recompute_on_assign_unit)

        with (
            patch.object(mappy.engine, "list_existing_units", return_value=["UNIT_A"]),
            patch.object(mappy.engine, "get_color_table", return_value={}),
            patch.object(mappy.engine, "find_indicator_for_polygon", return_value=None),
            patch.object(mappy.engine, "assign_unit", side_effect=record_and_noop),
            patch.object(mappy.engine, "recompute_map") as recompute_map,
            patch("mappy.assign_unit_dialog.AssignUnitDialog.getUnit", return_value=("UNIT_B", None, {}, True)),
        ):
            mappy._refresh_engine_config()
            mappy.assign_unit_to_selection(polygons, features)

        # assign_unit() itself must never see auto-recompute enabled during
        # the loop -- otherwise it would trigger its own recompute per call
        self.assertEqual(seen_auto_recompute_during_loop, [False, False])
        recompute_map.assert_called_once()
        # the setting is restored once the loop is done
        self.assertTrue(mappy.engine.config.auto_recompute_on_assign_unit)

        dock.get_widget_by_name("auto_recompute_on_assign_unit").setChecked(False)

    def test_pushes_summary_message_with_count_when_auto_recompute_disabled(self):
        mappy, points, polygons = self._make_setup()
        features = list(polygons.getFeatures())

        with (
            patch.object(mappy.engine, "list_existing_units", return_value=["UNIT_A"]),
            patch.object(mappy.engine, "get_color_table", return_value={}),
            patch.object(mappy.engine, "find_indicator_for_polygon", return_value=None),
            patch.object(mappy.engine, "assign_unit"),
            patch("mappy.assign_unit_dialog.AssignUnitDialog.getUnit", return_value=("UNIT_B", None, {}, True)),
        ):
            mappy.assign_unit_to_selection(polygons, features)

        mappy.iface.messageBar().pushInfo.assert_called_with(
            "Mappy",
            "Unit assigned to 2 polygons. Recompute the map to update the point/polygon join, dangle cleanup, etc.",
        )

    def test_stops_and_alerts_on_engine_error_mid_loop(self):
        mappy, points, polygons = self._make_setup()
        features = list(polygons.getFeatures())

        with (
            patch.object(mappy.engine, "list_existing_units", return_value=["UNIT_A"]),
            patch.object(mappy.engine, "get_color_table", return_value={}),
            patch.object(mappy.engine, "find_indicator_for_polygon", return_value=None),
            patch.object(mappy.engine, "assign_unit", side_effect=[None, EngineError("boom")]),
            patch.object(mappy, "alert_box") as alert_box,
            patch("mappy.assign_unit_dialog.AssignUnitDialog.getUnit", return_value=("UNIT_B", None, {}, True)),
        ):
            mappy.assign_unit_to_selection(polygons, features)

        alert_box.assert_called_once_with("Error", "Stopped after 1 of 2 polygons: boom")
