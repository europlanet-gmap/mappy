from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor
from qgis.core import (
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsVectorLayer,
)

from mappy.tests import ExtendedUnitTesting


def _category_color(layer, value):
    """Reads a category's current color, keeping every intermediate object
    named -- chaining renderer.categories()[i].symbol().color().name() in
    one expression has been observed to segfault in this PyQGIS build."""
    renderer = layer.renderer()
    index = renderer.categoryIndexForValue(value)
    categories = renderer.categories()
    category = categories[index]
    symbol = category.symbol()
    color = symbol.color()
    return color.name()


def _recolor_category(layer, value, new_color):
    """Simulates a manual recolor made by hand in QGIS's Symbology panel.

    Deliberately never reads back the existing category's symbol at all --
    it builds a brand new one from the layer's geometry type instead.
    Chaining calls like renderer.categories()[i].symbol()... segfaults here:
    the intermediate SIP wrappers can get garbage-collected while the C++
    side still expects them alive, especially right after a prior
    updateCategorySymbol call transferred ownership of the old symbol away.
    """
    from qgis.core import QgsSymbol

    renderer = layer.renderer()
    index = renderer.categoryIndexForValue(value)
    fresh_symbol = QgsSymbol.defaultSymbol(layer.geometryType())
    fresh_symbol.setColor(QColor(new_color))
    renderer.updateCategorySymbol(index, fresh_symbol)


class TestColorTable(ExtendedUnitTesting):
    def _make_points(self, unit_names):
        layer = QgsVectorLayer("Point?crs=EPSG:4326", "zzz_pts", "memory")
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
        layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "zzz_polys", "memory")
        layer.dataProvider().addAttributes([QgsField("unit_name", QVariant.String)])
        layer.updateFields()

        for i, name in enumerate(unit_names):
            x = i * 2
            f = QgsFeature(layer.fields())
            f.setGeometry(QgsGeometry.fromWkt(
                f"POLYGON(({x} 0, {x+1} 0, {x+1} 1, {x} 1, {x} 0))"
            ))
            f["unit_name"] = name
            layer.dataProvider().addFeature(f)
        return layer

    def test_creates_missing_color_field(self):
        from mappy.mappy_utils import get_or_create_color_table

        layer = self._make_points(["Basalt"])
        self.assertEqual(layer.fields().indexFromName("color"), -1)

        get_or_create_color_table(layer, "unit_name")

        self.assertNotEqual(layer.fields().indexFromName("color"), -1)

    def test_populates_color_for_every_matching_point(self):
        from mappy.mappy_utils import get_or_create_color_table

        layer = self._make_points(["Basalt", "Breccia", "Basalt"])
        table = get_or_create_color_table(layer, "unit_name")

        colors = {f["unit_name"]: f["color"] for f in layer.getFeatures()}
        self.assertEqual(colors["Basalt"], table["Basalt"])
        self.assertEqual(colors["Breccia"], table["Breccia"])
        self.assertNotEqual(table["Basalt"], table["Breccia"])

    def test_stable_across_repeated_calls(self):
        from mappy.mappy_utils import get_or_create_color_table

        layer = self._make_points(["Basalt", "Breccia"])
        table1 = get_or_create_color_table(layer, "unit_name")
        table2 = get_or_create_color_table(layer, "unit_name")

        self.assertEqual(table1, table2)

    def test_new_unit_does_not_collide_with_or_change_existing_colors(self):
        # regression test: the per-unit color index used to be computed as
        # len(color_table) *while* color_table was being mutated in the same
        # loop, double-counting growth and making later units collide with
        # earlier ones assigned in a previous call
        from mappy.mappy_utils import get_or_create_color_table

        layer = self._make_points(["Basalt", "Breccia"])
        table1 = get_or_create_color_table(layer, "unit_name")

        f = QgsFeature(layer.fields())
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(9, 9)))
        f["unit_name"] = "Regolith"
        layer.dataProvider().addFeature(f)
        layer.updateExtents()

        table2 = get_or_create_color_table(layer, "unit_name")

        self.assertEqual(table1["Basalt"], table2["Basalt"])
        self.assertEqual(table1["Breccia"], table2["Breccia"])
        self.assertEqual(len(set(table2.values())), len(table2))

    def test_backfills_legacy_points_missing_a_color(self):
        from mappy.mappy_utils import get_or_create_color_table

        layer = self._make_points(["Basalt", "Basalt"])
        # simulate legacy data: the field already exists but one feature's
        # color was never set
        get_or_create_color_table(layer, "unit_name")
        layer.startEditing()
        color_index = layer.fields().indexFromName("color")
        first_id = next(layer.getFeatures()).id()
        layer.changeAttributeValue(first_id, color_index, None)
        layer.commitChanges()

        table = get_or_create_color_table(layer, "unit_name")

        colors = [f["color"] for f in layer.getFeatures()]
        self.assertEqual(colors, [table["Basalt"], table["Basalt"]])

    def test_reset_categories_uses_persisted_color(self):
        from mappy.mappy_utils import get_or_create_color_table, resetCategoriesIfNeeded

        points = self._make_points(["Basalt", "Breccia"])
        table = get_or_create_color_table(points, "unit_name")

        polygons = QgsVectorLayer("Polygon?crs=EPSG:4326", "zzz_polys", "memory")
        polygons.dataProvider().addAttributes([QgsField("unit_name", QVariant.String)])
        polygons.updateFields()
        for name, wkt in [
            ("Basalt", "POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"),
            ("Breccia", "POLYGON((2 0, 3 0, 3 1, 2 1, 2 0))"),
        ]:
            f = QgsFeature(polygons.fields())
            f.setGeometry(QgsGeometry.fromWkt(wkt))
            f["unit_name"] = name
            polygons.dataProvider().addFeature(f)

        resetCategoriesIfNeeded(polygons, "unit_name", color_table=table)

        for unit in ["Basalt", "Breccia"]:
            self.assertEqual(_category_color(polygons, unit), table[unit])

    def test_sync_colors_both_layers_from_points(self):
        from mappy.mappy_utils import sync_unit_colors

        points = self._make_points(["Basalt", "Breccia"])
        polygons = self._make_polygons(["Basalt", "Breccia"])

        table = sync_unit_colors(points, polygons, "unit_name")

        for unit in ["Basalt", "Breccia"]:
            self.assertEqual(_category_color(points, unit), table[unit])
            self.assertEqual(_category_color(polygons, unit), table[unit])

    def test_manual_recolor_on_polygons_propagates_to_points_and_data(self):
        from mappy.mappy_utils import sync_unit_colors

        points = self._make_points(["Basalt", "Breccia"])
        polygons = self._make_polygons(["Basalt", "Breccia"])
        sync_unit_colors(points, polygons, "unit_name")

        _recolor_category(polygons, "Basalt", "#00ff00")

        table = sync_unit_colors(points, polygons, "unit_name")

        self.assertEqual(table["Basalt"], "#00ff00")
        self.assertEqual(_category_color(points, "Basalt"), "#00ff00")
        for f in points.getFeatures():
            if f["unit_name"] == "Basalt":
                self.assertEqual(f["color"], "#00ff00")

    def test_manual_recolor_on_points_propagates_to_polygons(self):
        from mappy.mappy_utils import sync_unit_colors

        points = self._make_points(["Basalt", "Breccia"])
        polygons = self._make_polygons(["Basalt", "Breccia"])
        sync_unit_colors(points, polygons, "unit_name")

        _recolor_category(points, "Breccia", "#0000ff")

        table = sync_unit_colors(points, polygons, "unit_name")

        self.assertEqual(table["Breccia"], "#0000ff")
        self.assertEqual(_category_color(polygons, "Breccia"), "#0000ff")

    def test_conflicting_manual_recolor_prefers_polygons(self):
        from mappy.mappy_utils import sync_unit_colors

        points = self._make_points(["Basalt", "Breccia"])
        polygons = self._make_polygons(["Basalt", "Breccia"])
        sync_unit_colors(points, polygons, "unit_name")

        _recolor_category(polygons, "Basalt", "#111111")
        _recolor_category(points, "Basalt", "#222222")

        table = sync_unit_colors(points, polygons, "unit_name")

        self.assertEqual(table["Basalt"], "#111111")
