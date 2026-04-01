#!/usr/bin/env bash
# venv.sh — create and/or activate the project virtual environment.
#
# This script must be SOURCED, not executed directly:
#   source venv.sh
#   . venv.sh
#
# Running it directly (bash venv.sh / ./venv.sh) will create the venv and
# install dependencies but the activation will have no effect on your shell.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/.venv"

if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    echo "[venv] Creating virtual environment at ${VENV_DIR}..."
    python3 -m venv "${VENV_DIR}"
    echo "[venv] Installing dependencies from requirements.txt..."
    "${VENV_DIR}/bin/pip" install --quiet --upgrade pip
    "${VENV_DIR}/bin/pip" install --quiet -r "${SCRIPT_DIR}/requirements.txt"
    echo "[venv] Done."
fi

source "${VENV_DIR}/bin/activate"
