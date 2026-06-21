# -*- coding: utf-8 -*-
"""
存储管理器模块

本模块实现了数据存储管理功能，负责数据的持久化和检索。
主要特性：
- 按数据源和日期组织 JSON 文件（data/{source}/{YYYY-MM-DD}.json）
- 支持单条和批量数据保存
- 使用原子写入操作确保数据安全
- 支持按数据源、日期范围、关键词查询数据
- 检查磁盘空间并在空间不足时发出警告

需求：7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7
"""

import json
import logging
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

from filters.news_normalizer import normalize_news_item
from utils.exceptions import DiskFullException


class StorageManager:
    """
    数据存储管理器
    
    管理 JSON 文件的读写，按数据源和日期组织文件结构。
    
    Attributes:
        base_path: 数据存储根目录
        logger: 日志记录器
        min_disk_space: 最小磁盘空间要求（字节）
    """
    
    def __init__(self, base_path: str, logger: logging.Logger, min_disk_space: int = 1 * 1024 * 1024 * 1024):
        """
        初始化存储管理器
        
        Args:
            base_path: 数据存储根目录（如：./data）
            logger: 日志记录器
            min_disk_space: 最小磁盘空间要求（字节），默认 1GB
        """
        self.base_path = base_path
        self.logger = logger
        self.min_disk_space = min_disk_space
        
        # 确保基础目录存在
        Path(self.base_path).mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"存储管理器初始化完成，数据目录: {self.base_path}")

    def _get_unique_key(self, data: Dict[str, Any], source: str) -> str:
        """
        生成本地文件内去重键，防止同一条新闻被重复写入 JSON 文件。
        """
        if source == "cninfo":
            return "|".join(str(data.get(field, "")) for field in ("stock_code", "title", "publish_time"))

        if data.get("url"):
            return str(data["url"])

        return "|".join(str(data.get(field, "")) for field in ("title", "publish_time"))

    def _prepare_for_storage(self, data: Dict[str, Any], source: str) -> Dict[str, Any]:
        """
        保存前只补充客观时间和采集来源字段，不生成分析标签。
        """
        return normalize_news_item(data, source)

    def _merge_duplicate(self, existing: Dict[str, Any], incoming: Dict[str, Any]) -> bool:
        def url_list(item: Dict[str, Any]) -> List[str]:
            values = item.get("source_urls")
            return [str(value) for value in values] if isinstance(values, list) else []

        urls = list(
            dict.fromkeys(
                str(value)
                for value in [
                    *url_list(existing),
                    existing.get("url"),
                    *url_list(incoming),
                    incoming.get("url"),
                ]
                if value
            )
        )
        changed = urls != url_list(existing)
        if changed:
            existing["source_urls"] = urls
        existing_collected = str(existing.get("collected_at") or existing.get("crawled_at") or "")
        incoming_collected = str(incoming.get("collected_at") or incoming.get("crawled_at") or "")
        if incoming_collected and (not existing_collected or incoming_collected < existing_collected):
            existing["collected_at"] = incoming_collected
            existing["crawled_at"] = incoming_collected
            changed = True
        return changed

    def _get_date_key(self, data: Dict[str, Any], source: str) -> str:
        """
        获取数据归档日期，优先使用标准化后的北京时间日期。
        """
        publish_date_bj = str(data.get("publish_date_bj") or "").strip()
        if publish_date_bj:
            try:
                datetime.strptime(publish_date_bj, "%Y-%m-%d")
                return publish_date_bj
            except ValueError:
                self.logger.warning(f"北京时间日期格式异常，使用发布时间兜底: {publish_date_bj}")

        publish_time_str = data.get("publish_time", "")
        if publish_time_str:
            try:
                publish_time = datetime.fromisoformat(str(publish_time_str).replace('Z', '+00:00'))
                return publish_time.strftime("%Y-%m-%d")
            except (ValueError, AttributeError) as e:
                self.logger.warning(f"无法解析发布时间，使用当前日期: {publish_time_str}, 错误: {e}")

        return datetime.now().strftime("%Y-%m-%d")
    
    def _get_file_path(self, source: str, date: datetime) -> str:
        """
        获取数据文件路径
        
        文件按数据源和日期组织：{base_path}/{source}/{YYYY-MM-DD}.json
        
        Args:
            source: 数据源（ndrc/cls/cninfo）
            date: 日期
            
        Returns:
            文件路径字符串
        """
        # 格式化日期为 YYYY-MM-DD
        date_str = date.strftime("%Y-%m-%d")
        
        # 构建文件路径
        file_path = os.path.join(self.base_path, source, f"{date_str}.json")
        
        return file_path
    
    def save(self, data: Dict[str, Any], source: str):
        """
        保存单条数据
        
        实现逻辑：
        1. 确定文件路径（基于当前日期）
        2. 如果文件不存在，创建新文件
        3. 使用原子写入操作追加数据
        4. 检查磁盘空间
        
        Args:
            data: 数据字典
            source: 数据源（ndrc/cls/cninfo）
            
        Raises:
            IOError: 磁盘空间不足或写入失败
        """
        try:
            data = self._prepare_for_storage(data, source)

            # 检查磁盘空间
            available_space = self.check_disk_space()
            if available_space < self.min_disk_space:
                warning_msg = (
                    f"磁盘空间不足！可用空间: {available_space / (1024**3):.2f} GB, "
                    f"最小要求: {self.min_disk_space / (1024**3):.2f} GB"
                )
                self.logger.warning(warning_msg)
                raise DiskFullException(
                    warning_msg,
                    available_space=available_space,
                    required_space=self.min_disk_space,
                )
            
            # 获取文件路径（使用北京时间归档日期）
            date_key = self._get_date_key(data, source)
            current_date = datetime.strptime(date_key, "%Y-%m-%d")
            file_path = self._get_file_path(source, current_date)
            
            # 确保目录存在
            Path(file_path).parent.mkdir(parents=True, exist_ok=True)
            
            # 读取现有数据（如果文件存在）
            existing_data = []
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        existing_data = json.load(f)
                    
                    # 确保是列表格式
                    if not isinstance(existing_data, list):
                        self.logger.warning(f"文件格式异常，将重新创建: {file_path}")
                        existing_data = []
                        
                except json.JSONDecodeError as e:
                    self.logger.error(f"文件 JSON 格式错误，将重新创建: {file_path}, 错误: {e}")
                    existing_data = []
            
            existing_keys = {self._get_unique_key(item, source) for item in existing_data if isinstance(item, dict)}
            data_key = self._get_unique_key(data, source)
            if data_key in existing_keys:
                for existing in existing_data:
                    if isinstance(existing, dict) and self._get_unique_key(existing, source) == data_key:
                        if self._merge_duplicate(existing, data):
                            self._atomic_write(file_path, existing_data)
                        break
                self.logger.debug(f"数据已存在，跳过保存: source={source}, key={data_key[:80]}")
                return False

            # 追加新数据
            existing_data.append(data)
            
            # 原子写入
            self._atomic_write(file_path, existing_data)
            
            self.logger.debug(f"数据已保存: source={source}, file={file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存数据失败: source={source}, 错误: {e}", exc_info=True)
            raise
    
    def batch_save(self, data_list: List[Dict[str, Any]], source: str):
        """
        批量保存数据
        
        Args:
            data_list: 数据列表
            source: 数据源（ndrc/cls/cninfo）
            
        Raises:
            IOError: 磁盘空间不足或写入失败
        """
        if not data_list:
            self.logger.debug(f"批量保存：数据列表为空，跳过保存")
            return
        
        try:
            # 检查磁盘空间
            available_space = self.check_disk_space()
            if available_space < self.min_disk_space:
                warning_msg = (
                    f"磁盘空间不足！可用空间: {available_space / (1024**3):.2f} GB, "
                    f"最小要求: {self.min_disk_space / (1024**3):.2f} GB"
                )
                self.logger.warning(warning_msg)
                raise DiskFullException(
                    warning_msg,
                    available_space=available_space,
                    required_space=self.min_disk_space,
                )
            
            prepared_list = [self._prepare_for_storage(data, source) for data in data_list]

            # 按北京时间日期分组数据
            data_by_date: Dict[str, List[Dict[str, Any]]] = {}
            
            for data in prepared_list:
                date_key = self._get_date_key(data, source)
                
                if date_key not in data_by_date:
                    data_by_date[date_key] = []
                
                data_by_date[date_key].append(data)
            
            # 按日期保存数据
            total_saved = 0
            for date_str, date_data in data_by_date.items():
                try:
                    # 解析日期字符串
                    date = datetime.strptime(date_str, "%Y-%m-%d")
                    file_path = self._get_file_path(source, date)
                    
                    # 确保目录存在
                    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
                    
                    # 读取现有数据
                    existing_data = []
                    if os.path.exists(file_path):
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                existing_data = json.load(f)
                            
                            if not isinstance(existing_data, list):
                                self.logger.warning(f"文件格式异常，将重新创建: {file_path}")
                                existing_data = []
                                
                        except json.JSONDecodeError as e:
                            self.logger.error(f"文件 JSON 格式错误，将重新创建: {file_path}, 错误: {e}")
                            existing_data = []
                    
                    existing_keys = {
                        self._get_unique_key(item, source)
                        for item in existing_data
                        if isinstance(item, dict)
                    }
                    merged_data = list(existing_data)
                    date_saved = 0
                    for item in date_data:
                        item_key = self._get_unique_key(item, source)
                        if item_key in existing_keys:
                            for existing in merged_data:
                                if isinstance(existing, dict) and self._get_unique_key(existing, source) == item_key:
                                    self._merge_duplicate(existing, item)
                                    break
                            continue
                        existing_keys.add(item_key)
                        merged_data.append(item)
                        date_saved += 1
                    
                    # 原子写入
                    self._atomic_write(file_path, merged_data)
                    
                    total_saved += date_saved
                    self.logger.debug(
                        f"批量保存: source={source}, date={date_str}, "
                        f"incoming={len(date_data)}, saved={date_saved}"
                    )
                    
                except Exception as e:
                    self.logger.error(f"保存日期数据失败: date={date_str}, 错误: {e}", exc_info=True)
                    # 继续处理其他日期的数据
                    continue
            
            self.logger.info(f"批量保存完成: source={source}, total={len(data_list)}, saved={total_saved}")
            
        except Exception as e:
            self.logger.error(f"批量保存失败: source={source}, 错误: {e}", exc_info=True)
            raise
    
    def _atomic_write(self, file_path: str, data: List[Dict[str, Any]]):
        """
        原子写入操作
        
        使用临时文件 + os.rename() 确保写入安全，避免数据损坏。
        
        实现逻辑：
        1. 写入临时文件
        2. 使用 os.rename() 原子替换
        
        Args:
            file_path: 目标文件路径
            data: 要写入的数据列表
            
        Raises:
            IOError: 写入失败
        """
        try:
            # 创建临时文件（在同一目录下，确保在同一文件系统）
            temp_file = f"{file_path}.tmp"
            
            # 写入临时文件
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # 原子重命名（在同一文件系统上，rename 是原子操作）
            os.replace(temp_file, file_path)
            
            self.logger.debug(f"原子写入成功: {file_path}, 数据条数: {len(data)}")
            
        except Exception as e:
            self.logger.error(f"原子写入失败: {file_path}, 错误: {e}", exc_info=True)
            
            # 清理临时文件
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            except Exception:
                pass
            
            raise
    
    def check_disk_space(self) -> int:
        """
        检查磁盘可用空间
        
        Returns:
            可用空间（字节）
        """
        try:
            # 获取磁盘使用情况
            stat = shutil.disk_usage(self.base_path)
            available_space = stat.free
            
            self.logger.debug(
                f"磁盘空间: 总计={stat.total / (1024**3):.2f} GB, "
                f"已用={stat.used / (1024**3):.2f} GB, "
                f"可用={available_space / (1024**3):.2f} GB"
            )
            
            return available_space
            
        except Exception as e:
            self.logger.error(f"检查磁盘空间失败: {e}", exc_info=True)
            # 返回一个大值，避免因检查失败而阻止保存
            return self.min_disk_space * 10

    def cleanup_old_files(self, retention_days: int):
        """
        删除超过保留天数的数据文件。
        """
        if retention_days <= 0:
            return

        cutoff_date = (datetime.now() - timedelta(days=retention_days)).date()
        removed_count = 0

        base_path = Path(self.base_path)
        if not base_path.exists():
            return

        for source_dir in base_path.iterdir():
            if not source_dir.is_dir():
                continue

            for file_path in source_dir.glob("*.json"):
                try:
                    file_date = datetime.strptime(file_path.stem, "%Y-%m-%d").date()
                except ValueError:
                    continue

                if file_date < cutoff_date:
                    file_path.unlink()
                    removed_count += 1

        if removed_count:
            self.logger.info(f"已清理 {removed_count} 个超过 {retention_days} 天的数据文件")
    
    def query(
        self,
        source: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        keywords: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        查询数据
        
        支持按数据源、日期范围、关键词过滤数据。
        
        Args:
            source: 数据源过滤（可选），如果为 None 则查询所有数据源
            start_date: 开始日期（可选），如果为 None 则不限制开始日期
            end_date: 结束日期（可选），如果为 None 则不限制结束日期
            keywords: 关键词过滤（可选），如果为 None 则不过滤关键词
            
        Returns:
            符合条件的数据列表
        """
        try:
            results = []
            
            # 确定要查询的数据源
            if source:
                sources = [source]
            else:
                # 查询所有数据源
                sources = []
                base_path = Path(self.base_path)
                if base_path.exists():
                    sources = [d.name for d in base_path.iterdir() if d.is_dir()]
            
            self.logger.debug(f"查询数据源: {sources}")
            
            # 遍历每个数据源
            for src in sources:
                source_path = Path(self.base_path) / src
                
                if not source_path.exists():
                    self.logger.debug(f"数据源目录不存在: {source_path}")
                    continue
                
                # 遍历该数据源下的所有 JSON 文件
                for file_path in source_path.glob("*.json"):
                    try:
                        # 从文件名提取日期
                        file_date_str = file_path.stem  # 获取不带扩展名的文件名
                        file_date = datetime.strptime(file_date_str, "%Y-%m-%d")
                        
                        # 检查日期范围
                        if start_date and file_date < start_date:
                            continue
                        
                        if end_date and file_date > end_date:
                            continue
                        
                        # 读取文件内容
                        with open(file_path, 'r', encoding='utf-8') as f:
                            data_list = json.load(f)
                        
                        # 确保是列表格式
                        if not isinstance(data_list, list):
                            self.logger.warning(f"文件格式异常，跳过: {file_path}")
                            continue
                        
                        # 过滤数据
                        for data in data_list:
                            # 关键词过滤
                            if keywords:
                                # 检查标题和内容字段
                                text_fields = []
                                
                                if "title" in data:
                                    text_fields.append(data["title"])
                                
                                if "content" in data:
                                    text_fields.append(data["content"])
                                
                                # 合并所有文本字段
                                combined_text = " ".join(text_fields)
                                
                                # 检查是否包含任一关键词
                                if not any(keyword in combined_text for keyword in keywords):
                                    continue
                            
                            results.append(data)
                        
                    except (ValueError, json.JSONDecodeError) as e:
                        self.logger.warning(f"读取文件失败，跳过: {file_path}, 错误: {e}")
                        continue
                    except Exception as e:
                        self.logger.error(f"处理文件时发生错误: {file_path}, 错误: {e}", exc_info=True)
                        continue
            
            self.logger.info(
                f"查询完成: source={source}, "
                f"start_date={start_date.strftime('%Y-%m-%d') if start_date else 'None'}, "
                f"end_date={end_date.strftime('%Y-%m-%d') if end_date else 'None'}, "
                f"keywords={keywords}, "
                f"结果数量={len(results)}"
            )
            
            return results
            
        except Exception as e:
            self.logger.error(f"查询数据失败: {e}", exc_info=True)
            return []
    
    def get_file_count(self, source: Optional[str] = None) -> int:
        """
        获取文件数量
        
        Args:
            source: 数据源（可选），如果为 None 则统计所有数据源
            
        Returns:
            文件数量
        """
        try:
            count = 0
            
            if source:
                source_path = Path(self.base_path) / source
                if source_path.exists():
                    count = len(list(source_path.glob("*.json")))
            else:
                base_path = Path(self.base_path)
                if base_path.exists():
                    for source_dir in base_path.iterdir():
                        if source_dir.is_dir():
                            count += len(list(source_dir.glob("*.json")))
            
            return count
            
        except Exception as e:
            self.logger.error(f"获取文件数量失败: {e}", exc_info=True)
            return 0
    
    def get_data_count(self, source: Optional[str] = None) -> int:
        """
        获取数据条目总数
        
        Args:
            source: 数据源（可选），如果为 None 则统计所有数据源
            
        Returns:
            数据条目总数
        """
        try:
            count = 0
            
            # 查询所有数据（不过滤）
            data_list = self.query(source=source)
            count = len(data_list)
            
            return count
            
        except Exception as e:
            self.logger.error(f"获取数据数量失败: {e}", exc_info=True)
            return 0


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    "StorageManager",
]
