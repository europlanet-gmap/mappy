from qgis.PyQt.QtCore import Qt

from mappy.assign_unit_dialog import AssignUnitDialog
from mappy.tests import ExtendedUnitTesting


class TestAssignUnitDialog(ExtendedUnitTesting):
    def test_all_units_visible_when_opened_with_a_current_value(self):
        # pre-filling the filter box with the current value must not filter
        # the list down to a single match -- the whole point of the dialog
        # is to make every other unit easy to pick too
        values = ["Basalt", "Breccia", "Regolith", "Ridge", "Rille"]
        dlg = AssignUnitDialog(values, current_value="Regolith")

        visible = [
            dlg.list_widget.item(i).text()
            for i in range(dlg.list_widget.count())
            if not dlg.list_widget.item(i).isHidden()
        ]
        self.assertEqual(visible, values)
        self.assertEqual(dlg.filter_edit.text(), "Regolith")
        self.assertEqual(dlg.list_widget.currentItem().text(), "Regolith")

    def test_typing_filters_the_list_case_insensitively(self):
        dlg = AssignUnitDialog(["Basalt", "Breccia", "Regolith", "Ridge", "Rille"])

        dlg.filter_edit.setText("RI")

        visible = [
            dlg.list_widget.item(i).text()
            for i in range(dlg.list_widget.count())
            if not dlg.list_widget.item(i).isHidden()
        ]
        self.assertEqual(visible, ["Ridge", "Rille"])

    def test_clicking_an_item_fills_the_filter_box(self):
        dlg = AssignUnitDialog(["Basalt", "Breccia"])

        item = dlg.list_widget.findItems("Breccia", Qt.MatchFlag.MatchExactly)[0]
        dlg._select_item(item)

        self.assertEqual(dlg.unit_name(), "Breccia")

    def test_activating_an_item_accepts_the_dialog(self):
        dlg = AssignUnitDialog(["Basalt", "Breccia"])

        item = dlg.list_widget.findItems("Breccia", Qt.MatchFlag.MatchExactly)[0]
        dlg._accept_item(item)

        self.assertEqual(dlg.result(), 1)  # QDialog.DialogCode.Accepted
        self.assertEqual(dlg.unit_name(), "Breccia")

    def test_typing_a_brand_new_value_is_kept_as_is(self):
        dlg = AssignUnitDialog(["Basalt", "Breccia"])

        dlg.filter_edit.setText("NewUnit")

        self.assertEqual(dlg.unit_name(), "NewUnit")
