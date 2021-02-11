# -*- coding: utf-8 -*-
"""
/***************************************************************************
 MappyDockWidget
                                 A QGIS plugin
 helper for consistent goelogical map generation
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2020-06-24
        git sha              : $Format:%H$
        copyright            : (C) 2020 by Luca Penasa, PLANMAP and GMAP team
        email                : luca.penasa@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
import os
from typing import List, Tuple

from qgis.PyQt import QtGui, QtWidgets, uic, QtCore
from qgis.PyQt.QtCore import pyqtSignal, QObject
from qgis.PyQt.QtWidgets import QFileDialog, QLineEdit, QCheckBox
from qgis.core import QgsCategorizedSymbolRenderer
from qgis.gui import QgsMapLayerComboBox, QgsFieldComboBox, QgsDoubleSpinBox
from qgis.core import QgsMessageLog, QgsProject, QgsMapLayerProxyModel, QgsSymbol, QgsRendererCategory, \
    QgsSingleSymbolRenderer, QgsVectorLayer

import mappy.geom_ops

import logging as log

from .log_helper import *

from pathlib import Path

from mappy.conversions import read_layer

# from qgis.gui import QgsMapLayerComboBox

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'qgismappy_dockwidget_base.ui'))

import enum


class MODE(enum.Enum):
    CONSTRUCT = 0
    DECONSTRUCT = 1


# describe the mapping between the qt-objects and the arguments of the method call
mappy_construct_args_mapping = [("lines", "lines"),
                                ("points", "points"),
                                ("units_field", "units_field"),
                                ("auto_extend", "auto_extend"),
                                ("output", "output"),
                                ("layer_name", "layer_name"),
                                ("overwrite", "overwrite"),
                                ("debug", "debug")]

mappy_deconstruct_args_mapping = [("de_map_layer", "polygons"),
                                  ("de_units_field", "units_field"),
                                  ("de_output_gpkg", "output_gpkg"),
                                  ("de_lines_layer", "lines_layer_name"),
                                  ("de_points_layer", "points_layer_name")]


def resetCategoriesIfNeeded(layer, units_field, unassigned=True):
    prev_rend = layer.renderer()

    if not isinstance(prev_rend, QgsCategorizedSymbolRenderer):
        renderer = QgsCategorizedSymbolRenderer(units_field)
        layer.setRenderer(renderer)
    else:
        renderer = prev_rend

    prev_cats = renderer.categories()
    id = layer.fields().indexFromName(units_field)
    uniques = list(layer.uniqueValues(id))
    uniques_clean = [u for u in uniques if u is not None]

    values = sorted(uniques_clean)

    if None in uniques and unassigned:
        values.append(None)

    categories = []

    for current, value in enumerate(values):

        already_in = False
        for prev in prev_cats:
            if prev.value() == value:
                already_in = True
                continue

        if not already_in:
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            category = QgsRendererCategory(value, symbol, str(value))
            categories.append(category)

    for cat in categories:
        renderer.addCategory(cat)

    # layer.setRenderer(renderer)
    layer.rendererChanged.emit()
    layer.dataSourceChanged.emit()

    layer.triggerRepaint()




class MappyDockWidget(QtWidgets.QDockWidget, FORM_CLASS):
    closingPlugin = pyqtSignal()

    def __init__(self, parent=None):
        """Constructor."""
        super(MappyDockWidget, self).__init__(parent)
        # Set up the user interface from Designer.
        # After setupUI you can access any designer object by doing
        # self.<objectname>, and you can use autoconnect slots - see
        # http://doc.qt.io/qt-5/designer-using-a-ui-file.html
        # #widgets-and-dialogs-with-auto-connect
        self.setupUi(self)

        self.on_tab_currentChanged()

        # self.button_execute.clicked.connect(self.execute)
        self.log_message("Initializing Mappy")
        self.initConstruct()
        self.initDeconstruct()

    def getUserHome(self):
        return str(Path.home())

    def initConstruct(self):
        self.lines.setFilters(QgsMapLayerProxyModel.LineLayer)
        self.points.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.save_as.setCheckable(False)
        self.output.setText(f"{self.getUserHome()}/geomap.gpkg")

    def initDeconstruct(self):
        self.de_map_layer.setFilters(QgsMapLayerProxyModel.PolygonLayer)
        self.de_output_gpkg.setText(f"{self.getUserHome()}/geomap.gpkg")

    def log_message(self, message, level=0, notifyUser=True):
        QgsMessageLog.logMessage(message, "Mappy", level, notifyUser)

    # slots:

    def on_tab_currentChanged(self):
        self.current_mode = MODE(self.tab.currentIndex())
        log.debug(f"current mode {self.current_mode}")

    def on_points_layerChanged(self, layer):
        self.units_field.setLayer(layer)

    def on_de_map_layer_layerChanged(self, layer):
        self.de_units_field.setLayer(layer)

    def closeEvent(self, event):
        self.closingPlugin.emit()
        event.accept()

    @QtCore.pyqtSlot()
    def on_save_as_clicked(self):
        self.log_message("save as clicked", notifyUser=1)
        filename, ext = QFileDialog.getSaveFileName(self, "Select output file ", "", '*.gpkg')
        if filename[-5:] == ".gpkg":
            filename = filename[:-5]

        self.log_message(filename)
        self.log_message(ext)
        if filename:
            self.output.setText(filename + ext[1:])

    @QtCore.pyqtSlot()
    def on_de_save_as_clicked(self):
        self.log_message("save as clicked", notifyUser=1)
        filename, ext = QFileDialog.getSaveFileName(self, "Select output file ", "", '*.gpkg')
        if filename[-5:] == ".gpkg":
            filename = filename[:-5]

        self.log_message(filename)
        self.log_message(ext)
        if filename:
            self.de_output_gpkg.setText(filename + ext[1:])

    # def update_layer_selection(self):
    # layers = [layer for layer in QgsProject.instance().mapLayers().values()]
    # self.log_message(str(layers))

    # def on_pushButton_execute_triggered(self):
    #     print(" triggered")

    @QtCore.pyqtSlot()
    def on_execute_clicked(self):
        log.debug(" execution clicked")

        log.debug(f"executing, mode is {self.current_mode}")

        if self.current_mode == MODE.CONSTRUCT:
            mapping = mappy_construct_args_mapping
            args = self.readParametersToDict(mapping)
            log.debug(f"collected args: {args}")
            self.execute_construct(args)

        elif self.current_mode == MODE.DECONSTRUCT:
            mapping = mappy_deconstruct_args_mapping
            args = self.readParametersToDict(mapping)
            log.debug(f"collected args: {args}")
            self.execute_deconstruct(args)

        else:
            log.critical("cannot proceed")
            return

    def findLayer(self, gpkg, layer_name):
        gpkg = os.path.abspath(gpkg)

        gpkg += f"|layername={layer_name}"
        layers = QgsProject.instance().mapLayers()

        for name, layer in layers.items():
            luri = layer.dataProvider().dataSourceUri()

            if luri == gpkg:
                return layer

        return None

    @staticmethod
    def readWidgetContent(widget):
        if isinstance(widget, QgsMapLayerComboBox):
            return read_layer(widget.currentLayer())

        elif isinstance(widget, QgsFieldComboBox):
            return str(widget.currentField())

        elif isinstance(widget, QgsDoubleSpinBox):
            return widget.value()

        elif isinstance(widget, QLineEdit):
            return widget.text()

        elif isinstance(widget, QCheckBox):
            return bool(widget.checkState())

        else:
            log.error(f"reading not supported for widget of type {type(widget)}. Consider adding the case to "
                      f"readWidgetContent")

    def readParametersToDict(self, mapping: List[Tuple]):
        out = {}
        for widget_name, parameter_name in mapping:
            value = self.readWidgetContent(getattr(self, widget_name))
            out[parameter_name] = value

        return out

    def addLayerFromGeopackage(self, gpkgfile, layer_name, categories_field=None):
        gpkgfile += f"|layername={layer_name}"
        l = QgsVectorLayer(gpkgfile)
        l.setName(layer_name)
        QgsProject.instance().addMapLayer(l)

        if categories_field is not None:
            self.resetCategoriesIfNeeded(l, categories_field)

        # l.triggerRepaint()
        # l.dataChanged.emit()  # or dataSourceChanged?
        # l.dataSourceChanged.emit()
        return l

    def execute_construct(self, args):
        try:
            output = mappy.geom_ops.mappy_construct(**args)  # this will write to the geopackage
        except Exception as e:
            log.debug(" error occured")
            log.error(e)
            traceback.print_exc()
            return

        # outgpkg = outgpkg[:-5]
        layer_name = args["layer_name"]
        outgpkg = args["output"]
        units_field = args["units_field"]

        log.info(f"loading layer {outgpkg}")

        l = self.findLayer(outgpkg, layer_name)  # check if already loaded
        if l:
            log.info("Layer already loaded, just updating categories")

        else:
            l = self.addLayerFromGeopackage(outgpkg, layer_name, units_field)

        self.resetCategoriesIfNeeded(l, units_field)

    def execute_deconstruct(self, args):
        log.info("executing deconstruct")
        try:
            log.debug(" trying")
            for a, b in args.items():
                log.debug(f"-->  {type(b)}")
            output = mappy.geom_ops.mappy_deconstruct(**args)  # this will write to the geopackage
            log.debug(" trying done")
        except Exception as e:
            log.error(" error occured")
            log.error(e)
            import traceback
            traceback.print_exc()
            return

        # outgpkg = outgpkg[:-5]
        # polygons, units_field, output_gpkg, lines_layer_name, points_layer_name

        # layer_name = args["layer_name"]
        outgpkg = args["output_gpkg"]

        for layer in [args["lines_layer_name"], args["points_layer_name"]]:
            l = self.findLayer(outgpkg, layer)  # check if already loaded
            if l:
                log.info("Layer already loaded, just updating categories")

            else:
                l = self.addLayerFromGeopackage(outgpkg, layer, None)

        self.resetCategoriesIfNeeded(l, args["units_field"])
        # units_field = args["units_field"]
        #
        # log.info(f"loading layer {outgpkg}")
        #
        # l = self.findLayer(outgpkg, layer_name)  # check if already loaded
        # if l:
        #     log.info("Layer already loaded, just updating categories")
        #
        # else:
        #     l = self.addLayerFromGeopackage(outgpkg, layer_name, units_field)
        #
        # self.resetCategoriesIfNeeded(l, units_field)

    def resetCategoriesIfNeeded(self, layer, units_field):

        prev_rend = layer.renderer()

        if not isinstance(prev_rend, QgsCategorizedSymbolRenderer):
            renderer = QgsCategorizedSymbolRenderer(units_field)
            layer.setRenderer(renderer)
        else:
            renderer = prev_rend

        prev_cats = renderer.categories()

        id = layer.fields().indexFromName(units_field)
        uniques = list(layer.uniqueValues(id))
        uniques = [u for u in uniques if u is not None]

        values = sorted(uniques)
        categories = []

        for current, value in enumerate(values):

            already_in = False
            for prev in prev_cats:
                if prev.value() == value:
                    already_in = True
                    continue

            if not already_in:
                symbol = QgsSymbol.defaultSymbol(layer.geometryType())
                category = QgsRendererCategory(value, symbol, str(value))
                categories.append(category)

        for cat in categories:
            renderer.addCategory(cat)

        # layer.setRenderer(renderer)
        layer.rendererChanged.emit()
        layer.dataSourceChanged.emit()

        layer.triggerRepaint()
