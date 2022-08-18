# Toolbox algorithms

:::{important}
The suggested way of using Mappy for your daily work is through the
mappy dedicated configuration dialog and the mappy toolbar, 
as explained in the {any}`quick_start` document.
:::

Mappy provides several algorithms that can be accessed through the QGIS
{guilabel}`Processing Toolbox`:

:::{figure} imgs/toolbox.png
:align: center
:width: 50%

The QGIS processing toolbox and the algorithms provided by mappy.
:::

The algorithms are internally used by the mappy toolbar to regenerate the map
while you are working, but can be easily used to generate custom workflows by 
using the [QGIS model designer](https://docs.qgis.org/testing/en/docs/user_manual/processing/modeler.html).


This page gives an introduction on how to use (some of) the algorithms provided
by Mappy, which can be activated from the toolbox.

(quick_setup)=
## Quick Mapping Project Setup

This algorithm will generate the initial dataset (point layer and line layers)
to jump-start your mapping project in a consistent and simple way.

## Map generation

It will generate a new polygonal layer that can be used for
printing the map. The mappy tools can be found within the {guilabel}`Processing Toolbox` dialog,
under {guilabel}`Mappy`. We are especially interested into the {guilabel}`Map Construction`
processing tool where we need to select the layers that will be used as
contacts and the one that represent the points.

:::{figure} imgs/mappy.png
:align: center
:::

There are not many options here but at the present implementation we have:

- Extend Line Distance. Is the distance in map-units that will be used to
  extend each end segment of the lines. This might be useful if some of your
  lines do not intersect by a minimum distance. Of course is better to fix the
  problem by modifying the contacts layer itself.
- Drop unassigned polygons. If selected, mappy will not produce polygons that
  were not assigned with the point layer.
- Constructed Map. Is where the output will be placed.

:::{tip}

The default value for the {guilabel}`Constructed Map` option is to create a temporary layer
every time the algorithm is run. During the mapping you might want to run the
algorithm many times to have a peek at how your final map will look like. To
avoid having to restyle everytime the newly generated map you could just set
this option to overwrite a file on disk (e.g. a layer within your geopackage).
In this way mappy can be run and QGIS will automatically find out that the
layer was changed, and it will reload it (you can force the reloading by
pressing {guilabel}`F5` if needed).

Alternatively you can use the tool {guilabel}`Map Automatic Styling`, privided by mappy
to quick-style your newly created map.

:::

After the map is generated it will look like this:

:::{figure} imgs/polygons.png
:align: center
:width: 50%
:::

Mappy generated the polygonal layer for you and added the properties defined
within the point layer. You can verify this by opening the attribute table for
the polygonal layer:

:::{figure} imgs/attrs.png
:align: center
:::

## Remove Dangles

Sometimes it might be useful to also style the contacts depending on their
meaning or other qualities.
For this task mappy provides the {guilabel}`Remove Dangles` tool which can remove any
dangling line end or start to produce a new contacts layers, free of any
imprecision that the operator used during mapping. The original attributes are
retained and can be used to style the contacts:

In {numref}`cleaned_contacts` we cleaned the original contacts with {guilabel}`Remove Dangles` and used
a different style depending on the `type` attribute of the contacts. This
feature make it possible to re-use the contacts for layout purposes. 

:::{figure} imgs/contacts_cleaned.png
:align: center
:name: cleaned_contacts

Example of cleaned contacts that are then styled and used to finalize the map
:::
