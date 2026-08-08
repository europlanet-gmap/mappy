from pathlib import Path
from unittest.mock import patch

from qgis.core import (
    QgsCoordinateTransformContext,
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QVariant

from mappy.engine import EngineConfig, IncrementalMapEngine, topology_db
from mappy.engine.layers import add_layer_from_geopackage
from mappy.tests import ExtendedUnitTesting

OUTPUT = "/tmp/zzz_incremental_lines_test_output.gpkg"
SOURCE = "/tmp/zzz_incremental_lines_test_source.gpkg"


def _write_gpkg_layer(layer, gpkg_path, layer_name):
    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = "GPKG"
    opts.layerName = layer_name
    if Path(gpkg_path).exists():
        opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    else:
        opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
    QgsVectorFileWriter.writeAsVectorFormatV3(layer, gpkg_path, QgsCoordinateTransformContext(), opts)


class TestIncrementalLines(ExtendedUnitTesting):
    """Three adjacent unit squares in a row, (0,0)-(3,1), split by two
    dividers at x=1 and x=2, with indicator points UNIT_A/UNIT_B/UNIT_C at
    (0.5,0.5)/(1.5,0.5)/(2.5,0.5)."""

    def setUp(self):
        self._engines = []

    def tearDown(self):
        # an engine's sidecar sqlite3 connection must be closed, and every
        # QGIS layer backed by this test's files removed from the project,
        # before those files get deleted/recreated by the next test -- a
        # lingering open handle (Python-side sqlite3 connection or a GDAL
        # dataset QGIS is still holding onto) was observed to intermittently
        # corrupt the next test's file operations ("disk I/O error")
        for engine in self._engines:
            engine.close()
        project = QgsProject.instance()
        stale = [
            layer_id
            for layer_id, layer in project.mapLayers().items()
            if OUTPUT in layer.dataProvider().dataSourceUri() or SOURCE in layer.dataProvider().dataSourceUri()
        ]
        project.removeMapLayers(stale)
        self.clean_up([OUTPUT, topology_db.sidecar_path_for(OUTPUT), SOURCE])

    def _make_engine(self):
        self.clean_up([OUTPUT, topology_db.sidecar_path_for(OUTPUT), SOURCE])

        lines_mem = QgsVectorLayer("LineString?crs=EPSG:4326", "src_lines", "memory")
        line_fids = {}
        for _name, wkt in (
            ("outer", "LINESTRING(0 0, 3 0, 3 1, 0 1, 0 0)"),
            ("divider1", "LINESTRING(1 0, 1 1)"),
            ("divider2", "LINESTRING(2 0, 2 1)"),
        ):
            f = QgsFeature(lines_mem.fields())
            f.setGeometry(QgsGeometry.fromWkt(wkt))
            lines_mem.dataProvider().addFeature(f)
        _write_gpkg_layer(lines_mem, SOURCE, "source_contacts")
        lines = add_layer_from_geopackage(SOURCE, "source_contacts")
        # re-fetch fids as actually assigned by the gpkg writer, keyed by name via geometry match
        for name, wkt in (
            ("outer", "LINESTRING(0 0, 3 0, 3 1, 0 1, 0 0)"),
            ("divider1", "LINESTRING(1 0, 1 1)"),
            ("divider2", "LINESTRING(2 0, 2 1)"),
        ):
            target = QgsGeometry.fromWkt(wkt)
            for f in lines.getFeatures():
                if f.geometry().equals(target):
                    line_fids[name] = f.id()
                    break

        points_mem = QgsVectorLayer("Point?crs=EPSG:4326", "src_points", "memory")
        points_mem.dataProvider().addAttributes([QgsField("unit_name", QVariant.String)])
        points_mem.updateFields()
        for xy, unit in (((0.5, 0.5), "UNIT_A"), ((1.5, 0.5), "UNIT_B"), ((2.5, 0.5), "UNIT_C")):
            f = QgsFeature(points_mem.fields())
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(*xy)))
            f["unit_name"] = unit
            points_mem.dataProvider().addFeature(f)
        _write_gpkg_layer(points_mem, SOURCE, "source_indicators")
        points = add_layer_from_geopackage(SOURCE, "source_indicators")

        config = EngineConfig(
            lines=lines,
            points=points,
            output=OUTPUT,
            out_polygons_layer_name="zzz_incr_lines_final_map",
            units_field="unit_name",
        )
        engine = IncrementalMapEngine(config)
        self._engines.append(engine)
        return engine, lines, points, line_fids

    def test_deleting_a_line_merges_two_polygons_with_lower_fid_tiebreak(self):
        engine, lines, _points, line_fids = self._make_engine()
        engine.recompute_map()
        self.assertEqual(engine.get_polygons_layer().featureCount(), 3)
        # this scenario's 1-changed-line-out-of-3-faces ratio (33%) exceeds
        # the default oversized-batch fallback threshold (30%) -- raise it
        # so this test actually exercises the incremental merge path
        # instead of silently falling back to a full recompute
        engine.config.incremental_dirty_fraction_fallback = 1.0

        left_before = engine.find_polygon_at_point(QgsPointXY(0.5, 0.5))
        right_before = engine.find_polygon_at_point(QgsPointXY(1.5, 0.5))
        winner = left_before if left_before.id() < right_before.id() else right_before
        expected_unit = winner["unit_name"]

        lines.startEditing()
        lines.deleteFeature(line_fids["divider1"])
        lines.commitChanges()

        engine.process_pending_changes()

        polygons = engine.get_polygons_layer()
        self.assertEqual(polygons.featureCount(), 2, "the two merged squares must collapse into one output feature")

        merged = engine.find_polygon_at_point(QgsPointXY(0.5, 0.5))
        self.assertEqual(merged["unit_name"], expected_unit)
        self.assertAlmostEqual(merged.geometry().area(), 2.0, places=6)

        # square 3 (unaffected by this edit) must be untouched
        untouched = engine.find_polygon_at_point(QgsPointXY(2.5, 0.5))
        self.assertEqual(untouched["unit_name"], "UNIT_C")

    def test_adding_a_line_splits_a_polygon(self):
        engine, lines, _points, _line_fids = self._make_engine()
        engine.recompute_map()
        engine.config.incremental_dirty_fraction_fallback = 1.0

        original = engine.find_polygon_at_point(QgsPointXY(2.5, 0.5))
        original_uuid = original["mappy_face_uuid"]

        # split square 3 (2,0)-(3,1) at x=2.3 -- UNIT_C at (2.5, 0.5) ends up
        # only in the right half; the left half has no indicator
        lines.startEditing()
        new_feature = QgsFeature(lines.fields())
        new_feature.setGeometry(QgsGeometry.fromWkt("LINESTRING(2.3 0, 2.3 1)"))
        lines.addFeature(new_feature)
        lines.commitChanges()

        engine.process_pending_changes()

        polygons = engine.get_polygons_layer()
        self.assertEqual(polygons.featureCount(), 4)

        right_half = engine.find_polygon_at_point(QgsPointXY(2.6, 0.5))
        left_half = engine.find_polygon_at_point(QgsPointXY(2.15, 0.5))
        self.assertIsNotNone(right_half)
        self.assertIsNotNone(left_half)
        self.assertEqual(right_half["unit_name"], "UNIT_C")
        self.assertIn(left_half["unit_name"], (None, ""))

        # one side keeps the original polygon's identity (uuid), the other is new
        uuids = {right_half["mappy_face_uuid"], left_half["mappy_face_uuid"]}
        self.assertIn(original_uuid, uuids)
        self.assertEqual(len(uuids), 2)

        self.assertAlmostEqual(right_half.geometry().area() + left_half.geometry().area(), 1.0, places=6)

    def test_modifying_a_line_geometry_shifts_the_boundary(self):
        engine, lines, _points, line_fids = self._make_engine()
        engine.recompute_map()
        engine.config.incremental_dirty_fraction_fallback = 1.0

        # move divider1 from x=1 to x=1.3 (point UNIT_B at 1.5,0.5 stays on
        # the right side, safely away from the new boundary)
        lines.startEditing()
        lines.changeGeometry(line_fids["divider1"], QgsGeometry.fromWkt("LINESTRING(1.3 0, 1.3 1)"))
        lines.commitChanges()

        engine.process_pending_changes()

        left = engine.find_polygon_at_point(QgsPointXY(0.5, 0.5))
        right = engine.find_polygon_at_point(QgsPointXY(1.5, 0.5))
        self.assertEqual(left["unit_name"], "UNIT_A")
        self.assertEqual(right["unit_name"], "UNIT_B")
        self.assertAlmostEqual(left.geometry().area(), 1.3, places=6)
        self.assertAlmostEqual(right.geometry().area(), 0.7, places=6)

    def test_oversized_batch_falls_back_to_full_recompute(self):
        engine, lines, _points, line_fids = self._make_engine()
        engine.recompute_map()
        engine.config.incremental_dirty_fraction_fallback = 0.0  # force fallback on any change at all

        lines.startEditing()
        lines.deleteFeature(line_fids["divider1"])
        lines.commitChanges()

        with patch.object(engine, "recompute_map", wraps=engine.recompute_map) as recompute:
            engine.process_pending_changes()

        recompute.assert_called_once()
        # the fallback still produces a correct map
        self.assertEqual(engine.get_polygons_layer().featureCount(), 2)

    def test_no_pending_line_changes_is_a_harmless_noop(self):
        engine, _lines, _points, _line_fids = self._make_engine()
        engine.recompute_map()

        with patch.object(engine, "get_polygons_layer", wraps=engine.get_polygons_layer) as get_layer:
            engine.process_pending_changes()
        # points-path already calls get_polygons_layer defensively when
        # there ARE pending point changes; with nothing dirty at all on
        # either role, neither path should touch it
        get_layer.assert_not_called()
