# Configuration file for the Sphinx documentation builder.

# -- Project information

import sys
sys.path.append("../")

project = 'Mappy'
copyright = 'Luca Penasa, PLANMAP and GMAP team'
author = 'Luca Penasa'

release = '0.1'
version = '0.1.4'

# -- General configuration

extensions = [
    'sphinx.ext.duration',
    'sphinx.ext.doctest',
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.intersphinx',
    'myst_parser',
    'sphinx.ext.autosectionlabel'
    # 'numfig'
]

myst_enable_extensions = [
  "colon_fence",
  "dollarmath"
]


source_suffix = ['.rst', '.md']
numfig = True

intersphinx_mapping = {
    'python': ('https://docs.python.org/3/', None),
    'sphinx': ('https://www.sphinx-doc.org/en/master/', None),
}
intersphinx_disabled_domains = ['std']

templates_path = ['_templates']

# -- Options for HTML output

html_theme = 'sphinx_rtd_theme'

# -- Options for EPUB output
epub_show_urls = 'footnote'
