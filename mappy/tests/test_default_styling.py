from qgis.PyQt.QtCore import QVariant
from qgis.core import QgsField, QgsVectorLayer

from mappy.tests import ExtendedUnitTesting


class TestDefaultStyling(ExtendedUnitTesting):
    def test_polygon_labels_are_forced_inside_the_polygon(self):
        from mappy.mappy_utils import enable_default_labels

        polygons = QgsVectorLayer("Polygon?crs=EPSG:4326", "zzz_polys", "memory")
        polygons.dataProvider().addAttributes([QgsField("unit_name", QVariant.String)])
        polygons.updateFields()

        enable_default_labels(polygons, "unit_name")

        self.assertTrue(polygons.labelsEnabled())
        settings = polygons.labeling().settings()
        self.assertEqual(settings.fieldName, "unit_name")
        # the Placement tab's "only show label which completely fits within
        # the polygon boundary" option, so labels never spill outside it
        self.assertTrue(settings.fitInPolygonOnly)

    def test_point_labels_are_not_forced_to_fit_a_polygon(self):
        from mappy.mappy_utils import enable_default_labels

        points = QgsVectorLayer("Point?crs=EPSG:4326", "zzz_pts", "memory")
        points.dataProvider().addAttributes([QgsField("unit_name", QVariant.String)])
        points.updateFields()

        enable_default_labels(points, "unit_name")

        self.assertTrue(points.labelsEnabled())
        settings = points.labeling().settings()
        self.assertEqual(settings.fieldName, "unit_name")
        self.assertFalse(settings.fitInPolygonOnly)

    def test_does_not_override_existing_labeling(self):
        from mappy.mappy_utils import enable_default_labels

        polygons = QgsVectorLayer("Polygon?crs=EPSG:4326", "zzz_polys2", "memory")
        polygons.dataProvider().addAttributes([QgsField("unit_name", QVariant.String)])
        polygons.updateFields()

        enable_default_labels(polygons, "unit_name")
        polygons.setLabelsEnabled(False)

        # a second call (e.g. on layer reload) must not clobber the user's
        # choice to turn labels back off
        enable_default_labels(polygons, "unit_name")
        self.assertFalse(polygons.labelsEnabled())
