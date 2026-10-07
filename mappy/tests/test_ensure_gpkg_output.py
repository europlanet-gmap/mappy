import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mappy.tests import ExtendedUnitTesting


class TestEnsureGpkgOutput(ExtendedUnitTesting):
    def _make_setup(self):
        from mappy.qgismappy import Mappy

        mappy = Mappy.instance
        return mappy, mappy.config_dock

    def test_missing_extension_gets_appended_and_persisted(self):
        # regression test: recomputing with an output path missing the
        # .gpkg extension used to silently write a file QGIS then couldn't
        # reload -- the extension must now be added automatically, and the
        # fix must stick (both the dock widget and the live engine config),
        # not just the local pars dict this call happened to receive
        mappy, dock = self._make_setup()
        tmpdir = tempfile.mkdtemp()
        no_ext_path = str(Path(tmpdir) / "mymap")
        pars = {"output": no_ext_path}

        with patch.object(mappy, "alert_box") as alert_box:
            ok = mappy._ensure_gpkg_output(pars)

        self.assertTrue(ok)
        alert_box.assert_not_called()
        expected = no_ext_path + ".gpkg"
        self.assertEqual(pars["output"], expected)
        self.assertEqual(dock.get_widget_by_name("output").filePath(), expected)
        self.assertEqual(mappy.engine.config.output, expected)

    def test_already_correct_extension_is_left_untouched(self):
        mappy, dock = self._make_setup()
        tmpdir = tempfile.mkdtemp()
        path = str(Path(tmpdir) / "mymap.gpkg")
        pars = {"output": path}

        ok = mappy._ensure_gpkg_output(pars)

        self.assertTrue(ok)
        self.assertEqual(pars["output"], path)

    def test_missing_output_path_shows_alert(self):
        mappy, dock = self._make_setup()
        pars = {"output": ""}

        with patch.object(mappy, "alert_box") as alert_box:
            ok = mappy._ensure_gpkg_output(pars)

        self.assertFalse(ok)
        alert_box.assert_called_once()
        self.assertIn("Missing output", alert_box.call_args.args[1])

    def test_nonexistent_output_folder_shows_alert(self):
        mappy, dock = self._make_setup()
        pars = {"output": "/this/folder/does/not/exist/mymap.gpkg"}

        with patch.object(mappy, "alert_box") as alert_box:
            ok = mappy._ensure_gpkg_output(pars)

        self.assertFalse(ok)
        alert_box.assert_called_once()
        self.assertIn("does not exist", alert_box.call_args.args[1])

    # root bypasses permission bits, so the chmod below leaves the folder
    # writable -- the case in CI, whose qgis/qgis containers run as root.
    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root ignores folder permissions")
    def test_unwritable_output_folder_shows_alert(self):
        mappy, dock = self._make_setup()
        tmpdir = tempfile.mkdtemp()
        os.chmod(tmpdir, 0o500)  # read+execute only, no write
        try:
            pars = {"output": str(Path(tmpdir) / "mymap.gpkg")}

            with patch.object(mappy, "alert_box") as alert_box:
                ok = mappy._ensure_gpkg_output(pars)

            self.assertFalse(ok)
            alert_box.assert_called_once()
            self.assertIn("not writable", alert_box.call_args.args[1])
        finally:
            os.chmod(tmpdir, 0o700)
