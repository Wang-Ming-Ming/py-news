# -*- coding: utf-8 -*-
"""
关键词过滤器模块

本模块实现了基于关键词的数据过滤功能，用于筛选包含特定关键词的新闻和公告。

主要功能：
- 维护可配置的关键词列表
- 动态添加和删除关键词
- 检查数据是否包含任一关键词
- 批量过滤数据列表
- 支持在多个字段中搜索关键词

需求：6.1, 6.2, 6.3, 6.7
"""

import logging
from typing import List, Dict, Any, Set


class KeywordFilter:
    """
    关键词过滤器
    
    用于根据关键词列表过滤数据，支持动态管理关键词和批量过滤操作。
    
    Attributes:
        keywords: 关键词集合（使用 set 提高查找效率）
        logger: 日志记录器
    
    示例:
        >>> from utils.logger import get_logger
        >>> logger = get_logger(__name__)
        >>> filter = KeywordFilter(["AI", "半导体", "新能源"], logger)
        >>> data = {"title": "AI芯片新突破", "content": "..."}
        >>> filter.filter(data)  # 返回 True（包含关键词 "AI"）
    """
    
    def __init__(self, keywords: List[str], logger: logging.Logger):
        """
        初始化关键词过滤器
        
        Args:
            keywords: 关键词列表
            logger: 日志记录器
        """
        self.keywords: Set[str] = set(keywords)
        self.logger = logger
        
        self.logger.info(
            f"关键词过滤器初始化完成，共 {len(self.keywords)} 个关键词"
        )
        self.logger.debug(f"关键词列表: {', '.join(sorted(self.keywords))}")
    
    def add_keyword(self, keyword: str):
        """
        添加关键词
        
        Args:
            keyword: 要添加的关键词
        
        示例:
            >>> filter.add_keyword("机器人")
        """
        if keyword in self.keywords:
            self.logger.debug(f"关键词已存在，跳过添加: {keyword}")
            return
        
        self.keywords.add(keyword)
        self.logger.info(f"添加关键词: {keyword}，当前共 {len(self.keywords)} 个关键词")
    
    def remove_keyword(self, keyword: str):
        """
        移除关键词
        
        Args:
            keyword: 要移除的关键词
        
        示例:
            >>> filter.remove_keyword("机器人")
        """
        if keyword not in self.keywords:
            self.logger.debug(f"关键词不存在，跳过移除: {keyword}")
            return
        
        self.keywords.remove(keyword)
        self.logger.info(f"移除关键词: {keyword}，当前共 {len(self.keywords)} 个关键词")
    
    def filter(
        self, 
        data: Dict[str, Any], 
        fields: List[str] = None
    ) -> bool:
        """
        判断数据是否包含任一关键词
        
        Args:
            data: 待过滤的数据字典
            fields: 需要检查的字段列表，默认为 ["title", "content"]
        
        Returns:
            True 表示数据包含关键词（应保留），False 表示不包含（应丢弃）
        
        示例:
            >>> data = {"title": "AI芯片新突破", "content": "详细内容..."}
            >>> filter.filter(data)  # 返回 True
            >>> 
            >>> data = {"title": "天气预报", "content": "今天晴天"}
            >>> filter.filter(data)  # 返回 False
            >>> 
            >>> # 自定义检查字段
            >>> data = {"title": "普通标题", "content": "AI相关内容"}
            >>> filter.filter(data, fields=["content"])  # 返回 True
        """
        # 默认检查 title 和 content 字段
        if fields is None:
            fields = ["title", "content"]
        
        # 检查每个字段
        for field in fields:
            if field not in data:
                continue
            
            field_value = data[field]
            
            # 跳过非字符串字段
            if not isinstance(field_value, str):
                continue
            
            # 检查是否包含任一关键词
            for keyword in self.keywords:
                if keyword in field_value:
                    self.logger.debug(
                        f"数据包含关键词 '{keyword}'，字段: {field}, "
                        f"内容片段: {field_value[:50]}..."
                    )
                    return True
        
        # 未找到任何关键词
        self.logger.debug(
            f"数据不包含任何关键词，已过滤: "
            f"{data.get('title', 'N/A')[:50]}..."
        )
        return False
    
    def batch_filter(self, data_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        批量过滤数据
        
        Args:
            data_list: 待过滤的数据列表
        
        Returns:
            过滤后的数据列表（仅包含包含关键词的数据）
        
        示例:
            >>> data_list = [
            ...     {"title": "AI新闻", "content": "..."},
            ...     {"title": "天气预报", "content": "..."},
            ...     {"title": "半导体行业", "content": "..."}
            ... ]
            >>> filtered = filter.batch_filter(data_list)
            >>> len(filtered)  # 返回 2（AI新闻 和 半导体行业）
        """
        original_count = len(data_list)
        
        # 过滤数据
        filtered_data = [data for data in data_list if self.filter(data)]
        
        filtered_count = original_count - len(filtered_data)
        
        self.logger.info(
            f"批量过滤完成: 原始数据 {original_count} 条, "
            f"保留 {len(filtered_data)} 条, 过滤 {filtered_count} 条"
        )
        
        return filtered_data
    
    def get_keywords(self) -> List[str]:
        """
        获取当前关键词列表
        
        Returns:
            关键词列表（按字母顺序排序）
        
        示例:
            >>> keywords = filter.get_keywords()
            >>> print(keywords)
            ['AI', '半导体', '新能源', '机器人']
        """
        return sorted(self.keywords)
    
    def get_keyword_count(self) -> int:
        """
        获取关键词数量
        
        Returns:
            关键词数量
        
        示例:
            >>> count = filter.get_keyword_count()
            >>> print(f"共有 {count} 个关键词")
        """
        return len(self.keywords)
    
    def clear_keywords(self):
        """
        清空所有关键词
        
        示例:
            >>> filter.clear_keywords()
        """
        count = len(self.keywords)
        self.keywords.clear()
        self.logger.warning(f"已清空所有关键词，共移除 {count} 个关键词")
    
    def update_keywords(self, keywords: List[str]):
        """
        更新关键词列表（替换现有关键词）
        
        Args:
            keywords: 新的关键词列表
        
        示例:
            >>> filter.update_keywords(["AI", "机器人", "云计算"])
        """
        old_count = len(self.keywords)
        self.keywords = set(keywords)
        new_count = len(self.keywords)
        
        self.logger.info(
            f"关键词列表已更新: 原有 {old_count} 个, 现有 {new_count} 个"
        )
        self.logger.debug(f"新关键词列表: {', '.join(sorted(self.keywords))}")


# ============================================================================
# 便捷函数
# ============================================================================

def create_keyword_filter_from_config(
    config_key: str = "STOCK_KEYWORDS",
    logger: logging.Logger = None
) -> KeywordFilter:
    """
    从配置文件创建关键词过滤器
    
    Args:
        config_key: 配置键名（STOCK_KEYWORDS 或 CNINFO_KEYWORDS）
        logger: 日志记录器，如果为 None 则自动创建
    
    Returns:
        配置好的关键词过滤器
    
    示例:
        >>> # 创建用于发改委和证券报的过滤器
        >>> filter = create_keyword_filter_from_config("STOCK_KEYWORDS")
        >>> 
        >>> # 创建用于证券信息网的过滤器
        >>> filter = create_keyword_filter_from_config("CNINFO_KEYWORDS")
    """
    # 导入配置
    try:
        from config import STOCK_KEYWORDS, CNINFO_KEYWORDS
    except ImportError:
        raise ImportError("无法导入配置文件 config.py")
    
    # 获取关键词列表
    if config_key == "STOCK_KEYWORDS":
        keywords = STOCK_KEYWORDS
    elif config_key == "CNINFO_KEYWORDS":
        keywords = CNINFO_KEYWORDS
    else:
        raise ValueError(f"无效的配置键: {config_key}")
    
    # 创建日志记录器（如果未提供）
    if logger is None:
        from utils.logger import get_logger
        logger = get_logger(__name__)
    
    # 创建过滤器
    return KeywordFilter(keywords, logger)


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    "KeywordFilter",
    "create_keyword_filter_from_config",
]
