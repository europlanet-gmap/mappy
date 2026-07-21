from dataclasses import dataclass

from qgis.PyQt.QtCore import QObject, pyqtSignal
from qgis.core import QgsFeature, QgsPointXY, QgsVectorLayer


@dataclass
class EngineConfig:
    """Replaces the ad hoc `pars` dict previously read out of the config dock
    via `collect_parameters`. Fields mirror exactly what `recompute_map`/
    `assign_unit_at_point` used to read out of that dict.
    """

    lines: QgsVectorLayer | None = None
    points: QgsVectorLayer | None = None
    output: str = ""
    out_polygons_layer_name: str = ""
    out_contacts_layer_name: str = ""
    units_field: str = ""
    add_indicators: bool = False
    generate_clean_contacts: bool = False
    copyoverlinestyle: bool = False
    auto_recompute_on_assign_unit: bool = False

    @classmethod
    def from_parameters(cls, pars: dict) -> "EngineConfig":
        """`pars` comes from `collect_parameters(dock)`; a key is simply
        absent if the corresponding widget has nothing selected yet, same
        as the `pars.get(...)`/`pars[...]` mix this replaces -- so missing
        keys fall back to this dataclass's own defaults.
        """
        names = cls.__dataclass_fields__.keys()
        return cls(**{name: pars[name] for name in names if name in pars})


class EngineError(Exception):
    """Raised by a MapEngine when a precondition for an operation isn't met
    (missing/invalid layers, map not yet generated, missing units field,
    etc). The GUI layer catches this and turns it into an alert box."""


class MapEngine(QObject):
    """Abstract contract for a map-generation/processing engine, kept
    independent of any GUI (no dialogs, no menus, no map tools, no
    `iface`) so a future, differently-implemented engine (e.g. one that
    keeps the map incrementally updated rather than fully recomputing it)
    can be swapped in without touching the GUI layer.

    This is a plain QObject, not an ABC: QObject's sip metaclass conflicts
    with Python's ABCMeta, so subclasses must override every method below
    themselves -- there is no enforcement at class-definition time.

    Signals are the mechanism for the engine to notify a GUI of things that
    happened. Only what today's behavior needs is emitted for now:
    `errorOccurred` is declared here but intentionally unused by this
    round's implementation (which reports failures synchronously via
    `EngineError`) -- it's reserved for a future engine where an operation
    can fail asynchronously after the call already returned. Likewise,
    finer-grained events (a contact being created or edited) aren't part
    of this interface yet; they slot in here later as the same kind of
    signal, once an engine implementation exists that can actually detect
    and emit them.
    """

    mapRecomputed = pyqtSignal()
    unitAssigned = pyqtSignal(str, object)  # unit text, assigned polygon feature id
    errorOccurred = pyqtSignal(str)  # reserved, not emitted this round

    def __init__(self, config: EngineConfig | None = None, parent=None):
        super().__init__(parent)
        self.config = config or EngineConfig()

    def recompute_map(self) -> None:
        raise NotImplementedError

    def get_polygons_layer(self) -> QgsVectorLayer:
        raise NotImplementedError

    def find_polygon_at_point(self, point: QgsPointXY) -> QgsFeature | None:
        raise NotImplementedError

    def find_indicator_for_polygon(
        self, polygon_feature: QgsFeature, near_point: QgsPointXY | None = None
    ) -> QgsFeature | None:
        raise NotImplementedError

    def list_existing_units(self) -> list[str]:
        raise NotImplementedError

    def get_color_table(self) -> dict[str, str]:
        raise NotImplementedError

    def assign_unit(
        self,
        polygon_feature: QgsFeature,
        point_feature: QgsFeature | None,
        click_point: QgsPointXY,
        unit_text: str,
        color: str | None = None,
        changed_colors: dict[str, str] | None = None,
    ) -> None:
        raise NotImplementedError
