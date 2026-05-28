# -*- coding: utf-8 -*-
"""
日志系统模块

本模块实现了金融数据采集系统的日志记录功能，包括：
- 按日期分割的日志文件（logs/{YYYY-MM-DD}.log）
- 日志轮转（单文件超过 100MB 自动切分）
- 支持 DEBUG、INFO、WARNING、ERROR、CRITICAL 级别
- 同时输出到控制台和文件
- 日志格式：[时间] [级别] [模块名] 消息内容

需求：8.1, 8.2, 8.3, 8.4, 8.5
"""

import logging
import os
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


class DateRotatingFileHandler(logging.Handler):
    """
    按日期轮转的文件处理器
    
    特性：
    - 每天创建新的日志文件（logs/{YYYY-MM-DD}.log）
    - 单个文件超过指定大小时自动切分（添加 .1, .2 等后缀）
    - 保留指定数量的备份文件
    """
    
    def __init__(
        self,
        log_dir: str,
        max_bytes: int = 100 * 1024 * 1024,  # 100MB
        backup_count: int = 10,
        encoding: str = "utf-8"
    ):
        """
        初始化日期轮转文件处理器
        
        Args:
            log_dir: 日志目录路径
            max_bytes: 单个日志文件最大大小（字节）
            backup_count: 保留的备份文件数量
            encoding: 文件编码
        """
        super().__init__()
        self.log_dir = log_dir
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.encoding = encoding
        
        # 确保日志目录存在
        Path(self.log_dir).mkdir(parents=True, exist_ok=True)
        
        # 当前日期和文件处理器
        self.current_date = None
        self.current_handler = None
        
        # 初始化当前日期的处理器
        self._update_handler()
    
    def _get_log_filename(self, date: Optional[datetime] = None) -> str:
        """
        获取日志文件名
        
        Args:
            date: 日期对象，默认为当前日期
        
        Returns:
            日志文件路径
        """
        if date is None:
            date = datetime.now()
        
        date_str = date.strftime("%Y-%m-%d")
        return os.path.join(self.log_dir, f"{date_str}.log")
    
    def _update_handler(self):
        """
        更新文件处理器（检查日期是否变更）
        """
        today = datetime.now().date()
        
        # 如果日期变更或首次初始化，创建新的处理器
        if self.current_date != today:
            # 关闭旧的处理器
            if self.current_handler:
                self.current_handler.close()
            
            # 创建新的轮转文件处理器
            log_filename = self._get_log_filename()
            self.current_handler = RotatingFileHandler(
                filename=log_filename,
                maxBytes=self.max_bytes,
                backupCount=self.backup_count,
                encoding=self.encoding
            )
            
            # 设置格式器（从父处理器继承）
            if hasattr(self, 'formatter') and self.formatter:
                self.current_handler.setFormatter(self.formatter)
            
            # 更新当前日期
            self.current_date = today
    
    def setFormatter(self, fmt):
        """
        设置格式器（同时应用到内部处理器）
        
        Args:
            fmt: 格式器对象
        """
        super().setFormatter(fmt)
        # 如果内部处理器已存在，也设置其格式器
        if self.current_handler:
            self.current_handler.setFormatter(fmt)
    
    def emit(self, record):
        """
        发送日志记录
        
        Args:
            record: 日志记录对象
        """
        try:
            # 检查是否需要更新处理器（日期变更）
            self._update_handler()
            
            # 使用当前处理器发送日志
            if self.current_handler:
                self.current_handler.emit(record)
        except Exception:
            self.handleError(record)
    
    def close(self):
        """
        关闭处理器
        """
        if self.current_handler:
            self.current_handler.close()
        super().close()


def setup_logger(
    name: str,
    log_dir: str = "./logs",
    log_level: str = "INFO",
    max_file_size: int = 100 * 1024 * 1024,  # 100MB
    backup_count: int = 10,
    console_output: bool = True,
    console_level: str = "INFO",
    log_format: Optional[str] = None,
    date_format: Optional[str] = None,
    encoding: str = "utf-8"
) -> logging.Logger:
    """
    设置并返回配置好的日志记录器
    
    Args:
        name: 日志记录器名称（通常使用模块名）
        log_dir: 日志目录路径
        log_level: 文件日志级别（DEBUG, INFO, WARNING, ERROR, CRITICAL）
        max_file_size: 单个日志文件最大大小（字节）
        backup_count: 保留的备份文件数量
        console_output: 是否同时输出到控制台
        console_level: 控制台日志级别
        log_format: 日志格式字符串
        date_format: 日期格式字符串
        encoding: 文件编码
    
    Returns:
        配置好的日志记录器
    
    示例:
        >>> logger = setup_logger("my_module")
        >>> logger.info("这是一条信息日志")
        >>> logger.error("这是一条错误日志")
    """
    # 创建日志记录器
    logger = logging.getLogger(name)
    
    # 如果已经配置过，直接返回
    if logger.handlers:
        return logger
    
    # 设置日志级别
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # 设置日志格式
    if log_format is None:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    if date_format is None:
        date_format = "%Y-%m-%d %H:%M:%S"
    
    formatter = logging.Formatter(log_format, datefmt=date_format)
    
    # 添加文件处理器（按日期轮转）
    file_handler = DateRotatingFileHandler(
        log_dir=log_dir,
        max_bytes=max_file_size,
        backup_count=backup_count,
        encoding=encoding
    )
    file_handler.setLevel(getattr(logging, log_level.upper()))
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # 添加控制台处理器（可选）
    if console_output:
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, console_level.upper()))
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # 防止日志传播到父记录器
    logger.propagate = False
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    获取已配置的日志记录器
    
    如果日志记录器尚未配置，将使用默认配置创建
    
    Args:
        name: 日志记录器名称
    
    Returns:
        日志记录器
    
    示例:
        >>> logger = get_logger(__name__)
        >>> logger.info("使用默认配置的日志记录器")
    """
    logger = logging.getLogger(name)
    
    # 如果尚未配置，使用默认配置
    if not logger.handlers:
        # 尝试从 config 模块加载配置
        try:
            from config import LOGGING_CONFIG
            return setup_logger(
                name=name,
                log_dir=LOGGING_CONFIG.get("log_dir", "./logs"),
                log_level=LOGGING_CONFIG.get("log_level", "INFO"),
                max_file_size=LOGGING_CONFIG.get("max_file_size", 100 * 1024 * 1024),
                backup_count=LOGGING_CONFIG.get("backup_count", 10),
                console_output=LOGGING_CONFIG.get("console_output", True),
                console_level=LOGGING_CONFIG.get("console_level", "INFO"),
                log_format=LOGGING_CONFIG.get("format"),
                date_format=LOGGING_CONFIG.get("date_format"),
                encoding=LOGGING_CONFIG.get("encoding", "utf-8")
            )
        except ImportError:
            # 如果无法导入配置，使用默认配置
            return setup_logger(name=name)
    
    return logger


def cleanup_old_logs(log_dir: str, retention_days: int):
    """
    清理旧的日志文件
    
    Args:
        log_dir: 日志目录路径
        retention_days: 保留天数（删除超过此天数的日志文件）
    
    示例:
        >>> cleanup_old_logs("./logs", 30)  # 删除 30 天前的日志
    """
    if retention_days <= 0:
        return
    
    log_path = Path(log_dir)
    if not log_path.exists():
        return
    
    # 计算截止日期
    cutoff_date = datetime.now().timestamp() - (retention_days * 24 * 60 * 60)
    
    # 遍历日志文件
    deleted_count = 0
    for log_file in log_path.glob("*.log*"):
        try:
            # 检查文件修改时间
            if log_file.stat().st_mtime < cutoff_date:
                log_file.unlink()
                deleted_count += 1
        except Exception as e:
            # 忽略删除失败的文件
            print(f"无法删除日志文件 {log_file}: {e}")
    
    if deleted_count > 0:
        print(f"已清理 {deleted_count} 个旧日志文件")


# ============================================================================
# 便捷函数
# ============================================================================

def log_exception(logger: logging.Logger, message: str, exc_info: bool = True):
    """
    记录异常信息（包含完整堆栈跟踪）
    
    Args:
        logger: 日志记录器
        message: 错误消息
        exc_info: 是否包含异常信息
    
    示例:
        >>> try:
        ...     1 / 0
        ... except Exception:
        ...     log_exception(logger, "发生除零错误")
    """
    logger.error(message, exc_info=exc_info)


def log_statistics(logger: logging.Logger, stats: dict):
    """
    记录统计信息
    
    Args:
        logger: 日志记录器
        stats: 统计数据字典
    
    示例:
        >>> stats = {
        ...     "total": 100,
        ...     "success": 95,
        ...     "failed": 5
        ... }
        >>> log_statistics(logger, stats)
    """
    stats_str = ", ".join(f"{key}={value}" for key, value in stats.items())
    logger.info(f"统计信息: {stats_str}")


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    "DateRotatingFileHandler",
    "setup_logger",
    "get_logger",
    "cleanup_old_logs",
    "log_exception",
    "log_statistics",
]
