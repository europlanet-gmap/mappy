from qgis._core import QgsCoordinateReferenceSystem
from qgis.core import (QgsProcessingException,
                       QgsProcessingParameterRasterLayer)

from .MappyProcessingAlgorithm import MappyProcessingAlgorithm


class RemoveScalingFromCrs(MappyProcessingAlgorithm):
    INPUT = 'INPUT'
    OUTPUT = 'OUTPUT'

    def createInstance(self):
        return RemoveScalingFromCrs()

    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'fix_ode_ctx_crs'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr('Remove Scaling From CRS definition')

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.tr('Fixies')

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'fixies'

    def shortHelpString(self):
        """
        Returns a localised short helper string for the algorithm. This string
        should provide a basic description about what the algorithm does and the
        parameters and outputs associated with it..
        """
        return self.tr("Remove Scaling from the CRS definition of input layer (i.e. proj4 +k value)")

    def initAlgorithm(self, config=None):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties.
        """

        # We add the input vector features source. It can have any kind of
        # geometry.
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.INPUT,
                self.tr('Input layer')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """

        source = self.parameterAsLayer(
            parameters,
            self.INPUT,
            context
        )

        feedback.pushInfo(f"source {source}")

        if source is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT))

        curcrs = source.crs().toProj()
        import re
        mm = re.compile("\+k.*")

        newcrs = [c for c in curcrs.split(" ") if not mm.match(c)]

        out = " ".join(newcrs)

        feedback.pushInfo(f" Starting crs: {curcrs}")
        feedback.pushInfo(f" cleaned crs: {out}")

        newcrs = QgsCoordinateReferenceSystem()
        status = newcrs.createFromProj(out)

        feedback.pushInfo(f" cleaned crs 2: stat {status} : {newcrs}")
        source.setCrs(newcrs)

        return {}
