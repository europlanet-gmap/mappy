"""
Model exported as python.
Name : test_import
Group :
With QGIS : 32601
"""

from qgis.core import QgsApplication
from qgis.core import QgsProcessing
from qgis.core import QgsProcessingException
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterVectorLayer
from qgis.core import QgsProcessingParameterDistance
from qgis.core import QgsProcessingParameterFeatureSink
from qgis import processing
from mappy.providers.MappyProcessingAlgorithm import MappyProcessingAlgorithm

# GRASS is not always available -- depending on the OS/QGIS install, its
# provider can be present but disabled, or its own PATH/GRASS_PREFIX env
# vars can be missing even when GRASS itself is installed (a known issue on
# macOS). Checked before running rather than letting v.to.lines fail with a
# generic "algorithm not found" error deep inside processing.run().
GRASS_LINES_ALGORITHM = "grass7:v.to.lines"
GRASS_UNAVAILABLE_MESSAGE = (
    "This tool requires the GRASS provider (v.to.lines), which isn't available in this QGIS "
    "installation.\n\n"
    "- Check that the GRASS provider is enabled under Settings > Options > Processing > Providers > GRASS.\n"
    "- Make sure GRASS itself is installed and on your PATH -- on macOS this sometimes needs launching QGIS "
    "with GRASS_PREFIX/PATH set explicitly, e.g.:\n"
    "    export GRASS_PREFIX=/opt/local/lib/grass84\n"
    "    export PATH=$GRASS_PREFIX/bin:$PATH\n"
    "    open /Applications/QGIS.app"
)


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
        if QgsApplication.processingRegistry().algorithmById(GRASS_LINES_ALGORITHM) is None:
            raise QgsProcessingException(GRASS_UNAVAILABLE_MESSAGE)

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
