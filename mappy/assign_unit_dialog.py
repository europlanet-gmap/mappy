from qgis.PyQt.QtCore import QEvent, Qt
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)
from qgis.gui import QgsFilterLineEdit


class AssignUnitDialog(QDialog):
    """Lets the user pick a unit name out of every value currently in use,
    filtering the list live as they type, or type a brand new one."""

    def __init__(self, existing_values, current_value=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Assign unit")
        self.resize(320, 400)

        self.filter_edit = QgsFilterLineEdit()
        self.filter_edit.setPlaceholderText("Filter, or type a new unit name...")
        self.filter_edit.installEventFilter(self)

        self.list_widget = QListWidget()
        for value in existing_values:
            self.list_widget.addItem(QListWidgetItem(value))

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        layout = QVBoxLayout()
        layout.addWidget(self.filter_edit)
        layout.addWidget(self.list_widget)
        layout.addWidget(self.button_box)
        self.setLayout(layout)

        self.list_widget.itemClicked.connect(self._select_item)
        self.list_widget.itemActivated.connect(self._accept_item)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        # pre-fill the current value without triggering the filter -- the
        # list should still show every unit at first, just with the current
        # one highlighted, not filtered down to a single match
        if current_value:
            self.filter_edit.setText(current_value)
            matches = self.list_widget.findItems(current_value, Qt.MatchFlag.MatchExactly)
            if matches:
                self.list_widget.setCurrentItem(matches[0])
                self.list_widget.scrollToItem(matches[0])

        self.filter_edit.textChanged.connect(self._apply_filter)

        self.filter_edit.setFocus()
        self.filter_edit.selectAll()

    def eventFilter(self, obj, event):
        # Down/Up from the filter box hands keyboard focus to the list, so
        # the whole picker is usable without touching the mouse
        if obj is self.filter_edit and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                self._focus_list()
                return True
        return super().eventFilter(obj, event)

    def _focus_list(self):
        if self.list_widget.currentRow() == -1:
            for i in range(self.list_widget.count()):
                if not self.list_widget.item(i).isHidden():
                    self.list_widget.setCurrentRow(i)
                    break
        self.list_widget.setFocus()

    def _apply_filter(self, text):
        text = text.lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(text not in item.text().lower())

    def _select_item(self, item):
        self.filter_edit.setText(item.text())

    def _accept_item(self, item):
        self.filter_edit.setText(item.text())
        self.accept()

    def unit_name(self):
        return self.filter_edit.text().strip()

    @staticmethod
    def getUnit(parent, existing_values, current_value=None):
        dlg = AssignUnitDialog(existing_values, current_value, parent)
        ok = dlg.exec() == QDialog.DialogCode.Accepted
        return dlg.unit_name(), ok
