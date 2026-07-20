# Reproduce the release-CI test environment locally (see
# .github/workflows/pre-release.yml / tagged-release.yml), so behavior that
# only shows up under Ubuntu's apt-packaged (PyQt5-based) QGIS can be
# investigated without waiting on an actual GitHub Actions run.
#
# Build (defaults to the same Ubuntu/QGIS version CI uses):
#   docker build -t mappy-test .
# Build against an older Ubuntu release (and whatever QGIS/PyQt5 combination
# its universe repo carries) instead:
#   docker build --build-arg UBUNTU_VERSION=22.04 -t mappy-test:22.04 .
#
# Run the full suite (equivalent to `just test` in CI):
#   docker run --rm mappy-test
# Get a shell instead, e.g. to attach gdb after a crash:
#   docker run --rm -it mappy-test bash
#   gdb -batch -ex run -ex bt --args .venv/bin/python -m pytest mappy/tests -vs --order-dependencies

ARG UBUNTU_VERSION=24.04
FROM ubuntu:${UBUNTU_VERSION}

LABEL maintainer="Luca Penasa"

ENV TZ=Europe/Rome
ENV DEBIAN_FRONTEND=noninteractive
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# git: the justfile's `VERSION := `git describe --tags --abbrev=0`` is
#   evaluated eagerly for every `just` invocation, so real tag history (not
#   just a working tree) has to be present -- see the .git COPY below.
# gdb: for pulling a native backtrace out of a segfault (see usage above).
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-qgis \
    pyqt5-dev-tools \
    git \
    gdb \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# uv and just, matching the tools installed in .github/workflows/*.yml
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"
RUN curl --proto '=https' --tlsv1.2 -sSf https://just.systems/install.sh \
    | bash -s -- --to /usr/local/bin

WORKDIR /app
COPY . .

# Pin uv to the system interpreter for every uv command in this image (not
# just `uv venv`): left to its own preference, uv happily downloads and
# uses its own managed CPython build instead -- `uv venv --python` alone
# isn't enough, since a later plain `uv sync` re-resolves independently and
# silently recreates the venv against that other interpreter, undoing it.
ENV UV_PYTHON=/usr/bin/python3

# --system-site-packages so the venv can see the apt-installed qgis
# bindings; a plain `pip install` would otherwise fail on Ubuntu 24.04's
# PEP 668 "externally-managed-environment" system Python.
RUN uv venv --system-site-packages && uv sync

ENV QT_QPA_PLATFORM=offscreen
CMD ["uv", "run", "just", "test"]
