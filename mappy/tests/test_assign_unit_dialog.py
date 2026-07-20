from unittest.mock import patch

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QColor

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

    def test_shows_existing_units_stored_color(self):
        color_table = {"Basalt": "#ff0000", "Breccia": "#00ff00"}
        dlg = AssignUnitDialog(["Basalt", "Breccia"], current_value="Basalt", color_table=color_table)

        self.assertEqual(dlg.unit_color(), "#ff0000")

        item = dlg.list_widget.findItems("Breccia", Qt.MatchFlag.MatchExactly)[0]
        dlg._select_item(item)
        self.assertEqual(dlg.unit_color(), "#00ff00")

    def test_list_items_carry_a_color_swatch_icon(self):
        color_table = {"Basalt": "#ff0000"}
        dlg = AssignUnitDialog(["Basalt"], color_table=color_table)

        item = dlg.list_widget.item(0)
        self.assertFalse(item.icon().isNull())

    def test_new_unit_gets_a_proposed_color_stable_while_typing(self):
        dlg = AssignUnitDialog(["Basalt"], color_table={"Basalt": "#ff0000"})

        dlg.filter_edit.setText("Regolith")
        proposed = dlg.unit_color()

        self.assertIsNotNone(proposed)
        self.assertNotIn(proposed, {"#ff0000"})

        # re-setting the exact same text must not re-roll the proposal
        dlg.filter_edit.setText("Regolith")
        self.assertEqual(dlg.unit_color(), proposed)

    def test_manual_color_pick_is_kept_while_editing_the_same_new_unit(self):
        dlg = AssignUnitDialog(["Basalt"], color_table={"Basalt": "#ff0000"})
        dlg.filter_edit.setText("Regolith")

        with patch("mappy.assign_unit_dialog.QColorDialog.getColor", return_value=QColor("#0000ff")):
            dlg._pick_color()

        self.assertEqual(dlg.unit_color(), "#0000ff")

        # re-setting the identical text (e.g. Qt re-firing textChanged)
        # must not discard the manual pick
        dlg.filter_edit.setText("Regolith")
        self.assertEqual(dlg.unit_color(), "#0000ff")
        self.assertEqual(dlg.color_table["Regolith"], "#0000ff")

    def test_manual_pick_does_not_leak_into_a_different_new_unit(self):
        dlg = AssignUnitDialog(["Basalt"], color_table={"Basalt": "#ff0000"})
        dlg.filter_edit.setText("Regolith")
        with patch("mappy.assign_unit_dialog.QColorDialog.getColor", return_value=QColor("#0000ff")):
            dlg._pick_color()

        dlg.filter_edit.setText("Impact melt")

        self.assertNotEqual(dlg.unit_color(), "#0000ff")

    def test_recoloring_an_existing_unit_updates_its_list_icon_and_table(self):
        dlg = AssignUnitDialog(["Basalt"], color_table={"Basalt": "#ff0000"})
        dlg.filter_edit.setText("Basalt")

        with patch("mappy.assign_unit_dialog.QColorDialog.getColor", return_value=QColor("#abcdef")):
            dlg._pick_color()

        self.assertEqual(dlg.unit_color(), "#abcdef")
        self.assertEqual(dlg.color_table["Basalt"], "#abcdef")
        item = dlg.list_widget.item(0)
        self.assertFalse(item.icon().isNull())

    def test_empty_text_disables_the_color_button(self):
        dlg = AssignUnitDialog(["Basalt"], color_table={"Basalt": "#ff0000"})

        dlg.filter_edit.setText("")

        self.assertFalse(dlg.color_button.isEnabled())
        self.assertIsNone(dlg.unit_color())

    def test_cancelling_the_color_dialog_keeps_the_previous_color(self):
        dlg = AssignUnitDialog(["Basalt"], color_table={"Basalt": "#ff0000"})
        dlg.filter_edit.setText("Basalt")

        with patch("mappy.assign_unit_dialog.QColorDialog.getColor", return_value=QColor()):  # invalid == cancelled
            dlg._pick_color()

        self.assertEqual(dlg.unit_color(), "#ff0000")

    def test_recoloring_one_unit_then_confirming_another_does_not_lose_the_first_change(self):
        # regression test: getUnit() used to only report the color for
        # whichever unit ended up confirmed on OK. Recoloring "Basalt" and
        # then picking/confirming "Breccia" silently dropped the Basalt
        # change -- changed_colors() must carry every edit made this session
        dlg = AssignUnitDialog(
            ["Basalt", "Breccia"], color_table={"Basalt": "#ff0000", "Breccia": "#00ff00"}
        )

        dlg.filter_edit.setText("Basalt")
        with patch("mappy.assign_unit_dialog.QColorDialog.getColor", return_value=QColor("#111111")):
            dlg._pick_color()

        item = dlg.list_widget.findItems("Breccia", Qt.MatchFlag.MatchExactly)[0]
        dlg._select_item(item)

        self.assertEqual(dlg.unit_name(), "Breccia")
        self.assertEqual(dlg.changed_colors(), {"Basalt": "#111111"})

    def test_changed_colors_includes_the_confirmed_unit_if_recolored(self):
        dlg = AssignUnitDialog(["Basalt"], color_table={"Basalt": "#ff0000"})
        dlg.filter_edit.setText("Basalt")

        with patch("mappy.assign_unit_dialog.QColorDialog.getColor", return_value=QColor("#111111")):
            dlg._pick_color()

        self.assertEqual(dlg.changed_colors(), {"Basalt": "#111111"})
        self.assertEqual(dlg.unit_color(), "#111111")

    def test_changed_colors_empty_when_nothing_recolored(self):
        dlg = AssignUnitDialog(["Basalt", "Breccia"], color_table={"Basalt": "#ff0000", "Breccia": "#00ff00"})

        item = dlg.list_widget.findItems("Breccia", Qt.MatchFlag.MatchExactly)[0]
        dlg._select_item(item)

        self.assertEqual(dlg.changed_colors(), {})
