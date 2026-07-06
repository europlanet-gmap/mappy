from unittest.mock import patch

from qgis.core import QgsProject
from qgis.PyQt.QtWidgets import QMainWindow, QToolBar

from mappy.tests import ExtendedUnitTesting


class TestPluginReload(ExtendedUnitTesting):
    def test_reload_leaves_only_new_dock_wired(self):
        import qgis.utils
        from mappy.qgismappy import Mappy

        old_mappy = Mappy.instance
        old_dock = old_mappy.config_dock

        # conftest's iface is a MagicMock, so iface.mainWindow() and
        # iface.addToolBar() normally return MagicMocks too -- fine for most
        # tests, but unload() now passes them to real Qt APIs
        # (removeToolBar/QAction parenting) that reject non-Qt objects. Give
        # it real Qt objects here, matching what real QGIS always provides.
        real_window = QMainWindow()
        old_mappy.toolbar = QToolBar(real_window)
        with patch.object(old_mappy.iface, "mainWindow", return_value=real_window):
            ok = qgis.utils.reloadPlugin("mappy")
        print("RELOAD OK:", ok)

        from mappy.qgismappy import Mappy as ReloadedMappy
        new_mappy = ReloadedMappy.instance
        new_dock = new_mappy.config_dock

        print("SAME INSTANCE:", old_mappy is new_mappy)
        print("SAME DOCK:", old_dock is new_dock)

        proj = QgsProject.instance()

        # old dock's connections must be gone; disconnecting again should raise
        with self.assertRaises(TypeError):
            proj.writeProject.disconnect(old_dock.saveSettingsToProject)

        # new dock must still be properly wired
        proj.writeProject.disconnect(new_dock.saveSettingsToProject)  # must not raise
        proj.writeProject.connect(new_dock.saveSettingsToProject)  # reconnect for later tests
