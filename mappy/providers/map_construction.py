from qgis import processing
from qgis.core import QgsProcessingParameterBoolean, QgsProcessingUtils, QgsApplication
from qgis.core import (QgsProcessing,
                       QgsProcessingException,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterFeatureSink, QgsProcessingParameterDistance, QgsWkbTypes, QgsFeatureSink)

from qgis.PyQt.QtGui import QIcon

from .MappyProcessingAlgorithm import MappyProcessingAlgorithm


class MapConstructionProcessingAlgorithm(MappyProcessingAlgorithm):
    """
    Generate a new polygonal map from lines and points
    """

    def icon(self):
        return QIcon(':/plugins/qgismappy/icons/mapconstruction.png')

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    IN_LINES = 'IN_LINES'
    IN_POINTS = 'IN_POINTS'
    # CAT_FIELD = "CAT_FIELD"
    EXT_DISTANCE = "EXT_DISTANCE"
    OUTPUT = 'OUTPUT'
    DROP_UNMATCHED = "DROP_UNMATCHED"
    UNMATCHED = "UNMATCHED"

    # MAIN_FIELD = "MAIN_FIELD"

    def createInstance(self):
        return MapConstructionProcessingAlgorithm()

    def name(self):
        return 'mapconstruction'

    def displayName(self):
        return self.tr('Map Construction (lines and points to polygons)')

    def group(self):
        return self.tr('Mapping')

    def groupId(self):
        return 'mapping'

    def shortHelpString(self):
        return self.tr(
            "Generate consistent polygonal layers starting from limits and indicator points. This tool execute in sequences the following operations for you:\n"
            "- removes null geometries\n"
            "- remove duplicated vertices\n"
            "- extend lines to grant intersection\n"
            "- polygonize the lines\n"
            "- assign fields to polygons using the points layer (via a spatial join)\n"
            "The output is a polygonal layer with granted topological consistency (no overalps, holes, duplicated geometries etc), perfect for a geological map.")

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.IN_LINES,
                self.tr('Input Lines'),
                [QgsProcessing.TypeVectorLine]
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.IN_POINTS,
                self.tr('Input Points'),
                [QgsProcessing.TypeVectorPoint]
            )
        )

        self.addParameter(
            QgsProcessingParameterDistance(self.EXT_DISTANCE, self.tr('Extend Lines Distance'), defaultValue=0.0,
                                           minValue=0.0, optional=True, parentParameterName=self.IN_LINES))

        self.addParameter(
            QgsProcessingParameterBoolean(self.DROP_UNMATCHED, self.tr("Drop unassigned polygons"), defaultValue=False))

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Constructed Map')
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.UNMATCHED,
                self.tr('Unmatched Polygons'),
                optional=True,
                defaultValue=None,
                createByDefault=False

            )
        )

    def checkSavedState(self, parameters, context, name):
        layer = self.parameterAsLayer(parameters,
                                      name,
                                      context)

        if layer.isModified():
            import os
            basename = os.path.splitext(os.path.basename(layer.source()))[0]
            raise QgsProcessingException(
                f"Input layer {basename} for input parameter {name} was modified but not saved. Please be sure to save your edits before generating the polygons")

    def matchAlgo(self, name):
        reg = QgsApplication.processingRegistry()
        found = reg.algorithmById(name)
        if found:
            return name
        else:
            return "qgis:" + name.split(":")[1]

    def processAlgorithm(self, parameters, context, feedback):
        pname = self.matchAlgo("native:polygonize")
        spiname = self.matchAlgo("native:createspatialindex")
        jname = self.matchAlgo("native:joinattributesbylocation")

        source_lines = self.parameterAsSource(
            parameters,
            self.IN_LINES,
            context
        )

        source_pts = self.parameterAsSource(
            parameters,
            self.IN_POINTS,
            context
        )

        self.checkSavedState(parameters, context, self.IN_POINTS)
        self.checkSavedState(parameters, context, self.IN_LINES)

        # field = self.parameterAsString(parameters, self.MAIN_FIELD, context)
        distance = self.parameterAsDouble(parameters, self.EXT_DISTANCE, context)

        if source_lines is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.IN_LINES))

        if source_pts is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.IN_POINTS))

        if feedback.isCanceled():
            return {}

        nonnull = processing.run("native:removenullgeometries",
                                 {'INPUT': parameters[self.IN_LINES],
                                  'OUTPUT': 'memory:', 'REMOVE_EMPTY': True}, context=context,
                                 feedback=feedback, is_child_algorithm=True)

        nodups = processing.run("native:removeduplicatevertices",
                                {'INPUT': nonnull["OUTPUT"],
                                 'OUTPUT': 'memory:', "TOLERANCE": 1e-06,
                                 'USE_Z_VALUE=': False}, context=context,
                                feedback=feedback, is_child_algorithm=True)

        extended_layer = processing.run("native:extendlines",
                                        {'END_DISTANCE': distance,
                                         'INPUT': nodups["OUTPUT"],
                                         'OUTPUT': 'memory:', 'START_DISTANCE': distance}, context=context,
                                        feedback=feedback, is_child_algorithm=True)

        feedback.pushInfo(f"polygonizing")

        polygonized_layer = processing.run(pname, {
            'INPUT': extended_layer["OUTPUT"],
            "OUTPUT": QgsProcessingUtils.generateTempFilename("polygonize.gpkg")
        }, context=context, feedback=feedback, is_child_algorithm=True)

        feedback.pushInfo(f"output of polygonize at {polygonized_layer['OUTPUT']}")
        feedback.pushInfo(f"processing {type(processing)}")

        feedback.pushInfo(f"generating spatial index")

        polygons_wspatial = processing.run(spiname,
                                           {"INPUT": polygonized_layer["OUTPUT"]}, is_child_algorithm=True,
                                           feedback=feedback)

        points_wspatial = processing.run(spiname,
                                         {"INPUT": parameters[self.IN_POINTS]}, is_child_algorithm=True,
                                         feedback=feedback)

        points_layer = self.parameterAsLayer(parameters, self.IN_POINTS, context)
        feedback.pushInfo(str(points_layer))

        drop = self.parameterAsBool(parameters, self.DROP_UNMATCHED, context)

        feedback.pushInfo(f"joining")

        # [2021 - 06 - 09 17: 0
        # 9: 58] processing.run("native:joinattributesbylocation", {'INPUT': '/home/luca/geomap.gpkg|layername=final_map',
        #                                                           'JOIN': '/home/luca/Code/mappy.git/demo_data/mars/vectors_map.gpkg|layername=geo_units',
        #                                                           'PREDICATE': [5], 'JOIN_FIELDS': [], 'METHOD': 0,
        #                                                           'DISCARD_NONMATCHING': False, 'PREFIX': '',
        #                                                           'OUTPUT': 'TEMPORARY_OUTPUT',
        #                                                           'NON_MATCHING': 'TEMPORARY_OUTPUT'})




        pars = {'DISCARD_NONMATCHING': drop,
                'INPUT': polygonized_layer["OUTPUT"],
                'JOIN': parameters[self.IN_POINTS],
                'JOIN_FIELDS': [],
                'METHOD': 1,
                'OUTPUT': 'TEMPORARY_OUTPUT',
                # 'NON_MATCHING': 'TEMPORARY_OUTPUT',
                'PREDICATE': [0],
                'PREFIX': ''}

        if self.UNMATCHED in parameters.keys():
            pars["NON_MATCHING"] = 'TEMPORARY_OUTPUT'

        joined_layer = processing.run(jname,
                                      pars
                                      , context=context, feedback=feedback, is_child_algorithm=False)
        # feedback.pushInfo(f"layer is {joined_layer}")




        dest_id = self.copy_output_to_sink(parameters, context, joined_layer["OUTPUT"], self.OUTPUT)

        # (sink, dest_id) = self.parameterAsSink(
        #     parameters,
        #     self.OUTPUT,
        #     context,
        #     joined_layer["OUTPUT"].fields(),  # QgsFields() for an empty fields list or source_lines.fields()
        #     QgsWkbTypes.Polygon,
        #     source_lines.sourceCrs()
        # )
        #
        # # feedback.pushInfo(f"destination {dest_id}")
        # #
        # # # If sink was not created, throw an exception to indicate that the algorithm
        # # # encountered a fatal error. The exception text can be any string, but in this
        # # # case we use the pre-built invalidSinkError method to return a standard
        # # # helper text for when a sink cannot be evaluated
        # if sink is None:
        #     raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))
        #
        # #
        # for feature in joined_layer["OUTPUT"].getFeatures():
        #     sink.addFeature(feature, QgsFeatureSink.FastInsert)

        out = {self.OUTPUT: dest_id}

        if self.UNMATCHED in parameters.keys():
            unmatched = joined_layer["NON_MATCHING"]
            id = self.copy_output_to_sink(parameters, context, unmatched, self.UNMATCHED)
            out[self.UNMATCHED] = id
        # outlayer = self.parameterAsLayer(parameters, self.OUTPUT, context)
        # feedback.pushInfo("->"+str(outlayer))

        # from qgismappy.qgismappy_dockwidget import resetCategoriesIfNeeded
        # resetCategoriesIfNeeded(sink, field)

        # Return the results of the algorithm. In this case our only result is
        # the feature sink which contains the processed features, but some
        # algorithms may return multiple feature sinks, calculated numeric
        # statistics, etc. These should all be included in the returned
        # dictionary, with keys matching the feature corresponding parameter
        # or output names.
        return out
