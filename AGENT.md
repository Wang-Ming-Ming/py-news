# Agent Context

## Goal

完善当前 Python 金融数据采集项目，使它能作为股票分析系统的新闻数据源，实际采集多个网站的数据：

- `ndrc`: 国家发展改革委政策新闻
- `cls`: 财联社/证券新闻
- `cninfo`: 巨潮资讯上市公司公告
- `eastmoney_global`: 东方财富全球财经快讯

## Current Findings

- 项目结构完整，已有爬虫、解析器、关键词过滤、去重、存储、增量更新和日志模块。
- `main.py` 已补充运行参数：`--source`、`--days`、`--log-level`，兼容 README 示例。
- `cls` 旧接口 `/nodeapi/telegraphList` 已返回 404；已切换为当前财联社网页端使用的 `/v1/roll/get_roll_list`，并按网页端规则生成 `sign` 参数。
- `cls` 最新验证结果：`python main.py --source cls --days 1 --log-level INFO` 成功解析 20 条、保存 20 条、错误 0。
- 财联社返回字段包含 `title`、`content`、`ctime`、`shareurl` 等，已保存为本项目统一新闻字段。
- 新增 `eastmoney_global`，通过 AKShare 的东方财富全球财经快讯接口获取全球重大财经新闻，字段包含标题、摘要、发布时间、链接。

## Work Needed

1. 确认可用的实时数据入口。
2. 更新各爬虫或配置中的 URL/参数。
3. 保证输出数据字段适合股票分析系统使用：来源、标题、发布时间、正文/摘要、URL、关键词/板块。
4. 修复成功判定，避免 0 条加错误被当成成功。
5. 用真实联网运行验证各数据源至少能抓到数据或给出明确失败原因。

## User Clarification

当前阶段不需要复杂分析、打分或策略，只需要稳定抓取最新原始新闻/公告数据，作为另一个股票分析系统的新闻源接口。

推荐采集范围：

- `cls`: 财联社滚动电报，适合实时市场消息、公司新闻、产业链消息。
- `eastmoney_global`: 东方财富全球财经快讯，适合全球市场、央行、汇率、商品、海外公司和地缘政策消息。
- `cninfo`: 巨潮资讯公告，适合上市公司公告、回购、并购、担保、诉讼、业绩、股权变动等。
- `ndrc`: 国家发展改革委新闻发布、通知公告、司局/地方动态，适合政策与产业方向消息。

已完成方向：

- 关闭硬关键词过滤，默认保存原始数据，同时写入 `matched_keywords` 方便下游筛选。
- 巨潮公告保留 PDF 链接，不在本项目内下载/解析 PDF 正文，由下游 AI 分析系统按需读取。
- 新增 `news_api.py`，提供轻量 HTTP JSON 接口：
  - `GET /health`
  - `GET /news?source=all&limit=100`
  - `GET /news?source=cls|eastmoney_global|cninfo|ndrc&limit=50`
  - `GET /news?keyword=人工智能`

## Retention And Frequency

- 服务器按日期永久保留原始新闻、公告和市场快照。
- `STORAGE_CONFIG["retention_days"] = 0`，不自动删除历史文件。
- 首次部署默认补采最近 15 天。
- `news_api.py` 和本地 skill 默认读取最近 15 天，显式指定日期时可回取更早归档。

建议调度：

- `cls`: 每 5-10 分钟采集一次。
- `eastmoney_global`: 每 10-15 分钟采集一次。
- `cninfo`: 每 30-60 分钟采集一次，交易日盘后可额外采集一次。
- `ndrc`: 每 2-4 小时采集一次。

不要每分钟全量采集所有源，避免网站限制。

当前采用的定时脚本：

- 推荐一键启动：`python run.py`
- `run.py` 同时启动新闻接口、后台新闻定时采集、交易日市场快照定时采集。
- `scheduler.py`
- 默认启动后立即采集一次。
- 默认间隔：`cls=300s`、`eastmoney_global=600s`、`cninfo=3600s`、`ndrc=14400s`。
- 市场快照默认时间：`09:20`、`09:30`、`10:30`、`13:30`、`14:30`、`14:45`、`14:55`。
- 市场快照拉取失败只写 `*_failed_snapshot.json`，不覆盖上一份有效 `latest_*_snapshot.json`。
- 市场数据网络模式：默认 `MARKET_NETWORK_MODE=system_proxy`；可选 `direct`、`custom_proxy`、`local_adapter`。
- 运行：`python scheduler.py`
- 只启动接口：`python news_api.py --host 127.0.0.1 --port 8765 --data-dir data_dev`
