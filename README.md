# 股票新闻源采集器

这个项目只做一件事：抓取最新原始新闻/公告数据，并通过 JSON 接口提供给股票分析系统使用。

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

数据默认只保留最近 7 天，超过一周的 JSON 文件会在采集结束后自动清理。

## 建议调用频率

为了避免给网站造成压力，也降低被限制的概率，建议按来源分开调度：

```text
cls      每 5-10 分钟采集一次
eastmoney_global 每 10-15 分钟采集一次
cninfo   每 30-60 分钟采集一次，交易日盘后可额外采集一次
ndrc     每 2-4 小时采集一次
```

比较稳妥的第一版方案：

```text
09:00-15:30  每 10 分钟采集 cls
全天        每 10-15 分钟采集 eastmoney_global
09:00-22:00  每 60 分钟采集 cninfo
08:00-22:00  每 4 小时采集 ndrc
```

不要每分钟全量采集所有源。财联社和东方财富快讯可以稍微频繁；巨潮和发改委更新没那么高频，低频更合适。

## 启动定时采集

最简单的启动方式：

```bash
python run.py
```

它会同时启动新闻接口和后台定时采集。默认频率：

```text
cls      每 5 分钟
eastmoney_global 每 10 分钟
cninfo   每 60 分钟
ndrc     每 4 小时
```

启动后会先立即采集一次，然后按频率循环。停止整个服务时按 `Ctrl+C`。

如果不想启动后立即采集：

```bash
python run.py --no-immediate
```

如果需要临时调整频率，可以传秒数：

```bash
python run.py --cls-interval 300 --eastmoney-global-interval 600 --cninfo-interval 3600 --ndrc-interval 14400
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

接口默认也只返回最近 7 天数据。需要调整时：

```bash
python news_api.py --host 127.0.0.1 --port 8765 --data-dir data_dev --retention-days 7
```

接口：

```text
GET /health
GET /news?source=all&limit=100
GET /news?source=cls&limit=50
GET /news?source=eastmoney_global&limit=50
GET /news?source=cninfo&limit=50
GET /news?source=ndrc&limit=50
GET /news?keyword=人工智能
```

示例：

```bash
curl "http://127.0.0.1:8765/news?source=all&limit=20"
```

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
