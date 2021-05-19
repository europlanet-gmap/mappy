# -*- coding: utf-8 -*-

"""
***************************************************************************
*                                                                         *
*   This program is free software; you can redistribute it and/or modify  *
*   it under the terms of the GNU General Public License as published by  *
*   the Free Software Foundation; either version 2 of the License, or     *
*   (at your option) any later version.                                   *
*                                                                         *
***************************************************************************
"""

from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.core import (QgsProcessing,
                       QgsProcessingException,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterFeatureSink, QgsProcessingParameterDistance, QgsWkbTypes, QgsFeatureSink)
from qgis.core import QgsSpatialIndex

from .MappyProcessingAlgorithm import MappyProcessingAlgorithm


class RemoveDuplicateSegmentsProcessingAlgorithm(MappyProcessingAlgorithm):
    """
    Helper to remove duplicated segments from a line layer
    """
    IN_SEGMENTS = "IN_SEGMENTS"
    THRESHOLD = "THRESHOLD"
    OUTPUT = "OUTPUT"


    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return RemoveDuplicateSegmentsProcessingAlgorithm()

    def name(self):
        return 'removeduplicatedsegments'

    def displayName(self):
        return self.tr('Remove Duplicated Segments')

    def group(self):
        return self.tr('Utils')

    def groupId(self):
        return 'utils'

    def shortHelpString(self):
        return self.tr("""Remove duplicated segments using a threshold""")

    def initAlgorithm(self, config=None):

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.IN_SEGMENTS,
                self.tr('Input Segments)'),
                [QgsProcessing.TypeVectorLine]
            )
        )

        self.addParameter(
            QgsProcessingParameterDistance(
                self.THRESHOLD,
                self.tr('Precision'),
                parentParameterName=self.IN_SEGMENTS,
                defaultValue=1e-6
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Cleaned segments')
            )
        )

    def equal_segments(self, seg1, seg2, threshold=1e-6):
        s1_s, s1_e = seg1.vertices()
        s2_s, s2_e = seg2.vertices()

        if s1_s.distance(s2_s) < threshold and s1_e.distance(s2_e) < threshold:
            return True

        if s1_s.distance(s2_e) < threshold and s1_e.distance(s2_s) < threshold:
            return True
        else:
            return False

    def processAlgorithm(self, parameters, context, feedback):
        segments_layer = self.parameterAsLayer(
            parameters,
            self.IN_SEGMENTS,
            context
        )

        t = self.parameterAsDouble(parameters, self.THRESHOLD, context)

        index = QgsSpatialIndex()  # Spatial index

        index.addFeatures(segments_layer.getFeatures())

        todel = []
        for ln in segments_layer.getFeatures():
            index.deleteFeature(ln)

            cands = index.intersects(ln.geometry().boundingBox())

            ln1 = ln.geometry()
            for ca in cands:
                totest = segments_layer.getFeature(ca)
                ln2 = totest.geometry()

                are_equal = self.equal_segments(ln1, ln2, t)
                if are_equal:
                    index.deleteFeature(totest)
                    todel.append(ca)

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            segments_layer.fields(),  # QgsFields() for an empty fields list or source_lines.fields()
            QgsWkbTypes.MultiLineString,
            segments_layer.sourceCrs()
        )

        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        for feature in segments_layer.getFeatures():
            if feature.id() not in todel:
                sink.addFeature(feature, QgsFeatureSink.FastInsert)

        return {"OUTPUT": dest_id}
