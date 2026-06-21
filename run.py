# -*- coding: utf-8 -*-
"""
项目一键启动入口。

同时启动：
- 新闻源 HTTP 接口
- 后台定时采集任务
"""

import argparse
import threading
from pathlib import Path

from config import STORAGE_CONFIG
from news_api import create_server
from scheduler import (
    DEFAULT_INTERVALS,
    DEFAULT_MARKET_SNAPSHOT_SCHEDULE,
    parse_market_schedule,
    run_market_snapshot_scheduler,
    run_scheduler,
)


def parse_args():
    parser = argparse.ArgumentParser(description="股票新闻源服务")
    parser.add_argument("--host", default="127.0.0.1", help="新闻接口监听地址")
    parser.add_argument("--port", type=int, default=8765, help="新闻接口端口")
    parser.add_argument("--data-dir", default=STORAGE_CONFIG["base_path"], help="数据目录")
    parser.add_argument("--retention-days", type=int, default=15, help="API 默认新闻查询窗口，不控制服务器归档删除")
    parser.add_argument("--days", type=int, default=1, help="每次采集最近 N 天范围")
    parser.add_argument("--no-immediate", action="store_true", help="启动后不立即采集，等待第一个周期")
    parser.add_argument("--cls-interval", type=int, default=DEFAULT_INTERVALS["cls"])
    parser.add_argument("--eastmoney-global-interval", type=int, default=DEFAULT_INTERVALS["eastmoney_global"])
    parser.add_argument("--cninfo-interval", type=int, default=DEFAULT_INTERVALS["cninfo"])
    parser.add_argument("--ndrc-interval", type=int, default=DEFAULT_INTERVALS["ndrc"])
    parser.add_argument("--no-market", action="store_true", help="不启动市场数据定时快照")
    parser.add_argument(
        "--market-times",
        default=",".join(f"{time_text}={mode}" for time_text, mode in DEFAULT_MARKET_SNAPSHOT_SCHEDULE),
        help="市场快照时间，格式 HH:MM=mode,HH:MM=mode",
    )
    parser.add_argument("--market-output-dir", default="data_market", help="市场快照输出目录")
    parser.add_argument("--market-retention-days", type=int, default=0, help="市场快照保留天数，0 表示永久保留")
    parser.add_argument("--calendar-cache", default=None, help="交易日历缓存，默认位于市场数据目录")
    parser.add_argument("--collector-state", default=None, help="采集健康状态，默认位于新闻数据目录")
    parser.add_argument("--api-token", default="", help="只读 v1 API 令牌，也可使用 DATA_API_TOKEN")
    return parser.parse_args()


def main():
    args = parse_args()
    calendar_cache = args.calendar_cache or str(Path(args.market_output_dir) / "trading_calendar.json")
    collector_state = args.collector_state or str(Path(args.data_dir) / "collector_health.json")
    intervals = {
        "cls": max(60, args.cls_interval),
        "eastmoney_global": max(300, args.eastmoney_global_interval),
        "cninfo": max(300, args.cninfo_interval),
        "ndrc": max(900, args.ndrc_interval),
    }

    server = create_server(
        host=args.host,
        port=args.port,
        data_dir=args.data_dir,
        retention_days=args.retention_days,
        market_dir=args.market_output_dir,
        calendar_cache=calendar_cache,
        collector_state=collector_state,
        api_token=args.api_token,
    )

    scheduler_thread = threading.Thread(
        target=run_scheduler,
        kwargs={
            "intervals": intervals,
            "days": max(1, args.days),
            "run_immediately": not args.no_immediate,
            "state_path": collector_state,
            "data_dir": args.data_dir,
            "calendar_cache": calendar_cache,
        },
        daemon=True,
    )
    scheduler_thread.start()

    market_thread = None
    if not args.no_market:
        market_thread = threading.Thread(
            target=run_market_snapshot_scheduler,
            kwargs={
                "schedule": parse_market_schedule(args.market_times),
                "output_dir": args.market_output_dir,
                "retention_days": args.market_retention_days,
                "calendar_cache": calendar_cache,
            },
            daemon=True,
        )
        market_thread.start()

    print(f"只读数据接口已启动: http://{args.host}:{args.port}/v1/manifest")
    if market_thread:
        print("新闻采集和市场数据定时快照已在后台启动，按 Ctrl+C 停止服务")
    else:
        print("新闻采集已在后台启动，按 Ctrl+C 停止服务")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
