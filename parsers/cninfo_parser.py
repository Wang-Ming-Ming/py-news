# -*- coding: utf-8 -*-
"""
证券信息网解析器模块

本模块实现了证券信息网（CNInfo）的数据解析功能，用于从 API 响应中提取公司公告数据。

主要功能：
- 解析 JSON 格式的 API 响应
- 提取股票代码、股票名称、标题、发布时间、公告类型、URL、关键词
- 支持解析公告列表和公告详情
- 处理中文编码问题
- 错误处理和日志记录

需求：3.1, 3.2, 3.5, 3.7, 3.8
"""

import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

from models import CNInfoAnnouncement


class CNInfoParser:
    """
    证券信息网数据解析器
    
    用于解析证券信息网的 API 响应（JSON 格式），
    提取公司公告的结构化数据。
    
    支持的功能：
    - 解析公告列表
    - 解析公告详情
    
    Attributes:
        logger: 日志记录器
    
    示例:
        >>> from utils.logger import get_logger
        >>> logger = get_logger(__name__)
        >>> parser = CNInfoParser(logger)
        >>> 
        >>> # 解析公告列表
        >>> json_data = {"announcements": [...]}
        >>> announcements = parser.parse_announcement_list(json_data)
        >>> 
        >>> # 解析单条公告
        >>> announcement_data = parser.parse_announcement(announcement_item)
    """
    
    def __init__(self, logger: logging.Logger):
        """
        初始化证券信息网解析器
        
        Args:
            logger: 日志记录器
        """
        self.logger = logger
        self.logger.info("证券信息网解析器初始化完成")
    
    def _parse_datetime(self, timestamp: Any) -> Optional[str]:
        """
        解析时间戳为 ISO 8601 格式
        
        Args:
            timestamp: 时间戳（可能是秒级或毫秒级的整数，或字符串）
        
        Returns:
            ISO 8601 格式的时间字符串，如果解析失败返回 None
        """
        if not timestamp:
            return None
        
        try:
            # 如果是字符串，尝试多种格式解析
            if isinstance(timestamp, str):
                # 常见的时间格式
                formats = [
                    "%Y-%m-%d %H:%M:%S",
                    "%Y-%m-%d %H:%M",
                    "%Y-%m-%d",
                    "%Y/%m/%d %H:%M:%S",
                    "%Y/%m/%d %H:%M",
                    "%Y/%m/%d",
                    "%Y年%m月%d日 %H:%M:%S",
                    "%Y年%m月%d日 %H:%M",
                    "%Y年%m月%d日",
                ]
                
                for fmt in formats:
                    try:
                        dt = datetime.strptime(timestamp.strip(), fmt)
                        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                    except ValueError:
                        continue
                
                # 如果是 ISO 格式字符串，直接返回
                if "T" in timestamp:
                    return timestamp
                
                # 尝试解析为时间戳
                try:
                    timestamp = int(timestamp)
                except ValueError:
                    self.logger.warning(f"无法解析时间字符串: {timestamp}")
                    return timestamp
            
            # 如果是数字，判断是秒级还是毫秒级时间戳
            if isinstance(timestamp, (int, float)):
                # 如果大于 10 位数，认为是毫秒级时间戳
                if timestamp > 10000000000:
                    timestamp = timestamp / 1000
                
                # 使用 UTC 时间
                from datetime import timezone
                dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            
        except Exception as e:
            self.logger.warning(f"时间解析失败: {timestamp}, 错误: {e}")
        
        # 如果所有尝试都失败，返回原始值的字符串形式
        return str(timestamp) if timestamp else None
    
    def _extract_field(
        self, 
        data: Dict[str, Any], 
        field_path: str,
        default: Any = None
    ) -> Any:
        """
        从嵌套字典中提取字段值
        
        Args:
            data: 数据字典
            field_path: 字段路径，使用点号分隔（如 "data.items.0.title"）
            default: 默认值
        
        Returns:
            字段值，如果不存在返回默认值
        """
        try:
            keys = field_path.split(".")
            value = data
            
            for key in keys:
                # 处理数组索引
                if key.isdigit():
                    value = value[int(key)]
                else:
                    value = value[key]
            
            return value if value is not None else default
        
        except (KeyError, IndexError, TypeError):
            return default
    
    def parse_announcement(
        self, 
        announcement_item: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        解析单条公告数据
        
        Args:
            announcement_item: 公告数据字典（从 API 响应中提取）
        
        Returns:
            公告数据字典，如果解析失败返回 None
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
        
        示例:
            >>> announcement_item = {
            ...     "secCode": "000001",
            ...     "secName": "平安银行",
            ...     "announcementTitle": "2023年年度报告",
            ...     "announcementTime": 1705305000,
            ...     "announcementType": "年度报告",
            ...     "adjunctUrl": "http://www.cninfo.com.cn/finalpage/2024-01-15/1234567890.PDF"
            ... }
            >>> announcement = parser.parse_announcement(announcement_item)
        """
        try:
            # 提取股票代码（必需字段）
            stock_code = (
                announcement_item.get("secCode") or 
                announcement_item.get("stockCode") or
                announcement_item.get("code") or
                announcement_item.get("stock_code") or
                ""
            )
            
            if not stock_code:
                self.logger.warning(f"公告缺少股票代码，跳过: {announcement_item}")
                return None
            
            # 提取股票名称（必需字段）
            stock_name = (
                announcement_item.get("secName") or 
                announcement_item.get("stockName") or
                announcement_item.get("name") or
                announcement_item.get("stock_name") or
                ""
            )
            
            if not stock_name:
                self.logger.warning(f"公告缺少股票名称，跳过: {announcement_item}")
                return None
            
            # 提取标题（必需字段）
            title = (
                announcement_item.get("announcementTitle") or 
                announcement_item.get("title") or
                announcement_item.get("announcementName") or
                ""
            )
            
            if not title:
                self.logger.warning(f"公告缺少标题，跳过: {announcement_item}")
                return None
            
            # 提取发布时间
            publish_time_raw = (
                announcement_item.get("announcementTime") or 
                announcement_item.get("publishTime") or
                announcement_item.get("publish_time") or
                announcement_item.get("pubDate") or
                announcement_item.get("announcementDate")
            )
            
            publish_time = self._parse_datetime(publish_time_raw)
            
            if not publish_time:
                # 如果没有发布时间，使用当前时间
                publish_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
                self.logger.debug(f"未找到发布时间，使用当前时间: {publish_time}")
            
            # 提取公告类型
            announcement_type = (
                announcement_item.get("announcementType") or 
                announcement_item.get("type") or
                announcement_item.get("category") or
                ""
            )
            
            # 提取 URL
            url = (
                announcement_item.get("adjunctUrl") or 
                announcement_item.get("url") or
                announcement_item.get("pdfUrl") or
                announcement_item.get("announcementUrl") or
                ""
            )
            
            # 如果 URL 是相对路径，补全为完整 URL
            if url and not url.startswith("http"):
                base_url = "http://www.cninfo.com.cn"
                if url.startswith("/"):
                    url = base_url + url
                else:
                    url = base_url + "/" + url
            
            # 提取关键词
            keywords = []
            keywords_raw = (
                announcement_item.get("keywords") or 
                announcement_item.get("keyword") or
                announcement_item.get("tags") or
                []
            )
            
            if isinstance(keywords_raw, list):
                keywords = [str(kw).strip() for kw in keywords_raw if kw]
            elif isinstance(keywords_raw, str):
                # 如果是字符串，尝试按逗号或分号分割
                keywords = [kw.strip() for kw in keywords_raw.replace(";", ",").split(",") if kw.strip()]
            
            # 构建公告数据
            announcement_data = {
                "source": "cninfo",
                "stock_code": str(stock_code).strip(),
                "stock_name": str(stock_name).strip(),
                "title": str(title).strip(),
                "publish_time": publish_time,
                "announcement_type": str(announcement_type).strip() if announcement_type else "",
                "url": str(url).strip() if url else "",
                "keywords": keywords
            }
            
            self.logger.debug(
                f"成功解析公告: {stock_code} - {title[:30]}..., "
                f"类型: {announcement_type}, 关键词数: {len(keywords)}"
            )
            
            return announcement_data
        
        except Exception as e:
            self.logger.error(
                f"解析公告失败: {e}, "
                f"数据: {announcement_item}",
                exc_info=True
            )
            return None
    
    def parse_announcement_list(
        self, 
        response_data: Any
    ) -> List[Dict[str, Any]]:
        """
        解析公告列表（从 API 响应中提取）
        
        Args:
            response_data: API 响应数据（可能是字典、列表或 JSON 字符串）
        
        Returns:
            公告数据列表
        
        示例:
            >>> # 响应格式 1: {"announcements": [...]}
            >>> response = {"announcements": [{"secCode": "000001", ...}]}
            >>> announcements = parser.parse_announcement_list(response)
            >>> 
            >>> # 响应格式 2: {"data": [...]}
            >>> response = {"data": [{"secCode": "000001", ...}]}
            >>> announcements = parser.parse_announcement_list(response)
            >>> 
            >>> # 响应格式 3: [...]
            >>> response = [{"secCode": "000001", ...}]
            >>> announcements = parser.parse_announcement_list(response)
        """
        try:
            # 如果是字符串，尝试解析为 JSON
            if isinstance(response_data, str):
                try:
                    response_data = json.loads(response_data)
                except json.JSONDecodeError as e:
                    self.logger.error(f"JSON 解析失败: {e}")
                    return []
            
            # 提取公告列表
            announcement_items = []
            
            if isinstance(response_data, dict):
                # 尝试多种可能的数据结构
                announcement_items = (
                    self._extract_field(response_data, "announcements", []) or
                    self._extract_field(response_data, "data.announcements", []) or
                    self._extract_field(response_data, "data.records", []) or
                    self._extract_field(response_data, "data", []) or
                    self._extract_field(response_data, "records", []) or
                    self._extract_field(response_data, "list", []) or
                    []
                )
                
                # 如果 data 字段本身就是列表
                if not announcement_items and "data" in response_data:
                    data = response_data["data"]
                    if isinstance(data, list):
                        announcement_items = data
            
            elif isinstance(response_data, list):
                # 如果响应本身就是列表
                announcement_items = response_data
            
            else:
                self.logger.warning(f"不支持的响应数据类型: {type(response_data)}")
                return []
            
            # 解析每条公告
            parsed_announcements = []
            for item in announcement_items:
                if not isinstance(item, dict):
                    continue
                
                announcement = self.parse_announcement(item)
                if announcement:
                    parsed_announcements.append(announcement)
            
            self.logger.info(
                f"成功解析 {len(parsed_announcements)} 条公告 "
                f"(原始数据 {len(announcement_items)} 条)"
            )
            
            return parsed_announcements
        
        except Exception as e:
            self.logger.error(
                f"解析公告列表失败: {e}, "
                f"响应数据类型: {type(response_data)}",
                exc_info=True
            )
            return []
    
    def parse_to_model(
        self, 
        announcement_item: Dict[str, Any]
    ) -> Optional[CNInfoAnnouncement]:
        """
        解析数据并返回 CNInfoAnnouncement 模型实例
        
        Args:
            announcement_item: 公告数据字典
        
        Returns:
            CNInfoAnnouncement 实例，如果解析失败返回 None
        
        示例:
            >>> announcement = parser.parse_to_model(announcement_item)
            >>> if announcement:
            ...     print(announcement.title)
            ...     print(announcement.to_dict())
        """
        announcement_data = self.parse_announcement(announcement_item)
        
        if not announcement_data:
            return None
        
        try:
            # 创建 CNInfoAnnouncement 实例
            announcement = CNInfoAnnouncement.from_dict(announcement_data)
            return announcement
        except Exception as e:
            self.logger.error(
                f"创建 CNInfoAnnouncement 实例失败: {e}, "
                f"数据: {announcement_data}",
                exc_info=True
            )
            return None
    
    def parse_to_models(
        self, 
        response_data: Any
    ) -> List[CNInfoAnnouncement]:
        """
        解析公告列表并返回 CNInfoAnnouncement 模型实例列表
        
        Args:
            response_data: API 响应数据
        
        Returns:
            CNInfoAnnouncement 实例列表
        
        示例:
            >>> announcements = parser.parse_to_models(response_data)
            >>> for announcement in announcements:
            ...     print(announcement.title)
        """
        announcement_data_list = self.parse_announcement_list(response_data)
        
        models = []
        for announcement_data in announcement_data_list:
            try:
                announcement = CNInfoAnnouncement.from_dict(announcement_data)
                models.append(announcement)
            except Exception as e:
                self.logger.error(
                    f"创建 CNInfoAnnouncement 实例失败: {e}, "
                    f"数据: {announcement_data}",
                    exc_info=True
                )
                continue
        
        return models


# ============================================================================
# 便捷函数
# ============================================================================

def create_cninfo_parser_from_config(logger: logging.Logger = None) -> CNInfoParser:
    """
    从配置文件创建证券信息网解析器
    
    Args:
        logger: 日志记录器，如果为 None 则自动创建
    
    Returns:
        配置好的证券信息网解析器
    
    示例:
        >>> parser = create_cninfo_parser_from_config()
    """
    # 创建日志记录器（如果未提供）
    if logger is None:
        from utils.logger import get_logger
        logger = get_logger(__name__)
    
    # 创建解析器
    return CNInfoParser(logger)


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    "CNInfoParser",
    "create_cninfo_parser_from_config",
]
