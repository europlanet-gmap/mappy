# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

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
