from collections.abc import Callable
from dataclasses import dataclass, field

from qgis.PyQt.QtCore import QObject, pyqtSignal
from qgis.core import QgsFeature, QgsPointXY, QgsVectorLayer


@dataclass
class TopologyValidationReport:
    """Result of MapEngine.validate_topology(): whether the engine's
    topology bookkeeping (if any) still matches reality, and human-readable
    notes on any drift found. `ProcessingMapEngine` (no topology of its own)
    always reports in_sync=True."""

    in_sync: bool
    issues: list[str] = field(default_factory=list)


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
    # Independent on/off switches for the categorized coloring and default
    # labeling this plugin otherwise applies automatically to the output
    # polygons and indicator points layers on every recompute/assign_unit.
    # All default True (today's unconditional behavior); a user who's
    # already styled/labeled a layer by hand can turn the matching one off
    # without losing the underlying persisted color data, which keeps
    # flowing between layers regardless (see engine/colors.py).
    auto_color_polygons: bool = True
    auto_label_polygons: bool = True
    auto_color_points: bool = True
    auto_label_points: bool = True
    # Off by default: a wrongly-selected lines layer can make points that
    # aren't actually duplicates land in the same malformed polygon,
    # permanently deleting real data (see drop_duplicate_points_per_polygon
    # in layers.py). Opt-in, not just guarded/confirmed at the point of
    # deletion, so this never runs at all unless a user deliberately wants
    # the cleanup.
    remove_duplicate_indicator_points: bool = False
    generate_clean_contacts: bool = False
    copyoverlinestyle: bool = False
    auto_recompute_on_assign_unit: bool = False
    use_incremental_engine: bool = False
    incremental_debounce_ms: int = 500
    incremental_dirty_fraction_fallback: float = 0.3
    # SpatiaLite's ISO topology engine requires near-exact coordinate
    # matching at junctions -- real digitized line data essentially never
    # satisfies that (unlike native:polygonize/GEOS, which is far more
    # forgiving), causing spurious "geometry crosses an edge" errors on
    # ordinary data. IncrementalMapEngine handles this itself by snapping
    # every line's coordinates to a grid this wide before it reaches the
    # topology (CreateTopology's own tolerance parameter turned out to
    # silently reject any non-integer value in testing -- see
    # incremental_engine.py's _prepare_line_geometry). 1e-6 matches the
    # tolerance already used elsewhere in this codebase for the same kind
    # of near-duplicate-vertex slop (see native:removeduplicatevertices
    # calls in map_construction.py/addselfintersectionpoints.py).
    topology_tolerance: float = 1e-6

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


class RecomputeCancelled(EngineError):
    """Raised when the user declines a MapEngine.confirm_destructive_step
    prompt (currently just drop_duplicate_points_per_polygon's deletions)
    -- the operation that raised it aborts without writing anything. A
    subclass of EngineError so callers that don't distinguish still catch
    it, but the GUI catches this one separately and stays silent instead of
    showing an alert box, mirroring qgismappy.check_input_pars' own
    Save/Cancel convention for a user-initiated cancellation."""


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
    topologyDirty = pyqtSignal(int)  # count of pending dirty-line rows, for an optional status indicator

    def __init__(self, config: EngineConfig | None = None, parent=None):
        super().__init__(parent)
        self.config = config or EngineConfig()
        # Optional GUI-injected yes/no gate for a destructive, hard-to-reverse
        # step (currently just drop_duplicate_points_per_polygon's
        # deletions) -- keeps this class itself free of dialogs per the
        # class docstring above. None (the default outside the Mappy GUI:
        # tests, scripts, direct Processing algorithm use) auto-approves,
        # preserving that non-interactive behavior; Mappy wires a real
        # confirmation dialog onto each engine instance it constructs.
        self.confirm_destructive_step: Callable[[str], bool] | None = None

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

    def process_pending_changes(self) -> None:
        """Drain whatever "features changed" bookkeeping this engine keeps
        and react to it. Called by the GUI shortly after it notices a
        commit on the configured lines/points layers (see
        Mappy._rewire_layer_signals); callers don't need to -- and don't --
        carry the precise added/modified/removed payload themselves, since
        an engine that tracks this at all (see IncrementalMapEngine) keeps
        its own authoritative record of what changed."""
        raise NotImplementedError

    def invalidate(self) -> None:
        """Drops any incremental/topology state this engine keeps, so the
        next recompute_map() rebuilds it from scratch. Also the manual
        "repair drift" action."""
        raise NotImplementedError

    def validate_topology(self) -> TopologyValidationReport:
        """Read-only drift check between whatever topology bookkeeping this
        engine keeps and the current state of its layers."""
        raise NotImplementedError
