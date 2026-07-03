#!/usr/bin/env python3
"""Discover main-board trend leaders, repricing starts, and healthy pullbacks."""

from __future__ import annotations

import argparse
import gzip
import json
import math
from pathlib import Path
from typing import Any


DEFAULT_CONTEXT = Path("data_server_cache/latest_context.json")
ORDINARY_PREFIXES = ("000", "001", "002", "003", "600", "601", "603", "605")
VALID_MODES = {"morning", "overnight", "trend"}


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def number(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = row.get(key)
    return float(value) if isinstance(value, (int, float)) else default


def opening_vwap(row: dict[str, Any]) -> float:
    amount = number(row, "amount")
    volume = number(row, "volume")
    price = number(row, "price")
    if amount <= 0 or volume <= 0 or price <= 0:
        return 0.0
    raw = amount / volume
    return raw / 100 if raw / price > 20 else raw


def is_ordinary(row: dict[str, Any]) -> bool:
    code = str(row.get("code") or "")
    name = str(row.get("name") or "")
    return (
        code.startswith(ORDINARY_PREFIXES)
        and "ST" not in name.upper()
        and "退" not in name
        and number(row, "price") > 0
    )


def _base_metrics(row: dict[str, Any]) -> dict[str, float] | None:
    if not is_ordinary(row) or int(number(row, "history_points")) < 15:
        return None
    price = number(row, "price")
    previous_close = number(row, "prev_close")
    open_price = number(row, "open")
    high = number(row, "high")
    low = number(row, "low")
    amount = number(row, "amount")
    vwap = opening_vwap(row)
    if min(price, previous_close, open_price, high, low, amount, vwap) <= 0:
        return None
    return {
        "price": price,
        "previous_close": previous_close,
        "open": open_price,
        "high": high,
        "low": low,
        "amount": amount,
        "amount_ratio_5d": number(row, "amount_ratio_5d"),
        "vwap": vwap,
        "pct": number(row, "pct"),
        "gap_pct": (open_price / previous_close - 1) * 100,
        "vwap_distance_pct": (price / vwap - 1) * 100,
        "distance_from_high_pct": (high - price) / high * 100,
        "close_position": (price - low) / max(high - low, price * 0.001),
        "range_position_15d": number(row, "range_position_15d", 1.0),
        "return_5d": number(row, "return_5d"),
        "return_10d": number(row, "return_10d"),
        "return_15d": number(row, "return_15d"),
        "ma5": number(row, "ma5"),
        "ma10": number(row, "ma10"),
        "ma20": number(row, "ma20"),
    }


def _lane_scores(row: dict[str, Any], mode: str) -> list[tuple[str, float]]:
    metrics = _base_metrics(row)
    if metrics is None:
        return []
    m = metrics
    if m["pct"] >= 9.5:
        return []

    scores: list[tuple[str, float]] = []
    liquidity_bonus = min(math.log10(m["amount"] / 50_000_000 + 1) * 5, 6)

    expectation_trend = (
        -1.2 <= m["pct"] <= 3.5
        and -2.0 <= m["gap_pct"] <= 4.0
        and -2 <= m["return_5d"] <= 15
        and 0 <= m["return_10d"] <= 30
        and m["return_15d"] <= 45
        and 0.35 <= m["range_position_15d"] <= 0.88
        and m["amount"] >= 100_000_000
        and m["vwap_distance_pct"] >= -0.25
        and m["distance_from_high_pct"] <= 3.0
        and m["ma5"] > 0
        and m["ma10"] > 0
        and m["ma20"] > 0
        and m["price"] >= m["ma5"] * 0.99
        and m["price"] >= m["ma10"] * 0.99
        and m["price"] >= m["ma20"]
        and m["amount_ratio_5d"] >= 0.55
    )
    if expectation_trend:
        score = (
            44
            + max(0, 3 - abs(m["pct"] - 1.2)) * 1.5
            + min(max(m["return_10d"], 0), 20) * 0.25
            + max(0, 3 - m["distance_from_high_pct"]) * 2
            + min(max(m["vwap_distance_pct"], 0), 2) * 2
            + max(0, 0.88 - m["range_position_15d"]) * 5
            + liquidity_bonus
        )
        scores.append(("expectation_trend_theme", score))

    emerging = (
        1.5 <= m["pct"] < 9.5
        and -2.0 <= m["gap_pct"] <= 5.5
        and m["vwap_distance_pct"] >= 0.2
        and m["distance_from_high_pct"] <= 3.0
        and m["amount"] >= 50_000_000
        and m["range_position_15d"] <= 0.90
        and m["return_10d"] <= 35
        and m["return_5d"] <= 22
    )
    if emerging:
        score = (
            35
            + min(m["pct"], 8) * 2
            + max(0, 3 - m["distance_from_high_pct"]) * 3
            + min(max(m["vwap_distance_pct"], 0), 4) * 2
            + max(0, 0.9 - m["range_position_15d"]) * 8
            + liquidity_bonus
        )
        scores.append(("early_repricing", score))

    trend = (
        -1.5 <= m["pct"] < 9.5
        and 3 <= m["return_5d"] <= 55
        and 8 <= m["return_10d"] <= 90
        and m["return_15d"] <= 130
        and m["amount"] >= 100_000_000
        and m["vwap_distance_pct"] >= -0.5
        and m["distance_from_high_pct"] <= 4.0
        and m["ma5"] > 0
        and m["ma10"] > 0
        and m["price"] >= m["ma5"] * 0.99
        and (m["ma5"] >= m["ma10"] or m["price"] >= m["ma10"] * 1.03)
    )
    if trend:
        score = (
            32
            + min(m["return_10d"], 60) * 0.25
            + min(max(m["pct"], 0), 8) * 1.5
            + max(0, 4 - m["distance_from_high_pct"]) * 2
            + max(0, m["close_position"]) * 4
            + liquidity_bonus
        )
        scores.append(("trend_continuation", score))

    pullback = (
        -4.0 <= m["pct"] <= 2.5
        and 8 <= m["return_10d"] <= 70
        and m["return_15d"] <= 110
        and m["amount"] >= 50_000_000
        and m["ma5"] > 0
        and m["ma10"] > 0
        and m["price"] >= m["ma5"] * 0.975
        and m["price"] >= m["ma10"] * 0.99
        and m["close_position"] >= 0.45
    )
    if pullback:
        score = (
            30
            + min(m["return_10d"], 50) * 0.2
            + max(0, m["close_position"]) * 6
            + max(0, 1.5 + m["pct"]) * 1.5
            + liquidity_bonus
        )
        scores.append(("healthy_pullback", score))

    quiet = (
        0.5 <= m["pct"] <= 5.5
        and -12 <= m["return_10d"] <= 15
        and -20 <= m["return_15d"] <= 25
        and m["range_position_15d"] <= 0.75
        and m["amount"] >= 50_000_000
        and m["vwap_distance_pct"] >= 0.2
        and m["distance_from_high_pct"] <= 3.0
    )
    if quiet:
        score = (
            34
            + min(m["pct"], 5) * 2
            + max(0, 0.75 - m["range_position_15d"]) * 10
            + max(0, 3 - m["distance_from_high_pct"]) * 2
            + liquidity_bonus
        )
        scores.append(("pre_activation", score))

    if mode == "overnight":
        scores = [
            (lane, score)
            for lane, score in scores
            if m["pct"] >= 0
            and m["vwap_distance_pct"] >= 0
            and m["distance_from_high_pct"] <= 3
        ]
    elif mode == "trend":
        scores = [
            (lane, score)
            for lane, score in scores
            if lane
            in {
                "expectation_trend_theme",
                "trend_continuation",
                "healthy_pullback",
                "early_repricing",
            }
        ]
    return scores


def score_row(row: dict[str, Any], mode: str) -> dict[str, Any] | None:
    scores = _lane_scores(row, mode)
    metrics = _base_metrics(row)
    if not scores or metrics is None:
        return None
    lane, score = max(scores, key=lambda item: item[1])
    m = metrics
    return {
        "code": str(row["code"]),
        "name": str(row["name"]),
        "lane": lane,
        "score": round(score, 4),
        "price": round(m["price"], 4),
        "pct": round(m["pct"], 4),
        "opening_gap_pct": round(m["gap_pct"], 4),
        "vwap": round(m["vwap"], 4),
        "vwap_distance_pct": round(m["vwap_distance_pct"], 4),
        "distance_from_high_pct": round(m["distance_from_high_pct"], 4),
        "amount": round(m["amount"], 2),
        "amount_ratio_5d": round(m["amount_ratio_5d"], 4),
        "range_position_15d": round(m["range_position_15d"], 4),
        "return_5d": round(m["return_5d"], 4),
        "return_10d": round(m["return_10d"], 4),
        "return_15d": round(m["return_15d"], 4),
        "selection_tag": "objective_market_leadership",
        "expectation_trend_candidate": lane == "expectation_trend_theme",
        "capital_retention_signal": bool(
            m["price"] >= max(m["ma10"], m["ma20"])
            and m["distance_from_high_pct"] <= 3
            and m["amount_ratio_5d"] >= 0.55
        ),
        "morning_execution_eligible_at_snapshot": bool(
            m["pct"] <= 5 and m["gap_pct"] <= 5
        ),
        "needs_theme_verification": True,
        "needs_chain_verification": True,
        "needs_hard_risk_check": True,
    }


def anchor_row(row: dict[str, Any]) -> dict[str, Any] | None:
    metrics = _base_metrics(row)
    if metrics is None or metrics["pct"] < 9.5:
        return None
    return {
        "code": str(row["code"]),
        "name": str(row["name"]),
        "price": round(metrics["price"], 4),
        "pct": round(metrics["pct"], 4),
        "amount": round(metrics["amount"], 2),
        "role": "unbuyable_or_near_limit_theme_anchor",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Discover objective main-board trend and repricing leaders."
    )
    parser.add_argument("--context", default=str(DEFAULT_CONTEXT))
    parser.add_argument("--mode", choices=sorted(VALID_MODES), default="morning")
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--anchor-limit", type=int, default=20)
    args = parser.parse_args()

    context = read_json(Path(args.context))
    features_path = Path(context["downloads"]["features"]["path"])
    candidates: list[dict[str, Any]] = []
    anchors: list[dict[str, Any]] = []
    with gzip.open(features_path, "rt", encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            candidate = score_row(row, args.mode)
            if candidate:
                candidates.append(candidate)
            anchor = anchor_row(row)
            if anchor:
                anchors.append(anchor)

    candidates.sort(key=lambda item: item["score"], reverse=True)
    anchors.sort(key=lambda item: (item["pct"], item["amount"]), reverse=True)
    payload = {
        "schema_version": "1.0",
        "mode": args.mode,
        "snapshot_id": (context.get("snapshot") or {}).get("snapshot_id"),
        "source_time": (context.get("snapshot") or {}).get("source_time"),
        "method": (
            "objective discovery only; verify theme event cluster, level-1/2 chain "
            "evidence, hard risks, next buyers, and T+1 execution"
        ),
        "candidates": candidates[: max(0, args.limit)],
        "anchors": anchors[: max(0, args.anchor_limit)],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
