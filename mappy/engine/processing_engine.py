from qgis import processing
from qgis.core import (
    QgsFeature,
    QgsFeatureRequest,
    QgsGeometry,
    QgsRectangle,
    QgsVectorLayer,
)

from .colors import get_or_create_color_table, resetCategoriesIfNeeded, sync_unit_colors, write_colors_to_points
from .interface import EngineError, MapEngine, TopologyValidationReport
from .layers import add_layer_from_geopackage, drop_duplicate_points_per_polygon, find_layer, write_layer_to_gpkg
from .styling import enable_default_labels


class ProcessingMapEngine(MapEngine):
    """MapEngine implementation built on today's QGIS Processing algorithms
    (polygonize + spatial join, via `processing.run("mappy:mapconstruction",
    ...)`) and full recompute-on-demand -- i.e. exactly today's behavior,
    just relocated behind the MapEngine interface. A future incremental
    engine would implement the same interface differently.
    """

    def _load_layer_if_not_loaded(
        self, gpkgfile, layername, field_style=None, insert_after=None, points_layer=None
    ) -> QgsVectorLayer:
        layer = find_layer(gpkgfile, layername)
        if layer is None:
            layer = add_layer_from_geopackage(gpkgfile, layername, insert_after=insert_after)
        else:
            layer.dataProvider().reloadData()
            layer.triggerRepaint()

        layer.setReadOnly()

        if field_style:
            config = self.config
            if points_layer is not None:
                sync_unit_colors(
                    points_layer,
                    layer,
                    field_style,
                    style_points=config.auto_color_points,
                    style_polygons=config.auto_color_polygons,
                )
                if config.auto_label_points:
                    enable_default_labels(points_layer, field_style)
            elif config.auto_color_polygons:
                resetCategoriesIfNeeded(layer, field_style)
            if config.auto_label_polygons:
                enable_default_labels(layer, field_style)

        return layer

    def recompute_map(self) -> None:
        config = self.config
        if config.lines is None or config.points is None:
            raise EngineError("Missing lines or points layer.")

        ofile = config.output
        olayername = config.out_polygons_layer_name
        o_cont_name = config.out_contacts_layer_name
        points_layer = config.points

        args = {
            "IN_LINES": config.lines,
            "IN_POINTS": points_layer,
            "OUTPUT": "TEMPORARY_OUTPUT",
            "UNMATCHED": "TEMPORARY_OUTPUT",
        }
        o = processing.run("mappy:mapconstruction", args)

        layer = o["OUTPUT"]
        unmatched = o["UNMATCHED"]

        # the join that assigned attributes to polygons only used the first
        # matching point where more than one fell inside the same polygon;
        # leftover duplicate indicator points are only cosmetic clutter (the
        # join already ignored them), so cleaning them up is opt-in -- off
        # by default, see EngineConfig.remove_duplicate_indicator_points.
        # confirm_destructive_step/the guard threshold inside
        # drop_duplicate_points_per_polygon still apply on top when enabled.
        if config.remove_duplicate_indicator_points:
            drop_duplicate_points_per_polygon(points_layer, layer, confirm=self.confirm_destructive_step)

        if config.add_indicators:
            newpoints = processing.run(
                "mappy:labelspointsfrompolygons", {"IN_LAYER": unmatched, "TOLERANCE": 1, "OUTPUT": "TEMPORARY_OUTPUT"}
            )["OUTPUT"]

            newfeats = []
            for feature in newpoints.getFeatures():
                newf = QgsFeature()
                newf.setGeometry(feature.geometry())
                newfeats.append(newf)

            points_layer.dataProvider().addFeatures(newfeats)
            points_layer.dataProvider().reloadData()
            points_layer.triggerRepaint()

        write_layer_to_gpkg(layer, ofile, olayername)
        self._load_layer_if_not_loaded(
            ofile,
            olayername,
            field_style=config.units_field,
            insert_after=["source_contacts", "source_indicators"],
            points_layer=points_layer,
        )

        if config.generate_clean_contacts:
            opts = {
                "Extenddistance": 0,
                "PrecisionjoinBuffer": 0.001,
                "contacts": config.lines,
                "polygonized": layer,
                "OUTPUT": "TEMPORARY_OUTPUT",
            }
            layer = processing.run("mappy:removedangles", opts)["OUTPUT"]
            write_layer_to_gpkg(layer, ofile, o_cont_name)
            layer = self._load_layer_if_not_loaded(ofile, o_cont_name, None)

            if config.copyoverlinestyle:
                newrend = config.lines.renderer().clone()  # we clone the renderer
                layer.setRenderer(newrend)

        self.mapRecomputed.emit()

    def get_polygons_layer(self) -> QgsVectorLayer:
        config = self.config
        if config.points is None or not config.units_field:
            raise EngineError("Missing points layer or units field. Please configure them in Mappy settings.")

        polygons_layer = find_layer(config.output, config.out_polygons_layer_name)
        if polygons_layer is None:
            raise EngineError("The map hasn't been generated yet. Run map construction first.")

        return polygons_layer

    def find_polygon_at_point(self, point) -> QgsFeature | None:
        polygons_layer = self.get_polygons_layer()
        click_geom = QgsGeometry.fromPointXY(point)
        request = QgsFeatureRequest().setFilterRect(QgsRectangle(point, point))
        for f in polygons_layer.getFeatures(request):
            if f.geometry().intersects(click_geom):
                return f
        return None

    def find_indicator_for_polygon(self, polygon_feature, near_point=None) -> QgsFeature | None:
        points_layer = self.config.points
        request = QgsFeatureRequest().setFilterRect(polygon_feature.geometry().boundingBox())
        candidates = [f for f in points_layer.getFeatures(request) if polygon_feature.geometry().intersects(f.geometry())]

        if not candidates:
            return None

        if near_point is not None:
            click_geom = QgsGeometry.fromPointXY(near_point)
            return min(candidates, key=lambda f: f.geometry().distance(click_geom))

        return candidates[0]

    def list_existing_units(self) -> list[str]:
        points_layer = self.config.points
        field_index = points_layer.fields().indexFromName(self.config.units_field)
        return sorted({str(v) for v in points_layer.uniqueValues(field_index) if v not in (None, "")})

    def get_color_table(self) -> dict[str, str]:
        return get_or_create_color_table(self.config.points, self.config.units_field)

    def _propagate_point_unit_to_polygon(self, polygon_feature, unit_text, color_updates=None) -> None:
        """Writes unit_text to polygon_feature's own units_field attribute
        (if the polygon layer has that field yet -- i.e. a full recompute
        has run at least once) and syncs unit colors. Does not touch the
        points layer itself -- callers that need to write/create the point
        (assign_unit) or that already know the point was written elsewhere
        (the incremental engine's points-path, reacting to a commit that
        already happened) do that separately.

        color_updates is passed into sync_unit_colors as an explicit
        override rather than written to points_layer here: the polygon
        layer's renderer hasn't been told about it yet at this point, and
        writing to points_layer first would make sync_unit_colors mistake
        that staleness for a manual Symbology edit on the *polygon* layer
        and let the old, stale color win, reverting the very change just
        made.
        """
        config = self.config
        points_layer = config.points
        units_field = config.units_field
        color_updates = dict(color_updates) if color_updates else {}

        polygons_layer = self.get_polygons_layer()
        poly_field_index = polygons_layer.fields().indexFromName(units_field)
        if poly_field_index != -1:
            was_read_only = polygons_layer.readOnly()
            polygons_layer.setReadOnly(False)
            polygons_layer.startEditing()
            polygons_layer.changeAttributeValue(polygon_feature.id(), poly_field_index, unit_text)
            polygons_layer.commitChanges()
            polygons_layer.setReadOnly(was_read_only)

            sync_unit_colors(
                points_layer,
                polygons_layer,
                units_field,
                explicit_overrides=color_updates,
                style_points=config.auto_color_points,
                style_polygons=config.auto_color_polygons,
            )
            if config.auto_label_polygons:
                enable_default_labels(polygons_layer, units_field)
            if config.auto_label_points:
                enable_default_labels(points_layer, units_field)
        elif color_updates:
            # polygon layer has no units_field yet (map never recomputed) --
            # nothing to sync colors with, but still persist the choice
            write_colors_to_points(points_layer, units_field, "color", color_updates)

    def assign_unit(
        self,
        polygon_feature,
        point_feature,
        click_point,
        unit_text,
        color=None,
        changed_colors=None,
    ) -> None:
        """Writes unit_text to point_feature (or creates a new indicator
        point at click_point if there was none), and -- since only the
        attribute changes, not the polygon geometry -- also writes it
        directly to polygon_feature's own attribute so its color/label
        update immediately without waiting for a full recompute_map()."""
        config = self.config
        points_layer = config.points
        units_field = config.units_field
        click_geom = QgsGeometry.fromPointXY(click_point)

        field_index = points_layer.fields().indexFromName(units_field)

        if not points_layer.isEditable():
            points_layer.startEditing()

        if point_feature is not None:
            points_layer.changeAttributeValue(point_feature.id(), field_index, unit_text)
        else:
            newf = QgsFeature(points_layer.fields())
            newf.setGeometry(click_geom)
            newf[units_field] = unit_text
            points_layer.addFeature(newf)

        points_layer.commitChanges()

        color_updates = dict(changed_colors) if changed_colors else {}
        if color:
            color_updates[unit_text] = color

        self._propagate_point_unit_to_polygon(polygon_feature, unit_text, color_updates)

        self.unitAssigned.emit(unit_text, polygon_feature.id())

        if config.auto_recompute_on_assign_unit:
            self.recompute_map()

    def process_pending_changes(self) -> None:
        """This engine keeps no incremental/topology state, so there is
        nothing to drain -- the GUI's commit-signal nudge (see
        Mappy._rewire_layer_signals) is simply a no-op here. A future
        incremental engine reacts to this instead of requiring the user to
        remember to click "Recompute map"."""

    def invalidate(self) -> None:
        """No incremental state to drop."""

    def validate_topology(self) -> TopologyValidationReport:
        """No topology of its own to drift out of sync."""
        return TopologyValidationReport(in_sync=True)
