from mappy.engine import IncrementalMapEngine, ProcessingMapEngine
from mappy.tests import ExtendedUnitTesting


class TestIncrementalEngineToggle(ExtendedUnitTesting):
    """Mappy._ensure_engine_matches_config: swapping self.engine between
    ProcessingMapEngine (default) and IncrementalMapEngine (opt-in) based
    on the dock's "use_incremental_engine" checkbox."""

    def _make_setup(self):
        from mappy.qgismappy import Mappy

        mappy = Mappy.instance
        dock = mappy.config_dock
        # tests run against the shared dock singleton -- start every test
        # from a known state regardless of what an earlier test left it as
        dock.get_widget_by_name("use_incremental_engine").setChecked(False)
        mappy._refresh_engine_config()
        return mappy, dock

    def tearDown(self):
        from mappy.qgismappy import Mappy

        mappy = Mappy.instance
        dock = mappy.config_dock
        dock.get_widget_by_name("use_incremental_engine").setChecked(False)
        mappy._refresh_engine_config()

    def test_defaults_to_processing_engine(self):
        mappy, _dock = self._make_setup()
        self.assertIsInstance(mappy.engine, ProcessingMapEngine)
        self.assertNotIsInstance(mappy.engine, IncrementalMapEngine)

    def test_checking_the_box_swaps_to_incremental_engine(self):
        mappy, dock = self._make_setup()

        dock.get_widget_by_name("use_incremental_engine").setChecked(True)
        mappy._refresh_engine_config()

        self.assertIsInstance(mappy.engine, IncrementalMapEngine)

    def test_unchecking_the_box_swaps_back(self):
        mappy, dock = self._make_setup()

        dock.get_widget_by_name("use_incremental_engine").setChecked(True)
        mappy._refresh_engine_config()
        self.assertIsInstance(mappy.engine, IncrementalMapEngine)

        dock.get_widget_by_name("use_incremental_engine").setChecked(False)
        mappy._refresh_engine_config()
        self.assertIsInstance(mappy.engine, ProcessingMapEngine)
        self.assertNotIsInstance(mappy.engine, IncrementalMapEngine)

    def test_refreshing_without_changing_the_box_keeps_the_same_engine_instance(self):
        mappy, _dock = self._make_setup()
        first = mappy.engine

        mappy._refresh_engine_config()

        self.assertIs(mappy.engine, first)

    def test_config_carries_over_after_a_swap(self):
        mappy, dock = self._make_setup()

        dock.get_widget_by_name("use_incremental_engine").setChecked(True)
        mappy._refresh_engine_config()

        self.assertEqual(mappy.engine.config.use_incremental_engine, True)
