from qgis.PyQt.QtCore import QCoreApplication
from qgis.core import QgsProcessingUtils
from qgis.core import QgsProcessingException, QgsFeatureSink
from qgis.core import QgsProcessingAlgorithm


class MappyProcessingAlgorithm(QgsProcessingAlgorithm):
    def copy_output_to_sink(self, parameters, context, layer, oname="OUTPUT"):

        if isinstance(layer, str):
            layer = QgsProcessingUtils.mapLayerFromString(layer, context, False)

        (sink, dest_id) = self.parameterAsSink(
            parameters,
            oname,
            context,
            layer.fields(),
            layer.wkbType(),
            layer.sourceCrs()
        )

        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, oname))

        print(f"SINK {type(sink)}")
        for feature in layer.getFeatures():
            sink.addFeature(feature, QgsFeatureSink.FastInsert)

        # layer = QgsProcessingUtils.mapLayerFromString(dest_id, context, False)
        

        return dest_id

    def tr(self, string):
        """
        Returns a translatable string with the self.tr() function.
        """
        return QCoreApplication.translate('Processing', string)