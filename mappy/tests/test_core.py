from qgis.PyQt.QtCore import QVariant
from qgis.core import QgsVectorLayer, QgsField, QgsFeature, QgsGeometry, QgsPointXY, QgsProject, QgsLineString, \
    QgsVectorFileWriter, QgsApplication
from qgis.analysis import QgsNativeAlgorithms
import pytest

from mappy.tests.conftest import qgis_app



from . import ExtendedUnitTesting


dep = pytest.mark.dependency

class Storage:
    points = None
    lines = None
    map = None
    providers = []


class TestCore(ExtendedUnitTesting):
    def test_app(self):
        self.assertIsNotNone(QgsApplication.instance(), "app is none")

    def test_mappy_plugin_is_loaded(self):
        import qgis.utils
        self.assertIn("mappy", qgis.utils.plugins, "mappy plugin not found in qgis.utils.plugins")

    def test_mappy_plugin_path_registered(self):
        import qgis.utils
        from pathlib import Path
        project_root = str(Path(__file__).resolve().parents[2])
        self.assertIn(project_root, qgis.utils.plugin_paths,
                      f"{project_root} not in qgis.utils.plugin_paths")


    def _test_provider_can_be_loaded(self, prov, id):
        app = QgsApplication.instance()
        app.processingRegistry().addProvider(prov)

        r = app.processingRegistry()
        pp = r.providerById(id)
        print(pp.id())
        print(pp.name())
        self.assertIs(str(pp.id()) == id,True)
        self.assertIsNotNone(pp)



    def test_load_native_provider(self):
        n = QgsNativeAlgorithms()
        self._test_provider_can_be_loaded(n, "native")
        Storage.providers.append(n)

    def test_load_mappy_provider(self):
        from mappy.providers.MappyProvider import MappyProvider
        p = MappyProvider()
        self._test_provider_can_be_loaded(p, "mappy")
        for alg in QgsApplication.processingRegistry().algorithms():
            id = alg.id()
            if "mappy" in id:
                print(alg.id(), "--->", alg.displayName())

        Storage.providers.append(p)

    @pytest.mark.order(1)
    @dep(name="points")
    def test_point_layer(self):
        vl = QgsVectorLayer("Point", "points", "memory")
        pr = vl.dataProvider()
        pr.addAttributes([QgsField("geo_unit", QVariant.String)])
        vl.updateFields()

        f = QgsFeature()
        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(0.25, 0.5)))
        f.setAttributes(["UNIT_A"])
        pr.addFeature(f)

        f.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(0.75, 0.5)))
        f.setAttributes(["UNIT_B"])
        pr.addFeature(f)

        vl.updateExtents()
        QgsProject.instance().addMapLayer(vl)

        Storage.points = vl

    @pytest.mark.order(2)
    @dep(name="lines")
    def test_lines_layer(self):
        vl = QgsVectorLayer("linestring", "lines", "memory")
        pr = vl.dataProvider()
        vl.updateFields()

        f = QgsFeature()
        f.setGeometry(QgsGeometry.fromWkt("LINESTRING (0 0, 1 0, 1 1, 0 1, 0 0)"))
        pr.addFeature(f)

        f = QgsFeature()
        f.setGeometry(QgsGeometry.fromWkt("LINESTRING (0.5 -0.25, 0.5 1.25)"))
        pr.addFeature(f)



        vl.updateExtents()
        QgsProject.instance().addMapLayer(vl)

        Storage.lines = vl

    @dep(name="ret", depends=["points", "lines"])
    def test_retrieve(self):
        l = QgsProject.instance().mapLayersByName("lines")
        self.assertIs(len(l), 1)
        l = QgsProject.instance().mapLayersByName("points")
        self.assertIs(len(l), 1)

        l = QgsProject.instance().mapLayersByName("miss")
        self.assertIs(len(l), 0)


    @dep(depends=["points", "lines"])
    def test_save(self):
        from .utils import save_to_geopackage2

        o = save_to_geopackage2("out.gpkg", Storage.points, "points")
        print(o)
        o = save_to_geopackage2("out.gpkg", Storage.lines, "lines")
        print(o)


        self.assertFileExists("out.gpkg")

    @pytest.mark.order(3)
    @dep(name = "mapc",depends=["points", "lines"])
    def test_map_construction(self):
        from qgis.core import QgsApplication, QgsProcessingFeedback
        from qgis.analysis import QgsNativeAlgorithms

        import sys
        sys.path.append("/usr/share/qgis/python/plugins/")
        from qgis import processing
        # import processing
        # QgsApplication.processingRegistry().addProvider(QgsNativeAlgorithms())
        # from mappy.providers.MappyProvider import MappyProvider
        # QgsApplication.processingRegistry().addProvider(MappyProvider())

        # Processing.initialize()
        o: QgsVectorLayer = processing.run("mappy:mapconstruction", {"IN_LINES": Storage.lines, "IN_POINTS": Storage.points, "OUTPUT": "TEMPORARY_OUTPUT"})["OUTPUT"]
        print(o)
        self.assertIsNotNone(o)
        Storage.map = o



    @dep(name="map", depends=["mapc"])
    def test_map(self):
        n = Storage.map.featureCount()
        self.assertIs(n, 2)
        from .utils import save_to_geopackage2
        o = save_to_geopackage2("out.gpkg", Storage.map, "map")
        self.assertTrue(o[0] == 0)

        ff = [Storage.map.getFeature(i)["geo_unit"] for i in [1,2]]
        self.assertIn("UNIT_A", ff)
        self.assertIn("UNIT_B", ff)
