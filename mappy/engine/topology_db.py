"""Sidecar SpatiaLite ISO topology database.

Mappy's incremental engine keeps a real topology (edges/faces, correctly
split/merged as linework changes) in a separate SpatiaLite ``.sqlite`` file
next to the project's GeoPackage -- not embedded inside the GeoPackage
itself, since GeoPackage's binary geometry encoding and SpatiaLite's native
geometry blob format are incompatible, and mixing GDAL's and libspatialite's
``ST_*`` SQL functions in the same file/process risks a name collision.

Accessed via a raw stdlib ``sqlite3`` connection with ``mod_spatialite``
loaded, not QGIS's own "spatialite" :class:`QgsAbstractDatabaseProviderConnection`.
That was the original design (motivated by ``sqlite3.enable_load_extension()``
being documented as broken on some Windows QGIS builds, QGIS issue #41857),
but empirical testing found QGIS's connection reliably runs the
topology-*creation* functions (``CreateTopology``, ``TopoGeo_AddLineString``)
yet fails every edge-*removal* primitive tried (``ST_RemEdgeNewFace``,
``ST_RemEdgeModFace``, via both ``executeSql()`` and ``execSql()``) with a
spurious "non-existent edge" error against an edge that demonstrably exists
-- reproducible in isolation, independent of topology name or file setup.
The identical sequence via raw ``sqlite3`` + ``mod_spatialite`` works
correctly for every operation, including removal, so that's what this module
uses throughout (a single connection mechanism, rather than mixing two --
mixing connections to the same file was independently found fragile too,
specific to QGIS's connection wrapper). The Windows loadability risk is
accepted as a result -- see `_load_mod_spatialite`'s multi-candidate loading
and clear failure message.

Unlike QGIS's connection, raw sqlite3 has no issue with reading a
topology's own tables (e.g. an edge's left_face/right_face) in between
edit calls on the same connection -- verified empirically (read, then
remove, then add again, all on one connection, no corruption). Callers are
free to interleave reads and edits as needed.
"""

import sqlite3
from pathlib import Path

_MOD_SPATIALITE_CANDIDATES = ("mod_spatialite", "mod_spatialite.so", "mod_spatialite.dll", "mod_spatialite.dylib")


def sidecar_path_for(gpkg_path: str) -> str:
    """The sidecar topology database path for a given GeoPackage path,
    e.g. ``/x/project.gpkg`` -> ``/x/project.mappy-topology.sqlite``."""
    p = Path(gpkg_path)
    return str(p.with_suffix("")) + ".mappy-topology.sqlite"


def _load_mod_spatialite(conn: sqlite3.Connection) -> None:
    if not hasattr(conn, "enable_load_extension"):
        raise RuntimeError(
            "This Python's sqlite3 module was built without loadable-extension "
            "support, so mappy's incremental topology engine (which needs "
            "mod_spatialite) cannot run here. ProcessingMapEngine (the default, "
            "non-incremental engine) is unaffected."
        )
    conn.enable_load_extension(True)
    errors = []
    for name in _MOD_SPATIALITE_CANDIDATES:
        try:
            conn.execute(f"SELECT load_extension('{name}')")
            return
        except sqlite3.OperationalError as e:
            errors.append(f"{name}: {e}")
    raise RuntimeError(
        "Could not load the mod_spatialite SQLite extension needed for mappy's "
        "incremental topology engine (tried: " + ", ".join(_MOD_SPATIALITE_CANDIDATES) + "). "
        "ProcessingMapEngine (the default, non-incremental engine) is unaffected.\n" + "\n".join(errors)
    )


def get_connection(sqlite_path: str) -> sqlite3.Connection:
    """A raw sqlite3 connection to `sqlite_path` with mod_spatialite loaded
    (creates the file first if it doesn't exist yet)."""
    conn = sqlite3.connect(sqlite_path)
    _load_mod_spatialite(conn)
    return conn


def _scalar_rows(cursor) -> list:
    return [row[0] for row in cursor.fetchall()]


def _sql_str(value: str) -> str:
    """A single-quoted SQL string literal, with embedded quotes doubled."""
    return "'" + value.replace("'", "''") + "'"


def _sql_num(value: float) -> str:
    """A numeric SQL literal, rendered as a bare integer when `value` is a
    whole number. CreateTopology's tolerance argument, empirically, only
    behaves correctly given an integer-typed 0 -- a float literal "0.0"
    makes the call fail (returns -1, no topology created, no exception
    raised) even though 0 and 0.0 are the same tolerance value."""
    return str(int(value)) if float(value).is_integer() else str(value)


def _topology_exists(conn: sqlite3.Connection, topo_name: str) -> bool:
    # The "topologies" catalog table itself doesn't exist until the first
    # CreateTopology() call ever made against this database (InitSpatialMetaData
    # alone doesn't create it) -- so "no such table" here just means "no
    # topology has ever been created here yet", not an error.
    try:
        cursor = conn.execute(f"SELECT topology_name FROM topologies WHERE topology_name = {_sql_str(topo_name)}")
    except sqlite3.OperationalError:
        return False
    return bool(_scalar_rows(cursor))


def ensure_topology(conn: sqlite3.Connection, topo_name: str, srid: int = 0, tolerance: float = 0.0) -> None:
    """Idempotently initializes spatial metadata and creates `topo_name`
    if it doesn't already exist. Also creates mappy's own bookkeeping
    tables that SpatiaLite's topology tables have no concept of: which
    source-line feature an edge came from (`mappy_edge_source`), and which
    output-polygon-layer feature (by stable uuid) a face corresponds to
    (`mappy_face_polygon`) -- the same shape of mapping topology-manager
    keeps as its own `__edge_relation` cache on top of PostGIS topology."""
    conn.execute("SELECT InitSpatialMetaData(1)")
    conn.execute("CREATE TABLE IF NOT EXISTS mappy_edge_source (edge_id INTEGER, source_fid INTEGER)")
    conn.execute("CREATE TABLE IF NOT EXISTS mappy_face_polygon (face_id INTEGER UNIQUE, polygon_uuid TEXT UNIQUE)")
    conn.commit()
    if not _topology_exists(conn, topo_name):
        conn.execute(f"SELECT CreateTopology({_sql_str(topo_name)}, {int(srid)}, {_sql_num(tolerance)})")
        conn.commit()


def record_edge_source(conn: sqlite3.Connection, edge_id: int, source_fid: int) -> None:
    conn.execute("INSERT INTO mappy_edge_source (edge_id, source_fid) VALUES (?, ?)", (int(edge_id), int(source_fid)))
    conn.commit()


def clear_edge_sources(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM mappy_edge_source")
    conn.commit()


def clear_edge_source_for_line(conn: sqlite3.Connection, source_fid: int) -> None:
    """Forgets which edges came from `source_fid` -- called once that line
    has been removed, or before re-adding it with new geometry."""
    conn.execute("DELETE FROM mappy_edge_source WHERE source_fid = ?", (int(source_fid),))
    conn.commit()


def edges_for_line(conn: sqlite3.Connection, source_fid: int) -> list[int]:
    """Topology edge ids that were created from the given source-line fid."""
    cursor = conn.execute("SELECT edge_id FROM mappy_edge_source WHERE source_fid = ?", (int(source_fid),))
    return [r[0] for r in cursor.fetchall()]


def edge_faces(conn: sqlite3.Connection, topo_name: str, edge_id: int) -> tuple[int, int] | None:
    """(left_face, right_face) for `edge_id`, or None if it no longer
    exists. Meant to be read *before* removing an edge, to learn which two
    faces a removal is about to merge (ST_RemEdgeNewFace only returns the
    new merged face id, not what it replaced)."""
    cursor = conn.execute(f'SELECT left_face, right_face FROM "{topo_name}_edge" WHERE edge_id = ?', (int(edge_id),))
    row = cursor.fetchone()
    return (row[0], row[1]) if row else None


def map_face_to_polygon(conn: sqlite3.Connection, face_id: int, polygon_uuid: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO mappy_face_polygon (face_id, polygon_uuid) VALUES (?, ?)", (int(face_id), polygon_uuid)
    )
    conn.commit()


def polygon_uuid_for_face(conn: sqlite3.Connection, face_id: int) -> str | None:
    cursor = conn.execute("SELECT polygon_uuid FROM mappy_face_polygon WHERE face_id = ?", (int(face_id),))
    row = cursor.fetchone()
    return row[0] if row else None


def unmap_face(conn: sqlite3.Connection, face_id: int) -> None:
    """Forgets a face's polygon mapping (the face no longer exists, e.g.
    it was one of the two faces a merge just retired)."""
    conn.execute("DELETE FROM mappy_face_polygon WHERE face_id = ?", (int(face_id),))
    conn.commit()


def clear_face_polygons(conn: sqlite3.Connection) -> None:
    conn.execute("DELETE FROM mappy_face_polygon")
    conn.commit()


def list_face_ids(conn: sqlite3.Connection, topo_name: str) -> list[int]:
    """All face ids in the topology except the universal exterior face (0).
    [] (not an error) if the topology doesn't exist (e.g. after invalidate())."""
    try:
        cursor = conn.execute(f'SELECT face_id FROM "{topo_name}_face" WHERE face_id <> 0')
    except sqlite3.OperationalError:
        return []
    return [r[0] for r in cursor.fetchall()]


def drop_topology(conn: sqlite3.Connection, topo_name: str) -> None:
    """Removes `topo_name` and all its primitives, if present."""
    if _topology_exists(conn, topo_name):
        conn.execute(f"SELECT DropTopology({_sql_str(topo_name)})")
        conn.commit()


def add_linestring(conn: sqlite3.Connection, topo_name: str, wkt: str) -> list[int]:
    """Adds `wkt` (a LINESTRING/MULTILINESTRING) to the topology, splitting
    existing edges/faces as needed. Returns the created/matched edge id(s).
    Idempotent: re-adding identical geometry returns the same edge id(s)
    rather than erroring or duplicating.

    When a single call ends up creating more than one edge (the new line
    crosses enough existing edges to be split immediately on insertion),
    SpatiaLite returns them as one row holding a single comma-separated
    string (e.g. "10, 12, 14"), not one row per edge id as a simple id
    might suggest -- confirmed empirically, undocumented as far as we
    could find. Each returned value is split on commas unconditionally,
    which also handles the common single-id-per-row case fine (splitting
    "4" on "," is just ["4"])."""
    cursor = conn.execute(f"SELECT TopoGeo_AddLineString({_sql_str(topo_name)}, GeomFromText({_sql_str(wkt)}))")
    edge_ids = [int(part.strip()) for v in _scalar_rows(cursor) for part in str(v).split(",") if part.strip()]
    conn.commit()
    return edge_ids


def remove_edge(conn: sqlite3.Connection, topo_name: str, edge_id: int) -> int | None:
    """Removes `edge_id`. If it separated two faces, they are merged into
    one and the new face id is returned; if it was a dangle (bordering the
    universal face only) or the edge no longer exists (e.g. a related edit
    already removed it earlier in the same batch), returns None."""
    try:
        cursor = conn.execute(f"SELECT ST_RemEdgeNewFace({_sql_str(topo_name)}, {int(edge_id)})")
        rows = _scalar_rows(cursor)
    except sqlite3.OperationalError:
        return None
    conn.commit()
    if not rows:
        return None
    face_id = int(rows[0])
    return face_id if face_id != 0 else None


def get_face_geometry_wkt(conn: sqlite3.Connection, topo_name: str, face_id: int) -> str | None:
    cursor = conn.execute(f"SELECT ST_AsText(ST_GetFaceGeometry({_sql_str(topo_name)}, {int(face_id)}))")
    rows = _scalar_rows(cursor)
    return rows[0] if rows else None


def validate_topology(conn: sqlite3.Connection, topo_name: str) -> list:
    """Runs SpatiaLite's own consistency check (a scalar function, despite
    the name). An empty list means the topology is fully consistent."""
    cursor = conn.execute(f"SELECT ST_ValidateTopoGeo({_sql_str(topo_name)})")
    return [v for v in _scalar_rows(cursor) if v is not None]
