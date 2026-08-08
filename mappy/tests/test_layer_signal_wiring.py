from unittest.mock import patch

from qgis.core import QgsFeature, QgsGeometry, QgsProject, QgsVectorLayer

from mappy.tests import ExtendedUnitTesting


class TestLayerSignalWiring(ExtendedUnitTesting):
    """GUI-side plumbing that nudges the engine to check for pending
    changes after a commit on the configured lines/points layer -- see
    Mappy._rewire_layer_signals. Covers the signal-lifecycle correctness
    this codebase has a documented history of getting wrong on plugin
    reload/layer swaps (see qgismappy_dockwidget.connect_widgets' comment)."""

    def _make_lines_layer(self, name):
        layer = QgsVectorLayer("LineString?crs=EPSG:4326", name, "memory")
        QgsProject.instance().addMapLayer(layer)
        return layer

    def test_picking_a_lines_layer_in_the_dock_connects_it(self):
        from mappy.qgismappy import Mappy

        mappy = Mappy.instance
        dock = mappy.config_dock

        layer = self._make_lines_layer("zzz_wiring_lines_a")
        dock.get_widget_by_name("lines").setLayer(layer)

        self.assertIs(mappy._connected_lines_layer, layer)

    def test_committing_a_feature_starts_the_debounce_timer(self):
        from mappy.qgismappy import Mappy

        mappy = Mappy.instance
        dock = mappy.config_dock

        layer = self._make_lines_layer("zzz_wiring_lines_b")
        dock.get_widget_by_name("lines").setLayer(layer)

        mappy._pending_changes_timer.stop()
        self.assertFalse(mappy._pending_changes_timer.isActive())

        layer.startEditing()
        f = QgsFeature(layer.fields())
        f.setGeometry(QgsGeometry.fromWkt("LINESTRING(0 0, 1 1)"))
        layer.addFeature(f)
        layer.commitChanges()

        self.assertTrue(mappy._pending_changes_timer.isActive())
        mappy._pending_changes_timer.stop()

    def test_debounce_timeout_calls_engine_process_pending_changes(self):
        from mappy.qgismappy import Mappy

        mappy = Mappy.instance

        with patch.object(mappy.engine, "process_pending_changes") as process:
            mappy._process_pending_engine_changes()

        process.assert_called_once()

    def test_engine_error_during_drain_shows_alert_not_crash(self):
        from mappy.engine import EngineError
        from mappy.qgismappy import Mappy

        mappy = Mappy.instance

        with (
            patch.object(mappy.engine, "process_pending_changes", side_effect=EngineError("boom")),
            patch.object(mappy, "alert_box") as alert_box,
        ):
            mappy._process_pending_engine_changes()

        alert_box.assert_called_once_with("Error", "boom")

    def test_switching_lines_layer_disconnects_the_previous_one(self):
        from mappy.qgismappy import Mappy

        mappy = Mappy.instance
        dock = mappy.config_dock

        first = self._make_lines_layer("zzz_wiring_lines_c")
        second = self._make_lines_layer("zzz_wiring_lines_d")

        dock.get_widget_by_name("lines").setLayer(first)
        self.assertIs(mappy._connected_lines_layer, first)

        dock.get_widget_by_name("lines").setLayer(second)
        self.assertIs(mappy._connected_lines_layer, second)

        mappy._pending_changes_timer.stop()

        # committing on the now-disconnected old layer must not start the timer
        first.startEditing()
        f = QgsFeature(first.fields())
        f.setGeometry(QgsGeometry.fromWkt("LINESTRING(0 0, 1 1)"))
        first.addFeature(f)
        first.commitChanges()

        self.assertFalse(mappy._pending_changes_timer.isActive())

    def test_rewire_with_none_disconnects_cleanly(self):
        """Mirrors what unload() does -- disconnecting must not raise even
        though the layer was already connected (exercised directly rather
        than via unload() itself, since unload() tears down process-wide
        plugin state that other tests, e.g. test_plugin_reload.py, depend
        on running last)."""
        from mappy.qgismappy import Mappy

        mappy = Mappy.instance
        dock = mappy.config_dock

        layer = self._make_lines_layer("zzz_wiring_lines_e")
        dock.get_widget_by_name("lines").setLayer(layer)
        self.assertIs(mappy._connected_lines_layer, layer)

        mappy._rewire_layer_signals("lines", None)
        self.assertIsNone(mappy._connected_lines_layer)

        # a second disconnect-to-None must also not raise (nothing connected)
        mappy._rewire_layer_signals("lines", None)
