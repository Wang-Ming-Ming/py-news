# A 股客观数据采集与只读接口

服务器只负责采集、标准化、客观数学计算、按日期保存和提供只读 API。服务器不包含 AI，不判断主线、公告风险、产业逻辑或买卖结论；这些由本地 Codex 和三个 skill 完成。

## 当前数据源

### 财联社 `cls`

抓取财联社滚动电报。

适合做实时市场新闻源，包括：

- 公司快讯
- 产业链消息
- 海外市场消息
- 突发事件
- 机构研报摘要

### 巨潮资讯 `cninfo`

抓取上市公司公告。

适合做公司事件新闻源，包括：

- 回购、增持、减持
- 并购重组、定增、股权变动
- 业绩预告、业绩快报
- 重大合同、中标、担保、诉讼
- 监管、问询、风险提示

### 国家发展改革委 `ndrc`

抓取发改委新闻、通知公告、司局/地方动态。

适合做政策新闻源，包括：

- 宏观政策
- 产业政策
- 能源、价格、投资、消费政策
- 重大项目
- 民营经济、数字经济、新质生产力相关消息

### 东方财富全球财经快讯 `eastmoney_global`

通过 AKShare 抓取东方财富全球财经快讯。

适合做全球重大新闻源，包括：

- 海外市场和宏观消息
- 央行、利率、汇率、商品相关消息
- 全球公司重大事件
- 地缘政治和国际政策消息

## 是否还需要其他新闻源

当前 4 个源已经能覆盖一个股票分析系统的基础输入：

- `cls` 覆盖实时市场消息
- `cninfo` 覆盖上市公司公告
- `ndrc` 覆盖宏观政策方向
- `eastmoney_global` 覆盖全球重大财经新闻

后续如果要增强，可以再加这些源：

- 证监会：监管政策、处罚、IPO/再融资政策
- 上交所/深交所/北交所：问询函、监管函、交易所公告
- 央行：货币政策、流动性、金融统计
- 工信部：半导体、AI、机器人、新能源车、工业政策
- 商务部/财政部：消费、外贸、财政补贴政策

但第一版不建议继续扩，先把这些源稳定跑起来。

## 安装

```bash
cd /Users/bawangchajiyouxiangongsi/Desktop/py-study
source venv/bin/activate
pip install -r requirements.txt
```

## 采集数据

采集全部 4 个源：

```bash
python main.py --source cls eastmoney_global cninfo ndrc --days 1
```

服务器原始新闻、公告和市场快照按日期永久保存。只读 API 默认返回最近 15 天，避免每次传输全部历史数据。

## 建议调用频率

生产调度器会串行启动各来源、复用连接，并在 `403/429` 或连续失败时执行持久化退避。交易时段基准频率：

```text
cls      每 5 分钟
eastmoney_global 每 10 分钟
cninfo   每 30 分钟，15:00-22:00 每 15 分钟
ndrc     每 60 分钟
```

非交易时段和周末自动降频，不做每分钟全量采集。

## 启动定时采集

最简单的启动方式：

```bash
python run.py
```

它会同时启动新闻接口和后台定时采集。默认频率：

```text
cls      每 5 分钟
eastmoney_global 每 10 分钟
cninfo   每 30 分钟（盘后公告时段 15 分钟）
ndrc     每 60 分钟
```

同时也会在交易日自动生成市场快照：

```text
09:15 09:20 09:24 09:25 09:30 09:35 09:45
14:30 14:40 14:45 14:48 14:50 14:52 14:55 15:00
```

如果市场数据拉取失败，只会写入 `*_failed_snapshot.json`，不会覆盖上一份有效的
`latest_*_snapshot.json`。

启动后会先立即采集一次，然后按频率循环。停止整个服务时按 `Ctrl+C`。

如果不想启动后立即采集：

```bash
python run.py --no-immediate
```

如果需要临时调整频率，可以传秒数：

```bash
python run.py --cls-interval 300 --eastmoney-global-interval 600 --cninfo-interval 3600 --ndrc-interval 14400
```

如果只想启动新闻源，不跑市场数据定时快照：

```bash
python run.py --no-market
```

市场数据网络模式默认使用系统代理环境，不再强制直连。可选模式：

```bash
# 系统代理/服务器环境变量，默认
MARKET_NETWORK_MODE=system_proxy python market_data/market_snapshot.py --mode overnight

# 强制直连
MARKET_NETWORK_MODE=direct python market_data/market_snapshot.py --mode overnight

# 指定代理
MARKET_NETWORK_MODE=custom_proxy MARKET_PROXY=http://127.0.0.1:7890 python market_data/market_snapshot.py --mode overnight

# 使用本地 adapter 兜底全 A 行情
MARKET_NETWORK_MODE=local_adapter MARKET_LOCAL_ADAPTER_URL=http://127.0.0.1:8000 python market_data/market_snapshot.py --mode overnight
```

单独采集某个源：

```bash
python main.py --source cls
python main.py --source eastmoney_global
python main.py --source cninfo
python main.py --source ndrc
```

数据保存到：

```text
data_dev/cls/YYYY-MM-DD.json
data_dev/eastmoney_global/YYYY-MM-DD.json
data_dev/cninfo/YYYY-MM-DD.json
data_dev/ndrc/YYYY-MM-DD.json
```

## 启动新闻源接口

一般不需要单独启动接口，使用 `python run.py` 即可。

只启动接口时：

```bash
python news_api.py --host 127.0.0.1 --port 8765 --data-dir data_dev
```

接口默认返回最近 15 天数据。需要调整查询窗口时：

```bash
python news_api.py --host 127.0.0.1 --port 8765 --data-dir data_dev --retention-days 15
```

生产环境使用 `/v1/*` 只读接口。配置 `DATA_API_TOKEN` 后，包括兼容接口在内的全部路径均需令牌。主要接口：

```text
GET /v1/health
GET /v1/calendar
GET /v1/manifest
GET /v1/news
GET /v1/announcements
GET /v1/market/snapshots
GET /v1/market/snapshots/{snapshot_id}/export
```

示例：

```bash
curl -H "Authorization: Bearer ${DATA_API_TOKEN}" "http://127.0.0.1:8765/v1/manifest"
```

## 客户端服务器配置

客户端和三个选股 skill 统一读取项目根目录的 `.env`：

```dotenv
STOCK_DATA_SERVER="http://服务器IP:8765"
STOCK_DATA_TOKEN="服务器 DATA_API_TOKEN"
```

配置读取顺序为：进程环境变量、项目 `.env`、旧用户目录 JSON、默认本机地址。更换服务器时直接修改 `.env` 即可。

## 数据字段

不同来源字段略有差异，但核心字段保持一致：

- `source`: 来源，`cls` / `eastmoney_global` / `cninfo` / `ndrc`
- `title`: 标题
- `publish_time`: 发布时间
- `content`: 正文或摘要，公告源可能为空
- `url`: 原文链接或公告 PDF 链接
- `matched_keywords`: 命中的股票/产业关键词

巨潮公告额外包含：

- `stock_code`
- `stock_name`
- `announcement_type`

巨潮公告的 `url` 是公告 PDF 链接。项目本身不下载 PDF 正文，避免请求过重；下游 AI 分析系统可按需读取该链接。

## 项目结构

```text
main.py          采集入口
news_api.py      新闻源 HTTP JSON 接口
config.py        数据源和存储配置
spiders/         各新闻源采集逻辑
parsers/         数据解析逻辑
storage/         JSON 存储、去重、增量状态
filters/         关键词标注
utils/           日志、重试、异常
models.py        数据模型
```

## 每日推荐封存与复盘

早盘和尾盘 skill 会把最终七只候选、重点票、触发/放弃条件、数据截止时间和卖出纪律封存在：

`data_recommendations/daily_recommendations.json`

同一时段重新推荐不会覆盖旧记录，而是新增版本并将旧版本标记为 `superseded`。晚上 22:00 生成复盘输入：

```bash
venv/bin/python analysis/recommendation_journal.py review-context \
  --date YYYY-MM-DD \
  --output /tmp/daily_review_context.json
```

复盘口径固定为“当天早盘 + 上一交易日尾盘”。当天尾盘记录保留为待下一交易日复盘，避免提前使用尚未发生的结果。
