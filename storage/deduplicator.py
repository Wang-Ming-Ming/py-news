# -*- coding: utf-8 -*-
"""
去重器模块

本模块实现了数据去重功能，用于识别并删除重复的数据条目。
主要特性：
- 使用 SHA256 哈希算法计算数据指纹
- 支持不同数据源的去重逻辑（NDRC/CLS 基于 URL，CNInfo 基于组合键）
- 维护基于哈希的索引以实现快速重复检测
- 支持索引的持久化和加载

需求：4.1, 4.2, 4.3, 4.4, 4.5, 4.6
"""

import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, Set, Any


class Deduplicator:
    """
    数据去重器
    
    使用哈希索引跟踪已见过的数据条目，支持不同数据源的去重策略。
    
    Attributes:
        index_file: 去重索引文件路径
        logger: 日志记录器
        _hash_index: 哈希值集合，用于快速查找
    """
    
    def __init__(self, index_file: str, logger: logging.Logger):
        """
        初始化去重器
        
        Args:
            index_file: 去重索引文件路径（如：data/.dedup_index.json）
            logger: 日志记录器
        """
        self.index_file = index_file
        self.logger = logger
        self._hash_index: Set[str] = set()
        
        # 尝试加载已有的索引
        self.load_index()
        
        self.logger.info(f"去重器初始化完成，已加载 {len(self._hash_index)} 条索引记录")
    
    def _compute_hash(self, data: Dict[str, Any], source: str) -> str:
        """
        计算数据的哈希值
        
        不同数据源使用不同的去重逻辑：
        - NDRC/CLS/东方财富全球快讯: 基于 url 字段计算哈希
        - CNInfo: 基于 stock_code + title + publish_time 组合计算哈希
        
        Args:
            data: 数据字典
            source: 数据源（ndrc/cls/cninfo）
            
        Returns:
            SHA256 哈希值（十六进制字符串）
            
        Raises:
            KeyError: 如果数据缺少必需的字段
        """
        try:
            if source in ["ndrc", "cls", "eastmoney_global"]:
                # 新闻类数据使用 URL 作为唯一标识
                if "url" not in data:
                    raise KeyError(f"数据源 {source} 缺少必需的 'url' 字段")
                
                unique_key = data["url"]
                
            elif source == "cninfo":
                # CNInfo 使用股票代码 + 标题 + 发布时间的组合
                required_fields = ["stock_code", "title", "publish_time"]
                missing_fields = [f for f in required_fields if f not in data]
                
                if missing_fields:
                    raise KeyError(
                        f"数据源 {source} 缺少必需的字段: {', '.join(missing_fields)}"
                    )
                
                # 组合三个字段作为唯一标识
                unique_key = f"{data['stock_code']}|{data['title']}|{data['publish_time']}"
                
            else:
                # 未知数据源，记录警告并使用所有字段的 JSON 字符串
                self.logger.warning(f"未知的数据源: {source}，使用默认去重策略")
                unique_key = json.dumps(data, sort_keys=True, ensure_ascii=False)
            
            # 计算 SHA256 哈希
            hash_obj = hashlib.sha256(unique_key.encode('utf-8'))
            hash_value = hash_obj.hexdigest()
            
            self.logger.debug(f"计算哈希: source={source}, key={unique_key[:50]}..., hash={hash_value[:16]}...")
            
            return hash_value
            
        except KeyError as e:
            self.logger.error(f"计算哈希失败: {e}")
            raise
        except Exception as e:
            self.logger.error(f"计算哈希时发生未知错误: {e}", exc_info=True)
            raise
    
    def is_duplicate(self, data: Dict[str, Any], source: str) -> bool:
        """
        检查数据是否重复
        
        Args:
            data: 待检查的数据字典
            source: 数据源（ndrc/cls/cninfo）
            
        Returns:
            True 表示数据重复（已存在），False 表示数据不重复（首次出现）
        """
        try:
            hash_value = self._compute_hash(data, source)
            is_dup = hash_value in self._hash_index
            
            if is_dup:
                self.logger.debug(f"检测到重复数据: source={source}, hash={hash_value[:16]}...")
            
            return is_dup
            
        except Exception as e:
            # 如果计算哈希失败，保守处理：认为不重复，允许保存
            self.logger.error(f"检查重复时发生错误，将数据标记为不重复: {e}")
            return False
    
    def mark_as_seen(self, data: Dict[str, Any], source: str):
        """
        将数据标记为已见过（添加到索引）
        
        Args:
            data: 数据字典
            source: 数据源（ndrc/cls/cninfo）
        """
        try:
            hash_value = self._compute_hash(data, source)
            
            # 添加到索引
            if hash_value not in self._hash_index:
                self._hash_index.add(hash_value)
                self.logger.debug(f"标记数据为已见: source={source}, hash={hash_value[:16]}...")
            
        except Exception as e:
            self.logger.error(f"标记数据为已见时发生错误: {e}", exc_info=True)
    
    def save_index(self):
        """
        将去重索引持久化到磁盘
        
        索引以 JSON 格式保存，包含所有哈希值的列表。
        使用临时文件 + 原子重命名确保写入安全。
        """
        try:
            # 确保目录存在
            index_path = Path(self.index_file)
            index_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 将集合转换为列表以便 JSON 序列化
            index_data = {
                "version": "1.0",
                "count": len(self._hash_index),
                "hashes": list(self._hash_index)
            }
            
            # 写入临时文件
            temp_file = f"{self.index_file}.tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(index_data, f, ensure_ascii=False, indent=2)
            
            # 原子重命名（确保写入安全）
            Path(temp_file).replace(index_path)
            
            self.logger.info(f"去重索引已保存: {self.index_file}, 共 {len(self._hash_index)} 条记录")
            
        except Exception as e:
            self.logger.error(f"保存去重索引失败: {e}", exc_info=True)
            # 清理临时文件
            try:
                temp_file_path = Path(f"{self.index_file}.tmp")
                if temp_file_path.exists():
                    temp_file_path.unlink()
            except Exception:
                pass
    
    def load_index(self):
        """
        从磁盘加载去重索引
        
        如果索引文件不存在或加载失败，将使用空索引。
        """
        try:
            index_path = Path(self.index_file)
            
            if not index_path.exists():
                self.logger.info(f"去重索引文件不存在，将创建新索引: {self.index_file}")
                self._hash_index = set()
                return
            
            # 读取索引文件
            with open(self.index_file, 'r', encoding='utf-8') as f:
                index_data = json.load(f)
            
            # 验证索引格式
            if not isinstance(index_data, dict) or "hashes" not in index_data:
                self.logger.warning(f"去重索引格式无效，将创建新索引")
                self._hash_index = set()
                return
            
            # 加载哈希列表
            hashes = index_data.get("hashes", [])
            self._hash_index = set(hashes)
            
            version = index_data.get("version", "unknown")
            count = index_data.get("count", len(hashes))
            
            self.logger.info(
                f"去重索引加载成功: version={version}, "
                f"count={count}, actual_loaded={len(self._hash_index)}"
            )
            
            # 验证计数一致性
            if count != len(self._hash_index):
                self.logger.warning(
                    f"索引计数不一致: 声明={count}, 实际={len(self._hash_index)}"
                )
            
        except json.JSONDecodeError as e:
            self.logger.error(f"去重索引文件格式错误: {e}")
            self._hash_index = set()
            
        except Exception as e:
            self.logger.error(f"加载去重索引失败: {e}", exc_info=True)
            self._hash_index = set()
    
    def get_index_size(self) -> int:
        """
        获取索引中的记录数量
        
        Returns:
            索引中的哈希值数量
        """
        return len(self._hash_index)
    
    def clear_index(self):
        """
        清空索引（谨慎使用）
        
        此操作会清空内存中的索引，但不会删除磁盘上的索引文件。
        需要调用 save_index() 才能将清空操作持久化。
        """
        self.logger.warning("清空去重索引")
        self._hash_index.clear()
    
    def __del__(self):
        """
        析构函数：在对象销毁时自动保存索引
        """
        try:
            if hasattr(self, '_hash_index') and self._hash_index:
                self.save_index()
        except Exception:
            # 忽略析构时的错误
            pass


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    "Deduplicator",
]
