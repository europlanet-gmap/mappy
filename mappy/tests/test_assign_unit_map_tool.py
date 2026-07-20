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


class TestAssignUnitAtPoint(ExtendedUnitTesting):
    def _make_setup(self):
        from mappy.qgismappy import Mappy

        mappy = Mappy.instance
        dock = mappy.config_dock

        # tests run against the shared dock singleton -- start every test
        # from the documented default (auto-recompute off) regardless of
        # what an earlier test in this run left it as
        dock.get_widget_by_name("auto_recompute_on_assign_unit").setChecked(False)

        points = QgsVectorLayer("Point?crs=EPSG:4326", "zzz_points", "memory")
        points.dataProvider().addAttributes([QgsField("unit_name", QVariant.String)])
        points.updateFields()
        QgsProject.instance().addMapLayer(points)

        # mirrors the real final_map layer, which carries a copy of the
        # units_field attribute from the join done at map construction time
        polygons = QgsVectorLayer("Polygon?crs=EPSG:4326", "zzz_final_map", "memory")
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

        mappy.iface.mapCanvas().mapSettings().destinationCrs.return_value = polygons.crs()

        dock.get_widget_by_name("points").setLayer(points)
        dock.get_widget_by_name("units_field").setLayer(points)
        dock.get_widget_by_name("units_field").setField("unit_name")

        from mappy.mappy_utils import restoreWidgetContent

        restoreWidgetContent(dock.get_widget_by_name("output"), "/tmp/zzz_assign_unit_test.gpkg")
        dock.get_widget_by_name("out_polygons_layer_name").setText("zzz_final_map")

        return mappy, points, polygons

    def test_updates_existing_point_in_clicked_polygon(self):
        mappy, points, polygons = self._make_setup()

        with (
            patch.object(mappy, "recompute_map") as recompute,
            patch.object(mappy, "findLayer", return_value=polygons),
            patch("mappy.assign_unit_dialog.AssignUnitDialog.getUnit", return_value=("UNIT_B", "#123456", {}, True)),
        ):
            mappy.assign_unit_at_point(QgsPointXY(0.5, 0.5))

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
        mappy, points, polygons = self._make_setup()

        with (
            patch.object(mappy, "recompute_map") as recompute,
            patch.object(mappy, "findLayer", return_value=polygons),
            patch("mappy.assign_unit_dialog.AssignUnitDialog.getUnit", return_value=("UNIT_C", "#654321", {}, True)),
        ):
            mappy.assign_unit_at_point(QgsPointXY(2.5, 0.5))

        recompute.assert_not_called()
        values = sorted(f["unit_name"] for f in points.getFeatures())
        self.assertEqual(values, ["UNIT_A", "UNIT_C"])
        self.assertEqual(points.featureCount(), 2)

    def test_recomputes_map_when_setting_enabled(self):
        mappy, points, polygons = self._make_setup()
        mappy.config_dock.get_widget_by_name("auto_recompute_on_assign_unit").setChecked(True)

        with (
            patch.object(mappy, "recompute_map") as recompute,
            patch.object(mappy, "findLayer", return_value=polygons),
            patch("mappy.assign_unit_dialog.AssignUnitDialog.getUnit", return_value=("UNIT_B", "#123456", {}, True)),
        ):
            mappy.assign_unit_at_point(QgsPointXY(0.5, 0.5))

        recompute.assert_called_once()

    def test_recoloring_a_different_unit_during_the_dialog_still_propagates(self):
        # regression test: the dialog can report color changes for units
        # other than the one confirmed (e.g. the user tweaked an existing
        # unit's color while browsing before picking a different one) --
        # those must still be written to the points layer, not dropped
        mappy, points, polygons = self._make_setup()

        with (
            patch.object(mappy, "recompute_map"),
            patch.object(mappy, "findLayer", return_value=polygons),
            patch(
                "mappy.assign_unit_dialog.AssignUnitDialog.getUnit",
                return_value=("UNIT_D", "#dddddd", {"UNIT_A": "#aaaaaa"}, True),
            ),
        ):
            mappy.assign_unit_at_point(QgsPointXY(2.5, 0.5))

        colors = {f["unit_name"]: f["color"] for f in points.getFeatures()}
        self.assertEqual(colors["UNIT_D"], "#dddddd")
        self.assertEqual(colors["UNIT_A"], "#aaaaaa")

    def test_recoloring_the_confirmed_existing_unit_actually_sticks(self):
        # regression test: writing the dialog's chosen color to points_layer
        # *before* calling sync_unit_colors made sync_unit_colors's baseline
        # already reflect the new color, while the polygon layer's renderer
        # (not yet touched) still showed the old one -- that mismatch was
        # misread as a manual Symbology override on the polygon layer, which
        # then "won" and silently reverted the just-applied change back to
        # the old color.
        mappy, points, polygons = self._make_setup()

        with (
            patch.object(mappy, "recompute_map"),
            patch.object(mappy, "findLayer", return_value=polygons),
            patch("mappy.assign_unit_dialog.AssignUnitDialog.getUnit", return_value=("UNIT_A", "#ff0000", {}, True)),
        ):
            mappy.assign_unit_at_point(QgsPointXY(0.5, 0.5))

        with (
            patch.object(mappy, "recompute_map"),
            patch.object(mappy, "findLayer", return_value=polygons),
            patch("mappy.assign_unit_dialog.AssignUnitDialog.getUnit", return_value=("UNIT_A", "#0000ff", {}, True)),
        ):
            mappy.assign_unit_at_point(QgsPointXY(0.5, 0.5))

        for f in points.getFeatures():
            self.assertEqual(f["color"], "#0000ff")

        renderer = polygons.renderer()
        index = renderer.categoryIndexForValue("UNIT_A")
        categories = renderer.categories()
        category = categories[index]
        symbol = category.symbol()
        self.assertEqual(symbol.color().name(), "#0000ff")

    def test_click_outside_any_polygon_does_nothing(self):
        mappy, points, polygons = self._make_setup()

        with (
            patch.object(mappy, "recompute_map") as recompute,
            patch.object(mappy, "findLayer", return_value=polygons),
            patch("mappy.assign_unit_dialog.AssignUnitDialog.getUnit") as getitem,
        ):
            mappy.assign_unit_at_point(QgsPointXY(10, 10))

        recompute.assert_not_called()
        getitem.assert_not_called()
        self.assertEqual(points.featureCount(), 1)
