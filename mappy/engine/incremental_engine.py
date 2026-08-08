"""IncrementalMapEngine: Phases 1-3 of mappy's incremental-engine plan.

Phase 1 builds and maintains a real SpatiaLite ISO topology (see
topology_db.py) in a sidecar database alongside the conventional
full-recompute pipeline, as a foundation for eventually regenerating only
the polygons an edit actually affects -- recompute_map() still does a full
ProcessingMapEngine rebuild every time, the topology is just a byproduct.
It also stamps a stable uuid (`mappy_face_uuid`) onto every output polygon
feature, matched to its topology face via a representative point (the
output layer and the topology are built by two separate pipelines --
mapconstruction's polygonize/extend-lines chain vs. TopoGeo_AddLineString --
so exact geometry equality isn't assumed).

Phase 2 adds the cheap half of process_pending_changes(): draining
dirty-queue rows for the *points* layer (see dirty_queue.py) and
propagating a changed point's unit value straight into its containing
polygon, with no geometry regeneration and no topology involved.

Phase 3 adds the hard half: draining dirty-queue rows for the *lines*
layer and regenerating only the polygons an edit actually affects.
Because the topology is a real ISO SQL/MM engine (not a hand-rolled cache),
the fiddly part -- correctly detecting and applying face splits/merges as
edges are added/removed -- is SpatiaLite's job, not this module's: removing
an edge that separated two faces returns the new merged face id directly
(no BFS/connected-component code needed here), and adding a line that
splits a face keeps one side's face id and creates a new one for the other.
What this module still owns (the same shape of glue topology-manager keeps
on top of PostGIS topology): mapping source-line fids to the edges they
produced, mapping topology faces to output-polygon-layer features, running
the merge-conflict tiebreak, and syncing the output layer.
"""

import uuid

from qgis.core import Qgis, QgsFeature, QgsFeatureRequest, QgsField, QgsGeometry, QgsMessageLog
from qgis.PyQt.QtCore import QVariant

from . import dirty_queue, topology_db
from .interface import EngineError, TopologyValidationReport
from .processing_engine import ProcessingMapEngine

TOPOLOGY_NAME = "mappy_topo"
UUID_FIELD = "mappy_face_uuid"


class IncrementalMapEngine(ProcessingMapEngine):
    def __init__(self, config=None, parent=None):
        super().__init__(config, parent)
        self._topology_conn = None

    def close(self) -> None:
        """Closes the sidecar topology connection, if open. Not called
        automatically anywhere in this engine's own lifecycle (there's no
        single obvious "this engine is done" hook -- Mappy keeps one alive
        for the whole plugin session); callers that create short-lived
        engine instances (tests included) should call this explicitly
        rather than relying on garbage collection, since a lingering open
        sqlite3 handle to the sidecar file can collide with a later
        recreate/delete of the same path."""
        if self._topology_conn is not None:
            self._topology_conn.close()
            self._topology_conn = None

    def _topology_connection(self):
        if self.config.output == "":
            raise EngineError("Missing output GeoPackage path; cannot locate the topology sidecar database.")
        sidecar_path = topology_db.sidecar_path_for(self.config.output)
        if self._topology_conn is None:
            self._topology_conn = topology_db.get_connection(sidecar_path)
        return self._topology_conn

    def _ensure_dirty_tracking(self) -> None:
        """Installs dirty-queue triggers (see dirty_queue.py) on whichever
        of the configured lines/points layers are GeoPackage-backed and
        don't have them yet. Idempotent and cheap, so it's safe to call
        both as part of recompute_map()'s bootstrap and defensively at the
        start of process_pending_changes() (self-healing if a layer was
        swapped in after the last recompute, or if this engine instance is
        fresh and recompute_map() hasn't run yet)."""
        for layer, role in ((self.config.lines, "lines"), (self.config.points, "points")):
            if layer is not None and dirty_queue.is_geopackage_backed(layer):
                dirty_queue.ensure_dirty_queue_for_layer(layer, role)

    def recompute_map(self) -> None:
        """Full rebuild (inherited, unchanged), then rebuild the topology
        from scratch against the just-recomputed lines layer, and re-stamp
        every output polygon with a fresh face uuid."""
        super().recompute_map()
        self._ensure_dirty_tracking()
        self._rebuild_topology()
        self._stamp_polygon_uuids()

    def _prepare_line_geometry(self, geometry: QgsGeometry) -> QgsGeometry:
        """Forgives near-miss coordinates at intended junctions between
        *different* line features -- real digitized data essentially never
        has exact floating-point coincidence there, but SpatiaLite's ISO
        topology engine requires it unless told otherwise.

        This does NOT use CreateTopology's own `tolerance` parameter: found
        empirically that this SpatiaLite build (5.1.0) silently rejects any
        non-integer tolerance there -- CreateTopology returns -1 (a no-op
        failure, no exception) for every fractional value tried (plain
        literals, bound parameters, explicit CAST AS REAL, the 4-arg
        has_z form, multiple SRIDs -- all fail identically), while integer
        values (0, 1, 2, ...) work fine. So the topology itself is always
        created with tolerance=0 (see ensure_topology calls below), and the
        forgiveness happens here instead: snapping every coordinate to a
        fine grid (config.topology_tolerance wide) before the geometry ever
        reaches the topology means two points that were merely close
        together become *exactly* equal, satisfying the topology's exact-
        match requirement without needing it to do any snapping itself.
        removeDuplicateNodes afterward cleans up any now-literal duplicate
        vertices the grid-snap produced (mirrors
        native:removeduplicatevertices, already used by
        ProcessingMapEngine's mapconstruction pipeline)."""
        cleaned = geometry.snappedToGrid(self.config.topology_tolerance, self.config.topology_tolerance)
        cleaned.removeDuplicateNodes(self.config.topology_tolerance)
        return cleaned

    def _rebuild_topology(self) -> None:
        conn = self._topology_connection()
        topology_db.drop_topology(conn, TOPOLOGY_NAME)
        topology_db.ensure_topology(conn, TOPOLOGY_NAME)
        topology_db.clear_edge_sources(conn)
        topology_db.clear_face_polygons(conn)

        for feature in self.config.lines.getFeatures():
            geometry = feature.geometry()
            if geometry is None or geometry.isEmpty():
                continue
            geometry = self._prepare_line_geometry(geometry)
            edge_ids = topology_db.add_linestring(conn, TOPOLOGY_NAME, geometry.asWkt())
            for edge_id in edge_ids:
                topology_db.record_edge_source(conn, edge_id, feature.id())

    def _ensure_uuid_field(self, polygons_layer) -> int:
        """Ensures polygons_layer has a mappy_face_uuid text field, adding
        it if missing. Returns its field index."""
        field_index = polygons_layer.fields().indexFromName(UUID_FIELD)
        if field_index != -1:
            return field_index

        was_read_only = polygons_layer.readOnly()
        polygons_layer.setReadOnly(False)
        polygons_layer.dataProvider().addAttributes([QgsField(UUID_FIELD, QVariant.String)])
        polygons_layer.updateFields()
        polygons_layer.setReadOnly(was_read_only)
        return polygons_layer.fields().indexFromName(UUID_FIELD)

    def _stamp_polygon_uuids(self) -> None:
        """Matches every current topology face to its corresponding output
        polygon feature (via a representative point inside the face -- the
        two are computed by separate pipelines, so exact geometry equality
        isn't assumed) and stamps a stable uuid on it, recorded in
        mappy_face_polygon. This is what lets later incremental syncs
        update/insert/delete the right output feature for a given face
        without redoing this matching from scratch."""
        try:
            polygons_layer = self.get_polygons_layer()
        except EngineError:
            return

        conn = self._topology_connection()
        uuid_field_index = self._ensure_uuid_field(polygons_layer)

        was_read_only = polygons_layer.readOnly()
        polygons_layer.setReadOnly(False)
        polygons_layer.startEditing()

        for face_id in topology_db.list_face_ids(conn, TOPOLOGY_NAME):
            face_wkt = topology_db.get_face_geometry_wkt(conn, TOPOLOGY_NAME, face_id)
            if not face_wkt:
                continue
            face_geom = QgsGeometry.fromWkt(face_wkt)
            rep_point = face_geom.pointOnSurface().asPoint()
            polygon_feature = self.find_polygon_at_point(rep_point)
            if polygon_feature is None:
                continue
            face_uuid = str(uuid.uuid4())
            polygons_layer.changeAttributeValue(polygon_feature.id(), uuid_field_index, face_uuid)
            topology_db.map_face_to_polygon(conn, face_id, face_uuid)

        polygons_layer.commitChanges()
        polygons_layer.setReadOnly(was_read_only)

    def process_pending_changes(self) -> None:
        self._ensure_dirty_tracking()
        self._process_pending_point_changes()
        self._process_pending_line_changes()

    def _process_pending_point_changes(self) -> None:
        """Points never affect polygon geometry, only the point-in-polygon
        attribute join -- so this needs no topology involvement at all,
        unlike the lines path below. For each added/moved point that
        already carries a units_field value, resolve which polygon it
        currently falls in and propagate the value straight into that
        polygon's attribute, reusing the same helper assign_unit() uses.

        Deliberately not handled here (accepted gaps, consistent with
        drop_duplicate_points_per_polygon's existing lowest-fid tiebreak
        imprecision elsewhere in this engine): a *removed* point's old
        polygon isn't re-resolved from a remaining candidate indicator, and
        a *moved* point's previous polygon isn't revisited either -- both
        require knowing the point's prior geometry, which the dirty-queue
        trigger doesn't capture (fid + change type only). Both are left
        stale until the next full recompute_map(), which rebuilds every
        polygon's attribute from scratch from whatever points exist then.
        """
        points_layer = self.config.points
        if points_layer is None or not dirty_queue.is_geopackage_backed(points_layer):
            return

        path, _ = dirty_queue.layer_source_parts(points_layer)
        changes = dirty_queue.drain_dirty_queue_for_layer(path, "points")
        changed_fids = changes["added"] + changes["modified"]
        if not changed_fids:
            return

        try:
            self.get_polygons_layer()
        except EngineError:
            # map not generated yet, or units_field unconfigured -- nothing
            # to propagate into; a later full recompute rebuilds every
            # polygon's unit attribute from scratch from all current points
            # regardless, so draining-and-discarding here is harmless
            return

        units_field = self.config.units_field
        field_index = points_layer.fields().indexFromName(units_field)
        if field_index == -1:
            return

        for fid in changed_fids:
            point_feature = points_layer.getFeature(fid)
            if not point_feature.isValid():
                continue
            unit_text = point_feature[units_field]
            if unit_text in (None, ""):
                continue
            polygon_feature = self.find_polygon_at_point(point_feature.geometry().asPoint())
            if polygon_feature is None:
                continue
            self._propagate_point_unit_to_polygon(polygon_feature, str(unit_text))

    def _process_pending_line_changes(self) -> None:
        """Drains dirty rows for the lines layer and regenerates only the
        polygon(s) affected -- see this module's docstring for why the
        split/merge detection itself is SpatiaLite's job, not ours.

        Shape: (1) apply every removal first (removed + modified lines lose
        their old edges -- ST_RemEdgeNewFace tells us directly which faces
        merged as a result), (2) then every addition (added + modified
        lines get their current geometry added -- a modify is exactly
        remove-old-then-add-new), (3) only *then* read back which faces
        border the newly (re)created edges, since it's safe to interleave
        reads and edits on this connection but there's no reason to read
        anything before every edit in the batch is done, (4) sync the
        output polygon layer for every face touched.
        """
        lines_layer = self.config.lines
        if lines_layer is None or not dirty_queue.is_geopackage_backed(lines_layer):
            return

        path, _ = dirty_queue.layer_source_parts(lines_layer)
        changes = dirty_queue.drain_dirty_queue_for_layer(path, "lines")
        changed_fids = changes["added"] + changes["modified"] + changes["removed"]
        if not changed_fids:
            return

        try:
            self.get_polygons_layer()
        except EngineError:
            # map not generated yet -- nothing to sync into; the eventual
            # first recompute_map() builds everything from scratch anyway
            return

        conn = self._topology_connection()

        total_faces = len(topology_db.list_face_ids(conn, TOPOLOGY_NAME))
        if total_faces and len(changed_fids) / total_faces > self.config.incremental_dirty_fraction_fallback:
            # oversized batch (bulk import, big paste) -- a full rebuild is
            # cheaper and safer than many individual topology edits
            self.recompute_map()
            return

        merges: list[tuple[int, int, int]] = []  # (retired_face_a, retired_face_b, merged_face_id)

        for fid in changes["removed"] + changes["modified"]:
            for edge_id in topology_db.edges_for_line(conn, fid):
                before = topology_db.edge_faces(conn, TOPOLOGY_NAME, edge_id)
                merged_face_id = topology_db.remove_edge(conn, TOPOLOGY_NAME, edge_id)
                if merged_face_id is not None and before is not None:
                    face_a, face_b = before
                    if face_a != face_b and face_a != 0 and face_b != 0:
                        merges.append((face_a, face_b, merged_face_id))
            topology_db.clear_edge_source_for_line(conn, fid)

        new_edge_ids: list[int] = []
        for fid in changes["added"] + changes["modified"]:
            feature = lines_layer.getFeature(fid)
            if not feature.isValid():
                continue
            geometry = feature.geometry()
            if geometry is None or geometry.isEmpty():
                continue
            geometry = self._prepare_line_geometry(geometry)
            edge_ids = topology_db.add_linestring(conn, TOPOLOGY_NAME, geometry.asWkt())
            for edge_id in edge_ids:
                topology_db.record_edge_source(conn, edge_id, fid)
            new_edge_ids.extend(edge_ids)

        affected_face_ids: set[int] = set()
        for edge_id in new_edge_ids:
            faces = topology_db.edge_faces(conn, TOPOLOGY_NAME, edge_id)
            if faces is not None:
                affected_face_ids.update(f for f in faces if f != 0)

        forced_units: dict[int, str | None] = {}
        retired_polygon_ids: set[int] = set()
        for face_a, face_b, merged_face_id in merges:
            # resolve the tiebreak *before* unmapping -- it needs to look up
            # face_a/face_b's still-current polygon_uuid mappings, which
            # unmap_face() below is what makes unfindable
            resolved_unit = self._resolve_merge_unit(face_a, face_b)

            for retired_face in (face_a, face_b):
                old_uuid = topology_db.polygon_uuid_for_face(conn, retired_face)
                if old_uuid is not None:
                    old_feature = self._find_polygon_by_uuid(old_uuid)
                    if old_feature is not None:
                        retired_polygon_ids.add(old_feature.id())
                topology_db.unmap_face(conn, retired_face)

            if merged_face_id in affected_face_ids:
                # this merge's result was itself split again later in the
                # same batch -- e.g. a "modify" is remove-old-edge (a merge)
                # then add-new-edge (a split), so the id a merge produced
                # can immediately get split further. The merge's tiebreak
                # value belonged to the *whole* temporarily-merged region,
                # not to whichever smaller piece happens to keep this id
                # after the later split -- let it resolve normally (point-
                # in-polygon) instead of inheriting a now-stale override.
                continue
            forced_units[merged_face_id] = resolved_unit
            affected_face_ids.add(merged_face_id)

        self._sync_output_faces(affected_face_ids, forced_units, retired_polygon_ids)

    def _resolve_merge_unit(self, face_a: int, face_b: int) -> str | None:
        """Deterministic merge-conflict tiebreak: the surviving unit value
        is the one from whichever of the two dissolved faces' output
        polygon had the lower original feature id. Logs a note when the two
        sides actually disagreed (as opposed to one simply being unset)."""
        conn = self._topology_connection()
        candidates = []
        for face_id in (face_a, face_b):
            polygon_uuid = topology_db.polygon_uuid_for_face(conn, face_id)
            if polygon_uuid is None:
                continue
            feature = self._find_polygon_by_uuid(polygon_uuid)
            if feature is None:
                continue
            unit_value = feature[self.config.units_field]
            if unit_value in (None, ""):
                continue
            candidates.append((feature.id(), str(unit_value)))

        if not candidates:
            return None

        candidates.sort(key=lambda c: c[0])
        winner_fid, winner_unit = candidates[0]
        distinct_values = {c[1] for c in candidates}
        if len(distinct_values) > 1:
            QgsMessageLog.logMessage(
                "Mappy: a deleted/redrawn line merged two polygons with differing units "
                f"({', '.join(sorted(distinct_values))}); kept '{winner_unit}' "
                f"(from the lower original feature id, {winner_fid}). Reassign if that's wrong.",
                "Mappy",
                Qgis.MessageLevel.Warning,
            )
        return winner_unit

    def _find_polygon_by_uuid(self, polygon_uuid: str) -> QgsFeature | None:
        polygons_layer = self.get_polygons_layer()
        field_index = polygons_layer.fields().indexFromName(UUID_FIELD)
        if field_index == -1:
            return None
        request = QgsFeatureRequest().setFilterExpression(f"\"{UUID_FIELD}\" = '{polygon_uuid}'")
        for feature in polygons_layer.getFeatures(request):
            return feature
        return None

    def _resolve_unit_for_geometry(self, polygon_geometry: QgsGeometry) -> str | None:
        """Point-in-polygon join for a polygon that doesn't (yet) exist as
        an output feature -- the same bbox+intersects search
        find_indicator_for_polygon does against a feature's geometry, just
        against a bare QgsGeometry instead."""
        points_layer = self.config.points
        if points_layer is None:
            return None
        request = QgsFeatureRequest().setFilterRect(polygon_geometry.boundingBox())
        candidates = [f for f in points_layer.getFeatures(request) if polygon_geometry.intersects(f.geometry())]
        if not candidates:
            return None
        value = candidates[0][self.config.units_field]
        return str(value) if value not in (None, "") else None

    def _sync_output_faces(
        self, face_ids: set[int], forced_units: dict[int, str | None], retired_polygon_ids: set[int] | None = None
    ) -> None:
        """Updates (or inserts) the output polygon layer feature for each
        given topology face id, with its current geometry and a freshly
        resolved (or merge-forced) unit value; deletes retired_polygon_ids
        (the old output features for faces a merge just dissolved -- their
        topology face ids no longer exist, so they can't go through the
        update/insert loop below). A face_id with no current geometry was
        itself superseded again later in the same batch (a rare
        multi-related-edit case); it's skipped rather than guessed at --
        validate_topology()/a manual rebuild is the safety net for that,
        consistent with never silently serving a wrong map."""
        retired_polygon_ids = retired_polygon_ids or set()
        if not face_ids and not retired_polygon_ids:
            return

        conn = self._topology_connection()
        polygons_layer = self.get_polygons_layer()
        uuid_field_index = self._ensure_uuid_field(polygons_layer)
        units_field = self.config.units_field
        unit_field_index = polygons_layer.fields().indexFromName(units_field) if units_field else -1

        was_read_only = polygons_layer.readOnly()
        polygons_layer.setReadOnly(False)
        polygons_layer.startEditing()

        if retired_polygon_ids:
            polygons_layer.deleteFeatures(list(retired_polygon_ids))

        # (face_id, face_uuid) pairs for brand-new faces -- written to the
        # sidecar db only *after* polygons_layer.commitChanges() below, not
        # interleaved with it: committing on the sidecar sqlite3 connection
        # while the output GeoPackage layer has an edit session open on a
        # different connection was observed to corrupt the GeoPackage's
        # on-disk schema (a column silently renamed to one added earlier
        # elsewhere in the same process) -- reproducible, not yet fully
        # root-caused, but reliably avoided by never interleaving the two.
        new_mappings: list[tuple[int, str]] = []

        for face_id in face_ids:
            face_wkt = topology_db.get_face_geometry_wkt(conn, TOPOLOGY_NAME, face_id)
            if not face_wkt:
                continue
            face_geom = QgsGeometry.fromWkt(face_wkt)

            if face_id in forced_units:
                unit_value = forced_units[face_id]
            else:
                unit_value = self._resolve_unit_for_geometry(face_geom)

            existing_uuid = topology_db.polygon_uuid_for_face(conn, face_id)
            existing_feature = self._find_polygon_by_uuid(existing_uuid) if existing_uuid is not None else None

            if existing_feature is not None:
                polygons_layer.changeGeometry(existing_feature.id(), face_geom)
                if unit_field_index != -1 and unit_value is not None:
                    polygons_layer.changeAttributeValue(existing_feature.id(), unit_field_index, unit_value)
                continue

            new_feature = QgsFeature(polygons_layer.fields())
            new_feature.setGeometry(face_geom)
            face_uuid = str(uuid.uuid4())
            new_feature.setAttribute(uuid_field_index, face_uuid)
            if unit_field_index != -1 and unit_value is not None:
                new_feature.setAttribute(unit_field_index, unit_value)
            polygons_layer.addFeature(new_feature)
            new_mappings.append((face_id, face_uuid))

        polygons_layer.commitChanges()
        polygons_layer.setReadOnly(was_read_only)

        for face_id, face_uuid in new_mappings:
            topology_db.map_face_to_polygon(conn, face_id, face_uuid)

    def invalidate(self) -> None:
        """Drops the topology and all bookkeeping; the next recompute_map()
        rebuilds everything from scratch. Also the manual "repair drift"
        action."""
        conn = self._topology_connection()
        topology_db.drop_topology(conn, TOPOLOGY_NAME)
        topology_db.clear_edge_sources(conn)
        topology_db.clear_face_polygons(conn)

    def validate_topology(self) -> TopologyValidationReport:
        conn = self._topology_connection()
        issues = topology_db.validate_topology(conn, TOPOLOGY_NAME)
        return TopologyValidationReport(in_sync=not issues, issues=[str(issue) for issue in issues])
