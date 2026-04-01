#!/usr/bin/env bash
# addAutorun.sh — install eve-data-framework as a systemd service (Ubuntu/Debian)
set -euo pipefail

SERVICE_NAME="eve-data-framework"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUN_USER="${SUDO_USER:-$USER}"

# Prefer the venv interpreter if one exists alongside this script.
if [[ -x "${REPO_DIR}/.venv/bin/python" ]]; then
    PYTHON="${REPO_DIR}/.venv/bin/python"
elif [[ -x "${REPO_DIR}/venv/bin/python" ]]; then
    PYTHON="${REPO_DIR}/venv/bin/python"
else
    PYTHON="$(command -v python3)"
fi

echo "[addAutorun] Service name : ${SERVICE_NAME}"
echo "[addAutorun] Repo directory: ${REPO_DIR}"
echo "[addAutorun] Python        : ${PYTHON}"
echo "[addAutorun] Run as user   : ${RUN_USER}"

cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=EVE Data Framework
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${RUN_USER}
WorkingDirectory=${REPO_DIR}
ExecStart=${PYTHON} ${REPO_DIR}/main.py
Restart=on-failure
RestartSec=10

# Keep stdout/stderr in journald (journalctl -u ${SERVICE_NAME} -f)
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "[addAutorun] Wrote ${SERVICE_FILE}"

systemctl daemon-reload
systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"

echo "[addAutorun] Done. Service is enabled and running."
echo "  Check status : sudo systemctl status ${SERVICE_NAME}"
echo "  Follow logs  : sudo journalctl -u ${SERVICE_NAME} -f"
