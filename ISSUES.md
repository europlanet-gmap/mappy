# Known issues

Deferred/tracked findings that aren't fixed yet, with enough detail to pick
back up later. Not a general bug tracker -- just things found during review
that were consciously left out of the fix at the time.

## Incremental engine drops color/category/label sync on line edits

**Where:** `IncrementalMapEngine._process_pending_line_changes()` and the
`_sync_output_faces()` helper it calls (`mappy/engine/incremental_engine.py`).

**What's wrong:** When a line edit causes a topology face split or merge,
`_sync_output_faces()` creates/updates the affected output polygon
feature(s) directly (`changeAttributeValue`/`addFeature`) but never calls
`resetCategoriesIfNeeded`, `sync_unit_colors`, or `enable_default_labels`
afterward.

Every other path that can introduce a new unit value onto the polygon layer
does call into `engine/colors.py` to keep the categorized renderer (and
labels) in sync:

- `ProcessingMapEngine._load_layer_if_not_loaded()` -- after a full
  `recompute_map()` -- calls `sync_unit_colors()` and
  `enable_default_labels()`.
- `IncrementalMapEngine._process_pending_point_changes()` -- routes through
  `_propagate_point_unit_to_polygon()`, which calls `sync_unit_colors()` and
  `enable_default_labels()`.
- `_process_pending_line_changes()` / `_sync_output_faces()` -- calls
  neither. Confirmed by grep: there is no mention of color/categor(y)/style
  anywhere in `incremental_engine.py`.

**User-visible impact:** if a line edit (split or merge) produces a polygon
whose resolved unit value (`_resolve_merge_unit()` /
`_resolve_unit_for_geometry()`) has no existing category yet on the
polygon layer's renderer, `QgsCategorizedSymbolRenderer` silently skips
drawing any feature that matches no category. The polygon exists in the
data (attribute is set correctly) but is invisible on the map, with no
error -- it reads as data loss rather than a styling gap, until the user
happens to run a full "Recompute map" (which rebuilds the renderer from
scratch via `_load_layer_if_not_loaded`).

**Why deferred:** fixing this needs a real incremental-engine test fixture
(topology + dirty queue + a line edit that produces a genuinely new unit
value) to pin down, which is more involved than the two `engine/colors.py`
fixes done alongside this (see git history around 2026-08-09). Left out on
purpose rather than fixed blind.

**Suggested direction when picked up:** have `_sync_output_faces()` call
`sync_unit_colors(config.points, polygons_layer, units_field)` (and
`enable_default_labels`) once at the end, mirroring
`_propagate_point_unit_to_polygon()`, rather than per-feature -- it already
batches all the affected faces into one edit session, so the resync should
happen once after `commitChanges()`, not once per face.
