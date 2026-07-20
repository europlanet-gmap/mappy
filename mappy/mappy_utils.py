from qgis.PyQt.QtCore import QFile, QTextStream
from qgis.PyQt.QtWidgets import QLineEdit, QCheckBox
from qgis.core import (
    QgsFeatureRequest,
    QgsVectorLayer,
    QgsMapLayer,
    QgsApplication,
    QgsLayerTreeLayer,
)
from qgis.core import (
    QgsVectorFileWriter,
    QgsProject,
    QgsCategorizedSymbolRenderer,
    QgsSymbol,
    QgsRendererCategory,
)
from qgis.gui import QgsFileWidget
from qgis.gui import QgsFieldComboBox, QgsDoubleSpinBox, QgsMapLayerComboBox

parameters_widgets = [
    QgsMapLayerComboBox,
    QgsFieldComboBox,
    QgsDoubleSpinBox,
    QLineEdit,
    QCheckBox,
    QgsFileWidget,
]


def hasAlgo(name):
    reg = QgsApplication.processingRegistry()
    found = reg.algorithmById(name)
    if found:
        return True
    else:
        return False


def matchAlgo(name):
    if hasAlgo(name):
        return name
    else:
        newname = "qgis:" + name.split(":")[1]
        if hasAlgo(newname):
            return newname
        else:
            raise NameError(
                f"Cannot match algorithm with name {name}. This is possibly due to using this plugin on an older version of QGIS."
            )


def readWidgetContent(widget):
    if isinstance(widget, QgsMapLayerComboBox):
        return widget.currentLayer()

    elif isinstance(widget, QgsFieldComboBox):
        return str(widget.currentField())

    elif isinstance(widget, QgsDoubleSpinBox):
        return widget.value()

    elif isinstance(widget, QLineEdit):
        return widget.text()

    elif isinstance(widget, QCheckBox):
        return widget.isChecked()

    elif isinstance(widget, QgsFileWidget):
        return widget.filePath()

    else:
        return None


def restoreWidgetContent(widget, value):
    if isinstance(widget, QgsMapLayerComboBox):
        if not isinstance(value, QgsMapLayer):
            raise TypeError(
                f"{type(value)} is a wrong type for widget QgsMapLayerComboBox"
            )
        widget.setLayer(value)

    elif isinstance(widget, QgsFieldComboBox):
        exists = widget.findText(str(value))
        if exists == -1:
            raise ValueError(
                f"You are trying to set the widget {widget.objectName()} to value {value}. but combo box does not contain this value"
            )

        widget.setField(str(value))

    elif isinstance(widget, QgsDoubleSpinBox):
        widget.setValue(float(value))

    elif isinstance(widget, QLineEdit):
        widget.setText(str(value))

    elif isinstance(widget, QCheckBox):
        widget.setChecked(bool(value))

    elif isinstance(widget, QgsFileWidget):
        widget.setFilePath(str(value))

    else:
        raise NotImplementedError("not implemented for this widget")


def getChangeSignal(widget):
    if isinstance(widget, QgsMapLayerComboBox):
        return widget.layerChanged

    elif isinstance(widget, QgsFieldComboBox):
        return widget.fieldChanged

    elif isinstance(widget, QgsDoubleSpinBox):
        return widget.valueChanged

    elif isinstance(widget, QLineEdit):
        return widget.textChanged

    elif isinstance(widget, QCheckBox):
        return widget.stateChanged

    elif isinstance(widget, QgsFileWidget):
        return widget.fileChanged

    else:
        return None


def serialize_value_for_settings(value):
    if type(value) in [QgsVectorLayer]:
        return value.id()
    else:
        return str(value)


def collect_parameters(qt_obj):  # -> dict[Any, Any]:
    pars = {}
    for name in qt_obj.__dict__:
        val = readWidgetContent(getattr(qt_obj, name))
        if val is not None:
            pars[name] = val

    return pars


def insert_layer_after(layer, after_layer_names):
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


def add_layer_from_geopackage(
    gpkgfile, layer_name, categories_field=None, insert_after=None
):
    gpkgfile += f"|layername={layer_name}"
    l = QgsVectorLayer(gpkgfile)
    l.setName(layer_name)

    if insert_after:
        QgsProject.instance().addMapLayer(l, False)
        insert_layer_after(l, insert_after)
    else:
        QgsProject.instance().addMapLayer(l)

    return l


def drop_duplicate_points_per_polygon(points_layer, polygons_layer):
    """When more than one point falls within the same polygon, only the
    first one (lowest feature id) was actually used by the join that assigns
    attributes to that polygon; delete the rest from points_layer so leftover
    duplicate indicator points don't linger.
    """
    to_delete = set()
    for poly_feature in polygons_layer.getFeatures():
        poly_geom = poly_feature.geometry()
        request = QgsFeatureRequest().setFilterRect(poly_geom.boundingBox())
        candidates = [
            f
            for f in points_layer.getFeatures(request)
            if poly_geom.intersects(f.geometry())
        ]
        if len(candidates) > 1:
            candidates.sort(key=lambda f: f.id())
            to_delete.update(f.id() for f in candidates[1:])

    if to_delete:
        points_layer.dataProvider().deleteFeatures(list(to_delete))
        points_layer.dataProvider().reloadData()
        points_layer.triggerRepaint()

    return to_delete


def load_mappy_info_text():
    file = QFile(":/plugins/qgismappy/INFO.html")
    file.open(QFile.OpenModeFlag.ReadOnly | QFile.OpenModeFlag.Text)
    stream = QTextStream(file)
    text = stream.readAll()
    # print(f"text {text}")
    return text


def write_layer_to_gpkg(layer, gpkgfile, layername):
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    options.layerName = layername
    context = QgsProject.instance().transformContext()
    QgsVectorFileWriter.writeAsVectorFormatV2(layer, gpkgfile, context, options)


def write_layer_to_gpkg2(layer, gpkgfile, layername):
    options = QgsVectorFileWriter.SaveVectorOptions()
    from pathlib import Path

    if Path(gpkgfile).exists():
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    else:
        options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile

    # to get rid of spaces in the layer name
    options.layerName = layername
    context = QgsProject.instance().transformContext()

    if hasattr(QgsVectorFileWriter, "writeAsVectorFormatV3"):
        return QgsVectorFileWriter.writeAsVectorFormatV3(
            layer, gpkgfile, context, options
        )
    else:
        return QgsVectorFileWriter.writeAsVectorFormatV2(
            layer, gpkgfile, context, options
        )


def resetCategoriesIfNeeded(layer, units_field):

    prev_rend = layer.renderer()

    if not isinstance(prev_rend, QgsCategorizedSymbolRenderer):
        renderer = QgsCategorizedSymbolRenderer(units_field)
        layer.setRenderer(renderer)
    else:
        renderer = prev_rend

    prev_cats = renderer.categories()

    id = layer.fields().indexFromName(units_field)
    uniques = list(layer.uniqueValues(id))
    has_unassigned = None in uniques
    uniques = [u for u in uniques if u is not None]

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

    for current, value in enumerate(values):
        already_in = False
        for prev in prev_cats:
            if prev.value() == value:
                already_in = True
                continue

        if not already_in:
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            from qgis.PyQt.QtCore import Qt
            from qgis.PyQt.QtGui import QColor

            if slayer := symbol.symbolLayer(0):
                slayer.setStrokeStyle(Qt.PenStyle.NoPen)

            if value is None:
                symbol.setColor(QColor(200, 200, 200))
                if slayer and hasattr(slayer, "setBrushStyle"):
                    slayer.setBrushStyle(Qt.BrushStyle.DiagCrossPattern)
                label = "Unassigned"
            else:
                label = str(value)

            category = QgsRendererCategory(value, symbol, label)
            categories.append(category)

    for cat in categories:
        renderer.addCategory(cat)

    # layer.setRenderer(renderer)
    layer.rendererChanged.emit()
    layer.dataSourceChanged.emit()

    layer.triggerRepaint()
