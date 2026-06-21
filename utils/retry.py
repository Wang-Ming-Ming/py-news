# -*- coding: utf-8 -*-
"""
重试机制模块

本模块实现了数据采集系统的重试机制，包括：
- RetryHandler: 支持指数退避的重试处理器
- FailureTracker: 跟踪连续失败次数的失败跟踪器

用于处理网络请求失败、API 调用失败等临时性错误。
"""

import time
import logging
from typing import Callable, Any, List, Dict, Optional
from datetime import datetime, timedelta
from functools import wraps

from .exceptions import NetworkException, APIException


class RetryHandler:
    """
    重试处理器
    
    支持指数退避策略的重试机制。当函数执行失败时，
    会按照配置的延迟时间进行重试，直到成功或达到最大重试次数。
    
    Attributes:
        max_retries: 最大重试次数
        delays: 每次重试的延迟时间列表（秒）
        logger: 日志记录器
    """
    
    def __init__(
        self, 
        max_retries: int = 3, 
        delays: List[int] = None,
        logger: logging.Logger = None
    ):
        """
        初始化重试处理器
        
        Args:
            max_retries: 最大重试次数，默认 3 次
            delays: 每次重试的延迟时间列表（秒），默认 [1, 2, 4]（指数退避）
            logger: 日志记录器，如果为 None 则创建默认记录器
        """
        self.max_retries = max_retries
        self.delays = delays if delays is not None else [1, 2, 4]
        self.logger = logger or logging.getLogger(__name__)
        
        # 验证配置
        if self.max_retries < 0:
            raise ValueError("max_retries 不能为负数")
        
        if len(self.delays) < self.max_retries:
            # 如果延迟列表长度不足，使用最后一个延迟值填充
            last_delay = self.delays[-1] if self.delays else 1
            self.delays.extend([last_delay] * (self.max_retries - len(self.delays)))
    
    def execute_with_retry(
        self, 
        func: Callable, 
        *args, 
        **kwargs
    ) -> Any:
        """
        执行函数并在失败时重试
        
        Args:
            func: 要执行的函数
            *args: 函数的位置参数
            **kwargs: 函数的关键字参数
        
        Returns:
            函数执行结果
        
        Raises:
            最后一次尝试的异常
        
        实现逻辑：
        1. 尝试执行函数
        2. 如果成功，返回结果
        3. 如果失败，等待指定时间后重试
        4. 使用指数退避策略
        5. 记录每次重试的日志
        6. 如果所有重试都失败，抛出最后一次的异常
        """
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                # 尝试执行函数
                result = func(*args, **kwargs)
                
                # 如果不是第一次尝试，记录成功日志
                if attempt > 0:
                    self.logger.info(
                        f"重试成功: {func.__name__} "
                        f"(第 {attempt + 1} 次尝试)"
                    )
                
                return result
            except APIException as e:
                last_exception = e
                if e.status_code in (403, 429):
                    self.logger.warning(
                        f"上游返回 HTTP {e.status_code}，本轮不继续重试，交由来源级退避处理"
                    )
                    raise
                if attempt < self.max_retries:
                    delay = self.delays[attempt]
                    self.logger.warning(
                        f"执行失败: {func.__name__} "
                        f"(第 {attempt + 1}/{self.max_retries + 1} 次尝试) "
                        f"| 错误: {str(e)} | {delay} 秒后重试..."
                    )
                    time.sleep(delay)
                else:
                    self.logger.error(f"执行失败，已达最大重试次数: {func.__name__}")
            except Exception as e:
                last_exception = e
                
                # 如果还有重试机会
                if attempt < self.max_retries:
                    delay = self.delays[attempt]
                    self.logger.warning(
                        f"执行失败: {func.__name__} "
                        f"(第 {attempt + 1}/{self.max_retries + 1} 次尝试) "
                        f"| 错误: {str(e)} "
                        f"| {delay} 秒后重试..."
                    )
                    time.sleep(delay)
                else:
                    # 所有重试都失败
                    self.logger.error(
                        f"执行失败，已达最大重试次数: {func.__name__} "
                        f"(共 {self.max_retries + 1} 次尝试) "
                        f"| 最后错误: {str(e)}",
                        exc_info=True
                    )
        
        # 抛出最后一次的异常
        raise last_exception
    
    def retry_on_exception(
        self, 
        exceptions: tuple = (Exception,)
    ):
        """
        装饰器：为函数添加重试机制
        
        Args:
            exceptions: 需要重试的异常类型元组，默认捕获所有异常
        
        Returns:
            装饰器函数
        
        使用示例：
            @retry_handler.retry_on_exception(exceptions=(NetworkException, APIException))
            def fetch_data(url):
                # 网络请求代码
                pass
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                last_exception = None
                
                for attempt in range(self.max_retries + 1):
                    try:
                        result = func(*args, **kwargs)
                        
                        if attempt > 0:
                            self.logger.info(
                                f"重试成功: {func.__name__} "
                                f"(第 {attempt + 1} 次尝试)"
                            )
                        
                        return result
                        
                    except exceptions as e:
                        last_exception = e
                        
                        if attempt < self.max_retries:
                            delay = self.delays[attempt]
                            self.logger.warning(
                                f"执行失败: {func.__name__} "
                                f"(第 {attempt + 1}/{self.max_retries + 1} 次尝试) "
                                f"| 错误: {str(e)} "
                                f"| {delay} 秒后重试..."
                            )
                            time.sleep(delay)
                        else:
                            self.logger.error(
                                f"执行失败，已达最大重试次数: {func.__name__} "
                                f"(共 {self.max_retries + 1} 次尝试) "
                                f"| 最后错误: {str(e)}",
                                exc_info=True
                            )
                
                raise last_exception
            
            return wrapper
        return decorator


class FailureTracker:
    """
    失败跟踪器
    
    跟踪每个数据源的连续失败次数。当连续失败次数超过阈值时，
    可以暂停该数据源的采集，避免浪费资源。
    
    Attributes:
        threshold: 连续失败阈值
        pause_duration_hours: 暂停时长（小时）
        logger: 日志记录器
        failure_counts: 每个数据源的失败计数
        paused_until: 每个数据源的暂停截止时间
    """
    
    def __init__(
        self, 
        threshold: int = 5,
        pause_duration_hours: int = 1,
        logger: logging.Logger = None
    ):
        """
        初始化失败跟踪器
        
        Args:
            threshold: 连续失败阈值，默认 5 次
            pause_duration_hours: 暂停时长（小时），默认 1 小时
            logger: 日志记录器，如果为 None 则创建默认记录器
        """
        self.threshold = threshold
        self.pause_duration_hours = pause_duration_hours
        self.logger = logger or logging.getLogger(__name__)
        
        # 每个数据源的失败计数
        self.failure_counts: Dict[str, int] = {}
        
        # 每个数据源的暂停截止时间
        self.paused_until: Dict[str, datetime] = {}
        
        # 验证配置
        if self.threshold <= 0:
            raise ValueError("threshold 必须大于 0")
        
        if self.pause_duration_hours <= 0:
            raise ValueError("pause_duration_hours 必须大于 0")
    
    def record_failure(self, source: str):
        """
        记录失败
        
        Args:
            source: 数据源名称（如 "ndrc", "cls", "cninfo"）
        """
        # 增加失败计数
        self.failure_counts[source] = self.failure_counts.get(source, 0) + 1
        
        current_count = self.failure_counts[source]
        
        self.logger.warning(
            f"数据源 {source} 失败 "
            f"(连续失败 {current_count} 次)"
        )
        
        # 检查是否达到阈值
        if current_count >= self.threshold:
            self.logger.critical(
                f"数据源 {source} 连续失败 {current_count} 次，"
                f"已达阈值 {self.threshold}，暂停采集 {self.pause_duration_hours} 小时"
            )
            self.pause_source(source, hours=self.pause_duration_hours)
    
    def record_success(self, source: str):
        """
        记录成功，重置失败计数
        
        Args:
            source: 数据源名称
        """
        # 如果之前有失败记录，记录恢复日志
        if source in self.failure_counts and self.failure_counts[source] > 0:
            self.logger.info(
                f"数据源 {source} 恢复正常，"
                f"重置失败计数（之前连续失败 {self.failure_counts[source]} 次）"
            )
        
        # 重置失败计数
        self.failure_counts[source] = 0
    
    def pause_source(self, source: str, hours: int = None):
        """
        暂停数据源
        
        Args:
            source: 数据源名称
            hours: 暂停时长（小时），如果为 None 则使用默认值
        """
        if hours is None:
            hours = self.pause_duration_hours
        
        # 计算暂停截止时间
        pause_until = datetime.now() + timedelta(hours=hours)
        self.paused_until[source] = pause_until
        
        self.logger.warning(
            f"数据源 {source} 已暂停，"
            f"将在 {pause_until.strftime('%Y-%m-%d %H:%M:%S')} 恢复"
        )
    
    def is_paused(self, source: str) -> bool:
        """
        检查数据源是否被暂停
        
        Args:
            source: 数据源名称
        
        Returns:
            True 表示暂停中，False 表示可以采集
        """
        if source not in self.paused_until:
            return False
        
        # 检查是否已过暂停时间
        if datetime.now() < self.paused_until[source]:
            return True
        else:
            # 暂停时间已过，移除暂停状态
            self.logger.info(
                f"数据源 {source} 暂停时间已过，恢复采集"
            )
            del self.paused_until[source]
            # 重置失败计数
            self.failure_counts[source] = 0
            return False
    
    def get_failure_count(self, source: str) -> int:
        """
        获取数据源的失败计数
        
        Args:
            source: 数据源名称
        
        Returns:
            失败计数
        """
        return self.failure_counts.get(source, 0)
    
    def get_pause_info(self, source: str) -> Optional[Dict[str, Any]]:
        """
        获取数据源的暂停信息
        
        Args:
            source: 数据源名称
        
        Returns:
            暂停信息字典，如果未暂停返回 None
            {
                "paused": bool,
                "pause_until": datetime,
                "remaining_seconds": int
            }
        """
        if not self.is_paused(source):
            return None
        
        pause_until = self.paused_until[source]
        remaining = (pause_until - datetime.now()).total_seconds()
        
        return {
            "paused": True,
            "pause_until": pause_until,
            "remaining_seconds": int(remaining)
        }
    
    def reset(self, source: str = None):
        """
        重置失败跟踪
        
        Args:
            source: 数据源名称，如果为 None 则重置所有数据源
        """
        if source is None:
            # 重置所有数据源
            self.failure_counts.clear()
            self.paused_until.clear()
            self.logger.info("已重置所有数据源的失败跟踪")
        else:
            # 重置指定数据源
            if source in self.failure_counts:
                del self.failure_counts[source]
            if source in self.paused_until:
                del self.paused_until[source]
            self.logger.info(f"已重置数据源 {source} 的失败跟踪")
    
    def get_status(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有数据源的状态
        
        Returns:
            状态字典，格式：
            {
                "source_name": {
                    "failure_count": int,
                    "paused": bool,
                    "pause_until": datetime (可选)
                }
            }
        """
        status = {}
        
        # 获取所有已知的数据源
        all_sources = set(self.failure_counts.keys()) | set(self.paused_until.keys())
        
        for source in all_sources:
            source_status = {
                "failure_count": self.failure_counts.get(source, 0),
                "paused": self.is_paused(source)
            }
            
            if source_status["paused"]:
                source_status["pause_until"] = self.paused_until[source]
            
            status[source] = source_status
        
        return status


# 导出类和函数
__all__ = [
    "RetryHandler",
    "FailureTracker",
]
