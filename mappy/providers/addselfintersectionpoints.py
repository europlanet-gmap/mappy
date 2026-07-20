from qgis import processing
from qgis.core import QgsProcessing
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterBoolean
from qgis.core import QgsProcessingParameterFeatureSink
from qgis.core import QgsProcessingParameterVectorLayer

from .MappyProcessingAlgorithm import MappyProcessingAlgorithm


class AddSelfIntersectionPoints(MappyProcessingAlgorithm):
    """
    Produce a new line layer with vertices at each intersection and self-intersection
    """

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterVectorLayer('INPUT', 'Input Lines', types=[QgsProcessing.TypeVectorLine],
                                              defaultValue=None))
        self.addParameter(
            QgsProcessingParameterFeatureSink('OUTPUT', 'Cleaned Lines', type=QgsProcessing.TypeVectorAnyGeometry,
                                              createByDefault=True, supportsAppend=True, defaultValue=None))
        self.addParameter(
            QgsProcessingParameterBoolean('VERBOSE_LOG', 'Verbose logging', optional=True, defaultValue=False))

    def processAlgorithm(self, parameters, context, model_feedback):
        feedback = QgsProcessingMultiStepFeedback(9, model_feedback)
        results = {}
        outputs = {}

        # Add autoincremental field
        alg_params = {
            'FIELD_NAME': 'MAPPY_UUID',
            'GROUP_FIELDS': [''],
            'INPUT': parameters['INPUT'],
            'SORT_ASCENDING': True,
            'SORT_EXPRESSION': '',
            'SORT_NULLS_FIRST': False,
            'START': 0,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['AddAutoincrementalField'] = processing.run('native:addautoincrementalfield', alg_params,
                                                            context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(1)
        if feedback.isCanceled():
            return {}

        # Remove null geometries
        alg_params = {
            'INPUT': outputs['AddAutoincrementalField']['OUTPUT'],
            'REMOVE_EMPTY': False,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['RemoveNullGeometries'] = processing.run('native:removenullgeometries', alg_params, context=context,
                                                         feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}

        # Remove duplicate vertices
        alg_params = {
            'INPUT': outputs['RemoveNullGeometries']['OUTPUT'],
            'TOLERANCE': 1e-06,
            'USE_Z_VALUE': False,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['RemoveDuplicateVertices'] = processing.run('native:removeduplicatevertices', alg_params,
                                                            context=context, feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(3)
        if feedback.isCanceled():
            return {}

        # Check validity
        alg_params = {
            'IGNORE_RING_SELF_INTERSECTION': False,
            'INPUT_LAYER': outputs['RemoveDuplicateVertices']['OUTPUT'],
            'METHOD': 2,
            'VALID_OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['CheckValidity'] = processing.run('qgis:checkvalidity', alg_params, context=context, feedback=feedback,
                                                  is_child_algorithm=True)

        feedback.setCurrentStep(4)
        if feedback.isCanceled():
            return {}

        # Explode lines
        alg_params = {
            'INPUT': outputs['CheckValidity']['VALID_OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ExplodeLines'] = processing.run('native:explodelines', alg_params, context=context, feedback=feedback,
                                                 is_child_algorithm=True)

        feedback.setCurrentStep(5)
        if feedback.isCanceled():
            return {}

        # Split with lines
        alg_params = {
            'INPUT': outputs['ExplodeLines']['OUTPUT'],
            'LINES': outputs['ExplodeLines']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['SplitWithLines'] = processing.run('native:splitwithlines', alg_params, context=context,
                                                   feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(6)
        if feedback.isCanceled():
            return {}

        # Remove Duplicated Segments
        alg_params = {
            'IN_SEGMENTS': outputs['SplitWithLines']['OUTPUT'],
            'THRESHOLD': 1e-06,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['RemoveDuplicatedSegments'] = processing.run('mappy:removeduplicatedsegments', alg_params,
                                                             context=context, feedback=feedback,
                                                             is_child_algorithm=True)

        feedback.setCurrentStep(7)
        if feedback.isCanceled():
            return {}

        # Dissolve
        alg_params = {
            'FIELD': ['MAPPY_UUID'],
            'INPUT': outputs['RemoveDuplicatedSegments']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Dissolve'] = processing.run('native:dissolve', alg_params, context=context, feedback=feedback,
                                             is_child_algorithm=True)

        feedback.setCurrentStep(8)
        if feedback.isCanceled():
            return {}

        # Drop field(s)
        alg_params = {
            'COLUMN': ['MAPPY_UUID'],
            'INPUT': outputs['Dissolve']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['DropFields'] = processing.run('native:deletecolumn', alg_params, context=context, feedback=feedback,
                                               is_child_algorithm=True)

        dest_id = self.copy_output_to_sink(parameters, context, outputs['DropFields']["OUTPUT"], "OUTPUT")

        results['OUTPUT'] = dest_id

        return {"OUTPUT": dest_id}

    def name(self):
        return 'ensureintersectionpoints'

    def displayName(self):
        return 'Add Self Intersection Points'

    def shortHelpString(self):
        return self.tr(
            "Split and regenerate the lines to ensure each self intersection is correctly represented by a point in all the lines")

    def group(self):
        return self.tr('Utils')

    def groupId(self):
        return 'utils'

    def createInstance(self):
        return AddSelfIntersectionPoints()
