# Requirements Document

## Introduction

本文档规定了一个专业的 Python 金融数据采集系统的需求，该系统旨在从三个核心数据源采集高质量数据：国家发展和改革委员会（NDRC）、中国证券报（CLS）和中国证券信息网（CNInfo）。该系统作为现有股票分析系统的数据提供者，专注于数据采集，不包含任何 Web 界面、用户管理或身份验证组件。

## Glossary

- **数据采集器（Data_Collector）**: 负责从多个数据源采集金融数据的整体系统
- **发改委爬虫（NDRC_Spider）**: 从国家发展和改革委员会网站采集政策新闻的爬虫组件
- **证券报爬虫（CLS_Spider）**: 从中国证券报网站采集热点新闻的爬虫组件
- **证券信息爬虫（CNInfo_Spider）**: 从中国证券信息网采集公司公告的爬虫组件
- **解析器（Parser）**: 从原始 HTML 或 API 响应中提取结构化数据的组件
- **过滤器（Filter）**: 基于关键词、相关性或其他标准过滤数据的组件
- **存储管理器（Storage_Manager）**: 管理数据持久化和检索的组件
- **去重器（Deduplicator）**: 识别并删除重复数据条目的组件
- **关键词提取器（Keyword_Extractor）**: 从采集的数据中提取和分析关键词的组件
- **增量更新器（Incremental_Updater）**: 跟踪并仅采集自上次采集以来的新数据的组件
- **有效JSON（Valid_JSON）**: 符合每个数据源指定模式的 JSON 对象
- **股票关键词（Stock_Keyword）**: 与股票市场板块相关的关键词，包括 AI、半导体、新能源、机器人、数据中心、低空经济、数字经济和新基建

## Requirements

### 需求 1：发改委政策数据采集

**用户故事：** 作为一名股票分析师，我希望从发改委网站采集政策新闻，以便分析国家政策对股票板块的影响。

#### 验收标准

1. 发改委爬虫（NDRC_Spider）应当使用 requests 和 lxml 库从 https://www.ndrc.gov.cn/ 采集政策新闻
2. 发改委爬虫（NDRC_Spider）应当从每篇新闻文章中提取标题、发布时间、内容、链接和政策类别
3. 发改委爬虫（NDRC_Spider）应当过滤包含股票关键词（Stock_Keyword）值的新闻文章（AI算力、半导体芯片、新能源、机器人、数据中心、数据要素、低空经济、数字经济、新基建）
4. 当采集到一篇新闻文章时，发改委爬虫（NDRC_Spider）应当输出符合以下模式的有效JSON（Valid_JSON）：{"source": "ndrc", "title": "", "publish_time": "", "content": "", "url": "", "tags": []}
5. 发改委爬虫（NDRC_Spider）应当使用 xpath 表达式解析 HTML 内容
6. 当解析失败时，发改委爬虫（NDRC_Spider）应当记录包含链接的错误日志并继续处理其他文章

### 需求 2：证券报热点新闻数据采集

**用户故事：** 作为一名股票交易员，我希望从证券报网站采集实时热点新闻，以便识别市场趋势和热门板块。

#### 验收标准

1. 证券报爬虫（CLS_Spider）应当通过分析和调用 API 端点从 https://www.cls.cn/ 采集热点新闻
2. 证券报爬虫（CLS_Spider）应当优先使用基于 API 的采集方式而非 HTML 解析
3. 证券报爬虫（CLS_Spider）应当从以下类别采集新闻：电报、AI新闻、板块异动、涨停逻辑、热点题材、产业链新闻
4. 当采集到一条新闻时，证券报爬虫（CLS_Spider）应当输出符合以下模式的有效JSON（Valid_JSON）：{"source": "cls", "title": "", "publish_time": "", "content": "", "tags": [], "plate": [], "level": ""}
5. 证券报爬虫（CLS_Spider）应当每 60 秒执行一次采集以实现实时更新
6. 关键词提取器（Keyword_Extractor）应当分析采集的证券报新闻并生成关键词频率统计
7. 关键词提取器（Keyword_Extractor）应当将新闻分类到以下板块：AI、算力、半导体、机器人
8. 当 API 请求失败时，证券报爬虫（CLS_Spider）应当使用指数退避策略重试最多 3 次

### 需求 3：证券信息网公司公告采集

**用户故事：** 作为一名股票分析师，我希望从证券信息网采集公司公告，以便跟踪重要的企业事件和机会。

#### 验收标准

1. 证券信息爬虫（CNInfo_Spider）应当通过分析和调用 API 端点从 https://www.cninfo.com.cn/ 采集公司公告
2. 证券信息爬虫（CNInfo_Spider）应当优先使用基于 API 的采集方式而非 HTML 解析
3. 证券信息爬虫（CNInfo_Spider）应当过滤包含以下关键词的公告：AI合作、算力订单、中标大合同、回购增持、并购重组、战略合作、GPU、数据中心
4. 当采集到一条公告时，证券信息爬虫（CNInfo_Spider）应当输出符合以下模式的有效JSON（Valid_JSON）：{"source": "cninfo", "stock_code": "", "stock_name": "", "title": "", "publish_time": "", "announcement_type": "", "url": "", "keywords": []}
5. 证券信息爬虫（CNInfo_Spider）应当从每条公告中提取股票代码、股票名称、标题、发布时间、公告类型和链接
6. 证券信息爬虫（CNInfo_Spider）应当支持获取公告列表和公告详情
7. 证券信息爬虫（CNInfo_Spider）应当提供解析 PDF 公告文件的能力
8. 当需要解析 PDF 时，证券信息爬虫（CNInfo_Spider）应当从 PDF 文件中提取文本内容

### 需求 4：数据去重

**用户故事：** 作为一名系统管理员，我希望删除重复的数据条目，以便保持数据存储的清洁和高效。

#### 验收标准

1. 去重器（Deduplicator）应当基于链接（url）识别发改委和证券报数据源的重复条目
2. 去重器（Deduplicator）应当基于股票代码、标题和发布时间的组合识别证券信息网数据源的重复条目
3. 当检测到重复条目时，去重器（Deduplicator）应当跳过存储该重复条目
4. 去重器（Deduplicator）应当维护基于哈希的索引以实现快速重复检测
5. 去重器（Deduplicator）应当在系统重启后持久化去重索引
6. 对于所有采集的数据条目，去重器（Deduplicator）应当在存储前验证唯一性

### 需求 5：增量数据更新

**用户故事：** 作为一名系统操作员，我希望仅采集自上次采集以来的新数据，以便最小化网络流量和处理时间。

#### 验收标准

1. 增量更新器（Incremental_Updater）应当跟踪每个数据源的最后采集时间戳
2. 当采集数据时，增量更新器（Incremental_Updater）应当仅请求在最后采集时间戳之后发布的数据
3. 增量更新器（Incremental_Updater）应当将最后采集时间戳持久化到磁盘
4. 当系统重启时，增量更新器（Incremental_Updater）应当从磁盘加载最后采集时间戳
5. 如果不存在先前的采集时间戳，那么增量更新器（Incremental_Updater）应当采集过去 7 天的数据

### 需求 6：关键词过滤和提取

**用户故事：** 作为一名股票分析师，我希望从采集的数据中过滤和提取相关关键词，以便专注于与股票相关的信息。

#### 验收标准

1. 过滤器（Filter）应当维护一个可配置的股票关键词（Stock_Keyword）列表
2. 当过滤发改委新闻时，过滤器（Filter）应当接受至少包含一个股票关键词（Stock_Keyword）的文章
3. 当过滤证券信息网公告时，过滤器（Filter）应当接受至少包含一个股票关键词（Stock_Keyword）的公告
4. 关键词提取器（Keyword_Extractor）应当从标题和内容字段中提取关键词
5. 关键词提取器（Keyword_Extractor）应当为每个采集周期生成关键词频率统计
6. 关键词提取器（Keyword_Extractor）应当识别高频主题（每小时出现超过 5 次的关键词）
7. 过滤器（Filter）应当支持在不修改代码的情况下添加和删除股票关键词（Stock_Keyword）值

### 需求 7：数据存储和持久化

**用户故事：** 作为一名数据消费者，我希望采集的数据以结构化格式存储，以便我可以轻松地将其集成到我的股票分析系统中。

#### 验收标准

1. 存储管理器（Storage_Manager）应当以 JSON 格式存储采集的数据
2. 存储管理器（Storage_Manager）应当按数据源和日期组织数据文件，模式为：data/{source}/{YYYY-MM-DD}.json
3. 当存储数据时，存储管理器（Storage_Manager）应当将新条目追加到当日文件
4. 存储管理器（Storage_Manager）应当在日期变更时创建新文件
5. 存储管理器（Storage_Manager）应当确保原子写入操作以防止数据损坏
6. 存储管理器（Storage_Manager）应当提供查询接口以按数据源、日期范围和关键词检索数据
7. 当磁盘空间低于 1GB 时，存储管理器（Storage_Manager）应当记录警告消息

### 需求 8：日志记录和监控

**用户故事：** 作为一名系统管理员，我希望对系统操作进行全面的日志记录，以便我可以排查问题并监控系统健康状况。

#### 验收标准

1. 数据采集器（Data_Collector）应当记录所有采集操作的时间戳、数据源和状态
2. 数据采集器（Data_Collector）应当记录包含完整堆栈跟踪和上下文信息的错误
3. 数据采集器（Data_Collector）应当按日期组织日志文件，模式为：logs/{YYYY-MM-DD}.log
4. 数据采集器（Data_Collector）应当在文件大小超过 100MB 时轮转日志文件
5. 数据采集器（Data_Collector）应当维护独立的日志级别：DEBUG、INFO、WARNING、ERROR、CRITICAL
6. 当发生错误时，数据采集器（Data_Collector）应当记录错误并继续处理其他数据源
7. 数据采集器（Data_Collector）应当记录采集统计信息，包括：采集的总条目数、过滤的重复项数、遇到的错误数

### 需求 9：配置管理

**用户故事：** 作为一名系统操作员，我希望在不修改代码的情况下配置系统参数，以便我可以使系统适应不同的环境和需求。

#### 验收标准

1. 数据采集器（Data_Collector）应当从 config.py 文件加载配置
2. 数据采集器（Data_Collector）应当支持配置：采集间隔、重试次数、超时值、关键词列表、存储路径、日志级别
3. 当配置文件缺失时，数据采集器（Data_Collector）应当使用默认配置值
4. 当配置文件包含无效值时，数据采集器（Data_Collector）应当记录警告并使用默认值
5. 数据采集器（Data_Collector）应当在启动时验证配置值
6. 数据采集器（Data_Collector）应当支持特定环境的配置文件（开发环境、生产环境）

### 需求 10：错误处理和弹性

**用户故事：** 作为一名系统操作员，我希望系统能够优雅地处理错误，以便临时故障不会停止整个采集过程。

#### 验收标准

1. 当网络请求失败时，数据采集器（Data_Collector）应当使用指数退避策略（1秒、2秒、4秒）重试最多 3 次
2. 当爬虫失败时，数据采集器（Data_Collector）应当记录错误并继续处理其他爬虫
3. 当解析失败时，解析器（Parser）应当记录包含原始数据的错误并跳过该条目
4. 如果数据源连续 5 次以上无法访问，那么数据采集器（Data_Collector）应当发送警报通知
5. 数据采集器（Data_Collector）应当为所有 HTTP 请求实施 30 秒的请求超时
6. 当检测到速率限制（HTTP 429）时，数据采集器（Data_Collector）应当等待指定的 retry-after 时长
7. 数据采集器（Data_Collector）应当优雅地处理连接超时、读取超时和 DNS 解析失败

### 需求 11：项目结构和模块化

**用户故事：** 作为一名开发人员，我希望有一个组织良好的项目结构，以便我可以轻松地理解、维护和扩展系统。

#### 验收标准

1. 数据采集器（Data_Collector）应当将代码组织到以下模块：spiders/、parsers/、filters/、storage/、logs/、config/、data/
2. 数据采集器（Data_Collector）应当提供一个 requirements.txt 文件列出所有 Python 依赖项
3. 数据采集器（Data_Collector）应当将每个爬虫实现为 spiders/ 目录中的独立模块
4. 数据采集器（Data_Collector）应当将每个解析器实现为 parsers/ 目录中的独立模块
5. 数据采集器（Data_Collector）应当在 filters/ 目录中实现过滤器
6. 数据采集器（Data_Collector）应当在 storage/ 目录中实现存储逻辑
7. 数据采集器（Data_Collector）应当包含全面的内联注释来解释每个函数和类

### 需求 12：Python 环境和依赖项

**用户故事：** 作为一名开发人员，我希望使用现代 Python 特性和可靠的库，以便系统易于维护且性能良好。

#### 验收标准

1. 数据采集器（Data_Collector）应当要求 Python 3.11 或更高版本
2. 数据采集器（Data_Collector）应当使用 requests 库进行 HTTP 请求
3. 数据采集器（Data_Collector）应当使用 lxml 库通过 xpath 进行 HTML 解析
4. 数据采集器（Data_Collector）应当使用 asyncio 库进行异步操作（保留供将来使用）
5. 数据采集器（Data_Collector）应当使用标准库 json 模块进行 JSON 操作
6. 数据采集器（Data_Collector）应当使用标准库 logging 模块进行日志记录
7. 在需要动态渲染的情况下，数据采集器（Data_Collector）应当使用 Playwright 库而非 Selenium
8. 数据采集器（Data_Collector）应当在 requirements.txt 中包含所有带版本约束的依赖项
