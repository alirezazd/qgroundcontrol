# QGroundControl Development Commands
# Install (requires just >=1.30 for home_directory()):
#   python tools/setup/install_python.py dev   (recommended; pulls rust-just into .venv)
#   brew install just / cargo install just / pipx install rust-just
# `apt install just` on Ubuntu ships 1.21 which is too old.

# Configuration from build-config.json
qt_version := `python3 ./tools/setup/read_config.py --get qt.version 2>/dev/null || echo "6.11.1"`
cmake_min_version := `python3 ./tools/setup/read_config.py --get build.cmake_minimum_version 2>/dev/null || echo "3.25"`
gstreamer_version := `python3 ./tools/setup/read_config.py --get gstreamer.version.default 2>/dev/null || echo "1.28.4"`
qt_dir := env_var_or_default("QT_DIR", home_directory() / "Qt" / qt_version / "gcc_64")
# Defaults are this fork's: a custom build renames the binary through
# QGC_APP_NAME, so the stock name would point at a file that is never built.
# All three take an environment override, so an upstream layout still works
# with BUILD_DIR=build BUILD_TYPE=Debug APP_NAME=QGroundControl.
build_type := env_var_or_default("BUILD_TYPE", "Release")
build_dir := env_var_or_default("BUILD_DIR", "build-v514")
app_name := env_var_or_default("APP_NAME", "32RavenQGC")
# Use all cores by default; override with JOBS=N.
jobs := env_var_or_default("JOBS", `python3 -c "import os; print(os.cpu_count() or 4)" 2>/dev/null || echo 4`)

# Default: show available commands
default:
    @just --list --unsorted

# ─────────────────────────────────────────────────────────────────────────────
# Setup
# ─────────────────────────────────────────────────────────────────────────────

# Preflight the host, read-only (TARGET=build|test|lint|all); exits 1 where a recipe is blocked
doctor target=env_var_or_default("TARGET", "all"):
    python3 ./tools/doctor.py --target {{target}} --qt-root {{qt_dir}} -B {{build_dir}} -t {{build_type}} --app-name {{app_name}}

# Install system dependencies; auto-detects apt/dnf/pacman/brew (forwards ARGS: --dry-run, --category qt, ...)
install-deps *ARGS:
    @echo "Installing dependencies (requires sudo)..."
    python3 ./tools/setup/install_dependencies {{ARGS}}

alias deps := install-deps

# Initialize git submodules
submodules:
    git submodule update --init --recursive

# ─────────────────────────────────────────────────────────────────────────────
# Build
# ─────────────────────────────────────────────────────────────────────────────

# Configure CMake build
configure: submodules
    python3 ./tools/configure.py -B {{build_dir}} -t {{build_type}} --testing --qt-root {{qt_dir}}

# Build the project
build:
    cmake --build {{build_dir}} --config {{build_type}} --parallel {{jobs}} --target {{app_name}}

# Configure and build Release
release:
    python3 ./tools/configure.py -B {{build_dir}} --release --qt-root {{qt_dir}}
    cmake --build {{build_dir}} --config Release --parallel {{jobs}}

# Clean build directory (forwards to tools/clean.py; pass --cache, --all, --dry-run)
clean *ARGS:
    ./tools/clean.py {{ARGS}}

# Clean, configure, and build
rebuild: clean configure build

# Full setup: install-deps, submodules, configure, build
setup: install-deps submodules configure build

# ─────────────────────────────────────────────────────────────────────────────
# Quality
# ─────────────────────────────────────────────────────────────────────────────

# Run unit tests (matches CI label filters; override with `LABELS=... EXCLUDE=... just test`)
test labels=env_var_or_default("LABELS", "Unit|Integration") exclude=env_var_or_default("EXCLUDE", "Flaky|Network"):
    cd {{build_dir}} && ctest --output-on-failure -L "{{labels}}" -LE "{{exclude}}"

# Lint what you changed: uncommitted, untracked, and commits not yet upstream
lint:
    python3 ./tools/pre_commit.py --changed

# What CI runs: every hook over every file. Advisory there (failures go to a PR
# comment, the job passes); here the fixer hooks rewrite files, so run it on a
# clean tree and expect upstream's own findings.
lint-all:
    python3 ./tools/pre_commit.py

# Check code formatting (no changes)
format:
    python3 ./tools/analyze.py --tool clang-format

# Format code (apply fixes)
format-fix:
    python3 ./tools/analyze.py --tool clang-format --fix

# Run static analysis
analyze:
    python3 ./tools/analyze.py

# Generate coverage report
coverage:
    python3 ./tools/coverage.py

# Run lint + test
check: lint test

# ─────────────────────────────────────────────────────────────────────────────
# Run & Deploy
# ─────────────────────────────────────────────────────────────────────────────

# Build what changed, then launch. The dependency is free when nothing has:
# ninja reports no work and the binary starts immediately.
# WSLg (/dev/dxg present): Fedora's Mesa ships the D3D12 GPU driver but never
# selects it on its own, so the app renders on llvmpipe. WSL_GPU=1 opts into
# D3D12 -- opt-in only, because Mesa 26.2's d3d12 driver deadlocks the render
# thread on itself (pb_slab reclaim inside alloc) after a while, leaving a
# window that cannot be closed.
# A session started before `usermod -aG dialout` lacks the group until the
# login is redone (VS Code terminals inherit it from a server that is older
# still); sg re-enters with it, so serial ports open without a relogin.
run: build
    #!/usr/bin/env bash
    set -euo pipefail
    if [ -e /dev/dxg ] && [ "${WSL_GPU:-0}" = 1 ] && [ -z "${GALLIUM_DRIVER:-}" ]; then
        export GALLIUM_DRIVER=d3d12
    fi
    app=./{{build_dir}}/{{build_type}}/{{app_name}}
    # WSL: forward every usbipd-bound USB device (attachments die with the VM).
    python3 ./tools/setup/wsl_usb_attach.py
    for group in dialout uucp; do
        if getent group "$group" | cut -d: -f4 | tr ',' '\n' | grep -qx "$USER" && ! id -nG | grep -qw "$group"; then
            exec sg "$group" -c "exec $app"
        fi
    done
    exec "$app"

# Build documentation
docs:
    npm run docs:build

# Build using Docker (Ubuntu)
docker:
    ./deploy/docker/run-docker.sh ubuntu

# ─────────────────────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────────────────────

# Show build configuration
info:
    @echo "Qt version:  {{qt_version}}"
    @echo "Qt dir:      {{qt_dir}}"
    @echo "CMake min:   {{cmake_min_version}}"
    @echo "GStreamer:   {{gstreamer_version}}"
    @echo "Build type:  {{build_type}}"
    @echo "Build dir:   {{build_dir}}"
    @echo "Jobs:        {{jobs}}"

# Check dependency versions
check-deps:
    python3 ./tools/check_deps.py

# Clean build, caches, and generated files
distclean:
    ./tools/clean.py --all
    rm -rf node_modules
