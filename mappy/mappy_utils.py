import os

from qgis.PyQt.QtCore import QFile, QTextStream
from qgis.PyQt.QtWidgets import QLineEdit, QCheckBox
from qgis.core import QgsVectorLayer, QgsMapLayer
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


def readWidgetContent(widget) -> QgsMapLayer | str | float | bool | None:
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


def restoreWidgetContent(widget, value) -> None:
    if isinstance(widget, QgsMapLayerComboBox):
        if not isinstance(value, QgsMapLayer):
            raise TypeError(f"{type(value)} is a wrong type for widget QgsMapLayerComboBox")
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


def serialize_value_for_settings(value) -> str:
    if type(value) in [QgsVectorLayer]:
        return value.id()
    else:
        return str(value)


def collect_parameters(qt_obj) -> dict:
    pars = {}
    for name in qt_obj.__dict__:
        val = readWidgetContent(getattr(qt_obj, name))
        if val is not None:
            pars[name] = val

    return pars


def is_dev_mode() -> bool:
    """True when the MAPPY_DEV environment variable is set to a truthy
    value. Gates GUI-visible access to still-experimental features (e.g.
    the incremental engine) behind an explicit opt-in, so a generic user
    never sees or can enable them."""
    return os.environ.get("MAPPY_DEV", "").strip().lower() in ("1", "true", "yes", "on")


def load_mappy_info_text() -> str:
    file = QFile(":/plugins/qgismappy/INFO.html")
    file.open(QFile.OpenModeFlag.ReadOnly | QFile.OpenModeFlag.Text)
    stream = QTextStream(file)
    text = stream.readAll()
    # print(f"text {text}")
    return text
