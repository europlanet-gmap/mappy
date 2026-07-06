import atexit
import os
import sys
import pytest
from pathlib import Path
from qgis.core import QgsApplication

_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])

# Force an offscreen Qt platform so tests don't depend on (or interfere with)
# a real display: on a live X session with no window manager, GUI calls made
# by the plugin (e.g. showing a dock widget) can hang waiting on a window
# manager handshake that will never come.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# pytest's unittest.TestCase integration re-invokes session-scoped autouse
# fixtures once per test module instead of caching a single instance for the
# whole run. A second invocation would re-run initQgis()/startPlugin() against
# the still-live QgsApplication from the first, and its finalizer would call
# exitQgis() while later modules still need it (or a second time at process
# exit) -- unregistering the "mappy" processing provider and eventually
# crashing. Guard so the real setup/teardown happens exactly once per process.
_qgis_env = None


@pytest.fixture(scope="session", autouse=True)
def qgis_app():
    """Initializes a headless QGIS application instance for testing."""
    global _qgis_env

    if _qgis_env is not None:
        yield _qgis_env
        return

    qgis_env = QgsApplication([], True)
    qgis_env.initQgis()

    sys.path.append("/usr/share/qgis/python/plugins/")
    from processing.core.Processing import Processing
    Processing.initialize()

    # Register and start the plugin using QGIS's own mechanism.
    # startPlugin requires qgis.utils.iface; use a MagicMock to satisfy
    # GUI calls (addToolBar, addDockWidget, etc.) in headless mode.
    from unittest.mock import MagicMock
    import qgis.utils
    if _PROJECT_ROOT not in qgis.utils.plugin_paths:
        qgis.utils.plugin_paths.insert(0, _PROJECT_ROOT)
    # Scan plugin_paths for metadata.txt files — required before startPlugin
    qgis.utils.updateAvailablePlugins()
    mock_iface = MagicMock()
    # Qt6 strict type-checking: QAction rejects MagicMock as a QObject parent
    mock_iface.mainWindow.return_value = None
    qgis.utils.iface = mock_iface
    qgis.utils.loadPlugin("mappy")
    qgis.utils.startPlugin("mappy")

    _qgis_env = qgis_env
    # Tear down at real process exit rather than in the fixture's own
    # finalizer, since that finalizer can run before other test modules
    # that still expect the shared instance to be alive (see guard above).
    atexit.register(qgis_env.exitQgis)

    yield qgis_env