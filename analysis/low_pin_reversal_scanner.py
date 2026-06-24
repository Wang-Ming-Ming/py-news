#!/usr/bin/env python3
"""Discover objective low-position pin-reversal evidence from local server archives."""

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
    if not code.startswith(("000", "001", "002", "003", "600", "601", "603", "605")):
        return False
    upper_name = name.upper()
    return "ST" not in upper_name and "退" not in name


def _market_date_from_path(path: Path) -> str:
    for part in path.parts:
        if len(part) == 10 and part[4] == "-" and part[7] == "-":
            try:
                date.fromisoformat(part)
                return part
            except ValueError:
                pass
    return ""


def _daily_paths(cache_dir: Path, until: str, days: int) -> list[tuple[str, Path]]:
    archive = cache_dir / "archive"
    if not archive.exists():
        return []
    selected: list[tuple[str, Path]] = []
    for day_dir in sorted((path for path in archive.iterdir() if path.is_dir())):
        market_date = day_dir.name
        if market_date > until:
            continue
        candidates = sorted((day_dir / "market").glob("*/stocks.ndjson.gz"))
        if candidates:
            selected.append((market_date, candidates[-1]))
    return selected[-days:]


def _ema(values: list[float], span: int) -> list[float]:
    if not values:
        return []
    alpha = 2 / (span + 1)
    result = [values[0]]
    for value in values[1:]:
        result.append(alpha * value + (1 - alpha) * result[-1])
    return result


def macd(values: list[float]) -> dict[str, Any]:
    if len(values) < 12:
        return {
            "dif": None,
            "dea": None,
            "histogram": None,
            "previous_histogram": None,
            "state": "insufficient_history",
            "slope_up": False,
        }
    ema12 = _ema(values, 12)
    ema26 = _ema(values, 26)
    dif = [fast - slow for fast, slow in zip(ema12, ema26)]
    dea = _ema(dif, 9)
    histogram = [2 * (d - e) for d, e in zip(dif, dea)]
    current = histogram[-1]
    previous = histogram[-2]
    slope_up = dif[-1] > dif[-2] and dea[-1] >= dea[-2]
    if current > 0 >= previous and slope_up:
        state = "red_turn"
    elif current > 0 and current > previous and slope_up:
        state = "red_expanding"
    elif len(histogram) >= 3 and current <= 0 and current > previous > histogram[-3] and dif[-1] > dif[-2]:
        state = "green_contracting"
    elif current > 0:
        state = "red_weakening"
    else:
        state = "green_or_weak"
    return {
        "dif": round(dif[-1], 6),
        "dea": round(dea[-1], 6),
        "histogram": round(current, 6),
        "previous_histogram": round(previous, 6),
        "state": state,
        "slope_up": slope_up,
    }


def _return(closes: list[float], sessions: int) -> float | None:
    if len(closes) <= sessions or closes[-sessions - 1] <= 0:
        return None
    return (closes[-1] / closes[-sessions - 1] - 1) * 100


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _pin_metrics(observations: list[dict[str, Any]], index: int) -> dict[str, Any] | None:
    current = observations[index]
    history = observations[: index + 1]
    closes = [item["close"] for item in history if item["close"] > 0]
    if len(closes) < 12:
        return None
    open_price = current["open"]
    close = current["close"]
    high = current["high"]
    low = current["low"]
    day_range = high - low
    if day_range <= 0 or low <= 0:
        return None

    lower_shadow = (min(open_price, close) - low) / day_range
    upper_shadow = (high - max(open_price, close)) / day_range
    close_position = (close - low) / day_range
    highs = [item["high"] for item in history[-20:] if item["high"] > 0]
    lows = [item["low"] for item in history[-20:] if item["low"] > 0]
    range_high = max(highs) if highs else None
    range_low = min(lows) if lows else None
    range_position = (
        (close - range_low) / (range_high - range_low)
        if range_high is not None and range_low is not None and range_high > range_low
        else None
    )
    prior_lows = [item["low"] for item in history[-4:-1] if item["low"] > 0]
    swept_recent_low = bool(prior_lows and low <= min(prior_lows) * 1.01)
    previous_amounts = [item["amount"] for item in history[-6:-1] if item["amount"] > 0]
    average_amount = _mean(previous_amounts)
    amount_ratio = current["amount"] / average_amount if average_amount else None
    prev_close = current["prev_close"]
    pct = (close / prev_close - 1) * 100 if prev_close > 0 else current["pct"]
    return_5d = _return(closes, 5)
    return_10d = _return(closes, 10)

    hard_shape = all(
        (
            range_position is not None and range_position <= 0.58,
            lower_shadow >= 0.28,
            close_position >= 0.62,
            swept_recent_low,
            current["amount"] >= 50_000_000,
            amount_ratio is None or 0.4 <= amount_ratio <= 3.5,
            return_5d is not None and return_5d <= 15,
            return_10d is not None and return_10d <= 20,
            -4.5 <= pct <= 4.5,
        )
    )
    return {
        "index": index,
        "market_date": current["market_date"],
        "close": close,
        "open": open_price,
        "high": high,
        "low": low,
        "pct": pct,
        "amount": current["amount"],
        "amount_ratio": amount_ratio,
        "lower_shadow": lower_shadow,
        "upper_shadow": upper_shadow,
        "close_position": close_position,
        "recovery_from_low": (close / low - 1) * 100,
        "swept_recent_low": swept_recent_low,
        "range_position": range_position,
        "return_5d": return_5d,
        "return_10d": return_10d,
        "hard_shape": hard_shape,
    }


def evaluate_series(
    code: str,
    name: str,
    observations: list[dict[str, Any]],
    pin_lookback: int = 3,
) -> dict[str, Any] | None:
    if len(observations) < 12:
        return None
    current = observations[-1]
    closes = [item["close"] for item in observations if item["close"] > 0]
    if len(closes) < 12:
        return None

    start_index = max(11, len(observations) - max(pin_lookback, 1))
    pin_rows = [
        metrics
        for index in range(start_index, len(observations))
        if (metrics := _pin_metrics(observations, index)) is not None
    ]
    if not pin_rows:
        return None
    pin = max(
        pin_rows,
        key=lambda item: (
            item["hard_shape"],
            item["lower_shadow"] + item["close_position"] - (item["range_position"] or 1),
        ),
    )

    close = current["close"]
    ma5 = _mean(closes[-5:])
    macd_values = macd(closes)
    prev_close = current["prev_close"]
    current_pct = (close / prev_close - 1) * 100 if prev_close > 0 else current["pct"]
    days_since_pin = len(observations) - 1 - pin["index"]
    histogram = macd_values["histogram"]
    previous_histogram = macd_values["previous_histogram"]
    fast_near_cross = bool(
        histogram is not None
        and previous_histogram is not None
        and histogram <= 0
        and histogram > previous_histogram
        and abs(histogram) <= max(abs(previous_histogram) * 0.55, 0.01)
    )
    breakout_confirmation = bool(
        1 <= days_since_pin <= 2
        and close > pin["high"]
        and ma5 is not None
        and close >= ma5
        and 1.0 <= current_pct <= 8.5
        and current["amount"] >= 50_000_000
        and (macd_values["state"] in {"red_turn", "red_expanding"} or fast_near_cross)
    )
    macd_confirmed = bool(
        macd_values["state"] in {"red_turn", "red_expanding"} and macd_values["slope_up"]
    ) or breakout_confirmation
    scout_only = pin["hard_shape"] and not macd_confirmed and macd_values["state"] == "green_contracting"

    score = 0.0
    position_value = pin["range_position"] if pin["range_position"] is not None else 1.0
    score += max(0.0, 20 * (1 - min(max(position_value, 0), 1)))
    score += min(pin["lower_shadow"] / 0.5, 1.4) * 20
    score += min(pin["close_position"], 1) * 15
    score += 22 if macd_values["state"] == "red_turn" else 17 if macd_values["state"] == "red_expanding" else 9 if scout_only else 0
    score += 12 if breakout_confirmation else 0
    score += 20 if fast_near_cross else 0
    score += 8 if breakout_confirmation and 2 <= current_pct <= 6.5 else 0
    if pin["amount"] > 0:
        current_to_pin_amount = current["amount"] / pin["amount"]
        score += 6 if breakout_confirmation and 1.2 <= current_to_pin_amount <= 3.5 else 0
    else:
        current_to_pin_amount = None
    score += 8 if pin["swept_recent_low"] else 0
    score += 8 if pin["amount_ratio"] is not None and 0.7 <= pin["amount_ratio"] <= 2.2 else 3
    score += 7 if ma5 is not None and close >= ma5 else 0
    score -= max(pin["upper_shadow"] - 0.35, 0) * 20

    return {
        "code": code,
        "name": name,
        "pattern_date": pin["market_date"],
        "confirmation_date": current["market_date"],
        "days_since_pin": days_since_pin,
        "price": round(close, 4),
        "pct": round(current_pct, 4),
        "open": round(pin["open"], 4),
        "high": round(pin["high"], 4),
        "low": round(pin["low"], 4),
        "pin_close": round(pin["close"], 4),
        "pin_pct": round(pin["pct"], 4),
        "lower_shadow_ratio": round(pin["lower_shadow"], 4),
        "upper_shadow_ratio": round(pin["upper_shadow"], 4),
        "close_position_in_range": round(pin["close_position"], 4),
        "recovery_from_low_pct": round(pin["recovery_from_low"], 4),
        "swept_recent_3d_low": pin["swept_recent_low"],
        "range_position_20d": round(pin["range_position"], 4) if pin["range_position"] is not None else None,
        "return_5d": round(pin["return_5d"], 4) if pin["return_5d"] is not None else None,
        "return_10d": round(pin["return_10d"], 4) if pin["return_10d"] is not None else None,
        "amount": round(current["amount"], 2),
        "pin_amount": round(pin["amount"], 2),
        "amount_ratio_5d": round(pin["amount_ratio"], 4) if pin["amount_ratio"] is not None else None,
        "ma5": round(ma5, 4) if ma5 is not None else None,
        "macd": macd_values,
        "history_points": len(observations),
        "shape_pass": pin["hard_shape"],
        "breakout_confirmation": breakout_confirmation,
        "fast_near_cross": fast_near_cross,
        "current_to_pin_amount_ratio": round(current_to_pin_amount, 4) if current_to_pin_amount is not None else None,
        "macd_confirmed": macd_confirmed,
        "scout_only": scout_only,
        "objective_score": round(score, 2),
    }


def _row_observation(market_date: str, row: dict[str, Any]) -> dict[str, Any] | None:
    close = number(row, ["最新价", "收盘"])
    open_price = number(row, ["今开", "开盘"])
    high = number(row, ["最高"])
    low = number(row, ["最低"])
    if min(close, open_price, high, low) <= 0:
        return None
    return {
        "market_date": market_date,
        "close": close,
        "open": open_price,
        "high": high,
        "low": low,
        "prev_close": number(row, ["昨收"]),
        "pct": number(row, ["涨跌幅"]),
        "amount": number(row, ["成交额"]),
        "volume": number(row, ["成交量"]),
    }


def scan(cache_dir: Path, mode: str, limit: int = 30, pattern_date: str = "") -> dict[str, Any]:
    context = _read_json(cache_dir / "latest_context.json", {})
    calendar = _read_json(cache_dir / "latest_calendar.json", {})
    snapshot = context.get("snapshot") or {}
    snapshot_date = str(snapshot.get("market_date") or "")
    if len(snapshot_date) == 8 and snapshot_date.isdigit():
        snapshot_date = f"{snapshot_date[:4]}-{snapshot_date[4:6]}-{snapshot_date[6:8]}"
    if not pattern_date:
        if mode == "morning":
            current_date = str(calendar.get("current_date") or "")
            previous_trade_day = str(calendar.get("previous_trade_day") or "")
            pattern_date = previous_trade_day if snapshot_date == current_date and previous_trade_day else snapshot_date
        else:
            pattern_date = snapshot_date
    date.fromisoformat(pattern_date)

    paths = _daily_paths(cache_dir, pattern_date, 35)
    series: dict[str, list[dict[str, Any]]] = defaultdict(list)
    names: dict[str, str] = {}
    for market_date, path in paths:
        for row in _read_gzip_rows(path):
            code = get_code(row)
            name = get_name(row)
            if not code or not _ordinary_main_board(code, name):
                continue
            observation = _row_observation(market_date, row)
            if observation is not None:
                series[code].append(observation)
                names[code] = name

    latest_rows: dict[str, dict[str, Any]] = {}
    latest_path_text = context.get("downloads", {}).get("stocks", {}).get("path") or ""
    latest_path = Path(latest_path_text) if latest_path_text else None
    if latest_path and latest_path.exists():
        latest_rows = {get_code(row): row for row in _read_gzip_rows(latest_path) if get_code(row)}

    candidates: list[dict[str, Any]] = []
    for code, observations in series.items():
        result = evaluate_series(code, names[code], observations)
        if result is None or not result["shape_pass"]:
            continue
        current = latest_rows.get(code)
        if current is not None:
            result["latest_confirmation"] = {
                "source_time": snapshot.get("source_time") or snapshot.get("captured_at"),
                "price": number(current, ["最新价", "收盘"]),
                "pct": number(current, ["涨跌幅"]),
                "open": number(current, ["今开", "开盘"]),
                "high": number(current, ["最高"]),
                "low": number(current, ["最低"]),
                "amount": number(current, ["成交额"]),
            }
            result["live_breakout_confirmation"] = False
            if mode == "morning" and snapshot_date and snapshot_date > pattern_date:
                live_observation = _row_observation(snapshot_date, current)
                if live_observation is not None:
                    live_result = evaluate_series(code, names[code], observations + [live_observation])
                    if live_result is not None and live_result["pattern_date"] == result["pattern_date"]:
                        result["live_breakout_confirmation"] = live_result["breakout_confirmation"]
                        result["live_macd"] = live_result["macd"]
                        result["live_confirmation_score"] = live_result["objective_score"]
        candidates.append(result)

    candidates.sort(
        key=lambda item: (
            item.get("live_breakout_confirmation", False),
            item["breakout_confirmation"],
            item["macd_confirmed"],
            item["objective_score"],
            item["amount"],
        ),
        reverse=True,
    )
    confirmed = [item for item in candidates if item["macd_confirmed"]]
    scouts = [item for item in candidates if not item["macd_confirmed"]]
    recent_pin_breakouts = sorted(
        (item for item in candidates if item["breakout_confirmation"]),
        key=lambda item: (item["objective_score"], item["amount"]),
        reverse=True,
    )
    live_breakouts = sorted(
        (item for item in candidates if item.get("live_breakout_confirmation")),
        key=lambda item: (item.get("live_confirmation_score", 0), item["objective_score"]),
        reverse=True,
    )
    return {
        "schema_version": "1.0",
        "mode": mode,
        "pattern_date": pattern_date,
        "latest_snapshot_id": snapshot.get("snapshot_id"),
        "latest_source_time": snapshot.get("source_time") or snapshot.get("captured_at"),
        "history_dates": [day for day, _ in paths],
        "method": "objective discovery only; Codex must verify news, theme, risk, and tape",
        "confirmed_count": len(confirmed),
        "scout_count": len(scouts),
        "recent_pin_breakout_count": len(recent_pin_breakouts),
        "live_breakout_count": len(live_breakouts),
        "recent_pin_breakouts": recent_pin_breakouts[:limit],
        "live_breakouts": live_breakouts[:limit],
        "confirmed": confirmed[:limit],
        "scouts": scouts[:limit],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan low-position pin-reversal evidence.")
    parser.add_argument("--mode", choices=["morning", "overnight"], required=True)
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR))
    parser.add_argument("--pattern-date", default="")
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()
    result = scan(Path(args.cache_dir), args.mode, args.limit, args.pattern_date)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
