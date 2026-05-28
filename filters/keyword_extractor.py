# -*- coding: utf-8 -*-
"""
关键词提取器模块

本模块实现了关键词提取和统计分析功能，用于从采集的数据中提取关键词、
分类到板块并生成统计信息。

主要功能：
- 从文本中提取关键词
- 根据关键词分类到板块（AI、算力、半导体、机器人）
- 生成关键词频率统计
- 识别高频主题（每小时出现超过 5 次的关键词）

需求：2.6, 2.7, 6.4, 6.5, 6.6
"""

import logging
import re
from typing import List, Dict, Any, Set, Tuple
from datetime import datetime, timedelta
from collections import Counter, defaultdict


class KeywordExtractor:
    """
    关键词提取器和统计分析器
    
    用于从文本中提取关键词、分类到板块并生成统计信息。
    
    Attributes:
        PLATE_MAPPING: 板块分类映射字典
        logger: 日志记录器
        keyword_history: 关键词历史记录（用于高频主题识别）
    
    示例:
        >>> from utils.logger import get_logger
        >>> logger = get_logger(__name__)
        >>> extractor = KeywordExtractor(logger)
        >>> 
        >>> # 提取关键词
        >>> keywords = extractor.extract_keywords("AI芯片和半导体技术发展")
        >>> print(keywords)
        ['AI', '芯片', '半导体', '技术']
        >>> 
        >>> # 分类到板块
        >>> plates = extractor.classify_plate(keywords)
        >>> print(plates)
        ['AI', '半导体']
        >>> 
        >>> # 生成统计信息
        >>> data_list = [...]
        >>> stats = extractor.generate_statistics(data_list)
    """
    
    # 板块分类映射
    PLATE_MAPPING = {
        "AI": [
            "AI", "人工智能", "大模型", "ChatGPT", "GPT", "深度学习",
            "机器学习", "神经网络", "自然语言处理", "NLP", "计算机视觉",
            "语音识别", "图像识别", "智能算法"
        ],
        "算力": [
            "算力", "GPU", "芯片", "服务器", "数据中心", "云计算",
            "高性能计算", "HPC", "超算", "计算集群", "算力网络",
            "智算中心", "算力基础设施"
        ],
        "半导体": [
            "半导体", "芯片", "集成电路", "晶圆", "光刻机", "EDA",
            "芯片设计", "芯片制造", "封装测试", "晶圆厂", "fab",
            "制程", "工艺", "芯片产业链", "IC"
        ],
        "机器人": [
            "机器人", "自动化", "工业机器人", "服务机器人", "协作机器人",
            "机械臂", "AGV", "无人驾驶", "自动驾驶", "智能制造",
            "工业4.0", "智能工厂", "机器人产业"
        ]
    }
    
    def __init__(self, logger: logging.Logger):
        """
        初始化关键词提取器
        
        Args:
            logger: 日志记录器
        """
        self.logger = logger
        
        # 关键词历史记录：{keyword: [(timestamp, count), ...]}
        self.keyword_history: Dict[str, List[Tuple[datetime, int]]] = defaultdict(list)
        
        # 构建反向索引：keyword -> [plates]
        self._build_reverse_index()
        
        self.logger.info("关键词提取器初始化完成")
        self.logger.debug(
            f"板块映射: {', '.join(self.PLATE_MAPPING.keys())}, "
            f"共 {sum(len(keywords) for keywords in self.PLATE_MAPPING.values())} 个关键词"
        )
    
    def _build_reverse_index(self):
        """
        构建反向索引：keyword -> [plates]
        
        用于快速查找关键词所属的板块。
        """
        self.keyword_to_plates: Dict[str, List[str]] = {}
        
        for plate, keywords in self.PLATE_MAPPING.items():
            for keyword in keywords:
                if keyword not in self.keyword_to_plates:
                    self.keyword_to_plates[keyword] = []
                self.keyword_to_plates[keyword].append(plate)
        
        self.logger.debug(
            f"反向索引构建完成，共 {len(self.keyword_to_plates)} 个关键词"
        )
    
    def extract_keywords(
        self, 
        text: str, 
        top_n: int = 10,
        min_length: int = 2
    ) -> List[str]:
        """
        从文本中提取关键词
        
        实现策略：
        1. 使用板块映射中的关键词进行匹配
        2. 按出现频率排序
        3. 返回前 N 个关键词
        
        Args:
            text: 输入文本
            top_n: 返回前 N 个关键词，默认 10
            min_length: 关键词最小长度，默认 2
        
        Returns:
            关键词列表（按频率降序排序）
        
        示例:
            >>> text = "AI芯片和半导体技术在数据中心的应用"
            >>> keywords = extractor.extract_keywords(text, top_n=5)
            >>> print(keywords)
            ['AI', '芯片', '半导体', '数据中心', '技术']
        """
        if not text:
            self.logger.debug("输入文本为空，返回空列表")
            return []
        
        # 统计关键词出现次数
        keyword_counts = Counter()
        
        # 遍历所有板块的关键词
        for plate, keywords in self.PLATE_MAPPING.items():
            for keyword in keywords:
                # 跳过过短的关键词
                if len(keyword) < min_length:
                    continue
                
                # 统计关键词在文本中出现的次数
                count = text.count(keyword)
                if count > 0:
                    keyword_counts[keyword] += count
        
        # 获取前 N 个高频关键词
        top_keywords = [
            keyword for keyword, count in keyword_counts.most_common(top_n)
        ]
        
        self.logger.debug(
            f"从文本中提取到 {len(top_keywords)} 个关键词: "
            f"{', '.join(top_keywords[:5])}{'...' if len(top_keywords) > 5 else ''}"
        )
        
        return top_keywords
    
    def classify_plate(self, keywords: List[str]) -> List[str]:
        """
        根据关键词分类到板块
        
        Args:
            keywords: 关键词列表
        
        Returns:
            板块列表（去重）
        
        示例:
            >>> keywords = ["AI", "芯片", "半导体", "GPU"]
            >>> plates = extractor.classify_plate(keywords)
            >>> print(plates)
            ['AI', '算力', '半导体']
        """
        if not keywords:
            self.logger.debug("关键词列表为空，返回空板块列表")
            return []
        
        # 收集所有匹配的板块
        plates: Set[str] = set()
        
        for keyword in keywords:
            if keyword in self.keyword_to_plates:
                plates.update(self.keyword_to_plates[keyword])
        
        plate_list = sorted(plates)
        
        self.logger.debug(
            f"关键词 {keywords[:3]}{'...' if len(keywords) > 3 else ''} "
            f"分类到板块: {', '.join(plate_list)}"
        )
        
        return plate_list
    
    def generate_statistics(
        self, 
        data_list: List[Dict[str, Any]],
        time_window_hours: int = 1,
        high_frequency_threshold: int = 5
    ) -> Dict[str, Any]:
        """
        生成关键词频率统计
        
        Args:
            data_list: 数据列表，每条数据应包含 title、content、publish_time 字段
            time_window_hours: 时间窗口（小时），用于高频主题识别，默认 1 小时
            high_frequency_threshold: 高频阈值，默认 5 次
        
        Returns:
            统计结果字典：
            {
                "total_count": int,  # 总数据条数
                "keyword_frequency": Dict[str, int],  # 关键词频率
                "high_frequency_topics": List[str],  # 高频主题（每小时出现 > 5 次）
                "plate_distribution": Dict[str, int],  # 板块分布
                "time_range": {  # 时间范围
                    "start": str,
                    "end": str
                },
                "top_keywords": List[Tuple[str, int]]  # 前 20 个高频关键词
            }
        
        示例:
            >>> data_list = [
            ...     {
            ...         "title": "AI芯片新突破",
            ...         "content": "...",
            ...         "publish_time": "2024-01-15T10:00:00Z"
            ...     },
            ...     # ... 更多数据
            ... ]
            >>> stats = extractor.generate_statistics(data_list)
            >>> print(f"总数据: {stats['total_count']}")
            >>> print(f"高频主题: {stats['high_frequency_topics']}")
        """
        if not data_list:
            self.logger.warning("数据列表为空，返回空统计结果")
            return {
                "total_count": 0,
                "keyword_frequency": {},
                "high_frequency_topics": [],
                "plate_distribution": {},
                "time_range": {"start": None, "end": None},
                "top_keywords": []
            }
        
        self.logger.info(f"开始生成统计信息，数据条数: {len(data_list)}")
        
        # 统计关键词频率
        keyword_counter = Counter()
        plate_counter = Counter()
        
        # 时间范围
        timestamps = []
        
        # 遍历所有数据
        for data in data_list:
            # 提取文本
            text = ""
            if "title" in data:
                text += data["title"] + " "
            if "content" in data:
                text += data["content"]
            
            # 提取关键词
            keywords = self.extract_keywords(text, top_n=20)
            keyword_counter.update(keywords)
            
            # 分类到板块
            plates = self.classify_plate(keywords)
            plate_counter.update(plates)
            
            # 记录时间戳
            if "publish_time" in data:
                try:
                    timestamp = self._parse_timestamp(data["publish_time"])
                    timestamps.append(timestamp)
                except Exception as e:
                    self.logger.debug(f"解析时间戳失败: {e}")
        
        # 计算时间范围
        time_range = {
            "start": min(timestamps).isoformat() if timestamps else None,
            "end": max(timestamps).isoformat() if timestamps else None
        }
        
        # 识别高频主题
        high_frequency_topics = self._identify_high_frequency_topics(
            keyword_counter,
            timestamps,
            time_window_hours,
            high_frequency_threshold
        )
        
        # 构建统计结果
        statistics = {
            "total_count": len(data_list),
            "keyword_frequency": dict(keyword_counter),
            "high_frequency_topics": high_frequency_topics,
            "plate_distribution": dict(plate_counter),
            "time_range": time_range,
            "top_keywords": keyword_counter.most_common(20)
        }
        
        self.logger.info(
            f"统计信息生成完成: "
            f"总数据 {statistics['total_count']} 条, "
            f"关键词 {len(statistics['keyword_frequency'])} 个, "
            f"高频主题 {len(statistics['high_frequency_topics'])} 个, "
            f"板块 {len(statistics['plate_distribution'])} 个"
        )
        
        return statistics
    
    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """
        解析时间戳字符串
        
        支持多种格式：
        - ISO 8601: 2024-01-15T10:00:00Z
        - 中文格式: 2024年01月15日 10:00:00
        - 简单格式: 2024-01-15 10:00:00
        
        Args:
            timestamp_str: 时间戳字符串
        
        Returns:
            datetime 对象
        
        Raises:
            ValueError: 无法解析时间戳
        """
        # 尝试 ISO 8601 格式
        try:
            # 移除 Z 后缀
            if timestamp_str.endswith('Z'):
                timestamp_str = timestamp_str[:-1]
            return datetime.fromisoformat(timestamp_str)
        except ValueError:
            pass
        
        # 尝试简单格式
        try:
            return datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
        
        # 尝试中文格式
        try:
            # 移除中文字符
            cleaned = re.sub(r'[年月日]', '-', timestamp_str)
            cleaned = cleaned.replace('时', ':').replace('分', ':').replace('秒', '')
            return datetime.strptime(cleaned, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass
        
        raise ValueError(f"无法解析时间戳: {timestamp_str}")
    
    def _identify_high_frequency_topics(
        self,
        keyword_counter: Counter,
        timestamps: List[datetime],
        time_window_hours: int,
        threshold: int
    ) -> List[str]:
        """
        识别高频主题
        
        高频主题定义：在指定时间窗口内出现次数超过阈值的关键词
        
        Args:
            keyword_counter: 关键词计数器
            timestamps: 时间戳列表
            time_window_hours: 时间窗口（小时）
            threshold: 频率阈值
        
        Returns:
            高频主题列表
        """
        if not timestamps:
            self.logger.debug("没有时间戳数据，无法识别高频主题")
            return []
        
        # 计算时间范围
        start_time = min(timestamps)
        end_time = max(timestamps)
        time_span_hours = (end_time - start_time).total_seconds() / 3600
        
        # 如果时间跨度小于时间窗口，直接使用总频率
        if time_span_hours <= time_window_hours:
            high_frequency_topics = [
                keyword for keyword, count in keyword_counter.items()
                if count > threshold
            ]
        else:
            # 计算每小时平均频率
            hours = max(1, time_span_hours)
            high_frequency_topics = [
                keyword for keyword, count in keyword_counter.items()
                if (count / hours) * time_window_hours > threshold
            ]
        
        self.logger.info(
            f"识别到 {len(high_frequency_topics)} 个高频主题 "
            f"(时间窗口: {time_window_hours}小时, 阈值: {threshold}次): "
            f"{', '.join(high_frequency_topics[:5])}{'...' if len(high_frequency_topics) > 5 else ''}"
        )
        
        return sorted(high_frequency_topics)
    
    def analyze_text(self, text: str) -> Dict[str, Any]:
        """
        分析单个文本，提取关键词和板块
        
        这是一个便捷方法，组合了 extract_keywords 和 classify_plate。
        
        Args:
            text: 输入文本
        
        Returns:
            分析结果：
            {
                "keywords": List[str],  # 关键词列表
                "plates": List[str],    # 板块列表
                "keyword_count": int    # 关键词数量
            }
        
        示例:
            >>> text = "AI芯片和半导体技术在数据中心的应用"
            >>> result = extractor.analyze_text(text)
            >>> print(result)
            {
                "keywords": ["AI", "芯片", "半导体", "数据中心"],
                "plates": ["AI", "算力", "半导体"],
                "keyword_count": 4
            }
        """
        keywords = self.extract_keywords(text)
        plates = self.classify_plate(keywords)
        
        return {
            "keywords": keywords,
            "plates": plates,
            "keyword_count": len(keywords)
        }
    
    def batch_analyze(
        self, 
        data_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        批量分析数据，为每条数据添加关键词和板块信息
        
        Args:
            data_list: 数据列表
        
        Returns:
            增强后的数据列表（添加了 keywords 和 plates 字段）
        
        示例:
            >>> data_list = [
            ...     {"title": "AI新闻", "content": "..."},
            ...     {"title": "半导体行业", "content": "..."}
            ... ]
            >>> enhanced_data = extractor.batch_analyze(data_list)
            >>> print(enhanced_data[0]["keywords"])
            ['AI', '新闻']
        """
        self.logger.info(f"开始批量分析，数据条数: {len(data_list)}")
        
        enhanced_data = []
        
        for data in data_list:
            # 提取文本
            text = ""
            if "title" in data:
                text += data["title"] + " "
            if "content" in data:
                text += data["content"]
            
            # 分析文本
            analysis = self.analyze_text(text)
            
            # 添加分析结果到数据
            enhanced_item = data.copy()
            enhanced_item["keywords"] = analysis["keywords"]
            enhanced_item["plates"] = analysis["plates"]
            
            enhanced_data.append(enhanced_item)
        
        self.logger.info(f"批量分析完成，处理 {len(enhanced_data)} 条数据")
        
        return enhanced_data


# ============================================================================
# 便捷函数
# ============================================================================

def create_keyword_extractor(logger: logging.Logger = None) -> KeywordExtractor:
    """
    创建关键词提取器
    
    Args:
        logger: 日志记录器，如果为 None 则自动创建
    
    Returns:
        关键词提取器实例
    
    示例:
        >>> extractor = create_keyword_extractor()
        >>> keywords = extractor.extract_keywords("AI芯片技术")
    """
    # 创建日志记录器（如果未提供）
    if logger is None:
        from utils.logger import get_logger
        logger = get_logger(__name__)
    
    return KeywordExtractor(logger)


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    "KeywordExtractor",
    "create_keyword_extractor",
]
