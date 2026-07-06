from qgis.PyQt.QtCore import QVariant
from qgis.core import QgsField, QgsProject, QgsVectorLayer

from mappy.tests import ExtendedUnitTesting


class TestRestoreMultipleLayers(ExtendedUnitTesting):
    def test_restore_picks_saved_layer_not_first_available(self):
        from mappy.qgismappy import Mappy

        dock = Mappy.instance.config_dock
        proj = QgsProject.instance()

        def make_pts(name):
            l = QgsVectorLayer("Point", name, "memory")
            l.dataProvider().addAttributes([QgsField("unit_name", QVariant.String)])
            l.updateFields()
            QgsProject.instance().addMapLayer(l)
            return l

        # target layer added in the middle, so it's neither first nor last,
        # and isn't whatever the combo happens to auto-select
        layer_a = make_pts("restore_multi_layer_a")
        layer_b_target = make_pts("restore_multi_layer_b_target")
        layer_c = make_pts("restore_multi_layer_c")

        proj.writeEntry("mappy", "points", layer_b_target.id())
        proj.writeEntry("mappy", "units_field", "unit_name")

        dock.restoreSettingsFromProject()

        self.assertEqual(dock.points.currentLayer(), layer_b_target)
        self.assertEqual(dock.units_field.layer(), layer_b_target)
        self.assertEqual(dock.units_field.currentField(), "unit_name")
