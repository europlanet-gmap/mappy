from qgis._core import QgsVectorFileWriter, QgsCoordinateTransformContext


def save_to_geopackage(gpkg_filename, layer, layername="layer"):
    opts = QgsVectorFileWriter.SaveVectorOptions()
    opts.driverName = "GPKG"
    opts.layerName = layername

    from pathlib import Path

    if not Path(gpkg_filename).exists():
        opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteFile
    else:
        print("file exsists")
        opts.actionOnExistingFile = QgsVectorFileWriter.CreateOrOverwriteLayer



    return QgsVectorFileWriter.writeAsVectorFormatV2(layer, gpkg_filename, QgsCoordinateTransformContext(), opts)
