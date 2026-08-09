from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsCategorizedSymbolRenderer,
    QgsField,
    QgsRendererCategory,
    QgsSymbol,
)


def resetCategoriesIfNeeded(layer, units_field, color_table=None) -> None:
    """color_table is an optional {str(value): "#rrggbb"} mapping (see
    get_or_create_color_table) used to give a category its persisted color
    instead of QgsSymbol.defaultSymbol's randomly-generated one, so a unit's
    color stays stable across reloads rather than being re-rolled from
    scratch every time the renderer is rebuilt.
    """

    prev_rend = layer.renderer()

    if not isinstance(prev_rend, QgsCategorizedSymbolRenderer):
        renderer = QgsCategorizedSymbolRenderer(units_field)
        layer.setRenderer(renderer)
    else:
        renderer = prev_rend

    prev_cats = renderer.categories()

    id = layer.fields().indexFromName(units_field)
    uniques = list(layer.uniqueValues(id))
    # "" is as unassigned as a real NULL -- e.g. clearing a text field via
    # QGIS's attribute table leaves "" behind, not NULL -- and the rest of
    # this module (get_or_create_color_table, write_colors_to_points)
    # already treats the two as equivalent
    has_unassigned = any(u is None or u == "" for u in uniques)
    uniques = [u for u in uniques if u is not None and u != ""]

    values = sorted(uniques)
    if has_unassigned:
        # catch-all category so polygons with no unit value are still drawn
        # (QgsCategorizedSymbolRenderer skips features that match no category)
        values.append(None)
    categories = []

    # delete "old/unused categories"
    for cat in prev_cats:
        cat: QgsRendererCategory
        if cat.value() not in values:
            cat_id = renderer.categoryIndexForValue(cat.value())
            renderer.deleteCategory(cat_id)

    from qgis.PyQt.QtGui import QColor

    for value in values:
        # query the live renderer, not prev_cats -- categories may already
        # have been deleted above, which shifts every index after them, and
        # updateCategorySymbol needs an index into the *current* list
        existing_index = renderer.categoryIndexForValue(value)

        if existing_index != -1:
            # already styled -- if color_table disagrees with what's
            # currently shown, treat color_table as the up-to-date truth
            # (e.g. it was just updated to reflect a manual recolor made on
            # the *other* layer) and bring this category's color in line.
            #
            # Careful: chaining renderer.categories()[i].symbol()... in one
            # expression segfaults -- the intermediate QgsRendererCategory/
            # QgsSymbol SIP wrappers get garbage-collected before the C++
            # side is done with them. Keep every intermediate in a named
            # variable so it stays alive for the whole block, and never
            # touch a symbol object again after handing it to
            # updateCategorySymbol (which takes ownership of it).
            if value is not None and color_table:
                wanted = color_table.get(str(value))
                existing_categories = renderer.categories()
                existing_category = existing_categories[existing_index]
                existing_symbol = existing_category.symbol()
                existing_color_name = existing_symbol.color().name()
                if wanted and QColor(wanted).name() != existing_color_name:
                    fresh_symbol = QgsSymbol.defaultSymbol(layer.geometryType())
                    fresh_symbol.setColor(QColor(wanted))
                    renderer.updateCategorySymbol(existing_index, fresh_symbol)
            continue

        symbol = QgsSymbol.defaultSymbol(layer.geometryType())
        from qgis.PyQt.QtCore import Qt

        if (slayer := symbol.symbolLayer(0)) and hasattr(slayer, "setStrokeStyle"):
            # only fill symbol layers (polygons) have a separate stroke to
            # suppress -- line layers have no such method (the line *is*
            # the stroke), and this same helper is also used for line
            # layers (see MapAutoStyleProcessingAlgorithm, which accepts
            # both polygon and line input)
            slayer.setStrokeStyle(Qt.PenStyle.NoPen)

        if value is None:
            symbol.setColor(QColor(200, 200, 200))
            if slayer and hasattr(slayer, "setBrushStyle"):
                slayer.setBrushStyle(Qt.BrushStyle.DiagCrossPattern)
            label = "Unassigned"
        else:
            label = str(value)
            persisted_color = color_table.get(label) if color_table else None
            if persisted_color:
                symbol.setColor(QColor(persisted_color))

        category = QgsRendererCategory(value, symbol, label)
        categories.append(category)

    for cat in categories:
        renderer.addCategory(cat)

    # layer.setRenderer(renderer)
    layer.rendererChanged.emit()
    layer.dataSourceChanged.emit()

    layer.triggerRepaint()


# hue step (in degrees) between successive auto-generated colors -- the
# golden angle gives a sequence of hues that stays well spread out around
# the color wheel no matter how many are generated, without needing to know
# the total count of units up front
_GOLDEN_ANGLE = 137.508


def sequential_color(index):
    from qgis.PyQt.QtGui import QColor

    hue = (index * _GOLDEN_ANGLE) % 360
    return QColor.fromHsvF(hue / 360, 0.55, 0.85)


def get_or_create_color_table(points_layer, units_field, color_field="color") -> dict[str, str]:
    """Returns a {str(unit_value): "#rrggbb"} color table, sourced from and
    kept in sync with a `color_field` attribute stored directly on
    points_layer -- so a unit's color is a durable property of the data
    itself rather than something re-derived (and re-randomized) from a
    layer's renderer state every time it's rebuilt.

    Creates color_field if it doesn't exist yet. Any unit missing a color
    (new, or pre-existing data from before this field existed) gets one
    assigned and written back to every point sharing that unit, so the
    column stays fully populated. Colors already stored are never changed.
    """
    fields = points_layer.fields()
    if fields.indexFromName(color_field) == -1:
        points_layer.dataProvider().addAttributes([QgsField(color_field, QVariant.String)])
        points_layer.updateFields()

    unit_index = points_layer.fields().indexFromName(units_field)
    color_index = points_layer.fields().indexFromName(color_field)

    color_table = {}
    for f in points_layer.getFeatures():
        unit = f[unit_index]
        if unit in (None, ""):
            continue
        color = f[color_index]
        unit = str(unit)
        if color not in (None, "") and unit not in color_table:
            color_table[unit] = color

    missing_units = sorted(
        {
            str(f[unit_index])
            for f in points_layer.getFeatures()
            if f[unit_index] not in (None, "") and str(f[unit_index]) not in color_table
        }
    )

    start = len(color_table)
    for i, unit in enumerate(missing_units):
        color_table[unit] = sequential_color(start + i).name()

    write_colors_to_points(points_layer, units_field, color_field, color_table)

    return color_table


def write_colors_to_points(points_layer, units_field, color_field, color_table) -> None:
    """Backfills/corrects color_field on every point so it matches
    color_table, leaving points whose unit already has the right color
    untouched."""
    unit_index = points_layer.fields().indexFromName(units_field)
    color_index = points_layer.fields().indexFromName(color_field)

    was_editable = points_layer.isEditable()
    if not was_editable:
        points_layer.startEditing()

    for f in points_layer.getFeatures():
        unit = f[unit_index]
        if unit in (None, ""):
            continue
        wanted = color_table.get(str(unit))
        if wanted and f[color_index] != wanted:
            points_layer.changeAttributeValue(f.id(), color_index, wanted)

    points_layer.commitChanges()
    if was_editable:
        points_layer.startEditing()


def _current_category_overrides(layer, baseline) -> dict[str, str]:
    """Returns {str(value): current_color} for every existing category on
    layer's categorized renderer whose color differs from baseline -- i.e.
    a manual recolor made directly in QGIS's Symbology panel since the last
    sync. Empty if the layer has no categorized renderer yet."""
    renderer = layer.renderer()
    if not isinstance(renderer, QgsCategorizedSymbolRenderer):
        return {}

    overrides = {}
    for cat in renderer.categories():
        value = cat.value()
        if value is None:
            continue
        value = str(value)
        baseline_color = baseline.get(value)
        # keep every intermediate named -- chaining straight through to
        # .color().name() has been observed to segfault (see
        # resetCategoriesIfNeeded's comment on this same SIP pitfall)
        symbol = cat.symbol()
        color = symbol.color()
        current_color = color.name()
        if baseline_color and current_color.lower() != baseline_color.lower():
            overrides[value] = current_color
    return overrides


def sync_unit_colors(
    points_layer, polygons_layer, units_field, color_field="color", explicit_overrides=None
) -> dict[str, str]:
    """Reconciles unit colors across points_layer, polygons_layer and the
    persisted color_field, then applies the result to both layers.

    A color changed by hand in QGIS's Symbology panel, on either layer, is
    detected against the last-synced value and propagated: into the
    persisted points data, and onto the other layer's matching category --
    instead of being silently overwritten or left to drift out of sync. If
    both layers were recolored differently for the same unit since the last
    sync, the polygon layer's choice wins, since it's the primary map output.

    explicit_overrides ({unit: color}) is for a color just chosen through
    our own UI (e.g. AssignUnitDialog) rather than detected from a layer's
    renderer, and always wins over both the baseline and any renderer-
    detected override. This matters because the polygon layer's renderer
    hasn't been told about such a change yet at the point this function is
    called -- comparing it against a baseline that already reflects the new
    color (if it had been written to points_layer beforehand) would make
    the *stale* polygon color look like an intentional manual override and
    win, silently reverting the very change being applied.
    """
    baseline = get_or_create_color_table(points_layer, units_field, color_field)

    points_overrides = _current_category_overrides(points_layer, baseline)
    polygon_overrides = _current_category_overrides(polygons_layer, baseline)

    final_table = dict(baseline)
    final_table.update(points_overrides)
    final_table.update(polygon_overrides)
    if explicit_overrides:
        final_table.update(explicit_overrides)

    if final_table != baseline:
        write_colors_to_points(points_layer, units_field, color_field, final_table)

    resetCategoriesIfNeeded(polygons_layer, units_field, color_table=final_table)
    resetCategoriesIfNeeded(points_layer, units_field, color_table=final_table)

    return final_table
