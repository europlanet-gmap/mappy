# -*- coding: utf-8 -*-
"""
/***************************************************************************
 Mappy
                                 A QGIS plugin
 helper for consistent goelogical map generation
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                             -------------------
        begin                : 2020-06-24
        copyright            : (C) 2020 by Luca Penasa, PLANMAP and GMAP team
        email                : luca.penasa@gmail.com
        git sha              : $Format:%H$
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script initializes the plugin, making it known to QGIS.
"""

# import os
# import sys
#
# path = os.path.dirname(os.path.abspath(__file__))
#
# if os.path.exists(os.path.join(path, "mappy")): #  in the package
#     sys.path.append(path)
#     sys.path.append(os.path.join(path, "external"))
#
#
# else:  # we are in the dev folder
#     fullpath = path + " /../../"
#     fullpath = os.path.abspath(fullpath)
#
#     ext_path = os.path.join(fullpath, "external")
#
#     if fullpath not in sys.path:
#         # print(" adding the path")
#         sys.path.insert(0, fullpath)
#
#     if ext_path not in sys.path:
#         # print(" adding the path")
#         sys.path.insert(0, ext_path)
#
# try:
#     import mappy
# except:
#     raise ImportError("Cannot import mappy. This should not happen")
from qgis.core import QgsApplication
import sys

if 'sphinx' in sys.modules:
    qgs = QgsApplication([], False)

    # load providers
    qgs.initQgis()

# noinspection PyPep8Naming
def classFactory(iface):  # pylint: disable=invalid-name
    """Load Mappy class from file Mappy.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    #
    from .qgismappy import Mappy
    return Mappy(iface)


