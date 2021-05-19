from qgis.PyQt.QtCore import NULL
from qgis.core import QgsCategorizedSymbolRenderer, QgsSymbol, QgsRendererCategory


def resetCategoriesIfNeeded(layer, units_field, unassigned=True):
    prev_rend = layer.renderer()

    if not isinstance(prev_rend, QgsCategorizedSymbolRenderer):
        renderer = QgsCategorizedSymbolRenderer(units_field)
        layer.setRenderer(renderer)
    else:
        renderer = prev_rend

    prev_cats = renderer.categories()
    id = layer.fields().indexFromName(units_field)
    uniques = list(layer.uniqueValues(id))
    uniques_clean = []

    for u in uniques:
        if u not in [None, NULL]:
            uniques_clean.append(u)

    values = sorted(uniques_clean)

    if unassigned:
        if None in uniques or NULL in uniques:
            values.append("")

    categories = []

    for current, value in enumerate(values):

        already_in = False
        for prev in prev_cats:
            if prev.value() == value:
                already_in = True
                continue

        if not already_in:
            if value =="":
                name = "Unassigned"
            else:
                name = str(value)
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            category = QgsRendererCategory(value, symbol, name)
            categories.append(category)

    for cat in categories:
        renderer.addCategory(cat)

    # layer.setRenderer(renderer)
    layer.rendererChanged.emit()
    layer.dataSourceChanged.emit()

    layer.triggerRepaint()