"""
数据模型定义模块

本模块定义了金融数据采集系统使用的所有数据模型。
每个模型都使用 dataclass 装饰器，并提供 to_dict() 和 from_dict() 方法用于序列化和反序列化。
"""

from typing import List, Dict, Any
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class NDRCNews:
    """发改委新闻数据模型
    
    用于存储从国家发展和改革委员会网站采集的政策新闻数据。
    
    Attributes:
        source: 数据源标识，固定为 "ndrc"
        title: 新闻标题
        publish_time: 发布时间，ISO 8601 格式（如：2024-01-15T10:30:00Z）
        content: 新闻正文内容
        url: 新闻详情页面 URL
        tags: 新闻标签列表
    """
    title: str
    publish_time: str
    content: str
    url: str
    tags: List[str] = field(default_factory=list)
    source: str = "ndrc"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式
        
        Returns:
            包含所有字段的字典
        """
        return {
            "source": self.source,
            "title": self.title,
            "publish_time": self.publish_time,
            "content": self.content,
            "url": self.url,
            "tags": self.tags
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NDRCNews':
        """从字典创建实例
        
        Args:
            data: 包含新闻数据的字典
            
        Returns:
            NDRCNews 实例
        """
        return cls(
            title=data["title"],
            publish_time=data["publish_time"],
            content=data["content"],
            url=data["url"],
            tags=data.get("tags", [])
        )


@dataclass
class CLSNews:
    """证券报新闻数据模型
    
    用于存储从中国证券报网站采集的热点新闻数据。
    
    Attributes:
        source: 数据源标识，固定为 "cls"
        title: 新闻标题
        publish_time: 发布时间，ISO 8601 格式
        content: 新闻正文内容
        tags: 新闻标签列表
        plate: 相关板块列表（如：AI、算力、半导体等）
        level: 新闻级别（如：重要、一般）
    """
    title: str
    publish_time: str
    content: str
    tags: List[str] = field(default_factory=list)
    plate: List[str] = field(default_factory=list)
    level: str = ""
    source: str = "cls"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式
        
        Returns:
            包含所有字段的字典
        """
        return {
            "source": self.source,
            "title": self.title,
            "publish_time": self.publish_time,
            "content": self.content,
            "tags": self.tags,
            "plate": self.plate,
            "level": self.level
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CLSNews':
        """从字典创建实例
        
        Args:
            data: 包含新闻数据的字典
            
        Returns:
            CLSNews 实例
        """
        return cls(
            title=data["title"],
            publish_time=data["publish_time"],
            content=data["content"],
            tags=data.get("tags", []),
            plate=data.get("plate", []),
            level=data.get("level", "")
        )


@dataclass
class CNInfoAnnouncement:
    """证券信息网公告数据模型
    
    用于存储从中国证券信息网采集的公司公告数据。
    
    Attributes:
        source: 数据源标识，固定为 "cninfo"
        stock_code: 股票代码（如：000001）
        stock_name: 股票名称
        title: 公告标题
        publish_time: 发布时间，ISO 8601 格式
        announcement_type: 公告类型（如：年度报告、重大事项等）
        url: 公告详情页面或 PDF 文件 URL
        keywords: 关键词列表
    """
    stock_code: str
    stock_name: str
    title: str
    publish_time: str
    announcement_type: str
    url: str
    keywords: List[str] = field(default_factory=list)
    source: str = "cninfo"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式
        
        Returns:
            包含所有字段的字典
        """
        return {
            "source": self.source,
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "title": self.title,
            "publish_time": self.publish_time,
            "announcement_type": self.announcement_type,
            "url": self.url,
            "keywords": self.keywords
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CNInfoAnnouncement':
        """从字典创建实例
        
        Args:
            data: 包含公告数据的字典
            
        Returns:
            CNInfoAnnouncement 实例
        """
        return cls(
            stock_code=data["stock_code"],
            stock_name=data["stock_name"],
            title=data["title"],
            publish_time=data["publish_time"],
            announcement_type=data["announcement_type"],
            url=data["url"],
            keywords=data.get("keywords", [])
        )


@dataclass
class CollectionStatistics:
    """采集统计数据模型
    
    用于记录每次数据采集的统计信息，包括采集数量、过滤数量、错误信息等。
    
    Attributes:
        source: 数据源标识（ndrc/cls/cninfo）
        start_time: 采集开始时间
        end_time: 采集结束时间
        total_fetched: 总共获取的条目数
        filtered_count: 被关键词过滤掉的条目数
        duplicate_count: 检测到的重复条目数
        saved_count: 成功保存的条目数
        error_count: 遇到的错误数
        errors: 错误详情列表，每个错误包含 type、message、url 等信息
    """
    source: str
    start_time: datetime
    end_time: datetime
    total_fetched: int = 0
    filtered_count: int = 0
    duplicate_count: int = 0
    saved_count: int = 0
    error_count: int = 0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式
        
        Returns:
            包含所有字段的字典，包括计算的持续时间
        """
        return {
            "source": self.source,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat(),
            "duration_seconds": (self.end_time - self.start_time).total_seconds(),
            "total_fetched": self.total_fetched,
            "filtered_count": self.filtered_count,
            "duplicate_count": self.duplicate_count,
            "saved_count": self.saved_count,
            "error_count": self.error_count,
            "errors": self.errors
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CollectionStatistics':
        """从字典创建实例
        
        Args:
            data: 包含统计数据的字典
            
        Returns:
            CollectionStatistics 实例
        """
        return cls(
            source=data["source"],
            start_time=datetime.fromisoformat(data["start_time"]),
            end_time=datetime.fromisoformat(data["end_time"]),
            total_fetched=data.get("total_fetched", 0),
            filtered_count=data.get("filtered_count", 0),
            duplicate_count=data.get("duplicate_count", 0),
            saved_count=data.get("saved_count", 0),
            error_count=data.get("error_count", 0),
            errors=data.get("errors", [])
        )
