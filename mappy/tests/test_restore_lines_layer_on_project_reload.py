import tempfile
from pathlib import Path

from qgis.core import (
    QgsCoordinateTransformContext,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)

from mappy.tests import ExtendedUnitTesting


class TestRestoreLinesLayerOnProjectReload(ExtendedUnitTesting):
    def test_reloading_a_saved_project_keeps_the_saved_lines_layer(self):
        # regression test: reopening a saved project with multiple line
        # layers used to reset the "limits layer" (lines) combo to the
        # first layer in the list instead of the one that was saved. The
        # lines combo emits layerChanged on its own while it gets cleared
        # and repopulated during QgsProject.clear()/read(), and that used
        # to get written straight back into the project's "mappy/lines"
        # entry, clobbering the real value before restoreSettingsFromProject
        # ever read it back.
        from mappy.qgismappy import Mappy

        dock = Mappy.instance.config_dock
        proj = QgsProject.instance()

        tmpdir = tempfile.mkdtemp()

        def make_line_on_disk(name):
            mem = QgsVectorLayer("LineString", name, "memory")
            path = str(Path(tmpdir) / f"{name}.gpkg")
            QgsVectorFileWriter.writeAsVectorFormatV3(
                mem, path, QgsCoordinateTransformContext(), QgsVectorFileWriter.SaveVectorOptions()
            )
            layer = QgsVectorLayer(path, name, "ogr")
            QgsProject.instance().addMapLayer(layer)
            return layer

        # target layer added in the middle, so it's neither first nor last
        _layer_a = make_line_on_disk("restore_reload_line_a")
        layer_b_target = make_line_on_disk("restore_reload_line_b_target")
        _layer_c = make_line_on_disk("restore_reload_line_c")

        dock.lines.setLayer(layer_b_target)
        self.assertEqual(dock.lines.currentLayer(), layer_b_target)

        project_path = str(Path(tmpdir) / "project.qgs")
        self.assertTrue(proj.write(project_path))

        # simulate "File > Open Project": clear the in-memory project, then
        # read the just-saved file back, exactly like a real reopen.
        proj.clear()
        self.assertTrue(proj.read(project_path), "failed to read back the saved project")

        reloaded_target = next(
            (lyr for lyr in proj.mapLayers().values() if lyr.name() == "restore_reload_line_b_target"),
            None,
        )
        self.assertIsNotNone(reloaded_target)
        self.assertEqual(
            dock.lines.currentLayer(),
            reloaded_target,
            "the lines combo ended up on the wrong layer after reload",
        )
