"""
Model exported as python.
Name : test_import
Group :
With QGIS : 32601
"""

from qgis.core import QgsProcessing
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterVectorLayer
from qgis.core import QgsProcessingParameterDistance
from qgis.core import QgsProcessingParameterFeatureSink
from qgis import processing
from mappy.providers.MappyProcessingAlgorithm import MappyProcessingAlgorithm


class ImportPolgonalMap(MappyProcessingAlgorithm):
    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterVectorLayer(
                "input_polygonal_layer", "Input Polygonal Layer", types=[QgsProcessing.TypeVectorPolygon], defaultValue=None
            )
        )
        self.addParameter(
            QgsProcessingParameterDistance(
                "simplify_tolerance",
                "Simplify tolerance",
                parentParameterName="input_polygonal_layer",
                minValue=0,
                defaultValue=0.0001,
            )
        )
        self.addParameter(
            QgsProcessingParameterDistance(
                "vinogr_snap_tolerance_1__no_snap",
                "v.in.ogr snap tolerance (-1 = no snap)",
                parentParameterName="input_polygonal_layer",
                minValue=-1,
                maxValue=1.79769e308,
                defaultValue=1e-06,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                "Points",
                "Points",
                type=QgsProcessing.TypeVectorPoint,
                createByDefault=True,
                supportsAppend=True,
                defaultValue=None,
            )
        )
        self.addParameter(
            QgsProcessingParameterFeatureSink(
                "Contacts",
                "Contacts",
                type=QgsProcessing.TypeVectorLine,
                createByDefault=True,
                supportsAppend=True,
                defaultValue=None,
            )
        )

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(3, model_feedback)
        results = {}
        outputs = {}

        # Automatic create label points from existing polygons
        alg_params = {"IN_LAYER": parameters["input_polygonal_layer"], "TOLERANCE": 0.0001, "OUTPUT": parameters["Points"]}
        outputs["AutomaticCreateLabelPointsFromExistingPolygons"] = processing.run(
            "mappy:labelspointsfrompolygons", alg_params, context=context, feedback=feedback, is_child_algorithm=True
        )
        results["Points"] = outputs["AutomaticCreateLabelPointsFromExistingPolygons"]["OUTPUT"]

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}

        # v.to.lines
        alg_params = {
            "GRASS_MIN_AREA_PARAMETER": 0.0001,
            "GRASS_OUTPUT_TYPE_PARAMETER": 0,  # auto
            "GRASS_REGION_PARAMETER": None,
            "GRASS_SNAP_TOLERANCE_PARAMETER": parameters["vinogr_snap_tolerance_1__no_snap"],
            "GRASS_VECTOR_DSCO": "",
            "GRASS_VECTOR_EXPORT_NOCAT": False,
            "GRASS_VECTOR_LCO": "",
            "input": parameters["input_polygonal_layer"],
            "method": 0,  # delaunay
            "output": QgsProcessing.TEMPORARY_OUTPUT,
        }
        outputs["Vtolines"] = processing.run(
            "grass7:v.to.lines", alg_params, context=context, feedback=feedback, is_child_algorithm=True
        )

        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}

        # Simplify
        alg_params = {
            "INPUT": outputs["Vtolines"]["output"],
            "METHOD": 0,  # Distance (Douglas-Peucker)
            "TOLERANCE": parameters["simplify_tolerance"],
            "OUTPUT": parameters["Contacts"],
        }
        outputs["Simplify"] = processing.run(
            "native:simplifygeometries", alg_params, context=context, feedback=feedback, is_child_algorithm=True
        )

        results["Contacts"] = outputs["Simplify"]["OUTPUT"]
        return results

    def name(self):
        return "importpolygons"

    def displayName(self):
        return "Import Polygonal Map"

    def group(self):
        return "Mapping"

    def groupId(self):
        return "mapping"

    def createInstance(self):
        return ImportPolgonalMap()

    def shortHelpString(self):
        return self.tr("Import an existent polygonal map")
