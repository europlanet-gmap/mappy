from qgis.PyQt.QtCore import QEvent, QSize, Qt
from qgis.PyQt.QtGui import QColor, QIcon, QPixmap
from qgis.PyQt.QtWidgets import (
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QToolButton,
    QVBoxLayout,
)
from qgis.gui import QgsFilterLineEdit

from .mappy_utils import sequential_color


def _swatch_icon(color):
    pixmap = QPixmap(16, 16)
    pixmap.fill(QColor(color))
    return QIcon(pixmap)


class AssignUnitDialog(QDialog):
    """Lets the user pick a unit name out of every value currently in use,
    filtering the list live as they type, or type a brand new one -- with
    every unit's color shown alongside it, and a swatch button to change
    the color of whichever unit is currently typed/selected right there,
    with no separate dialog beyond the native color picker.
    """

    def __init__(self, existing_values, current_value=None, color_table=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Assign unit")
        self.resize(320, 400)

        # local copy: edits made in this dialog (recoloring an existing
        # unit, or picking a color for a new one) only take effect once the
        # caller reads them back via unit_color()/changed_colors(), not as
        # a side effect of merely opening the dialog
        self.color_table = dict(color_table or {})
        self._current_color = None
        self._manual_pick_text = None
        # every color explicitly picked this session, keyed by unit name --
        # not just the one for whatever ends up confirmed on OK. Without
        # this, recoloring "Basalt" and then picking/confirming "Breccia"
        # would silently drop the Basalt change.
        self._changed_colors = {}

        self.filter_edit = QgsFilterLineEdit()
        self.filter_edit.setPlaceholderText("Filter, or type a new unit name...")
        self.filter_edit.installEventFilter(self)

        self.color_button = QToolButton()
        self.color_button.setFixedSize(QSize(24, 24))
        self.color_button.setToolTip("Change this unit's color")
        self.color_button.clicked.connect(self._pick_color)

        self.list_widget = QListWidget()
        for value in existing_values:
            item = QListWidgetItem(value)
            color = self.color_table.get(value)
            if color:
                item.setIcon(_swatch_icon(color))
            self.list_widget.addItem(item)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )

        top_row = QHBoxLayout()
        top_row.addWidget(self.filter_edit)
        top_row.addWidget(self.color_button)

        layout = QVBoxLayout()
        layout.addLayout(top_row)
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

        self._refresh_color_for_text(self.filter_edit.text())

        self.filter_edit.textChanged.connect(self._apply_filter)
        self.filter_edit.textChanged.connect(self._refresh_color_for_text)

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

    def _refresh_color_for_text(self, text):
        text = text.strip()

        if text == self._manual_pick_text:
            # user already hand-picked a color for exactly this text; don't
            # override it just because setText() re-fired textChanged
            return

        if not text:
            self._current_color = None
            self.color_button.setEnabled(False)
            self.color_button.setIcon(QIcon())
            return

        self.color_button.setEnabled(True)
        if text in self.color_table:
            self._set_current_color(self.color_table[text], manual=False)
        else:
            # propose the next auto-generated color for a brand new unit --
            # same sequence used when the unit is actually persisted, so the
            # preview matches what would happen if the user didn't touch it
            proposed = sequential_color(len(self.color_table)).name()
            self._set_current_color(proposed, manual=False)

    def _set_current_color(self, color, manual):
        self._current_color = color
        self._manual_pick_text = self.filter_edit.text().strip() if manual else None
        self.color_button.setIcon(_swatch_icon(color))

    def _pick_color(self):
        initial = QColor(self._current_color) if self._current_color else QColor("white")
        chosen = QColorDialog.getColor(initial, self, "Pick unit color")
        if not chosen.isValid():
            return

        self._set_current_color(chosen.name(), manual=True)

        text = self.filter_edit.text().strip()
        if not text:
            return
        self.color_table[text] = chosen.name()
        self._changed_colors[text] = chosen.name()
        matches = self.list_widget.findItems(text, Qt.MatchFlag.MatchExactly)
        if matches:
            matches[0].setIcon(_swatch_icon(chosen.name()))

    def unit_name(self):
        return self.filter_edit.text().strip()

    def unit_color(self):
        return self._current_color

    def changed_colors(self):
        """Every color explicitly picked during this session, keyed by unit
        name -- including units other than the one finally confirmed."""
        return dict(self._changed_colors)

    @staticmethod
    def getUnit(parent, existing_values, current_value=None, color_table=None):
        dlg = AssignUnitDialog(existing_values, current_value, color_table, parent)
        ok = dlg.exec() == QDialog.DialogCode.Accepted
        return dlg.unit_name(), dlg.unit_color(), dlg.changed_colors(), ok
