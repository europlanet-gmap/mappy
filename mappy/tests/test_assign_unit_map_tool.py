from unittest.mock import patch

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsCoordinateReferenceSystem,
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

        crs = QgsCoordinateReferenceSystem("EPSG:4326")

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

        with patch.object(mappy, "recompute_map") as recompute, \
             patch.object(mappy, "findLayer", return_value=polygons), \
             patch("mappy.assign_unit_dialog.AssignUnitDialog.getUnit", return_value=("UNIT_B", True)):
            mappy.assign_unit_at_point(QgsPointXY(0.5, 0.5))

        # auto-recompute is disabled by default, so assigning a unit must
        # not trigger a full map regeneration
        recompute.assert_not_called()
        values = [f["unit_name"] for f in points.getFeatures()]
        self.assertEqual(values, ["UNIT_B"])

        # the clicked polygon's own attribute is updated directly, in sync
        # with the point, even without a full recompute
        poly_values = [f["unit_name"] for f in polygons.getFeatures() if f.geometry().intersects(QgsGeometry.fromPointXY(QgsPointXY(0.5, 0.5)))]
        self.assertEqual(poly_values, ["UNIT_B"])
        self.assertFalse(polygons.isEditable())

    def test_creates_new_point_when_polygon_has_none(self):
        mappy, points, polygons = self._make_setup()

        with patch.object(mappy, "recompute_map") as recompute, \
             patch.object(mappy, "findLayer", return_value=polygons), \
             patch("mappy.assign_unit_dialog.AssignUnitDialog.getUnit", return_value=("UNIT_C", True)):
            mappy.assign_unit_at_point(QgsPointXY(2.5, 0.5))

        recompute.assert_not_called()
        values = sorted(f["unit_name"] for f in points.getFeatures())
        self.assertEqual(values, ["UNIT_A", "UNIT_C"])
        self.assertEqual(points.featureCount(), 2)

    def test_recomputes_map_when_setting_enabled(self):
        mappy, points, polygons = self._make_setup()
        mappy.config_dock.get_widget_by_name("auto_recompute_on_assign_unit").setChecked(True)

        with patch.object(mappy, "recompute_map") as recompute, \
             patch.object(mappy, "findLayer", return_value=polygons), \
             patch("mappy.assign_unit_dialog.AssignUnitDialog.getUnit", return_value=("UNIT_B", True)):
            mappy.assign_unit_at_point(QgsPointXY(0.5, 0.5))

        recompute.assert_called_once()

    def test_click_outside_any_polygon_does_nothing(self):
        mappy, points, polygons = self._make_setup()

        with patch.object(mappy, "recompute_map") as recompute, \
             patch.object(mappy, "findLayer", return_value=polygons), \
             patch("mappy.assign_unit_dialog.AssignUnitDialog.getUnit") as getitem:
            mappy.assign_unit_at_point(QgsPointXY(10, 10))

        recompute.assert_not_called()
        getitem.assert_not_called()
        self.assertEqual(points.featureCount(), 1)
