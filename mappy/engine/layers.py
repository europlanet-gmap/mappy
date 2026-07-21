import os.path

from qgis.core import (
    QgsFeatureRequest,
    QgsLayerTreeLayer,
    QgsProject,
    QgsVectorFileWriter,
    QgsVectorLayer,
)


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


def drop_duplicate_points_per_polygon(points_layer, polygons_layer) -> set:
    """When more than one point falls within the same polygon, only the
    first one (lowest feature id) was actually used by the join that assigns
    attributes to that polygon; delete the rest from points_layer so leftover
    duplicate indicator points don't linger.
    """
    to_delete = set()
    for poly_feature in polygons_layer.getFeatures():
        poly_geom = poly_feature.geometry()
        request = QgsFeatureRequest().setFilterRect(poly_geom.boundingBox())
        candidates = [f for f in points_layer.getFeatures(request) if poly_geom.intersects(f.geometry())]
        if len(candidates) > 1:
            candidates.sort(key=lambda f: f.id())
            to_delete.update(f.id() for f in candidates[1:])

    if to_delete:
        points_layer.dataProvider().deleteFeatures(list(to_delete))
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
