# -*- coding: utf-8 -*-
"""
增量更新器模块

本模块实现了增量更新跟踪功能，用于记录每个数据源的最后采集时间。
主要特性：
- 跟踪每个数据源的最后采集时间戳
- 计算采集时间范围（从上次采集到现在）
- 如果没有历史记录，默认采集过去 7 天的数据
- 支持状态的持久化和加载

需求：5.1, 5.2, 5.3, 5.4, 5.5
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple, Any


class IncrementalUpdater:
    """
    增量更新跟踪器
    
    跟踪每个数据源的采集进度，实现增量更新功能。
    
    Attributes:
        state_file: 状态文件路径
        logger: 日志记录器
        _state: 状态字典，存储每个数据源的采集信息
    """
    
    def __init__(self, state_file: str, logger: logging.Logger):
        """
        初始化增量更新器
        
        Args:
            state_file: 状态文件路径（如：data/.incremental_state.json）
            logger: 日志记录器
        """
        self.state_file = state_file
        self.logger = logger
        self._state: Dict[str, Dict[str, Any]] = {}
        
        # 尝试加载已有的状态
        self.load_state()
        
        self.logger.info(f"增量更新器初始化完成，已加载 {len(self._state)} 个数据源的状态")
    
    def get_last_update_time(self, source: str) -> Optional[datetime]:
        """
        获取指定数据源的最后更新时间
        
        Args:
            source: 数据源（ndrc/cls/cninfo）
            
        Returns:
            最后更新时间，如果不存在返回 None
        """
        try:
            if source not in self._state:
                self.logger.debug(f"数据源 {source} 没有历史记录")
                return None
            
            last_update_str = self._state[source].get("last_update")
            
            if not last_update_str:
                self.logger.debug(f"数据源 {source} 的 last_update 字段为空")
                return None
            
            # 解析 ISO 8601 格式的时间字符串
            last_update = datetime.fromisoformat(last_update_str.replace('Z', '+00:00'))
            
            # 转换为本地时间（去除时区信息）
            if last_update.tzinfo is not None:
                last_update = last_update.replace(tzinfo=None)
            
            self.logger.debug(f"数据源 {source} 的最后更新时间: {last_update}")
            
            return last_update
            
        except (ValueError, AttributeError) as e:
            self.logger.error(f"解析最后更新时间失败: source={source}, 错误: {e}")
            return None
        except Exception as e:
            self.logger.error(f"获取最后更新时间时发生未知错误: source={source}, 错误: {e}", exc_info=True)
            return None
    
    def set_last_update_time(self, source: str, timestamp: datetime):
        """
        设置指定数据源的最后更新时间
        
        Args:
            source: 数据源（ndrc/cls/cninfo）
            timestamp: 时间戳
        """
        try:
            # 如果数据源不存在，初始化状态
            if source not in self._state:
                self._state[source] = {
                    "last_update": None,
                    "last_success": None,
                    "total_collected": 0
                }
            
            # 转换为 ISO 8601 格式字符串
            timestamp_str = timestamp.isoformat() + 'Z'
            
            # 更新最后更新时间
            self._state[source]["last_update"] = timestamp_str
            self._state[source]["last_success"] = timestamp_str
            
            self.logger.debug(f"设置数据源 {source} 的最后更新时间: {timestamp_str}")
            
        except Exception as e:
            self.logger.error(f"设置最后更新时间失败: source={source}, 错误: {e}", exc_info=True)
    
    def increment_collected_count(self, source: str, count: int = 1):
        """
        增加数据源的采集计数
        
        Args:
            source: 数据源（ndrc/cls/cninfo）
            count: 增加的数量，默认为 1
        """
        try:
            # 如果数据源不存在，初始化状态
            if source not in self._state:
                self._state[source] = {
                    "last_update": None,
                    "last_success": None,
                    "total_collected": 0
                }
            
            # 增加计数
            self._state[source]["total_collected"] = self._state[source].get("total_collected", 0) + count
            
            self.logger.debug(f"数据源 {source} 的采集计数增加 {count}，总计: {self._state[source]['total_collected']}")
            
        except Exception as e:
            self.logger.error(f"增加采集计数失败: source={source}, 错误: {e}", exc_info=True)
    
    def get_time_range(self, source: str, default_days: int = 7) -> Tuple[datetime, datetime]:
        """
        获取采集时间范围
        
        如果有历史记录，返回从最后更新时间到现在的时间范围。
        如果没有历史记录，返回从 default_days 天前到现在的时间范围。
        
        Args:
            source: 数据源（ndrc/cls/cninfo）
            default_days: 如果没有历史记录，默认采集的天数，默认为 7 天
            
        Returns:
            (start_date, end_date) 元组，表示采集时间范围
        """
        try:
            end_date = datetime.now()
            
            # 获取最后更新时间
            last_update = self.get_last_update_time(source)
            
            if last_update:
                # 有历史记录，从最后更新时间开始
                start_date = last_update
                self.logger.info(
                    f"数据源 {source} 使用增量更新: "
                    f"start={start_date.strftime('%Y-%m-%d %H:%M:%S')}, "
                    f"end={end_date.strftime('%Y-%m-%d %H:%M:%S')}"
                )
            else:
                # 没有历史记录，使用默认天数
                start_date = end_date - timedelta(days=default_days)
                self.logger.info(
                    f"数据源 {source} 没有历史记录，采集过去 {default_days} 天的数据: "
                    f"start={start_date.strftime('%Y-%m-%d %H:%M:%S')}, "
                    f"end={end_date.strftime('%Y-%m-%d %H:%M:%S')}"
                )
            
            return (start_date, end_date)
            
        except Exception as e:
            self.logger.error(f"获取时间范围失败: source={source}, 错误: {e}", exc_info=True)
            # 返回默认时间范围
            end_date = datetime.now()
            start_date = end_date - timedelta(days=default_days)
            return (start_date, end_date)
    
    def save_state(self):
        """
        将状态持久化到磁盘
        
        状态以 JSON 格式保存，包含每个数据源的采集信息。
        使用临时文件 + 原子重命名确保写入安全。
        """
        try:
            # 确保目录存在
            state_path = Path(self.state_file)
            state_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 写入临时文件
            temp_file = f"{self.state_file}.tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self._state, f, ensure_ascii=False, indent=2)
            
            # 原子重命名（确保写入安全）
            Path(temp_file).replace(state_path)
            
            self.logger.info(f"增量更新状态已保存: {self.state_file}, 共 {len(self._state)} 个数据源")
            
        except Exception as e:
            self.logger.error(f"保存增量更新状态失败: {e}", exc_info=True)
            # 清理临时文件
            try:
                temp_file_path = Path(f"{self.state_file}.tmp")
                if temp_file_path.exists():
                    temp_file_path.unlink()
            except Exception:
                pass
    
    def load_state(self):
        """
        从磁盘加载状态
        
        如果状态文件不存在或加载失败，将使用空状态。
        """
        try:
            state_path = Path(self.state_file)
            
            if not state_path.exists():
                self.logger.info(f"增量更新状态文件不存在，将创建新状态: {self.state_file}")
                self._state = {}
                return
            
            # 读取状态文件
            with open(self.state_file, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
            
            # 验证状态格式
            if not isinstance(state_data, dict):
                self.logger.warning(f"增量更新状态格式无效，将创建新状态")
                self._state = {}
                return
            
            # 加载状态
            self._state = state_data
            
            self.logger.info(f"增量更新状态加载成功: {len(self._state)} 个数据源")
            
            # 打印每个数据源的状态
            for source, info in self._state.items():
                last_update = info.get("last_update", "未知")
                total_collected = info.get("total_collected", 0)
                self.logger.debug(
                    f"  - {source}: last_update={last_update}, total_collected={total_collected}"
                )
            
        except json.JSONDecodeError as e:
            self.logger.error(f"增量更新状态文件格式错误: {e}")
            self._state = {}
            
        except Exception as e:
            self.logger.error(f"加载增量更新状态失败: {e}", exc_info=True)
            self._state = {}
    
    def get_state_info(self, source: str) -> Optional[Dict[str, Any]]:
        """
        获取指定数据源的完整状态信息
        
        Args:
            source: 数据源（ndrc/cls/cninfo）
            
        Returns:
            状态信息字典，如果不存在返回 None
        """
        return self._state.get(source)
    
    def get_all_sources(self) -> list:
        """
        获取所有已跟踪的数据源列表
        
        Returns:
            数据源名称列表
        """
        return list(self._state.keys())
    
    def reset_source(self, source: str):
        """
        重置指定数据源的状态（谨慎使用）
        
        此操作会清空该数据源的所有状态信息。
        需要调用 save_state() 才能将重置操作持久化。
        
        Args:
            source: 数据源（ndrc/cls/cninfo）
        """
        if source in self._state:
            self.logger.warning(f"重置数据源 {source} 的状态")
            del self._state[source]
        else:
            self.logger.debug(f"数据源 {source} 不存在，无需重置")
    
    def __del__(self):
        """
        析构函数：在对象销毁时自动保存状态
        """
        try:
            if hasattr(self, '_state') and self._state:
                self.save_state()
        except Exception:
            # 忽略析构时的错误
            pass


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    "IncrementalUpdater",
]
