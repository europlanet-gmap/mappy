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

        crs = QgsCoordinateReferenceSystem("EPSG:4326")

        points = QgsVectorLayer("Point?crs=EPSG:4326", "zzz_points", "memory")
        points.dataProvider().addAttributes([QgsField("unit_name", QVariant.String)])
        points.updateFields()
        QgsProject.instance().addMapLayer(points)

        polygons = QgsVectorLayer("Polygon?crs=EPSG:4326", "zzz_final_map", "memory")
        QgsProject.instance().addMapLayer(polygons)

        f1 = QgsFeature()
        f1.setGeometry(QgsGeometry.fromWkt("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"))
        polygons.dataProvider().addFeature(f1)

        f2 = QgsFeature()
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
             patch("qgis.PyQt.QtWidgets.QInputDialog.getItem", return_value=("UNIT_B", True)):
            mappy.assign_unit_at_point(QgsPointXY(0.5, 0.5))

        recompute.assert_called_once()
        values = [f["unit_name"] for f in points.getFeatures()]
        self.assertEqual(values, ["UNIT_B"])

    def test_creates_new_point_when_polygon_has_none(self):
        mappy, points, polygons = self._make_setup()

        with patch.object(mappy, "recompute_map") as recompute, \
             patch.object(mappy, "findLayer", return_value=polygons), \
             patch("qgis.PyQt.QtWidgets.QInputDialog.getItem", return_value=("UNIT_C", True)):
            mappy.assign_unit_at_point(QgsPointXY(2.5, 0.5))

        recompute.assert_called_once()
        values = sorted(f["unit_name"] for f in points.getFeatures())
        self.assertEqual(values, ["UNIT_A", "UNIT_C"])
        self.assertEqual(points.featureCount(), 2)

    def test_click_outside_any_polygon_does_nothing(self):
        mappy, points, polygons = self._make_setup()

        with patch.object(mappy, "recompute_map") as recompute, \
             patch.object(mappy, "findLayer", return_value=polygons), \
             patch("qgis.PyQt.QtWidgets.QInputDialog.getItem") as getitem:
            mappy.assign_unit_at_point(QgsPointXY(10, 10))

        recompute.assert_not_called()
        getitem.assert_not_called()
        self.assertEqual(points.featureCount(), 1)
