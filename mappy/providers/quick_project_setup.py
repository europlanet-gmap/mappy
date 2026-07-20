from pathlib import Path

from qgis.PyQt.QtCore import QSettings
from qgis.PyQt.QtGui import QIcon
from qgis._core import QgsProcessingParameterFolderDestination, QgsProcessingFeedback, QgsStyle, \
    QgsProcessingParameterString, QgsApplication, QgsProcessingParameterCrs, QgsVectorLayer, QgsField, \
    QgsProcessingAlgorithm, QgsProject, QgsProcessingParameterBoolean
from qgis.PyQt.QtCore import QVariant

from .MappyProcessingAlgorithm import MappyProcessingAlgorithm

from pathlib import Path

from ..mappy_utils import restoreWidgetContent


class QuickProjectSetup(MappyProcessingAlgorithm):
    """Quick download planetary geology symbology"""

    def initAlgorithm(self, config=None):

        pars = []
        pars.append(QgsProcessingParameterString("ProjectName", "Name of the project", defaultValue="Map"))
        pars.append(QgsProcessingParameterFolderDestination("OutFolder", "Folder to store your project in",
                                                            defaultValue=Path.home().joinpath(
                                                                "Mapping Projects").as_posix()))

        pars.append(QgsProcessingParameterCrs("CRS", "Project Reference System", defaultValue="ProjectCrs"))

        pars.append(QgsProcessingParameterBoolean("LinearFeaturesLayer", "Create an additional line layer for structural mapping or linear features", defaultValue=True))

        for p in pars:
            self.addParameter(p)

    def next_step(self):
        self.feedback.setCurrentStep(self.current_step)
        self.current_step += 1
        if self.feedback.isCanceled():
            return True

    def ensureDir(self, dir, model_feedback):
        if not Path(dir).exists():
            Path(dir).mkdir(parents=True)
            model_feedback.pushCommandInfo(f"Created folder {dir}")

    def processAlgorithm(self, parameters, context, model_feedback: QgsProcessingFeedback):

        project_name = parameters["ProjectName"]

        create_linear_features_layer = parameters["LinearFeaturesLayer"]

        if parameters["OutFolder"] == "TEMPORARY_OUTPUT":
            import tempfile
            parameters["OutFolder"] = tempfile.gettempdir()

        ofolder = Path(parameters["OutFolder"]).joinpath(project_name)
        crs = self.parameterAsCrs(parameters, "CRS", context)

        vector_folder = ofolder.joinpath("vector")
        vector_file = vector_folder.joinpath(project_name.lower()).with_suffix(".gpkg")

        model_feedback.pushCommandInfo(f"Setting up project {project_name} in folder {ofolder}")

        model_feedback.pushCommandInfo(
            f"Vector files will be located in folder {vector_folder} (file will be {vector_file})")

        self.ensureDir(ofolder, model_feedback)
        self.ensureDir(vector_folder, model_feedback)

        # vl = QgsVectorLayer("Point", "source_indicators", "memory")

        pts_fields = [["unit_name", QVariant.String]]
        line_fields = [["certainty", QVariant.String]]

        indicators_layer = self.generate_and_load_geopackage_layer(vector_file.as_posix(), crs, type="Point", name="source_indicators",
                                                fields=pts_fields)
        contacts_layer = self.generate_and_load_geopackage_layer(vector_file.as_posix(), crs, type="Linestring", name="source_contacts",
                                                fields=line_fields)

        from ..mappy_utils import enable_default_labels, style_simple_black_line
        enable_default_labels(indicators_layer, "unit_name")
        style_simple_black_line(contacts_layer)

        if create_linear_features_layer:
            structure_fields = [["certainty", QVariant.String], ["type", QVariant.String] ]
            self.generate_and_load_geopackage_layer(vector_file.as_posix(), crs, type="Linestring", name="linear_features",
                                                    fields=structure_fields)


        proj = QgsProject.instance()
        proj.write(ofolder.joinpath(project_name).with_suffix(".qgz").as_posix())

        from mappy.qgismappy import Mappy
        instance : Mappy = Mappy.instance
        instance.config_dock.show()

        dock = instance.config_dock

        w = dock.get_widget_by_name("output")
        restoreWidgetContent(w, vector_file)

        w = dock.get_widget_by_name("points")
        restoreWidgetContent(w, indicators_layer)

        # Setting "points" above triggers the dock's own points->units_field
        # wiring via a Qt signal, but its delivery isn't guaranteed to be
        # synchronous in every context (e.g. a live GUI event loop), so don't
        # rely on it here: bind units_field to the layer directly before
        # selecting the field, otherwise the combo can end up with no layer
        # (and thus no fields) bound to it at all.
        w = dock.get_widget_by_name("units_field")
        w.setLayer(indicators_layer)
        restoreWidgetContent(w, "unit_name")


        return {}

    def generate_and_load_geopackage_layer(self, gpkg_file, crs=None, type="Point", name="source_indicators",
                                           fields=dict(name="unit_name", type=QVariant.String)):
        vl = QgsVectorLayer(type, name, "memory")

        pr = vl.dataProvider()

        for field in fields:
            pr.addAttributes([QgsField(field[0], field[1])])
        vl.updateFields()
        if crs is not None:
            vl.setCrs(crs)

        from mappy.mappy_utils import write_layer_to_gpkg2, add_layer_from_geopackage

        write_layer_to_gpkg2(vl, gpkg_file, name)

        # vector_file = vector_file.as_posix() + f"|layername={vl.name()}"
        # print(vector_file)
        # l = QgsVectorLayer(vector_file)
        # l.setName(vl.name())

        l = add_layer_from_geopackage(gpkg_file, name)

        return l

    def flags(self):
        """
        doing this beacuase we are going to interact with qgis main instance. we need to be within the same thread
        """
        return super().flags() | QgsProcessingAlgorithm.FlagNoThreading

    def name(self):
        return 'quickprojectsetup'

    def icon(self):
        return QIcon(':/plugins/qgismappy/icons/new_project.png')

    def displayName(self):
        return 'Quick Mapping Project Setup'

    def shortHelpString(self):
        return self.tr("Helper to quickly setup a new mapping project and start mapping right away")

    def group(self):
        return 'Mapping'

    def groupId(self):
        return 'mapping'

    def createInstance(self):
        return QuickProjectSetup()
