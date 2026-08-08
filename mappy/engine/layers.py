import os.path
from collections.abc import Callable

from qgis.core import (
    QgsFeatureRequest,
    QgsLayerTreeLayer,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)

from .interface import EngineError, RecomputeCancelled

# A "duplicate" count is only auto-refused outright (rather than just asking
# for confirmation) when it's both a large absolute number and a large share
# of the whole points layer -- that combination is the actual signature of
# the wrong lines layer being selected (malformed polygons make unrelated
# points look like they collide), while an occasional, plausible, small-
# scale duplicate stays a simple confirm.
DUPLICATE_POINTS_GUARD_MIN_COUNT = 5
DUPLICATE_POINTS_GUARD_FRACTION = 0.3


def find_layer(gpkg, layer_name) -> QgsVectorLayer | None:
    gpkg = os.path.abspath(gpkg)

    gpkg += f"|layername={layer_name}"
    layers = QgsProject.instance().mapLayers()

    for layer in layers.values():
        luri = layer.dataProvider().dataSourceUri()

        r = os.path.realpath
        if r(luri) == r(gpkg):
            return layer

    return None


def insert_layer_after(layer, after_layer_names) -> None:
    """Insert `layer` into the layer tree root, directly after whichever of
    `after_layer_names` currently sits lowest (last) among the root's direct
    children. Falls back to the default top-of-tree position if none of those
    names are present there.
    """
    root = QgsProject.instance().layerTreeRoot()

    anchor_index = None
    for i, child in enumerate(root.children()):
        if isinstance(child, QgsLayerTreeLayer) and child.name() in after_layer_names:
            anchor_index = i

    if anchor_index is None:
        root.insertLayer(0, layer)
    else:
        root.insertLayer(anchor_index + 1, layer)


def add_layer_from_geopackage(gpkgfile, layer_name, categories_field=None, insert_after=None) -> QgsVectorLayer:
    gpkgfile += f"|layername={layer_name}"
    layer = QgsVectorLayer(gpkgfile)
    layer.setName(layer_name)

    if insert_after:
        QgsProject.instance().addMapLayer(layer, False)
        insert_layer_after(layer, insert_after)
    else:
        QgsProject.instance().addMapLayer(layer)

    return layer


def drop_duplicate_points_per_polygon(points_layer, polygons_layer, confirm: Callable[[str], bool] | None = None) -> set:
    """When more than one point falls within the same polygon, only the
    first one (lowest feature id) was actually used by the join that assigns
    attributes to that polygon; delete the rest from points_layer so leftover
    duplicate indicator points don't linger.

    Two safeguards against deleting real data through a misconfigured
    recompute (e.g. the wrong lines layer selected, producing polygons that
    don't correspond to points_layer's actual geography):
    - refuses outright (EngineError, nothing deleted) if the count is both
      large and a large share of points_layer -- see DUPLICATE_POINTS_GUARD_*
      above.
    - otherwise, if `confirm` is given, it's called with a ready-to-display
      message and must return True before anything is deleted;
      RecomputeCancelled is raised if it returns False. `confirm=None`
      (direct/test/script use, not through the Mappy GUI) skips asking and
      proceeds, matching this function's previous unconditional behavior.

    Deletion goes through the edit buffer (startEditing/commitChanges), not
    a direct provider write, so a real commit failure is caught and raised
    instead of silently doing nothing -- but only commits if this call
    itself opened the edit session; if points_layer was already mid-edit
    when called, the deletion is left staged for whichever code owns that
    session to commit or discard, since force-committing here would also
    finalize unrelated pending edits this function doesn't know about.
    """
    to_delete = set()
    for poly_feature in polygons_layer.getFeatures():
        poly_geom = poly_feature.geometry()
        request = QgsFeatureRequest().setFilterRect(poly_geom.boundingBox())
        candidates = [f for f in points_layer.getFeatures(request) if poly_geom.intersects(f.geometry())]
        if len(candidates) > 1:
            candidates.sort(key=lambda f: f.id())
            to_delete.update(f.id() for f in candidates[1:])

    if not to_delete:
        return to_delete

    total = points_layer.featureCount()
    fraction = len(to_delete) / total if total else 0.0
    if len(to_delete) >= DUPLICATE_POINTS_GUARD_MIN_COUNT and fraction > DUPLICATE_POINTS_GUARD_FRACTION:
        raise EngineError(
            f"Recompute would delete {len(to_delete)} of {total} points in "
            f"'{points_layer.name()}' ({fraction:.0%}) as per-polygon duplicates -- "
            "this usually means the wrong lines layer is selected, producing "
            "polygons that don't match this points layer's real geography. "
            "Nothing was changed; check the lines/points layer selection "
            "before recomputing again."
        )

    if confirm is not None:
        message = (
            f"Recompute will permanently delete {len(to_delete)} point(s) from "
            f"'{points_layer.name()}' that fall inside the same polygon as another "
            "point and are treated as duplicates. This cannot be undone.\n\n"
            "Continue?"
        )
        if not confirm(message):
            raise RecomputeCancelled("Recompute cancelled: user declined to delete duplicate indicator points.")

    was_editable = points_layer.isEditable()
    if not was_editable:
        points_layer.startEditing()

    points_layer.deleteFeatures(list(to_delete))

    if not was_editable:
        if not points_layer.commitChanges():
            errors = "; ".join(points_layer.commitErrors())
            raise EngineError(f"Failed to delete duplicate indicator points: {errors}")
        points_layer.dataProvider().reloadData()

    points_layer.triggerRepaint()

    return to_delete


def write_layer_to_gpkg(layer, gpkgfile, layername):
    options = QgsVectorFileWriter.SaveVectorOptions()
    from pathlib import Path

    if Path(gpkgfile).exists():
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    else:
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile

    # to get rid of spaces in the layer name
    options.layerName = layername
    context = QgsProject.instance().transformContext()

    return QgsVectorFileWriter.writeAsVectorFormatV3(layer, gpkgfile, context, options)
