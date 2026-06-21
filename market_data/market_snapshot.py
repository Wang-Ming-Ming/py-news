#!/usr/bin/env python3
"""Generate an AkShare-backed A-share market snapshot."""

from __future__ import annotations

import argparse
import hashlib
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
from market_data.market_derivation import derive_snapshot

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
    window_valid = bool(snapshot.get("metadata", {}).get("window_valid", True))
    return stock_spot_ok and stock_count > 1000 and tradeable_count > 500 and window_valid


def is_mode_window_valid(mode: str, captured_at: datetime) -> bool:
    minutes = captured_at.hour * 60 + captured_at.minute
    if mode == "morning":
        return 9 * 60 + 14 <= minutes <= 9 * 60 + 46
    if mode == "midday":
        return 9 * 60 + 47 <= minutes <= 14 * 60 + 28
    if mode == "overnight":
        return 14 * 60 + 29 <= minutes <= 15 * 60 + 2
    return True


def build_snapshot_id(mode: str, captured_at: datetime) -> str:
    raw = f"{mode}|{captured_at.isoformat(timespec='seconds')}"
    suffix = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:10]
    return f"{captured_at.strftime('%Y%m%dT%H%M%S')}_{mode}_{suffix}"


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
    snapshot_id = build_snapshot_id(args.mode, captured_at)
    window_valid = is_mode_window_valid(args.mode, captured_at)
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
            "schema_version": "2.0",
            "snapshot_id": snapshot_id,
            "dataset_version": snapshot_id,
            "mode": args.mode,
            "captured_at": captured_at.isoformat(),
            "source_time": captured_at.isoformat(),
            "market_date": market_date,
            "window_valid": window_valid,
            "network_mode": os.getenv("MARKET_NETWORK_MODE") or "system_proxy",
            "local_adapter_url": os.getenv("MARKET_LOCAL_ADAPTER_URL"),
            "allow_chinext": args.allow_chinext,
            "retention_days": args.retention_days,
            "units": {
                "price": "CNY_per_share",
                "pct": "percent",
                "amount": "CNY",
                "volume": "upstream_native_unit",
                "market_cap": "CNY",
            },
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
        default=0,
        help="Delete date folders older than this many days. Defaults to 0 (permanent archive).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    snapshot = build_snapshot(args)
    captured_at = datetime.fromisoformat(snapshot["metadata"]["captured_at"])
    date_dir = output_dir / captured_at.strftime("%Y-%m-%d")
    snapshot_path = date_dir / f"{args.mode}_snapshot.json"
    immutable_snapshot_path = date_dir / f"{args.mode}_{captured_at.strftime('%H%M%S')}_{snapshot['metadata']['snapshot_id']}.json"
    failed_snapshot_path = date_dir / f"{args.mode}_failed_snapshot.json"
    latest_path = output_dir / f"latest_{args.mode}_snapshot.json"
    snapshot_valid = is_valid_snapshot(snapshot)
    if snapshot_valid:
        write_json(immutable_snapshot_path, snapshot)
        write_json(snapshot_path, snapshot)
        write_json(latest_path, snapshot)
    else:
        write_json(failed_snapshot_path, snapshot)
    removed = cleanup_old_snapshots(output_dir, args.retention_days)

    summary = snapshot["derived"]["summary"]
    print(json.dumps({
        "snapshot_path": str(snapshot_path) if snapshot_valid else None,
        "immutable_snapshot_path": str(immutable_snapshot_path) if snapshot_valid else None,
        "failed_snapshot_path": None if snapshot_valid else str(failed_snapshot_path),
        "latest_path": str(latest_path),
        "latest_updated": snapshot_valid,
        "snapshot_id": snapshot["metadata"]["snapshot_id"],
        "window_valid": snapshot["metadata"]["window_valid"],
        "stock_count": summary["stock_count"],
        "tradeable_stock_count": summary["tradeable_stock_count"],
        "limit_up_count": summary["limit_up_count"],
        "broken_limit_count": summary["broken_limit_count"],
        "errors": snapshot["errors"],
        "removed_old_folders": removed,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
