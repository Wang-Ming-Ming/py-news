#!/usr/bin/env python3
"""Generate an AkShare-backed A-share market snapshot."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from market_data.akshare_client import fetch_market_frames
from market_data.market_scoring import derive_snapshot

CST = timezone(timedelta(hours=8))


def now_cst() -> datetime:
    return datetime.now(CST)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def is_valid_snapshot(snapshot: dict[str, Any]) -> bool:
    summary = snapshot.get("derived", {}).get("summary", {})
    source_status = snapshot.get("source_status", {})
    stock_spot_ok = bool(source_status.get("stock_spot", {}).get("ok"))
    stock_count = int(summary.get("stock_count") or 0)
    tradeable_count = int(summary.get("tradeable_stock_count") or 0)
    return stock_spot_ok and stock_count > 1000 and tradeable_count > 500


def cleanup_old_snapshots(output_dir: Path, retention_days: int) -> list[str]:
    if retention_days <= 0 or not output_dir.exists():
        return []
    cutoff = now_cst().date() - timedelta(days=retention_days)
    removed: list[str] = []
    for child in output_dir.iterdir():
        if not child.is_dir():
            continue
        try:
            folder_date = datetime.strptime(child.name, "%Y-%m-%d").date()
        except ValueError:
            continue
        if folder_date < cutoff:
            shutil.rmtree(child)
            removed.append(child.name)
    return removed


def build_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    captured_at = now_cst()
    market_date = args.market_date or captured_at.strftime("%Y%m%d")
    frames = fetch_market_frames(market_date)
    derived = derive_snapshot(frames, allow_chinext=args.allow_chinext)
    errors = {
        key: value.get("error")
        for key, value in frames.items()
        if not value.get("ok")
    }
    return {
        "metadata": {
            "source": "akshare",
            "mode": args.mode,
            "captured_at": captured_at.isoformat(),
            "market_date": market_date,
            "network_mode": os.getenv("MARKET_NETWORK_MODE") or "system_proxy",
            "local_adapter_url": os.getenv("MARKET_LOCAL_ADAPTER_URL"),
            "allow_chinext": args.allow_chinext,
            "retention_days": args.retention_days,
            "notes": "Market data only. News/policy/announcements remain in data_dev.",
        },
        "source_status": {
            key: {
                "ok": value.get("ok"),
                "rows": value.get("rows"),
                "duration_sec": value.get("duration_sec"),
                "error": value.get("error"),
                "columns": value.get("columns"),
            }
            for key, value in frames.items()
        },
        "derived": derived,
        "raw": {
            key: value.get("records", [])
            for key, value in frames.items()
        },
        "errors": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate A-share market snapshot with AkShare.")
    parser.add_argument(
        "--mode",
        choices=["morning", "midday", "overnight", "custom"],
        default="custom",
        help="Snapshot mode used in the output filename.",
    )
    parser.add_argument(
        "--output-dir",
        default="data_market",
        help="Directory for market snapshots.",
    )
    parser.add_argument(
        "--market-date",
        default=None,
        help="Trading date for limit-up pool interfaces, format YYYYMMDD. Defaults to today in China time.",
    )
    parser.add_argument(
        "--allow-chinext",
        action="store_true",
        help="Include 300/301 ChiNext stocks in derived tradable rankings.",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=30,
        help="Delete date folders older than this many days. Set 0 to disable cleanup.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    snapshot = build_snapshot(args)
    captured_at = datetime.fromisoformat(snapshot["metadata"]["captured_at"])
    date_dir = output_dir / captured_at.strftime("%Y-%m-%d")
    snapshot_path = date_dir / f"{args.mode}_snapshot.json"
    failed_snapshot_path = date_dir / f"{args.mode}_failed_snapshot.json"
    latest_path = output_dir / f"latest_{args.mode}_snapshot.json"
    snapshot_valid = is_valid_snapshot(snapshot)
    if snapshot_valid:
        write_json(snapshot_path, snapshot)
        write_json(latest_path, snapshot)
    else:
        write_json(failed_snapshot_path, snapshot)
    removed = cleanup_old_snapshots(output_dir, args.retention_days)

    summary = snapshot["derived"]["summary"]
    print(json.dumps({
        "snapshot_path": str(snapshot_path) if snapshot_valid else None,
        "failed_snapshot_path": None if snapshot_valid else str(failed_snapshot_path),
        "latest_path": str(latest_path),
        "latest_updated": snapshot_valid,
        "stock_count": summary["stock_count"],
        "tradeable_stock_count": summary["tradeable_stock_count"],
        "limit_up_count": summary["limit_up_count"],
        "broken_limit_count": summary["broken_limit_count"],
        "errors": snapshot["errors"],
        "removed_old_folders": removed,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
