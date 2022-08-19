# Configuration file for the Sphinx documentation builder.

# -- Project information

import sys, re
sys.path.append("../")

project = 'Mappy'
copyright = 'Luca Penasa, PLANMAP and GMAP team'
author = 'Luca Penasa'


def read_version(metadata_file = "../../mappy/metadata.txt"):
    with open(metadata_file, "r") as f:
        t = f.read()
    m = re.match(r"(?s).*version=([0-9\\.]*)(?s).*", t)
    return m.group(1)

release = read_version()
version = '.'.join(release.split(".")[:2]) # only major v.

print(f"Release {release}")
print(f"Version {version}")

# -- General configuration

extensions = [
    'sphinx.ext.duration',
    'sphinx.ext.doctest',
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.intersphinx',
    'myst_parser',
    'sphinx.ext.autosectionlabel',
    'sphinxcontrib.bibtex'
]

bibtex_bibfiles = ['biblio.bib']

myst_enable_extensions = [
  "colon_fence",
  "dollarmath"
]




bibtex_encoding = 'utf-8-sig'
bibtex_default_style = 'unsrt'

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


# -- Options for TEX output
# latex_engine = 'xelatex'
# latex_use_xindy = False
#
#
# latex_elements = {'preamble': r'''\usepackage{pmboxdraw}''',
#
#                   }


latex_engine = 'xelatex'
latex_elements = {
    'fontpkg': r'''
\setmainfont{DejaVu Serif}
\setsansfont{DejaVu Sans}
\setmonofont{DejaVu Sans Mono}
''',
    'preamble': r'''
\usepackage[titles]{tocloft}
\cftsetpnumwidth {1.25cm}\cftsetrmarg{1.5cm}
\setlength{\cftchapnumwidth}{0.75cm}
\setlength{\cftsecindent}{\cftchapnumwidth}
\setlength{\cftsecnumwidth}{1.25cm}
''',
    'fncychap': r'\usepackage[Bjornstrup]{fncychap}',
    'printindex': r'\footnotesize\raggedright\printindex',
}
latex_show_urls = 'footnote'
