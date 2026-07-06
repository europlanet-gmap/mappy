VERSION := `git describe --tags --abbrev=0`

# Start QGIS with the project root on QGIS_PLUGINPATH so the under-dev plugin is found
qgis:
    QGIS_PLUGINPATH={{justfile_directory()}} qgis

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

# Deploy the plugin locally using pb_tool
deploy: clean update-info compile-resources
    cd mappy && pb_tool deploy -y

# Build a distributable zip archive
package: clean update-info compile-resources
    @echo "VERSION: {{VERSION}}"
    cd mappy && \
    pb_tool zip && \
    cp zip_build/mappy.zip zip_build/mappy-{{VERSION}}.zip

# Run the test suite (headless, offscreen Qt platform)
test:
    QT_QPA_PLATFORM=offscreen pytest mappy/tests -vs --order-dependencies

# Live-reload documentation server
docs:
    uv run sphinx-autobuild docs/source docs/build
