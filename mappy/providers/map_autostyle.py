from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import QgsProcessingParameterBoolean
from qgis.core import (QgsProcessing,
                       QgsProcessingParameterFeatureSource,
                       QgsProcessingParameterField)


from qgis.utils import iface

from qgis.PyQt.QtGui import QIcon

from ..utils import resetCategoriesIfNeeded
from .MappyProcessingAlgorithm import MappyProcessingAlgorithm


class MapAutoStyleProcessingAlgorithm(MappyProcessingAlgorithm):
    """
    Helper to assign categorized style to a polygonal layer
    """

    def icon(self):
        return QIcon(':/plugins/qgismappy/icons/mapstyle.png')


    IN_LAYER = "IN_LAYER"
    CAT_FIELD = "CAT_FIELD"
    STYLE_UNASSIGNED = "STYLE_UNASSIGNED"

    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return MapAutoStyleProcessingAlgorithm()

    def name(self):
        return 'mapautostyle'

    def displayName(self):
        return self.tr('Map Automatic Styling')

    def group(self):
        return self.tr('Style')

    def groupId(self):
        return 'style'



    def shortHelpString(self):
        return self.tr("""Generate or update styling for a polygon layer created by mappy's map generation tool""")


    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.IN_LAYER,
                self.tr('Input Polygons'),
                [QgsProcessing.TypeVectorPolygon, QgsProcessing.TypeVectorLine]
            )
        )

        self.addParameter(
            QgsProcessingParameterField(
                self.CAT_FIELD,
                self.tr('Units field in point layer'),
                parentLayerParameterName = self.IN_LAYER,
                optional=False
            )
        )

        self.addParameter(
            QgsProcessingParameterBoolean(
                self.STYLE_UNASSIGNED,
                self.tr('Create category also for unassigned polygons'),
                defaultValue=True, optional=False
            )
        )


    def processAlgorithm(self, parameters, context, feedback):
        polygons_layer = self.parameterAsLayer(
            parameters,
            self.IN_LAYER,
            context
        )

        fieldname = self.parameterAsString(parameters, self.CAT_FIELD, context)
        unassigned = self.parameterAsBool(parameters, self.STYLE_UNASSIGNED, context)
        feedback.pushInfo(f"field used is {fieldname}")

        from ..utils import resetCategoriesIfNeeded
        resetCategoriesIfNeeded(polygons_layer, fieldname, unassigned=unassigned)
        return {}

