# -*- coding: utf-8 -*-
"""
定时采集入口。

按固定频率调用 main.py 采集新闻源：
- cls: 5 分钟
- eastmoney_global: 10 分钟
- cninfo: 60 分钟
- ndrc: 4 小时

也可以按交易日固定时间调用 market_data/market_snapshot.py 生成市场快照。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple


DEFAULT_INTERVALS = {
    "cls": 5 * 60,
    "eastmoney_global": 10 * 60,
    "cninfo": 60 * 60,
    "ndrc": 4 * 60 * 60,
}

DEFAULT_MARKET_SNAPSHOT_SCHEDULE = [
    ("09:20", "morning"),
    ("09:30", "morning"),
    ("10:30", "midday"),
    ("13:30", "midday"),
    ("14:30", "overnight"),
    ("14:45", "overnight"),
    ("14:55", "overnight"),
]


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _is_weekday(value: datetime) -> bool:
    return value.weekday() < 5


def parse_market_schedule(value: str) -> List[Tuple[str, str]]:
    if not value:
        return DEFAULT_MARKET_SNAPSHOT_SCHEDULE

    schedule: List[Tuple[str, str]] = []
    for raw_part in value.split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "=" in part:
            time_text, mode = part.split("=", 1)
            mode = mode.strip()
        else:
            time_text = part
            hour, minute = _parse_hhmm(time_text)
            if hour < 10:
                mode = "morning"
            elif hour < 14:
                mode = "midday"
            else:
                mode = "overnight"
        _parse_hhmm(time_text)
        if mode not in {"morning", "midday", "overnight", "custom"}:
            raise ValueError(f"无效市场快照模式: {mode}")
        schedule.append((time_text.strip(), mode))
    return schedule or DEFAULT_MARKET_SNAPSHOT_SCHEDULE


def _parse_hhmm(value: str) -> tuple[int, int]:
    hour_text, minute_text = value.strip().split(":", 1)
    hour = int(hour_text)
    minute = int(minute_text)
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"无效时间: {value}")
    return hour, minute


def _next_market_run(schedule: List[Tuple[str, str]], now: datetime | None = None) -> tuple[datetime, str]:
    current = now or datetime.now()
    candidates: list[tuple[datetime, str]] = []
    for day_offset in range(8):
        target_date = current.date() + timedelta(days=day_offset)
        for time_text, mode in schedule:
            hour, minute = _parse_hhmm(time_text)
            run_at = datetime.combine(target_date, datetime.min.time()).replace(hour=hour, minute=minute)
            if run_at <= current or not _is_weekday(run_at):
                continue
            candidates.append((run_at, mode))
        if candidates:
            return min(candidates, key=lambda item: item[0])
    raise RuntimeError("无法计算下一次市场快照时间")


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


def run_market_snapshot(mode: str, output_dir: str, retention_days: int, project_dir: Path) -> bool:
    cmd = [
        sys.executable,
        str(project_dir / "market_data" / "market_snapshot.py"),
        "--mode",
        mode,
        "--output-dir",
        output_dir,
        "--retention-days",
        str(retention_days),
    ]

    print(f"[{_now()}] 开始生成市场快照 {mode}")
    result = subprocess.run(cmd, cwd=str(project_dir))

    if result.returncode == 0:
        print(f"[{_now()}] 市场快照 {mode} 生成完成")
        return True

    print(f"[{_now()}] 市场快照 {mode} 生成失败，退出码: {result.returncode}")
    return False


def run_market_snapshot_scheduler(
    schedule: List[Tuple[str, str]] | None = None,
    output_dir: str = "data_market",
    retention_days: int = 30,
):
    project_dir = Path(__file__).resolve().parent
    market_schedule = schedule or DEFAULT_MARKET_SNAPSHOT_SCHEDULE
    print("市场快照定时器已启动")
    for time_text, mode in market_schedule:
        print(f"  - {time_text}: {mode}")

    try:
        while True:
            run_at, mode = _next_market_run(market_schedule)
            sleep_seconds = max(1, (run_at - datetime.now()).total_seconds())
            print(f"[{_now()}] 下一次市场快照: {run_at.strftime('%Y-%m-%d %H:%M')} ({mode})")
            time.sleep(sleep_seconds)
            run_market_snapshot(mode, output_dir, retention_days, project_dir)
    except KeyboardInterrupt:
        print(f"\n[{_now()}] 市场快照定时器已停止")


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
    parser.add_argument("--with-market", action="store_true", help="同时启动交易日市场快照定时器")
    parser.add_argument(
        "--market-times",
        default=",".join(f"{time_text}={mode}" for time_text, mode in DEFAULT_MARKET_SNAPSHOT_SCHEDULE),
        help="市场快照时间，格式 HH:MM=mode,HH:MM=mode",
    )
    parser.add_argument("--market-output-dir", default="data_market", help="市场快照输出目录")
    parser.add_argument("--market-retention-days", type=int, default=30, help="市场快照保留天数")
    return parser.parse_args()


def main():
    args = parse_args()
    intervals = {
        "cls": max(60, args.cls_interval),
        "eastmoney_global": max(300, args.eastmoney_global_interval),
        "cninfo": max(300, args.cninfo_interval),
        "ndrc": max(900, args.ndrc_interval),
    }
    if args.with_market:
        import threading

        threading.Thread(
            target=run_market_snapshot_scheduler,
            kwargs={
                "schedule": parse_market_schedule(args.market_times),
                "output_dir": args.market_output_dir,
                "retention_days": args.market_retention_days,
            },
            daemon=True,
        ).start()
    run_scheduler(intervals, days=max(1, args.days), run_immediately=not args.no_immediate)


if __name__ == "__main__":
    main()
