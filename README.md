# Mappy QGIS plugin


[![Doc Status](https://readthedocs.org/projects/mappy/badge/?version=master)](https://mappy.readthedocs.io/en/master/?badge=master)
[![Pre Release Build](https://github.com/europlanet-gmap/mappy/actions/workflows/pre-release.yml/badge.svg)](https://github.com/europlanet-gmap/mappy/actions/workflows/pre-release.yml)




This QGIS plugin collects several useful algorithms to easily generate geological 
maps starting from contacts and points. 

> This plugin was developed as the result of the PLANMAP project (N 776276) and is now maintained thanks to the
> EUROPLANET-GMAP infrastructure (N 871149) and supported by the JANUS camera team of the JUICE mission (ASI-INAF 2018-25-HH.0). 

# Documentation

Documentation is hosted by [Readthedocs](https://mappy.readthedocs.io).

# Development

Common dev tasks are `just` recipes -- run `just` (no arguments) to list
them all. A few worth knowing about:

- `just setup-qgis` -- create the local `.venv` with access to the system
  QGIS/PyQt bindings (needed once per machine).
- `just test` -- run the test suite headlessly against your local QGIS
  install.
- `just deploy` / `just package` -- install the plugin into your local QGIS
  profile, or build a distributable zip.
- `just bump patch|minor|major` -- bump the version, release the
  `CHANGELOG.md` "Unreleased" section, commit and tag.

## Testing against CI's QGIS (Docker)

The release CI (`.github/workflows/`) runs against Ubuntu's apt-packaged
QGIS, which is still PyQt5-based -- likely a different QGIS/Qt combination
than whatever you have installed locally. Behavior that only shows up under
that specific environment (see the `Dockerfile` for the full story behind
why this exists) can be reproduced and debugged locally instead of pushing
and waiting on a GitHub Actions run:

```sh
just docker-test              # build (if needed) and run the full suite
just docker-test 22.04        # ...against a different Ubuntu/QGIS combo
just docker-shell              # interactive shell instead, e.g. to attach
                                # gdb after a crash
```

Note that the Ubuntu version has to ship a system Python satisfying this
project's `requires-python` floor (currently 3.11+) for its `uv sync` step
to succeed -- see the `Dockerfile` header for which releases actually work.

# Troubleshooting

In case of troubles just drop an issue here on github!


