from qgis.PyQt.QtCore import QVariant
from qgis.core import QgsField, QgsProject, QgsVectorLayer

from mappy.tests import ExtendedUnitTesting


class TestRestoreUnitsFieldAfterReload(ExtendedUnitTesting):
    def test_restore_when_points_setlayer_is_a_noop(self):
        from mappy.qgismappy import Mappy

        dock = Mappy.instance.config_dock
        proj = QgsProject.instance()

        pts = QgsVectorLayer("Point", "restore_test_points", "memory")
        pts.dataProvider().addAttributes([QgsField("unit_name", QVariant.String)])
        pts.updateFields()
        QgsProject.instance().addMapLayer(pts)  # auto-selected by "points" combo

        dock.get_widget_by_name("points").setLayer(pts)  # no-op, already selected
        dock.get_widget_by_name("units_field").setLayer(None)  # simulate never-bound state

        proj.writeEntry("mappy", "points", pts.id())
        proj.writeEntry("mappy", "units_field", "unit_name")

        dock.restoreSettingsFromProject()

        print("points.currentLayer():", dock.points.currentLayer())
        print("units_field.layer():", dock.units_field.layer())
        print("units_field.currentField():", dock.units_field.currentField())

        self.assertEqual(dock.units_field.layer(), pts)
        self.assertEqual(dock.units_field.currentField(), "unit_name")
