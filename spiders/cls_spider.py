# -*- coding: utf-8 -*-
"""
证券报爬虫模块

本模块实现了证券报（CLS）网站的数据采集功能，用于从网站采集实时热点新闻数据。

主要功能：
- 通过 API 调用从证券报网站采集热点新闻
- 支持多个新闻类别（电报、AI新闻、板块异动、涨停逻辑、热点题材、产业链新闻）
- 优先使用基于 API 的采集方式而非 HTML 解析
- 支持持续采集模式（每 60 秒采集一次）
- 集成解析器，解析 API 响应
- 使用重试机制处理 API 请求失败和速率限制
- 设置 30 秒超时和浏览器 User-Agent

需求：2.1, 2.2, 2.3, 2.4, 2.5, 2.8, 10.1, 10.6
"""

import logging
import hashlib
import requests
import time
from typing import List, Dict, Any, Optional
from datetime import datetime

from parsers.cls_parser import CLSParser
from storage.deduplicator import Deduplicator
from storage.storage_manager import StorageManager
from filters.keyword_extractor import KeywordExtractor
from utils.retry import RetryHandler
from utils.exceptions import NetworkException, APIException


class CLSSpider:
    """
    证券报热点新闻爬虫
    
    从中国证券报网站采集实时热点新闻，支持多个新闻类别和持续采集模式。
    
    支持的新闻类别：
    - telegraph: 电报
    - ai_news: AI新闻
    - plate_movement: 板块异动
    - limit_up_logic: 涨停逻辑
    - hot_topics: 热点题材
    - industry_chain: 产业链新闻
    
    Attributes:
        config: 配置字典
        logger: 日志记录器
        parser: CLS 解析器
        deduplicator: 去重器
        storage_manager: 存储管理器
        retry_handler: 重试处理器
    
    示例:
        >>> from utils.logger import get_logger
        >>> from config import CLS_CONFIG
        >>> 
        >>> logger = get_logger(__name__)
        >>> parser = CLSParser(logger)
        >>> deduplicator = Deduplicator("data/.dedup_index.json", logger)
        >>> storage_manager = StorageManager("data", logger)
        >>> 
        >>> spider = CLSSpider(
        ...     config=CLS_CONFIG,
        ...     logger=logger,
        ...     parser=parser,
        ...     deduplicator=deduplicator,
        ...     storage_manager=storage_manager
        ... )
        >>> 
        >>> # 执行一次采集
        >>> news_list = spider.run_once()
        >>> 
        >>> # 持续采集模式（每 60 秒一次）
        >>> spider.run_continuous(interval=60)
    """
    
    # 支持的新闻类别
    CATEGORIES = [
        "telegraph",      # 电报
    ]
    
    def __init__(
        self,
        config: Dict[str, Any],
        logger: logging.Logger,
        parser: CLSParser,
        deduplicator: Deduplicator,
        storage_manager: StorageManager,
        keyword_extractor: Optional[KeywordExtractor] = None
    ):
        """
        初始化证券报爬虫
        
        Args:
            config: 配置字典，包含 API 端点、密钥等
            logger: 日志记录器
            parser: CLS 解析器
            deduplicator: 去重器
            storage_manager: 存储管理器
            keyword_extractor: 关键词提取器（可选）
        """
        self.config = config
        self.logger = logger
        self.parser = parser
        self.deduplicator = deduplicator
        self.storage_manager = storage_manager
        self.keyword_extractor = keyword_extractor or KeywordExtractor(logger)
        
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
        self.base_url = config.get("base_url", "https://www.cls.cn")
        self.api_endpoints = config.get("api_endpoints", {})
        self.categories = list(self.api_endpoints.keys()) or self.CATEGORIES
        self.api_key = config.get("api_key", "")
        self.api_token = config.get("api_token", "")
        self.interval = config.get("interval", 60)
        
        # 统计信息
        self.stats = {
            "total_fetched": 0,
            "duplicate_count": 0,
            "saved_count": 0,
            "error_count": 0,
        }
        
        self.logger.info(
            f"证券报爬虫初始化完成: base_url={self.base_url}, "
            f"timeout={self.timeout}s, retry_times={retry_times}, "
            f"interval={self.interval}s"
        )

    @staticmethod
    def _sort_key(value: Any) -> str:
        return str(value).upper()

    @classmethod
    def _stringify_sign_value(cls, key: str, value: Any) -> Optional[str]:
        if value is None:
            return None

        if isinstance(value, (str, int, float, bool)):
            return f"{key}={value}"

        if isinstance(value, list):
            if not value:
                return f"{key}[]"
            return "&".join(
                item
                for index, child in enumerate(value)
                for item in [cls._stringify_sign_value(f"{key}[{index}]", child)]
                if item
            )

        if isinstance(value, dict):
            return "&".join(
                item
                for child_key in sorted(value.keys(), key=cls._sort_key)
                for item in [cls._stringify_sign_value(f"{key}[{child_key}]", value[child_key])]
                if item
            )

        return f"{key}={value}"

    @classmethod
    def _build_cls_sign(cls, params: Dict[str, Any]) -> str:
        query = "&".join(
            item
            for key in sorted(params.keys(), key=cls._sort_key)
            for item in [cls._stringify_sign_value(key, params[key])]
            if item
        )
        sha1_value = hashlib.sha1(query.encode("utf-8")).hexdigest()
        return hashlib.md5(sha1_value.encode("utf-8")).hexdigest()

    @classmethod
    def _build_signed_params(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        signed_params = dict(params)
        signed_params["os"] = signed_params.get("os", "web")
        signed_params["sv"] = signed_params.get("sv", "8.7.9")
        signed_params["app"] = signed_params.get("app", "CailianpressWeb")
        signed_params["sign"] = cls._build_cls_sign(signed_params)
        return signed_params
    
    def _make_request(
        self, 
        url: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None
    ) -> requests.Response:
        """
        发送 HTTP 请求
        
        Args:
            url: 请求 URL
            method: 请求方法（GET 或 POST）
            params: URL 参数
            data: 表单数据
            json_data: JSON 数据
        
        Returns:
            响应对象
        
        Raises:
            NetworkException: 网络请求失败
            APIException: API 调用失败
        """
        try:
            headers = {
                "User-Agent": self.user_agent,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
                "Referer": self.base_url,
            }
            
            # 添加 API 认证（如果配置）
            if self.api_key:
                headers["X-API-Key"] = self.api_key
            
            if self.api_token:
                headers["Authorization"] = f"Bearer {self.api_token}"
            
            self.logger.debug(f"发送请求: {method} {url}")
            
            # 发送请求
            if method.upper() == "GET":
                response = requests.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.timeout,
                    allow_redirects=True
                )
            elif method.upper() == "POST":
                response = requests.post(
                    url,
                    params=params,
                    data=data,
                    json=json_data,
                    headers=headers,
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
    
    def _handle_rate_limit(self, retry_after: int):
        """
        处理速率限制
        
        Args:
            retry_after: 需要等待的秒数
        """
        self.logger.warning(f"遇到速率限制，等待 {retry_after} 秒后重试")
        time.sleep(retry_after)
    
    def fetch_category_news(
        self, 
        category: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        从指定类别获取新闻
        
        Args:
            category: 新闻类别（必须是 CATEGORIES 中的一个）
            limit: 获取的新闻数量上限
        
        Returns:
            新闻数据列表，每条新闻格式：
            {
                "source": "cls",
                "title": str,
                "publish_time": str (ISO 8601 格式),
                "content": str,
                "tags": List[str],
                "plate": List[str],
                "level": str
            }
        
        Raises:
            APIException: API 调用失败
        """
        if category not in self.CATEGORIES:
            self.logger.warning(
                f"不支持的新闻类别: {category}, "
                f"支持的类别: {self.CATEGORIES}"
            )
            return []
        
        self.logger.info(f"开始获取 {category} 类别的新闻，限制 {limit} 条")
        
        try:
            # 获取 API 端点
            endpoint = self.api_endpoints.get(category)
            
            if not endpoint:
                self.logger.warning(f"未配置 {category} 类别的 API 端点")
                return []
            
            # 构建完整 URL
            if endpoint.startswith("http"):
                url = endpoint
            else:
                url = f"{self.base_url}{endpoint}"
            
            # 构建请求参数
            params = self._build_signed_params({
                "refresh_type": 1,
                "rn": limit,
                "last_time": int(time.time()),
            })
            
            # 使用重试机制发送请求
            try:
                response = self.retry_handler.execute_with_retry(
                    self._make_request,
                    url,
                    method="GET",
                    params=params
                )
            except APIException as e:
                # 如果是速率限制，等待后重试
                if e.status_code == 429:
                    self._handle_rate_limit(e.retry_after)
                    # 再次尝试
                    response = self._make_request(
                        url,
                        method="GET",
                        params=params
                    )
                else:
                    raise
            
            # 解析响应
            try:
                response_data = response.json()
            except ValueError as e:
                self.logger.error(f"JSON 解析失败: {e}, 响应内容: {response.text[:200]}")
                return []
            
            # 使用解析器提取新闻数据
            news_list = self.parser.parse_news_list(response_data, category=category)
            
            self.logger.info(
                f"成功获取 {category} 类别的新闻: {len(news_list)} 条"
            )
            
            return news_list
            
        except NetworkException as e:
            self.logger.error(f"获取 {category} 类别新闻失败: {e}")
            self.stats["error_count"] += 1
            return []
        
        except APIException as e:
            self.logger.error(f"API 调用失败: {category}, 错误: {e}")
            self.stats["error_count"] += 1
            return []
        
        except Exception as e:
            self.logger.error(
                f"获取 {category} 类别新闻时发生未知错误: {e}",
                exc_info=True
            )
            self.stats["error_count"] += 1
            return []
    
    def run_once(self) -> List[Dict[str, Any]]:
        """
        执行一次完整的采集流程（所有类别）
        
        流程：
        1. 遍历所有新闻类别
        2. 获取每个类别的新闻
        3. 去重检查
        4. 使用关键词提取器分析新闻并添加关键词和板块信息
        5. 保存数据
        6. 生成关键词频率统计
        
        Returns:
            采集到的所有新闻数据列表
        """
        self.logger.info("开始采集证券报新闻（所有类别）")
        
        # 重置统计信息
        self.stats = {
            "total_fetched": 0,
            "duplicate_count": 0,
            "saved_count": 0,
            "error_count": 0,
        }
        
        collected_news = []
        
        try:
            # 遍历所有类别
            for category in self.categories:
                self.logger.info(f"处理类别: {category}")
                
                try:
                    # 获取该类别的新闻
                    news_list = self.fetch_category_news(category, limit=20)
                    
                    if not news_list:
                        self.logger.debug(f"类别 {category} 未获取到新闻")
                        continue
                    
                    # 处理每条新闻
                    for news_data in news_list:
                        self.stats["total_fetched"] += 1
                        
                        # 去重检查
                        # 注意：CLS 新闻可能没有 url 字段，需要基于标题和时间去重
                        # 为了兼容去重器，我们添加一个虚拟 url
                        if "url" not in news_data or not news_data["url"]:
                            # 使用标题和时间生成唯一标识
                            news_data["url"] = f"cls://{category}/{news_data['title']}/{news_data['publish_time']}"
                        
                        if self.deduplicator.is_duplicate(news_data, "cls"):
                            self.logger.debug(
                                f"新闻重复，已跳过: "
                                f"{news_data.get('title', 'N/A')[:30]}..."
                            )
                            self.stats["duplicate_count"] += 1
                            continue
                        
                        # 使用关键词提取器分析新闻
                        text = ""
                        if "title" in news_data:
                            text += news_data["title"] + " "
                        if "content" in news_data:
                            text += news_data["content"]
                        
                        # 提取关键词和板块
                        analysis = self.keyword_extractor.analyze_text(text)
                        news_data["keywords"] = analysis["keywords"]
                        news_data["plates"] = analysis["plates"]
                        
                        self.logger.debug(
                            f"新闻分析完成: 关键词={len(analysis['keywords'])}, "
                            f"板块={', '.join(analysis['plates'])}"
                        )
                        
                        # 保存数据
                        self.storage_manager.save(news_data, "cls")
                        
                        # 标记为已见
                        self.deduplicator.mark_as_seen(news_data, "cls")
                        
                        # 添加到结果列表
                        collected_news.append(news_data)
                        self.stats["saved_count"] += 1
                        
                        self.logger.debug(
                            f"成功保存新闻: {news_data.get('title', 'N/A')[:30]}..."
                        )
                
                except Exception as e:
                    self.logger.error(
                        f"处理类别 {category} 时发生错误: {e}",
                        exc_info=True
                    )
                    self.stats["error_count"] += 1
                    # 继续处理下一个类别
                    continue
            
            # 保存去重索引
            self.deduplicator.save_index()
            
            # 生成关键词频率统计
            if collected_news:
                self.logger.info("生成关键词频率统计...")
                try:
                    statistics = self.keyword_extractor.generate_statistics(
                        collected_news,
                        time_window_hours=1,
                        high_frequency_threshold=5
                    )
                    
                    self.logger.info(
                        f"统计信息: "
                        f"总关键词={len(statistics['keyword_frequency'])}, "
                        f"高频主题={len(statistics['high_frequency_topics'])}, "
                        f"板块分布={statistics['plate_distribution']}"
                    )
                    
                    # 输出高频主题
                    if statistics['high_frequency_topics']:
                        self.logger.info(
                            f"高频主题（每小时 > 5次）: "
                            f"{', '.join(statistics['high_frequency_topics'][:10])}"
                        )
                    
                    # 输出前10个高频关键词
                    if statistics['top_keywords']:
                        top_10 = [f"{kw}({cnt})" for kw, cnt in statistics['top_keywords'][:10]]
                        self.logger.info(f"前10个高频关键词: {', '.join(top_10)}")
                    
                except Exception as e:
                    self.logger.error(f"生成统计信息失败: {e}", exc_info=True)
            
            # 输出统计信息
            self.logger.info(
                f"证券报新闻采集完成: "
                f"总获取={self.stats['total_fetched']}, "
                f"重复={self.stats['duplicate_count']}, "
                f"保存={self.stats['saved_count']}, "
                f"错误={self.stats['error_count']}"
            )
            
            return collected_news
            
        except Exception as e:
            self.logger.error(f"采集流程失败: {e}", exc_info=True)
            raise
    
    def run_continuous(self, interval: Optional[int] = None):
        """
        持续采集模式，每隔指定时间采集一次
        
        Args:
            interval: 采集间隔（秒），默认使用配置中的值（60秒）
        
        注意：此方法会一直运行，直到被中断（Ctrl+C）
        """
        if interval is None:
            interval = self.interval
        
        self.logger.info(f"启动持续采集模式，采集间隔: {interval} 秒")
        
        try:
            while True:
                try:
                    # 执行一次采集
                    self.run_once()
                    
                    # 等待指定时间
                    self.logger.info(f"等待 {interval} 秒后进行下一次采集...")
                    time.sleep(interval)
                
                except KeyboardInterrupt:
                    self.logger.info("收到中断信号，停止持续采集")
                    break
                
                except Exception as e:
                    self.logger.error(
                        f"采集过程中发生错误: {e}，等待 {interval} 秒后重试",
                        exc_info=True
                    )
                    time.sleep(interval)
        
        except KeyboardInterrupt:
            self.logger.info("持续采集已停止")
    
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

def create_cls_spider_from_config(logger: logging.Logger = None) -> CLSSpider:
    """
    从配置文件创建证券报爬虫
    
    Args:
        logger: 日志记录器，如果为 None 则自动创建
    
    Returns:
        配置好的证券报爬虫
    
    示例:
        >>> spider = create_cls_spider_from_config()
        >>> news_list = spider.run_once()
    """
    # 创建日志记录器（如果未提供）
    if logger is None:
        from utils.logger import get_logger
        logger = get_logger(__name__)
    
    # 导入配置
    try:
        from config import (
            CLS_CONFIG,
            DEDUP_CONFIG,
            STORAGE_CONFIG
        )
    except ImportError:
        raise ImportError("无法导入配置文件 config.py")
    
    # 创建组件
    parser = CLSParser(logger)
    deduplicator = Deduplicator(DEDUP_CONFIG["index_file"], logger)
    storage_manager = StorageManager(STORAGE_CONFIG["base_path"], logger)
    keyword_extractor = KeywordExtractor(logger)
    
    # 创建爬虫
    spider = CLSSpider(
        config=CLS_CONFIG,
        logger=logger,
        parser=parser,
        deduplicator=deduplicator,
        storage_manager=storage_manager,
        keyword_extractor=keyword_extractor
    )
    
    return spider


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    "CLSSpider",
    "create_cls_spider_from_config",
]
