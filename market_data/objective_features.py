"""Compute objective multi-day price/volume fields from saved market snapshots."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from market_data.market_filters import get_code, get_name
from market_data.market_derivation import number


def _snapshot_time(payload: dict[str, Any]) -> datetime:
    value = payload.get("metadata", {}).get("captured_at") or ""
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.min


def load_snapshot(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def discover_daily_snapshots(market_dir: str | Path, days: int = 20) -> list[dict[str, Any]]:
    root = Path(market_dir)
    selected: list[dict[str, Any]] = []
    for date_dir in sorted((path for path in root.iterdir() if path.is_dir()), reverse=True):
        candidates: list[dict[str, Any]] = []
        for path in date_dir.glob("*_snapshot.json"):
            if "failed" in path.name:
                continue
            try:
                payload = load_snapshot(path)
            except (OSError, json.JSONDecodeError):
                continue
            summary = payload.get("derived", {}).get("summary", {})
            if int(summary.get("stock_count") or 0) < 1000:
                continue
            candidates.append(payload)
        if candidates:
            selected.append(max(candidates, key=_snapshot_time))
        if len(selected) >= days:
            break
    return list(reversed(selected))


def _record_map(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = snapshot.get("raw", {}).get("stock_spot", [])
    return {get_code(row): row for row in rows if get_code(row)}


def _mean(values: Iterable[float]) -> float | None:
    rows = list(values)
    return sum(rows) / len(rows) if rows else None


def _round(value: float | None, digits: int = 4) -> float | None:
    return round(value, digits) if value is not None else None


def _return(closes: list[float], window: int) -> float | None:
    if len(closes) < window + 1 or closes[-(window + 1)] <= 0:
        return None
    return (closes[-1] / closes[-(window + 1)] - 1) * 100


def _moving_average(values: list[float], window: int) -> float | None:
    return _mean(values[-window:]) if len(values) >= window else None


def _average_true_range(observations: list[tuple[str, dict[str, Any]]], window: int = 14) -> float | None:
    ranges: list[float] = []
    previous_close: float | None = None
    for _, row in observations:
        high = number(row, ["最高"])
        low = number(row, ["最低"])
        close = number(row, ["最新价", "收盘"])
        source_previous_close = number(row, ["昨收"])
        reference_close = source_previous_close if source_previous_close > 0 else previous_close
        if high > 0 and low > 0 and high >= low:
            candidates = [high - low]
            if reference_close and reference_close > 0:
                candidates.extend((abs(high - reference_close), abs(low - reference_close)))
            ranges.append(max(candidates))
        if close > 0:
            previous_close = close
    return _mean(ranges[-window:]) if len(ranges) >= window else None


def _consecutive_increases(values: list[float]) -> int:
    count = 0
    for index in range(len(values) - 1, 0, -1):
        previous = values[index - 1]
        current = values[index]
        if previous <= 0 or current <= previous:
            break
        count += 1
    return count


def build_objective_features(
    current_snapshot: dict[str, Any],
    history_snapshots: list[dict[str, Any]],
) -> dict[str, Any]:
    snapshots = list(history_snapshots)
    current_id = current_snapshot.get("metadata", {}).get("snapshot_id")
    if not snapshots or snapshots[-1].get("metadata", {}).get("snapshot_id") != current_id:
        snapshots.append(current_snapshot)

    dated_maps: list[tuple[str, dict[str, dict[str, Any]]]] = []
    seen_dates: set[str] = set()
    for snapshot in snapshots:
        market_date = str(snapshot.get("metadata", {}).get("market_date") or "")
        market_date = f"{market_date[:4]}-{market_date[4:6]}-{market_date[6:8]}" if len(market_date) == 8 else market_date
        if not market_date:
            continue
        mapping = _record_map(snapshot)
        if market_date in seen_dates:
            dated_maps = [(day, rows) for day, rows in dated_maps if day != market_date]
        dated_maps.append((market_date, mapping))
        seen_dates.add(market_date)

    current_rows = _record_map(current_snapshot)
    features: list[dict[str, Any]] = []
    for code, current in current_rows.items():
        observations: list[tuple[str, dict[str, Any]]] = [
            (day, rows[code]) for day, rows in dated_maps if code in rows
        ]
        closes = [number(row, ["最新价", "收盘"]) for _, row in observations]
        closes = [value for value in closes if value > 0]
        amounts = [number(row, ["成交额"]) for _, row in observations]
        volumes = [number(row, ["成交量"]) for _, row in observations]
        highs = [number(row, ["最高"]) for _, row in observations]
        lows = [number(row, ["最低"]) for _, row in observations]
        price = number(current, ["最新价", "收盘"])
        open_price = number(current, ["今开", "开盘"])
        high = number(current, ["最高"])
        low = number(current, ["最低"])
        amount = number(current, ["成交额"])
        volume = number(current, ["成交量"])
        average_amount_5d = _mean(amounts[-6:-1]) if len(amounts) >= 6 else None
        average_volume_5d = _mean(volumes[-6:-1]) if len(volumes) >= 6 else None
        range_high_15d = max((value for value in highs[-15:] if value > 0), default=None)
        range_low_15d = min((value for value in lows[-15:] if value > 0), default=None)
        range_position = None
        if range_high_15d is not None and range_low_15d is not None and range_high_15d > range_low_15d:
            range_position = (price - range_low_15d) / (range_high_15d - range_low_15d)
        day_range = high - low
        upper_shadow = (high - max(open_price, price)) / day_range if day_range > 0 else None
        lower_shadow = (min(open_price, price) - low) / day_range if day_range > 0 else None
        body_ratio = abs(price - open_price) / day_range if day_range > 0 else None
        atr14 = _average_true_range(observations)

        features.append(
            {
                "code": code,
                "name": get_name(current),
                "price": price,
                "pct": number(current, ["涨跌幅"]),
                "amount": amount,
                "volume": volume,
                "turnover": number(current, ["换手率"]),
                "volume_ratio": number(current, ["量比"]),
                "amplitude": number(current, ["振幅"]),
                "open": open_price,
                "high": high,
                "low": low,
                "prev_close": number(current, ["昨收"]),
                "ma5": _round(_moving_average(closes, 5)),
                "ma10": _round(_moving_average(closes, 10)),
                "ma15": _round(_moving_average(closes, 15)),
                "ma20": _round(_moving_average(closes, 20)),
                "return_5d": _round(_return(closes, 5)),
                "return_10d": _round(_return(closes, 10)),
                "return_15d": _round(_return(closes, 15)),
                "average_amount_5d": _round(average_amount_5d, 2),
                "amount_ratio_5d": _round(amount / average_amount_5d if average_amount_5d else None),
                "average_volume_5d": _round(average_volume_5d, 2),
                "volume_ratio_5d": _round(volume / average_volume_5d if average_volume_5d else None),
                "consecutive_amount_increases": _consecutive_increases(amounts),
                "consecutive_volume_increases": _consecutive_increases(volumes),
                "atr14": _round(atr14),
                "atr14_pct": _round(atr14 / price * 100 if atr14 is not None and price > 0 else None),
                "range_high_15d": _round(range_high_15d),
                "range_low_15d": _round(range_low_15d),
                "range_position_15d": _round(range_position),
                "upper_shadow_ratio": _round(upper_shadow),
                "lower_shadow_ratio": _round(lower_shadow),
                "body_ratio": _round(body_ratio),
                "history_points": len(observations),
                "history_dates": [day for day, _ in observations[-15:]],
                "recent_high_series": [
                    {"market_date": day, "high": _round(number(row, ["最高"]))}
                    for day, row in observations[-15:]
                ],
                "recent_low_series": [
                    {"market_date": day, "low": _round(number(row, ["最低"]))}
                    for day, row in observations[-15:]
                ],
            }
        )

    return {
        "schema_version": "1.0",
        "snapshot_id": current_snapshot.get("metadata", {}).get("snapshot_id"),
        "source_time": current_snapshot.get("metadata", {}).get("source_time")
        or current_snapshot.get("metadata", {}).get("captured_at"),
        "stock_count": len(features),
        "history_dates": [day for day, _ in dated_maps[-15:]],
        "units": {
            "price": "CNY_per_share",
            "pct": "percent",
            "amount": "CNY",
            "volume": "source_native_shares_or_lots",
            "turnover": "percent",
            "amplitude": "percent",
            "ratios": "decimal_ratio",
        },
        "data": features,
    }
