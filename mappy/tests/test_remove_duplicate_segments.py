import sys

from qgis.core import QgsFeature, QgsGeometry, QgsProcessingException, QgsVectorLayer

from mappy.tests import ExtendedUnitTesting


class TestRemoveDuplicateSegments(ExtendedUnitTesting):
    def _run(self, features):
        sys.path.append("/usr/share/qgis/python/plugins/")
        from qgis import processing

        layer = QgsVectorLayer("LineString?crs=EPSG:4326", "zzz_segments", "memory")
        layer.dataProvider().addFeatures(features)
        layer.updateExtents()

        return processing.run(
            "mappy:removeduplicatedsegments",
            {"IN_SEGMENTS": layer, "THRESHOLD": 1e-6, "OUTPUT": "TEMPORARY_OUTPUT"},
        )["OUTPUT"]

    def _line(self, wkt):
        f = QgsFeature()
        f.setGeometry(QgsGeometry.fromWkt(wkt))
        return f

    def test_multi_vertex_input_raises_a_clear_error_instead_of_crashing(self):
        # regression test: a feature that isn't a strict 2-vertex segment
        # (e.g. an ordinary un-exploded polyline) used to crash with
        # "ValueError: too many values to unpack (expected 2)" from deep
        # inside equal_segments() -- must now fail with an actionable
        # QgsProcessingException instead
        features = [
            self._line("LINESTRING(0 0, 1 0, 2 0)"),  # 3 vertices
            # same bounding box as the line above, so the spatial index
            # actually pairs them up for comparison
            self._line("LINESTRING(0 0, 2 0)"),
        ]

        with self.assertRaises(QgsProcessingException) as ctx:
            self._run(features)

        self.assertIn("2-vertex", str(ctx.exception))
        self.assertIn("Explode Lines", str(ctx.exception))

    def test_removes_a_reversed_duplicate_segment(self):
        features = [
            self._line("LINESTRING(0 0, 1 0)"),
            self._line("LINESTRING(1 0, 0 0)"),  # same segment, reversed
            self._line("LINESTRING(5 5, 6 5)"),  # unrelated, kept
        ]

        out = self._run(features)

        self.assertEqual(out.featureCount(), 2)
