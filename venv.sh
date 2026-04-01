#!/usr/bin/env bash
# venv.sh — create and/or activate the project virtual environment.
#
# Must be SOURCED so the activation applies to the calling shell:
#   source venv.sh
#   . venv.sh

# Detect direct execution and bail out with a clear message.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    echo "[venv] ERROR: this script must be sourced, not executed directly."
    echo "  Run:  source venv.sh"
    echo "   or:  . venv.sh"
    exit 1
fi

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
