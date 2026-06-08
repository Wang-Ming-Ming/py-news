# -*- coding: utf-8 -*-
"""
发改委爬虫模块

本模块实现了发改委（NDRC）网站的数据采集功能，用于从网站采集政策新闻数据。

主要功能：
- 使用 requests 库发送 HTTP 请求
- 获取指定日期范围的新闻列表
- 获取单篇新闻的详细信息
- 集成关键词过滤器，过滤包含股票关键词的新闻
- 集成解析器，解析 HTML 内容
- 使用重试机制处理网络请求失败
- 设置 30 秒超时和浏览器 User-Agent

需求：1.1, 1.2, 1.3, 1.4, 1.6, 10.1, 10.5
"""

import logging
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from parsers.ndrc_parser import NDRCParser
from filters.keyword_filter import KeywordFilter
from storage.deduplicator import Deduplicator
from storage.storage_manager import StorageManager
from utils.retry import RetryHandler
from utils.exceptions import NetworkException, ParseException


class NDRCSpider:
    """
    发改委政策新闻爬虫
    
    从国家发展和改革委员会网站采集政策新闻，支持关键词过滤和去重。
    
    Attributes:
        config: 配置字典
        logger: 日志记录器
        parser: NDRC 解析器
        keyword_filter: 关键词过滤器
        deduplicator: 去重器
        storage_manager: 存储管理器
        retry_handler: 重试处理器
    
    示例:
        >>> from utils.logger import get_logger
        >>> from config import NDRC_CONFIG, STOCK_KEYWORDS
        >>> 
        >>> logger = get_logger(__name__)
        >>> parser = NDRCParser(logger)
        >>> keyword_filter = KeywordFilter(STOCK_KEYWORDS, logger)
        >>> deduplicator = Deduplicator("data/.dedup_index.json", logger)
        >>> storage_manager = StorageManager("data", logger)
        >>> 
        >>> spider = NDRCSpider(
        ...     config=NDRC_CONFIG,
        ...     logger=logger,
        ...     parser=parser,
        ...     keyword_filter=keyword_filter,
        ...     deduplicator=deduplicator,
        ...     storage_manager=storage_manager
        ... )
        >>> 
        >>> # 采集过去 7 天的新闻
        >>> start_date = datetime.now() - timedelta(days=7)
        >>> end_date = datetime.now()
        >>> news_list = spider.run(start_date, end_date)
    """
    
    def __init__(
        self,
        config: Dict[str, Any],
        logger: logging.Logger,
        parser: NDRCParser,
        keyword_filter: KeywordFilter,
        deduplicator: Deduplicator,
        storage_manager: StorageManager
    ):
        """
        初始化发改委爬虫
        
        Args:
            config: 配置字典，包含 URL、超时、重试等参数
            logger: 日志记录器
            parser: NDRC 解析器
            keyword_filter: 关键词过滤器
            deduplicator: 去重器
            storage_manager: 存储管理器
        """
        self.config = config
        self.logger = logger
        self.parser = parser
        self.keyword_filter = keyword_filter
        self.deduplicator = deduplicator
        self.storage_manager = storage_manager
        
        # 初始化重试处理器
        retry_times = config.get("retry_times", 3)
        retry_delays = config.get("retry_delays", [1, 2, 4])
        self.retry_handler = RetryHandler(
            max_retries=retry_times,
            delays=retry_delays,
            logger=logger
        )
        
        # 请求配置
        self.timeout = config.get("timeout", 30)
        self.user_agent = config.get(
            "user_agent",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.base_url = config.get("base_url", "https://www.ndrc.gov.cn")
        
        # 统计信息
        self.stats = {
            "total_fetched": 0,
            "filtered_count": 0,
            "duplicate_count": 0,
            "saved_count": 0,
            "error_count": 0,
        }
        
        self.logger.info(
            f"发改委爬虫初始化完成: base_url={self.base_url}, "
            f"timeout={self.timeout}s, retry_times={retry_times}"
        )
    
    def _make_request(self, url: str) -> requests.Response:
        """
        发送 HTTP 请求
        
        Args:
            url: 请求 URL
        
        Returns:
            响应对象
        
        Raises:
            NetworkException: 网络请求失败
        """
        try:
            headers = {
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
            }
            
            self.logger.debug(f"发送请求: {url}")
            
            response = requests.get(
                url,
                headers=headers,
                timeout=self.timeout,
                allow_redirects=True
            )
            response.encoding = response.apparent_encoding or self.config.get("encoding", "utf-8")
            
            # 检查响应状态
            response.raise_for_status()
            
            self.logger.debug(
                f"请求成功: {url}, "
                f"状态码={response.status_code}, "
                f"内容长度={len(response.content)}"
            )
            
            return response
            
        except requests.Timeout as e:
            self.logger.error(f"请求超时: {url}, 错误: {e}")
            raise NetworkException(f"请求超时: {url}")
        
        except requests.ConnectionError as e:
            self.logger.error(f"连接失败: {url}, 错误: {e}")
            raise NetworkException(f"连接失败: {url}")
        
        except requests.HTTPError as e:
            self.logger.error(
                f"HTTP 错误: {url}, "
                f"状态码={e.response.status_code}, "
                f"错误: {e}"
            )
            raise NetworkException(f"HTTP 错误: {url}, 状态码={e.response.status_code}")
        
        except Exception as e:
            self.logger.error(f"请求失败: {url}, 错误: {e}", exc_info=True)
            raise NetworkException(f"请求失败: {url}, 错误: {e}")
    
    def fetch_news_list(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[str]:
        """
        获取新闻列表页面的所有新闻链接
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
        
        Returns:
            新闻详情页面的 URL 列表
        
        Raises:
            NetworkException: 网络请求失败
            ParseException: HTML 解析失败
        """
        self.logger.info(
            f"开始获取新闻列表: "
            f"start_date={start_date.strftime('%Y-%m-%d')}, "
            f"end_date={end_date.strftime('%Y-%m-%d')}"
        )
        
        all_links = []
        
        try:
            list_urls = self.config.get("list_urls") or [
                f"{self.base_url}/xwdt/",
                f"{self.base_url}/xwdt/xwfb/",
                f"{self.base_url}/xwdt/tzgg/",
                f"{self.base_url}/xwdt/dt/sjdt/",
                f"{self.base_url}/xwdt/dt/dfdt/",
            ]
            
            list_page_error_count = 0

            for list_url in list_urls:
                try:
                    # 使用重试机制发送请求
                    response = self.retry_handler.execute_with_retry(
                        self._make_request,
                        list_url
                    )
                    
                    # 解析 HTML 获取新闻链接
                    html_content = response.text
                    links = self.parser.parse_news_list(html_content, list_url)
                    
                    if not links:
                        self.logger.info(f"列表页没有找到新闻链接: {list_url}")
                        continue
                    
                    all_links.extend(links)
                    self.logger.debug(f"列表页获取到 {len(links)} 个链接: {list_url}")
                    
                except NetworkException as e:
                    self.logger.warning(f"获取列表页失败: {list_url}, 错误: {e}")
                    list_page_error_count += 1
                    continue
                
                except ParseException as e:
                    self.logger.warning(f"解析列表页失败: {list_url}, 错误: {e}")
                    list_page_error_count += 1
                    continue
            
            # 去重
            all_links = list(set(all_links))
            
            self.logger.info(f"获取新闻列表完成，共 {len(all_links)} 个链接")

            if list_page_error_count:
                self.stats["error_count"] += list_page_error_count
            
            return all_links
            
        except Exception as e:
            self.logger.error(f"获取新闻列表失败: {e}", exc_info=True)
            raise
    
    def fetch_news_detail(self, url: str) -> Optional[Dict[str, Any]]:
        """
        获取单篇新闻的详细信息
        
        Args:
            url: 新闻详情页面 URL
        
        Returns:
            包含新闻数据的字典，如果获取失败返回 None
            {
                "source": "ndrc",
                "title": str,
                "publish_time": str (ISO 8601 格式),
                "content": str,
                "url": str,
                "tags": List[str]
            }
        
        Raises:
            NetworkException: 网络请求失败
        """
        try:
            self.logger.debug(f"获取新闻详情: {url}")
            
            # 使用重试机制发送请求
            response = self.retry_handler.execute_with_retry(
                self._make_request,
                url
            )
            
            # 解析 HTML 获取新闻数据
            html_content = response.text
            news_data = self.parser.parse_news_detail(html_content, url)
            
            if not news_data:
                self.logger.warning(f"解析新闻详情失败: {url}")
                return None
            
            self.logger.debug(
                f"成功获取新闻详情: {news_data.get('title', 'N/A')[:30]}..."
            )
            
            return news_data
            
        except NetworkException as e:
            self.logger.error(f"获取新闻详情失败: {url}, 错误: {e}")
            self.stats["error_count"] += 1
            return None
        
        except Exception as e:
            self.logger.error(
                f"获取新闻详情时发生未知错误: {url}, 错误: {e}",
                exc_info=True
            )
            self.stats["error_count"] += 1
            return None
    
    def run(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """
        执行完整的采集流程
        
        流程：
        1. 获取新闻列表
        2. 遍历每个新闻链接
        3. 获取新闻详情
        4. 关键词过滤
        5. 去重检查
        6. 保存数据
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
        
        Returns:
            采集到的所有新闻数据列表
        """
        self.logger.info(
            f"开始采集发改委新闻: "
            f"start_date={start_date.strftime('%Y-%m-%d')}, "
            f"end_date={end_date.strftime('%Y-%m-%d')}"
        )
        
        # 重置统计信息
        self.stats = {
            "total_fetched": 0,
            "filtered_count": 0,
            "duplicate_count": 0,
            "saved_count": 0,
            "error_count": 0,
        }
        
        collected_news = []
        
        try:
            # 1. 获取新闻列表
            news_links = self.fetch_news_list(start_date, end_date)
            
            if not news_links:
                self.logger.warning("未获取到任何新闻链接")
                return collected_news
            
            # 2. 遍历每个新闻链接
            for i, url in enumerate(news_links, 1):
                self.logger.info(f"处理新闻 {i}/{len(news_links)}: {url}")
                
                try:
                    # 3. 获取新闻详情
                    news_data = self.fetch_news_detail(url)
                    
                    if not news_data:
                        continue
                    
                    self.stats["total_fetched"] += 1
                    
                    # 4. 关键词标注；必要时可启用硬过滤
                    matched_keywords = [
                        keyword for keyword in self.keyword_filter.get_keywords()
                        if keyword in f"{news_data.get('title', '')} {news_data.get('content', '')}"
                    ]
                    news_data["matched_keywords"] = matched_keywords
                    
                    if not matched_keywords:
                        self.stats["filtered_count"] += 1
                    
                    if self.config.get("enable_keyword_filter", False) and not matched_keywords:
                        self.logger.debug(
                            f"新闻不包含关键词，已过滤: "
                            f"{news_data.get('title', 'N/A')[:30]}..."
                        )
                        continue
                    
                    # 5. 去重检查
                    if self.deduplicator.is_duplicate(news_data, "ndrc"):
                        self.logger.debug(
                            f"新闻重复，已跳过: "
                            f"{news_data.get('title', 'N/A')[:30]}..."
                        )
                        self.stats["duplicate_count"] += 1
                        continue
                    
                    # 6. 保存数据
                    self.storage_manager.save(news_data, "ndrc")
                    
                    # 标记为已见
                    self.deduplicator.mark_as_seen(news_data, "ndrc")
                    
                    # 添加到结果列表
                    collected_news.append(news_data)
                    self.stats["saved_count"] += 1
                    
                    self.logger.info(
                        f"成功保存新闻: {news_data.get('title', 'N/A')[:30]}..."
                    )
                    
                except Exception as e:
                    self.logger.error(
                        f"处理新闻时发生错误: {url}, 错误: {e}",
                        exc_info=True
                    )
                    self.stats["error_count"] += 1
                    # 继续处理下一条新闻
                    continue
            
            # 保存去重索引
            self.deduplicator.save_index()
            
            # 输出统计信息
            self.logger.info(
                f"发改委新闻采集完成: "
                f"总获取={self.stats['total_fetched']}, "
                f"过滤={self.stats['filtered_count']}, "
                f"重复={self.stats['duplicate_count']}, "
                f"保存={self.stats['saved_count']}, "
                f"错误={self.stats['error_count']}"
            )
            
            return collected_news
            
        except Exception as e:
            self.logger.error(f"采集流程失败: {e}", exc_info=True)
            raise
    
    def get_stats(self) -> Dict[str, int]:
        """
        获取采集统计信息
        
        Returns:
            统计信息字典
        """
        return self.stats.copy()


# ============================================================================
# 便捷函数
# ============================================================================

def create_ndrc_spider_from_config(logger: logging.Logger = None) -> NDRCSpider:
    """
    从配置文件创建发改委爬虫
    
    Args:
        logger: 日志记录器，如果为 None 则自动创建
    
    Returns:
        配置好的发改委爬虫
    
    示例:
        >>> spider = create_ndrc_spider_from_config()
        >>> start_date = datetime.now() - timedelta(days=7)
        >>> end_date = datetime.now()
        >>> news_list = spider.run(start_date, end_date)
    """
    # 创建日志记录器（如果未提供）
    if logger is None:
        from utils.logger import get_logger
        logger = get_logger(__name__)
    
    # 导入配置
    try:
        from config import (
            NDRC_CONFIG,
            STOCK_KEYWORDS,
            DEDUP_CONFIG,
            STORAGE_CONFIG
        )
    except ImportError:
        raise ImportError("无法导入配置文件 config.py")
    
    # 创建组件
    parser = NDRCParser(logger)
    keyword_filter = KeywordFilter(STOCK_KEYWORDS, logger)
    deduplicator = Deduplicator(DEDUP_CONFIG["index_file"], logger)
    storage_manager = StorageManager(STORAGE_CONFIG["base_path"], logger)
    
    # 创建爬虫
    spider = NDRCSpider(
        config=NDRC_CONFIG,
        logger=logger,
        parser=parser,
        keyword_filter=keyword_filter,
        deduplicator=deduplicator,
        storage_manager=storage_manager
    )
    
    return spider


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    "NDRCSpider",
    "create_ndrc_spider_from_config",
]
