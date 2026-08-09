import tempfile
from pathlib import Path

import pytest
from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsCoordinateTransformContext,
    QgsField,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)

from mappy.tests import ExtendedUnitTesting


class TestRestorePointsAndFieldOnProjectReload(ExtendedUnitTesting):
    def _make_point_layer_on_disk(self, tmpdir, name, fields):
        mem = QgsVectorLayer("Point", name, "memory")
        mem.dataProvider().addAttributes([QgsField(f, QVariant.String) for f in fields])
        mem.updateFields()
        path = str(Path(tmpdir) / f"{name}.gpkg")
        QgsVectorFileWriter.writeAsVectorFormatV3(
            mem, path, QgsCoordinateTransformContext(), QgsVectorFileWriter.SaveVectorOptions()
        )
        layer = QgsVectorLayer(path, name, "ogr")
        QgsProject.instance().addMapLayer(layer)
        return layer

    @pytest.mark.order("last")
    def test_reloading_a_saved_project_keeps_the_saved_points_layer_and_field(self):
        # same bug as the "lines" combo (see
        # test_restore_lines_layer_on_project_reload.py), but for the
        # indicator points layer and its unit-name field combo: both go
        # through the same value_changed()->project-entry write path, so a
        # project reload used to reset them to the first point layer /
        # first field instead of what was saved.
        #
        # proj.clear() below wipes every layer in the shared, session-wide
        # QgsProject.instance() -- including ones other test modules (e.g.
        # test_core.py's Storage.points/lines) keep Python references to
        # for the rest of the session. Ordered last so this never runs
        # before something else that depends on those surviving.
        from mappy.qgismappy import Mappy

        dock = Mappy.instance.config_dock
        proj = QgsProject.instance()

        tmpdir = tempfile.mkdtemp()

        # target layer added in the middle, so it's neither first nor last
        _layer_a = self._make_point_layer_on_disk(tmpdir, "restore_reload_pts_a", ["alpha", "unit_name"])
        layer_b_target = self._make_point_layer_on_disk(
            tmpdir, "restore_reload_pts_b_target", ["alpha", "unit_name"]
        )
        _layer_c = self._make_point_layer_on_disk(tmpdir, "restore_reload_pts_c", ["alpha", "unit_name"])

        dock.points.setLayer(layer_b_target)
        self.assertEqual(dock.points.currentLayer(), layer_b_target)
        dock.units_field.setField("unit_name")
        self.assertEqual(dock.units_field.currentField(), "unit_name")

        project_path = str(Path(tmpdir) / "project.qgs")
        self.assertTrue(proj.write(project_path))

        # simulate "File > Open Project"
        proj.clear()
        self.assertTrue(proj.read(project_path), "failed to read back the saved project")

        reloaded_target = next(
            (lyr for lyr in proj.mapLayers().values() if lyr.name() == "restore_reload_pts_b_target"),
            None,
        )
        self.assertIsNotNone(reloaded_target)
        self.assertEqual(
            dock.points.currentLayer(),
            reloaded_target,
            "the points combo ended up on the wrong layer after reload",
        )
        self.assertEqual(
            dock.units_field.currentField(),
            "unit_name",
            "the units_field combo ended up on the wrong field after reload",
        )
