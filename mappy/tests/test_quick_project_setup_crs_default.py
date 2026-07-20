import sys
from unittest.mock import patch

from qgis.core import QgsCoordinateReferenceSystem, QgsProject

from mappy.tests import ExtendedUnitTesting


class TestQuickProjectSetupCrsDefault(ExtendedUnitTesting):
    def test_omitted_crs_defaults_to_project_crs(self):
        from mappy.qgismappy import Mappy

        dock = Mappy.instance.config_dock

        project_crs = QgsCoordinateReferenceSystem("EPSG:3857")
        QgsProject.instance().setCrs(project_crs)

        sys.path.append("/usr/share/qgis/python/plugins/")
        from qgis import processing

        with patch.object(dock, "show"):
            processing.run(
                "mappy:quickprojectsetup",
                {
                    "ProjectName": "CrsDefaultTest",
                    "OutFolder": "TEMPORARY_OUTPUT",
                    # CRS intentionally omitted -- should default to project CRS
                    "LinearFeaturesLayer": False,
                },
            )

        points_layer = dock.get_widget_by_name("points").currentLayer()
        self.assertIsNotNone(points_layer)
        self.assertEqual(points_layer.crs().authid(), "EPSG:3857")
