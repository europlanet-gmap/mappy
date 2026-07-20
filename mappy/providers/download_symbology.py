from pathlib import Path

from qgis.PyQt.QtCore import QSettings
from qgis.PyQt.QtGui import QIcon
from qgis._core import (
    QgsProcessingParameterFolderDestination,
    QgsProcessingFeedback,
    QgsStyle,
    QgsProcessingParameterString,
    QgsApplication,
)

from .MappyProcessingAlgorithm import MappyProcessingAlgorithm


symbols_url_zip = "https://github.com/afrigeri/geologic-symbols-qgis/releases/download/v1.0.0-rc.1/gsymblib-v1.0.0-rc.1.zip"
file_to_load = "geologic_symbols_qgis/geologic_symblib.xml"
default_svg_path = "geologic_symbols_qgis/svg"


class DownloadSymbology(MappyProcessingAlgorithm):
    """Quick download planetary geology symbology"""

    def initAlgorithm(self, config=None):
        from pathlib import Path

        default = Path.home().joinpath("qgis_symbols").as_posix()
        dest = QgsProcessingParameterFolderDestination(
            "DestinationFolder", "Destination folder of the svg files", defaultValue=default
        )
        self.addParameter(dest)

        url = QgsProcessingParameterString("Url", "Source Zip Url", defaultValue=symbols_url_zip)
        self.addParameter(url)

    def next_step(self):
        self.feedback.setCurrentStep(self.current_step)
        self.current_step += 1
        if self.feedback.isCanceled():
            return True

    def processAlgorithm(self, parameters, context, model_feedback: QgsProcessingFeedback):

        s = Path(parameters["DestinationFolder"])
        model_feedback.pushCommandInfo(f"Destination folder set to {s}")

        full_svg_path = s.joinpath(default_svg_path).as_posix()

        svg_paths = QSettings().value("svg/searchPathsForSVG")

        if not svg_paths:
            svg_paths = QgsApplication.svgPaths()

        if full_svg_path in svg_paths:
            model_feedback.pushCommandInfo(f"svg path {full_svg_path} is already present in the settings")
        else:
            model_feedback.pushCommandInfo(f"Adding svg path {full_svg_path} to the settings")
            svg_paths.append(full_svg_path)
            QSettings().setValue("svg/searchPathsForSVG", svg_paths)

        if not s.exists():
            model_feedback.pushCommandInfo(f"Folder does not exists. Creating it at {s}")
            s.mkdir(parents=True)

        else:
            model_feedback.pushCommandInfo("Folder already exists.")

        import requests

        url = parameters["Url"]

        myfile = requests.get(url, timeout=30)
        fname = Path(url).name
        model_feedback.pushCommandInfo(fname)

        import tempfile

        tdir = Path(tempfile.gettempdir())

        newfname = tdir.joinpath(fname)

        with open(newfname, "wb") as f:
            f.write(myfile.content)

        # now we decompress it
        from zipfile import ZipFile

        with ZipFile(newfname, "r") as zf:
            dest_root = s.resolve()
            for member in zf.namelist():
                member_path = dest_root.joinpath(member).resolve()
                if dest_root not in member_path.parents and member_path != dest_root:
                    raise ValueError(f"Unsafe path in zip archive: {member}")
            zf.extractall(s)

        from .symbol_xml_extractor import SymbolXMLExtractor

        extractor = SymbolXMLExtractor(s.joinpath(file_to_load).as_posix())
        extractor.parse_xml()

        symbols = extractor.symbols

        style = QgsStyle.defaultStyle()

        tag_name = "Planetary Symbols"
        tag = style.tagId(tag_name)
        if tag == 0:
            tag = style.addTag(tag_name)

        for symbol in symbols:
            symbol_name = "{} ({})".format(symbol["name"], "Planetary Symbols")
            style.addSymbol(symbol_name, symbol["symbol"], True)
            style.tagSymbol(QgsStyle.SymbolEntity, symbol_name, [tag_name])

        return {}

    def name(self):
        return "downloadsymbology"

    def icon(self):
        return QIcon(":/plugins/qgismappy/icons/download.png")

    def displayName(self):
        return "Auto download and setup mapping symbology"

    def shortHelpString(self):
        return self.tr("This will automatically download and install the planetary symbology set from Ale Frigeri repo.")

    def group(self):
        return "Mapping"

    def groupId(self):
        return "mapping"

    def createInstance(self):
        return DownloadSymbology()
