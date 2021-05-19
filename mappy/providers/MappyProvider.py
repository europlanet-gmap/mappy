import os
from pathlib import Path

from qgis.PyQt.QtGui import QIcon
from qgis.core import QgsProcessingModelAlgorithm, QgsProcessing
from qgis.core import QgsProcessingProvider

from .map_autostyle import MapAutoStyleProcessingAlgorithm
from .map_construction import MapConstructionProcessingAlgorithm
from .remove_duplicate_segments import RemoveDuplicateSegmentsProcessingAlgorithm
from .remove_scaling_from_crs import RemoveScalingFromCrs
from .addselfintersectionpoints import AddSelfIntersectionPoints
from .removedangles import RemoveDangles


class Provider(QgsProcessingProvider):
    """
    The Mappy provider for QGIS processing framework
    """
    def loadAlgorithms(self, *args, **kwargs):
        print("LOADING")
        self.addAlgorithm(MapConstructionProcessingAlgorithm())
        self.addAlgorithm(MapAutoStyleProcessingAlgorithm())
        self.addAlgorithm(RemoveDuplicateSegmentsProcessingAlgorithm())
        self.addAlgorithm(AddSelfIntersectionPoints())
        self.addAlgorithm(RemoveDangles())
        self.addAlgorithm(RemoveScalingFromCrs())

        # useful during dev
        # self.load_models_as_algorithms()

    def load_models_as_algorithms(self):
        """currently not used, but helper for dev"""
        for dirpath, dirnames, files in os.walk(os.path.dirname(__file__)):
            for file_name in files:
                print(file_name)
                if file_name.lower().endswith('.model3'):
                    print(dirpath)
                    print(file_name)
                    alg = QgsProcessingModelAlgorithm()
                    file = os.path.join(dirpath, file_name)
                    alg.fromFile(file)
                    print("ADDING ")
                    code = alg.asPythonCode(QgsProcessing.PythonQgsProcessingAlgorithmSubclass, 4)
                    cc = ""
                    for c in code:
                        cc += c + "\n"
                    # print(code)
                    pp = Path(file).with_suffix(".py")
                    print(pp)

                    with open(pp, "w") as f:
                        f.write(cc)

                    self.addAlgorithm(alg)

    def id(self, *args, **kwargs):
        """The ID of your plugin, used for identifying the provider.

        This string should be a unique, short, character only string,
        eg "qgis" or "gdal". This string should not be localised.
        """
        return 'mappy'

    def name(self, *args, **kwargs):
        """The human friendly name of your plugin in Processing.

        This string should be as short as possible (e.g. "Lastools", not
        "Lastools version 1.0.1 64-bit") and localised.
        """
        return self.tr('Mappy')

    def icon(self):
        """Should return a QIcon which is used for your provider inside
        the Processing toolbox.
        """
        return QIcon(':/plugins/qgismappy/icons/icon.png')
