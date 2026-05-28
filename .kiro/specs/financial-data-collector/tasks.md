# Implementation Plan: financial-data-collector

## Overview

本实施计划将金融数据采集系统的设计转换为可执行的编码任务。系统采用模块化架构，按照"基础设施 → 核心组件 → 爬虫实现 → 集成测试"的顺序逐步构建。每个任务都是独立可执行的，并明确标注了依赖的需求条款。

## Tasks

### 1. 项目初始化和基础设施

- [x] 1.1 创建项目目录结构和依赖配置
  - 创建目录：`spiders/`, `parsers/`, `filters/`, `storage/`, `utils/`, `tests/`, `logs/`, `data/`
  - 创建 `requirements.txt` 文件，包含所有依赖项及版本约束
  - 创建 `README.md` 文件，说明项目结构和使用方法
  - _需求：11.1, 11.2, 12.1, 12.8_

- [x] 1.2 实现配置管理模块（config.py）
  - 定义所有数据源的配置字典（NDRC_CONFIG, CLS_CONFIG, CNINFO_CONFIG）
  - 定义关键词配置（STOCK_KEYWORDS, CNINFO_KEYWORDS）
  - 定义存储、日志、增量更新、去重配置
  - 实现配置验证函数，检查配置值的有效性
  - 支持环境特定配置（开发/生产）
  - _需求：9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

- [x] 1.3 实现日志系统（utils/logger.py）
  - 使用 Python logging 模块配置日志记录器
  - 实现按日期组织的日志文件（logs/{YYYY-MM-DD}.log）
  - 实现日志轮转机制（文件大小超过 100MB 时轮转）
  - 支持多个日志级别（DEBUG, INFO, WARNING, ERROR, CRITICAL）
  - 配置日志格式，包含时间戳、模块名、级别和消息
  - _需求：8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 1.4 实现重试机制和异常定义（utils/retry.py, utils/exceptions.py）
  - 创建自定义异常类（ParseException, DiskFullException, APIException）
  - 实现 RetryHandler 类，支持指数退避重试策略
  - 实现 execute_with_retry 方法，处理网络请求重试
  - 实现 FailureTracker 类，跟踪连续失败次数
  - _需求：10.1, 10.2, 10.4, 10.7_

### 2. 数据模型定义

- [x] 2.1 定义数据模型类（models.py）
  - 使用 dataclass 定义 NDRCNews 模型
  - 使用 dataclass 定义 CLSNews 模型
  - 使用 dataclass 定义 CNInfoAnnouncement 模型
  - 使用 dataclass 定义 CollectionStatistics 模型
  - 为每个模型实现 to_dict() 和 from_dict() 方法
  - _需求：1.4, 2.4, 3.4_

### 3. 存储层组件

- [x] 3.1 实现去重器（storage/deduplicator.py）
  - 实现 Deduplicator 类，使用 SHA256 哈希算法
  - 实现 _compute_hash 方法，支持不同数据源的去重逻辑
  - 对于 NDRC/CLS：基于 url 字段计算哈希
  - 对于 CNInfo：基于 stock_code + title + publish_time 组合计算哈希
  - 实现 is_duplicate 和 mark_as_seen 方法
  - 实现索引的持久化（save_index）和加载（load_index）
  - _需求：4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [x] 3.2 实现存储管理器（storage/storage_manager.py）
  - 实现 StorageManager 类，管理 JSON 文件的读写
  - 实现 _get_file_path 方法，按数据源和日期组织文件（data/{source}/{YYYY-MM-DD}.json）
  - 实现 save 方法，支持单条数据保存
  - 实现 batch_save 方法，支持批量数据保存
  - 实现 _atomic_write 方法，使用临时文件和 os.rename() 确保原子写入
  - 实现 check_disk_space 方法，检查可用磁盘空间
  - 实现 query 方法，支持按数据源、日期范围、关键词查询数据
  - _需求：7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_

- [x] 3.3 实现增量更新器（storage/incremental_updater.py）
  - 实现 IncrementalUpdater 类，跟踪每个数据源的最后采集时间
  - 实现 get_last_update_time 方法，获取指定数据源的最后更新时间
  - 实现 set_last_update_time 方法，设置最后更新时间
  - 实现 get_time_range 方法，计算采集时间范围
  - 如果没有历史记录，默认采集过去 7 天的数据
  - 实现状态的持久化（save_state）和加载（load_state）
  - _需求：5.1, 5.2, 5.3, 5.4, 5.5_

### 4. 过滤和提取组件

- [x] 4.1 实现关键词过滤器（filters/keyword_filter.py）
  - 实现 KeywordFilter 类，维护可配置的关键词列表
  - 实现 add_keyword 和 remove_keyword 方法，支持动态管理关键词
  - 实现 filter 方法，检查数据是否包含任一关键词
  - 实现 batch_filter 方法，批量过滤数据列表
  - 支持在标题和内容字段中搜索关键词
  - _需求：6.1, 6.2, 6.3, 6.7_

- [x] 4.2 实现关键词提取器（filters/keyword_extractor.py）
  - 实现 KeywordExtractor 类，定义板块分类映射（PLATE_MAPPING）
  - 实现 extract_keywords 方法，从文本中提取关键词
  - 实现 classify_plate 方法，根据关键词分类到板块
  - 实现 generate_statistics 方法，生成关键词频率统计
  - 识别高频主题（每小时出现超过 5 次的关键词）
  - _需求：2.6, 2.7, 6.4, 6.5, 6.6_

### 5. 发改委数据采集

- [x] 5.1 实现发改委解析器（parsers/ndrc_parser.py）
  - 实现 NDRCParser 类，使用 lxml 和 xpath 解析 HTML
  - 定义 xpath 表达式常量（XPATH_TITLE, XPATH_PUBLISH_TIME, XPATH_CONTENT, XPATH_TAGS）
  - 实现 parse_news_list 方法，从列表页提取新闻链接
  - 实现 parse_news_detail 方法，从详情页提取标题、时间、内容、标签
  - 处理编码问题，自动转换为 UTF-8
  - 实现错误处理，解析失败时记录日志并返回 None
  - _需求：1.1, 1.2, 1.5, 1.6_

- [x] 5.2 实现发改委爬虫（spiders/ndrc_spider.py）
  - 实现 NDRCSpider 类，使用 requests 库发送 HTTP 请求
  - 实现 fetch_news_list 方法，获取指定日期范围的新闻链接
  - 实现 fetch_news_detail 方法，获取单篇新闻详情
  - 实现 run 方法，执行完整的采集流程
  - 集成 KeywordFilter，过滤包含股票关键词的新闻
  - 集成 NDRCParser，解析 HTML 内容
  - 设置 30 秒超时和浏览器 User-Agent
  - 使用 RetryHandler 处理网络请求失败
  - _需求：1.1, 1.2, 1.3, 1.4, 1.6, 10.1, 10.5_

- [ ]* 5.3 编写发改委爬虫单元测试（tests/test_ndrc_spider.py）
  - 测试 NDRCParser 的 HTML 解析功能
  - 使用 mock 对象模拟 HTTP 响应
  - 测试关键词过滤逻辑
  - 测试错误处理和重试机制
  - _需求：1.1, 1.2, 1.3, 1.6_

### 6. 证券报数据采集

- [x] 6.1 实现证券报解析器（parsers/cls_parser.py）
  - 实现 CLSParser 类，解析 JSON 格式的 API 响应
  - 实现 parse_news 方法，提取标题、时间、内容、标签、板块、级别
  - 处理不同新闻类别的数据结构差异
  - 实现错误处理，解析失败时记录日志并返回 None
  - _需求：2.1, 2.2, 2.4_

- [x] 6.2 实现证券报爬虫（spiders/cls_spider.py）
  - 实现 CLSSpider 类，定义 CATEGORIES 常量
  - 通过浏览器开发者工具逆向工程，确定 API 端点和请求参数
  - 实现 fetch_category_news 方法，从指定类别获取新闻
  - 实现 run_once 方法，执行一次完整采集（所有类别）
  - 实现 run_continuous 方法，每 60 秒采集一次
  - 集成 CLSParser 解析 API 响应
  - 使用 RetryHandler 处理 API 请求失败和速率限制（HTTP 429）
  - _需求：2.1, 2.2, 2.3, 2.4, 2.5, 2.8, 10.1, 10.6_

- [x] 6.3 集成关键词提取器到证券报爬虫
  - 在 CLSSpider 中调用 KeywordExtractor
  - 分析采集的新闻并生成关键词频率统计
  - 将新闻分类到板块（AI、算力、半导体、机器人）
  - _需求：2.6, 2.7_

- [ ]* 6.4 编写证券报爬虫单元测试（tests/test_cls_spider.py）
  - 测试 CLSParser 的 JSON 解析功能
  - 使用 mock 对象模拟 API 响应
  - 测试不同新闻类别的处理
  - 测试速率限制处理（HTTP 429）
  - _需求：2.1, 2.2, 2.4, 2.8_

### 7. 证券信息网数据采集

- [x] 7.1 实现证券信息网解析器（parsers/cninfo_parser.py）
  - 实现 CNInfoParser 类，解析 JSON 格式的 API 响应
  - 实现 parse_announcement_list 方法，解析公告列表
  - 实现 parse_announcement_detail 方法，解析公告详情
  - 实现 parse_pdf 方法，使用 PyPDF2 或 pdfplumber 提取 PDF 文本
  - 处理中文编码问题
  - 实现错误处理，解析失败时记录日志并返回 None
  - _需求：3.1, 3.2, 3.5, 3.7, 3.8_

- [x] 7.2 实现证券信息网爬虫（spiders/cninfo_spider.py）
  - 实现 CNInfoSpider 类，定义 KEYWORDS 常量
  - 通过浏览器开发者工具逆向工程，确定 API 端点和请求参数
  - 实现 fetch_announcement_list 方法，获取公告列表
  - 实现 fetch_announcement_detail 方法，获取公告详情
  - 实现 download_pdf 方法，下载 PDF 文件
  - 实现 run 方法，执行完整的采集流程
  - 集成 KeywordFilter，过滤包含关键词的公告
  - 集成 CNInfoParser 解析 API 响应和 PDF 文件
  - 使用 RetryHandler 处理网络请求失败
  - _需求：3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 10.1_

- [ ]* 7.3 编写证券信息网爬虫单元测试（tests/test_cninfo_spider.py）
  - 测试 CNInfoParser 的 JSON 和 PDF 解析功能
  - 使用 mock 对象模拟 API 响应和 PDF 文件
  - 测试关键词过滤逻辑
  - 测试错误处理和重试机制
  - _需求：3.1, 3.2, 3.3, 3.5, 3.7, 3.8_

### 8. 主程序和数据采集协调

- [x] 8.1 实现主程序入口（main.py）
  - 加载配置文件（config.py）
  - 初始化日志系统
  - 初始化所有组件（爬虫、过滤器、去重器、存储管理器、增量更新器）
  - 实现数据采集协调逻辑，按顺序执行各爬虫
  - 实现数据处理管道：采集 → 解析 → 过滤 → 去重 → 存储
  - 记录采集统计信息（总条目数、过滤数、重复数、错误数）
  - 实现错误处理，单个爬虫失败不影响其他爬虫
  - 使用 FailureTracker 跟踪连续失败，超过 5 次时暂停数据源
  - _需求：8.1, 8.6, 8.7, 10.2, 10.4_

- [x] 8.2 实现命令行参数支持
  - 使用 argparse 模块解析命令行参数
  - 支持参数：--source（指定数据源）、--days（采集天数）、--continuous（持续采集模式）
  - 支持 --config 参数指定配置文件路径
  - 支持 --log-level 参数设置日志级别
  - _需求：9.1, 9.6_

### 9. 检查点：核心功能验证

- [x] 9. 检查点 - 核心功能验证
  - 运行主程序，测试三个数据源的采集功能
  - 验证数据文件是否正确生成（data/{source}/{YYYY-MM-DD}.json）
  - 验证日志文件是否正确记录（logs/{YYYY-MM-DD}.log）
  - 验证去重功能是否正常工作
  - 验证增量更新功能是否正常工作
  - 检查采集统计信息是否准确
  - 确保所有测试通过，如有问题请向用户提问

### 10. 集成测试和端到端测试

- [ ]* 10.1 编写存储层集成测试（tests/test_storage_integration.py）
  - 测试 Deduplicator + StorageManager 的集成
  - 测试数据保存和查询功能
  - 测试磁盘空间检查和警告
  - 测试原子写入操作
  - _需求：4.1, 4.2, 4.3, 7.1, 7.2, 7.5, 7.7_

- [ ]* 10.2 编写过滤器集成测试（tests/test_filter_integration.py）
  - 测试 KeywordFilter + KeywordExtractor 的集成
  - 测试批量过滤和关键词提取
  - 测试板块分类功能
  - 测试高频主题识别
  - _需求：6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

- [ ]* 10.3 编写端到端测试（tests/test_end_to_end.py）
  - 使用 mock 对象模拟所有外部依赖
  - 测试完整的数据采集流程：采集 → 解析 → 过滤 → 去重 → 存储
  - 测试增量更新逻辑
  - 测试错误处理和重试机制
  - 测试连续失败检测和数据源暂停
  - _需求：1.1-1.6, 2.1-2.8, 3.1-3.8, 4.1-4.6, 5.1-5.5, 10.1-10.7_

- [ ]* 10.4 运行代码覆盖率测试
  - 使用 pytest-cov 生成代码覆盖率报告
  - 确保核心模块的覆盖率达到 80% 以上
  - 识别未覆盖的代码路径并补充测试
  - _需求：所有需求_

### 11. 文档和部署

- [ ] 11.1 完善 README.md 文档
  - 添加项目简介和功能特性
  - 添加安装说明（Python 版本、依赖安装）
  - 添加使用说明（命令行参数、配置文件）
  - 添加项目结构说明
  - 添加常见问题解答（FAQ）
  - _需求：11.1, 11.7_

- [x] 11.2 创建使用示例和配置模板
  - 创建 config.example.py 配置模板
  - 创建使用示例脚本（examples/）
  - 添加数据查询示例
  - 添加自定义关键词示例
  - _需求：9.1, 9.2, 9.6_

- [ ]* 11.3 创建部署脚本
  - 创建 setup.sh 脚本，自动创建目录结构
  - 创建 run.sh 脚本，启动数据采集
  - 创建 systemd 服务文件（可选），支持后台运行
  - 添加日志清理脚本（清理旧日志文件）
  - _需求：11.1_

### 12. 最终检查点

- [ ] 12. 最终检查点 - 系统完整性验证
  - 运行完整的测试套件，确保所有测试通过
  - 在真实环境中测试数据采集（小规模）
  - 验证所有需求条款是否已实现
  - 检查代码质量（注释、命名规范、错误处理）
  - 验证文档的完整性和准确性
  - 确保系统可以在新环境中快速部署
  - 如有问题请向用户提问，否则项目完成

## Notes

### 任务标记说明

- **标记 `*` 的任务**：可选任务，主要是测试相关的子任务。这些任务对于确保代码质量很重要，但可以在快速 MVP 开发时跳过。
- **未标记的任务**：核心实现任务，必须完成。

### 需求追溯

每个任务都标注了对应的需求条款编号（如 _需求：1.1, 1.2_），确保所有需求都有对应的实现任务。

### 任务依赖

- **第 1-2 阶段**：基础设施和数据模型，无依赖，可并行开发
- **第 3-4 阶段**：存储层和过滤组件，依赖第 1-2 阶段
- **第 5-7 阶段**：三个数据源的爬虫，依赖第 1-4 阶段，可并行开发
- **第 8 阶段**：主程序集成，依赖第 1-7 阶段
- **第 9 阶段**：核心功能验证检查点
- **第 10 阶段**：集成测试，依赖第 1-9 阶段
- **第 11 阶段**：文档和部署，依赖第 1-10 阶段
- **第 12 阶段**：最终验证检查点

### 开发建议

1. **优先级**：按照任务编号顺序开发，确保基础设施先就绪
2. **测试策略**：核心逻辑（解析器、过滤器、去重器）应优先编写单元测试
3. **增量开发**：每完成一个爬虫，立即进行小规模测试验证
4. **错误处理**：所有网络请求和文件操作都应有完善的错误处理
5. **日志记录**：关键操作都应记录日志，便于调试和监控

### 检查点说明

- **检查点 9**：在完成核心功能后，验证系统基本可用性
- **检查点 12**：在完成所有任务后，验证系统完整性和生产就绪性

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.3", "1.4"] },
    { "id": 1, "tasks": ["2.1"] },
    { "id": 2, "tasks": ["3.1", "3.2", "3.3", "4.1", "4.2"] },
    { "id": 3, "tasks": ["5.1", "6.1", "7.1"] },
    { "id": 4, "tasks": ["5.2", "5.3", "6.2", "7.2"] },
    { "id": 5, "tasks": ["6.3", "6.4", "7.3"] },
    { "id": 6, "tasks": ["8.1"] },
    { "id": 7, "tasks": ["8.2"] },
    { "id": 8, "tasks": ["10.1", "10.2"] },
    { "id": 9, "tasks": ["10.3", "10.4", "11.1", "11.2"] },
    { "id": 10, "tasks": ["11.3"] }
  ]
}
```
