# Mappy QGIS plugin

[![Python package](https://github.com/luca-penasa/mappy/actions/workflows/python-package.yml/badge.svg)](https://github.com/luca-penasa/mappy/actions/workflows/python-package.yml)

This QGIS plugin collects several useful algorithms to easily generate geological 
maps starting from contacts and points. 

> This plugin was developed as the result of the PLANMAP project (N 776276) and is now maintained thanks to the
> EUROPLANET-GMAP infrastructure (N 871149) and supported by the JANUS camera team of the JUICE mission (ASI-INAF 2018-25-HH.0). 

The algorithms are provided in the form of ```processing``` tools (look for mappy in the qgis toolbox). 

More info on the basic idea [here](documents/README.md) and see also the [tutorial](documents/mappy.md).


# Install

**The plugin will be soon contributed to the [QGIS Python Plugins Repository](https://plugins.qgis.org/plugins/) 
to make installation easier. Meanwhile:**

You can use the pre-generated zip packages that can be installed in qgis by using the plugin manager.
Download it from [Releases](https://github.com/europlanet-gmap/mappy/releases) and install the zip using the plugin manager.


## Notes for developers

- this plugin uses pb-tool to compile resources and zip the plugin.
- a top-level Makefile wraps some operations and can be used to create the package quickly
- the code of plugin itself is in the ```mappy``` folder


# (Quick) How to use

- Ensure the plugin was correctly loaded and activated from Plugins -> Manage ...
- Open the plugin interface via Plugins->mappy->Mappy
- Load some data, for example you can use the data in the repository folder "demo_data": load contacts and unit_id 
  (just drag and drop the two folders in QGIS)
- You can now execute the "construction" by using the appropriate processing algorithm from the toolbox.

# Troubleshooting

In case of troubles just drop an issue here on github!
