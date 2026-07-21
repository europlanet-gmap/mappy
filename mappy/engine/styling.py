from qgis.core import (
    QgsLineSymbol,
    QgsPalLayerSettings,
    QgsVectorLayerSimpleLabeling,
    QgsWkbTypes,
)


def enable_default_labels(layer, field_name) -> None:
    """Turn on simple labeling using field_name as the default for a freshly
    created/loaded layer.

    Only applied when the layer has no labeling configuration yet (mirrors
    the "only set up a fresh renderer if none exists" guard in
    resetCategoriesIfNeeded), so a user's later choice to disable or
    reconfigure labels isn't clobbered the next time the layer is reloaded.
    """
    if layer.labeling() is not None:
        return

    settings = QgsPalLayerSettings()
    settings.fieldName = field_name

    if layer.geometryType() == QgsWkbTypes.GeometryType.Polygon:
        settings.placement = QgsPalLayerSettings.Placement.Horizontal
        # Placement tab's "Only show label which completely fits within the
        # polygon boundary" -- forces labels inside the polygon rather than
        # letting them spill over its edges
        settings.fitInPolygonOnly = True
    else:
        settings.placement = QgsPalLayerSettings.Placement.OverPoint

    layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
    layer.setLabelsEnabled(True)
    layer.triggerRepaint()


def style_simple_black_line(layer) -> None:
    """Give a freshly created line layer a plain solid black line style."""
    symbol = QgsLineSymbol.createSimple({"color": "black", "style": "solid"})
    layer.renderer().setSymbol(symbol)
    layer.triggerRepaint()
