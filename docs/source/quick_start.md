# Quick start tutorial

This section should provide all the information needed to quickly start using
mappy. If you are really in a hurry, jump to {any}`generating_map`.

:::{warning}
We assume you already loaded the basemaps you intend to use for your mapping.
If you haven't, do it now! It will also simplify the selection of a meaningful
CRS for your project. CRSs are extremely important when you are first setting
up
a mapping project. Have a
look [here](https://docs.qgis.org/testing/en/docs/gentle_gis_introduction/coordinate_reference_systems.html)
for an introduction.
:::

(initial)=

## Initial setup

:::{important}
You can also skip this section "{ref}`initial`" and use the mappy algorithm
[{guilabel}`Quick Mapping Project Setup`](quick_setup) to easily set up the
minimum dataset
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
used to enter the field's values. An {guilabel}```Unique Values``` or
a
{guilabel}```Value Map``` [widget](https://docs.qgis.org/testing/en/docs/user_manual/working_with_vector/vector_properties.html#edit-widgets)
might be used for this task. An example will be demonstrated later.
:::

The layers can be created in any format supported by QGIS (e.g. ESRI
Shapefiles), but we suggest organizing your work within
a [geopackage](https://en.wikipedia.org/wiki/GeoPackage) file. This
open format make it possible to store within a single and portable file any
number of different vector layers. To create a new geopackage
use {guilabel}`Layer ► Create Layer ► New Geopackage Layer` or `CTRL+SHIFT+N`.

:::{figure} imgs/geopackage.png
:align: center
:width: 50% 

Creating a new geopackage layer in QGIS with one point layer named ```points```
, with one field ```geo_units```of type ```Text Data```. Once the geopackage is
created new layers can be appended to the same file by selecting the
same ```Database``` geopackage. The same operation should be performed for
creating the line layer that will contain the contacts.
:::

:::{warning}
Remember to set a
meaningful [CRS](https://docs.qgis.org/testing/en/docs/gentle_gis_introduction/coordinate_reference_systems.html)
for the layer. It might be worth taking some
time to verify the CRSs that are used in the basemaps you will be using for
your
mapping and chose among those the most suitable. If you have loaded your
basemap
at the beginning as suggested you might just need to select the "Project CRS"
from the options.
:::

## Drawing the contacts

Assuming you have already loaded your basemaps you can now start tracing your
contacts. Just enable the editing (use {guilabel}`Toggle Editing` from
right-clicking on
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

:::{tip}
Mappy will generate indicator points for any unlabeled unit by default.
But you will still need to provide a point layer to be used for labelling the
units.
:::

The next step consist in labelling each region we have identified with the
contacts. To do so a point layer will be used: a new point will be placed
anywhere within the given unit and its fields will be populated accordingly.

We will use the following unit's shortcuts:
:::{table}
:align: center
| Code | Legend |
--- | --- |
| SCA | Outer escarpment of the volcano |
| EDF | Main shield volcanic edifice|
| SC | Summit calderas |
:::

and populate the points layer. If you want you can setup dedicated field widget
to ease this work (
{guilabel}`Right Click on Layer ► Properties ► Attributes Forms`).

:::{figure} imgs/forms_example.png
:align: center
:width: 100%

Example of attribute form set up with the predefined unit's names (notice you
can also create them as a CSV file to load).
:::

After enabling the point layer for editing we add new points by left-clicking
with the mouse in the location of interest. You must activate the adequate tool
for adding new points (look for {guilabel}`Add Point Feature` button or use
{guilabel}`CTRL+.`).
For each unit you will need to enter the corresponding unit. If you set up a
dedicated {guilabel}`Attribute form` the dialog will look something like this:

:::{figure} imgs/widget.png
:align: center
:width: 80%

Example of Feature Attribute Dialog, customized with a {guilabel}`Value Map`
field
widget. It ensures no wrong codes can can be inserted into the database.
:::

After adding all the needed points the results should be something like this:

:::{figure} imgs/points.png
:align: center

Example of points used to define the names of the units. Short-codes were used
to uniquely identify the unit. To show the labels
follow {guilabel}`Right-Click on layer ► Properties ► Labels` and configure
accordingly.
:::

Remember to save the layers by using the {guilabel}`Save Layer Edit` in the
{guilabel}`Digitizing`
toolbar.

(generating_map)=
## Generating the polygonal map

Mappy can be accessed through a dedicated toolbar:
:::{figure} imgs/toolbar.png
:align: center
:::

The gear button will toggle the configuration dialog:

:::{figure} imgs/dialog.png
:width: 60%
:align: center

Mappy settings dialog
:::

The second button (Recompute Map) is used to quickly recompute the map on the
basis of the configuration provided in the main dialog. It is meant to be the
only button that you are going to use every time you need to refresh the
polygons
during the mapping.

The config dialog requires you to set:

### Input

- **Line-geometry layer**: it will be used as source of your contacts, any line
  layer will work (you can organize the fields of your contacts freely).
- **Point-geometry layer**: it will be used to label the newly generated
  polygons, and it must have at least one field that will be used as unit's
  name.
- **Unit's field** is the field of the points layer that is used by mappy.
  Although mappy transfer all the existing fields to the polygons the field is
  still needed so that mappy knows what field to use for generating the
  legend/colors.

### Output

- **Output Geopackage**: The geopackage in which the output layers will be
  written
- **Polygons layer**: the name that will be used in the output geopackage to
  name the polygonal layer
- **Clean Contacts layer name**: (if enabled) the name for the clean contacts
  layer in the output geopackage

If clean contacts generation is enabled mappy will generate a copy of your
input contacts after cleaning them from dangling ends.
This layer is intended to be used as overlay for your final layout



:::{warning}
The operation of dangling-ends removal that is used to generate the
{guilabel}`Clean Contacts` layer is computationally intensive in the present
implementation.
If you experience qgis unresponsiveness during the map computation try
to disable this feature and use it only at the end for finalizing the map.
:::

### Options

- **Overwrite Output Layer**: it will take the freedom to overwrite the output
  polygonal layer if it is already present
- **Auto-add Missing Indicator Points**: it will automatically compute and add
  any missing indicator point. You will then still need to populate the fields
  to label your units.
- **Copy Line Style**: it will copy the styling of your contacts to your
  {guilabel}`Clean Contacts` layer (if generated). In this way you can work
  with correctly styled layers and have the style copied to final version of
  your contacts.
- **Automatically regenerate the map when assigning a unit**: off by default.
  When enabled, a full {guilabel}`Recompute Map` is triggered every time you
  assign a unit with the {guilabel}`Assign unit to polygon` tool (see
  {ref}`assigning_units` below), instead of only updating the clicked polygon.

---

After setting and double-checking your config you can now press the
{guilabel}`Recompute Map` toolbar button and have your polygons computed.

(assigning_units)=
## Assigning units and quick editing

Once a map has been generated at least once, two additional toolbar tools let
you keep refining it without going back through the full recompute cycle every
time:

:::{tip}
Both tools live on the same Mappy toolbar as {guilabel}`Recompute Map`
(see the toolbar screenshot above).
:::

### Assign unit to polygon

The {guilabel}`Assign unit to polygon` tool (the map-pin icon) lets you
directly (re)assign the unit of an existing polygon on the generated map,
without re-digitizing or moving any indicator point by hand:

1. Click the {guilabel}`Assign unit to polygon` button to activate the tool
   (it stays active, like other QGIS map tools, until you click it again or
   switch tools).
2. Click anywhere inside a polygon of the generated map layer.
3. A dialog opens with a searchable list of every unit currently in use. Start
   typing to filter it live, or type a name that doesn't exist yet to create a
   new unit. Use the swatch button next to the filter box to pick or change
   that unit's color on the spot — no separate styling step needed.
4. Confirm with {guilabel}`OK` (or by double-clicking/pressing Enter on a list
   entry).

Mappy then updates the clicked polygon's unit and color immediately, keeps the
underlying indicator point in sync, and applies default labeling. Unit colors
are stored per-project, so once a unit has a color it stays consistent across
every polygon and every layer that uses it, even after the map is
regenerated. If you'd rather have the whole map recomputed after every
assignment instead, enable {guilabel}`Automatically regenerate the map when
assigning a unit` in the config dialog.

### Quick enable editing

The {guilabel}`Quick enable editing` button (QGIS's own pencil icon) is a
shortcut for the contacts layer: it switches to your configured lines layer,
turns on editing if it isn't already, and immediately activates the
{guilabel}`Add Line Feature` tool — the same three steps you'd otherwise do by
hand every time you want to add a new contact.

## Styling the map


:::{warning}
Mappy will take care of styling the polygons for you, it will also copy the
style of you contacts layer to the `Clean Contacts` layer. Anyway if you need to
style them by hand here are some instructions.
:::

The map can then be styled with
{guilabel}`Right-click on Layer ► Properties ► Symbology`.
A {guilabel}`Categorized` symbology might be used, like so (you can use the
{guilabel}`Classify`
button to automatically add all your unit's definitions, also remember to
modify the {guilabel}`Legend` items if you want a full description of the map
in the
printing layout):

:::{figure} imgs/symbology.png
:align: center
:::

:::{tip}
Notice you
might want to set the {guilabel}`Stroke Stile` to {guilabel}`No Pen` for the
polygonal layer, so that only
the line contacts will be visible in the final map.
:::

your map might look like this:

:::{figure} imgs/map.png
:align: center
:width: 50%

Polygonal map with styling.
:::

:::{tip}

To enable this kind of transparency find the {guilabel}`Blending Mode` option
under the
layer's {guilabel}`Symbology ► Layer Rendering` dialog, and set it to
{guilabel}`Overlay`

:::

