# this file is reused from qgis resource manager plugin and slightly stripped.
# unitl planetary symbology is also moved to the resource manager system.

from qgis.PyQt.QtXml import QDomDocument
from qgis.PyQt.QtCore import QFile, QIODevice
from qgis.core import QgsSymbolLayerUtils, QgsReadWriteContext, QgsProject


class SymbolXMLExtractor:
    """Parses the given file and returns the symbols and colorramps"""

    def __init__(self, xml_path):
        """Constructor of the class.

        :param xml_path: The path to the symbol xml
        :type xml_path: str
        """
        self._xml_path = xml_path
        self._symbols = []
        # Parse the xml to get the symbols and colorramps
        self.parse_xml()

    def parse_xml(self):
        """Parse the xml file. Returns false if there is failure."""
        xml_file = QFile(self._xml_path)
        if not xml_file.open(QIODevice.ReadOnly):
            return False

        document = QDomDocument()
        if not document.setContent(xml_file):
            return False

        xml_file.close()

        document_element = document.documentElement()
        if document_element.tagName() != "qgis_style":
            return False

        # Get all the symbols
        self._symbols = []
        symbols_element = document_element.firstChildElement("symbols")
        symbol_element = symbols_element.firstChildElement()
        context = QgsReadWriteContext()
        context.setPathResolver(QgsProject.instance().pathResolver())
        while not symbol_element.isNull():
            if symbol_element.tagName() == "symbol":
                symbol = QgsSymbolLayerUtils.loadSymbol(symbol_element, context)
                if symbol:
                    self._symbols.append({"name": symbol_element.attribute("name"), "symbol": symbol})
            symbol_element = symbol_element.nextSiblingElement()

        return True

    @property
    def symbols(self):
        return self._symbols
