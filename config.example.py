# -*- coding: utf-8 -*-
"""
金融数据采集系统配置模板

这是一个配置模板文件，展示了所有可配置的选项。
复制此文件为 config.py 并根据需要修改配置。

使用方法：
    cp config.example.py config.py
    # 编辑 config.py 修改配置
    python main.py
"""

import os

# ============================================================================
# 环境配置
# ============================================================================

# 运行环境：development（开发）或 production（生产）
ENVIRONMENT = os.getenv("DATA_COLLECTOR_ENV", "development")

# ============================================================================
# 数据源配置
# ============================================================================

# 发改委（NDRC）配置
NDRC_CONFIG = {
    "base_url": "https://www.ndrc.gov.cn",
    "list_url": "https://www.ndrc.gov.cn/fgsj/",  # 新闻列表页
    "timeout": 30,  # 请求超时时间（秒）
    "retry_times": 3,  # 最大重试次数
    "retry_delays": [1, 2, 4],  # 指数退避延迟（秒）
    "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}

# 证券报（CLS）配置
CLS_CONFIG = {
    "base_url": "https://www.cls.cn",
    "api_endpoints": {
        "telegraph": "/api/telegraph",  # 电报 API
        "ai_news": "/api/ai-news",  # AI新闻 API
        "plate_movement": "/api/plate-movement",  # 板块异动 API
        "limit_up_logic": "/api/limit-up-logic",  # 涨停逻辑 API
        "hot_topics": "/api/hot-topics",  # 热点题材 API
        "industry_chain": "/api/industry-chain",  # 产业链新闻 API
    },
    "api_key": os.getenv("CLS_API_KEY", ""),  # API 密钥（如果需要）
    "api_token": os.getenv("CLS_API_TOKEN", ""),  # API 令牌（如果需要）
    "interval": 60,  # 采集间隔（秒）
    "timeout": 30,
    "retry_times": 3,
    "retry_delays": [1, 2, 4],
    "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}

# 证券信息网（CNInfo）配置
CNINFO_CONFIG = {
    "base_url": "https://www.cninfo.com.cn",
    "api_endpoints": {
        "announcement_list": "/new/announcement/query",  # 公告列表 API
        "announcement_detail": "/new/announcement/detail",  # 公告详情 API
    },
    "timeout": 30,
    "retry_times": 3,
    "retry_delays": [1, 2, 4],
    "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}

# ============================================================================
# 关键词配置
# ============================================================================

# 股票关键词列表（用于过滤发改委和证券报新闻）
STOCK_KEYWORDS = [
    # AI 和算力相关
    "AI算力", "人工智能", "大模型", "ChatGPT", "深度学习",
    "GPU", "芯片", "算力网络", "智算中心",
    
    # 半导体相关
    "半导体芯片", "集成电路", "晶圆", "光刻机", "EDA",
    "芯片设计", "芯片制造", "封装测试",
    
    # 新能源相关
    "新能源", "光伏", "风电", "储能", "电池",
    "新能源汽车", "充电桩",
    
    # 机器人和自动化
    "机器人", "工业机器人", "服务机器人", "自动化",
    "智能制造", "工业4.0",
    
    # 数字经济
    "数据中心", "数据要素", "数字经济", "云计算",
    "大数据", "区块链",
    
    # 新基建
    "新基建", "5G", "物联网", "工业互联网",
    
    # 其他热点
    "低空经济", "无人机", "卫星互联网",
]

# 证券信息网关键词列表（用于过滤公司公告）
CNINFO_KEYWORDS = [
    # 合作和订单
    "AI合作", "算力订单", "中标大合同", "战略合作",
    "签订合同", "重大合同",
    
    # 资本运作
    "回购增持", "并购重组", "股权转让", "定向增发",
    "配股", "可转债",
    
    # 技术和产品
    "GPU", "数据中心", "芯片", "半导体",
    "新产品", "技术突破", "专利",
    
    # 业绩相关
    "业绩预告", "业绩快报", "分红", "利润分配",
]

# ============================================================================
# 存储配置
# ============================================================================

STORAGE_CONFIG = {
    "base_path": "./data",  # 数据存储根目录
    "min_disk_space": 1 * 1024 * 1024 * 1024,  # 最小磁盘空间要求：1GB
    "file_format": "json",  # 数据文件格式
    "encoding": "utf-8",  # 文件编码
    "date_format": "%Y-%m-%d",  # 日期格式
}

# ============================================================================
# 日志配置
# ============================================================================

LOGGING_CONFIG = {
    "log_dir": "./logs",  # 日志目录
    "log_level": "INFO",  # 日志级别：DEBUG, INFO, WARNING, ERROR, CRITICAL
    "max_file_size": 100 * 1024 * 1024,  # 单个日志文件最大大小：100MB
    "backup_count": 10,  # 保留的日志文件数量
    "date_format": "%Y-%m-%d",  # 日志文件日期格式
    "log_format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
}

# ============================================================================
# 增量更新配置
# ============================================================================

INCREMENTAL_CONFIG = {
    "state_file": "./data/.incremental_state.json",  # 状态文件路径
    "default_days": 7,  # 首次运行时默认采集的天数
    "enable_incremental": True,  # 是否启用增量更新
}

# ============================================================================
# 去重配置
# ============================================================================

DEDUP_CONFIG = {
    "index_file": "./data/.dedup_index.json",  # 去重索引文件路径
    "hash_algorithm": "sha256",  # 哈希算法
    "enable_dedup": True,  # 是否启用去重
}

# ============================================================================
# 错误处理配置
# ============================================================================

ERROR_HANDLING_CONFIG = {
    "failure_threshold": 5,  # 连续失败阈值（超过此值将暂停数据源）
    "pause_duration_hours": 1,  # 暂停时长（小时）
    "enable_failure_tracking": True,  # 是否启用失败跟踪
}

# ============================================================================
# 告警配置（可选）
# ============================================================================

ALERT_CONFIG = {
    "enable_alert": False,  # 是否启用告警
    "alert_email": os.getenv("ALERT_EMAIL", ""),  # 告警邮箱
    "smtp_server": os.getenv("SMTP_SERVER", "smtp.gmail.com"),
    "smtp_port": int(os.getenv("SMTP_PORT", "587")),
    "smtp_user": os.getenv("SMTP_USER", ""),
    "smtp_password": os.getenv("SMTP_PASSWORD", ""),
}

# ============================================================================
# 工具函数
# ============================================================================

def create_directories():
    """创建必要的目录"""
    import os
    
    directories = [
        STORAGE_CONFIG["base_path"],
        LOGGING_CONFIG["log_dir"],
        os.path.join(STORAGE_CONFIG["base_path"], "ndrc"),
        os.path.join(STORAGE_CONFIG["base_path"], "cls"),
        os.path.join(STORAGE_CONFIG["base_path"], "cninfo"),
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)


def validate_config():
    """
    验证配置的有效性
    
    Returns:
        (is_valid, errors): 是否有效和错误列表
    """
    errors = []
    
    # 检查必需的配置项
    if not NDRC_CONFIG.get("base_url"):
        errors.append("NDRC_CONFIG.base_url 未配置")
    
    if not CLS_CONFIG.get("base_url"):
        errors.append("CLS_CONFIG.base_url 未配置")
    
    if not CNINFO_CONFIG.get("base_url"):
        errors.append("CNINFO_CONFIG.base_url 未配置")
    
    # 检查关键词列表
    if not STOCK_KEYWORDS:
        errors.append("STOCK_KEYWORDS 为空，建议添加关键词")
    
    if not CNINFO_KEYWORDS:
        errors.append("CNINFO_KEYWORDS 为空，建议添加关键词")
    
    # 检查存储路径
    if not STORAGE_CONFIG.get("base_path"):
        errors.append("STORAGE_CONFIG.base_path 未配置")
    
    # 检查日志路径
    if not LOGGING_CONFIG.get("log_dir"):
        errors.append("LOGGING_CONFIG.log_dir 未配置")
    
    # 检查日志级别
    valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if LOGGING_CONFIG.get("log_level") not in valid_log_levels:
        errors.append(f"LOGGING_CONFIG.log_level 无效，必须是 {valid_log_levels} 之一")
    
    return len(errors) == 0, errors


# ============================================================================
# 配置验证（导入时自动执行）
# ============================================================================

if __name__ == "__main__":
    # 验证配置
    is_valid, errors = validate_config()
    
    if is_valid:
        print("✓ 配置验证通过")
    else:
        print("✗ 配置验证失败:")
        for error in errors:
            print(f"  - {error}")
