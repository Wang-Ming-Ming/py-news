# Design Document

## Overview

### 系统目标

金融数据采集系统（Financial Data Collector）是一个专业的 Python 数据采集系统，旨在从三个核心金融数据源自动采集、解析、过滤和存储高质量的结构化数据。该系统作为现有股票分析系统的数据提供者，专注于数据采集管道，不包含任何用户界面、身份验证或 Web 服务组件。

### 核心功能

1. **多源数据采集**：从国家发展和改革委员会（NDRC）、中国证券报（CLS）和中国证券信息网（CNInfo）三个数据源采集数据
2. **智能数据处理**：解析、过滤、去重和关键词提取
3. **增量更新**：仅采集自上次运行以来的新数据
4. **可靠性保障**：错误处理、重试机制、日志记录和监控
5. **灵活配置**：支持通过配置文件调整系统行为

### 设计原则

1. **模块化架构**：每个爬虫、解析器和处理组件都是独立模块，便于维护和扩展
2. **关注点分离**：采集、解析、过滤、存储等功能清晰分离
3. **容错性**：单个数据源或组件的失败不影响其他组件运行
4. **可配置性**：关键参数通过配置文件管理，无需修改代码
5. **可观测性**：全面的日志记录和统计信息

## Architecture

### 系统架构概述

系统采用**管道式架构（Pipeline Architecture）**，数据流经多个处理阶段：

```
数据源 → 采集器 → 解析器 → 过滤器 → 去重器 → 存储管理器 → JSON 文件
         ↓         ↓         ↓         ↓          ↓
      日志记录   日志记录   日志记录   日志记录    日志记录
```

### 架构层次


#### 1. 数据采集层（Data Collection Layer）

负责从外部数据源获取原始数据。

- **NDRC_Spider**：使用 requests + lxml 从发改委网站采集 HTML 页面
- **CLS_Spider**：通过 API 调用从证券报网站采集 JSON 数据
- **CNInfo_Spider**：通过 API 调用从证券信息网采集公告数据和 PDF 文件

#### 2. 数据处理层（Data Processing Layer）

负责数据的解析、转换和过滤。

- **Parser 模块**：将原始 HTML/JSON/PDF 转换为结构化数据
- **Filter 模块**：基于关键词过滤相关数据
- **Keyword_Extractor**：提取关键词并生成统计信息
- **Deduplicator**：识别并删除重复数据

#### 3. 数据持久化层（Data Persistence Layer）

负责数据的存储和检索。

- **Storage_Manager**：管理 JSON 文件的写入和组织
- **Incremental_Updater**：跟踪采集进度和时间戳

#### 4. 基础设施层（Infrastructure Layer）

提供横切关注点的支持。

- **配置管理**：从 config.py 加载系统配置
- **日志系统**：使用 Python logging 模块记录操作和错误
- **错误处理**：统一的异常处理和重试机制

### 数据流设计

#### 主数据流

1. **采集阶段**：爬虫从数据源获取原始数据（HTML/JSON/PDF）
2. **解析阶段**：解析器将原始数据转换为结构化的 Python 字典
3. **过滤阶段**：过滤器根据关键词筛选相关数据
4. **去重阶段**：去重器检查数据是否已存在
5. **存储阶段**：存储管理器将数据写入 JSON 文件


#### 错误处理流

```
网络请求失败 → 指数退避重试（1s, 2s, 4s）→ 最多 3 次
                                          ↓
                                    记录错误日志
                                          ↓
                                    继续处理下一项
```

#### 增量更新流

```
启动 → 加载上次采集时间戳 → 构建时间范围查询 → 采集新数据 → 更新时间戳
       ↓（如果不存在）
    使用默认值（过去 7 天）
```

### 模块依赖关系

```
main.py
  ├── config.py（配置）
  ├── spiders/
  │     ├── ndrc_spider.py → parsers/ndrc_parser.py
  │     ├── cls_spider.py → parsers/cls_parser.py
  │     └── cninfo_spider.py → parsers/cninfo_parser.py
  ├── filters/
  │     ├── keyword_filter.py
  │     └── keyword_extractor.py
  ├── storage/
  │     ├── deduplicator.py
  │     ├── storage_manager.py
  │     └── incremental_updater.py
  └── utils/
        ├── logger.py
        └── retry.py
```

## Components and Interfaces

### 1. NDRC_Spider（发改委爬虫）

#### 职责

从国家发展和改革委员会网站采集政策新闻。

#### 类设计

```python
class NDRCSpider:
    """发改委政策新闻爬虫"""
    
    def __init__(self, config: dict, logger: logging.Logger):
        """
        初始化爬虫
        
        Args:
            config: 配置字典，包含 URL、超时、重试等参数
            logger: 日志记录器
        """
```

        
    def fetch_news_list(self, start_date: datetime, end_date: datetime) -> List[str]:
        """
        获取新闻列表页面的所有新闻链接
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            新闻详情页面的 URL 列表
            
        Raises:
            RequestException: 网络请求失败
        """
        
    def fetch_news_detail(self, url: str) -> dict:
        """
        获取单篇新闻的详细信息
        
        Args:
            url: 新闻详情页面 URL
            
        Returns:
            包含新闻数据的字典：
            {
                "source": "ndrc",
                "title": str,
                "publish_time": str (ISO 8601 格式),
                "content": str,
                "url": str,
                "tags": List[str]
            }
            
        Raises:
            ParseException: HTML 解析失败
        """
        
    def run(self, start_date: datetime, end_date: datetime) -> List[dict]:
        """
        执行完整的采集流程
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            采集到的所有新闻数据列表
        """
```


#### 技术实现

- **HTTP 库**：requests
- **HTML 解析**：lxml + xpath
- **编码处理**：自动检测和转换为 UTF-8
- **超时设置**：30 秒
- **User-Agent**：模拟浏览器请求

#### XPath 表达式示例

```python
XPATH_NEWS_LIST = "//div[@class='news-list']//a/@href"
XPATH_TITLE = "//h1[@class='article-title']/text()"
XPATH_PUBLISH_TIME = "//span[@class='publish-time']/text()"
XPATH_CONTENT = "//div[@class='article-content']//text()"
XPATH_TAGS = "//div[@class='tags']//a/text()"
```

### 2. CLS_Spider（证券报爬虫）

#### 职责

从中国证券报网站采集实时热点新闻，支持多个新闻类别。

#### 类设计

```python
class CLSSpider:
    """证券报热点新闻爬虫"""
    
    # 支持的新闻类别
    CATEGORIES = [
        "telegraph",      # 电报
        "ai_news",        # AI新闻
        "plate_movement", # 板块异动
        "limit_up_logic", # 涨停逻辑
        "hot_topics",     # 热点题材
        "industry_chain"  # 产业链新闻
    ]
    
    def __init__(self, config: dict, logger: logging.Logger):
        """
        初始化爬虫
        
        Args:
            config: 配置字典，包含 API 端点、密钥等
            logger: 日志记录器
        """
```

        
    def fetch_category_news(self, category: str, limit: int = 20) -> List[dict]:
        """
        从指定类别获取新闻
        
        Args:
            category: 新闻类别（必须是 CATEGORIES 中的一个）
            limit: 获取的新闻数量上限
            
        Returns:
            新闻数据列表，每条新闻格式：
            {
                "source": "cls",
                "title": str,
                "publish_time": str (ISO 8601 格式),
                "content": str,
                "tags": List[str],
                "plate": List[str],  # 相关板块
                "level": str         # 新闻级别（重要/一般）
            }
            
        Raises:
            APIException: API 调用失败
        """
        
    def run_continuous(self, interval: int = 60):
        """
        持续采集模式，每隔指定时间采集一次
        
        Args:
            interval: 采集间隔（秒），默认 60 秒
        """
        
    def run_once(self) -> List[dict]:
        """
        执行一次完整的采集流程（所有类别）
        
        Returns:
            采集到的所有新闻数据列表
        """
```

#### 技术实现

- **API 调用**：requests.post() 或 requests.get()
- **数据格式**：JSON
- **认证方式**：可能需要 API 密钥或 token（通过逆向工程确定）
- **速率限制**：每 60 秒一次采集
- **重试策略**：指数退避，最多 3 次


#### API 端点示例

```python
API_ENDPOINTS = {
    "telegraph": "https://www.cls.cn/api/telegraph",
    "ai_news": "https://www.cls.cn/api/ai-news",
    "plate_movement": "https://www.cls.cn/api/plate-movement",
    # ... 其他端点需要通过逆向工程确定
}
```

### 3. CNInfo_Spider（证券信息爬虫）

#### 职责

从中国证券信息网采集公司公告，支持 PDF 解析。

#### 类设计

```python
class CNInfoSpider:
    """证券信息网公司公告爬虫"""
    
    # 关键词过滤列表
    KEYWORDS = [
        "AI合作", "算力订单", "中标大合同", "回购增持",
        "并购重组", "战略合作", "GPU", "数据中心"
    ]
    
    def __init__(self, config: dict, logger: logging.Logger):
        """
        初始化爬虫
        
        Args:
            config: 配置字典
            logger: 日志记录器
        """
        
    def fetch_announcement_list(
        self, 
        start_date: datetime, 
        end_date: datetime,
        stock_code: Optional[str] = None
    ) -> List[dict]:
        """
        获取公告列表
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            stock_code: 可选的股票代码过滤
            
        Returns:
            公告元数据列表
        """
```

        
    def fetch_announcement_detail(self, announcement_id: str) -> dict:
        """
        获取公告详情
        
        Args:
            announcement_id: 公告 ID
            
        Returns:
            公告详细数据：
            {
                "source": "cninfo",
                "stock_code": str,
                "stock_name": str,
                "title": str,
                "publish_time": str (ISO 8601 格式),
                "announcement_type": str,
                "url": str,
                "keywords": List[str]
            }
        """
        
    def download_pdf(self, pdf_url: str) -> bytes:
        """
        下载 PDF 文件
        
        Args:
            pdf_url: PDF 文件 URL
            
        Returns:
            PDF 文件的二进制内容
        """
        
    def parse_pdf(self, pdf_content: bytes) -> str:
        """
        解析 PDF 文件内容
        
        Args:
            pdf_content: PDF 文件的二进制内容
            
        Returns:
            提取的文本内容
            
        Raises:
            PDFParseException: PDF 解析失败
        """
        
    def run(self, start_date: datetime, end_date: datetime) -> List[dict]:
        """
        执行完整的采集流程
        
        Returns:
            采集到的所有公告数据列表
        """
```


#### 技术实现

- **API 调用**：requests
- **PDF 解析**：PyPDF2 或 pdfplumber
- **文本提取**：支持中文编码
- **过滤逻辑**：标题或内容包含任一关键词

### 4. Keyword_Filter（关键词过滤器）

#### 职责

根据配置的关键词列表过滤数据。

#### 类设计

```python
class KeywordFilter:
    """关键词过滤器"""
    
    def __init__(self, keywords: List[str], logger: logging.Logger):
        """
        初始化过滤器
        
        Args:
            keywords: 关键词列表
            logger: 日志记录器
        """
        
    def add_keyword(self, keyword: str):
        """添加关键词"""
        
    def remove_keyword(self, keyword: str):
        """移除关键词"""
        
    def filter(self, data: dict, fields: List[str] = ["title", "content"]) -> bool:
        """
        判断数据是否包含任一关键词
        
        Args:
            data: 待过滤的数据字典
            fields: 需要检查的字段列表
            
        Returns:
            True 表示数据包含关键词（应保留），False 表示不包含（应丢弃）
        """
        
    def batch_filter(self, data_list: List[dict]) -> List[dict]:
        """
        批量过滤数据
        
        Returns:
            过滤后的数据列表
        """
```


### 5. Keyword_Extractor（关键词提取器）

#### 职责

从数据中提取关键词并生成统计信息。

#### 类设计

```python
class KeywordExtractor:
    """关键词提取器和统计分析器"""
    
    # 板块分类映射
    PLATE_MAPPING = {
        "AI": ["AI", "人工智能", "大模型", "ChatGPT"],
        "算力": ["算力", "GPU", "芯片", "服务器"],
        "半导体": ["半导体", "芯片", "集成电路", "晶圆"],
        "机器人": ["机器人", "自动化", "工业机器人"]
    }
    
    def __init__(self, logger: logging.Logger):
        """初始化提取器"""
        
    def extract_keywords(self, text: str, top_n: int = 10) -> List[str]:
        """
        从文本中提取关键词
        
        Args:
            text: 输入文本
            top_n: 返回前 N 个关键词
            
        Returns:
            关键词列表
        """
        
    def classify_plate(self, keywords: List[str]) -> List[str]:
        """
        根据关键词分类到板块
        
        Args:
            keywords: 关键词列表
            
        Returns:
            板块列表
        """
        
    def generate_statistics(self, data_list: List[dict]) -> dict:
        """
        生成关键词频率统计
        
        Args:
            data_list: 数据列表
            
        Returns:
            统计结果：
            {
                "total_count": int,
                "keyword_frequency": Dict[str, int],
                "high_frequency_topics": List[str],  # 每小时出现 > 5 次
                "plate_distribution": Dict[str, int]
            }
        """
```


### 6. Deduplicator（去重器）

#### 职责

识别并删除重复的数据条目。

#### 类设计

```python
class Deduplicator:
    """数据去重器"""
    
    def __init__(self, index_file: str, logger: logging.Logger):
        """
        初始化去重器
        
        Args:
            index_file: 去重索引文件路径
            logger: 日志记录器
        """
        
    def _compute_hash(self, data: dict, source: str) -> str:
        """
        计算数据的哈希值
        
        Args:
            data: 数据字典
            source: 数据源（ndrc/cls/cninfo）
            
        Returns:
            SHA256 哈希值
            
        实现逻辑：
        - ndrc/cls: 基于 url 字段
        - cninfo: 基于 stock_code + title + publish_time 组合
        """
        
    def is_duplicate(self, data: dict, source: str) -> bool:
        """
        检查数据是否重复
        
        Args:
            data: 待检查的数据
            source: 数据源
            
        Returns:
            True 表示重复，False 表示不重复
        """
        
    def mark_as_seen(self, data: dict, source: str):
        """
        将数据标记为已见过
        
        Args:
            data: 数据字典
            source: 数据源
        """
        
    def save_index(self):
        """将去重索引持久化到磁盘"""
        
    def load_index(self):
        """从磁盘加载去重索引"""
```


#### 技术实现

- **哈希算法**：SHA256
- **索引结构**：Set[str]（哈希值集合）
- **持久化格式**：JSON 文件
- **索引文件路径**：`data/.dedup_index.json`

### 7. Storage_Manager（存储管理器）

#### 职责

管理数据的持久化和检索。

#### 类设计

```python
class StorageManager:
    """数据存储管理器"""
    
    def __init__(self, base_path: str, logger: logging.Logger):
        """
        初始化存储管理器
        
        Args:
            base_path: 数据存储根目录
            logger: 日志记录器
        """
        
    def _get_file_path(self, source: str, date: datetime) -> str:
        """
        获取数据文件路径
        
        Args:
            source: 数据源（ndrc/cls/cninfo）
            date: 日期
            
        Returns:
            文件路径，格式：{base_path}/{source}/{YYYY-MM-DD}.json
        """
        
    def save(self, data: dict, source: str):
        """
        保存单条数据
        
        Args:
            data: 数据字典
            source: 数据源
            
        实现逻辑：
        1. 确定文件路径（基于当前日期）
        2. 如果文件不存在，创建新文件
        3. 使用原子写入操作追加数据
        4. 检查磁盘空间
        """
```

        
    def batch_save(self, data_list: List[dict], source: str):
        """
        批量保存数据
        
        Args:
            data_list: 数据列表
            source: 数据源
        """
        
    def query(
        self,
        source: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        keywords: Optional[List[str]] = None
    ) -> List[dict]:
        """
        查询数据
        
        Args:
            source: 数据源过滤（可选）
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）
            keywords: 关键词过滤（可选）
            
        Returns:
            符合条件的数据列表
        """
        
    def check_disk_space(self) -> int:
        """
        检查磁盘可用空间
        
        Returns:
            可用空间（字节）
        """
        
    def _atomic_write(self, file_path: str, data: dict):
        """
        原子写入操作
        
        实现逻辑：
        1. 写入临时文件
        2. 使用 os.rename() 原子替换
        """
```

#### 文件组织结构

```
data/
├── ndrc/
│   ├── 2024-01-15.json
│   ├── 2024-01-16.json
│   └── ...
├── cls/
│   ├── 2024-01-15.json
│   └── ...
└── cninfo/
    ├── 2024-01-15.json
    └── ...
```


### 8. Incremental_Updater（增量更新器）

#### 职责

跟踪采集进度，实现增量更新。

#### 类设计

```python
class IncrementalUpdater:
    """增量更新跟踪器"""
    
    def __init__(self, state_file: str, logger: logging.Logger):
        """
        初始化增量更新器
        
        Args:
            state_file: 状态文件路径
            logger: 日志记录器
        """
        
    def get_last_update_time(self, source: str) -> Optional[datetime]:
        """
        获取指定数据源的最后更新时间
        
        Args:
            source: 数据源（ndrc/cls/cninfo）
            
        Returns:
            最后更新时间，如果不存在返回 None
        """
        
    def set_last_update_time(self, source: str, timestamp: datetime):
        """
        设置指定数据源的最后更新时间
        
        Args:
            source: 数据源
            timestamp: 时间戳
        """
        
    def get_time_range(self, source: str, default_days: int = 7) -> Tuple[datetime, datetime]:
        """
        获取采集时间范围
        
        Args:
            source: 数据源
            default_days: 如果没有历史记录，默认采集的天数
            
        Returns:
            (start_date, end_date) 元组
        """
        
    def save_state(self):
        """将状态持久化到磁盘"""
        
    def load_state(self):
        """从磁盘加载状态"""
```


#### 状态文件格式

```json
{
  "ndrc": {
    "last_update": "2024-01-15T10:30:00Z",
    "last_success": "2024-01-15T10:30:00Z",
    "total_collected": 1250
  },
  "cls": {
    "last_update": "2024-01-15T10:35:00Z",
    "last_success": "2024-01-15T10:35:00Z",
    "total_collected": 3420
  },
  "cninfo": {
    "last_update": "2024-01-15T10:40:00Z",
    "last_success": "2024-01-15T10:40:00Z",
    "total_collected": 890
  }
}
```

### 9. 配置管理（Config）

#### 配置文件结构

```python
# config.py

# 数据源配置
NDRC_CONFIG = {
    "base_url": "https://www.ndrc.gov.cn",
    "timeout": 30,
    "retry_times": 3,
    "retry_delays": [1, 2, 4],  # 指数退避（秒）
}

CLS_CONFIG = {
    "base_url": "https://www.cls.cn",
    "api_endpoints": {
        "telegraph": "/api/telegraph",
        "ai_news": "/api/ai-news",
        # ... 其他端点
    },
    "interval": 60,  # 采集间隔（秒）
    "timeout": 30,
    "retry_times": 3,
}

CNINFO_CONFIG = {
    "base_url": "https://www.cninfo.com.cn",
    "api_endpoints": {
        "announcement_list": "/api/announcement/list",
        "announcement_detail": "/api/announcement/detail",
    },
    "timeout": 30,
    "retry_times": 3,
}

# 关键词配置
STOCK_KEYWORDS = [
    "AI算力", "半导体芯片", "新能源", "机器人",
    "数据中心", "数据要素", "低空经济", "数字经济", "新基建"
]

CNINFO_KEYWORDS = [
    "AI合作", "算力订单", "中标大合同", "回购增持",
    "并购重组", "战略合作", "GPU", "数据中心"
]
```


# 存储配置
STORAGE_CONFIG = {
    "base_path": "./data",
    "min_disk_space": 1 * 1024 * 1024 * 1024,  # 1GB
}

# 日志配置
LOGGING_CONFIG = {
    "log_dir": "./logs",
    "log_level": "INFO",  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    "max_file_size": 100 * 1024 * 1024,  # 100MB
    "backup_count": 10,
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
}

# 增量更新配置
INCREMENTAL_CONFIG = {
    "state_file": "./data/.incremental_state.json",
    "default_days": 7,
}

# 去重配置
DEDUP_CONFIG = {
    "index_file": "./data/.dedup_index.json",
}
```

### 10. 日志系统（Logger）

#### 日志级别和用途

- **DEBUG**：详细的调试信息（HTTP 请求/响应、解析过程）
- **INFO**：正常操作信息（采集开始/完成、数据保存）
- **WARNING**：警告信息（磁盘空间不足、配置缺失）
- **ERROR**：错误信息（网络请求失败、解析错误）
- **CRITICAL**：严重错误（系统无法继续运行）

#### 日志格式

```
2024-01-15 10:30:45,123 - NDRCSpider - INFO - 开始采集发改委新闻，时间范围：2024-01-08 至 2024-01-15
2024-01-15 10:30:46,456 - NDRCSpider - DEBUG - 请求 URL: https://www.ndrc.gov.cn/news/list?page=1
2024-01-15 10:30:47,789 - NDRCSpider - INFO - 获取到 25 条新闻链接
2024-01-15 10:30:50,123 - KeywordFilter - INFO - 过滤后保留 8 条相关新闻
2024-01-15 10:30:51,456 - Deduplicator - INFO - 检测到 2 条重复数据，已跳过
2024-01-15 10:30:52,789 - StorageManager - INFO - 成功保存 6 条数据到 data/ndrc/2024-01-15.json
```


### 11. 错误处理和重试机制（Retry）

#### 重试策略

```python
class RetryHandler:
    """重试处理器"""
    
    def __init__(self, max_retries: int = 3, delays: List[int] = [1, 2, 4]):
        """
        初始化重试处理器
        
        Args:
            max_retries: 最大重试次数
            delays: 每次重试的延迟时间（秒）
        """
        
    def execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """
        执行函数并在失败时重试
        
        Args:
            func: 要执行的函数
            *args, **kwargs: 函数参数
            
        Returns:
            函数执行结果
            
        Raises:
            最后一次尝试的异常
            
        实现逻辑：
        1. 尝试执行函数
        2. 如果失败，等待指定时间后重试
        3. 使用指数退避策略
        4. 记录每次重试的日志
        """
```

#### 异常处理策略

| 异常类型 | 处理方式 |
|---------|---------|
| `requests.Timeout` | 重试 3 次，记录 ERROR 日志 |
| `requests.ConnectionError` | 重试 3 次，记录 ERROR 日志 |
| `requests.HTTPError (429)` | 等待 retry-after 时间，然后重试 |
| `requests.HTTPError (4xx)` | 不重试，记录 ERROR 日志 |
| `requests.HTTPError (5xx)` | 重试 3 次，记录 ERROR 日志 |
| `ParseException` | 不重试，记录 ERROR 日志，跳过该条目 |
| `DiskFullException` | 不重试，记录 CRITICAL 日志，停止采集 |


## Data Models

### 1. NDRC 数据模型

```python
from typing import List
from datetime import datetime
from dataclasses import dataclass

@dataclass
class NDRCNews:
    """发改委新闻数据模型"""
    source: str = "ndrc"
    title: str
    publish_time: str  # ISO 8601 格式：2024-01-15T10:30:00Z
    content: str
    url: str
    tags: List[str]
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "source": self.source,
            "title": self.title,
            "publish_time": self.publish_time,
            "content": self.content,
            "url": self.url,
            "tags": self.tags
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'NDRCNews':
        """从字典创建实例"""
        return cls(
            title=data["title"],
            publish_time=data["publish_time"],
            content=data["content"],
            url=data["url"],
            tags=data.get("tags", [])
        )
```

### 2. CLS 数据模型

```python
@dataclass
class CLSNews:
    """证券报新闻数据模型"""
    source: str = "cls"
    title: str
    publish_time: str  # ISO 8601 格式
    content: str
    tags: List[str]
    plate: List[str]  # 相关板块
    level: str  # 新闻级别：重要/一般
    
    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "title": self.title,
            "publish_time": self.publish_time,
            "content": self.content,
            "tags": self.tags,
            "plate": self.plate,
            "level": self.level
        }
```


### 3. CNInfo 数据模型

```python
@dataclass
class CNInfoAnnouncement:
    """证券信息网公告数据模型"""
    source: str = "cninfo"
    stock_code: str
    stock_name: str
    title: str
    publish_time: str  # ISO 8601 格式
    announcement_type: str
    url: str
    keywords: List[str]
    
    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "title": self.title,
            "publish_time": self.publish_time,
            "announcement_type": self.announcement_type,
            "url": self.url,
            "keywords": self.keywords
        }
```

### 4. 统计数据模型

```python
@dataclass
class CollectionStatistics:
    """采集统计数据模型"""
    source: str
    start_time: datetime
    end_time: datetime
    total_fetched: int  # 总共获取的条目数
    filtered_count: int  # 被过滤掉的条目数
    duplicate_count: int  # 重复条目数
    saved_count: int  # 成功保存的条目数
    error_count: int  # 错误数
    errors: List[dict]  # 错误详情列表
    
    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_seconds": (self.end_time - self.start_time).total_seconds(),
            "total_fetched": self.total_fetched,
            "filtered_count": self.filtered_count,
            "duplicate_count": self.duplicate_count,
            "saved_count": self.saved_count,
            "error_count": self.error_count,
            "errors": self.errors
        }
```


## Error Handling

### 错误分类和处理策略

#### 1. 网络错误

**错误类型**：
- 连接超时（`requests.Timeout`）
- 连接失败（`requests.ConnectionError`）
- DNS 解析失败（`socket.gaierror`）

**处理策略**：
- 使用指数退避重试（1秒、2秒、4秒）
- 最多重试 3 次
- 记录 ERROR 级别日志，包含完整堆栈跟踪
- 如果所有重试失败，跳过该条目，继续处理下一条

**示例代码**：
```python
try:
    response = retry_handler.execute_with_retry(
        requests.get, 
        url, 
        timeout=30
    )
except requests.RequestException as e:
    logger.error(f"网络请求失败，URL: {url}, 错误: {e}", exc_info=True)
    continue  # 跳过该条目
```

#### 2. HTTP 错误

**错误类型**：
- 4xx 客户端错误（如 404 Not Found）
- 429 速率限制
- 5xx 服务器错误

**处理策略**：
- **4xx 错误**：不重试，记录 WARNING 日志，跳过该条目
- **429 速率限制**：
  - 读取响应头中的 `Retry-After` 值
  - 等待指定时间后重试
  - 如果没有 `Retry-After`，等待 60 秒
- **5xx 错误**：重试 3 次，使用指数退避

**示例代码**：
```python
if response.status_code == 429:
    retry_after = int(response.headers.get('Retry-After', 60))
    logger.warning(f"遇到速率限制，等待 {retry_after} 秒")
    time.sleep(retry_after)
    # 重试请求
elif 400 <= response.status_code < 500:
    logger.warning(f"客户端错误 {response.status_code}，跳过 URL: {url}")
    continue
elif response.status_code >= 500:
    # 使用重试机制
    pass
```


#### 3. 解析错误

**错误类型**：
- HTML 解析失败（xpath 未找到元素）
- JSON 解析失败（格式错误）
- PDF 解析失败（文件损坏）
- 编码错误（字符集问题）

**处理策略**：
- 不重试（解析错误通常不是临时性的）
- 记录 ERROR 日志，包含原始数据（截断到 500 字符）
- 跳过该条目，继续处理下一条
- 如果同一数据源连续 10 次解析失败，记录 CRITICAL 日志

**示例代码**：
```python
try:
    title = tree.xpath(XPATH_TITLE)[0]
except (IndexError, AttributeError) as e:
    logger.error(
        f"解析失败，URL: {url}, 错误: {e}, "
        f"HTML 片段: {html_content[:500]}...",
        exc_info=True
    )
    parse_error_count += 1
    if parse_error_count >= 10:
        logger.critical(f"数据源 {source} 连续 10 次解析失败，可能存在结构变化")
    continue
```

#### 4. 存储错误

**错误类型**：
- 磁盘空间不足
- 文件权限错误
- I/O 错误

**处理策略**：
- **磁盘空间不足**：
  - 记录 CRITICAL 日志
  - 停止采集
  - 发送警报通知（如果配置）
- **文件权限错误**：
  - 记录 ERROR 日志
  - 尝试创建备用目录
  - 如果失败，停止采集
- **I/O 错误**：
  - 重试 3 次
  - 如果失败，记录 ERROR 日志并跳过

**示例代码**：
```python
def save(self, data: dict, source: str):
    # 检查磁盘空间
    if self.check_disk_space() < self.min_disk_space:
        logger.critical("磁盘空间不足，停止采集")
        raise DiskFullException("磁盘空间低于 1GB")
    
    try:
        self._atomic_write(file_path, data)
    except PermissionError as e:
        logger.error(f"文件权限错误: {e}")
        raise
    except IOError as e:
        logger.error(f"I/O 错误: {e}", exc_info=True)
        raise
```


#### 5. 配置错误

**错误类型**：
- 配置文件缺失
- 配置值无效（如负数超时）
- 必需配置项缺失

**处理策略**：
- 配置文件缺失：使用默认配置，记录 WARNING 日志
- 配置值无效：使用默认值，记录 WARNING 日志
- 必需配置项缺失：记录 ERROR 日志，停止启动

**示例代码**：
```python
def load_config():
    try:
        import config
    except ImportError:
        logger.warning("配置文件 config.py 不存在，使用默认配置")
        return DEFAULT_CONFIG
    
    # 验证配置
    if config.TIMEOUT <= 0:
        logger.warning(f"无效的超时值 {config.TIMEOUT}，使用默认值 30")
        config.TIMEOUT = 30
    
    return config
```

### 错误监控和警报

#### 连续失败检测

如果某个数据源连续失败超过 5 次，系统应：
1. 记录 CRITICAL 日志
2. 发送警报通知（如果配置了通知机制）
3. 暂停该数据源的采集 1 小时
4. 1 小时后自动重试

**实现逻辑**：
```python
class FailureTracker:
    """失败跟踪器"""
    
    def __init__(self, threshold: int = 5):
        self.failure_counts = {}
        self.threshold = threshold
        self.paused_until = {}
    
    def record_failure(self, source: str):
        """记录失败"""
        self.failure_counts[source] = self.failure_counts.get(source, 0) + 1
        
        if self.failure_counts[source] >= self.threshold:
            logger.critical(f"数据源 {source} 连续失败 {self.threshold} 次")
            self.pause_source(source, hours=1)
    
    def record_success(self, source: str):
        """记录成功，重置失败计数"""
        self.failure_counts[source] = 0
    
    def is_paused(self, source: str) -> bool:
        """检查数据源是否被暂停"""
        if source in self.paused_until:
            if datetime.now() < self.paused_until[source]:
                return True
            else:
                del self.paused_until[source]
        return False
```


## Testing Strategy

### 测试方法概述

由于金融数据采集系统主要涉及 I/O 操作、外部依赖和网络请求，**不适合使用属性测试（Property-Based Testing）**。系统测试策略将采用以下方法：

1. **单元测试**：测试独立组件的逻辑
2. **集成测试**：测试组件间的交互和外部依赖
3. **模拟测试**：使用 mock 对象模拟外部依赖
4. **端到端测试**：测试完整的数据采集流程

### 为什么不使用 PBT

本系统不适合属性测试的原因：

1. **主要是 I/O 操作**：网络请求、文件读写、数据库操作
2. **外部依赖**：依赖外部网站和 API，行为不可控
3. **副作用为主**：系统的主要功能是产生副作用（保存文件、发送请求）
4. **没有复杂的纯函数逻辑**：大部分逻辑涉及外部交互

更适合的测试方法是**集成测试**和**基于示例的单元测试**。

### 单元测试

#### 测试范围

- **解析器**：测试 HTML/JSON/PDF 解析逻辑
- **过滤器**：测试关键词过滤逻辑
- **去重器**：测试哈希计算和重复检测
- **配置管理**：测试配置加载和验证
- **工具函数**：测试日期转换、字符串处理等

#### 测试框架

- **pytest**：主测试框架
- **pytest-cov**：代码覆盖率
- **pytest-mock**：mock 支持

#### 示例测试用例

```python
# tests/test_keyword_filter.py

import pytest
from filters.keyword_filter import KeywordFilter

class TestKeywordFilter:
    """关键词过滤器单元测试"""
    
    def test_filter_with_matching_keyword(self):
        """测试：包含关键词的数据应被保留"""
        filter = KeywordFilter(["AI", "半导体"], logger)
        data = {"title": "AI芯片新突破", "content": "..."}
        
        assert filter.filter(data) == True
    
    def test_filter_without_matching_keyword(self):
        """测试：不包含关键词的数据应被过滤"""
        filter = KeywordFilter(["AI", "半导体"], logger)
        data = {"title": "天气预报", "content": "今天晴天"}
        
        assert filter.filter(data) == False
```

    
    def test_add_keyword(self):
        """测试：动态添加关键词"""
        filter = KeywordFilter(["AI"], logger)
        filter.add_keyword("机器人")
        data = {"title": "机器人产业发展", "content": "..."}
        
        assert filter.filter(data) == True
    
    def test_batch_filter(self):
        """测试：批量过滤"""
        filter = KeywordFilter(["AI"], logger)
        data_list = [
            {"title": "AI新闻", "content": "..."},
            {"title": "天气预报", "content": "..."},
            {"title": "AI算力", "content": "..."}
        ]
        
        result = filter.batch_filter(data_list)
        assert len(result) == 2
```

```python
# tests/test_deduplicator.py

import pytest
from storage.deduplicator import Deduplicator

class TestDeduplicator:
    """去重器单元测试"""
    
    def test_first_time_not_duplicate(self):
        """测试：首次出现的数据不是重复"""
        dedup = Deduplicator("test_index.json", logger)
        data = {"url": "https://example.com/news/1"}
        
        assert dedup.is_duplicate(data, "ndrc") == False
    
    def test_second_time_is_duplicate(self):
        """测试：第二次出现的数据是重复"""
        dedup = Deduplicator("test_index.json", logger)
        data = {"url": "https://example.com/news/1"}
        
        dedup.mark_as_seen(data, "ndrc")
        assert dedup.is_duplicate(data, "ndrc") == True
    
    def test_cninfo_dedup_logic(self):
        """测试：CNInfo 使用组合键去重"""
        dedup = Deduplicator("test_index.json", logger)
        data = {
            "stock_code": "000001",
            "title": "年度报告",
            "publish_time": "2024-01-15T10:00:00Z"
        }
        
        dedup.mark_as_seen(data, "cninfo")
        assert dedup.is_duplicate(data, "cninfo") == True
```


### 集成测试

#### 测试范围

- **爬虫 + 解析器**：测试完整的采集和解析流程
- **过滤器 + 去重器 + 存储**：测试数据处理管道
- **增量更新器 + 爬虫**：测试增量采集逻辑
- **错误处理**：测试各种错误场景

#### 使用 Mock 对象

由于集成测试不应依赖真实的外部网站，我们使用 mock 对象模拟 HTTP 响应。

```python
# tests/test_ndrc_spider_integration.py

import pytest
from unittest.mock import Mock, patch
from spiders.ndrc_spider import NDRCSpider

class TestNDRCSpiderIntegration:
    """发改委爬虫集成测试"""
    
    @patch('requests.get')
    def test_fetch_and_parse_news(self, mock_get):
        """测试：完整的采集和解析流程"""
        # 模拟 HTTP 响应
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'''
        <html>
            <div class="news-list">
                <a href="/news/1">AI政策新闻</a>
            </div>
        </html>
        '''
        mock_get.return_value = mock_response
        
        spider = NDRCSpider(config, logger)
        news_list = spider.fetch_news_list(start_date, end_date)
        
        assert len(news_list) > 0
        assert "AI" in news_list[0]["title"]
    
    @patch('requests.get')
    def test_retry_on_network_error(self, mock_get):
        """测试：网络错误时的重试机制"""
        # 前两次失败，第三次成功
        mock_get.side_effect = [
            requests.Timeout(),
            requests.ConnectionError(),
            Mock(status_code=200, content=b'<html>...</html>')
        ]
        
        spider = NDRCSpider(config, logger)
        result = spider.fetch_news_detail("https://example.com/news/1")
        
        assert result is not None
        assert mock_get.call_count == 3
```


### 端到端测试

#### 测试范围

测试完整的数据采集流程，从启动到数据保存。

```python
# tests/test_e2e.py

import pytest
import json
from pathlib import Path
from main import DataCollector

class TestEndToEnd:
    """端到端测试"""
    
    @pytest.fixture
    def temp_data_dir(self, tmp_path):
        """创建临时数据目录"""
        return tmp_path / "data"
    
    def test_full_collection_pipeline(self, temp_data_dir, mock_responses):
        """测试：完整的采集管道"""
        # 配置使用临时目录
        config = {
            "storage": {"base_path": str(temp_data_dir)},
            # ... 其他配置
        }
        
        collector = DataCollector(config)
        collector.run_once()
        
        # 验证数据文件已创建
        ndrc_file = temp_data_dir / "ndrc" / f"{today}.json"
        assert ndrc_file.exists()
        
        # 验证数据格式
        with open(ndrc_file) as f:
            data = json.load(f)
            assert len(data) > 0
            assert data[0]["source"] == "ndrc"
            assert "title" in data[0]
    
    def test_incremental_update(self, temp_data_dir):
        """测试：增量更新逻辑"""
        collector = DataCollector(config)
        
        # 第一次运行
        stats1 = collector.run_once()
        
        # 第二次运行（应该采集更少的数据）
        stats2 = collector.run_once()
        
        assert stats2["total_fetched"] <= stats1["total_fetched"]
    
    def test_deduplication_works(self, temp_data_dir):
        """测试：去重功能正常工作"""
        collector = DataCollector(config)
        
        # 运行两次
        collector.run_once()
        stats = collector.run_once()
        
        # 第二次运行应该检测到重复
        assert stats["duplicate_count"] > 0
```


### 测试数据准备

#### Mock 数据示例

```python
# tests/fixtures/mock_responses.py

MOCK_NDRC_LIST_HTML = """
<html>
<body>
    <div class="news-list">
        <a href="/news/1">国家发改委发布AI产业发展指导意见</a>
        <a href="/news/2">半导体产业扶持政策出台</a>
    </div>
</body>
</html>
"""

MOCK_NDRC_DETAIL_HTML = """
<html>
<body>
    <h1 class="article-title">国家发改委发布AI产业发展指导意见</h1>
    <span class="publish-time">2024-01-15 10:00:00</span>
    <div class="article-content">
        <p>为推动人工智能产业发展...</p>
    </div>
    <div class="tags">
        <a>AI</a>
        <a>产业政策</a>
    </div>
</body>
</html>
"""

MOCK_CLS_API_RESPONSE = {
    "code": 0,
    "message": "success",
    "data": [
        {
            "title": "AI板块异动拉升",
            "publish_time": "2024-01-15T10:30:00Z",
            "content": "今日AI板块集体拉升...",
            "tags": ["AI", "板块异动"],
            "plate": ["AI", "算力"],
            "level": "重要"
        }
    ]
}

MOCK_CNINFO_API_RESPONSE = {
    "announcements": [
        {
            "announcementId": "1234567",
            "stockCode": "000001",
            "stockName": "平安银行",
            "announcementTitle": "关于AI战略合作的公告",
            "announcementTime": "2024-01-15 10:00:00",
            "announcementType": "重大事项"
        }
    ]
}
```


### 测试覆盖率目标

- **单元测试覆盖率**：≥ 80%
- **集成测试覆盖率**：≥ 60%
- **关键路径覆盖**：100%（采集、解析、存储主流程）

### 测试执行

```bash
# 运行所有测试
pytest tests/

# 运行单元测试
pytest tests/unit/

# 运行集成测试
pytest tests/integration/

# 生成覆盖率报告
pytest --cov=. --cov-report=html tests/

# 运行特定测试
pytest tests/test_keyword_filter.py::TestKeywordFilter::test_filter_with_matching_keyword
```

### 持续集成

建议在 CI/CD 管道中配置：

1. **代码质量检查**：
   - pylint（代码风格）
   - mypy（类型检查）
   - black（代码格式化）

2. **自动化测试**：
   - 每次提交运行单元测试
   - 每次合并运行集成测试
   - 每日运行端到端测试

3. **测试报告**：
   - 生成覆盖率报告
   - 生成测试结果报告
   - 失败时发送通知

### 手动测试场景

某些场景需要手动测试：

1. **真实网站采集**：定期验证爬虫是否仍能正常工作（网站结构可能变化）
2. **性能测试**：测试大量数据采集时的性能表现
3. **长时间运行测试**：测试系统连续运行 24 小时的稳定性
4. **磁盘空间测试**：测试磁盘空间不足时的行为

---

## 附录：项目结构

```
financial-data-collector/
├── main.py                      # 主入口
├── config.py                    # 配置文件
├── requirements.txt             # Python 依赖
├── README.md                    # 项目说明
├── spiders/                     # 爬虫模块
│   ├── __init__.py
│   ├── ndrc_spider.py          # 发改委爬虫
│   ├── cls_spider.py           # 证券报爬虫
│   └── cninfo_spider.py        # 证券信息爬虫
├── parsers/                     # 解析器模块
│   ├── __init__.py
│   ├── ndrc_parser.py
│   ├── cls_parser.py
│   └── cninfo_parser.py
├── filters/                     # 过滤器模块
│   ├── __init__.py
│   ├── keyword_filter.py
│   └── keyword_extractor.py
├── storage/                     # 存储模块
│   ├── __init__.py
│   ├── storage_manager.py
│   ├── deduplicator.py
│   └── incremental_updater.py
├── utils/                       # 工具模块
│   ├── __init__.py
│   ├── logger.py
│   ├── retry.py
│   └── exceptions.py
├── data/                        # 数据目录（运行时创建）
│   ├── ndrc/
│   ├── cls/
│   ├── cninfo/
│   ├── .dedup_index.json
│   └── .incremental_state.json
├── logs/                        # 日志目录（运行时创建）
└── tests/                       # 测试目录
    ├── __init__.py
    ├── unit/
    │   ├── test_keyword_filter.py
    │   ├── test_deduplicator.py
    │   └── ...
    ├── integration/
    │   ├── test_ndrc_spider_integration.py
    │   └── ...
    ├── e2e/
    │   └── test_e2e.py
    └── fixtures/
        └── mock_responses.py
```
