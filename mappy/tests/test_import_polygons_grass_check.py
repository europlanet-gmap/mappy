import sys
from unittest.mock import patch

from qgis.core import QgsFeature, QgsGeometry, QgsProcessingException, QgsVectorLayer

from mappy.tests import ExtendedUnitTesting


class TestImportPolygonsGrassCheck(ExtendedUnitTesting):
    def _make_polygon_layer(self):
        layer = QgsVectorLayer("Polygon?crs=EPSG:4326", "zzz_import_polygons", "memory")
        f = QgsFeature()
        f.setGeometry(QgsGeometry.fromWkt("POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))"))
        layer.dataProvider().addFeature(f)
        layer.updateExtents()
        return layer

    def _run(self, layer):
        sys.path.append("/usr/share/qgis/python/plugins/")
        from qgis import processing

        return processing.run(
            "mappy:importpolygons",
            {
                "input_polygonal_layer": layer,
                "simplify_tolerance": 0.0001,
                "vinogr_snap_tolerance_1__no_snap": 1e-6,
                "Points": "TEMPORARY_OUTPUT",
                "Contacts": "TEMPORARY_OUTPUT",
            },
        )

    def test_missing_grass_raises_a_clear_actionable_error(self):
        # regression test: without the GRASS provider available, this used
        # to fail deep inside processing.run("grass7:v.to.lines", ...) with
        # a generic "algorithm not found" error and no guidance -- must now
        # fail fast with actionable instructions instead. GRASS happens to
        # be installed in this test environment, so unavailability is
        # simulated by patching the QgsApplication name this algorithm
        # module itself looks the registry up through (scoped to this
        # module only -- processing.run()'s own internal registry lookups,
        # which use qgis.core.QgsApplication directly, are unaffected).
        layer = self._make_polygon_layer()

        with patch("mappy.providers.import_polygons.QgsApplication") as mock_app:
            mock_app.processingRegistry.return_value.algorithmById.return_value = None

            with self.assertRaises(QgsProcessingException) as ctx:
                self._run(layer)

        message = str(ctx.exception)
        self.assertIn("GRASS", message)
        self.assertIn("Processing > Providers > GRASS", message)

    def test_available_grass_skips_the_preflight_error(self):
        layer = self._make_polygon_layer()

        with patch("mappy.providers.import_polygons.QgsApplication") as mock_app:
            mock_app.processingRegistry.return_value.algorithmById.return_value = object()

            try:
                self._run(layer)
            except QgsProcessingException as e:
                # whatever else may go wrong further down the pipeline,
                # it must not be our own GRASS-unavailable message
                self.assertNotIn("Processing > Providers > GRASS", str(e))
