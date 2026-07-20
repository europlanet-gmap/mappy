from qgis.PyQt.QtCore import QCoreApplication
from qgis._core import QgsProcessingParameterDistance, QgsProcessingParameterFeatureSink, QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterBoolean, QgsProperty
from qgis.core import (QgsProcessing,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterNumber,
                       QgsProcessingParameterField)

from qgis.utils import iface

from qgis.PyQt.QtGui import QIcon
from qgis import processing


from .MappyProcessingAlgorithm import MappyProcessingAlgorithm
from ..mappy_utils import matchAlgo


class LabelPointsFromPolygonsProcessingAlgorithm(MappyProcessingAlgorithm):
    """
    From a polygonal layer to labelled points
    """

    def icon(self):
        return QIcon(':/plugins/qgismappy/icons/create_points.png')

    INPUT = "IN_LAYER"
    TOLERANCE = "TOLERANCE"
    OUTPUT="OUTPUT"

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return LabelPointsFromPolygonsProcessingAlgorithm()

    def name(self):
        return 'labelspointsfrompolygons'

    def displayName(self):
        return self.tr('Automatic create label points from existing polygons')

    def group(self):
        return self.tr('Mapping')

    def groupId(self):
        return 'mapping'

    def shortHelpString(self):
        return self.tr("""Generate points suitable for labelling starting from a polygonal layer""")

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT,
                self.tr('Input Polygons'),
                [QgsProcessing.TypeVectorPolygon]
            )
        )

        self.addParameter(
            QgsProcessingParameterDistance(
                self.TOLERANCE,
                self.tr("Tolerance"),
                defaultValue=0.01
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Labelled Points'),
                type=QgsProcessing.TypeVectorPoint,
                createByDefault=True, supportsAppend=True,
                defaultValue=None
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        feedback = QgsProcessingMultiStepFeedback(2, feedback)


        polygons_layer = self.parameterAsLayer(
            parameters,
            self.INPUT,
            context
        )

        tolerance = self.parameterAsDouble(parameters, self.TOLERANCE, context)

        step_pars = dict(context=context,
                         feedback=feedback,
                         is_child_algorithm=True)

        # A fixed TOLERANCE that's too coarse relative to a thin/complex
        # polygon can make native:poleofinaccessibility return a point
        # outside the polygon entirely (the search never subdivides finely
        # enough to find a properly interior cell). Cap it per-feature to a
        # small fraction of that feature's own bounding-box size, so the
        # tolerance is always sensible relative to the shape it's computed
        # for, regardless of how coarse the caller-supplied value is.
        capped_tolerance = QgsProperty.fromExpression(
            f"min({tolerance}, max(min(x_max($geometry) - x_min($geometry), "
            f"y_max($geometry) - y_min($geometry)) * 0.001, 0.000001))"
        )

        pars = {'INPUT':polygons_layer,
                'TOLERANCE':capped_tolerance,
                'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT}

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}
        out = processing.run("native:poleofinaccessibility", pars, **step_pars
                             )

        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}
        pars = {
            'INPUT': out["OUTPUT"],
            'COLUMN': ['dist_pole'], 'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT}
        out = processing.run(matchAlgo("native:deletecolumn"), pars, **step_pars )


        id = self.copy_output_to_sink(parameters, context, out["OUTPUT"])

        return {"OUTPUT": id}
