import sqlite3
import tempfile
from pathlib import Path

from qgis.core import QgsFeature, QgsGeometry, QgsVectorLayer

from mappy.engine import dirty_queue
from mappy.engine.layers import add_layer_from_geopackage, write_layer_to_gpkg
from mappy.tests import ExtendedUnitTesting


class TestDirtyQueue(ExtendedUnitTesting):
    def _make_gpkg_lines_layer(self):
        tmpdir = tempfile.mkdtemp()
        gpkg_path = str(Path(tmpdir) / "probe.gpkg")

        src = QgsVectorLayer("LineString?crs=EPSG:4326", "source_contacts", "memory")
        f = QgsFeature(src.fields())
        f.setGeometry(QgsGeometry.fromWkt("LINESTRING(0 0, 1 1)"))
        src.dataProvider().addFeature(f)

        write_layer_to_gpkg(src, gpkg_path, "source_contacts")
        layer = add_layer_from_geopackage(gpkg_path, "source_contacts")
        return gpkg_path, layer

    def test_is_geopackage_backed(self):
        _, layer = self._make_gpkg_lines_layer()
        self.assertTrue(dirty_queue.is_geopackage_backed(layer))

        memory_layer = QgsVectorLayer("LineString?crs=EPSG:4326", "mem", "memory")
        self.assertFalse(dirty_queue.is_geopackage_backed(memory_layer))

    def test_ensure_dirty_queue_rejects_non_geopackage_layer(self):
        memory_layer = QgsVectorLayer("LineString?crs=EPSG:4326", "mem", "memory")
        with self.assertRaises(ValueError):
            dirty_queue.ensure_dirty_queue_for_layer(memory_layer, "lines")

    def test_commit_through_qgis_populates_dirty_queue(self):
        gpkg_path, layer = self._make_gpkg_lines_layer()
        dirty_queue.ensure_dirty_queue_for_layer(layer, "lines")

        self.assertEqual(dirty_queue.pending_count(gpkg_path), 0)

        # add
        layer.startEditing()
        new_feature = QgsFeature(layer.fields())
        new_feature.setGeometry(QgsGeometry.fromWkt("LINESTRING(2 2, 3 3)"))
        layer.addFeature(new_feature)
        layer.commitChanges()

        drained = dirty_queue.drain_dirty_queue(gpkg_path)
        self.assertEqual(len(drained["lines"]["added"]), 1)
        self.assertEqual(drained["lines"]["modified"], [])
        self.assertEqual(drained["lines"]["removed"], [])
        added_fid = drained["lines"]["added"][0]

        # queue was cleared by the drain
        self.assertEqual(dirty_queue.pending_count(gpkg_path), 0)

        # modify
        layer.startEditing()
        layer.changeGeometry(added_fid, QgsGeometry.fromWkt("LINESTRING(2 2, 5 5)"))
        layer.commitChanges()

        drained = dirty_queue.drain_dirty_queue(gpkg_path)
        self.assertEqual(drained["lines"]["modified"], [added_fid])

        # delete
        layer.startEditing()
        layer.deleteFeature(added_fid)
        layer.commitChanges()

        drained = dirty_queue.drain_dirty_queue(gpkg_path)
        self.assertEqual(drained["lines"]["removed"], [added_fid])

    def test_triggers_fire_for_any_writer_not_just_qgis(self):
        """The whole point of trigger-based tracking: a write that bypasses
        QGIS/GDAL's Python API entirely (e.g. a bulk-import script using
        ogr2ogr or spatialite directly) still gets picked up, because the
        trigger is attached to the table itself, not to any particular
        writer. Loading mod_spatialite here mirrors what any such external
        tool would have available -- GDAL's own GeoPackage driver already
        attaches spatial-index-maintenance triggers (calling ST_IsEmpty
        etc.) to every feature table it creates, so *no* writer, ours
        included, can insert into a GeoPackage feature table without some
        spatial SQL functions loaded; that's a GDAL/GeoPackage constraint
        that predates and is independent of mappy's own dirty-queue triggers."""
        gpkg_path, layer = self._make_gpkg_lines_layer()
        dirty_queue.ensure_dirty_queue_for_layer(layer, "lines")

        conn = sqlite3.connect(gpkg_path)
        try:
            conn.enable_load_extension(True)
            conn.execute("SELECT load_extension('mod_spatialite')")
            conn.execute("INSERT INTO source_contacts (geom, fid) VALUES (NULL, 999)")
            conn.commit()
        finally:
            conn.close()

        drained = dirty_queue.drain_dirty_queue(gpkg_path)
        self.assertEqual(drained["lines"]["added"], [999])

    def test_pending_count_before_install_is_zero(self):
        tmpdir = tempfile.mkdtemp()
        gpkg_path = str(Path(tmpdir) / "untouched.gpkg")
        Path(gpkg_path).touch()
        self.assertEqual(dirty_queue.pending_count(gpkg_path), 0)
