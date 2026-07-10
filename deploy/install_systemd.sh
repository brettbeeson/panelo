#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="${SERVICE_NAME:-panelo}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKDIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
TEMPLATE_PATH="${SCRIPT_DIR}/panelo.service.template"
TARGET_PATH="/etc/systemd/system/${SERVICE_NAME}.service"

if ! command -v envsubst >/dev/null 2>&1; then
  echo "Missing required command: envsubst" >&2
  echo "Install it with your distro package manager (often package 'gettext-base')." >&2
  exit 1
fi

if [[ ! -f "${TEMPLATE_PATH}" ]]; then
  echo "Missing template: ${TEMPLATE_PATH}" >&2
  exit 1
fi

if [[ -n "${SUDO_USER:-}" ]]; then
  APP_USER="${APP_USER:-${SUDO_USER}}"
else
  APP_USER="${APP_USER:-${USER}}"
fi
APP_GROUP="${APP_GROUP:-$(id -gn "${APP_USER}")}"
RUNS_ROOT="${PANELO_RUNS_ROOT:-${WORKDIR}/runs}"
EXEC_START="${EXEC_START:-${WORKDIR}/.venv/bin/panelo-web}"

if [[ ! -x "${EXEC_START}" ]]; then
  echo "ExecStart target is not executable: ${EXEC_START}" >&2
  echo "Run 'uv sync' first, or override EXEC_START when running install script." >&2
  exit 1
fi

export APP_USER APP_GROUP WORKDIR RUNS_ROOT EXEC_START

TMP_FILE="$(mktemp)"
cleanup() {
  rm -f "${TMP_FILE}"
}
trap cleanup EXIT

envsubst '${APP_USER} ${APP_GROUP} ${WORKDIR} ${RUNS_ROOT} ${EXEC_START}' < "${TEMPLATE_PATH}" > "${TMP_FILE}"

sudo install -m 0644 "${TMP_FILE}" "${TARGET_PATH}"
sudo systemctl daemon-reload


echo "Installed ${TARGET_PATH}"
echo "ExecStart: ${EXEC_START}"
echo "Run: sudo systemctl restart ${SERVICE_NAME}"
echo "Enable: sudo systemctl enable ${SERVICE_NAME}"
