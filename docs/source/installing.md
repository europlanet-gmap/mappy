# Installing Mappy

## Via the official QGIS plugins repository 

The plugin has now been contributed to the 
[QGIS Python Plugins Repository](https://plugins.qgis.org/plugins/mappy/) 
to make installation easier. To install it just launch QGIS and find the 
Plugin Manager under {guilabel}`Plugins ► Manage and Install`. 
Under {guilabel}`All` you should now be able to find {guilabel}`mappy` and
install it directly.


:::{warning}
If you experience problems installing Mappy and you already had a previous 
version of the plugin installed (e.g. during the [PLANMAP-GMAP Winter School](https://planetarymapping.eu)) 
you might try to remove the previous version of the plugin before proceeding 
with the normal installation. Very early versions of the plugin might indeed 
cause conflicts with the currently packaged version. 
:::


## From GitHub zip package (for the latest release) 
If you want to try the latest version available, you can use the pre-generated 
zip packages that can be installed in qgis by using the plugin manager.
Download it from [Releases](https://github.com/europlanet-gmap/mappy/releases) 
and install the zip using the plugin manager. 
Releases marked as {guilabel}`latest`are automatically in sync with the master of 
this repo. Tagged releases (e.g. named v0.1.2) should be considered as stable 
versions, although the plugin itself is still largely experimental.
