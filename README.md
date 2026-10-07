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
- `just qgis` -- launch QGIS with this checkout on `QGIS_PLUGINPATH`, so the
  under-development plugin is picked up instead of an installed copy.
- `just qgis-dev` -- same, with `MAPPY_DEV=1` set so the dock also reveals
  still-experimental features (currently the incremental engine toggle and
  its topology-tolerance setting) that are otherwise hidden from users.
- `just test` -- run the test suite headlessly against your local QGIS
  install.
- `just test-compat` -- run it across QGIS versions in Docker (local only,
  see below).
- `just deploy` / `just package` -- install the plugin into your local QGIS
  profile, or build a distributable zip.
- `just bump patch|minor|major` -- bump the version, release the
  `CHANGELOG.md` "Unreleased" section, commit and tag.

## Packaging and releasing the plugin

### Releasing on GitHub

Releases are built by CI (`.github/workflows/tagged-release.yml`) whenever a
`v*` tag is pushed:

```sh
just bump patch                 # or minor / major: bumps versions, releases the
                                # CHANGELOG "Unreleased" section, commits, tags
git push origin master v0.4.2   # push the commit AND the new tag
```

`just bump` creates a lightweight tag, and `git push --follow-tags` skips
lightweight tags. Name the tag explicitly when you push.

The workflow takes these steps in order:
1. It checks that the tag matches `version=` in `mappy/metadata.txt` and in
   `pyproject.toml`. A tag pushed without `just bump` fails here.
2. It runs ruff and the test suite.
3. It builds `mappy-vX.Y.Z.zip`.
4. It creates the GitHub release. The release notes are that version's
   `CHANGELOG.md` section, followed by GitHub's auto-generated notes.

If any step fails, no release is created. If the failure was transient,
re-run the failed job from the Actions tab. A re-run uses the code at the
tagged commit, so it won't pick up a fix you commit afterwards. In that case,
move the tag to the commit with the fix and push it again:

```sh
git tag -f vX.Y.Z
git push origin :refs/tags/vX.Y.Z
git push origin vX.Y.Z
```

### Building the zip locally

#### Prerequisites

- `just`, `zip`, and `pyrcc5`. On Ubuntu, `pyrcc5` comes from
  `pyqt5-dev-tools`. On Arch/Manjaro, it comes from `python-pyqt5`.
- The project venv (`just setup-qgis`, or `uv sync`). It provides `pb_tool`
  and the `markdown` package used to render `INFO.md`.

#### Steps

1. **Set the version.** The zip name comes from
   `git describe --tags --abbrev=0`, the nearest tag *reachable from HEAD*.
   The version shown in QGIS comes from `version=` in `mappy/metadata.txt`.
   If you have commits since the last tag, run `just bump patch` (or
   `minor`/`major`) first. Otherwise the zip goes out under the old version
   number. Before bumping, check `git tag` to make sure the new version
   isn't already taken.
2. **Build:**

   ```sh
   just package
   ```

   This runs these steps in order:
   1. `clean` deletes `mappy/INFO.html` and `mappy/resources.py`.
   2. `update-info` renders `INFO.md` into `mappy/INFO.html`.
   3. `compile-resources` compiles `mappy/resources.qrc` (icons and
      `INFO.html`) into `mappy/resources.py` and patches its import for Qt6.
   4. `pb_tool zip` packages the files listed in `mappy/pb_tool.cfg`.
3. **Collect the output** from `mappy/zip_build/mappy-<tag>.zip`. A copy
   named `mappy/mappy.zip` is also written. Both paths are gitignored.
4. **Clean up the working tree.** Recompiling usually changes only the
   embedded timestamps in `mappy/resources.py`. If `git diff` shows nothing
   else, discard the change with `git checkout -- mappy/resources.py`.

To install the zip in QGIS, use *Plugins → Manage and Install Plugins →
Install from ZIP*.

#### Without `just`

These commands do the same as `just package`. Run them from the repository
root:

```sh
VERSION=$(git describe --tags --abbrev=0)
rm -f mappy/INFO.html mappy/resources.py
(cd scripts && uv run python render_info_to_html.py)
pyrcc5 mappy/resources.qrc -o mappy/resources.py
sed -i 's/from PyQt5 import QtCore/from qgis.PyQt import QtCore/' mappy/resources.py
(cd mappy && echo y | uv run pb_tool zip)
mkdir -p mappy/zip_build && cp mappy/mappy.zip mappy/zip_build/mappy-$VERSION.zip
```

If you add a new top-level module or directory to the plugin, also add it to
`python_files` or `extra_dirs` in `mappy/pb_tool.cfg`. Otherwise it is left
out of the zip.

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

## Testing across QGIS versions (local only)

CI tests a single reference QGIS: Ubuntu 24.04's apt package, currently
3.34. Tests across the declared range (`qgisMinimumVersion` to
`qgisMaximumVersion` in `mappy/metadata.txt`) are too heavy for CI, so run
them locally. Do this before a release, and after changing code that depends
on version-specific QGIS API. The tests run inside the official `qgis/qgis`
Docker images:

```sh
just test-compat                         # every version in COMPAT_TAGS
just test-compat "release-3_30 stable"   # only the listed versions
just test-qgis ltr                       # one version, full output
```

`COMPAT_TAGS` in the `justfile` lists these images:
- `release-3_30` is the declared minimum, and the only pinned version tag
  upstream still publishes.
- `ltr` is the current long-term release.
- `stable` is the current release.
- `latest` is a nightly build of QGIS master. A failure there may come from
  unreleased QGIS changes rather than a plugin bug.

If you raise `qgisMinimumVersion`, update the minimum tag in `COMPAT_TAGS`
too.

Each image takes about 8.5 GB of disk. Delete them with
`docker rmi qgis/qgis:<tag>` when you're done. The containers run as root, so
tests that rely on file permissions are skipped there.

# Troubleshooting

In case of troubles just drop an issue here on github!


