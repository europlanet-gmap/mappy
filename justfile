VERSION := `git describe --tags --abbrev=0`

# Show available recipes
default:
    @just --list

# Start QGIS with the project root on QGIS_PLUGINPATH so the under-dev plugin is found
qgis:
    QGIS_PLUGINPATH={{justfile_directory()}} qgis

# Same as `qgis`, but with MAPPY_DEV=1 so the dock reveals still-experimental
# features (e.g. the incremental engine toggle) normally hidden from users
qgis-dev:
    QGIS_PLUGINPATH={{justfile_directory()}} MAPPY_DEV=1 qgis

# Create venv with access to system site-packages (for QGIS, PyQt6, osgeo, etc.)
# then install dev/test extras on top via uv.
setup-qgis:
    #!/usr/bin/env bash     
    set -euo pipefail

    SYS_SITE_PACKAGES="/usr/lib/python3.14/site-packages"

    if [ ! -d "$SYS_SITE_PACKAGES/qgis" ]; then
        echo "Error: QGIS not found at $SYS_SITE_PACKAGES/qgis"
        exit 1
    fi

    echo "Creating venv with system site-packages..."
    uv venv --system-site-packages --clear  

    echo "Installing dev dependencies..."
    uv sync

    echo "Done. QGIS and all system packages are now visible to the venv."

clean-venv:
    rm -rf .venv
    echo "Removed .venv."

# Remove generated build artifacts from the plugin directory
clean:
    cd mappy && \
    rm -fr providers/__pycache__ && \
    rm -f INFO.html resources.py

# Compile resources.qrc → resources.py and patch the PyQt5 import for Qt6 compatibility
compile-resources:
    pyrcc5 mappy/resources.qrc -o mappy/resources.py
    sed -i 's/from PyQt5 import QtCore/from qgis.PyQt import QtCore/' mappy/resources.py

# Render INFO.md → INFO.html via the render script
update-info:
    cd scripts && ./render_info_to_html.py

# Stamp the current git tag into mappy/metadata.txt
update-version:
    sed -i 's/version=[.a-zA-Z0-9]*/version={{VERSION}}/g' mappy/metadata.txt

# Bump the version (major, minor, patch) in pyproject.toml and mappy/metadata.txt,
# release the Unreleased changelog section, then commit and tag.
bump version_kind:
    #!/usr/bin/env bash
    set -euo pipefail

    current=$(grep -m1 '^version = ' pyproject.toml | sed -E 's/version = "([^"]+)"/\1/')
    IFS='.' read -r major minor patch <<< "$current"
    case "{{version_kind}}" in
        major) major=$((major + 1)); minor=0; patch=0 ;;
        minor) minor=$((minor + 1)); patch=0 ;;
        patch) patch=$((patch + 1)) ;;
        *) echo "Unknown version kind '{{version_kind}}' (expected major, minor, or patch)" >&2; exit 1 ;;
    esac
    new_version="$major.$minor.$patch"
    echo "Bumping {{version_kind}} version: $current -> $new_version"

    uv run kacl-cli verify

    sed -i "s/^version = \".*\"/version = \"$new_version\"/" pyproject.toml
    sed -i "s/version=[.a-zA-Z0-9]*/version=$new_version/g" mappy/metadata.txt
    uv lock

    just release-changelog "$new_version"

    git add pyproject.toml mappy/metadata.txt CHANGELOG.md uv.lock
    git commit -m "Bump version to $new_version and update changelog"
    git tag "v$new_version"
    echo "Version bump and changelog update complete."

# Release the Unreleased changelog section under the given version
release-changelog version:
    @echo "Releasing changelog for version {{version}}..."
    uv run kacl-cli release {{version}} -m --allow-no-changes

# Deploy the plugin locally using pb_tool
deploy: clean update-info compile-resources
    cd mappy && uv run pb_tool deploy -y

# Build a distributable zip archive
package: clean update-info compile-resources
    @echo "VERSION: {{VERSION}}"
    cd mappy && \
    echo y | uv run pb_tool zip && \
    mkdir -p zip_build && \
    cp mappy.zip zip_build/mappy-{{VERSION}}.zip

# Run the test suite (headless, offscreen Qt platform)
test:
    QT_QPA_PLATFORM=offscreen pytest mappy/tests -vs --order-dependencies

# Build the Docker image that mirrors the release CI's test environment (see
# Dockerfile for the full rationale). Defaults to the same Ubuntu/QGIS
# version CI uses; pass a different release to try that combination instead,
# e.g. `just docker-build 22.04` -- see the Dockerfile header for which
# releases actually work (the system Python has to satisfy requires-python).
docker-build ubuntu_version="24.04":
    docker build --build-arg UBUNTU_VERSION={{ubuntu_version}} -t mappy-test:{{ubuntu_version}} .

# Run the full test suite inside that Docker image -- this is how CI-only
# failures under Ubuntu's PyQt5-based QGIS (unlike this machine's Qt6 one)
# get reproduced and debugged locally instead of guessing from CI logs.
docker-test ubuntu_version="24.04": (docker-build ubuntu_version)
    docker run --rm mappy-test:{{ubuntu_version}}

# Get an interactive shell in that image instead, e.g. to attach gdb after a
# crash: gdb -batch -ex run -ex "bt full" --args .venv/bin/python -m pytest mappy/tests -vs --order-dependencies
docker-shell ubuntu_version="24.04": (docker-build ubuntu_version)
    docker run --rm -it mappy-test:{{ubuntu_version}} bash

# qgis/qgis Docker tags the local compatibility matrix covers: the declared
# minimum (qgisMinimumVersion in mappy/metadata.txt -- the only pinned tag
# upstream still publishes), the current LTR and stable releases, and the
# master/nightly build. Each image is ~8.5 GB.
COMPAT_TAGS := "release-3_30 ltr stable latest"

# Too heavy for CI, which only tests the reference Ubuntu-packaged QGIS (see
# .github/workflows/): run this locally before a release or after touching
# version-sensitive QGIS API.
#
# The checkout is mounted read-only and copied inside the container, so the
# root-owned files the run creates never land in the working tree. Only the
# bare test dependencies are installed (not `uv sync`): older images' Python
# is below this project's requires-python, and the plugin loads through
# QGIS's plugin path in conftest.py rather than as an installed package.
# pip options are passed as env vars, not flags (e.g. --break-system-packages):
# newer images mark their Python as externally-managed (PEP 668), but
# release-3_30's pip predates those flags and aborts on them, while ignoring
# the env vars.
#
# Run the test suite inside one qgis/qgis Docker image, e.g. `just test-qgis ltr`
test-qgis tag:
    @docker run --rm -v {{justfile_directory()}}:/mnt/src:ro \
        -e QT_QPA_PLATFORM=offscreen -e PIP_BREAK_SYSTEM_PACKAGES=1 -e PIP_ROOT_USER_ACTION=ignore -e PYTHONDONTWRITEBYTECODE=1 \
        qgis/qgis:{{tag}} sh -ec ' \
            mkdir /src && tar -C /mnt/src --exclude=./.git --exclude=./.venv -cf - . | tar -C /src -xf - && cd /src; \
            python3 -c "from qgis.core import Qgis; print(\"QGIS\", Qgis.version())"; \
            pip3 install -q pytest pytest-order pytest-dependency numpy; \
            python3 -m pytest mappy/tests -q -p no:cacheprovider --order-dependencies -rfE'

# Keeps going past failures and exits non-zero if any version failed. A
# `latest` failure may be upstream breakage in unreleased QGIS rather than a
# plugin bug.
#
# Run the suite on every COMPAT_TAGS QGIS image (or the given ones) and summarize
test-compat tags=COMPAT_TAGS:
    #!/usr/bin/env bash
    set -uo pipefail
    failed=()
    for tag in {{tags}}; do
        echo "=== qgis/qgis:$tag ==="
        just test-qgis "$tag" || failed+=("$tag")
    done
    if [ ${#failed[@]} -eq 0 ]; then
        echo "All passed: {{tags}}"
    else
        echo "FAILED on: ${failed[*]}" >&2
        exit 1
    fi

# Live-reload documentation server
docs:
    uv run sphinx-autobuild docs/source docs/build
