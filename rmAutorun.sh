#!/usr/bin/env bash
# rmAutorun.sh — remove eve-data-framework systemd service (Ubuntu/Debian)
set -euo pipefail

SERVICE_NAME="eve-data-framework"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "[rmAutorun] Stopping and disabling ${SERVICE_NAME}..."

systemctl stop    "${SERVICE_NAME}" 2>/dev/null || true
systemctl disable "${SERVICE_NAME}" 2>/dev/null || true

if [[ -f "${SERVICE_FILE}" ]]; then
    rm "${SERVICE_FILE}"
    echo "[rmAutorun] Removed ${SERVICE_FILE}"
else
    echo "[rmAutorun] ${SERVICE_FILE} not found — nothing to remove."
fi

systemctl daemon-reload
systemctl reset-failed 2>/dev/null || true

echo "[rmAutorun] Done. ${SERVICE_NAME} has been removed."
