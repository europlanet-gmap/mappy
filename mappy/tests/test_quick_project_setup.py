import sys
from unittest.mock import patch

from qgis.PyQt.QtCore import QVariant
from qgis.core import QgsCoordinateReferenceSystem, QgsField, QgsProject, QgsVectorLayer

from . import ExtendedUnitTesting


class TestQuickProjectSetup(ExtendedUnitTesting):
    def test_units_field_is_populated_after_setup(self):
        from mappy.qgismappy import Mappy

        dock = Mappy.instance.config_dock

        # Simulate a project that already has an unrelated point layer selected
        # in the "points" combo. This reproduces the scenario that used to leave
        # units_field un-populated: the combo does not auto-switch to a newly
        # created layer just because one was added to the project.
        decoy = QgsVectorLayer("Point", "decoy_points", "memory")
        decoy.dataProvider().addAttributes([QgsField("foo", QVariant.String)])
        decoy.updateFields()
        QgsProject.instance().addMapLayer(decoy)
        dock.get_widget_by_name("points").setLayer(decoy)

        sys.path.append("/usr/share/qgis/python/plugins/")
        from qgis import processing

        # the algorithm calls dock.show() to reveal the panel to the user;
        # skip that in tests so no real window is created (avoids relying on
        # a display/window manager being available in headless CI)
        with patch.object(dock, "show"):
            processing.run(
                "mappy:quickprojectsetup",
                {
                    "ProjectName": "QuickSetupTest",
                    "OutFolder": "TEMPORARY_OUTPUT",
                    "CRS": QgsCoordinateReferenceSystem("EPSG:4326"),
                    "LinearFeaturesLayer": True,
                },
            )

        points_widget = dock.get_widget_by_name("points")
        points_layer = points_widget.currentLayer()
        self.assertIsNotNone(points_layer)
        self.asser  tEqual(points_layer.name(), "source_indicators")

        units_widget = dock.get_widget_by_name("units_field")
        self.assertEqual(units_widget.layer(), points_layer)
        self.assertEqual(units_widget.currentField(), "unit_name")
