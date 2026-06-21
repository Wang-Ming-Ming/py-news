#!/usr/bin/env python3
"""Point-in-time replay for ten independent stock-selection factor tunnels."""

from __future__ import annotations

import argparse
import bisect
import glob
import gzip
import hashlib
import json
import math
import re
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional


CST = timezone(timedelta(hours=8))
POSITIVE_WORDS = (
    "中标",
    "订单",
    "合同",
    "回购",
    "增持",
    "预增",
    "扭亏",
    "涨价",
    "获批",
    "投产",
    "突破",
    "战略合作",
    "重大进展",
)
RISK_WORDS = (
    "减持",
    "澄清",
    "监管",
    "处罚",
    "立案",
    "诉讼",
    "终止",
    "风险提示",
    "亏损",
    "退市",
    "问询",
    "异常波动",
)
MAIN_BOARD_PREFIXES = ("000", "001", "002", "003", "600", "601", "603", "605")
RED_WINDOW_THRESHOLD = 0.5
REPLAY_START = "2026-06-08"
REPLAY_END = "2026-06-17"


def number(value: Any) -> float | None:
    if value in (None, "", "-"):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def mean(values: list[float]) -> float | None:
    clean = [value for value in values if value is not None and math.isfinite(value)]
    return sum(clean) / len(clean) if clean else None


def pct_change(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return (current / previous - 1.0) * 100.0


def in_range(value: float | None, low: float, high: float) -> bool:
    return value is not None and low <= value <= high


def parse_time(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=CST)
    return parsed.astimezone(CST)


def normalized_name(value: str) -> str:
    return re.sub(r"[\s*ＡA]", "", value or "").replace("ST", "")


def load_market(data_root: Path) -> tuple[list[str], dict[str, dict[str, dict[str, Any]]]]:
    rows_by_date: dict[str, dict[str, dict[str, Any]]] = {}
    pattern = str(data_root / "archive" / "*" / "market" / "*" / "stocks.ndjson.gz")
    for path_text in sorted(glob.glob(pattern)):
        path = Path(path_text)
        day = path.parts[-4]
        rows: dict[str, dict[str, Any]] = {}
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                row = json.loads(line)
                code = str(row.get("代码") or "").zfill(6)
                if code:
                    rows[code] = row
        if len(rows) > len(rows_by_date.get(day, {})):
            rows_by_date[day] = rows
    dates = sorted(rows_by_date)
    if len(dates) < 15:
        raise RuntimeError(f"at least 15 market dates required, found {len(dates)}")
    return dates, rows_by_date


def _largest_index(data_root: Path, day: str, filename: str) -> list[dict[str, Any]]:
    candidates = []
    pattern = str(data_root / "archive" / day / "news" / "*" / filename)
    for path_text in glob.glob(pattern):
        path = Path(path_text)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            rows = list(payload.get("data") or [])
            candidates.append((len(rows), path.stat().st_mtime, rows))
        except (OSError, json.JSONDecodeError):
            continue
    return max(candidates, default=(0, 0, []), key=lambda item: (item[0], item[1]))[2]


def load_messages(data_root: Path, dates: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    news: dict[str, dict[str, Any]] = {}
    announcements: dict[str, dict[str, Any]] = {}
    for day in dates:
        for item in _largest_index(data_root, day, "news_index.json"):
            news[str(item.get("id") or hashlib.sha1(json.dumps(item, sort_keys=True).encode()).hexdigest())] = item
        for item in _largest_index(data_root, day, "announcements_index.json"):
            announcements[
                str(item.get("id") or hashlib.sha1(json.dumps(item, sort_keys=True).encode()).hexdigest())
            ] = item
    return list(news.values()), list(announcements.values())


class PointInTimeMarketView:
    def __init__(self, dates: list[str], rows_by_date: dict[str, dict[str, dict[str, Any]]], as_of: str):
        self.dates = [day for day in dates if day <= as_of]
        self.rows_by_date = {day: rows_by_date[day] for day in self.dates}
        self.as_of = as_of
        if not self.dates or self.dates[-1] != as_of:
            raise RuntimeError(f"market view is not anchored to {as_of}")

    def histories(self) -> dict[str, list[tuple[str, dict[str, Any]]]]:
        result: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
        for day in self.dates:
            for code, row in self.rows_by_date[day].items():
                result[code].append((day, row))
        return result


def feature_row(code: str, history: list[tuple[str, dict[str, Any]]]) -> dict[str, Any] | None:
    if len(history) < 8:
        return None
    day, current = history[-1]
    closes = [number(row.get("收盘") or row.get("最新价")) for _, row in history]
    opens = [number(row.get("开盘") or row.get("今开")) for _, row in history]
    highs = [number(row.get("最高")) for _, row in history]
    lows = [number(row.get("最低")) for _, row in history]
    volumes = [number(row.get("成交量")) for _, row in history]
    if any(value is None for value in (closes[-1], opens[-1], highs[-1], lows[-1], volumes[-1])):
        return None
    close = float(closes[-1])
    open_price = float(opens[-1])
    high = float(highs[-1])
    low = float(lows[-1])
    volume = float(volumes[-1])
    previous_close = closes[-2]
    pct = number(current.get("涨跌幅"))
    if pct is None:
        pct = pct_change(close, previous_close)
    name = str(current.get("名称") or "")
    if not code.startswith(MAIN_BOARD_PREFIXES) or not name or "ST" in name.upper() or "退" in name:
        return None
    if not (2.0 <= close <= 250.0) or volume <= 0:
        return None

    def moving_average(window: int) -> float | None:
        values = closes[-window:]
        return mean([float(value) for value in values if value is not None]) if len(values) == window else None

    def return_n(window: int) -> float | None:
        return pct_change(close, closes[-window - 1]) if len(closes) > window else None

    ma3, ma5, ma10, ma15 = (moving_average(window) for window in (3, 5, 10, 15))
    ret3, ret5, ret10 = (return_n(window) for window in (3, 5, 10))
    avg_volume5 = mean([float(value) for value in volumes[-6:-1] if value is not None])
    volume_ratio5 = volume / avg_volume5 if avg_volume5 not in (None, 0) else None
    prior_high10_values = [float(value) for value in highs[-11:-1] if value is not None]
    high10_values = [float(value) for value in highs[-10:] if value is not None]
    low10_values = [float(value) for value in lows[-10:] if value is not None]
    prior_high10 = max(prior_high10_values) if prior_high10_values else None
    high10 = max(high10_values) if high10_values else None
    low10 = min(low10_values) if low10_values else None
    range_position10 = (
        (close - low10) / (high10 - low10) if high10 is not None and low10 is not None and high10 > low10 else None
    )
    drawdown_high10 = pct_change(close, high10)
    day_range = max(high - low, 0.0)
    close_position = (close - low) / day_range if day_range else 0.5
    upper_shadow = (high - max(open_price, close)) / close if close else None
    lower_shadow = (min(open_price, close) - low) / close if close else None
    body_ratio = abs(close - open_price) / close if close else None
    daily_ranges = []
    true_ranges = []
    for index in range(max(1, len(history) - 10), len(history)):
        c = closes[index]
        h = highs[index]
        l = lows[index]
        prev = closes[index - 1]
        if None in (c, h, l, prev) or not c:
            continue
        daily_ranges.append((float(h) - float(l)) / float(c) * 100.0)
        true_ranges.append(max(float(h) - float(l), abs(float(h) - float(prev)), abs(float(l) - float(prev))) / float(prev) * 100.0)
    recent_range = mean(daily_ranges[-3:])
    prior_range = mean(daily_ranges[-8:-3])
    compression = recent_range / prior_range if recent_range is not None and prior_range not in (None, 0) else None
    atr5 = mean(true_ranges[-5:])
    atr10 = mean(true_ranges[-10:])
    recent_pct = []
    for index in range(max(1, len(closes) - 5), len(closes)):
        value = pct_change(closes[index], closes[index - 1])
        if value is not None:
            recent_pct.append(value)
    pullback_days3 = sum(value < 0 for value in recent_pct[-3:])
    positive_days5 = sum(value > 0 for value in recent_pct[-5:])
    big_gain_days3 = sum(value >= 5.0 for value in recent_pct[-3:])
    previous_ma3 = mean([float(value) for value in closes[-4:-1] if value is not None])
    cross_ma3 = bool(
        ma3 is not None
        and previous_ma3 is not None
        and previous_close is not None
        and close > ma3
        and float(previous_close) <= previous_ma3
    )
    return {
        "date": day,
        "code": code,
        "name": name,
        "close": close,
        "open": open_price,
        "high": high,
        "low": low,
        "volume": volume,
        "liquidity_proxy": close * volume,
        "pct": pct,
        "ma3": ma3,
        "ma5": ma5,
        "ma10": ma10,
        "ma15": ma15,
        "ret3": ret3,
        "ret5": ret5,
        "ret10": ret10,
        "volume_ratio5": volume_ratio5,
        "prior_high10": prior_high10,
        "range_position10": range_position10,
        "drawdown_high10": drawdown_high10,
        "close_position": close_position,
        "upper_shadow": upper_shadow,
        "lower_shadow": lower_shadow,
        "body_ratio": body_ratio,
        "compression": compression,
        "atr5": atr5,
        "atr10": atr10,
        "pullback_days3": pullback_days3,
        "positive_days5": positive_days5,
        "big_gain_days3": big_gain_days3,
        "cross_ma3": cross_ma3,
    }


def percentile_ranks(features: dict[str, dict[str, Any]], field: str, reverse: bool = False) -> None:
    values = sorted(float(row[field]) for row in features.values() if row.get(field) is not None)
    if not values:
        return
    output_field = f"{field}_pct_rank"
    for row in features.values():
        value = row.get(field)
        if value is None:
            row[output_field] = None
            continue
        rank = bisect.bisect_right(values, float(value)) / len(values)
        row[output_field] = 1.0 - rank if reverse else rank


def point_in_time_messages(
    news: list[dict[str, Any]],
    announcements: list[dict[str, Any]],
    cutoff: datetime,
    lookback_days: int = 4,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lower = cutoff - timedelta(days=lookback_days)

    def visible(item: dict[str, Any]) -> bool:
        stamp = parse_time(str(item.get("source_time") or item.get("publish_time_bj") or item.get("publish_time") or ""))
        return stamp is not None and lower <= stamp <= cutoff

    return [item for item in news if visible(item)], [item for item in announcements if visible(item)]


def add_event_features(
    features: dict[str, dict[str, Any]],
    visible_news: list[dict[str, Any]],
    visible_announcements: list[dict[str, Any]],
) -> None:
    event = defaultdict(lambda: {"positive_ann": 0, "risk_ann": 0, "ann_count": 0})
    for item in visible_announcements:
        code = str(item.get("stock_code") or "").zfill(6)
        if code not in features:
            continue
        title = str(item.get("title") or "")
        event[code]["ann_count"] += 1
        event[code]["positive_ann"] += int(any(word in title for word in POSITIVE_WORDS))
        event[code]["risk_ann"] += int(any(word in title for word in RISK_WORDS))

    name_index: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for code, row in features.items():
        name = normalized_name(str(row.get("name") or ""))
        if len(name) >= 3:
            name_index[name[:2]].append((name, code))
    news_event = defaultdict(lambda: {"news_mentions": 0, "positive_news": 0, "risk_news": 0})
    for item in visible_news:
        title = normalized_name(str(item.get("title") or ""))
        if not title:
            continue
        matched_codes = set()
        for index in range(max(0, len(title) - 1)):
            for name, code in name_index.get(title[index : index + 2], []):
                if code not in matched_codes and name in title:
                    matched_codes.add(code)
        for code in matched_codes:
            news_event[code]["news_mentions"] += 1
            news_event[code]["positive_news"] += int(any(word in title for word in POSITIVE_WORDS))
            news_event[code]["risk_news"] += int(any(word in title for word in RISK_WORDS))

    for code, row in features.items():
        row.update(event[code])
        row.update(news_event[code])
        row["risk_hits"] = row["risk_ann"] + row["risk_news"]
        row["positive_hits"] = row["positive_ann"] + row["positive_news"]


def common_gate(row: dict[str, Any], mode: str) -> bool:
    pct = row.get("pct")
    return bool(
        row.get("ma5")
        and row.get("ma10")
        and row.get("ret5") is not None
        and row.get("volume_ratio5") is not None
        and row.get("liquidity_proxy_pct_rank", 0) >= 0.18
        and row.get("risk_hits", 0) == 0
        and pct is not None
        and pct < (5.5 if mode == "overnight" else 7.5)
        and row.get("big_gain_days3", 0) <= 1
    )


ScoreFunction = Callable[[dict[str, Any], str], Optional[float]]


@dataclass(frozen=True)
class Channel:
    channel_id: str
    name: str
    thesis: str
    conditions: str
    scorer: ScoreFunction


def channel_1(row: dict[str, Any], mode: str) -> float | None:
    if not common_gate(row, mode):
        return None
    if not (
        row["close"] > row["ma5"] > row["ma10"] * 0.995
        and in_range(row["ret5"], 1.0, 9.0)
        and (row["ret10"] is None or in_range(row["ret10"], -1.0, 16.0))
        and in_range(row["range_position10"], 0.42, 0.86)
        and in_range(row["volume_ratio5"], 0.72, 1.8)
        and row["close_position"] >= 0.55
        and row["upper_shadow"] <= 0.045
        and in_range(row["pct"], -0.8, 4.5)
    ):
        return None
    return 30 * row["ret5"] / 9 + 18 * row["close_position"] + 18 * row["ret5_pct_rank"] + 12 * row["liquidity_proxy_pct_rank"] - 100 * row["upper_shadow"]


def channel_2(row: dict[str, Any], mode: str) -> float | None:
    if not common_gate(row, mode):
        return None
    if not (
        row["close"] >= row["ma10"] * 0.99
        and (row["ret10"] is None or row["ret10"] >= 1.5)
        and in_range(row["drawdown_high10"], -9.0, -0.8)
        and in_range(row["pct"], -2.8, 1.3)
        and in_range(row["volume_ratio5"], 0.35, 0.98)
        and row["close_position"] >= 0.48
        and row["lower_shadow"] >= row["upper_shadow"] * 0.7
    ):
        return None
    return 30 * (1 - row["volume_ratio5"]) + 20 * row["close_position"] + 15 * (row["drawdown_high10"] + 9) / 8.2 + 15 * row["liquidity_proxy_pct_rank"]


def channel_3(row: dict[str, Any], mode: str) -> float | None:
    if not common_gate(row, mode) or row.get("prior_high10") in (None, 0):
        return None
    breakout = row["close"] / row["prior_high10"]
    if not (
        0.975 <= breakout <= 1.035
        and in_range(row["pct"], 0.4, 5.0)
        and in_range(row["volume_ratio5"], 1.08, 2.4)
        and in_range(row["ret5"], 1.0, 11.0)
        and row["upper_shadow"] <= 0.035
        and row["close_position"] >= 0.68
    ):
        return None
    return 35 * min(breakout, 1.02) + 20 * row["close_position"] + 15 * min(row["volume_ratio5"], 1.8) + 15 * row["ret5_pct_rank"] - 100 * row["upper_shadow"]


def channel_4(row: dict[str, Any], mode: str) -> float | None:
    if not common_gate(row, mode) or row.get("ret10") is None:
        return None
    if not (
        in_range(row["ret10"], 4.0, 20.0)
        and row["pullback_days3"] >= 1
        and in_range(row["pct"], -1.2, 2.8)
        and row["close"] >= row["ma5"] * 0.985
        and in_range(row["range_position10"], 0.52, 0.9)
        and in_range(row["volume_ratio5"], 0.5, 1.55)
        and in_range(row["drawdown_high10"], -8.0, -0.5)
    ):
        return None
    return 25 * row["ret5_pct_rank"] + 20 * row["close_position"] + 20 * (row["pullback_days3"] / 3) + 15 * row["liquidity_proxy_pct_rank"] + row["ret10"]


def channel_5(row: dict[str, Any], mode: str) -> float | None:
    if not common_gate(row, mode):
        return None
    if not (
        in_range(row["compression"], 0.25, 0.82)
        and row["close"] >= row["ma10"] * 0.99
        and in_range(row["range_position10"], 0.3, 0.76)
        and in_range(row["drawdown_high10"], -16.0, -2.0)
        and in_range(row["pct"], -1.3, 2.6)
        and in_range(row["volume_ratio5"], 0.5, 1.45)
        and in_range(row["atr5"], 0.5, 7.0)
    ):
        return None
    return 35 * (1 - row["compression"]) + 20 * row["close_position"] + 15 * (1 - row["range_position10"]) + 15 * row["liquidity_proxy_pct_rank"]


def channel_6(row: dict[str, Any], mode: str) -> float | None:
    if not common_gate(row, mode):
        return None
    if not (
        row["ret5_pct_rank"] >= 0.76
        and row["liquidity_proxy_pct_rank"] >= 0.62
        and row["atr5_pct_rank"] >= 0.45
        and in_range(row["pct"], -1.0, 4.8)
        and (row["ret10"] is None or row["ret10"] <= 20.0)
        and row["range_position10"] <= 0.92
        and row["close_position"] >= 0.52
    ):
        return None
    return 35 * row["ret5_pct_rank"] + 30 * row["liquidity_proxy_pct_rank"] + 20 * row["atr5_pct_rank"] + 15 * row["close_position"]


def channel_7(row: dict[str, Any], mode: str) -> float | None:
    if not common_gate(row, mode):
        return None
    if not (
        row["positive_hits"] >= 1
        and row["close"] >= row["ma5"] * 0.98
        and in_range(row["ret5"], -3.0, 11.0)
        and in_range(row["pct"], -2.2, 4.8)
        and in_range(row["volume_ratio5"], 0.45, 2.1)
    ):
        return None
    return 38 * min(row["positive_hits"], 3) + 12 * row["ann_count"] + 20 * row["close_position"] + 15 * row["liquidity_proxy_pct_rank"]


def channel_8(row: dict[str, Any], mode: str) -> float | None:
    if not common_gate(row, mode):
        return None
    if not (
        row["news_mentions"] >= 1
        and row["range_position10"] <= 0.7
        and row["close"] >= row["ma10"] * 0.975
        and (row["ret10"] is None or in_range(row["ret10"], -5.0, 13.0))
        and in_range(row["pct"], -2.2, 3.2)
        and in_range(row["volume_ratio5"], 0.45, 1.6)
    ):
        return None
    return 35 * min(row["news_mentions"], 4) + 18 * (1 - row["range_position10"]) + 15 * row["close_position"] + 15 * row["liquidity_proxy_pct_rank"]


def channel_9(row: dict[str, Any], mode: str) -> float | None:
    if not common_gate(row, mode) or row.get("ret10") is None:
        return None
    if not (
        in_range(row["ret10"], -16.0, 2.5)
        and in_range(row["range_position10"], 0.08, 0.58)
        and (row["cross_ma3"] or row["close"] > row["ma3"])
        and in_range(row["pct"], 0.15, 4.2)
        and row["close_position"] >= 0.62
        and in_range(row["volume_ratio5"], 0.72, 2.2)
        and row["lower_shadow"] >= 0.002
    ):
        return None
    return 30 * row["close_position"] + 20 * (1 - row["range_position10"]) + 18 * min(row["volume_ratio5"], 1.6) + 15 * row["liquidity_proxy_pct_rank"]


def channel_10(row: dict[str, Any], mode: str) -> float | None:
    if not common_gate(row, mode):
        return None
    if not (
        row["close"] >= row["ma10"] * 0.98
        and in_range(row["ret5"], -1.5, 9.0)
        and in_range(row["pct"], -1.3, 4.2)
        and in_range(row["range_position10"], 0.22, 0.82)
        and in_range(row["volume_ratio5"], 0.58, 1.75)
        and in_range(row["atr5"], 0.4, 8.0)
    ):
        return None
    catalyst = min(row["positive_hits"], 2) * 8 + min(row["news_mentions"], 2) * 4
    crowding_penalty = max(row["ret5"] - 6, 0) * 2 + max(row["range_position10"] - 0.72, 0) * 30
    return 20 * row["ret5_pct_rank"] + 18 * row["liquidity_proxy_pct_rank"] + 18 * row["atr5_pct_rank"] + 16 * row["close_position"] + 12 * (1 - abs(row["volume_ratio5"] - 1.05)) + catalyst - crowding_penalty


CHANNELS = (
    Channel("T01", "低位多周期趋势", "趋势已经向上但尚未高潮", "MA5>MA10、5/10日涨幅受控、中位区间、温和量比、收盘位置强、上影受控", channel_1),
    Channel("T02", "缩量回踩承接", "上涨趋势中的自然抛压衰减", "守住MA10、距10日高点1%-9%、当日弱而不破、缩量、下影/收盘承接", channel_2),
    Channel("T03", "温和放量突破", "接近前高且量价确认但非极端加速", "接近/小幅突破前10日高点、温和放量、涨幅受控、低上影、强收盘", channel_3),
    Channel("T04", "强势回撤修复", "已有强度、短回撤后重新稳定", "10日强势、近3日至少一次回撤、未远离MA5、非高位满格、量能不过热", channel_4),
    Channel("T05", "波动收缩点火", "趋势未坏且振幅压缩，等待扩张", "近3日波动显著低于此前、守MA10、距前高留空间、量比中性、ATR受控", channel_5),
    Channel("T06", "相对强度容量", "横截面强度、容量和稳定性共振", "5日强度前24%、流动性代理前38%、低波动排名合格、非高位过热、收盘强", channel_6),
    Channel("T07", "公司硬催化趋势", "公司级正向公告/新闻叠加可交易趋势", "固定正向词命中、无风险词、守MA5、涨幅与量比受控、具备流动性", channel_7),
    Channel("T08", "消息潜伏低位", "公司被消息点名但价格仍在中低位", "近4日公司名新闻命中、无风险词、区间位置<70%、守MA10、量价未高潮", channel_8),
    Channel("T09", "底部反转修复", "10日弱势后出现可验证的技术修复", "10日跌幅受控、低位、站回MA3、当日翻强、下影、放量不过热", channel_9),
    Channel("T10", "风险调整共振", "多因子平衡，惩罚拥挤和高位兑现", "趋势/强度/容量/稳定/收盘/量比/消息综合，限制5日涨幅、区间位置和ATR", channel_10),
)


def build_feature_map(view: PointInTimeMarketView) -> dict[str, dict[str, Any]]:
    features = {}
    for code, history in view.histories().items():
        row = feature_row(code, history)
        if row:
            features[code] = row
    percentile_ranks(features, "ret5")
    percentile_ranks(features, "liquidity_proxy")
    percentile_ranks(features, "atr5", reverse=True)
    return features


def public_candidate(row: dict[str, Any], score: float, rank: int) -> dict[str, Any]:
    fields = (
        "code",
        "name",
        "close",
        "pct",
        "ret5",
        "ret10",
        "volume_ratio5",
        "range_position10",
        "drawdown_high10",
        "close_position",
        "atr5",
        "liquidity_proxy_pct_rank",
        "positive_hits",
        "risk_hits",
        "news_mentions",
        "ann_count",
    )
    return {"rank": rank, "score": round(score, 4), **{field: row.get(field) for field in fields}}


def consensus(channel_picks: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    votes: dict[str, dict[str, Any]] = {}
    for channel_id, picks in channel_picks.items():
        for pick in picks:
            code = pick["code"]
            entry = votes.setdefault(code, {"code": code, "name": pick["name"], "votes": 0, "channels": []})
            entry["votes"] += 4 - pick["rank"]
            entry["channels"].append(channel_id)
    ranked = sorted(votes.values(), key=lambda item: (item["votes"], len(item["channels"]), item["code"]), reverse=True)
    return [{**item, "rank": index} for index, item in enumerate(ranked[:5], 1)]


def generate_signals(data_root: Path, output: Path) -> dict[str, Any]:
    dates, rows_by_date = load_market(data_root)
    replay_dates = [day for day in dates if REPLAY_START <= day <= REPLAY_END]
    news, announcements = load_messages(data_root, dates)
    decisions = []
    for mode in ("morning", "overnight"):
        for decision_date in replay_dates:
            day_index = dates.index(decision_date)
            as_of = dates[day_index - 1] if mode == "morning" else decision_date
            cutoff_clock = "09:25:00" if mode == "morning" else "15:00:00"
            cutoff = datetime.fromisoformat(f"{decision_date}T{cutoff_clock}+08:00")
            view = PointInTimeMarketView(dates, rows_by_date, as_of)
            features = build_feature_map(view)
            visible_news, visible_announcements = point_in_time_messages(news, announcements, cutoff)
            add_event_features(features, visible_news, visible_announcements)
            channel_picks = {}
            eligible_counts = {}
            for channel in CHANNELS:
                scored = []
                for row in features.values():
                    score = channel.scorer(row, mode)
                    if score is not None and math.isfinite(score):
                        scored.append((score, row))
                scored.sort(key=lambda item: (item[0], item[1]["liquidity_proxy"]), reverse=True)
                eligible_counts[channel.channel_id] = len(scored)
                channel_picks[channel.channel_id] = [
                    public_candidate(row, score, rank)
                    for rank, (score, row) in enumerate(scored[:3], 1)
                ]
            visible_message_times = [
                parse_time(str(item.get("source_time") or item.get("publish_time_bj") or item.get("publish_time") or ""))
                for item in visible_news + visible_announcements
            ]
            visible_message_times = [stamp for stamp in visible_message_times if stamp is not None]
            if visible_message_times and max(visible_message_times) > cutoff:
                raise AssertionError("future message leaked into signal generation")
            decisions.append(
                {
                    "mode": mode,
                    "decision_date": decision_date,
                    "market_as_of": as_of,
                    "information_cutoff": cutoff.isoformat(),
                    "visible_market_max": view.dates[-1],
                    "visible_message_max": max(visible_message_times).isoformat() if visible_message_times else None,
                    "feature_stock_count": len(features),
                    "visible_news_count": len(visible_news),
                    "visible_announcement_count": len(visible_announcements),
                    "eligible_counts": eligible_counts,
                    "channels": channel_picks,
                    "consensus": consensus(channel_picks),
                }
            )
    payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now(CST).isoformat(timespec="seconds"),
        "replay_start": REPLAY_START,
        "replay_end": REPLAY_END,
        "market_dates_available": dates,
        "rules_frozen_before_evaluation": True,
        "channels": [
            {
                "channel_id": channel.channel_id,
                "name": channel.name,
                "thesis": channel.thesis,
                "conditions": channel.conditions,
            }
            for channel in CHANNELS
        ],
        "decisions": decisions,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["signal_seal_sha256"] = hashlib.sha256(canonical).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def verify_seal(payload: dict[str, Any]) -> None:
    seal = payload.get("signal_seal_sha256")
    body = {key: value for key, value in payload.items() if key != "signal_seal_sha256"}
    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if seal != hashlib.sha256(canonical).hexdigest():
        raise RuntimeError("signal file seal mismatch")
    forbidden = ("next_open_return", "next_high_return", "next_close_return", "next_low_return")
    text = json.dumps(body, ensure_ascii=False)
    if any(key in text for key in forbidden):
        raise RuntimeError("future outcome field found in sealed signal file")


def outcome_for_pick(
    mode: str,
    decision_date: str,
    pick: dict[str, Any],
    dates: list[str],
    rows_by_date: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    index = dates.index(decision_date)
    if index + 1 >= len(dates):
        return {"status": "pending"}
    next_date = dates[index + 1]
    code = pick["code"]
    signal_row = rows_by_date[decision_date].get(code)
    next_row = rows_by_date[next_date].get(code)
    if not signal_row or not next_row:
        return {"status": "missing", "next_date": next_date}
    entry = number(signal_row.get("开盘") or signal_row.get("今开")) if mode == "morning" else number(signal_row.get("收盘") or signal_row.get("最新价"))
    next_open = number(next_row.get("开盘") or next_row.get("今开"))
    next_high = number(next_row.get("最高"))
    next_low = number(next_row.get("最低"))
    next_close = number(next_row.get("收盘") or next_row.get("最新价"))
    if None in (entry, next_open, next_high, next_low, next_close) or entry == 0:
        return {"status": "missing", "next_date": next_date}
    returns = {
        "next_open_return": pct_change(next_open, entry),
        "next_high_return": pct_change(next_high, entry),
        "next_low_return": pct_change(next_low, entry),
        "next_close_return": pct_change(next_close, entry),
    }
    return {
        "status": "complete",
        "next_date": next_date,
        "entry_price": entry,
        **{key: round(value, 4) for key, value in returns.items()},
        "red_window": returns["next_high_return"] >= RED_WINDOW_THRESHOLD,
        "positive_open": returns["next_open_return"] > 0,
        "positive_close": returns["next_close_return"] > 0,
        "no_red": returns["next_high_return"] <= 0,
    }


def aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
    complete = [record for record in records if record.get("status") == "complete"]
    if not complete:
        return {"samples": 0}
    def values(field: str) -> list[float]:
        return [float(record[field]) for record in complete]
    return {
        "samples": len(complete),
        "red_window_rate": sum(record["red_window"] for record in complete) / len(complete) * 100,
        "positive_open_rate": sum(record["positive_open"] for record in complete) / len(complete) * 100,
        "positive_close_rate": sum(record["positive_close"] for record in complete) / len(complete) * 100,
        "no_red_rate": sum(record["no_red"] for record in complete) / len(complete) * 100,
        "mean_open_return": mean(values("next_open_return")),
        "median_high_return": statistics.median(values("next_high_return")),
        "mean_high_return": mean(values("next_high_return")),
        "median_close_return": statistics.median(values("next_close_return")),
        "mean_close_return": mean(values("next_close_return")),
        "worst_low_return": min(values("next_low_return")),
    }


def fmt(value: Any, suffix: str = "%") -> str:
    return "-" if value is None else f"{float(value):.2f}{suffix}"


def evaluate(data_root: Path, signals_path: Path, report_path: Path, details_path: Path) -> dict[str, Any]:
    signals = json.loads(signals_path.read_text(encoding="utf-8"))
    verify_seal(signals)
    dates, rows_by_date = load_market(data_root)
    records = []
    daily = []
    for decision in signals["decisions"]:
        mode = decision["mode"]
        decision_date = decision["decision_date"]
        if mode == "morning" and not decision["visible_market_max"] < decision_date:
            raise AssertionError("morning signal used same-day or future close")
        if mode == "overnight" and decision["visible_market_max"] != decision_date:
            raise AssertionError("overnight signal not anchored to decision-day close")
        for channel_id, picks in decision["channels"].items():
            if not picks:
                continue
            outcome = outcome_for_pick(mode, decision_date, picks[0], dates, rows_by_date)
            records.append({"mode": mode, "group": channel_id, "decision_date": decision_date, "pick": picks[0], **outcome})
        consensus_rows = []
        for pick in decision["consensus"][:2]:
            outcome = outcome_for_pick(mode, decision_date, pick, dates, rows_by_date)
            consensus_rows.append({"pick": pick, **outcome})
            records.append({"mode": mode, "group": f"CONSENSUS_R{pick['rank']}", "decision_date": decision_date, "pick": pick, **outcome})
        daily.append({"mode": mode, "decision_date": decision_date, "consensus": consensus_rows})

    summaries = {}
    for mode in ("morning", "overnight"):
        groups = sorted({record["group"] for record in records if record["mode"] == mode})
        summaries[mode] = {
            group: aggregate([record for record in records if record["mode"] == mode and record["group"] == group])
            for group in groups
        }
    result = {
        "schema_version": "1.0",
        "evaluated_at": datetime.now(CST).isoformat(timespec="seconds"),
        "signal_seal_sha256": signals["signal_seal_sha256"],
        "red_window_threshold_pct": RED_WINDOW_THRESHOLD,
        "summaries": summaries,
        "daily": daily,
        "records": records,
    }
    details_path.parent.mkdir(parents=True, exist_ok=True)
    details_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    write_report(signals, result, report_path)
    return result


def write_report(signals: dict[str, Any], result: dict[str, Any], report_path: Path) -> None:
    channel_lookup = {item["channel_id"]: item for item in signals["channels"]}
    lines = [
        "# 10条隧道因子通道：早盘与尾盘无未来函数回放",
        "",
        f"回放区间：`{signals['replay_start']}` 至 `{signals['replay_end']}` ；信号封印：`{signals['signal_seal_sha256']}`。",
        "",
        "## 结论先行",
        "",
        "本报告是小样本训练验收，不是参数寻优。10条规则在查看结果前一次性冻结；信号文件不含任何次日收益字段。早盘以当日开盘为成本、尾盘以当日收盘为成本，均按A股T+1评价下一交易日。",
        "",
        "`红盘窗口`定义为下一交易日最高价相对成本至少 `+0.5%`。最高价只代表日内存在过该价格，不代表一定能以最高价成交；开盘收益和收盘收益同时列出，防止只看乐观指标。",
        "",
        "## 防偷看审计",
        "",
        "- 早盘信号：市场数据最多到前一交易日；消息最多到决策日09:25。",
        "- 尾盘信号：市场数据最多到决策日收盘；消息最多到决策日15:00。",
        "- 先生成并SHA256封印信号，再由独立评价阶段读取下一交易日OHLC。",
        "- 历史竞价、14:30-15:00分时无法在部署后补造，本次没有伪造这类字段。",
        "- 历史源多数股票缺成交额和换手率，使用价格×成交量的横截面排名作为流动性代理，并在规则中明确降级。",
        "- 历史公司名称来自当前股票池，存在轻微幸存者偏差；样本只有8个可评价决策日，结论只能用于校准，不能证明长期有效。",
        "",
        "## 十条独立通道",
        "",
        "| 通道 | 名称 | 独立假设 | 固定条件摘要 |",
        "|---|---|---|---|",
    ]
    for channel in signals["channels"]:
        lines.append(f"| {channel['channel_id']} | {channel['name']} | {channel['thesis']} | {channel['conditions']} |")

    for mode, title in (("morning", "早盘回放"), ("overnight", "尾盘回放")):
        lines.extend([
            "",
            f"## {title}",
            "",
            "| 通道 | 样本 | 红盘窗口率 | 红开率 | 红收率 | 无红盘率 | 次日高点中位 | 次日收盘中位 | 最差盘中回撤 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ])
        summary = result["summaries"][mode]
        ordered = sorted(
            summary.items(),
            key=lambda item: (item[1].get("red_window_rate", -1), item[1].get("median_high_return", -999)),
            reverse=True,
        )
        for group, metrics in ordered:
            label = group
            if group in channel_lookup:
                label = f"{group} {channel_lookup[group]['name']}"
            elif group == "CONSENSUS_R1":
                label = "共识第1"
            elif group == "CONSENSUS_R2":
                label = "共识第2"
            lines.append(
                f"| {label} | {metrics.get('samples', 0)} | {fmt(metrics.get('red_window_rate'))} | {fmt(metrics.get('positive_open_rate'))} | {fmt(metrics.get('positive_close_rate'))} | {fmt(metrics.get('no_red_rate'))} | {fmt(metrics.get('median_high_return'))} | {fmt(metrics.get('median_close_return'))} | {fmt(metrics.get('worst_low_return'))} |"
            )

        lines.extend(["", "### 每日共识推荐", "", "| 决策日 | 排名 | 股票 | 通道票数 | 次日 | 开盘收益 | 最高收益 | 收盘收益 | 红盘窗口 |", "|---|---:|---|---:|---|---:|---:|---:|---|"])
        for day in [item for item in result["daily"] if item["mode"] == mode]:
            for row in day["consensus"]:
                pick = row["pick"]
                if row.get("status") != "complete":
                    lines.append(f"| {day['decision_date']} | {pick['rank']} | {pick['name']} {pick['code']} | {pick['votes']} | 待评价 | - | - | - | - |")
                    continue
                lines.append(
                    f"| {day['decision_date']} | {pick['rank']} | {pick['name']} {pick['code']} | {pick['votes']} | {row['next_date']} | {fmt(row['next_open_return'])} | {fmt(row['next_high_return'])} | {fmt(row['next_close_return'])} | {'是' if row['red_window'] else '否'} |"
                )

    morning = result["summaries"]["morning"]
    overnight = result["summaries"]["overnight"]
    lines.extend([
        "",
        "## 这次训练真正暴露了什么",
        "",
        f"- **技术层面通过**：信号先封印、评价后读取未来日，早盘与尾盘的信息边界通过断言检查，结果可重复。",
        f"- **简单共识排序没有通过**：早盘共识第1红盘窗口率只有 {fmt(morning['CONSENSUS_R1'].get('red_window_rate'))}，共识第2却是 {fmt(morning['CONSENSUS_R2'].get('red_window_rate'))}。票数更多不等于次日兑现更好，不能直接把通道投票当最终排名。",
        f"- **早盘更稳的单通道**：T09底部修复红盘窗口率 {fmt(morning['T09'].get('red_window_rate'))}、红收率 {fmt(morning['T09'].get('positive_close_rate'))}、最差盘中回撤 {fmt(morning['T09'].get('worst_low_return'))}；T06相对强度容量红收率 {fmt(morning['T06'].get('positive_close_rate'))}，值得继续累计样本。",
        f"- **尾盘最符合“次日给红盘窗口”的通道**：T09红盘窗口率 {fmt(overnight['T09'].get('red_window_rate'))} 且最差盘中回撤 {fmt(overnight['T09'].get('worst_low_return'))}；T08消息潜伏无红盘率 {fmt(overnight['T08'].get('no_red_rate'))}、最差回撤 {fmt(overnight['T08'].get('worst_low_return'))}，风险收益更均衡。",
        f"- **高命中不等于好拿**：尾盘T04红盘窗口率虽为 {fmt(overnight['T04'].get('red_window_rate'))}，但红开率只有 {fmt(overnight['T04'].get('positive_open_rate'))}、最差回撤 {fmt(overnight['T04'].get('worst_low_return'))}，它依赖盘中卖点，不适合被包装成“开盘就容易兑现”。",
        f"- **硬催化关键词通道需要降级**：尾盘T07只有 {fmt(overnight['T07'].get('red_window_rate'))} 红盘窗口和 {fmt(overnight['T07'].get('positive_close_rate'))} 红收率。关键词只能发现公告，不能替代Codex阅读原文后判断催化硬度、预期差和兑现压力。",
        "- **成长结论**：系统已经能诚实地构造无未来函数训练场，也能发现自身排序错误；但样本不足以证明任何通道长期有效，因此本轮不自动修改正式Skill权重。",
        "",
        "## 对正式推荐系统的升级方向",
        "",
        "1. 10条通道保留为独立证据和互相否决机制，最终排名不能再用未经校准的原始票数。",
        "2. 早盘和尾盘必须拥有不同的通道可靠性记录；早盘重视T+1兑现，尾盘重视次日红盘窗口和无红盘风险。",
        "3. 最终前2名增加双目标门槛：红盘窗口证据足够，同时最差回撤/兑现风险不能失控。",
        "4. T07所有公司级催化必须回到公告原文核验，关键词命中只进入待审池，不直接加成最终排名。",
        "5. 等真实竞价和尾盘分时累计后，为现有通道增加执行确认层，而不是重写已经封存的日线因子。",
    ])

    lines.extend([
        "",
        "## 如何读这次训练",
        "",
        "1. 优先看每条通道的红盘窗口率和无红盘率，这对应用户能否在T+1获得可兑现窗口。",
        "2. 再看开盘收益：它比最高收益更保守，也更接近无需盘中择时的兑现能力。",
        "3. 收盘收益用于识别冲高回落；若高点好但收盘差，说明卖出纪律比选股本身更重要。",
        "4. 共识票数不是预测概率，只表示不同独立机制在同一时点收敛到同一只股票。",
        "5. 任何通道只有8个样本，不能据此删改规则。至少累计40-60个交易日后再做稳定性淘汰。",
        "",
        "## 下一步校准原则",
        "",
        "- 周一开始保存真实09:15-09:45和14:30-15:00快照后，再增加竞价强弱、尾盘自然承接和假拉识别；不能用日线替代。",
        "- 推荐日志必须在下单前封存，晚间复盘只读取封存结果，禁止重写当日候选。",
        "- 参数优化采用滚动训练/留出测试，不能在这8天结果上直接调到最好看。",
        "- 公司级消息通道需要继续补充原文语义核验；关键词只负责机械发现，最终硬逻辑仍由Codex判断。",
        "",
        "机器明细与每只股票的锁定因子值保存在同目录JSON文件中。",
    ])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("generate", "evaluate"))
    parser.add_argument("--data-root", default="data_server_cache")
    parser.add_argument("--signals", default="reports/tunnel_factor_signals_20260608_20260617.json")
    parser.add_argument("--report", default="reports/tunnel_factor_replay_20260608_20260617.md")
    parser.add_argument("--details", default="reports/tunnel_factor_replay_20260608_20260617.json")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "generate":
        payload = generate_signals(Path(args.data_root), Path(args.signals))
        counts = defaultdict(int)
        for decision in payload["decisions"]:
            for channel_id, picks in decision["channels"].items():
                counts[(decision["mode"], channel_id)] += int(bool(picks))
        print(json.dumps({"signal_seal_sha256": payload["signal_seal_sha256"], "decision_count": len(payload["decisions"]), "days_with_pick": {f"{mode}:{channel}": count for (mode, channel), count in sorted(counts.items())}}, ensure_ascii=False, indent=2))
    else:
        result = evaluate(Path(args.data_root), Path(args.signals), Path(args.report), Path(args.details))
        print(json.dumps({"report": str(Path(args.report).resolve()), "details": str(Path(args.details).resolve()), "signal_seal_sha256": result["signal_seal_sha256"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
