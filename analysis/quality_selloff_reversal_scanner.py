#!/usr/bin/env python3
"""Discover strong main-board stocks that may repair a recent non-fundamental selloff."""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from market_data.market_derivation import number
from market_data.market_filters import get_code, get_name


DEFAULT_CACHE_DIR = Path("data_server_cache")
ORDINARY_PREFIXES = ("000", "001", "002", "003", "600", "601", "603", "605")


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _read_gzip_rows(path: Path) -> Iterable[dict[str, Any]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def _ordinary_main_board(code: str, name: str) -> bool:
    upper_name = name.upper()
    return (
        code.startswith(ORDINARY_PREFIXES)
        and "ST" not in upper_name
        and "退" not in name
    )


def _daily_paths(cache_dir: Path, until: str, days: int) -> list[tuple[str, Path]]:
    archive = cache_dir / "archive"
    if not archive.exists():
        return []
    selected: list[tuple[str, Path]] = []
    for day_dir in sorted(path for path in archive.iterdir() if path.is_dir()):
        market_date = day_dir.name
        if market_date > until:
            continue
        candidates = sorted((day_dir / "market").glob("*/stocks.ndjson.gz"))
        if candidates:
            selected.append((market_date, candidates[-1]))
    return selected[-days:]


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _return(values: list[float], sessions: int) -> float | None:
    if len(values) <= sessions or values[-sessions - 1] <= 0:
        return None
    return (values[-1] / values[-sessions - 1] - 1) * 100


def _observation(market_date: str, row: dict[str, Any]) -> dict[str, Any] | None:
    close = number(row, ["最新价", "收盘"])
    open_price = number(row, ["今开", "开盘"])
    high = number(row, ["最高"])
    low = number(row, ["最低"])
    if min(close, open_price, high, low) <= 0:
        return None
    previous_close = number(row, ["昨收"])
    pct = (
        (close / previous_close - 1) * 100
        if previous_close > 0
        else number(row, ["涨跌幅"])
    )
    return {
        "market_date": market_date,
        "close": close,
        "open": open_price,
        "high": high,
        "low": low,
        "prev_close": previous_close,
        "pct": pct,
        "amount": number(row, ["成交额"]),
        "volume": number(row, ["成交量"]),
    }


def evaluate_selloff(
    code: str,
    name: str,
    observations: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Score the final observation as a repairable selloff after a strong trend."""
    if len(observations) < 7:
        return None
    selloff = observations[-1]
    prior = observations[:-1]
    prior_closes = [item["close"] for item in prior if item["close"] > 0]
    all_closes = prior_closes + [selloff["close"]]
    if len(prior_closes) < 6:
        return None

    prior_ma5 = _mean(prior_closes[-5:])
    prior_ma10 = _mean(prior_closes[-min(10, len(prior_closes)):])
    ma20_after = _mean(all_closes[-20:])
    return_5d_before = _return(prior_closes, 5)
    return_10d_before = _return(prior_closes, 10)
    if prior_ma5 is None or prior_ma10 is None or ma20_after is None:
        return None

    day_range = selloff["high"] - selloff["low"]
    close_position = (
        (selloff["close"] - selloff["low"]) / day_range if day_range > 0 else 0.0
    )
    prior_highs = [item["high"] for item in prior[-20:] if item["high"] > 0]
    prior_range_high = max(prior_highs) if prior_highs else prior_closes[-1]
    distance_from_prior_high = (
        (prior_range_high - prior_closes[-1]) / prior_range_high * 100
        if prior_range_high > 0
        else 100.0
    )
    previous_amounts = [item["amount"] for item in prior[-5:] if item["amount"] > 0]
    average_amount = _mean(previous_amounts)
    amount_ratio = selloff["amount"] / average_amount if average_amount else None
    prior_trend_strong = bool(
        (return_5d_before is not None and return_5d_before >= 3)
        or (return_10d_before is not None and return_10d_before >= 8)
    )
    trend_structure_intact = bool(
        prior_closes[-1] >= prior_ma10 * 0.98
        and selloff["close"] >= ma20_after * 0.97
        and distance_from_prior_high <= 18
    )
    hard_shape = bool(
        -9.2 <= selloff["pct"] <= -2.8
        and selloff["amount"] >= 50_000_000
        and prior_trend_strong
        and trend_structure_intact
        and close_position >= 0.12
        and (amount_ratio is None or 0.55 <= amount_ratio <= 4.0)
    )
    if not hard_shape:
        return None

    score = 35.0
    score += min(max((return_5d_before or 0), 0), 25) * 0.55
    score += min(max((return_10d_before or 0), 0), 50) * 0.25
    score += max(0.0, 18 - distance_from_prior_high) * 0.7
    score += min(close_position, 1) * 8
    score += 7 if selloff["close"] >= ma20_after else 3
    score += 6 if amount_ratio is not None and 0.8 <= amount_ratio <= 2.5 else 1
    score += max(0.0, 3.0 - abs(abs(selloff["pct"]) - 5.5))

    return {
        "code": code,
        "name": name,
        "selloff_date": selloff["market_date"],
        "selloff_close": round(selloff["close"], 4),
        "selloff_open": round(selloff["open"], 4),
        "selloff_high": round(selloff["high"], 4),
        "selloff_low": round(selloff["low"], 4),
        "selloff_prev_close": round(selloff["prev_close"], 4),
        "selloff_pct": round(selloff["pct"], 4),
        "selloff_amount": round(selloff["amount"], 2),
        "selloff_amount_ratio_5d": (
            round(amount_ratio, 4) if amount_ratio is not None else None
        ),
        "selloff_close_position": round(close_position, 4),
        "return_5d_before_selloff": (
            round(return_5d_before, 4) if return_5d_before is not None else None
        ),
        "return_10d_before_selloff": (
            round(return_10d_before, 4) if return_10d_before is not None else None
        ),
        "prior_ma5": round(prior_ma5, 4),
        "prior_ma10": round(prior_ma10, 4),
        "ma20_after_selloff": round(ma20_after, 4),
        "distance_from_prior_20d_high_pct": round(distance_from_prior_high, 4),
        "prior_trend_strong": prior_trend_strong,
        "trend_structure_intact": trend_structure_intact,
        "objective_score": round(score, 2),
        "requires_direct_business_evidence": True,
        "requires_selloff_cause_check": True,
        "requires_hard_risk_check": True,
        "requires_theme_or_new_catalyst": True,
    }


def _opening_vwap(row: dict[str, Any]) -> float:
    amount = number(row, ["成交额", "amount"])
    volume = number(row, ["成交量", "volume"])
    price = number(row, ["最新价", "收盘", "price"])
    if min(amount, volume, price) <= 0:
        return 0.0
    raw = amount / volume
    return raw / 100 if raw / price > 20 else raw


def evaluate_live_repair(
    candidate: dict[str, Any],
    row: dict[str, Any],
    source_time: str = "",
) -> dict[str, Any]:
    price = number(row, ["最新价", "收盘", "price"])
    open_price = number(row, ["今开", "开盘", "open"])
    high = number(row, ["最高", "high"])
    low = number(row, ["最低", "low"])
    previous_close = number(row, ["昨收", "prev_close"])
    amount = number(row, ["成交额", "amount"])
    pct = (
        (price / previous_close - 1) * 100
        if previous_close > 0
        else number(row, ["涨跌幅", "pct"])
    )
    vwap = _opening_vwap(row)
    day_range = high - low
    close_position = (price - low) / day_range if day_range > 0 else 0.5
    repair_body = max(
        candidate["selloff_prev_close"] - candidate["selloff_close"],
        0,
    )
    first_repair_price = candidate["selloff_close"] + repair_body * 0.35
    half_repair_price = candidate["selloff_close"] + repair_body * 0.50
    held_selloff_low = low >= candidate["selloff_low"] * 0.985 if low > 0 else False
    vwap_ok = vwap <= 0 or price >= vwap * 0.995
    live_confirmed = bool(
        min(price, open_price, high, low) > 0
        and 1.0 <= pct <= 8.8
        and price >= first_repair_price
        and held_selloff_low
        and vwap_ok
        and close_position >= 0.55
        and amount >= 20_000_000
    )
    return {
        "source_time": source_time,
        "price": round(price, 4),
        "pct": round(pct, 4),
        "open": round(open_price, 4),
        "high": round(high, 4),
        "low": round(low, 4),
        "amount": round(amount, 2),
        "vwap": round(vwap, 4) if vwap > 0 else None,
        "vwap_ok": vwap_ok,
        "held_selloff_low": held_selloff_low,
        "first_repair_price": round(first_repair_price, 4),
        "half_repair_price": round(half_repair_price, 4),
        "repaired_half_body": price >= half_repair_price,
        "close_position": round(close_position, 4),
        "live_repair_confirmation": live_confirmed,
    }


def _snapshot_date(context: dict[str, Any]) -> str:
    value = str((context.get("snapshot") or {}).get("market_date") or "")
    if len(value) == 8 and value.isdigit():
        return f"{value[:4]}-{value[4:6]}-{value[6:8]}"
    return value


def _fallback_market_dates(cache_dir: Path) -> list[str]:
    archive = cache_dir / "archive"
    if not archive.exists():
        return []
    return sorted(
        path.name
        for path in archive.iterdir()
        if path.is_dir() and (path / "market").exists()
    )


def _latest_stock_path(cache_dir: Path, market_date: str) -> Path | None:
    candidates = sorted(
        (cache_dir / "archive" / market_date / "market").glob("*/stocks.ndjson.gz")
    )
    return candidates[-1] if candidates else None


def scan(
    cache_dir: Path,
    mode: str,
    limit: int = 30,
    selloff_date: str = "",
) -> dict[str, Any]:
    context = _read_json(cache_dir / "latest_context.json", {})
    calendar = _read_json(cache_dir / "latest_calendar.json", {})
    snapshot_date = _snapshot_date(context)
    archive_dates = _fallback_market_dates(cache_dir)
    if not selloff_date:
        if mode == "morning":
            current_date = str(calendar.get("current_date") or "")
            previous_trade_day = str(calendar.get("previous_trade_day") or "")
            if snapshot_date == current_date and previous_trade_day:
                selloff_date = previous_trade_day
            elif snapshot_date:
                selloff_date = snapshot_date
            elif len(archive_dates) >= 2:
                selloff_date = archive_dates[-2]
        else:
            selloff_date = snapshot_date or (archive_dates[-1] if archive_dates else "")
    date.fromisoformat(selloff_date)

    paths = _daily_paths(cache_dir, selloff_date, 35)
    series: dict[str, list[dict[str, Any]]] = defaultdict(list)
    names: dict[str, str] = {}
    for market_date, path in paths:
        for row in _read_gzip_rows(path):
            code = get_code(row)
            name = get_name(row)
            if not code or not _ordinary_main_board(code, name):
                continue
            observation = _observation(market_date, row)
            if observation is not None:
                series[code].append(observation)
                names[code] = name

    latest_path_text = (
        context.get("downloads", {}).get("stocks", {}).get("path") or ""
    )
    latest_path = Path(latest_path_text) if latest_path_text else None
    if latest_path is None or not latest_path.exists():
        live_date = snapshot_date or (archive_dates[-1] if archive_dates else "")
        latest_path = _latest_stock_path(cache_dir, live_date) if live_date else None
    latest_rows: dict[str, dict[str, Any]] = {}
    if latest_path and latest_path.exists():
        latest_rows = {
            get_code(row): row
            for row in _read_gzip_rows(latest_path)
            if get_code(row)
        }

    source_time = str(
        (context.get("snapshot") or {}).get("source_time")
        or (context.get("snapshot") or {}).get("captured_at")
        or ""
    )
    candidates: list[dict[str, Any]] = []
    for code, observations in series.items():
        result = evaluate_selloff(code, names[code], observations)
        if result is None:
            continue
        live_row = latest_rows.get(code)
        if live_row is not None and snapshot_date > selloff_date:
            result["live_confirmation"] = evaluate_live_repair(
                result,
                live_row,
                source_time,
            )
        candidates.append(result)

    candidates.sort(
        key=lambda item: (
            bool(
                (item.get("live_confirmation") or {}).get(
                    "live_repair_confirmation"
                )
            ),
            item["objective_score"],
            item["selloff_amount"],
        ),
        reverse=True,
    )
    live_confirmed = [
        item
        for item in candidates
        if (item.get("live_confirmation") or {}).get("live_repair_confirmation")
    ]
    return {
        "schema_version": "1.0",
        "mode": mode,
        "selloff_date": selloff_date,
        "latest_snapshot_id": (context.get("snapshot") or {}).get("snapshot_id"),
        "latest_source_time": source_time or None,
        "history_dates": [day for day, _ in paths],
        "method": (
            "technical discovery only; require A/B+ company quality, intact thesis, "
            "non-fundamental selloff cause, theme or fresh catalyst, hard-risk check, "
            "and live VWAP/repair confirmation"
        ),
        "candidate_count": len(candidates),
        "live_confirmed_count": len(live_confirmed),
        "live_confirmed": live_confirmed[:limit],
        "candidates": candidates[:limit],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scan quality-stock selloffs for next-session repair evidence."
    )
    parser.add_argument("--mode", choices=["morning", "overnight"], required=True)
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR))
    parser.add_argument("--selloff-date", default="")
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()
    result = scan(Path(args.cache_dir), args.mode, args.limit, args.selloff_date)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
