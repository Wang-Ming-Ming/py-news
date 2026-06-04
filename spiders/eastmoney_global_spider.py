# -*- coding: utf-8 -*-
"""
东方财富全球财经快讯采集器。

通过 AKShare 的 stock_info_global_em 接口获取全球财经快讯，作为股票分析系统的
全球重大新闻补充源。
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from filters.keyword_extractor import KeywordExtractor
from storage.deduplicator import Deduplicator
from storage.storage_manager import StorageManager


class EastmoneyGlobalSpider:
    """
    东方财富全球财经快讯爬虫。
    """

    source = "eastmoney_global"

    def __init__(
        self,
        config: Dict[str, Any],
        logger: logging.Logger,
        deduplicator: Deduplicator,
        storage_manager: StorageManager,
        keyword_extractor: Optional[KeywordExtractor] = None,
    ):
        self.config = config
        self.logger = logger
        self.deduplicator = deduplicator
        self.storage_manager = storage_manager
        self.keyword_extractor = keyword_extractor or KeywordExtractor(logger)
        self.limit = int(config.get("limit", 200))
        self.stats = {
            "total_fetched": 0,
            "duplicate_count": 0,
            "saved_count": 0,
            "error_count": 0,
        }
        self.logger.info(f"东方财富全球财经快讯爬虫初始化完成: limit={self.limit}")

    def _parse_publish_time(self, value: Any) -> str:
        if value is None:
            return datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

        text = str(value).strip()
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M:%S"):
            try:
                return datetime.strptime(text, fmt).strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                continue

        if "T" in text:
            return text

        self.logger.debug(f"无法解析东方财富发布时间，使用当前时间: {text}")
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    def _normalize_item(self, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        title = str(row.get("标题") or "").strip()
        if not title:
            return None

        content = str(row.get("摘要") or "").strip()
        publish_time = self._parse_publish_time(row.get("发布时间"))
        url = str(row.get("链接") or "").strip()
        analysis = self.keyword_extractor.analyze_text(f"{title} {content}")

        return {
            "source": self.source,
            "title": title,
            "publish_time": publish_time,
            "content": content,
            "summary": content,
            "url": url or f"eastmoney_global://{title}/{publish_time}",
            "tags": ["东方财富", "全球财经快讯"],
            "plate": [],
            "level": "",
            "keywords": analysis["keywords"],
            "plates": analysis["plates"],
        }

    def fetch_news(self) -> List[Dict[str, Any]]:
        try:
            import akshare as ak
        except ImportError as e:
            raise RuntimeError("缺少依赖 akshare，请先安装 requirements.txt") from e

        data_frame = ak.stock_info_global_em()
        records = data_frame.head(self.limit).to_dict("records")

        news_list: List[Dict[str, Any]] = []
        for row in records:
            item = self._normalize_item(row)
            if item:
                news_list.append(item)

        return news_list

    def run_once(self) -> List[Dict[str, Any]]:
        self.stats = {
            "total_fetched": 0,
            "duplicate_count": 0,
            "saved_count": 0,
            "error_count": 0,
        }
        collected_news: List[Dict[str, Any]] = []

        try:
            news_list = self.fetch_news()
            self.logger.info(f"成功获取东方财富全球财经快讯: {len(news_list)} 条")

            for news_data in news_list:
                self.stats["total_fetched"] += 1

                if self.deduplicator.is_duplicate(news_data, self.source):
                    self.stats["duplicate_count"] += 1
                    continue

                saved = self.storage_manager.save(news_data, self.source)
                self.deduplicator.mark_as_seen(news_data, self.source)

                if saved is False:
                    self.stats["duplicate_count"] += 1
                    continue

                collected_news.append(news_data)
                self.stats["saved_count"] += 1

            self.deduplicator.save_index()
            self.logger.info(
                f"东方财富全球财经快讯采集完成: "
                f"总获取={self.stats['total_fetched']}, "
                f"重复={self.stats['duplicate_count']}, "
                f"保存={self.stats['saved_count']}, "
                f"错误={self.stats['error_count']}"
            )
            return collected_news

        except Exception as e:
            self.stats["error_count"] += 1
            self.logger.error(f"东方财富全球财经快讯采集失败: {e}", exc_info=True)
            return []

    def get_stats(self) -> Dict[str, int]:
        return self.stats.copy()
