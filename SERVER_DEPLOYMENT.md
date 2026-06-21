# 服务器部署说明

本部署包只包含客观数据采集、存储、数学计算和只读 API，不包含三个本地推荐 skill、Codex、模型或任何 AI 功能。

## 服务器要求

- Linux，推荐 Ubuntu 22.04/24.04。
- Python 3.10 或更高版本。
- 可用磁盘建议至少 50 GB；原始数据按日期永久保存。
- 云防火墙只允许你的固定公网 IP 访问 API 端口，或配置 HTTPS。

## 构建部署包

在本地项目根目录运行：

```bash
venv/bin/python deploy/build_release.py
```

生成：

```text
dist/stock-data-server-YYYYMMDD-HHMM.tar.gz
```

这个压缩包就是需要上传到服务器的全部服务器代码。本地的 `skills/`、`client/` 和 Codex 不需要上传。

## 上传和安装

```bash
scp dist/stock-data-server-*.tar.gz 用户名@服务器IP:/tmp/
ssh 用户名@服务器IP
cd /tmp
tar -xzf stock-data-server-*.tar.gz
cd stock-data-server-*
sudo bash deploy/install.sh /opt/stock-data 用户名
```

安装脚本会：

- 复制服务器代码到 `/opt/stock-data`。
- 创建 Python 虚拟环境并安装依赖。
- 创建永久日期数据目录。
- 生成只读 API 令牌。
- 后台启动一次性历史回填：保存最近 `20` 个已完成交易日的真实全市场日线，至少 `15` 日完整才标记为可用。
- 安装并启动 `stock-data-api` 和 `stock-data-collector` 两个 systemd 服务。
- 安装每日 23:30 的备份定时器；未配置备份目录时安全跳过。

## 查看令牌和状态

```bash
sudo cat /etc/stock-data.env
sudo systemctl status stock-data-api stock-data-bootstrap stock-data-collector
sudo journalctl -u stock-data-bootstrap -f
sudo journalctl -u stock-data-api -u stock-data-collector -f
```

历史回填会按单一数据源限速执行，通常需要一段时间。每只股票的下载结果都有检查点，网络中断或服务器重启后再次运行只补缺失部分，不会从头重复抓取：

```bash
sudo systemctl restart stock-data-bootstrap.service
```

回填期间 API 已可访问，但正式分析前应确认 `/v1/health` 返回的 `history_bootstrap.is_ready` 为 `true`，且 `completed_dates` 至少有 `15` 个交易日。系统默认抓取 `20` 个交易日，因为 `15 日涨跌幅` 需要至少 `16` 个收盘点，`MA20` 需要 `20` 个。同一只股票的一次历史请求会返回整个日期区间，因此从 15 调到 20 不增加每只股票的请求次数。

历史回填只创建真实日线和来源可返回的历史涨跌停池，不会伪造过去的竞价、尾盘分时、板块资金流或新闻。过去的竞价和尾盘分时无法在部署后补造，只能从部署后的每个交易日持续积累。

建议把 `/etc/stock-data.env` 里的 `STOCK_DATA_BACKUP_DIR` 设为另一块数据盘或已挂载的远程存储目录，然后执行：

```bash
sudo systemctl start stock-data-backup.service
sudo systemctl status stock-data-backup.service stock-data-backup.timer
```

## 验证 API

```bash
TOKEN='从 /etc/stock-data.env 取得的 DATA_API_TOKEN'
curl -H "Authorization: Bearer ${TOKEN}" http://127.0.0.1:8765/v1/health
curl -H "Authorization: Bearer ${TOKEN}" http://127.0.0.1:8765/v1/manifest
```

服务器原始新闻、公告和每个关键市场快照永久按日期保存。API 默认提供最近 15 天的新闻/公告索引，历史数据仍可保留并后续扩展日期查询。

首次启动时，巨潮公告和发改委来源会按日期能力尝试补采最近 `15` 天；财联社和东方财富快讯若上游接口只返回最新列表，就只保存接口真实返回的内容。系统保留实际来源时间，不会把当前新闻伪装成历史新闻。

## 本地连接服务器

本地项目设置：

```bash
export STOCK_DATA_SERVER='http://服务器IP:8765'
export STOCK_DATA_TOKEN='服务器 DATA_API_TOKEN'
```

然后测试任意一个模式；三个 skill 共用同一份本地服务器缓存，不需要为了初始化连续运行三遍：

```bash
venv/bin/python client/server_data_client.py sync --mode morning
```

三个 skill 的入口都会更新同一个 `data_server_cache/`。日期数据按交易日期、数据版本和快照 ID 保存到 `data_server_cache/archive/YYYY-MM-DD/`，共用的当前索引为 `data_server_cache/latest_context.json`。

按指定日期完整回补服务器归档：

```bash
venv/bin/python client/server_data_client.py archive-date --date 2026-06-18
```

API 默认提供最近 15 天索引，但显式日期查询和 `archive-date` 可以读取服务器永久保存的更早日期文件。

## 安全建议

直接使用服务器 IP 时，至少在云安全组中仅允许你的公网 IP 访问 TCP 8765。若跨公网长期使用，应在 API 前配置 Nginx/Caddy HTTPS，避免令牌通过明文 HTTP 传输。

## 周一实时验收

周末可以完成部署、历史数据、接口和分页验证。交易时段还需确认：

- `09:15-09:45` 竞价/早盘关键快照。
- `14:30-15:00` 尾盘关键快照。
- 快照实际时间、股票数量和接口完整度。
