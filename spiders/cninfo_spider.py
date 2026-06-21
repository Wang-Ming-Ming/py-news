# -*- coding: utf-8 -*-
"""
证券信息网爬虫模块

本模块实现了证券信息网（CNInfo）的数据采集功能，用于从网站采集公司公告数据。

主要功能：
- 通过 API 调用从证券信息网采集公司公告
- 优先使用基于 API 的采集方式而非 HTML 解析
- 支持获取公告列表和公告详情
- 支持下载和解析 PDF 公告文件
- 集成关键词过滤器，过滤包含关键词的公告
- 集成解析器，解析 API 响应和 PDF 文件
- 使用重试机制处理网络请求失败
- 设置 30 秒超时和浏览器 User-Agent

需求：3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 10.1
"""

import logging
import requests
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from parsers.cninfo_parser import CNInfoParser
from filters.keyword_filter import KeywordFilter
from storage.deduplicator import Deduplicator
from storage.storage_manager import StorageManager
from utils.retry import RetryHandler
from utils.request_pacer import RequestPacer
from utils.exceptions import NetworkException, APIException, ParseException


class CNInfoSpider:
    """
    证券信息网公司公告爬虫
    
    从中国证券信息网采集公司公告，支持关键词过滤、去重和 PDF 解析。
    
    关键词过滤列表：
    - AI合作、算力订单、中标大合同、回购增持
    - 并购重组、战略合作、GPU、数据中心
    
    Attributes:
        config: 配置字典
        logger: 日志记录器
        parser: CNInfo 解析器
        keyword_filter: 关键词过滤器
        deduplicator: 去重器
        storage_manager: 存储管理器
        retry_handler: 重试处理器
    
    示例:
        >>> from utils.logger import get_logger
        >>> from config import CNINFO_CONFIG, CNINFO_KEYWORDS
        >>> 
        >>> logger = get_logger(__name__)
        >>> parser = CNInfoParser(logger)
        >>> keyword_filter = KeywordFilter(CNINFO_KEYWORDS, logger)
        >>> deduplicator = Deduplicator("data/.dedup_index.json", logger)
        >>> storage_manager = StorageManager("data", logger)
        >>> 
        >>> spider = CNInfoSpider(
        ...     config=CNINFO_CONFIG,
        ...     logger=logger,
        ...     parser=parser,
        ...     keyword_filter=keyword_filter,
        ...     deduplicator=deduplicator,
        ...     storage_manager=storage_manager
        ... )
        >>> 
        >>> # 采集过去 7 天的公告
        >>> start_date = datetime.now() - timedelta(days=7)
        >>> end_date = datetime.now()
        >>> announcements = spider.run(start_date, end_date)
    """
    
    # 关键词过滤列表
    KEYWORDS = [
        "AI合作", "算力订单", "中标大合同", "回购增持",
        "并购重组", "战略合作", "GPU", "数据中心"
    ]
    
    def __init__(
        self,
        config: Dict[str, Any],
        logger: logging.Logger,
        parser: CNInfoParser,
        keyword_filter: KeywordFilter,
        deduplicator: Deduplicator,
        storage_manager: StorageManager
    ):
        """
        初始化证券信息网爬虫
        
        Args:
            config: 配置字典
            logger: 日志记录器
            parser: CNInfo 解析器
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
        self.session = requests.Session()
        self.request_pacer = RequestPacer(config.get("min_request_interval", 1.0))
        
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
        self.base_url = config.get("base_url", "https://www.cninfo.com.cn")
        self.api_endpoints = config.get("api_endpoints", {})
        
        # 统计信息
        self.stats = {
            "total_fetched": 0,
            "filtered_count": 0,
            "duplicate_count": 0,
            "saved_count": 0,
            "error_count": 0,
        }
        
        self.logger.info(
            f"证券信息网爬虫初始化完成: base_url={self.base_url}, "
            f"timeout={self.timeout}s, retry_times={retry_times}"
        )
    
    def _make_request(
        self, 
        url: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> requests.Response:
        """
        发送 HTTP 请求
        
        Args:
            url: 请求 URL
            method: 请求方法（GET 或 POST）
            params: URL 参数
            data: 表单数据
            json_data: JSON 数据
            headers: 自定义请求头
        
        Returns:
            响应对象
        
        Raises:
            NetworkException: 网络请求失败
            APIException: API 调用失败
        """
        try:
            default_headers = {
                "User-Agent": self.user_agent,
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Referer": self.base_url,
                "X-Requested-With": "XMLHttpRequest",
            }
            
            # 合并自定义请求头
            if headers:
                default_headers.update(headers)
            
            self.logger.debug(f"发送请求: {method} {url}")
            self.request_pacer.wait()
            
            # 发送请求
            if method.upper() == "GET":
                response = self.session.get(
                    url,
                    params=params,
                    headers=default_headers,
                    timeout=self.timeout,
                    allow_redirects=True
                )
            elif method.upper() == "POST":
                response = self.session.post(
                    url,
                    params=params,
                    data=data,
                    json=json_data,
                    headers=default_headers,
                    timeout=self.timeout,
                    allow_redirects=True
                )
            else:
                raise ValueError(f"不支持的请求方法: {method}")
            
            # 检查响应状态
            if response.status_code == 429:
                # 速率限制
                retry_after = int(response.headers.get('Retry-After', 60))
                self.logger.warning(f"遇到速率限制（HTTP 429），需要等待 {retry_after} 秒")
                raise APIException(
                    f"速率限制，需要等待 {retry_after} 秒",
                    status_code=429,
                    retry_after=retry_after
                )
            
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
            status_code = e.response.status_code
            
            if 400 <= status_code < 500:
                self.logger.warning(
                    f"客户端错误: {url}, "
                    f"状态码={status_code}, "
                    f"错误: {e}"
                )
                raise APIException(f"客户端错误: {url}", status_code=status_code)
            
            elif status_code >= 500:
                self.logger.error(
                    f"服务器错误: {url}, "
                    f"状态码={status_code}, "
                    f"错误: {e}"
                )
                raise NetworkException(f"服务器错误: {url}, 状态码={status_code}")
        
        except APIException:
            # 重新抛出 API 异常
            raise
        
        except Exception as e:
            self.logger.error(f"请求失败: {url}, 错误: {e}", exc_info=True)
            raise NetworkException(f"请求失败: {url}, 错误: {e}")
    
    def fetch_announcement_list(
        self, 
        start_date: datetime, 
        end_date: datetime,
        stock_code: Optional[str] = None,
        page_num: int = 1,
        page_size: int = 30
    ) -> List[Dict[str, Any]]:
        """
        获取公告列表
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            stock_code: 可选的股票代码过滤
            page_num: 页码（从 1 开始）
            page_size: 每页数量
        
        Returns:
            公告元数据列表
        
        Raises:
            NetworkException: 网络请求失败
            APIException: API 调用失败
        """
        self.logger.info(
            f"开始获取公告列表: "
            f"start_date={start_date.strftime('%Y-%m-%d')}, "
            f"end_date={end_date.strftime('%Y-%m-%d')}, "
            f"stock_code={stock_code}, "
            f"page_num={page_num}, "
            f"page_size={page_size}"
        )
        
        try:
            # 获取 API 端点
            endpoint = self.api_endpoints.get("announcement_list")
            
            if not endpoint:
                self.logger.error("未配置 announcement_list API 端点")
                return []
            
            # 构建完整 URL
            if endpoint.startswith("http"):
                url = endpoint
            else:
                url = f"{self.base_url}{endpoint}"
            
            # 构建请求参数
            # 注意：实际参数需要根据证券信息网的 API 文档调整
            params = {
                "pageNum": page_num,
                "pageSize": page_size,
                "seDate": f"{start_date.strftime('%Y-%m-%d')}~{end_date.strftime('%Y-%m-%d')}",
                "column": "szse",  # 深交所
                "tabName": "fulltext",
                "plate": "",
                "searchkey": "",
                "secid": "",
                "category": "",
                "trade": "",
                "sortName": "",
                "sortType": "desc",
                "isHLtitle": "true",
            }
            
            # 如果指定了股票代码，添加到参数中
            if stock_code:
                params["stock"] = stock_code
            
            # 使用重试机制发送请求
            response = self.retry_handler.execute_with_retry(
                self._make_request,
                url,
                method="POST",
                data=params
            )
            
            # 解析响应
            try:
                response_data = response.json()
            except ValueError as e:
                self.logger.error(f"JSON 解析失败: {e}, 响应内容: {response.text[:200]}")
                return []
            
            # 使用解析器提取公告数据
            announcements = self.parser.parse_announcement_list(response_data)
            
            self.logger.info(
                f"成功获取公告列表: {len(announcements)} 条 "
                f"(页码: {page_num})"
            )
            
            return announcements
            
        except NetworkException as e:
            self.logger.error(f"获取公告列表失败: {e}")
            self.stats["error_count"] += 1
            return []
        
        except APIException as e:
            self.logger.error(f"API 调用失败: {e}")
            self.stats["error_count"] += 1
            return []
        
        except Exception as e:
            self.logger.error(
                f"获取公告列表时发生未知错误: {e}",
                exc_info=True
            )
            self.stats["error_count"] += 1
            return []
    
    def fetch_announcement_detail(
        self, 
        announcement_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取公告详情
        
        Args:
            announcement_id: 公告 ID
        
        Returns:
            公告详细数据，如果获取失败返回 None
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
        
        Raises:
            NetworkException: 网络请求失败
        """
        try:
            self.logger.debug(f"获取公告详情: {announcement_id}")
            
            # 获取 API 端点
            endpoint = self.api_endpoints.get("announcement_detail")
            
            if not endpoint:
                self.logger.warning("未配置 announcement_detail API 端点")
                return None
            
            # 构建完整 URL
            if endpoint.startswith("http"):
                url = endpoint
            else:
                url = f"{self.base_url}{endpoint}"
            
            # 构建请求参数
            params = {
                "announcementId": announcement_id,
            }
            
            # 使用重试机制发送请求
            response = self.retry_handler.execute_with_retry(
                self._make_request,
                url,
                method="GET",
                params=params
            )
            
            # 解析响应
            try:
                response_data = response.json()
            except ValueError as e:
                self.logger.error(f"JSON 解析失败: {e}, 响应内容: {response.text[:200]}")
                return None
            
            # 使用解析器提取公告数据
            announcements = self.parser.parse_announcement_list(response_data)
            
            if announcements:
                announcement_data = announcements[0]
                self.logger.debug(
                    f"成功获取公告详情: {announcement_data.get('title', 'N/A')[:30]}..."
                )
                return announcement_data
            else:
                self.logger.warning(f"未找到公告详情: {announcement_id}")
                return None
            
        except NetworkException as e:
            self.logger.error(f"获取公告详情失败: {announcement_id}, 错误: {e}")
            self.stats["error_count"] += 1
            return None
        
        except Exception as e:
            self.logger.error(
                f"获取公告详情时发生未知错误: {announcement_id}, 错误: {e}",
                exc_info=True
            )
            self.stats["error_count"] += 1
            return None
    
    def download_pdf(self, pdf_url: str) -> Optional[bytes]:
        """
        下载 PDF 文件
        
        Args:
            pdf_url: PDF 文件 URL
        
        Returns:
            PDF 文件的二进制内容，如果下载失败返回 None
        
        Raises:
            NetworkException: 网络请求失败
        """
        try:
            self.logger.debug(f"下载 PDF: {pdf_url}")
            
            # 如果是相对路径，补全为完整 URL
            if not pdf_url.startswith("http"):
                if pdf_url.startswith("/"):
                    pdf_url = self.base_url + pdf_url
                else:
                    pdf_url = self.base_url + "/" + pdf_url
            
            # 使用重试机制发送请求
            response = self.retry_handler.execute_with_retry(
                self._make_request,
                pdf_url,
                method="GET"
            )
            
            pdf_content = response.content
            
            self.logger.debug(
                f"成功下载 PDF: {pdf_url}, "
                f"大小: {len(pdf_content)} 字节"
            )
            
            return pdf_content
            
        except NetworkException as e:
            self.logger.error(f"下载 PDF 失败: {pdf_url}, 错误: {e}")
            self.stats["error_count"] += 1
            return None
        
        except Exception as e:
            self.logger.error(
                f"下载 PDF 时发生未知错误: {pdf_url}, 错误: {e}",
                exc_info=True
            )
            self.stats["error_count"] += 1
            return None
    
    def run(
        self,
        start_date: datetime,
        end_date: datetime,
        stock_code: Optional[str] = None,
        max_pages: int = 500
    ) -> List[Dict[str, Any]]:
        """
        执行完整的采集流程
        
        流程：
        1. 获取公告列表（支持分页）
        2. 遍历每条公告
        3. 关键词过滤
        4. 去重检查
        5. 保存数据
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            stock_code: 可选的股票代码过滤
            max_pages: 最多获取的页数
        
        Returns:
            采集到的所有公告数据列表
        """
        self.logger.info(
            f"开始采集证券信息网公告: "
            f"start_date={start_date.strftime('%Y-%m-%d')}, "
            f"end_date={end_date.strftime('%Y-%m-%d')}, "
            f"stock_code={stock_code}"
        )
        
        # 重置统计信息
        self.stats = {
            "total_fetched": 0,
            "filtered_count": 0,
            "duplicate_count": 0,
            "saved_count": 0,
            "error_count": 0,
        }
        
        collected_announcements = []
        
        try:
            # 遍历多个页面
            seen_pages: set[str] = set()
            for page_num in range(1, max_pages + 1):
                self.logger.info(f"处理第 {page_num} 页")
                
                try:
                    # 获取公告列表
                    announcements = self.fetch_announcement_list(
                        start_date=start_date,
                        end_date=end_date,
                        stock_code=stock_code,
                        page_num=page_num,
                        page_size=30
                    )
                    
                    if not announcements:
                        self.logger.info(f"第 {page_num} 页没有公告，停止翻页")
                        break
                    page_identity = "|".join(
                        str(item.get("announcement_id") or item.get("url") or item.get("title"))
                        for item in announcements
                    )
                    if page_identity in seen_pages:
                        self.logger.warning("巨潮公告页面重复，停止翻页")
                        break
                    seen_pages.add(page_identity)
                    
                    # 处理每条公告
                    for announcement_data in announcements:
                        self.stats["total_fetched"] += 1
                        
                        # 关键词标注；必要时可启用硬过滤
                        matched_keywords = [
                            keyword for keyword in self.keyword_filter.get_keywords()
                            if keyword in f"{announcement_data.get('title', '')} {announcement_data.get('content', '')}"
                        ]
                        announcement_data["matched_keywords"] = matched_keywords
                        
                        if not matched_keywords:
                            self.stats["filtered_count"] += 1
                        
                        if self.config.get("enable_keyword_filter", False) and not matched_keywords:
                            self.logger.debug(
                                f"公告不包含关键词，已过滤: "
                                f"{announcement_data.get('title', 'N/A')[:30]}..."
                            )
                            continue
                        
                        # 去重检查
                        if self.deduplicator.is_duplicate(announcement_data, "cninfo"):
                            self.logger.debug(
                                f"公告重复，已跳过: "
                                f"{announcement_data.get('title', 'N/A')[:30]}..."
                            )
                            self.stats["duplicate_count"] += 1
                            continue
                        
                        # 保存数据
                        self.storage_manager.save(announcement_data, "cninfo")
                        
                        # 标记为已见
                        self.deduplicator.mark_as_seen(announcement_data, "cninfo")
                        
                        # 添加到结果列表
                        collected_announcements.append(announcement_data)
                        self.stats["saved_count"] += 1
                        
                        self.logger.info(
                            f"成功保存公告: "
                            f"{announcement_data.get('stock_code', 'N/A')} - "
                            f"{announcement_data.get('title', 'N/A')[:30]}..."
                        )

                    if len(announcements) < 30:
                        self.logger.info("巨潮公告已到最后一页")
                        break
                
                except Exception as e:
                    self.logger.error(
                        f"处理第 {page_num} 页时发生错误: {e}",
                        exc_info=True
                    )
                    self.stats["error_count"] += 1
                    # 继续处理下一页
                    continue
            
            # 保存去重索引
            self.deduplicator.save_index()
            
            # 输出统计信息
            self.logger.info(
                f"证券信息网公告采集完成: "
                f"总获取={self.stats['total_fetched']}, "
                f"过滤={self.stats['filtered_count']}, "
                f"重复={self.stats['duplicate_count']}, "
                f"保存={self.stats['saved_count']}, "
                f"错误={self.stats['error_count']}"
            )
            
            return collected_announcements
            
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

def create_cninfo_spider_from_config(logger: logging.Logger = None) -> CNInfoSpider:
    """
    从配置文件创建证券信息网爬虫
    
    Args:
        logger: 日志记录器，如果为 None 则自动创建
    
    Returns:
        配置好的证券信息网爬虫
    
    示例:
        >>> spider = create_cninfo_spider_from_config()
        >>> start_date = datetime.now() - timedelta(days=7)
        >>> end_date = datetime.now()
        >>> announcements = spider.run(start_date, end_date)
    """
    # 创建日志记录器（如果未提供）
    if logger is None:
        from utils.logger import get_logger
        logger = get_logger(__name__)
    
    # 导入配置
    try:
        from config import (
            CNINFO_CONFIG,
            CNINFO_KEYWORDS,
            DEDUP_CONFIG,
            STORAGE_CONFIG
        )
    except ImportError:
        raise ImportError("无法导入配置文件 config.py")
    
    # 创建组件
    parser = CNInfoParser(logger)
    keyword_filter = KeywordFilter(CNINFO_KEYWORDS, logger)
    deduplicator = Deduplicator(DEDUP_CONFIG["index_file"], logger)
    storage_manager = StorageManager(STORAGE_CONFIG["base_path"], logger)
    
    # 创建爬虫
    spider = CNInfoSpider(
        config=CNINFO_CONFIG,
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
    "CNInfoSpider",
    "create_cninfo_spider_from_config",
]
