#!/usr/bin/env python3
"""Sync the objective server data required by the morning skill."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from client.server_data_client import ServerDataClient, sync_with_fallback
from client.server_settings import load_server_settings


def compact_result(result: dict, cache_dir: Path) -> dict:
    snapshot = result.get("snapshot") or {}
    history_files = result.get("history_snapshot_context_files") or []
    downloads = result.get("downloads") or {}
    history_dates = sorted(
        {
            path.split("/archive/", 1)[1].split("/", 1)[0]
            for path in history_files
            if "/archive/" in path
        }
    )
    return {
        "schema_version": result.get("schema_version"),
        "mode": result.get("mode"),
        "synced_at": result.get("synced_at"),
        "server": result.get("server"),
        "snapshot": {
            key: snapshot.get(key)
            for key in (
                "snapshot_id",
                "source_time",
                "market_date",
                "window_valid",
                "expected_count",
                "actual_count",
                "is_complete",
            )
        },
        "history": {
            "snapshot_count": len(history_files),
            "date_from": history_dates[0] if history_dates else None,
            "date_to": history_dates[-1] if history_dates else None,
        },
        "datasets": {
            name: {
                "path": payload.get("path"),
                "actual_count": payload.get("actual_count"),
                "reused": payload.get("reused"),
            }
            for name, payload in downloads.items()
            if isinstance(payload, dict)
        },
        "pointers": {
            "latest_context": str(cache_dir / "latest_context.json"),
            "snapshot_context": result.get("snapshot_context_file"),
            "pools": result.get("pools_file"),
            "news_index": result.get("news_index_file"),
            "announcements_index": result.get("announcements_index_file"),
            "calendar": result.get("calendar_file"),
            "health": result.get("health_file"),
        },
        "news_count": result.get("news_count"),
        "announcement_count": result.get("announcement_count"),
        "sync_strategy": result.get("sync_strategy"),
        "using_cached_data": result.get("using_cached_data", False),
        "sync_error": result.get("sync_error"),
        "sync_duration_seconds": result.get("sync_duration_seconds"),
        "connection_config": result.get("connection_config"),
    }


def main() -> None:
    settings = load_server_settings()
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default=settings["server"])
    parser.add_argument("--token", default=settings["token"])
    parser.add_argument("--cache-dir", default="data_server_cache")
    parser.add_argument(
        "--full-output",
        action="store_true",
        help="Print the complete sync payload for debugging instead of the live compact summary.",
    )
    args = parser.parse_args()
    started = time.monotonic()
    result = sync_with_fallback(ServerDataClient(args.server, args.token), Path(args.cache_dir), "morning")
    result["sync_duration_seconds"] = round(time.monotonic() - started, 2)
    result["server"] = args.server
    result["connection_config"] = settings["config_path"]
    print(
        json.dumps(
            result if args.full_output else compact_result(result, Path(args.cache_dir)),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
