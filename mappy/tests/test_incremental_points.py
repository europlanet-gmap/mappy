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

OUTPUT = "/tmp/zzz_incremental_points_test_output.gpkg"
SOURCE = "/tmp/zzz_incremental_points_test_source.gpkg"


def _write_gpkg_layer(layer, gpkg_path, layer_name):
    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = "GPKG"
    opts.layerName = layer_name
    if Path(gpkg_path).exists():
        opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    else:
        opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
    QgsVectorFileWriter.writeAsVectorFormatV3(layer, gpkg_path, QgsCoordinateTransformContext(), opts)


class TestIncrementalPoints(ExtendedUnitTesting):
    def setUp(self):
        self._engines = []

    def tearDown(self):
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

    def _make_engine(self, with_initial_point=True):
        self.clean_up([OUTPUT, topology_db.sidecar_path_for(OUTPUT), SOURCE])

        # two adjacent unit squares, only the left one has an indicator point
        lines_mem = QgsVectorLayer("LineString?crs=EPSG:4326", "src_lines", "memory")
        for wkt in ("LINESTRING(0 0, 2 0, 2 1, 0 1, 0 0)", "LINESTRING(1 0, 1 1)"):
            f = QgsFeature(lines_mem.fields())
            f.setGeometry(QgsGeometry.fromWkt(wkt))
            lines_mem.dataProvider().addFeature(f)
        _write_gpkg_layer(lines_mem, SOURCE, "source_contacts")
        lines = add_layer_from_geopackage(SOURCE, "source_contacts")

        points_mem = QgsVectorLayer("Point?crs=EPSG:4326", "src_points", "memory")
        points_mem.dataProvider().addAttributes([QgsField("unit_name", QVariant.String)])
        points_mem.updateFields()
        if with_initial_point:
            f = QgsFeature(points_mem.fields())
            f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(0.5, 0.5)))
            f["unit_name"] = "UNIT_A"
            points_mem.dataProvider().addFeature(f)
        _write_gpkg_layer(points_mem, SOURCE, "source_indicators")
        points = add_layer_from_geopackage(SOURCE, "source_indicators")

        config = EngineConfig(
            lines=lines,
            points=points,
            output=OUTPUT,
            out_polygons_layer_name="zzz_incr_pts_final_map",
            units_field="unit_name",
        )
        engine = IncrementalMapEngine(config)
        self._engines.append(engine)
        return engine, lines, points

    def test_new_point_with_unit_propagates_without_recompute(self):
        engine, _lines, points = self._make_engine()
        engine.recompute_map()

        points.startEditing()
        f = QgsFeature(points.fields())
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(1.5, 0.5)))
        f["unit_name"] = "UNIT_B"
        points.addFeature(f)
        points.commitChanges()

        with patch.object(engine, "recompute_map") as recompute:
            engine.process_pending_changes()
        recompute.assert_not_called()

        polygon = engine.find_polygon_at_point(QgsPointXY(1.5, 0.5))
        self.assertIsNotNone(polygon)
        self.assertEqual(polygon["unit_name"], "UNIT_B")

    def test_point_with_empty_unit_value_is_not_propagated(self):
        engine, _lines, points = self._make_engine()
        engine.recompute_map()

        points.startEditing()
        f = QgsFeature(points.fields())
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(1.5, 0.5)))
        # leave unit_name unset
        points.addFeature(f)
        points.commitChanges()

        engine.process_pending_changes()

        polygon = engine.find_polygon_at_point(QgsPointXY(1.5, 0.5))
        self.assertIsNotNone(polygon)
        self.assertIn(polygon["unit_name"], (None, ""))

    def test_moved_point_updates_the_new_polygon(self):
        engine, _lines, points = self._make_engine()
        engine.recompute_map()

        # move the existing UNIT_A point from the left square into the right one
        existing = next(points.getFeatures())
        points.startEditing()
        points.changeGeometry(existing.id(), QgsGeometry.fromPointXY(QgsPointXY(1.5, 0.5)))
        points.commitChanges()

        engine.process_pending_changes()

        right_polygon = engine.find_polygon_at_point(QgsPointXY(1.5, 0.5))
        self.assertEqual(right_polygon["unit_name"], "UNIT_A")

    def test_no_pending_changes_is_a_harmless_noop(self):
        engine, _lines, _points = self._make_engine()
        engine.recompute_map()

        with patch.object(engine, "get_polygons_layer") as get_layer:
            engine.process_pending_changes()
        get_layer.assert_not_called()

    def test_point_committed_before_first_recompute_drains_without_raising(self):
        engine, _lines, points = self._make_engine(with_initial_point=False)
        # note: no engine.recompute_map() call at all yet -- the polygon
        # layer/output gpkg don't exist

        points.startEditing()
        f = QgsFeature(points.fields())
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(0.5, 0.5)))
        f["unit_name"] = "UNIT_A"
        points.addFeature(f)
        points.commitChanges()

        engine.process_pending_changes()  # must not raise

        from mappy.engine import dirty_queue

        # drained (and discarded) rather than left to accumulate forever
        self.assertEqual(dirty_queue.pending_count(SOURCE), 0)
