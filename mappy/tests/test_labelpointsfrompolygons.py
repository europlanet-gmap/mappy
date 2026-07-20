import sys

from qgis.core import QgsFeature, QgsGeometry, QgsVectorLayer

from mappy.tests import ExtendedUnitTesting


class TestLabelPointsFromPolygons(ExtendedUnitTesting):
    def test_point_stays_inside_thin_polygon_despite_coarse_tolerance(self):
        # native:poleofinaccessibility's TOLERANCE controls how finely it
        # subdivides the search -- if it's too coarse relative to a thin or
        # complex polygon (here, an L-shape with a 0.2-unit-wide arm), the
        # search can terminate on a cell whose center falls outside the
        # polygon entirely. recompute_map's add_indicators step hardcodes
        # TOLERANCE=1, which is exactly such a case.
        sys.path.append("/usr/share/qgis/python/plugins/")
        from qgis import processing

        wkt = "POLYGON((0 0, 10 0, 10 0.2, 0.2 0.2, 0.2 10, 0 10, 0 0))"
        layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "thin_l_shape", "memory")
        f = QgsFeature()
        f.setGeometry(QgsGeometry.fromWkt(wkt))
        layer.dataProvider().addFeature(f)
        layer.updateExtents()

        out = processing.run(
            "mappy:labelspointsfrompolygons",
            {"IN_LAYER": layer, "TOLERANCE": 1, "OUTPUT": "TEMPORARY_OUTPUT"},
        )["OUTPUT"]

        points = list(out.getFeatures())
        self.assertEqual(len(points), 1)
        self.assertTrue(f.geometry().contains(points[0].geometry()))
