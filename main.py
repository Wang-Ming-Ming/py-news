# -*- coding: utf-8 -*-
"""
金融数据采集系统主程序入口

本模块是金融数据采集系统的主程序入口，负责协调所有组件的初始化和数据采集流程。

主要功能：
- 加载配置文件
- 初始化日志系统
- 初始化所有组件（爬虫、过滤器、去重器、存储管理器、增量更新器）
- 实现数据采集协调逻辑，按顺序执行各爬虫
- 实现数据处理管道：采集 → 解析 → 过滤 → 去重 → 存储
- 记录采集统计信息（总条目数、过滤数、重复数、错误数）
- 实现错误处理，单个爬虫失败不影响其他爬虫
- 使用 FailureTracker 跟踪连续失败，超过 5 次时暂停数据源

需求：8.1, 8.6, 8.7, 10.2, 10.4

使用示例：
    # 运行所有爬虫
    python main.py
    
    # 运行指定爬虫
    python main.py --spiders ndrc cls
    
    # 指定配置文件
    python main.py --config config.py
"""

import sys
import argparse
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# 导入配置
try:
    import config
    from config import (
        NDRC_CONFIG,
        CLS_CONFIG,
        CNINFO_CONFIG,
        STOCK_KEYWORDS,
        CNINFO_KEYWORDS,
        STORAGE_CONFIG,
        LOGGING_CONFIG,
        INCREMENTAL_CONFIG,
        DEDUP_CONFIG,
        ERROR_HANDLING_CONFIG,
        create_directories,
        validate_config
    )
except ImportError as e:
    print(f"错误：无法导入配置文件 config.py: {e}")
    sys.exit(1)

# 导入爬虫
from spiders.ndrc_spider import NDRCSpider
from spiders.cls_spider import CLSSpider
from spiders.cninfo_spider import CNInfoSpider

# 导入解析器
from parsers.ndrc_parser import NDRCParser
from parsers.cls_parser import CLSParser
from parsers.cninfo_parser import CNInfoParser

# 导入过滤器
from filters.keyword_filter import KeywordFilter
from filters.keyword_extractor import KeywordExtractor

# 导入存储组件
from storage.deduplicator import Deduplicator
from storage.storage_manager import StorageManager
from storage.incremental_updater import IncrementalUpdater

# 导入工具
from utils.logger import get_logger, log_statistics
from utils.retry import FailureTracker
from utils.exceptions import DataCollectorException


class DataCollector:
    """
    金融数据采集系统主类
    
    负责协调所有组件，执行完整的数据采集流程。
    
    Attributes:
        logger: 日志记录器
        config: 配置对象
        deduplicator: 去重器
        storage_manager: 存储管理器
        incremental_updater: 增量更新器
        failure_tracker: 失败跟踪器
        spiders: 爬虫字典
        stats: 全局统计信息
    """
    
    def __init__(self, config_module=None, default_days: Optional[int] = None):
        """
        初始化数据采集系统
        
        Args:
            config_module: 配置模块，默认使用全局 config
        """
        # 使用配置模块
        self.config = config_module or config
        self.default_days = default_days
        
        # 创建必要的目录
        create_directories()
        
        # 初始化日志系统
        self.logger = get_logger(__name__)
        self.logger.info("=" * 80)
        self.logger.info("金融数据采集系统启动")
        self.logger.info("=" * 80)
        
        # 验证配置
        is_valid, errors = validate_config()
        if not is_valid:
            self.logger.warning(f"配置验证发现 {len(errors)} 个问题:")
            for error in errors:
                self.logger.warning(f"  - {error}")
        
        # 初始化核心组件
        self.logger.info("初始化核心组件...")
        
        # 去重器
        self.deduplicator = Deduplicator(
            DEDUP_CONFIG["index_file"],
            self.logger
        )
        
        # 存储管理器
        self.storage_manager = StorageManager(
            STORAGE_CONFIG["base_path"],
            self.logger
        )
        
        # 增量更新器
        self.incremental_updater = IncrementalUpdater(
            INCREMENTAL_CONFIG["state_file"],
            self.logger
        )
        
        # 失败跟踪器
        self.failure_tracker = FailureTracker(
            threshold=ERROR_HANDLING_CONFIG["failure_threshold"],
            pause_duration_hours=ERROR_HANDLING_CONFIG["pause_duration_hours"],
            logger=self.logger
        )
        
        # 初始化爬虫
        self.spiders = {}
        self._initialize_spiders()
        
        # 全局统计信息
        self.stats = {
            "start_time": None,
            "end_time": None,
            "total_fetched": 0,
            "filtered_count": 0,
            "duplicate_count": 0,
            "saved_count": 0,
            "error_count": 0,
            "sources": {}
        }
        
        self.logger.info("数据采集系统初始化完成")
    
    def _initialize_spiders(self):
        """
        初始化所有爬虫
        """
        self.logger.info("初始化爬虫...")
        
        # 初始化发改委爬虫
        try:
            ndrc_parser = NDRCParser(self.logger, NDRC_CONFIG.get("xpath"))
            ndrc_filter = KeywordFilter(STOCK_KEYWORDS, self.logger)
            
            self.spiders["ndrc"] = NDRCSpider(
                config=NDRC_CONFIG,
                logger=self.logger,
                parser=ndrc_parser,
                keyword_filter=ndrc_filter,
                deduplicator=self.deduplicator,
                storage_manager=self.storage_manager
            )
            self.logger.info("  ✓ 发改委爬虫初始化成功")
        except Exception as e:
            self.logger.error(f"  ✗ 发改委爬虫初始化失败: {e}", exc_info=True)
        
        # 初始化证券报爬虫
        try:
            cls_parser = CLSParser(self.logger)
            keyword_extractor = KeywordExtractor(self.logger)
            
            self.spiders["cls"] = CLSSpider(
                config=CLS_CONFIG,
                logger=self.logger,
                parser=cls_parser,
                deduplicator=self.deduplicator,
                storage_manager=self.storage_manager,
                keyword_extractor=keyword_extractor
            )
            self.logger.info("  ✓ 证券报爬虫初始化成功")
        except Exception as e:
            self.logger.error(f"  ✗ 证券报爬虫初始化失败: {e}", exc_info=True)
        
        # 初始化证券信息网爬虫
        try:
            cninfo_parser = CNInfoParser(self.logger)
            cninfo_filter = KeywordFilter(CNINFO_KEYWORDS, self.logger)
            
            self.spiders["cninfo"] = CNInfoSpider(
                config=CNINFO_CONFIG,
                logger=self.logger,
                parser=cninfo_parser,
                keyword_filter=cninfo_filter,
                deduplicator=self.deduplicator,
                storage_manager=self.storage_manager
            )
            self.logger.info("  ✓ 证券信息网爬虫初始化成功")
        except Exception as e:
            self.logger.error(f"  ✗ 证券信息网爬虫初始化失败: {e}", exc_info=True)
        
        self.logger.info(f"爬虫初始化完成，共 {len(self.spiders)} 个爬虫")
    
    def run_spider(self, source: str) -> bool:
        """
        运行单个爬虫
        
        Args:
            source: 数据源名称（ndrc/cls/cninfo）
        
        Returns:
            True 表示成功，False 表示失败
        """
        # 检查爬虫是否存在
        if source not in self.spiders:
            self.logger.error(f"爬虫 {source} 不存在")
            return False
        
        # 检查是否被暂停
        if self.failure_tracker.is_paused(source):
            pause_info = self.failure_tracker.get_pause_info(source)
            self.logger.warning(
                f"数据源 {source} 已暂停，"
                f"剩余 {pause_info['remaining_seconds']} 秒"
            )
            return False
        
        self.logger.info("-" * 80)
        self.logger.info(f"开始采集数据源: {source}")
        self.logger.info("-" * 80)
        
        try:
            spider = self.spiders[source]
            
            # 获取采集时间范围
            start_date, end_date = self.incremental_updater.get_time_range(
                source,
                default_days=self.default_days or INCREMENTAL_CONFIG.get("default_days", 7)
            )
            
            # 执行采集
            if source == "cls":
                # 证券报爬虫使用 run_once 方法
                collected_data = spider.run_once()
            else:
                # 发改委和证券信息网爬虫使用 run 方法
                collected_data = spider.run(start_date, end_date)
            
            # 获取爬虫统计信息
            spider_stats = spider.get_stats()
            
            # 更新全局统计信息
            self.stats["total_fetched"] += spider_stats.get("total_fetched", 0)
            self.stats["filtered_count"] += spider_stats.get("filtered_count", 0)
            self.stats["duplicate_count"] += spider_stats.get("duplicate_count", 0)
            self.stats["saved_count"] += spider_stats.get("saved_count", 0)
            self.stats["error_count"] += spider_stats.get("error_count", 0)
            
            # 记录数据源统计信息
            self.stats["sources"][source] = spider_stats

            fetched_count = spider_stats.get("total_fetched", 0)
            saved_count = spider_stats.get("saved_count", 0)
            error_count = spider_stats.get("error_count", 0)
            
            # 更新增量更新时间戳
            self.incremental_updater.set_last_update_time(source, datetime.now())
            self.incremental_updater.increment_collected_count(
                source,
                spider_stats.get("saved_count", 0)
            )
            
            if fetched_count == 0 and saved_count == 0 and error_count > 0:
                self.logger.error(
                    f"数据源 {source} 未获取到有效数据且发生 {error_count} 个错误，判定为失败"
                )
                self.failure_tracker.record_failure(source)
                return False

            # 记录成功
            self.failure_tracker.record_success(source)
            
            self.logger.info(
                f"数据源 {source} 采集完成: "
                f"获取={spider_stats.get('total_fetched', 0)}, "
                f"过滤={spider_stats.get('filtered_count', 0)}, "
                f"重复={spider_stats.get('duplicate_count', 0)}, "
                f"保存={spider_stats.get('saved_count', 0)}, "
                f"错误={spider_stats.get('error_count', 0)}"
            )
            
            return True
            
        except DataCollectorException as e:
            # 数据采集器自定义异常
            self.logger.error(f"数据源 {source} 采集失败: {e}")
            self.stats["error_count"] += 1
            self.failure_tracker.record_failure(source)
            return False
            
        except Exception as e:
            # 未知异常
            self.logger.error(
                f"数据源 {source} 采集时发生未知错误: {e}",
                exc_info=True
            )
            self.stats["error_count"] += 1
            self.failure_tracker.record_failure(source)
            return False
    
    def run_all_spiders(self, spider_names: Optional[List[str]] = None):
        """
        运行所有爬虫或指定的爬虫
        
        Args:
            spider_names: 要运行的爬虫名称列表，None 表示运行所有爬虫
        """
        # 记录开始时间
        self.stats["start_time"] = datetime.now()
        
        # 确定要运行的爬虫
        if spider_names is None:
            spider_names = list(self.spiders.keys())
        else:
            # 验证爬虫名称
            invalid_names = [name for name in spider_names if name not in self.spiders]
            if invalid_names:
                self.logger.error(f"无效的爬虫名称: {', '.join(invalid_names)}")
                self.logger.info(f"可用的爬虫: {', '.join(self.spiders.keys())}")
                return
        
        self.logger.info(f"准备运行 {len(spider_names)} 个爬虫: {', '.join(spider_names)}")
        
        # 按顺序执行各爬虫
        success_count = 0
        for source in spider_names:
            try:
                if self.run_spider(source):
                    success_count += 1
            except Exception as e:
                # 单个爬虫失败不影响其他爬虫
                self.logger.error(
                    f"运行爬虫 {source} 时发生严重错误: {e}",
                    exc_info=True
                )
                continue
        
        # 记录结束时间
        self.stats["end_time"] = datetime.now()
        
        # 保存状态
        self._save_state()
        
        # 清理过期数据
        self._cleanup_old_data()
        
        # 输出最终统计信息
        self._print_final_statistics(success_count, len(spider_names))
    
    def _save_state(self):
        """
        保存系统状态
        """
        try:
            self.logger.info("保存系统状态...")
            
            # 保存去重索引
            self.deduplicator.save_index()
            
            # 保存增量更新状态
            self.incremental_updater.save_state()
            
            self.logger.info("系统状态保存完成")
            
        except Exception as e:
            self.logger.error(f"保存系统状态失败: {e}", exc_info=True)

    def _cleanup_old_data(self):
        """
        清理超过保留天数的数据文件。
        """
        retention_days = STORAGE_CONFIG.get("retention_days", 7)
        try:
            self.storage_manager.cleanup_old_files(retention_days)
        except Exception as e:
            self.logger.error(f"清理过期数据失败: {e}", exc_info=True)
    
    def _print_final_statistics(self, success_count: int, total_count: int):
        """
        输出最终统计信息
        
        Args:
            success_count: 成功的爬虫数量
            total_count: 总爬虫数量
        """
        self.logger.info("=" * 80)
        self.logger.info("数据采集完成")
        self.logger.info("=" * 80)
        
        # 计算运行时长
        if self.stats["start_time"] and self.stats["end_time"]:
            duration = self.stats["end_time"] - self.stats["start_time"]
            duration_seconds = duration.total_seconds()
            self.logger.info(f"运行时长: {duration_seconds:.2f} 秒")
        
        # 输出全局统计
        self.logger.info(f"爬虫执行情况: {success_count}/{total_count} 成功")
        self.logger.info(
            f"全局统计: "
            f"总获取={self.stats['total_fetched']}, "
            f"过滤={self.stats['filtered_count']}, "
            f"重复={self.stats['duplicate_count']}, "
            f"保存={self.stats['saved_count']}, "
            f"错误={self.stats['error_count']}"
        )
        
        # 输出各数据源统计
        if self.stats["sources"]:
            self.logger.info("各数据源统计:")
            for source, source_stats in self.stats["sources"].items():
                self.logger.info(
                    f"  - {source}: "
                    f"获取={source_stats.get('total_fetched', 0)}, "
                    f"过滤={source_stats.get('filtered_count', 0)}, "
                    f"重复={source_stats.get('duplicate_count', 0)}, "
                    f"保存={source_stats.get('saved_count', 0)}, "
                    f"错误={source_stats.get('error_count', 0)}"
                )
        
        # 输出失败跟踪状态
        failure_status = self.failure_tracker.get_status()
        if failure_status:
            self.logger.info("失败跟踪状态:")
            for source, status in failure_status.items():
                if status["paused"]:
                    self.logger.warning(
                        f"  - {source}: 已暂停 "
                        f"(连续失败 {status['failure_count']} 次, "
                        f"暂停至 {status['pause_until'].strftime('%Y-%m-%d %H:%M:%S')})"
                    )
                elif status["failure_count"] > 0:
                    self.logger.info(
                        f"  - {source}: 连续失败 {status['failure_count']} 次"
                    )
        
        self.logger.info("=" * 80)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计信息
        
        Returns:
            统计信息字典
        """
        return self.stats.copy()


def parse_arguments():
    """
    解析命令行参数
    
    Returns:
        解析后的参数对象
    """
    parser = argparse.ArgumentParser(
        description="金融数据采集系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 运行所有爬虫
  python main.py
  
  # 运行指定爬虫
  python main.py --spiders ndrc cls
  
  # 显示版本信息
  python main.py --version
        """
    )
    
    parser.add_argument(
        "--spiders",
        nargs="+",
        choices=["ndrc", "cls", "cninfo"],
        help="指定要运行的爬虫（默认运行所有爬虫）"
    )

    parser.add_argument(
        "--source",
        nargs="+",
        choices=["ndrc", "cls", "cninfo"],
        help="指定要运行的数据源，等同于 --spiders（兼容 README 示例）"
    )

    parser.add_argument(
        "--days",
        type=int,
        help="首次运行或无增量状态时，默认采集最近 N 天的数据"
    )
    
    parser.add_argument(
        "--config",
        type=str,
        default="config.py",
        help="配置文件路径（默认: config.py）"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="金融数据采集系统 v1.0.0"
    )

    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="设置本次运行的日志级别"
    )
    
    return parser.parse_args()


def main():
    """
    主函数
    """
    # 解析命令行参数
    args = parse_arguments()

    spider_names = args.spiders or args.source

    if args.days is not None and args.days <= 0:
        print("错误：--days 必须是大于 0 的整数")
        sys.exit(1)

    if args.log_level:
        LOGGING_CONFIG["log_level"] = args.log_level
        LOGGING_CONFIG["console_level"] = args.log_level
        config.LOGGING_CONFIG["log_level"] = args.log_level
        config.LOGGING_CONFIG["console_level"] = args.log_level
    
    try:
        # 创建数据采集器
        collector = DataCollector(default_days=args.days)
        
        # 运行爬虫
        collector.run_all_spiders(spider_names=spider_names)
        
        # 正常退出
        sys.exit(0)
        
    except KeyboardInterrupt:
        print("\n收到中断信号，正在退出...")
        sys.exit(0)
        
    except Exception as e:
        print(f"严重错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
