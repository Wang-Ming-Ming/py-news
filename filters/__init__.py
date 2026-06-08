# -*- coding: utf-8 -*-
"""
过滤器模块

本模块包含数据过滤相关的组件：
- KeywordFilter: 关键词过滤器
- KeywordExtractor: 关键词提取器（待实现）
"""

from filters.keyword_filter import KeywordFilter, create_keyword_filter_from_config
from filters.news_enricher import (
    detect_risk_flags,
    enrich_news_item,
    normalize_publish_time,
    score_news,
)

__all__ = [
    "KeywordFilter",
    "create_keyword_filter_from_config",
    "detect_risk_flags",
    "enrich_news_item",
    "normalize_publish_time",
    "score_news",
]
