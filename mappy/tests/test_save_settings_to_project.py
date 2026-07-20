from qgis.core import QgsProject
from qgis.PyQt.QtXml import QDomDocument

from mappy.tests import ExtendedUnitTesting


class TestSaveSettingsOnProjectWrite(ExtendedUnitTesting):
    def _set_without_signal(self, dock, text):
        # bypass value_changed entirely (simulates a widget whose current
        # value never went through the tracked "changed" signal)
        dock.out_polygons_layer_name.blockSignals(True)
        dock.out_polygons_layer_name.setText(text)
        dock.out_polygons_layer_name.blockSignals(False)

    def test_save_settings_to_project_persists_current_dock_state(self):
        from mappy.qgismappy import Mappy

        dock = Mappy.instance.config_dock
        proj = QgsProject.instance()

        self._set_without_signal(dock, "zzz_never_signaled_map")

        value, found = proj.readEntry("mappy", "out_polygons_layer_name", None)
        # sanity check: nothing has persisted this value yet
        self.assertNotEqual(value, "zzz_never_signaled_map")

        dock.saveSettingsToProject()

        value, found = proj.readEntry("mappy", "out_polygons_layer_name", None)
        self.assertTrue(found)
        self.assertEqual(value, "zzz_never_signaled_map")

    def test_write_project_signal_is_wired_to_save(self):
        from mappy.qgismappy import Mappy

        dock = Mappy.instance.config_dock
        proj = QgsProject.instance()

        self._set_without_signal(dock, "zzz_via_real_signal")

        proj.writeProject.emit(QDomDocument())

        value, found = proj.readEntry("mappy", "out_polygons_layer_name", None)
        self.assertTrue(found)
        self.assertEqual(value, "zzz_via_real_signal")

    def test_unchecked_checkbox_survives_real_toggle_save_and_reload(self):
        # Qt.CheckState is a plain Enum (not IntEnum) in this PyQt6 binding,
        # so bool(widget.checkState()) is True for every state including
        # Unchecked -- any enum member is truthy unless it defines __bool__.
        # readWidgetContent must use widget.isChecked() instead, otherwise
        # every checkbox is reported (and persisted) as checked no matter
        # its actual on-screen state.
        from mappy.qgismappy import Mappy

        dock = Mappy.instance.config_dock
        proj = QgsProject.instance()

        # real user interaction: click the checkbox (fires the real
        # stateChanged signal), then a real project save
        dock.auto_recompute_on_assign_unit.setChecked(True)
        proj.writeProject.emit(QDomDocument())
        value, found = proj.readEntry("mappy", "auto_recompute_on_assign_unit", None)
        self.assertEqual(value, "True")

        dock.auto_recompute_on_assign_unit.setChecked(False)
        proj.writeProject.emit(QDomDocument())
        value, found = proj.readEntry("mappy", "auto_recompute_on_assign_unit", None)
        self.assertEqual(value, "False")

        # simulate reopening the project: flip the live widget to the wrong
        # state first, then let the project's stored value win
        dock.auto_recompute_on_assign_unit.setChecked(True)
        proj.readProject.emit(QDomDocument())
        self.assertFalse(dock.auto_recompute_on_assign_unit.isChecked())

    def test_new_dock_reloads_settings_already_in_project_at_construction(self):
        from mappy.qgismappy_dockwidget import MappyDockWidget

        proj = QgsProject.instance()
        proj.writeEntry("mappy", "out_polygons_layer_name", "zzz_reloaded_on_init")

        # a project can already hold mappy settings before the dock exists,
        # e.g. when the plugin initializes after a project was auto-reopened
        fresh_dock = MappyDockWidget()
        try:
            self.assertEqual(fresh_dock.out_polygons_layer_name.text(), "zzz_reloaded_on_init")
        finally:
            proj.readProject.disconnect(fresh_dock.restoreSettingsFromProject)
            proj.writeProject.disconnect(fresh_dock.saveSettingsToProject)
