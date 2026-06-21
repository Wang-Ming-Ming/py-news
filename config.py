# -*- coding: utf-8 -*-
"""
配置管理模块

本模块定义了金融数据采集系统的所有配置参数，包括：
- 数据源配置（NDRC、CLS、CNInfo）
- 关键词配置
- 存储配置
- 日志配置
- 增量更新配置
- 去重配置

支持环境特定配置（开发/生产）
"""

import os
from typing import Dict, List, Any, Optional
from pathlib import Path


# ============================================================================
# 环境配置
# ============================================================================

# 当前环境：development 或 production
ENVIRONMENT = os.getenv("DATA_COLLECTOR_ENV", "development")


# ============================================================================
# 数据源配置
# ============================================================================

# 发改委（NDRC）配置
NDRC_CONFIG = {
    "base_url": "https://www.ndrc.gov.cn",
    "timeout": 30,  # 请求超时时间（秒）
    "retry_times": 3,  # 最大重试次数
    "retry_delays": [1, 2, 4],  # 指数退避延迟（秒）
    "min_request_interval": 1.0,
    "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "encoding": "utf-8",  # 默认编码
    "enable_keyword_filter": False,  # 作为数据源默认保存全部，关键词仅用于标注
    # XPath 表达式（需要根据实际网站结构调整）
    "xpath": {
        "news_list": "//a[contains(@href, '/t20') or contains(@href, './') or contains(@href, '../')]/@href",
        "title": "//meta[@name='ArticleTitle']/@content | //div[contains(@class, 'article')]//*[contains(@class, 'title')][1]//text() | //h1//text()",
        "publish_time": "//meta[@name='PubDate']/@content | //span[contains(text(), '发布时间')]/text() | //div[contains(@class, 'article')]//*[contains(text(), '发布时间')]/text()",
        "content": "//*[contains(@class, 'TRS_Editor')]//text() | //div[contains(@class, 'article')]//p//text()",
        "tags": "//div[@class='tags']//a/text()",
    }
}

# 中国证券报（CLS）配置
CLS_CONFIG = {
    "base_url": "https://www.cls.cn",
    # 财联社网页端滚动电报接口，需要按网页端规则附带 sign 参数
    "api_endpoints": {
        "telegraph": "/v1/roll/get_roll_list",
    },
    "interval": 60,  # 采集间隔（秒）
    "timeout": 30,  # 请求超时时间（秒）
    "retry_times": 3,  # 最大重试次数
    "retry_delays": [1, 2, 4],  # 指数退避延迟（秒）
    "min_request_interval": 1.0,
    "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # API 认证参数（如需要）
    "api_key": os.getenv("CLS_API_KEY", ""),
    "api_token": os.getenv("CLS_API_TOKEN", ""),
}

# 中国证券信息网（CNInfo）配置
CNINFO_CONFIG = {
    "base_url": "https://www.cninfo.com.cn",
    # 巨潮资讯历史公告查询接口
    "api_endpoints": {
        "announcement_list": "/new/hisAnnouncement/query",
        "announcement_detail": "/new/announcement/detail",
        "pdf_download": "/new/announcement/download",
    },
    "timeout": 30,  # 请求超时时间（秒）
    "retry_times": 3,  # 最大重试次数
    "retry_delays": [1, 2, 4],  # 指数退避延迟（秒）
    "min_request_interval": 1.0,
    "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # 巨潮公告正文以 PDF 链接形式提供，由下游分析系统按需读取
    "enable_keyword_filter": False,  # 作为数据源默认保存全部，关键词仅用于标注
}

# 东方财富全球财经快讯配置（通过 AKShare 调用）
EASTMONEY_GLOBAL_CONFIG = {
    "base_url": "https://finance.eastmoney.com",
    "timeout": 30,
    "retry_times": 3,
    "retry_delays": [1, 2, 4],
    "limit": 200,
    "min_request_interval": 1.0,
    "enable_keyword_filter": False,
}


# ============================================================================
# 关键词配置
# ============================================================================

# 股票关键词（用于发改委和证券报数据过滤）
STOCK_KEYWORDS = [
    "AI算力",
    "半导体芯片",
    "新能源",
    "机器人",
    "数据中心",
    "数据要素",
    "低空经济",
    "数字经济",
    "新基建",
    # 可以添加更多关键词
    "人工智能",
    "AI",
    "芯片",
    "集成电路",
    "光伏",
    "风电",
    "储能",
    "自动驾驶",
    "工业机器人",
    "云计算",
    "大数据",
]

# 证券信息网关键词（用于公告过滤）
CNINFO_KEYWORDS = [
    "AI合作",
    "算力订单",
    "中标大合同",
    "回购增持",
    "并购重组",
    "战略合作",
    "GPU",
    "数据中心",
    # 可以添加更多关键词
    "重大合同",
    "股权激励",
    "定增",
    "配股",
    "业绩预告",
    "业绩快报",
]


# ============================================================================
# 存储配置
# ============================================================================

STORAGE_CONFIG = {
    "base_path": "./data",  # 数据存储根目录
    "min_disk_space": 1 * 1024 * 1024 * 1024,  # 最小磁盘空间要求：1GB
    "file_format": "json",  # 数据文件格式
    "encoding": "utf-8",  # 文件编码
    # 文件路径模式：{base_path}/{source}/{YYYY-MM-DD}.json
    "path_pattern": "{base_path}/{source}/{date}.json",
    # 是否启用数据压缩
    "enable_compression": False,
    # 原始新闻/公告永久按日期保留；API 通过独立查询窗口限制返回量。
    "retention_days": 0,
}


# ============================================================================
# 日志配置
# ============================================================================

LOGGING_CONFIG = {
    "log_dir": "./logs",  # 日志目录
    "log_level": "INFO",  # 日志级别：DEBUG, INFO, WARNING, ERROR, CRITICAL
    "max_file_size": 100 * 1024 * 1024,  # 单个日志文件最大大小：100MB
    "backup_count": 10,  # 保留的日志文件数量
    "retention_days": 30,  # 按日期清理旧日志
    "encoding": "utf-8",  # 日志文件编码
    # 日志格式
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "date_format": "%Y-%m-%d %H:%M:%S",
    # 日志文件名模式：{log_dir}/{YYYY-MM-DD}.log
    "filename_pattern": "{log_dir}/{date}.log",
    # 是否同时输出到控制台
    "console_output": True,
    # 控制台日志级别（可以与文件日志级别不同）
    "console_level": "INFO",
}


# ============================================================================
# 增量更新配置
# ============================================================================

INCREMENTAL_CONFIG = {
    "state_file": "./data/.incremental_state.json",  # 状态文件路径
    "default_days": 15,  # 首次运行时默认补采最近半个月
    "enable_incremental": True,  # 是否启用增量更新
    # 时间戳格式
    "timestamp_format": "%Y-%m-%dT%H:%M:%SZ",
}


# ============================================================================
# 去重配置
# ============================================================================

DEDUP_CONFIG = {
    "index_file": "./data/.dedup_index.json",  # 去重索引文件路径
    "hash_algorithm": "sha256",  # 哈希算法：md5, sha1, sha256
    "enable_dedup": True,  # 是否启用去重
    # 去重索引最大条目数（超过后清理旧条目）
    "max_index_size": 1000000,  # 100万条
    # 去重索引保留天数
    "index_retention_days": 30,
}


# ============================================================================
# 错误处理配置
# ============================================================================

ERROR_HANDLING_CONFIG = {
    # 连续失败阈值（超过后暂停数据源）
    "failure_threshold": 5,
    # 暂停时长（小时）
    "pause_duration_hours": 1,
    # 是否在连续失败时发送警报
    "enable_alerts": False,
    # 警报接收邮箱（如果启用警报）
    "alert_email": os.getenv("ALERT_EMAIL", ""),
}


# ============================================================================
# 环境特定配置
# ============================================================================

# 开发环境配置覆盖
DEVELOPMENT_CONFIG = {
    "LOGGING_CONFIG": {
        "log_level": "DEBUG",
        "console_level": "DEBUG",
    },
    "STORAGE_CONFIG": {
        "base_path": "./data_dev",
    },
    "CLS_CONFIG": {
        "interval": 300,  # 开发环境采集间隔更长：5分钟
    },
}

# 生产环境配置覆盖
PRODUCTION_CONFIG = {
    "LOGGING_CONFIG": {
        "log_level": "INFO",
        "console_level": "WARNING",
    },
    "ERROR_HANDLING_CONFIG": {
        "enable_alerts": True,
    },
}


# ============================================================================
# 配置验证函数
# ============================================================================

def validate_config() -> tuple[bool, List[str]]:
    """
    验证配置的有效性
    
    Returns:
        (is_valid, errors): 验证结果和错误列表
    """
    errors = []
    
    # 验证数据源配置
    for source_name, source_config in [
        ("NDRC_CONFIG", NDRC_CONFIG),
        ("CLS_CONFIG", CLS_CONFIG),
        ("CNINFO_CONFIG", CNINFO_CONFIG),
        ("EASTMONEY_GLOBAL_CONFIG", EASTMONEY_GLOBAL_CONFIG),
    ]:
        # 检查必需字段
        required_fields = ["base_url", "timeout", "retry_times"]
        for field in required_fields:
            if field not in source_config:
                errors.append(f"{source_name} 缺少必需字段: {field}")
        
        # 验证超时值
        if source_config.get("timeout", 0) <= 0:
            errors.append(f"{source_name}.timeout 必须大于 0")
        
        # 验证重试次数
        if source_config.get("retry_times", 0) < 0:
            errors.append(f"{source_name}.retry_times 不能为负数")
        
        # 验证重试延迟
        retry_delays = source_config.get("retry_delays", [])
        if len(retry_delays) != source_config.get("retry_times", 0):
            errors.append(
                f"{source_name}.retry_delays 长度必须等于 retry_times"
            )
    
    # 验证关键词配置
    if not STOCK_KEYWORDS:
        errors.append("STOCK_KEYWORDS 不能为空")
    
    if not CNINFO_KEYWORDS:
        errors.append("CNINFO_KEYWORDS 不能为空")
    
    # 验证存储配置
    if STORAGE_CONFIG["min_disk_space"] <= 0:
        errors.append("STORAGE_CONFIG.min_disk_space 必须大于 0")
    
    # 验证日志配置
    valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if LOGGING_CONFIG["log_level"] not in valid_log_levels:
        errors.append(
            f"LOGGING_CONFIG.log_level 必须是以下之一: {valid_log_levels}"
        )
    
    if LOGGING_CONFIG["max_file_size"] <= 0:
        errors.append("LOGGING_CONFIG.max_file_size 必须大于 0")
    
    if LOGGING_CONFIG["backup_count"] < 0:
        errors.append("LOGGING_CONFIG.backup_count 不能为负数")
    
    # 验证增量更新配置
    if INCREMENTAL_CONFIG["default_days"] <= 0:
        errors.append("INCREMENTAL_CONFIG.default_days 必须大于 0")
    
    # 验证去重配置
    valid_hash_algorithms = ["md5", "sha1", "sha256"]
    if DEDUP_CONFIG["hash_algorithm"] not in valid_hash_algorithms:
        errors.append(
            f"DEDUP_CONFIG.hash_algorithm 必须是以下之一: {valid_hash_algorithms}"
        )
    
    if DEDUP_CONFIG["max_index_size"] <= 0:
        errors.append("DEDUP_CONFIG.max_index_size 必须大于 0")
    
    # 验证错误处理配置
    if ERROR_HANDLING_CONFIG["failure_threshold"] <= 0:
        errors.append("ERROR_HANDLING_CONFIG.failure_threshold 必须大于 0")
    
    if ERROR_HANDLING_CONFIG["pause_duration_hours"] <= 0:
        errors.append("ERROR_HANDLING_CONFIG.pause_duration_hours 必须大于 0")
    
    return len(errors) == 0, errors


def apply_environment_config():
    """
    根据当前环境应用配置覆盖
    """
    global LOGGING_CONFIG, STORAGE_CONFIG, CLS_CONFIG, ERROR_HANDLING_CONFIG
    
    if ENVIRONMENT == "development":
        config_override = DEVELOPMENT_CONFIG
    elif ENVIRONMENT == "production":
        config_override = PRODUCTION_CONFIG
    else:
        # 未知环境，不应用覆盖
        return
    
    # 应用配置覆盖
    if "LOGGING_CONFIG" in config_override:
        LOGGING_CONFIG.update(config_override["LOGGING_CONFIG"])
    
    if "STORAGE_CONFIG" in config_override:
        STORAGE_CONFIG.update(config_override["STORAGE_CONFIG"])
    
    if "CLS_CONFIG" in config_override:
        CLS_CONFIG.update(config_override["CLS_CONFIG"])
    
    if "ERROR_HANDLING_CONFIG" in config_override:
        ERROR_HANDLING_CONFIG.update(config_override["ERROR_HANDLING_CONFIG"])


def get_config(config_name: str) -> Optional[Dict[str, Any]]:
    """
    获取指定的配置字典
    
    Args:
        config_name: 配置名称（如 "NDRC_CONFIG", "LOGGING_CONFIG"）
    
    Returns:
        配置字典，如果不存在返回 None
    """
    config_map = {
        "NDRC_CONFIG": NDRC_CONFIG,
        "CLS_CONFIG": CLS_CONFIG,
        "CNINFO_CONFIG": CNINFO_CONFIG,
        "EASTMONEY_GLOBAL_CONFIG": EASTMONEY_GLOBAL_CONFIG,
        "STOCK_KEYWORDS": {"keywords": STOCK_KEYWORDS},
        "CNINFO_KEYWORDS": {"keywords": CNINFO_KEYWORDS},
        "STORAGE_CONFIG": STORAGE_CONFIG,
        "LOGGING_CONFIG": LOGGING_CONFIG,
        "INCREMENTAL_CONFIG": INCREMENTAL_CONFIG,
        "DEDUP_CONFIG": DEDUP_CONFIG,
        "ERROR_HANDLING_CONFIG": ERROR_HANDLING_CONFIG,
    }
    
    return config_map.get(config_name)


def create_directories():
    """
    创建必要的目录结构
    """
    directories = [
        STORAGE_CONFIG["base_path"],
        LOGGING_CONFIG["log_dir"],
        os.path.dirname(INCREMENTAL_CONFIG["state_file"]),
        os.path.dirname(DEDUP_CONFIG["index_file"]),
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)


# ============================================================================
# 初始化
# ============================================================================

# 应用环境特定配置
apply_environment_config()

# 验证配置
is_valid, validation_errors = validate_config()
if not is_valid:
    import warnings
    warnings.warn(
        f"配置验证失败，发现 {len(validation_errors)} 个错误:\n" +
        "\n".join(f"  - {error}" for error in validation_errors)
    )


# ============================================================================
# 导出配置
# ============================================================================

__all__ = [
    "ENVIRONMENT",
    "NDRC_CONFIG",
    "CLS_CONFIG",
    "CNINFO_CONFIG",
    "EASTMONEY_GLOBAL_CONFIG",
    "STOCK_KEYWORDS",
    "CNINFO_KEYWORDS",
    "STORAGE_CONFIG",
    "LOGGING_CONFIG",
    "INCREMENTAL_CONFIG",
    "DEDUP_CONFIG",
    "ERROR_HANDLING_CONFIG",
    "DEVELOPMENT_CONFIG",
    "PRODUCTION_CONFIG",
    "validate_config",
    "apply_environment_config",
    "get_config",
    "create_directories",
]
