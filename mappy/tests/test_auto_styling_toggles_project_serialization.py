import tempfile
from pathlib import Path

import pytest
from qgis.core import QgsProject

from mappy.engine import EngineConfig
from mappy.mappy_utils import collect_parameters
from mappy.tests import ExtendedUnitTesting

TOGGLE_NAMES = ["auto_color_polygons", "auto_color_points", "auto_label_polygons", "auto_label_points"]


class TestAutoStylingTogglesProjectSerialization(ExtendedUnitTesting):
    def test_toggles_default_checked(self):
        from mappy.qgismappy import Mappy

        dock = Mappy.instance.config_dock
        for name in TOGGLE_NAMES:
            self.assertTrue(dock.get_widget_by_name(name).isChecked(), name)

    def test_unchecking_writes_to_the_project(self):
        # asserting right after setChecked(), with no save in between, would
        # instead observe stateChanged's raw Qt.CheckState int ("0"/"2"),
        # not "True"/"False" -- see
        # test_unchecked_checkbox_survives_real_toggle_save_and_reload in
        # test_save_settings_to_project.py. A real save (writeProject ->
        # saveSettingsToProject, driven off the actual widget value via
        # isChecked()) is what actually produces the correct string, and is
        # exactly what happens on a real project save.
        from qgis.PyQt.QtXml import QDomDocument

        from mappy.qgismappy import Mappy

        dock = Mappy.instance.config_dock
        proj = QgsProject.instance()

        for name in TOGGLE_NAMES:
            dock.get_widget_by_name(name).setChecked(False)

        proj.writeProject.emit(QDomDocument())

        for name in TOGGLE_NAMES:
            value, found = proj.readEntry("mappy", name, None)
            self.assertTrue(found, name)
            self.assertEqual(value.strip().lower(), "false", name)

        # restore for other tests sharing the same live dock/project instance
        for name in TOGGLE_NAMES:
            dock.get_widget_by_name(name).setChecked(True)

    @pytest.mark.order("last")
    def test_survives_a_real_save_clear_reload_cycle(self):
        # same save -> clear() -> read() round trip used to catch the
        # "limits layer reverts to the first layer" bug (see
        # test_restore_lines_layer_on_project_reload.py) -- makes sure a
        # plain QCheckBox setting isn't affected by anything related to
        # that fix (the restore guard added there only special-cases
        # QgsMapLayerComboBox's spurious layerChanged noise).
        #
        # proj.clear() below wipes every layer in the shared, session-wide
        # QgsProject.instance() -- including ones other test modules (e.g.
        # test_core.py's Storage.points/lines) keep Python references to
        # for the rest of the session. Ordered last so this never runs
        # before something else that depends on those surviving.
        from mappy.qgismappy import Mappy

        dock = Mappy.instance.config_dock
        proj = QgsProject.instance()

        for name in TOGGLE_NAMES:
            dock.get_widget_by_name(name).setChecked(False)

        tmpdir = tempfile.mkdtemp()
        project_path = str(Path(tmpdir) / "project.qgs")
        self.assertTrue(proj.write(project_path))

        proj.clear()
        self.assertTrue(proj.read(project_path), "failed to read back the saved project")

        for name in TOGGLE_NAMES:
            self.assertFalse(dock.get_widget_by_name(name).isChecked(), name)

        pars = collect_parameters(dock)
        config = EngineConfig.from_parameters(pars)
        self.assertFalse(config.auto_color_polygons)
        self.assertFalse(config.auto_color_points)
        self.assertFalse(config.auto_label_polygons)
        self.assertFalse(config.auto_label_points)

        # restore for other tests sharing the same live dock/project instance
        for name in TOGGLE_NAMES:
            dock.get_widget_by_name(name).setChecked(True)
