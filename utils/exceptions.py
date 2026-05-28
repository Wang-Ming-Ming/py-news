# -*- coding: utf-8 -*-
"""
自定义异常类模块

本模块定义了金融数据采集系统使用的所有自定义异常类。
这些异常类用于更精确地表示和处理不同类型的错误。
"""


class DataCollectorException(Exception):
    """
    数据采集器基础异常类
    
    所有自定义异常都应继承此类
    """
    pass


class ParseException(DataCollectorException):
    """
    解析异常
    
    当解析 HTML、JSON 或 PDF 内容失败时抛出此异常。
    
    Attributes:
        message: 错误消息
        source_url: 数据源 URL（可选）
        raw_content: 原始内容片段（可选，用于调试）
    """
    
    def __init__(
        self, 
        message: str, 
        source_url: str = None, 
        raw_content: str = None
    ):
        """
        初始化解析异常
        
        Args:
            message: 错误消息
            source_url: 数据源 URL
            raw_content: 原始内容片段（截断到 500 字符）
        """
        self.message = message
        self.source_url = source_url
        # 截断原始内容以避免日志过大
        self.raw_content = raw_content[:500] if raw_content else None
        
        # 构建完整的错误消息
        full_message = f"解析失败: {message}"
        if source_url:
            full_message += f" | URL: {source_url}"
        if self.raw_content:
            full_message += f" | 内容片段: {self.raw_content}..."
        
        super().__init__(full_message)
    
    def __str__(self):
        return self.args[0] if self.args else self.message


class DiskFullException(DataCollectorException):
    """
    磁盘空间不足异常
    
    当可用磁盘空间低于配置的最小值时抛出此异常。
    这是一个严重错误，应该停止数据采集。
    
    Attributes:
        message: 错误消息
        available_space: 当前可用空间（字节）
        required_space: 所需最小空间（字节）
    """
    
    def __init__(
        self, 
        message: str, 
        available_space: int = None, 
        required_space: int = None
    ):
        """
        初始化磁盘空间不足异常
        
        Args:
            message: 错误消息
            available_space: 当前可用空间（字节）
            required_space: 所需最小空间（字节）
        """
        self.message = message
        self.available_space = available_space
        self.required_space = required_space
        
        # 构建完整的错误消息
        full_message = f"磁盘空间不足: {message}"
        if available_space is not None and required_space is not None:
            available_mb = available_space / (1024 * 1024)
            required_mb = required_space / (1024 * 1024)
            full_message += (
                f" | 可用空间: {available_mb:.2f} MB, "
                f"所需空间: {required_mb:.2f} MB"
            )
        
        super().__init__(full_message)
    
    def __str__(self):
        return self.args[0] if self.args else self.message


class APIException(DataCollectorException):
    """
    API 调用异常
    
    当调用外部 API 失败时抛出此异常。
    
    Attributes:
        message: 错误消息
        api_url: API URL
        status_code: HTTP 状态码（可选）
        response_body: 响应体内容（可选）
        retry_after: 速率限制时需要等待的秒数（可选）
    """
    
    def __init__(
        self, 
        message: str, 
        api_url: str = None, 
        status_code: int = None,
        response_body: str = None,
        retry_after: int = None
    ):
        """
        初始化 API 异常
        
        Args:
            message: 错误消息
            api_url: API URL
            status_code: HTTP 状态码
            response_body: 响应体内容（截断到 500 字符）
            retry_after: 速率限制时需要等待的秒数
        """
        self.message = message
        self.api_url = api_url
        self.status_code = status_code
        self.retry_after = retry_after
        # 截断响应体以避免日志过大
        self.response_body = response_body[:500] if response_body else None
        
        # 构建完整的错误消息
        full_message = f"API 调用失败: {message}"
        if api_url:
            full_message += f" | URL: {api_url}"
        if status_code:
            full_message += f" | 状态码: {status_code}"
        if retry_after:
            full_message += f" | 需要等待: {retry_after} 秒"
        if self.response_body:
            full_message += f" | 响应: {self.response_body}..."
        
        super().__init__(full_message)
    
    def __str__(self):
        return self.args[0] if self.args else self.message


class NetworkException(DataCollectorException):
    """
    网络异常
    
    当网络请求失败时抛出此异常（连接超时、DNS 解析失败等）。
    
    Attributes:
        message: 错误消息
        url: 请求 URL
        original_exception: 原始异常对象
    """
    
    def __init__(
        self, 
        message: str, 
        url: str = None, 
        original_exception: Exception = None
    ):
        """
        初始化网络异常
        
        Args:
            message: 错误消息
            url: 请求 URL
            original_exception: 原始异常对象
        """
        self.message = message
        self.url = url
        self.original_exception = original_exception
        
        # 构建完整的错误消息
        full_message = f"网络请求失败: {message}"
        if url:
            full_message += f" | URL: {url}"
        if original_exception:
            full_message += f" | 原因: {str(original_exception)}"
        
        super().__init__(full_message)
    
    def __str__(self):
        return self.args[0] if self.args else self.message


class ConfigException(DataCollectorException):
    """
    配置异常
    
    当配置无效或缺失时抛出此异常。
    
    Attributes:
        message: 错误消息
        config_key: 配置键名
    """
    
    def __init__(self, message: str, config_key: str = None):
        """
        初始化配置异常
        
        Args:
            message: 错误消息
            config_key: 配置键名
        """
        self.message = message
        self.config_key = config_key
        
        # 构建完整的错误消息
        full_message = f"配置错误: {message}"
        if config_key:
            full_message += f" | 配置项: {config_key}"
        
        super().__init__(full_message)
    
    def __str__(self):
        return self.args[0] if self.args else self.message


# 导出所有异常类
__all__ = [
    "DataCollectorException",
    "ParseException",
    "DiskFullException",
    "APIException",
    "NetworkException",
    "ConfigException",
]
