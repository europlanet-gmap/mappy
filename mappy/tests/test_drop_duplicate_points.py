from qgis.PyQt.QtCore import QVariant
from qgis.core import QgsFeature, QgsField, QgsGeometry, QgsPointXY, QgsVectorLayer

from mappy.tests import ExtendedUnitTesting


class TestDropDuplicatePointsPerPolygon(ExtendedUnitTesting):
    def _make_polygons(self):
        polys = QgsVectorLayer("Polygon", "polys", "memory")
        pr = polys.dataProvider()

        f1 = QgsFeature()
        f1.setGeometry(QgsGeometry.fromWkt("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"))
        pr.addFeature(f1)

        f2 = QgsFeature()
        f2.setGeometry(QgsGeometry.fromWkt("POLYGON((2 0, 3 0, 3 1, 2 1, 2 0))"))
        pr.addFeature(f2)

        polys.updateExtents()
        return polys

    def test_drops_all_but_first_when_multiple_points_in_one_polygon(self):
        from mappy.mappy_utils import drop_duplicate_points_per_polygon

        polys = self._make_polygons()

        pts = QgsVectorLayer("Point", "pts", "memory")
        pr = pts.dataProvider()
        pr.addAttributes([QgsField("unit_name", QVariant.String)])
        pts.updateFields()

        # two points inside polygon 1 (duplicate), one inside polygon 2 (unique)
        f1 = QgsFeature(pts.fields())
        f1.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(0.2, 0.2)))
        f1["unit_name"] = "FIRST_IN_POLY1"
        pr.addFeature(f1)

        f2 = QgsFeature(pts.fields())
        f2.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(0.8, 0.8)))
        f2["unit_name"] = "SECOND_IN_POLY1_SHOULD_BE_DROPPED"
        pr.addFeature(f2)

        f3 = QgsFeature(pts.fields())
        f3.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(2.5, 0.5)))
        f3["unit_name"] = "ONLY_IN_POLY2"
        pr.addFeature(f3)

        pts.updateExtents()

        first_id_in_poly1 = f1.id()

        deleted = drop_duplicate_points_per_polygon(pts, polys)

        remaining = {f["unit_name"]: f.id() for f in pts.getFeatures()}
        print("REMAINING:", remaining)
        print("DELETED IDS:", deleted)

        self.assertEqual(pts.featureCount(), 2)
        self.assertIn("FIRST_IN_POLY1", remaining)
        self.assertIn("ONLY_IN_POLY2", remaining)
        self.assertNotIn("SECOND_IN_POLY1_SHOULD_BE_DROPPED", remaining)
        self.assertEqual(remaining["FIRST_IN_POLY1"], first_id_in_poly1)

    def test_no_deletion_when_each_polygon_has_at_most_one_point(self):
        from mappy.mappy_utils import drop_duplicate_points_per_polygon

        polys = self._make_polygons()

        pts = QgsVectorLayer("Point", "pts", "memory")
        pr = pts.dataProvider()
        pr.addAttributes([QgsField("unit_name", QVariant.String)])
        pts.updateFields()

        f1 = QgsFeature(pts.fields())
        f1.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(0.5, 0.5)))
        f1["unit_name"] = "A"
        pr.addFeature(f1)

        f2 = QgsFeature(pts.fields())
        f2.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(2.5, 0.5)))
        f2["unit_name"] = "B"
        pr.addFeature(f2)

        pts.updateExtents()

        deleted = drop_duplicate_points_per_polygon(pts, polys)

        self.assertEqual(deleted, set())
        self.assertEqual(pts.featureCount(), 2)
