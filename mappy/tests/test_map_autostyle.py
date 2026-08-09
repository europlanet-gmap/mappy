import sys

from qgis.PyQt.QtCore import QVariant
from qgis.core import QgsFeature, QgsField, QgsGeometry, QgsPointXY, QgsVectorLayer

from mappy.engine.colors import get_or_create_color_table
from mappy.tests import ExtendedUnitTesting


def _category_color(layer, value):
    renderer = layer.renderer()
    index = renderer.categoryIndexForValue(value)
    categories = renderer.categories()
    category = categories[index]
    symbol = category.symbol()
    color = symbol.color()
    return color.name()


class TestMapAutoStyle(ExtendedUnitTesting):
    def _make_points(self, unit_names):
        layer = QgsVectorLayer("Point?crs=EPSG:4326", "zzz_autostyle_pts", "memory")
        layer.dataProvider().addAttributes([QgsField("unit_name", QVariant.String)])
        layer.updateFields()
        for i, name in enumerate(unit_names):
            f = QgsFeature(layer.fields())
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(i, i)))
            f["unit_name"] = name
            layer.dataProvider().addFeature(f)
        layer.updateExtents()
        return layer

    def _make_polygons(self, unit_names):
        layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "zzz_autostyle_polys", "memory")
        layer.dataProvider().addAttributes([QgsField("unit_name", QVariant.String)])
        layer.updateFields()
        for i, name in enumerate(unit_names):
            x = i * 2
            f = QgsFeature(layer.fields())
            f.setGeometry(QgsGeometry.fromWkt(f"POLYGON(({x} 0, {x + 1} 0, {x + 1} 1, {x} 1, {x} 0))"))
            f["unit_name"] = name
            layer.dataProvider().addFeature(f)
        return layer

    def test_without_points_layer_invents_its_own_colors(self):
        sys.path.append("/usr/share/qgis/python/plugins/")
        from qgis import processing

        points = self._make_points(["Basalt"])
        table = get_or_create_color_table(points, "unit_name")

        polygons = self._make_polygons(["Basalt"])

        processing.run("mappy:mapautostyle", {"IN_LAYER": polygons, "CAT_FIELD": "unit_name"})

        # no points layer given -- nothing to keep in sync with, so the
        # polygon layer's fresh category doesn't necessarily match the
        # points layer's persisted color
        self.assertNotEqual(_category_color(polygons, "Basalt"), table["Basalt"])

    def test_with_points_layer_reuses_the_persisted_color(self):
        sys.path.append("/usr/share/qgis/python/plugins/")
        from qgis import processing

        points = self._make_points(["Basalt"])
        table = get_or_create_color_table(points, "unit_name")

        polygons = self._make_polygons(["Basalt"])

        processing.run(
            "mappy:mapautostyle",
            {"IN_LAYER": polygons, "CAT_FIELD": "unit_name", "POINTS_LAYER": points},
        )

        self.assertEqual(_category_color(polygons, "Basalt"), table["Basalt"])
