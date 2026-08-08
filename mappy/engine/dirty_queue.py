"""Trigger-maintained "what changed" queue, persisted inside a GeoPackage.

`mappy_dirty_line` is a plain SQLite table living alongside a GeoPackage's
own feature tables. `AFTER INSERT/UPDATE/DELETE` triggers on the lines/points
feature tables append a row to it on every write -- since triggers are plain
SQLite schema objects, they fire for *any* writer touching those tables
(QGIS/GDAL's own edit-buffer commits included), not just writes that happen
to go through code that remembered to call some notify function. This makes
dirty-tracking robust by construction: a GUI-side signal-wiring bug can only
delay draining the queue, it can never lose a change.

Uses the stdlib ``sqlite3`` module directly (not QGIS's own connection
machinery) -- this DDL is plain table/trigger bookkeeping with no geometry
parsing and no SpatiaLite functions involved, so there's nothing here that
needs a loadable extension.
"""

import sqlite3

DIRTY_TABLE = "mappy_dirty_line"

_CHANGE_TYPES = {"INSERT": "insert", "UPDATE": "update", "DELETE": "delete"}
_BUCKET_BY_CHANGE_TYPE = {"insert": "added", "update": "modified", "delete": "removed"}


def layer_source_parts(layer) -> tuple[str, str | None]:
    """(gpkg file path, backing SQL table name) for a GeoPackage-backed
    QgsVectorLayer, e.g. "/x/project.gpkg|layername=source_contacts" ->
    ("/x/project.gpkg", "source_contacts"). table name is None if the
    layer's data source URI carries no layername (not GeoPackage-backed)."""
    uri = layer.dataProvider().dataSourceUri()
    path, _, rest = uri.partition("|")
    table = None
    for part in rest.split("|"):
        if part.startswith("layername="):
            table = part[len("layername=") :]
    return path, table


def is_geopackage_backed(layer) -> bool:
    if layer is None or layer.providerType() != "ogr":
        return False
    path, table = layer_source_parts(layer)
    return path.lower().endswith(".gpkg") and table is not None


def install_dirty_queue_table(gpkg_path: str) -> None:
    """Creates the mappy_dirty_line bookkeeping table if not already present."""
    conn = sqlite3.connect(gpkg_path)
    try:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {DIRTY_TABLE} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_layer TEXT NOT NULL,
                fid INTEGER NOT NULL,
                change_type TEXT NOT NULL,
                changed_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def install_triggers_for_layer(gpkg_path: str, table_name: str, source_layer: str) -> None:
    """Attaches AFTER INSERT/UPDATE/DELETE triggers on `table_name` (the
    GeoPackage feature table backing a lines/points layer) that append a
    row to mappy_dirty_line for every write. Idempotent: existing triggers
    of the same name are replaced.

    Assumes the GeoPackage feature-id primary key column is named "fid",
    which is the OGR/GDAL GeoPackage driver's default and what QGIS itself
    always creates via write_layer_to_gpkg (see mappy/engine/layers.py).
    """
    install_dirty_queue_table(gpkg_path)

    conn = sqlite3.connect(gpkg_path)
    try:
        for event, change_type in _CHANGE_TYPES.items():
            fid_ref = "OLD.fid" if change_type == "delete" else "NEW.fid"
            trigger_name = f"mappy_dirty_{table_name}_{change_type}"
            conn.execute(f'DROP TRIGGER IF EXISTS "{trigger_name}"')
            conn.execute(
                f"""
                CREATE TRIGGER "{trigger_name}"
                AFTER {event} ON "{table_name}"
                BEGIN
                    INSERT INTO {DIRTY_TABLE} (source_layer, fid, change_type)
                    VALUES ('{source_layer}', {fid_ref}, '{change_type}');
                END
                """
            )
        conn.commit()
    finally:
        conn.close()


def ensure_dirty_queue_for_layer(layer, source_layer: str) -> None:
    """Convenience wrapper: installs the dirty-queue table and triggers for
    a GeoPackage-backed QgsVectorLayer directly. Raises ValueError if the
    layer isn't GeoPackage-backed."""
    if not is_geopackage_backed(layer):
        raise ValueError(f"layer {layer!r} is not a GeoPackage-backed layer; cannot install dirty-tracking triggers")
    path, table = layer_source_parts(layer)
    assert table is not None  # guaranteed by the is_geopackage_backed() check above
    install_triggers_for_layer(path, table, source_layer)


def drain_dirty_queue(gpkg_path: str) -> dict[str, dict[str, list[int]]]:
    """Reads and clears all pending dirty-line rows, grouped by
    source_layer into {"added": [...], "modified": [...], "removed": [...]}
    fid lists."""
    conn = sqlite3.connect(gpkg_path)
    try:
        rows = conn.execute(f"SELECT source_layer, fid, change_type FROM {DIRTY_TABLE} ORDER BY id").fetchall()
        conn.execute(f"DELETE FROM {DIRTY_TABLE}")
        conn.commit()
    finally:
        conn.close()

    result: dict[str, dict[str, list[int]]] = {}
    for source_layer, fid, change_type in rows:
        bucket = result.setdefault(source_layer, {"added": [], "modified": [], "removed": []})
        bucket[_BUCKET_BY_CHANGE_TYPE[change_type]].append(fid)
    return result


def drain_dirty_queue_for_layer(gpkg_path: str, source_layer: str) -> dict[str, list[int]]:
    """Like drain_dirty_queue(), but only reads+clears rows for one
    `source_layer` ("lines" or "points"), leaving rows for any other role
    untouched. Needed once more than one role can be drained independently
    (e.g. the points-path runs before the lines-path is implemented): a
    blanket drain would silently discard dirty rows nothing has acted on
    yet, defeating the point of a durable, self-healing queue."""
    conn = sqlite3.connect(gpkg_path)
    try:
        rows = conn.execute(
            f"SELECT fid, change_type FROM {DIRTY_TABLE} WHERE source_layer = ? ORDER BY id", (source_layer,)
        ).fetchall()
        conn.execute(f"DELETE FROM {DIRTY_TABLE} WHERE source_layer = ?", (source_layer,))
        conn.commit()
    except sqlite3.OperationalError:
        return {"added": [], "modified": [], "removed": []}
    finally:
        conn.close()

    result = {"added": [], "modified": [], "removed": []}
    for fid, change_type in rows:
        result[_BUCKET_BY_CHANGE_TYPE[change_type]].append(fid)
    return result


def pending_count(gpkg_path: str) -> int:
    """0 if the dirty-queue table hasn't been installed yet (nothing to be
    pending), rather than raising."""
    conn = sqlite3.connect(gpkg_path)
    try:
        return conn.execute(f"SELECT count(*) FROM {DIRTY_TABLE}").fetchone()[0]
    except sqlite3.OperationalError:
        return 0
    finally:
        conn.close()
