# -*- coding: utf-8 -*-
"""
东方财富全球财经快讯采集器。

通过 AKShare 的 stock_info_global_em 接口获取全球财经快讯，作为股票分析系统的
全球重大新闻补充源。
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from filters.keyword_extractor import KeywordExtractor
from storage.deduplicator import Deduplicator
from storage.storage_manager import StorageManager
from utils.request_pacer import RequestPacer


class EastmoneyGlobalSpider:
    """
    东方财富全球财经快讯爬虫。
    """

    source = "eastmoney_global"
    fast_news_url = "https://np-weblist.eastmoney.com/comm/web/getFastNewsList"

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
        self.timeout = int(config.get("timeout", 30))
        self.session = requests.Session()
        self.request_pacer = RequestPacer(float(config.get("min_request_interval", 1.0)))
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

    def fetch_news(
        self,
        start_date: Optional[datetime] = None,
        page_size: int = 200,
        max_pages: int = 500,
    ) -> List[Dict[str, Any]]:
        news_list: List[Dict[str, Any]] = []
        cursor = ""
        seen_cursors: set[str] = set()
        cutoff = start_date.timestamp() if start_date is not None else None

        for page_number in range(1, max_pages + 1):
            self.request_pacer.wait()
            response = self.session.get(
                self.fast_news_url,
                params={
                    "client": "web",
                    "biz": "web_724",
                    "fastColumn": "102",
                    "sortEnd": cursor,
                    "pageSize": str(min(max(1, page_size), 200)),
                    "req_trace": str(int(time.time() * 1000)),
                },
                timeout=self.timeout,
                headers={"User-Agent": "Mozilla/5.0", "Referer": "https://kuaixun.eastmoney.com/"},
            )
            response.raise_for_status()
            payload = response.json()
            records = ((payload.get("data") or {}).get("fastNewsList") or [])
            if not records:
                break

            oldest_time: Optional[datetime] = None
            for raw in records:
                row = {
                    "标题": raw.get("title"),
                    "摘要": raw.get("summary"),
                    "发布时间": raw.get("showTime"),
                    "链接": (
                        f"https://finance.eastmoney.com/a/{raw.get('code')}.html"
                        if raw.get("code") else ""
                    ),
                }
                item = self._normalize_item(row)
                if item:
                    news_list.append(item)
                try:
                    current_time = datetime.strptime(str(raw.get("showTime")), "%Y-%m-%d %H:%M:%S")
                    oldest_time = current_time if oldest_time is None else min(oldest_time, current_time)
                except ValueError:
                    continue

            next_cursor = str(records[-1].get("realSort") or "")
            self.logger.info(
                "东方财富快讯历史回补第 %s 页: 获取=%s, 最早时间=%s",
                page_number,
                len(records),
                oldest_time.isoformat(timespec="seconds") if oldest_time else None,
            )
            if cutoff is None or (oldest_time is not None and oldest_time.timestamp() <= cutoff):
                break
            if not next_cursor or next_cursor == cursor or next_cursor in seen_cursors:
                self.logger.warning("东方财富快讯历史游标未向前推进，停止翻页")
                break
            seen_cursors.add(next_cursor)
            cursor = next_cursor

        if cutoff is not None:
            news_list = [
                item for item in news_list
                if datetime.strptime(str(item["publish_time"])[:19], "%Y-%m-%dT%H:%M:%S").timestamp() >= cutoff
            ]

        return news_list

    def run_once(self, start_date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        self.stats = {
            "total_fetched": 0,
            "duplicate_count": 0,
            "saved_count": 0,
            "error_count": 0,
        }
        collected_news: List[Dict[str, Any]] = []

        try:
            news_list = self.fetch_news(start_date=start_date)
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
