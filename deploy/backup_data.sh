#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${STOCK_DATA_APP_DIR:-/opt/stock-data}"
BACKUP_DIR="${STOCK_DATA_BACKUP_DIR:-}"

if [[ -z "${BACKUP_DIR}" ]]; then
  echo "STOCK_DATA_BACKUP_DIR 未配置，跳过备份。"
  exit 0
fi

mkdir -p "${BACKUP_DIR}/data" "${BACKUP_DIR}/data_market"
if command -v rsync >/dev/null 2>&1; then
  rsync -a --partial "${APP_DIR}/data/" "${BACKUP_DIR}/data/"
  rsync -a --partial "${APP_DIR}/data_market/" "${BACKUP_DIR}/data_market/"
else
  cp -a "${APP_DIR}/data/." "${BACKUP_DIR}/data/"
  cp -a "${APP_DIR}/data_market/." "${BACKUP_DIR}/data_market/"
fi
date -Iseconds >"${BACKUP_DIR}/last_success_at.txt"
