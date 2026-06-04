# -*- coding: utf-8 -*-
"""
项目一键启动入口。

同时启动：
- 新闻源 HTTP 接口
- 后台定时采集任务
"""

import argparse
import threading

from config import STORAGE_CONFIG
from news_api import create_server
from scheduler import DEFAULT_INTERVALS, run_scheduler


def parse_args():
    parser = argparse.ArgumentParser(description="股票新闻源服务")
    parser.add_argument("--host", default="127.0.0.1", help="新闻接口监听地址")
    parser.add_argument("--port", type=int, default=8765, help="新闻接口端口")
    parser.add_argument("--data-dir", default=STORAGE_CONFIG["base_path"], help="数据目录")
    parser.add_argument("--retention-days", type=int, default=STORAGE_CONFIG.get("retention_days", 7))
    parser.add_argument("--days", type=int, default=1, help="每次采集最近 N 天范围")
    parser.add_argument("--no-immediate", action="store_true", help="启动后不立即采集，等待第一个周期")
    parser.add_argument("--cls-interval", type=int, default=DEFAULT_INTERVALS["cls"])
    parser.add_argument("--eastmoney-global-interval", type=int, default=DEFAULT_INTERVALS["eastmoney_global"])
    parser.add_argument("--cninfo-interval", type=int, default=DEFAULT_INTERVALS["cninfo"])
    parser.add_argument("--ndrc-interval", type=int, default=DEFAULT_INTERVALS["ndrc"])
    return parser.parse_args()


def main():
    args = parse_args()
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
    )

    scheduler_thread = threading.Thread(
        target=run_scheduler,
        kwargs={
            "intervals": intervals,
            "days": max(1, args.days),
            "run_immediately": not args.no_immediate,
        },
        daemon=True,
    )
    scheduler_thread.start()

    print(f"新闻源接口已启动: http://{args.host}:{args.port}/news")
    print("定时采集已在后台启动，按 Ctrl+C 停止服务")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
