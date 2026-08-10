from qgis.PyQt.QtCore import Qt
from qgis.gui import QgsMapTool

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mappy.qgismappy import Mappy


class AssignUnitMapTool(QgsMapTool):
    """A plain click opens the assign-unit dialog immediately for just the
    clicked polygon. Ctrl+click instead toggles the clicked polygon into/out
    of a multi-polygon selection, which a right-click -- the same gesture
    QGIS's own digitizing tools use to close a sketch -- applies one dialog
    pick to all at once."""

    def __init__(self, canvas, mappy):
        super().__init__(canvas)
        self.mappy: Mappy = mappy

    def canvasReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            point = self.toMapCoordinates(event.pos())
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                self.mappy.add_polygon_to_assign_selection(point)
            else:
                self.mappy.assign_unit_at_point(point)
        elif event.button() == Qt.MouseButton.RightButton:
            self.mappy.finish_assign_unit_selection()

    def deactivate(self):
        super().deactivate()
        self.mappy.on_assign_unit_tool_deactivated()
