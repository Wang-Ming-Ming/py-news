"""Derive compact rankings from raw AkShare market data."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from market_data.market_filters import filter_tradeable, get_code, get_name, is_tradeable_main_market


def number(record: dict[str, Any], keys: Iterable[str], default: float = 0.0) -> float:
    for key in keys:
        value = record.get(key)
        if value in (None, "", "-"):
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def text(record: dict[str, Any], keys: Iterable[str]) -> str:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def top(records: list[dict[str, Any]], keys: Iterable[str], n: int = 30, reverse: bool = True) -> list[dict[str, Any]]:
    return sorted(records, key=lambda item: number(item, keys), reverse=reverse)[:n]


def _compact_stock(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": get_code(record),
        "name": get_name(record),
        "price": number(record, ["最新价", "收盘"]),
        "pct": number(record, ["涨跌幅"]),
        "amount": number(record, ["成交额"]),
        "turnover": number(record, ["换手率"]),
        "volume_ratio": number(record, ["量比"]),
        "amplitude": number(record, ["振幅"]),
        "speed": number(record, ["涨速"]),
        "change_5m": number(record, ["5分钟涨跌"]),
        "main_net": number(record, ["主力净流入"]),
        "market_cap_float": number(record, ["流通市值"]),
        "market_cap_total": number(record, ["总市值"]),
        "high": number(record, ["最高"]),
        "low": number(record, ["最低"]),
        "open": number(record, ["今开", "开盘"]),
        "prev_close": number(record, ["昨收"]),
    }


def _compact_board(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": text(record, ["板块名称", "名称", "行业", "概念名称"]),
        "pct": number(record, ["涨跌幅"]),
        "amount": number(record, ["成交额"]),
        "turnover": number(record, ["换手率"]),
        "rise_count": number(record, ["上涨家数"]),
        "fall_count": number(record, ["下跌家数"]),
        "leader": text(record, ["领涨股票", "领涨股"]),
        "leader_pct": number(record, ["领涨股票-涨跌幅", "领涨股-涨跌幅"]),
    }


def _compact_fund_flow(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": get_code(record),
        "name": get_name(record) or text(record, ["名称", "板块名称"]),
        "pct": number(record, ["今日涨跌幅", "涨跌幅"]),
        "main_net": number(record, ["今日主力净流入-净额", "主力净流入-净额", "净额"]),
        "main_net_pct": number(record, ["今日主力净流入-净占比", "主力净流入-净占比", "净占比"]),
        "super_net": number(record, ["今日超大单净流入-净额", "超大单净流入-净额"]),
        "big_net": number(record, ["今日大单净流入-净额", "大单净流入-净额"]),
    }


def _code_set(records: list[dict[str, Any]]) -> set[str]:
    return {get_code(record) for record in records if get_code(record)}


def _fund_flow_by_code(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item["code"]: item for item in (_compact_fund_flow(record) for record in records) if item["code"]}


def _pool_record_by_code(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {get_code(record): record for record in records if get_code(record)}


def _pool_industry_heat(
    limit_up_records: list[dict[str, Any]],
    previous_limit_records: list[dict[str, Any]],
    strong_records: list[dict[str, Any]],
    broken_limit_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    industries: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "name": "",
            "score": 0,
            "limit_up_count": 0,
            "previous_limit_count": 0,
            "strong_count": 0,
            "broken_limit_count": 0,
            "leaders": [],
        }
    )

    def add(records: list[dict[str, Any]], field: str, score: int) -> None:
        for record in records:
            industry = text(record, ["所属行业", "行业", "板块名称"])
            if not industry:
                continue
            item = industries[industry]
            item["name"] = industry
            item[field] += 1
            item["score"] += score
            if len(item["leaders"]) < 8:
                item["leaders"].append(
                    {
                        "code": get_code(record),
                        "name": get_name(record),
                        "pct": number(record, ["涨跌幅"]),
                    }
                )

    add(limit_up_records, "limit_up_count", 10)
    add(previous_limit_records, "previous_limit_count", 5)
    add(strong_records, "strong_count", 3)
    add(broken_limit_records, "broken_limit_count", -4)
    return sorted(industries.values(), key=lambda item: item["score"], reverse=True)[:50]


def _score_overnight_candidate(
    stock: dict[str, Any],
    fund_flow: dict[str, Any] | None,
    previous_limit_record: dict[str, Any] | None,
    strong_record: dict[str, Any] | None,
    broken_record: dict[str, Any] | None,
    industry_heat: dict[str, dict[str, Any]],
    market_context: dict[str, Any],
) -> dict[str, Any]:
    score = 0.0
    accept_score = 0.0
    high_open_score = 0.0
    reasons: list[str] = []
    risk_notes: list[str] = []
    high_open_reasons: list[str] = []
    next_day_fund_sources: list[str] = []

    pct = stock["pct"]
    amount = stock["amount"]
    turnover = (
        stock["turnover"]
        or number(strong_record or {}, ["换手率"])
        or number(previous_limit_record or {}, ["换手率"])
        or number(broken_record or {}, ["换手率"])
    )
    volume_ratio = stock["volume_ratio"] or number(strong_record or {}, ["量比"])
    speed = (
        stock["speed"]
        or number(strong_record or {}, ["涨速"])
        or number(previous_limit_record or {}, ["涨速"])
        or number(broken_record or {}, ["涨速"])
    )
    change_5m = stock["change_5m"]
    amplitude = stock["amplitude"] or number(previous_limit_record or {}, ["振幅"]) or number(broken_record or {}, ["振幅"])
    high = stock["high"]
    low = stock["low"]
    close_position = (stock["price"] - low) / (high - low) if high > low else 0.0
    market_breadth = number(market_context, ["market_breadth"])
    broken_limit_ratio = number(market_context, ["broken_limit_ratio"])
    industry = (
        text(previous_limit_record or {}, ["所属行业", "行业"])
        or text(strong_record or {}, ["所属行业", "行业"])
        or text(broken_record or {}, ["所属行业", "行业"])
    )

    if 1.0 <= pct <= 7.5:
        value = pct * 4.0
        score += value
        accept_score += min(value, 24)
        reasons.append(f"涨幅处在隔夜可博弈区间: {pct:.2f}%")
        if pct <= 6.5:
            high_open_score += 8
            high_open_reasons.append("涨幅未进入过度一致区")
        else:
            high_open_score += 2
            risk_notes.append("涨幅偏接近一致区，需要更强的晚间催化")
    elif 7.5 < pct <= 9.3:
        score += 18
        accept_score += 10
        high_open_score -= 8
        risk_notes.append(f"涨幅偏高，次日兑现压力增加: {pct:.2f}%")
    elif -1.5 <= pct < 1.0:
        score += 6
        accept_score += 5
        high_open_score += 4
        reasons.append(f"涨幅不高，若有催化仍有补涨空间: {pct:.2f}%")
    else:
        high_open_score -= 8
        risk_notes.append(f"涨幅不在隔夜优选区间: {pct:.2f}%")

    amount_score = min(amount / 1_000_000_000, 8) * 2.2
    score += amount_score
    accept_score += min(amount / 1_000_000_000, 6) * 1.5
    if amount >= 1_000_000_000:
        reasons.append(f"成交额充足: {amount / 100_000_000:.1f}亿")

    turnover_score = min(turnover, 18) * 0.75
    score += turnover_score
    if 2 <= turnover <= 15:
        accept_score += 8
        high_open_score += 7
        reasons.append(f"换手相对健康: {turnover:.2f}%")
    elif turnover > 20:
        high_open_score -= 8
        risk_notes.append(f"换手过高，筹码分歧较大: {turnover:.2f}%")

    if volume_ratio >= 1:
        value = min(volume_ratio, 6) * 3.0
        score += value
        accept_score += min(value, 12)
        high_open_score += min(value, 8)
        reasons.append(f"量比放大: {volume_ratio:.2f}")

    if speed > 0:
        value = min(speed, 3) * 4.0
        score += value
        accept_score += value
        high_open_score += min(value, 10)
        reasons.append(f"尾盘/盘口涨速为正: {speed:.2f}")
    elif speed < -1:
        high_open_score -= 6
        risk_notes.append(f"涨速转弱: {speed:.2f}")

    if change_5m > 0:
        value = min(change_5m, 4) * 3.0
        score += value
        accept_score += value
        high_open_score += min(value, 8)
        reasons.append(f"5分钟动量为正: {change_5m:.2f}%")
    elif change_5m < -1:
        high_open_score -= 6
        risk_notes.append(f"5分钟动量走弱: {change_5m:.2f}%")

    if close_position >= 0.75:
        accept_score += 6
        high_open_score += 10
        high_open_reasons.append("收盘接近全天高位，尾盘承接更像主动拿隔夜")
    elif 0 < close_position < 0.55:
        high_open_score -= 10
        risk_notes.append("收盘离全天高位较远，明早高开难度提高")

    if 3 <= amplitude <= 10:
        accept_score += 4
    elif amplitude > 12:
        high_open_score -= 6
        risk_notes.append(f"振幅过大，隔夜不确定性提高: {amplitude:.2f}%")

    if fund_flow:
        main_net = number(fund_flow, ["main_net"])
        main_net_pct = number(fund_flow, ["main_net_pct"])
        if main_net > 0:
            value = min(main_net / 100_000_000, 8) * 3.0
            score += value
            accept_score += min(value, 18)
            high_open_score += min(value, 16)
            reasons.append(f"主力资金净流入: {main_net / 100_000_000:.1f}亿")
            next_day_fund_sources.append("资金流净买入延续")
        elif main_net < -100_000_000:
            high_open_score -= 10
            risk_notes.append(f"主力资金净流出: {main_net / 100_000_000:.1f}亿")
        if main_net_pct > 3:
            score += min(main_net_pct, 12)
            accept_score += min(main_net_pct, 10)
            high_open_score += min(main_net_pct, 8)

    if previous_limit_record:
        score += 8
        accept_score += 10
        high_open_score += 9
        reasons.append("昨日涨停池仍有辨识度")
        next_day_fund_sources.append("昨日强势辨识度资金")

    if strong_record:
        score += 7
        accept_score += 7
        high_open_score += 7
        reason = text(strong_record, ["入选理由"])
        reasons.append(f"强势池: {reason or '入选'}")
        next_day_fund_sources.append("强势池趋势资金")

    if broken_record:
        score -= 16
        accept_score -= 12
        high_open_score -= 16
        risk_notes.append("曾炸板，分歧和兑现压力需要重点确认")

    rotation_risk = "medium"
    if industry and industry in industry_heat:
        heat = industry_heat[industry]
        heat_score = min(number(heat, ["score"]), 18)
        if heat_score > 0:
            score += heat_score
            accept_score += min(heat_score * 0.6, 10)
            high_open_score += min(heat_score * 0.5, 9)
            reasons.append(f"板块池热度靠前: {industry}")
            next_day_fund_sources.append(f"{industry}板块延续资金")
        if (
            number(heat, ["limit_up_count"]) >= 5
            and number(heat, ["strong_count"]) >= 8
            and number(heat, ["previous_limit_count"]) >= 4
        ):
            high_open_score -= 10
            rotation_risk = "high"
            risk_notes.append(f"{industry}板块热度偏高潮，明早轮动/兑现风险高")
        elif number(heat, ["limit_up_count"]) >= 3:
            rotation_risk = "medium"
        else:
            rotation_risk = "low"

    if pct >= 8.8:
        accept_score -= 8
        high_open_score -= 12
        risk_notes.append("接近涨停，明早兑现压力偏大")

    if amount < 100_000_000:
        score -= 10
        high_open_score -= 10
        risk_notes.append("成交额不足，流动性不适合作为优先隔夜标的")

    if market_breadth and market_breadth < 0.25:
        high_open_score -= 20
        accept_score -= 10
        risk_notes.append("全市场宽度极弱，隔夜高开需要明显新增催化")
    elif market_breadth and market_breadth < 0.35:
        high_open_score -= 14
        accept_score -= 7
        risk_notes.append("全市场宽度偏弱，不能只因今日板块强就主推")

    if broken_limit_ratio > 0.30:
        high_open_score -= 8
        risk_notes.append("炸板比例偏高，说明情绪分歧和次日兑现压力较大")

    high_open_score += min(max(accept_score, 0), 70) * 0.45
    if not next_day_fund_sources:
        high_open_score -= 8
        risk_notes.append("缺少明确明早新增资金来源，必须有新闻/政策再确认")

    score = round(max(score, 0), 2)
    accept_score = round(max(min(accept_score, 100), 0), 2)
    high_open_score = round(max(min(high_open_score, 100), 0), 2)
    if high_open_score >= 70 and accept_score >= 60 and rotation_risk != "high":
        execution_grade = "priority"
    elif high_open_score >= 55 and accept_score >= 50:
        execution_grade = "watch"
    else:
        execution_grade = "avoid"

    stock = {
        **stock,
        "turnover": turnover,
        "volume_ratio": volume_ratio,
        "amplitude": amplitude,
        "speed": speed,
        "change_5m": change_5m,
        "close_position": round(close_position, 4),
    }
    return {
        **stock,
        "market_score": score,
        "next_day_accept_score": accept_score,
        "high_open_score": high_open_score,
        "execution_grade": execution_grade,
        "rotation_risk": rotation_risk,
        "next_day_fund_sources": next_day_fund_sources[:6],
        "high_open_reasons": high_open_reasons[:6],
        "requires_news_catalyst": high_open_score < 70 or rotation_risk == "high",
        "score_reasons": reasons[:8],
        "risk_notes": risk_notes[:8],
        "fund_flow": fund_flow or {},
        "industry": industry,
        "tags": {
            "previous_limit": bool(previous_limit_record),
            "strong_pool": bool(strong_record),
            "broken_limit": bool(broken_record),
        },
    }


def derive_snapshot(frames: dict[str, dict[str, Any]], allow_chinext: bool = False) -> dict[str, Any]:
    stock_records = frames.get("stock_spot", {}).get("records", [])
    tradeable = filter_tradeable(stock_records, allow_chinext=allow_chinext)
    limit_up_records = frames.get("limit_up_pool", {}).get("records", [])
    previous_limit_records = frames.get("previous_limit_up_pool", {}).get("records", [])
    strong_records = frames.get("strong_pool", {}).get("records", [])
    broken_limit_records = frames.get("broken_limit_pool", {}).get("records", [])
    pool_industry_heat = _pool_industry_heat(
        limit_up_records,
        previous_limit_records,
        strong_records,
        broken_limit_records,
    )
    pool_industry_heat_by_name = {item["name"]: item for item in pool_industry_heat}

    gainers = [_compact_stock(record) for record in top(tradeable, ["涨跌幅"], n=50)]
    by_amount = [_compact_stock(record) for record in top(tradeable, ["成交额"], n=50)]
    by_turnover = [_compact_stock(record) for record in top(tradeable, ["换手率"], n=50)]
    by_volume_ratio = [_compact_stock(record) for record in top(tradeable, ["量比"], n=50)]
    active_candidates = [
        _compact_stock(record)
        for record in tradeable
        if -3 <= number(record, ["涨跌幅"]) <= 9.7
        and number(record, ["成交额"]) >= 100_000_000
        and (number(record, ["量比"]) >= 1 or number(record, ["量比"]) == 0)
    ]
    active_candidates.sort(
        key=lambda item: (
            item["pct"] * 2
            + min(item["turnover"], 30) * 0.2
            + min(item["volume_ratio"], 10) * 0.8
            + min(item["amount"] / 1_000_000_000, 10)
        ),
        reverse=True,
    )

    industry_boards = frames.get("industry_boards", {}).get("records", [])
    concept_boards = frames.get("concept_boards", {}).get("records", [])
    industry_funds = frames.get("industry_fund_flow_today", {}).get("records", [])
    concept_funds = frames.get("concept_fund_flow_today", {}).get("records", [])
    stock_funds = frames.get("individual_fund_flow_today", {}).get("records", [])
    fund_by_code = _fund_flow_by_code(stock_funds)
    limit_up_codes = _code_set(limit_up_records)
    previous_limit_by_code = _pool_record_by_code(previous_limit_records)
    strong_by_code = _pool_record_by_code(strong_records)
    broken_by_code = _pool_record_by_code(broken_limit_records)
    up_count = sum(1 for record in stock_records if number(record, ["涨跌幅"]) > 0)
    down_count = sum(1 for record in stock_records if number(record, ["涨跌幅"]) < 0)
    limit_up_count = len(limit_up_records)
    broken_limit_count = len(broken_limit_records)
    market_breadth = round(up_count / max(up_count + down_count, 1), 4)
    broken_limit_ratio = round(broken_limit_count / max(limit_up_count + broken_limit_count, 1), 4)
    market_context = {
        "market_breadth": market_breadth,
        "broken_limit_ratio": broken_limit_ratio,
    }

    overnight_candidates = []
    for record in tradeable:
        code = get_code(record)
        if not code or code in limit_up_codes:
            continue
        pct = number(record, ["涨跌幅"])
        amount = number(record, ["成交额"])
        if not (-2.5 <= pct <= 9.3 and amount >= 80_000_000):
            continue
        if not is_tradeable_main_market(record, allow_chinext=allow_chinext):
            continue
        stock = _compact_stock(record)
        overnight_candidates.append(
            _score_overnight_candidate(
                stock,
                fund_by_code.get(code),
                previous_limit_by_code.get(code),
                strong_by_code.get(code),
                broken_by_code.get(code),
                pool_industry_heat_by_name,
                market_context,
            )
        )

    overnight_candidates.sort(
        key=lambda item: (
            item["market_score"] * 0.30
            + item["next_day_accept_score"] * 0.25
            + item["high_open_score"] * 0.45,
            item["amount"],
        ),
        reverse=True,
    )

    return {
        "summary": {
            "stock_count": len(stock_records),
            "tradeable_stock_count": len(tradeable),
            "up_count": up_count,
            "down_count": down_count,
            "limit_up_count": limit_up_count,
            "broken_limit_count": broken_limit_count,
            "market_breadth": market_breadth,
            "broken_limit_ratio": broken_limit_ratio,
        },
        "rankings": {
            "top_gainers": gainers,
            "top_amount": by_amount,
            "top_turnover": by_turnover,
            "top_volume_ratio": by_volume_ratio,
            "active_candidates": active_candidates[:120],
            "overnight_candidates": overnight_candidates[:150],
            "top_industries": [_compact_board(record) for record in top(industry_boards, ["涨跌幅"], n=30)],
            "top_concepts": [_compact_board(record) for record in top(concept_boards, ["涨跌幅"], n=50)],
            "pool_industry_heat": pool_industry_heat,
            "top_industry_fund_flow": [_compact_fund_flow(record) for record in top(industry_funds, ["今日主力净流入-净额", "主力净流入-净额", "净额"], n=30)],
            "top_concept_fund_flow": [_compact_fund_flow(record) for record in top(concept_funds, ["今日主力净流入-净额", "主力净流入-净额", "净额"], n=50)],
            "top_stock_fund_flow": [_compact_fund_flow(record) for record in top(stock_funds, ["今日主力净流入-净额", "主力净流入-净额", "净额"], n=80)],
        },
        "pools": {
            "limit_up": limit_up_records,
            "previous_limit_up": previous_limit_records,
            "strong": strong_records,
            "broken_limit": broken_limit_records,
            "dtgc": frames.get("dtgc_pool", {}).get("records", []),
        },
    }
