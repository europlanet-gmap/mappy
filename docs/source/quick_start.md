# Quick start tutorial
This section should provide all the information needed to quickly start using 
mappy. 

:::{warning}
We assume you already loaded the basemaps you intend to use for your mapping. 
If you haven't, do it now! It will also simplify the selection of a meaningful 
CRS for your project. CRSs are extremely important when you are first setting up
a mapping project. Have a look [here](https://docs.qgis.org/testing/en/docs/gentle_gis_introduction/coordinate_reference_systems.html)
for an introduction.
:::




(initial)=
## Initial setup


:::{important}
You can also skip this section "{ref}`initial`" and use the mappy algorithm 
[{guilabel}`Quick Mapping Project Setup`](quick_setup) to easily set up the minimum dataset 
needed to quick-start your mapping project. This is still a suggested reading, 
as it provides some useful tips!
:::

Two different layers should be created:

- A line layer (either Line or MultiLine). The associated fields are not
  mandatory, but you might want to consider adding a couple of fields
  like ```certainty``` and/or ```type``` to represent the type of contact you
  are tracing. Keep in mind that more information you add to your vector data,
  easier will be to style them later or to reuse them for other purposes.
- A point layer. Here we need at least one field that will be used as unique
  identifier for each geological unit that will be mapped. Choose for
  example ```geo_units```.


Take your time to establish the naming of your fields to be meaningful and
readily understandable. The same apply for the layers. It will not influence
mappy in any way, but it will help you creating a clean dataset.


The type of fields can be freely chosen, but it is highly suggested you try to
define beforehand the entries that will be used when populating your map. For
example a ```string/char``` field can be used as type for the ```geo-units```
field, but it might be difficult to be consistent when entering those long
strings by hand (they could be easily misspelled), thus short names or a code
for each unit might be preferable.

:::{tip}
To avoid mistakes when typing in the name of the geological unit in a string
field, you could define them beforehand customizing
the [attribute form](https://docs.qgis.org/testing/en/docs/user_manual/working_with_vector/vector_properties.html#attributes-form-properties)
used to enter the field's values. An ```Unique Values``` or
a ```Value Map``` [widget](https://docs.qgis.org/testing/en/docs/user_manual/working_with_vector/vector_properties.html#edit-widgets)
might be used for this task. An example will be demonstrated later.
:::

The layers can be created in any format supported by QGIS (e.g. ESRI
Shapefiles), but we suggest organizing your work within a [geopackage](https://en.wikipedia.org/wiki/GeoPackage) file. This
open format make it possible to store within a single and portable file any
number of different vector layers. To create a new geopackage
use ```Layer> Create Layer> New Geopackage Layer``` or ```CTRL+SHIFT+N```.

:::{figure} imgs/geopackage.png
:align: center

Creating a new geopackage layer in QGIS with one point layer named ```points```
, with one field ```geo_units```of type ```Text Data```. Once the geopackage is
created new layers can be appended to the same file by selecting the
same ```Database``` geopackage. The same operation should be performed for
creating the line layer that will contain the contacts. 
:::

:::{warning}
Remember to set a meaningful [CRS](https://docs.qgis.org/testing/en/docs/gentle_gis_introduction/coordinate_reference_systems.html) for the layer. It might be worth taking some 
time to verify the CRSs that are used in the basemaps you will be using for your
mapping and chose among those the most suitable. If you have loaded your basemap 
at the beginning as suggested you might just need to select the "Project CRS" from the options.
:::

## Drawing the contacts

Assuming you have already loaded your basemaps you can now start tracing your
contacts. Just enable the editing (use `Toggle Editing` from right-clicking on
the layer) for your newly created layer and add new lines. Something very
important that you should keep in mind is that you should not be focusing on
the outline of each unit, but rather determine the contacts between the
different units.

:::{figure} imgs/lines.png
:align: center

Example of linework on
the [Olympus Mons](https://en.wikipedia.org/wiki/Olympus_Mons) volcanic edifice
on Mars, we used the lines to define the contacts between different
morphological units. Notice that the linework does not need to be precise (here
exaggerated), we just need the line to be intersecting to correctly define the
units. Also multiple lines can be used to define one contact, provided they all
intersect each other (see the calderas on the summit).
:::

## Defining indicator points

The next step consist in labelling each region we have identified with the
contacts. To do so a point layer will be used: a new point will be placed
anywhere within the given unit and its fields will be populated accordingly.

We will use the following unit's shortcuts:
:::{table}
:align: center
| code | description |
--- | --- |
| SCA | Outer escarpment of the volcano |
| EDF | Main shield volcanic edifice|
| SC | Summit calderas |
:::

and populate the points layer. If you want you can setup dedicated field widget
to ease this work (`Right Click on Layer >Properties> Attributes Forms> `).

:::{figure} imgs/forms_example.png
:align: center

Example of attribute form set up with the predefined unit's names (notice you
can also create them as a CSV file to load).
:::

After enabling the point layer for editing we add new points by left-clicking
with the mouse in the location of interest. You must activate the adequate tool
for adding new points (look for `Add Point Feature` button or use `CTRL+.`).
For each unit you will need to enter the corresponding unit. If you set up a
dedicated `Attribute form` the dialog will look something like this:

:::{figure} imgs/widget.png
:align: center

Example of Feature Attribute Dialog, customized with a `Value Map` field
widget. It ensures no wrong codes can can be inserted into the database.
:::

After adding all the needed points the results should be something like this:

:::{figure} imgs/points.png
:align: center

Example of points used to define the names of the units. Short-codes were used
to uniquely identify the unit. To show the labels
follow `Right-Click on layer> Properties> Labels` and configure accordingly.
:::

Remember to save the layers by using the `Save Layer Edit` in the `Digitizing`
toolbar.


## Generating the polygonal map

:::{figure} imgs/dialog.png
:width: 400
:align: center

Mappy quick map generation dialog
:::


## Styling the map

The map can then be styled with `Right-click on Layer> Properties> Symbology`.
A `Categorized` symbology might be used, like so (you can use the `Classify`
button to automatically add all your unit's definitions, also remember to
modify the `Legend` items if you want a full description of the map in the
printing layout):

:::{figure} imgs/symbology.png
:align: center
:::


:::{tip}
Notice you
might want to set the `Stroke Stile` to `No Pen` for the polygonal layer, or
the contacts will be duplicated multiple times.
:::

your map might look like this:

:::{figure} imgs/map.png
:align: center
:width: 50%

Polygonal map with styling.
:::



:::{tip}

To enable this kind of transparency find the `Blending Mode` option under the
layer's `Symbology> Layer Rendering` dialog, and set it to `Overlay`

:::

