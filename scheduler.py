# -*- coding: utf-8 -*-
"""
定时采集入口。

按固定频率调用 main.py 采集新闻源：
- cls: 5 分钟
- eastmoney_global: 10 分钟
- cninfo: 60 分钟
- ndrc: 4 小时
"""

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict


DEFAULT_INTERVALS = {
    "cls": 5 * 60,
    "eastmoney_global": 10 * 60,
    "cninfo": 60 * 60,
    "ndrc": 4 * 60 * 60,
}


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def run_source(source: str, days: int, project_dir: Path) -> bool:
    cmd = [
        sys.executable,
        str(project_dir / "main.py"),
        "--source",
        source,
        "--days",
        str(days),
        "--log-level",
        "INFO",
    ]

    print(f"[{_now()}] 开始采集 {source}")
    result = subprocess.run(cmd, cwd=str(project_dir))

    if result.returncode == 0:
        print(f"[{_now()}] {source} 采集完成")
        return True

    print(f"[{_now()}] {source} 采集失败，退出码: {result.returncode}")
    return False


def run_scheduler(intervals: Dict[str, int], days: int, run_immediately: bool):
    project_dir = Path(__file__).resolve().parent
    next_run = {}
    now = time.time()

    for source, interval in intervals.items():
        next_run[source] = now if run_immediately else now + interval

    print("新闻采集定时器已启动")
    for source, interval in intervals.items():
        print(f"  - {source}: 每 {interval // 60} 分钟")

    try:
        while True:
            current = time.time()
            due_sources = [
                source
                for source, scheduled_at in next_run.items()
                if current >= scheduled_at
            ]

            for source in due_sources:
                run_source(source, days, project_dir)
                next_run[source] = time.time() + intervals[source]

            sleep_seconds = max(5, min(next_run.values()) - time.time())
            time.sleep(sleep_seconds)

    except KeyboardInterrupt:
        print(f"\n[{_now()}] 定时采集已停止")


def parse_args():
    parser = argparse.ArgumentParser(description="股票新闻源定时采集器")
    parser.add_argument("--days", type=int, default=1, help="每次采集最近 N 天范围")
    parser.add_argument("--no-immediate", action="store_true", help="启动后不立即采集，等待第一个周期")
    parser.add_argument("--cls-interval", type=int, default=DEFAULT_INTERVALS["cls"], help="财联社采集间隔秒数")
    parser.add_argument("--eastmoney-global-interval", type=int, default=DEFAULT_INTERVALS["eastmoney_global"], help="东方财富全球财经快讯采集间隔秒数")
    parser.add_argument("--cninfo-interval", type=int, default=DEFAULT_INTERVALS["cninfo"], help="巨潮采集间隔秒数")
    parser.add_argument("--ndrc-interval", type=int, default=DEFAULT_INTERVALS["ndrc"], help="发改委采集间隔秒数")
    return parser.parse_args()


def main():
    args = parse_args()
    intervals = {
        "cls": max(60, args.cls_interval),
        "eastmoney_global": max(300, args.eastmoney_global_interval),
        "cninfo": max(300, args.cninfo_interval),
        "ndrc": max(900, args.ndrc_interval),
    }
    run_scheduler(intervals, days=max(1, args.days), run_immediately=not args.no_immediate)


if __name__ == "__main__":
    main()
