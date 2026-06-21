#!/usr/bin/env bash
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="${1:-/opt/stock-data}"
SERVICE_USER="${2:-${SUDO_USER:-$USER}}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "请使用 sudo 运行: sudo bash deploy/install.sh ${TARGET_DIR} ${SERVICE_USER}" >&2
  exit 1
fi

mkdir -p "${TARGET_DIR}"
for path in main.py run.py scheduler.py news_api.py config.py models.py requirements.txt market_calendar_overrides.json \
  market_data spiders parsers storage filters utils deploy; do
  rm -rf "${TARGET_DIR:?}/${path}"
  cp -R "${SOURCE_DIR}/${path}" "${TARGET_DIR}/${path}"
done
rm -f "${TARGET_DIR}/market_data/market_scoring.py" "${TARGET_DIR}/filters/news_enricher.py"
chmod +x "${TARGET_DIR}/deploy/backup_data.sh"

mkdir -p "${TARGET_DIR}/data" "${TARGET_DIR}/data_market" "${TARGET_DIR}/logs"
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${TARGET_DIR}"

if [[ ! -x "${TARGET_DIR}/venv/bin/python" ]]; then
  sudo -u "${SERVICE_USER}" python3 -m venv "${TARGET_DIR}/venv"
fi
sudo -u "${SERVICE_USER}" "${TARGET_DIR}/venv/bin/pip" install --upgrade pip
sudo -u "${SERVICE_USER}" "${TARGET_DIR}/venv/bin/pip" install -r "${TARGET_DIR}/requirements.txt"

if [[ ! -f /etc/stock-data.env ]]; then
  token="$(python3 -c 'import secrets; print(secrets.token_urlsafe(36))')"
  cat >/etc/stock-data.env <<EOF
DATA_COLLECTOR_ENV=production
TZ=Asia/Shanghai
DATA_API_TOKEN=${token}
MARKET_NETWORK_MODE=system_proxy
TRADE_CALENDAR_ALLOW_WEEKDAY_FALLBACK=0
TRADE_CALENDAR_OVERRIDES=${TARGET_DIR}/market_calendar_overrides.json
MARKET_BOOTSTRAP_TRADING_DAYS=20
MARKET_BOOTSTRAP_MINIMUM_DAYS=15
MARKET_HISTORY_PROVIDER=auto
MARKET_HISTORY_MIN_INTERVAL_SECONDS=1.0
STOCK_DATA_BACKUP_DIR=
PYTHONUNBUFFERED=1
EOF
  chmod 600 /etc/stock-data.env
  echo "已生成 /etc/stock-data.env，请妥善保存 DATA_API_TOKEN。"
else
  echo "保留现有 /etc/stock-data.env。"
fi

ensure_env_line() {
  local key="$1"
  local value="$2"
  if ! grep -q "^${key}=" /etc/stock-data.env; then
    printf '%s=%s\n' "${key}" "${value}" >>/etc/stock-data.env
  fi
}

if ! grep -q '^DATA_API_TOKEN=' /etc/stock-data.env; then
  token="$(python3 -c 'import secrets; print(secrets.token_urlsafe(36))')"
  printf 'DATA_API_TOKEN=%s\n' "${token}" >>/etc/stock-data.env
fi
ensure_env_line DATA_COLLECTOR_ENV production
ensure_env_line TZ Asia/Shanghai
ensure_env_line MARKET_NETWORK_MODE system_proxy
ensure_env_line TRADE_CALENDAR_ALLOW_WEEKDAY_FALLBACK 0
ensure_env_line TRADE_CALENDAR_OVERRIDES "${TARGET_DIR}/market_calendar_overrides.json"
ensure_env_line MARKET_BOOTSTRAP_TRADING_DAYS 20
ensure_env_line MARKET_BOOTSTRAP_MINIMUM_DAYS 15
ensure_env_line MARKET_HISTORY_PROVIDER auto
ensure_env_line MARKET_HISTORY_MIN_INTERVAL_SECONDS 1.0
ensure_env_line STOCK_DATA_BACKUP_DIR ""
ensure_env_line PYTHONUNBUFFERED 1
chmod 600 /etc/stock-data.env

for service in stock-data-api.service stock-data-bootstrap.service stock-data-collector.service stock-data-backup.service stock-data-backup.timer; do
  sed \
    -e "s|__APP_DIR__|${TARGET_DIR}|g" \
    -e "s|__SERVICE_USER__|${SERVICE_USER}|g" \
    "${SOURCE_DIR}/deploy/systemd/${service}" >"/etc/systemd/system/${service}"
done

systemctl daemon-reload
systemctl enable stock-data-api.service
systemctl restart stock-data-api.service
systemctl enable stock-data-bootstrap.service stock-data-collector.service
systemctl restart --no-block stock-data-bootstrap.service stock-data-collector.service
systemctl enable --now stock-data-backup.timer
systemctl --no-pager --full status stock-data-api.service stock-data-bootstrap.service stock-data-collector.service || true

echo
echo "部署完成。API: http://<服务器IP>:8765/v1/manifest"
echo "令牌文件: /etc/stock-data.env"
echo "历史回填已在后台启动；先查看 /v1/health 的 history_bootstrap.is_ready，再开始正式分析。"
echo "建议在云防火墙中只允许你的固定公网 IP 访问 8765，或配置 HTTPS 反向代理。"
