from qgis.PyQt.QtCore import Qt
from qgis.gui import QgsMapTool

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mappy.qgismappy import Mappy


class AssignUnitMapTool(QgsMapTool):
    """Click a polygon on the map to assign a unit name to its indicator point."""

    def __init__(self, canvas, mappy):
        super().__init__(canvas)
        self.mappy: Mappy = mappy

    def canvasReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return

        point = self.toMapCoordinates(event.pos())
        self.mappy.assign_unit_at_point(point)

    def deactivate(self):
        super().deactivate()
        self.mappy.on_assign_unit_tool_deactivated()
