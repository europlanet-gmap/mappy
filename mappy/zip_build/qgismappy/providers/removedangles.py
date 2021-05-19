"""
Model exported as python.
Name : extract_clean_contacts
Group : mappy
With QGIS : 31802
"""
from qgis.PyQt.QtGui import QIcon
from qgis import processing
from qgis.core import QgsProcessing
from qgis.core import QgsProcessingMultiStepFeedback
from qgis.core import QgsProcessingParameterBoolean
from qgis.core import QgsProcessingParameterDefinition
from qgis.core import QgsProcessingParameterDistance
from qgis.core import QgsProcessingParameterFeatureSink
from qgis.core import QgsProcessingParameterVectorLayer

from .MappyProcessingAlgorithm import MappyProcessingAlgorithm

class RemoveDangles(MappyProcessingAlgorithm):

    def initAlgorithm(self, config=None):
        self.addParameter(
            QgsProcessingParameterDistance('Extenddistance', 'Extend distance', parentParameterName='copntacts',
                                           minValue=0, defaultValue=None))
        param = QgsProcessingParameterDistance('PrecisionjoinBuffer', 'Precision join Buffer', optional=True,
                                               parentParameterName='copntacts', minValue=1e-16, defaultValue=0.001)
        param.setFlags(param.flags() | QgsProcessingParameterDefinition.FlagAdvanced)
        self.addParameter(param)
        self.addParameter(
            QgsProcessingParameterVectorLayer('contacts', 'contacts', types=[QgsProcessing.TypeVectorLine],
                                              defaultValue=None))
        self.addParameter(
            QgsProcessingParameterVectorLayer('polygonized', 'polygonized', types=[QgsProcessing.TypeVectorPolygon],
                                              defaultValue=None))
        self.addParameter(QgsProcessingParameterFeatureSink('OUTPUT', 'Clean Contacts',
                                                            type=QgsProcessing.TypeVectorAnyGeometry,
                                                            createByDefault=True, supportsAppend=True,
                                                            defaultValue=None))
        self.addParameter(
            QgsProcessingParameterBoolean('VERBOSE_LOG', 'Verbose logging', optional=True, defaultValue=False))

    def processAlgorithm(self, parameters, context, model_feedback):
        # Use a multi-step feedback, so that individual child algorithm progress reports are adjusted for the
        # overall progress through the model
        feedback = QgsProcessingMultiStepFeedback(14, model_feedback)
        results = {}
        outputs = {}

        # Add autoincremental field
        alg_params = {
            'FIELD_NAME': 'MAPPY_UUID',
            'GROUP_FIELDS': [''],
            'INPUT': parameters['contacts'],
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

        # Polygons to lines
        alg_params = {
            'INPUT': parameters['polygonized'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['PolygonsToLines'] = processing.run('native:polygonstolines', alg_params, context=context,
                                                    feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(2)
        if feedback.isCanceled():
            return {}

        # Extend lines
        alg_params = {
            'END_DISTANCE': parameters['Extenddistance'],
            'INPUT': outputs['AddAutoincrementalField']['OUTPUT'],
            'START_DISTANCE': parameters['Extenddistance'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ExtendLines'] = processing.run('native:extendlines', alg_params, context=context, feedback=feedback,
                                                is_child_algorithm=True)

        feedback.setCurrentStep(3)
        if feedback.isCanceled():
            return {}

        # Explode lines
        alg_params = {
            'INPUT': outputs['PolygonsToLines']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ExplodeLines'] = processing.run('native:explodelines', alg_params, context=context, feedback=feedback,
                                                 is_child_algorithm=True)

        feedback.setCurrentStep(4)
        if feedback.isCanceled():
            return {}

        # clean lines
        alg_params = {
            'INPUT': outputs['ExplodeLines']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['AddSelfIntersectionPoints'] = processing.run('mappy:ensureintersectionpoints', alg_params, context=context, feedback=feedback,
                                                is_child_algorithm=True)

        feedback.setCurrentStep(5)
        if feedback.isCanceled():
            return {}

        # Check validity
        alg_params = {
            'IGNORE_RING_SELF_INTERSECTION': False,
            'INPUT_LAYER': outputs['ExtendLines']['OUTPUT'],
            'METHOD': 2,
            'VALID_OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['CheckValidity'] = processing.run('qgis:checkvalidity', alg_params, context=context, feedback=feedback,
                                                  is_child_algorithm=True)

        feedback.setCurrentStep(6)
        if feedback.isCanceled():
            return {}

        # Retain fields
        alg_params = {
            'FIELDS': [''],
            'INPUT': outputs['AddSelfIntersectionPoints']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['RetainFields'] = processing.run('native:retainfields', alg_params, context=context, feedback=feedback,
                                                 is_child_algorithm=True)

        feedback.setCurrentStep(7)
        if feedback.isCanceled():
            return {}

        # Explode contacts lines
        alg_params = {
            'INPUT': outputs['CheckValidity']['VALID_OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['ExplodeContactsLines'] = processing.run('native:explodelines', alg_params, context=context,
                                                         feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(8)
        if feedback.isCanceled():
            return {}

        # Split With Lines_contacts
        alg_params = {
            'INPUT': outputs['ExplodeContactsLines']['OUTPUT'],
            'LINES': outputs['ExplodeContactsLines']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['SplitWithLines_contacts'] = processing.run('native:splitwithlines', alg_params, context=context,
                                                            feedback=feedback, is_child_algorithm=True)

        feedback.setCurrentStep(9)
        if feedback.isCanceled():
            return {}

        # Centroids
        alg_params = {
            'ALL_PARTS': False,
            'INPUT': outputs['SplitWithLines_contacts']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Centroids'] = processing.run('native:centroids', alg_params, context=context, feedback=feedback,
                                              is_child_algorithm=True)

        feedback.setCurrentStep(10)
        if feedback.isCanceled():
            return {}

        # Buffer
        alg_params = {
            'DISSOLVE': False,
            'DISTANCE': parameters['PrecisionjoinBuffer'],
            'END_CAP_STYLE': 0,
            'INPUT': outputs['Centroids']['OUTPUT'],
            'JOIN_STYLE': 0,
            'MITER_LIMIT': 2,
            'SEGMENTS': 5,
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Buffer'] = processing.run('native:buffer', alg_params, context=context, feedback=feedback,
                                           is_child_algorithm=True)

        feedback.setCurrentStep(11)
        if feedback.isCanceled():
            return {}

        # Join attributes by location
        alg_params = {
            'DISCARD_NONMATCHING': False,
            'INPUT': outputs['RetainFields']['OUTPUT'],
            'JOIN': outputs['Buffer']['OUTPUT'],
            'JOIN_FIELDS': [''],
            'METHOD': 2,
            'PREDICATE': [0],
            'PREFIX': '',
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['JoinAttributesByLocation'] = processing.run('native:joinattributesbylocation', alg_params,
                                                             context=context, feedback=feedback,
                                                             is_child_algorithm=True)

        feedback.setCurrentStep(12)
        if feedback.isCanceled():
            return {}

        # Dissolve
        alg_params = {
            'FIELD': ['MAPPY_UUID'],
            'INPUT': outputs['JoinAttributesByLocation']['OUTPUT'],
            'OUTPUT': QgsProcessing.TEMPORARY_OUTPUT
        }
        outputs['Dissolve'] = processing.run('native:dissolve', alg_params, context=context, feedback=feedback,
                                             is_child_algorithm=True)

        feedback.setCurrentStep(13)
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

        id = self.copy_output_to_sink(parameters, context, outputs["DropFields"]["OUTPUT"])

        return {"OUTPUT": id}

    def name(self):
        return 'removedangles'

    def icon(self):
        return QIcon(':/plugins/qgismappy/icons/dangles.png')

    def displayName(self):
        return 'Remove Dangles (Clean Contacts Dangling Ends)'

    def shortHelpString(self):
        return self.tr("Remove the dangling ends of intersecting lines (i.e. to clean the contacts)")

    def group(self):
        return 'Mapping'

    def groupId(self):
        return 'mapping'

    def createInstance(self):
        return RemoveDangles()
