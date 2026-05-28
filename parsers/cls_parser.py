# -*- coding: utf-8 -*-
"""
证券报解析器模块

本模块实现了证券报（CLS）网站的数据解析功能，用于从 API 响应或 HTML 页面中提取热点新闻数据。

主要功能：
- 解析 JSON 格式的 API 响应
- 提取标题、发布时间、内容、标签、板块、级别
- 处理不同新闻类别的数据结构差异
- 错误处理和日志记录

需求：2.1, 2.2, 2.4
"""

import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from lxml import etree, html

from models import CLSNews
from utils.exceptions import ParseException


class CLSParser:
    """
    证券报数据解析器
    
    用于解析证券报网站的 API 响应（JSON 格式）或 HTML 页面，
    提取热点新闻的结构化数据。
    
    支持的新闻类别：
    - telegraph: 电报
    - ai_news: AI新闻
    - plate_movement: 板块异动
    - limit_up_logic: 涨停逻辑
    - hot_topics: 热点题材
    - industry_chain: 产业链新闻
    
    Attributes:
        logger: 日志记录器
    
    示例:
        >>> from utils.logger import get_logger
        >>> logger = get_logger(__name__)
        >>> parser = CLSParser(logger)
        >>> 
        >>> # 解析 JSON 响应
        >>> json_data = {"data": {"items": [...]}}
        >>> news_list = parser.parse_news_list(json_data)
        >>> 
        >>> # 解析单条新闻
        >>> news_data = parser.parse_news(news_item)
    """
    
    def __init__(self, logger: logging.Logger):
        """
        初始化证券报解析器
        
        Args:
            logger: 日志记录器
        """
        self.logger = logger
        self.logger.info("证券报解析器初始化完成")
    
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
    
    def parse_news(
        self, 
        news_item: Dict[str, Any],
        category: str = ""
    ) -> Optional[Dict[str, Any]]:
        """
        解析单条新闻数据
        
        Args:
            news_item: 新闻数据字典（从 API 响应中提取）
            category: 新闻类别（可选）
        
        Returns:
            新闻数据字典，如果解析失败返回 None
            {
                "source": "cls",
                "title": str,
                "publish_time": str (ISO 8601 格式),
                "content": str,
                "tags": List[str],
                "plate": List[str],
                "level": str
            }
        
        示例:
            >>> news_item = {
            ...     "title": "AI芯片板块异动",
            ...     "content": "今日AI芯片板块大涨...",
            ...     "ctime": 1705305000,
            ...     "plate": ["AI", "半导体"],
            ...     "level": "重要"
            ... }
            >>> news = parser.parse_news(news_item)
        """
        try:
            # 提取标题（必需字段）
            title = news_item.get("title") or news_item.get("brief") or news_item.get("content", "")[:50]
            
            if not title:
                self.logger.warning(f"新闻缺少标题，跳过: {news_item}")
                return None
            
            # 提取发布时间
            # 尝试多个可能的时间字段
            publish_time_raw = (
                news_item.get("ctime") or 
                news_item.get("publish_time") or 
                news_item.get("time") or
                news_item.get("createTime") or
                news_item.get("pubDate")
            )
            
            publish_time = self._parse_datetime(publish_time_raw)
            
            if not publish_time:
                # 如果没有发布时间，使用当前时间
                publish_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
                self.logger.debug(f"未找到发布时间，使用当前时间: {publish_time}")
            
            # 提取内容
            # 优先使用 content 或 description，brief 作为最后的备选
            content = (
                news_item.get("content") or 
                news_item.get("description") or
                news_item.get("summary") or
                news_item.get("brief") or 
                ""
            )
            
            # 提取标签
            tags = []
            tags_raw = news_item.get("tags") or news_item.get("keywords") or []
            
            if isinstance(tags_raw, list):
                tags = [str(tag).strip() for tag in tags_raw if tag]
            elif isinstance(tags_raw, str):
                # 如果是字符串，尝试按逗号分割
                tags = [tag.strip() for tag in tags_raw.split(",") if tag.strip()]
            
            # 添加类别作为标签
            if category:
                tags.append(category)
            
            # 提取板块
            plate = []
            plate_raw = news_item.get("plate") or news_item.get("plates") or news_item.get("sector") or []
            
            if isinstance(plate_raw, list):
                plate = [str(p).strip() for p in plate_raw if p]
            elif isinstance(plate_raw, str):
                # 如果是字符串，尝试按逗号分割
                plate = [p.strip() for p in plate_raw.split(",") if p.strip()]
            
            # 提取级别
            level = news_item.get("level") or news_item.get("importance") or ""
            
            # 构建新闻数据
            news_data = {
                "source": "cls",
                "title": title,
                "publish_time": publish_time,
                "content": content,
                "url": str(news_item.get("url") or news_item.get("shareurl") or news_item.get("share_url") or ""),
                "tags": tags,
                "plate": plate,
                "level": str(level) if level else ""
            }
            
            self.logger.debug(
                f"成功解析新闻: {title[:30]}..., "
                f"内容长度: {len(content)}, 标签数: {len(tags)}, 板块数: {len(plate)}"
            )
            
            return news_data
        
        except Exception as e:
            self.logger.error(
                f"解析新闻失败: {e}, "
                f"数据: {news_item}",
                exc_info=True
            )
            return None
    
    def parse_news_list(
        self, 
        response_data: Any,
        category: str = ""
    ) -> List[Dict[str, Any]]:
        """
        解析新闻列表（从 API 响应中提取）
        
        Args:
            response_data: API 响应数据（可能是字典、列表或 JSON 字符串）
            category: 新闻类别（可选）
        
        Returns:
            新闻数据列表
        
        示例:
            >>> # 响应格式 1: {"data": {"items": [...]}}
            >>> response = {"data": {"items": [{"title": "新闻1"}, {"title": "新闻2"}]}}
            >>> news_list = parser.parse_news_list(response)
            >>> 
            >>> # 响应格式 2: {"data": [...]}
            >>> response = {"data": [{"title": "新闻1"}, {"title": "新闻2"}]}
            >>> news_list = parser.parse_news_list(response)
            >>> 
            >>> # 响应格式 3: [...]
            >>> response = [{"title": "新闻1"}, {"title": "新闻2"}]
            >>> news_list = parser.parse_news_list(response)
        """
        try:
            # 如果是字符串，尝试解析为 JSON
            if isinstance(response_data, str):
                try:
                    response_data = json.loads(response_data)
                except json.JSONDecodeError as e:
                    self.logger.error(f"JSON 解析失败: {e}")
                    return []
            
            # 提取新闻列表
            news_items = []
            
            if isinstance(response_data, dict):
                # 尝试多种可能的数据结构
                news_items = (
                    self._extract_field(response_data, "data.items", []) or
                    self._extract_field(response_data, "data.list", []) or
                    self._extract_field(response_data, "data.roll_data", []) or
                    self._extract_field(response_data, "data", []) or
                    self._extract_field(response_data, "items", []) or
                    self._extract_field(response_data, "list", []) or
                    []
                )
                
                # 如果 data 字段本身就是列表
                if not news_items and "data" in response_data:
                    data = response_data["data"]
                    if isinstance(data, list):
                        news_items = data
            
            elif isinstance(response_data, list):
                # 如果响应本身就是列表
                news_items = response_data
            
            else:
                self.logger.warning(f"不支持的响应数据类型: {type(response_data)}")
                return []
            
            # 解析每条新闻
            parsed_news = []
            for item in news_items:
                if not isinstance(item, dict):
                    continue
                
                news = self.parse_news(item, category=category)
                if news:
                    parsed_news.append(news)
            
            self.logger.info(
                f"成功解析 {len(parsed_news)} 条新闻 "
                f"(原始数据 {len(news_items)} 条)"
            )
            
            return parsed_news
        
        except Exception as e:
            self.logger.error(
                f"解析新闻列表失败: {e}, "
                f"响应数据类型: {type(response_data)}",
                exc_info=True
            )
            return []
    
    def parse_html(
        self, 
        html_content: str,
        category: str = ""
    ) -> List[Dict[str, Any]]:
        """
        解析 HTML 页面（备用方案，当 API 不可用时使用）
        
        Args:
            html_content: HTML 内容
            category: 新闻类别（可选）
        
        Returns:
            新闻数据列表
        
        注意：此方法需要根据实际的 HTML 结构调整 XPath 表达式
        """
        try:
            # 解析 HTML
            tree = html.fromstring(html_content)
            
            # 提取新闻列表（需要根据实际 HTML 结构调整）
            # 这里提供一个通用的示例
            news_items = tree.xpath("//div[@class='news-item']")
            
            parsed_news = []
            
            for item in news_items:
                try:
                    # 提取标题
                    title_list = item.xpath(".//h3/text() | .//h2/text() | .//a[@class='title']/text()")
                    title = title_list[0].strip() if title_list else None
                    
                    if not title:
                        continue
                    
                    # 提取时间
                    time_list = item.xpath(".//span[@class='time']/text() | .//time/text()")
                    time_str = time_list[0].strip() if time_list else None
                    publish_time = self._parse_datetime(time_str) if time_str else datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
                    
                    # 提取内容
                    content_list = item.xpath(".//p[@class='content']/text() | .//div[@class='brief']/text()")
                    content = " ".join(c.strip() for c in content_list if c.strip())
                    
                    # 提取标签
                    tags_list = item.xpath(".//span[@class='tag']/text()")
                    tags = [tag.strip() for tag in tags_list if tag.strip()]
                    
                    if category:
                        tags.append(category)
                    
                    # 构建新闻数据
                    news_data = {
                        "source": "cls",
                        "title": title,
                        "publish_time": publish_time,
                        "content": content,
                        "tags": tags,
                        "plate": [],
                        "level": ""
                    }
                    
                    parsed_news.append(news_data)
                
                except Exception as e:
                    self.logger.debug(f"解析单条新闻失败: {e}")
                    continue
            
            self.logger.info(f"从 HTML 解析到 {len(parsed_news)} 条新闻")
            
            return parsed_news
        
        except Exception as e:
            self.logger.error(
                f"HTML 解析失败: {e}, "
                f"HTML 片段: {html_content[:200]}...",
                exc_info=True
            )
            return []
    
    def parse_to_model(
        self, 
        news_item: Dict[str, Any],
        category: str = ""
    ) -> Optional[CLSNews]:
        """
        解析数据并返回 CLSNews 模型实例
        
        Args:
            news_item: 新闻数据字典
            category: 新闻类别（可选）
        
        Returns:
            CLSNews 实例，如果解析失败返回 None
        
        示例:
            >>> news = parser.parse_to_model(news_item)
            >>> if news:
            ...     print(news.title)
            ...     print(news.to_dict())
        """
        news_data = self.parse_news(news_item, category=category)
        
        if not news_data:
            return None
        
        try:
            # 创建 CLSNews 实例
            news = CLSNews.from_dict(news_data)
            return news
        except Exception as e:
            self.logger.error(
                f"创建 CLSNews 实例失败: {e}, "
                f"数据: {news_data}",
                exc_info=True
            )
            return None
    
    def parse_to_models(
        self, 
        response_data: Any,
        category: str = ""
    ) -> List[CLSNews]:
        """
        解析新闻列表并返回 CLSNews 模型实例列表
        
        Args:
            response_data: API 响应数据
            category: 新闻类别（可选）
        
        Returns:
            CLSNews 实例列表
        
        示例:
            >>> news_list = parser.parse_to_models(response_data, category="telegraph")
            >>> for news in news_list:
            ...     print(news.title)
        """
        news_data_list = self.parse_news_list(response_data, category=category)
        
        models = []
        for news_data in news_data_list:
            try:
                news = CLSNews.from_dict(news_data)
                models.append(news)
            except Exception as e:
                self.logger.error(
                    f"创建 CLSNews 实例失败: {e}, "
                    f"数据: {news_data}",
                    exc_info=True
                )
                continue
        
        return models


# ============================================================================
# 便捷函数
# ============================================================================

def create_cls_parser_from_config(logger: logging.Logger = None) -> CLSParser:
    """
    从配置文件创建证券报解析器
    
    Args:
        logger: 日志记录器，如果为 None 则自动创建
    
    Returns:
        配置好的证券报解析器
    
    示例:
        >>> parser = create_cls_parser_from_config()
    """
    # 创建日志记录器（如果未提供）
    if logger is None:
        from utils.logger import get_logger
        logger = get_logger(__name__)
    
    # 创建解析器
    return CLSParser(logger)


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    "CLSParser",
    "create_cls_parser_from_config",
]
