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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple

from market_data.trading_calendar import TradingCalendar
from utils.collector_state import CollectorStateStore


DEFAULT_INTERVALS = {
    "cls": 5 * 60,
    "eastmoney_global": 10 * 60,
    "cninfo": 30 * 60,
    "ndrc": 60 * 60,
}
CST = timezone(timedelta(hours=8))

DEFAULT_MARKET_SNAPSHOT_SCHEDULE = [
    ("09:15", "morning"),
    ("09:20", "morning"),
    ("09:24", "morning"),
    ("09:25", "morning"),
    ("09:30", "morning"),
    ("09:35", "morning"),
    ("09:45", "morning"),
    ("14:30", "overnight"),
    ("14:40", "overnight"),
    ("14:45", "overnight"),
    ("14:48", "overnight"),
    ("14:50", "overnight"),
    ("14:52", "overnight"),
    ("14:55", "overnight"),
    ("15:00", "overnight"),
]


def _now() -> str:
    return datetime.now(CST).strftime("%Y-%m-%d %H:%M:%S")


def _china_now_naive() -> datetime:
    return datetime.now(CST).replace(tzinfo=None)


def _effective_interval(source: str, base_interval: int, now: datetime, calendar: TradingCalendar) -> int:
    minutes = now.hour * 60 + now.minute
    trade_day = calendar.is_trade_day(now.date())
    in_market_window = trade_day and 8 * 60 + 45 <= minutes <= 15 * 60 + 30
    if source == "cls":
        return base_interval if in_market_window else max(base_interval, 15 * 60)
    if source == "eastmoney_global":
        return base_interval if in_market_window else max(base_interval, 20 * 60)
    if source == "cninfo":
        if trade_day and 15 * 60 <= minutes <= 22 * 60:
            return min(base_interval, 15 * 60)
        return base_interval if in_market_window else max(base_interval, 60 * 60)
    if source == "ndrc":
        return base_interval if trade_day else max(base_interval, 2 * 60 * 60)
    return base_interval


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


def _next_market_run(
    schedule: List[Tuple[str, str]],
    now: datetime | None = None,
    calendar: TradingCalendar | None = None,
) -> tuple[datetime, str]:
    current = now or _china_now_naive()
    if current.tzinfo is not None:
        current = current.astimezone(CST).replace(tzinfo=None)
    trade_calendar = calendar or TradingCalendar()
    if not trade_calendar.available:
        raise RuntimeError("交易日历不可用，拒绝按工作日猜测市场调度")
    candidates: list[tuple[datetime, str]] = []
    for day_offset in range(45):
        target_date = current.date() + timedelta(days=day_offset)
        if not trade_calendar.is_trade_day(target_date):
            continue
        for time_text, mode in schedule:
            hour, minute = _parse_hhmm(time_text)
            run_at = datetime.combine(target_date, datetime.min.time()).replace(hour=hour, minute=minute)
            if run_at <= current:
                continue
            candidates.append((run_at, mode))
        if candidates:
            return min(candidates, key=lambda item: item[0])
    raise RuntimeError("无法计算下一次市场快照时间")


def run_source(source: str, days: int, project_dir: Path, data_dir: str | None = None) -> bool:
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
    if data_dir:
        cmd.extend(["--data-dir", data_dir])

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
    retention_days: int = 0,
    calendar_cache: str = "data_market/trading_calendar.json",
):
    project_dir = Path(__file__).resolve().parent
    market_schedule = schedule or DEFAULT_MARKET_SNAPSHOT_SCHEDULE
    trade_calendar = TradingCalendar(calendar_cache)
    trade_calendar.ensure(refresh_if_missing=True)
    print("市场快照定时器已启动")
    for time_text, mode in market_schedule:
        print(f"  - {time_text}: {mode}")

    try:
        while True:
            if not trade_calendar.available:
                print(f"[{_now()}] 交易日历不可用，15 分钟后重试，不执行市场采集")
                time.sleep(900)
                trade_calendar.refresh()
                continue
            run_at, mode = _next_market_run(market_schedule, calendar=trade_calendar)
            sleep_seconds = max(1, (run_at - _china_now_naive()).total_seconds())
            print(f"[{_now()}] 下一次市场快照: {run_at.strftime('%Y-%m-%d %H:%M')} ({mode})")
            time.sleep(sleep_seconds)
            run_market_snapshot(mode, output_dir, retention_days, project_dir)
    except KeyboardInterrupt:
        print(f"\n[{_now()}] 市场快照定时器已停止")


def run_scheduler(
    intervals: Dict[str, int],
    days: int,
    run_immediately: bool,
    state_path: str = "data/collector_health.json",
    data_dir: str | None = None,
    calendar_cache: str = "data_market/trading_calendar.json",
):
    project_dir = Path(__file__).resolve().parent
    next_run = {}
    now = time.time()
    state_store = CollectorStateStore(state_path)
    trade_calendar = TradingCalendar(calendar_cache)
    trade_calendar.ensure(refresh_if_missing=True)
    persisted_sources = state_store.get_sources()

    for index, (source, interval) in enumerate(intervals.items()):
        paused_until_text = str((persisted_sources.get(source) or {}).get("paused_until") or "")
        try:
            paused_until = datetime.fromisoformat(paused_until_text).timestamp() if paused_until_text else 0
        except ValueError:
            paused_until = 0
        initial = now + index * 20 if run_immediately else now + interval
        next_run[source] = max(initial, paused_until)

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
                success = run_source(source, days, project_dir, data_dir=data_dir)
                if success:
                    state_store.record_success(source)
                    next_run[source] = time.time() + _effective_interval(
                        source,
                        intervals[source],
                        _china_now_naive(),
                        trade_calendar,
                    )
                else:
                    backoff = state_store.record_failure(
                        source,
                        "collector process returned non-zero",
                        base_interval=intervals[source],
                    )
                    next_run[source] = time.time() + backoff

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
    parser.add_argument("--market-retention-days", type=int, default=0, help="市场快照保留天数，0 表示永久保留")
    parser.add_argument("--calendar-cache", default="data_market/trading_calendar.json", help="交易日历缓存")
    parser.add_argument("--collector-state", default="data/collector_health.json", help="采集器健康状态文件")
    parser.add_argument("--data-dir", default=None, help="新闻公告数据目录")
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
                "calendar_cache": args.calendar_cache,
            },
            daemon=True,
        ).start()
    run_scheduler(
        intervals,
        days=max(1, args.days),
        run_immediately=not args.no_immediate,
        state_path=args.collector_state,
        data_dir=args.data_dir,
        calendar_cache=args.calendar_cache,
    )


if __name__ == "__main__":
    main()
