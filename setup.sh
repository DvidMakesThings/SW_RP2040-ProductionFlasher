#!/usr/bin/env bash

# Setup script: ensures system deps for pycairo, creates/activates venv, installs pycairo (if needed), then requirements.
# Works with bash/zsh. Run: ./setup.sh

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
PY="$VENV_DIR/bin/python"
PIP="$VENV_DIR/bin/pip"

is_command() { command -v "$1" >/dev/null 2>&1; }

pkg_install() {
  # Try common package managers to install pkg-config and cairo dev headers
  if is_command apt; then
    sudo apt update
    sudo apt install -y pkg-config libcairo2-dev
  elif is_command dnf; then
    sudo dnf install -y pkgconf-pkg-config cairo-devel
  elif is_command yum; then
    sudo yum install -y pkgconf-pkg-config cairo-devel
  elif is_command pacman; then
    sudo pacman -Sy --noconfirm pkgconf cairo
  elif is_command zypper; then
    sudo zypper install -y pkgconf-pkg-config cairo-devel
  else
    echo "[WARN] Unknown package manager. Please install pkg-config + Cairo dev headers manually." >&2
  fi
}

ensure_venv() {
  if [ ! -d "$VENV_DIR" ]; then
    echo "[INFO] Creating virtual environment at $VENV_DIR"
    python3 -m venv "$VENV_DIR"
  else
    echo "[INFO] Using existing virtual environment at $VENV_DIR"
  fi
}

upgrade_tools() {
  "$PY" -m pip install --upgrade pip setuptools wheel
}

have_pycairo() {
  "$PY" - <<'PY'
import sys
try:
    import cairo
except Exception as e:
    sys.exit(1)
sys.exit(0)
PY
}

install_pycairo() {
  echo "[INFO] Installing pycairo (and system deps if missing)"
  if ! is_command pkg-config; then
    echo "[INFO] pkg-config not found; attempting to install system deps"
    pkg_install || true
  fi
  # Try install pycairo; if it fails, hint about system deps
  if ! "$PY" -m pip install pycairo; then
    echo "[ERROR] pycairo install failed. Ensure pkg-config and Cairo development headers are installed." >&2
    exit 1
  fi
}

install_requirements() {
  echo "[INFO] Installing project requirements"
  "$PY" -m pip install -r "$PROJECT_DIR/requirements.txt"
}

main() {
  ensure_venv
  upgrade_tools
  if ! have_pycairo; then
    install_pycairo
  else
    echo "[INFO] pycairo already available in venv"
  fi
  install_requirements
  # If the script is sourced, activate the venv in the current shell; otherwise, print instructions
  if [ -n "${BASH_SOURCE:-}" ] && [ "${BASH_SOURCE[0]}" != "$0" ]; then
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
    echo "[SUCCESS] Environment ready and venv activated: $VIRTUAL_ENV"
  else
    echo "[SUCCESS] Environment ready. Activate with: source $VENV_DIR/bin/activate"
  fi
}

main "$@"
