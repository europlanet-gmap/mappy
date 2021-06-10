from qgis.PyQt.QtCore import QFile, QTextStream
from qgis.PyQt.QtWidgets import QLineEdit, QCheckBox
from qgis._core import QgsVectorFileWriter, QgsProject, QgsCategorizedSymbolRenderer, QgsSymbol, QgsRendererCategory
from qgis._gui import QgsFileWidget
from qgis.gui import QgsFieldComboBox, QgsDoubleSpinBox, QgsMapLayerComboBox


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


def collect_parameters(qt_obj):
    pars = {}
    for name in qt_obj.__dict__:
        val = readWidgetContent(getattr(qt_obj, name))
        if val is not None:
            pars[name] = val

    return pars


def load_mappy_info_text():
    file = QFile(":/plugins/qgismappy/INFO.html")
    file.open(QFile.ReadOnly | QFile.Text)
    stream = QTextStream(file)
    return stream.readAll()


def write_layer_to_gpkg(layer, gpkgfile,  layername):
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer
    options.layerName = layername
    context = QgsProject.instance().transformContext()
    QgsVectorFileWriter.writeAsVectorFormatV2(layer, gpkgfile, context, options)


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

    for current, value in enumerate(values):

        already_in = False
        for prev in prev_cats:
            if prev.value() == value:
                already_in = True
                continue

        if not already_in:
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            category = QgsRendererCategory(value, symbol, str(value))
            categories.append(category)

    for cat in categories:
        renderer.addCategory(cat)

    # layer.setRenderer(renderer)
    layer.rendererChanged.emit()
    layer.dataSourceChanged.emit()

    layer.triggerRepaint()

