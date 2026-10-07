# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- Incremental map engine (`IncrementalMapEngine`): keeps a SpatiaLite topology and
  dirty-queue sidecar so edits regenerate only the affected polygons instead of a
  full recompute. Still experimental and hidden from the GUI by default; set the
  `MAPPY_DEV` environment variable before launching QGIS to reveal the dock's
  "Use the incremental engine" toggle and its topology-tolerance setting
  (`just qgis-dev` does this for a local dev QGIS session).
- "Remove duplicate indicator points on recompute" dock option, off by default:
  Recompute Map's cleanup of per-polygon duplicate indicator points now only runs
  if explicitly enabled, and even then asks for confirmation (naming the count)
  before deleting anything and refuses outright if the count looks implausibly
  large relative to the points layer -- guards against a wrongly-selected lines
  layer producing malformed polygons that make real, distinct points look like
  duplicates and get silently, permanently deleted.

### Fixed

- Quick Project Setup's CRS parameter relied on QGIS's "ProjectCrs" magic default
  string, which fails parameter validation on QGIS < 3.32 when the parameter is
  omitted. Resolve to the project CRS explicitly instead, restoring support back
  to QGIS 3.30.

### Changed

- Raised `qgisMinimumVersion` from 3.16 to 3.30: the declared floor was untested and
  already broken by newer QGIS API usage adopted since (verified: 12 of 58 tests fail
  on 3.16, 10 fail on 3.24/3.28 due to unsupported scoped-enum access, down to 0 by
  3.30 after the CRS fix above). Re-verified on 3.30.3 (all tests pass).
- Multi-version QGIS testing moved from GitHub CI to a local `just test-compat`
  recipe. It runs the suite in the official `qgis/qgis` images: the 3.30
  minimum, the LTR, the stable release, and the nightly build. CI now tests
  only the reference Ubuntu-packaged QGIS.
- Tagged releases now fail early if the tag doesn't match the plugin version.
  The GitHub release notes are taken from this changelog.

## 0.4.1 - 2026-07-20

## 0.4.0 - 2026-07-20

### Added

- Assign-unit map tool for setting the map unit of selected polygons, with a searchable unit-picker dialog
- Quick-edit-mode tool, with map recompute gated behind a setting
- Durable, cross-layer unit colors, editable from the assign-unit dialog
- Default labeling for polygons on unit assignment
- Dedicated icons for the assign-unit and quick-edit-mode tools

### Changed

- Migrated to Qt6/PyQt6 and `uv` for dependency management
- Marked the plugin as non-experimental
- Polygon attribute and style now sync automatically on unit assignment

### Fixed

- Quick Project Setup unit-field bugs
- Plugin reload/restore bugs and duplicate join points
- A checkbox settings bug
- Pole-of-inaccessibility tolerance issue

## 0.3.2 - 2022-08-22

### Changed

- Baseline release predating this changelog; see git history for details on this and earlier versions
