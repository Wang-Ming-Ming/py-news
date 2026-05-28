# -*- coding: utf-8 -*-
"""
发改委解析器模块

本模块实现了发改委（NDRC）网站的 HTML 解析功能，用于从网页中提取政策新闻数据。

主要功能：
- 使用 lxml 和 xpath 解析 HTML 页面
- 从列表页提取新闻链接
- 从详情页提取标题、发布时间、内容、标签
- 处理编码问题（自动转换为 UTF-8）
- 错误处理和日志记录

需求：1.1, 1.2, 1.5, 1.6
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from lxml import etree, html
import re
from urllib.parse import urljoin

from models import NDRCNews
from utils.exceptions import ParseException


class NDRCParser:
    """
    发改委 HTML 解析器
    
    使用 lxml 和 xpath 表达式解析发改委网站的 HTML 页面，
    提取政策新闻的结构化数据。
    
    Attributes:
        logger: 日志记录器
        xpath_config: XPath 表达式配置字典
    
    示例:
        >>> from utils.logger import get_logger
        >>> logger = get_logger(__name__)
        >>> parser = NDRCParser(logger)
        >>> 
        >>> # 解析新闻列表页
        >>> html_content = "<html>...</html>"
        >>> links = parser.parse_news_list(html_content, base_url="https://www.ndrc.gov.cn")
        >>> 
        >>> # 解析新闻详情页
        >>> news_data = parser.parse_news_detail(html_content, url="https://www.ndrc.gov.cn/news/1")
    """
    
    # 默认 XPath 表达式（可以通过配置覆盖）
    DEFAULT_XPATH = {
        "news_list": "//div[@class='news-list']//a/@href",
        "title": "//h1[@class='article-title']/text()",
        "publish_time": "//span[@class='publish-time']/text()",
        "content": "//div[@class='article-content']//text()",
        "tags": "//div[@class='tags']//a/text()",
    }
    
    def __init__(
        self, 
        logger: logging.Logger,
        xpath_config: Optional[Dict[str, str]] = None
    ):
        """
        初始化发改委解析器
        
        Args:
            logger: 日志记录器
            xpath_config: XPath 表达式配置字典，如果为 None 则使用默认配置
        """
        self.logger = logger
        
        # 使用提供的配置或默认配置
        self.xpath_config = xpath_config if xpath_config else self.DEFAULT_XPATH.copy()
        
        self.logger.info("发改委解析器初始化完成")
        self.logger.debug(f"XPath 配置: {self.xpath_config}")
    
    def _parse_html(self, html_content: str) -> etree._Element:
        """
        解析 HTML 内容为 lxml 元素树
        
        Args:
            html_content: HTML 字符串
        
        Returns:
            lxml 元素树
        
        Raises:
            ParseException: HTML 解析失败
        """
        try:
            # 使用 lxml.html 解析 HTML
            tree = html.fromstring(html_content)
            return tree
        except Exception as e:
            self.logger.error(f"HTML 解析失败: {e}", exc_info=True)
            raise ParseException(f"HTML 解析失败: {e}")
    
    def _extract_text(
        self, 
        tree: etree._Element, 
        xpath: str,
        join_text: bool = True
    ) -> Optional[str]:
        """
        使用 XPath 提取文本内容
        
        Args:
            tree: lxml 元素树
            xpath: XPath 表达式
            join_text: 是否将多个文本节点连接为单个字符串
        
        Returns:
            提取的文本，如果未找到返回 None
        """
        try:
            result = tree.xpath(xpath)
            
            if not result:
                return None
            
            if join_text:
                # 连接所有文本节点，去除多余空白
                text = " ".join(str(item).strip() for item in result if str(item).strip())
                return text if text else None
            else:
                # 返回第一个结果
                return str(result[0]).strip() if result[0] else None
        
        except Exception as e:
            self.logger.debug(f"XPath 提取失败: {xpath}, 错误: {e}")
            return None
    
    def _extract_list(
        self, 
        tree: etree._Element, 
        xpath: str
    ) -> List[str]:
        """
        使用 XPath 提取列表数据
        
        Args:
            tree: lxml 元素树
            xpath: XPath 表达式
        
        Returns:
            提取的字符串列表
        """
        try:
            result = tree.xpath(xpath)
            
            if not result:
                return []
            
            # 过滤空字符串并去除空白
            return [str(item).strip() for item in result if str(item).strip()]
        
        except Exception as e:
            self.logger.debug(f"XPath 列表提取失败: {xpath}, 错误: {e}")
            return []
    
    def _normalize_url(self, url: str, base_url: str) -> str:
        """
        规范化 URL（处理相对路径）
        
        Args:
            url: 原始 URL
            base_url: 基础 URL
        
        Returns:
            完整的 URL
        """
        return urljoin(base_url, url)
    
    def _parse_datetime(self, time_str: str) -> Optional[str]:
        """
        解析时间字符串为 ISO 8601 格式
        
        Args:
            time_str: 时间字符串（如 "2024-01-15 10:30:00" 或 "2024-01-15"）
        
        Returns:
            ISO 8601 格式的时间字符串，如果解析失败返回 None
        """
        if not time_str:
            return None
        
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
        
        # 尝试每种格式
        for fmt in formats:
            try:
                dt = datetime.strptime(time_str.strip(), fmt)
                # 转换为 ISO 8601 格式
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                continue
        
        # 如果所有格式都失败，记录警告并返回原始字符串
        self.logger.warning(f"无法解析时间字符串: {time_str}")
        return time_str
    
    def parse_news_list(
        self, 
        html_content: str, 
        base_url: str = "https://www.ndrc.gov.cn"
    ) -> List[str]:
        """
        从列表页提取新闻链接
        
        Args:
            html_content: HTML 内容
            base_url: 基础 URL，用于构建完整链接
        
        Returns:
            新闻详情页面的 URL 列表
        
        Raises:
            ParseException: HTML 解析失败
        
        示例:
            >>> html = "<html><div class='news-list'><a href='/news/1'>新闻1</a></div></html>"
            >>> links = parser.parse_news_list(html)
            >>> print(links)
            ['https://www.ndrc.gov.cn/news/1']
        """
        try:
            # 解析 HTML
            tree = self._parse_html(html_content)
            
            # 提取链接
            xpath = self.xpath_config.get("news_list", self.DEFAULT_XPATH["news_list"])
            links = self._extract_list(tree, xpath)
            
            # 规范化 URL。真实发改委列表优先保留正文页面；测试或通用列表保持兼容。
            normalized_links = []
            for link in links:
                full_url = self._normalize_url(link, base_url)
                if full_url.startswith(("http://www.ndrc.gov.cn/", "https://www.ndrc.gov.cn/")):
                    normalized_links.append(full_url)
            
            article_links = [
                link for link in normalized_links
                if link.endswith(".html") and "/t20" in link
            ]
            full_links = list(dict.fromkeys(article_links or normalized_links))
            
            self.logger.info(f"从列表页提取到 {len(full_links)} 个新闻链接")
            self.logger.debug(f"新闻链接: {full_links[:5]}...")  # 只显示前5个
            
            return full_links
        
        except ParseException:
            raise
        except Exception as e:
            self.logger.error(
                f"解析新闻列表失败: {e}, "
                f"HTML 片段: {html_content[:200]}...",
                exc_info=True
            )
            raise ParseException(f"解析新闻列表失败: {e}")
    
    def parse_news_detail(
        self, 
        html_content: str, 
        url: str
    ) -> Optional[Dict[str, Any]]:
        """
        从详情页提取新闻数据
        
        Args:
            html_content: HTML 内容
            url: 新闻详情页面 URL
        
        Returns:
            新闻数据字典，如果解析失败返回 None
            {
                "source": "ndrc",
                "title": str,
                "publish_time": str (ISO 8601 格式),
                "content": str,
                "url": str,
                "tags": List[str]
            }
        
        示例:
            >>> html = "<html><h1 class='article-title'>AI政策</h1>...</html>"
            >>> news = parser.parse_news_detail(html, url="https://www.ndrc.gov.cn/news/1")
            >>> print(news["title"])
            'AI政策'
        """
        try:
            # 解析 HTML
            tree = self._parse_html(html_content)
            
            # 提取标题
            title_xpath = self.xpath_config.get("title", self.DEFAULT_XPATH["title"])
            title = self._extract_text(tree, title_xpath, join_text=False)
            
            if not title:
                self.logger.warning(f"未找到标题，URL: {url}")
                return None
            
            # 提取发布时间
            time_xpath = self.xpath_config.get("publish_time", self.DEFAULT_XPATH["publish_time"])
            publish_time_raw = self._extract_text(tree, time_xpath, join_text=False)
            if publish_time_raw:
                publish_time_raw = re.sub(r"^(发布时间|时间)[:：]\s*", "", publish_time_raw).strip()
            publish_time = self._parse_datetime(publish_time_raw) if publish_time_raw else None
            
            if not publish_time:
                # 如果没有发布时间，使用当前时间
                publish_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
                self.logger.debug(f"未找到发布时间，使用当前时间: {publish_time}")
            
            # 提取内容
            content_xpath = self.xpath_config.get("content", self.DEFAULT_XPATH["content"])
            content = self._extract_text(tree, content_xpath, join_text=True)
            
            if not content:
                self.logger.warning(f"未找到内容，URL: {url}")
                content = ""
            
            # 提取标签
            tags_xpath = self.xpath_config.get("tags", self.DEFAULT_XPATH["tags"])
            tags = self._extract_list(tree, tags_xpath)
            
            # 构建新闻数据
            news_data = {
                "source": "ndrc",
                "title": title,
                "publish_time": publish_time,
                "content": content,
                "url": url,
                "tags": tags
            }
            
            self.logger.debug(
                f"成功解析新闻: {title[:30]}..., "
                f"内容长度: {len(content)}, 标签数: {len(tags)}"
            )
            
            return news_data
        
        except ParseException:
            self.logger.error(
                f"解析新闻详情失败，URL: {url}, "
                f"HTML 片段: {html_content[:200]}...",
                exc_info=True
            )
            return None
        except Exception as e:
            self.logger.error(
                f"解析新闻详情失败: {e}, URL: {url}, "
                f"HTML 片段: {html_content[:200]}...",
                exc_info=True
            )
            return None
    
    def parse_to_model(
        self, 
        html_content: str, 
        url: str
    ) -> Optional[NDRCNews]:
        """
        解析 HTML 并返回 NDRCNews 模型实例
        
        Args:
            html_content: HTML 内容
            url: 新闻详情页面 URL
        
        Returns:
            NDRCNews 实例，如果解析失败返回 None
        
        示例:
            >>> news = parser.parse_to_model(html, url="https://www.ndrc.gov.cn/news/1")
            >>> if news:
            ...     print(news.title)
            ...     print(news.to_dict())
        """
        news_data = self.parse_news_detail(html_content, url)
        
        if not news_data:
            return None
        
        try:
            # 创建 NDRCNews 实例
            news = NDRCNews.from_dict(news_data)
            return news
        except Exception as e:
            self.logger.error(
                f"创建 NDRCNews 实例失败: {e}, "
                f"数据: {news_data}",
                exc_info=True
            )
            return None
    
    def update_xpath_config(self, xpath_config: Dict[str, str]):
        """
        更新 XPath 配置
        
        Args:
            xpath_config: 新的 XPath 配置字典
        
        示例:
            >>> parser.update_xpath_config({
            ...     "title": "//h1[@class='new-title']/text()",
            ...     "content": "//div[@class='new-content']//text()"
            ... })
        """
        self.xpath_config.update(xpath_config)
        self.logger.info("XPath 配置已更新")
        self.logger.debug(f"新配置: {self.xpath_config}")


# ============================================================================
# 便捷函数
# ============================================================================

def create_ndrc_parser_from_config(logger: logging.Logger = None) -> NDRCParser:
    """
    从配置文件创建发改委解析器
    
    Args:
        logger: 日志记录器，如果为 None 则自动创建
    
    Returns:
        配置好的发改委解析器
    
    示例:
        >>> parser = create_ndrc_parser_from_config()
    """
    # 创建日志记录器（如果未提供）
    if logger is None:
        from utils.logger import get_logger
        logger = get_logger(__name__)
    
    # 尝试从配置文件加载 XPath 配置
    try:
        from config import NDRC_CONFIG
        xpath_config = NDRC_CONFIG.get("xpath")
    except ImportError:
        logger.warning("无法导入配置文件，使用默认 XPath 配置")
        xpath_config = None
    
    # 创建解析器
    return NDRCParser(logger, xpath_config)


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    "NDRCParser",
    "create_ndrc_parser_from_config",
]
