from qgis.PyQt import Qt
from qgis.PyQt.QtCore import QFile, QTextStream
from qgis.PyQt.QtWidgets import QLineEdit, QCheckBox
from qgis._core import QgsVectorLayer, QgsMapLayer
from qgis.core import QgsVectorFileWriter, QgsProject, QgsCategorizedSymbolRenderer, QgsSymbol, QgsRendererCategory
from qgis.gui import QgsFileWidget
from qgis.gui import QgsFieldComboBox, QgsDoubleSpinBox, QgsMapLayerComboBox

parameters_widgets = [QgsMapLayerComboBox, QgsFieldComboBox, QgsDoubleSpinBox, QLineEdit, QCheckBox, QgsFileWidget]

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
        return bool(widget.checkState())

    elif isinstance(widget, QgsFileWidget):
        return widget.filePath()

    else:
        return None

def restoreWidgetContent(widget, value):
    if isinstance(widget, QgsMapLayerComboBox):
        if not isinstance(value, QgsMapLayer):
            raise TypeError(f"{type(value)} is a wrong type for widget QgsMapLayerComboBox")
        widget.setLayer(value)

    elif isinstance(widget, QgsFieldComboBox):
        exists = widget.findText(str(value))
        if not exists:
            raise ValueError(f"You are trying to set the widget {widget.name()} to value {value}. but combo box does not contain this value")

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

def collect_parameters(qt_obj):
    pars = {}
    for name in qt_obj.__dict__:
        val = readWidgetContent(getattr(qt_obj, name))
        if val is not None:
            pars[name] = val

    return pars

def add_layer_from_geopackage(gpkgfile, layer_name, categories_field=None):
    gpkgfile += f"|layername={layer_name}"
    l = QgsVectorLayer(gpkgfile)
    l.setName(layer_name)
    QgsProject.instance().addMapLayer(l)
    return l

def load_mappy_info_text():
    file = QFile(":/plugins/qgismappy/INFO.html")
    file.open(QFile.ReadOnly | QFile.Text)
    stream = QTextStream(file)
    text = stream.readAll()
    # print(f"text {text}")
    return text


def write_layer_to_gpkg(layer, gpkgfile,  layername):
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
        return QgsVectorFileWriter.writeAsVectorFormatV3(layer, gpkgfile, context, options)
    else:
        return QgsVectorFileWriter.writeAsVectorFormatV2(layer, gpkgfile, context, options)





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
    uniques = [u for u in uniques if u is not None]

    values = sorted(uniques)
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

            symbol.symbolLayer(0).setStrokeStyle(Qt.NoPen)

            category = QgsRendererCategory(value, symbol, str(value))
            categories.append(category)

    for cat in categories:
        renderer.addCategory(cat)

    # layer.setRenderer(renderer)
    layer.rendererChanged.emit()
    layer.dataSourceChanged.emit()

    layer.triggerRepaint()

