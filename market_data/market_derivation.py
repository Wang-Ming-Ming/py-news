"""Derive objective market summaries without candidate scoring or trading judgments."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from market_data.market_filters import filter_tradeable, get_code, get_name


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


def _top(records: list[dict[str, Any]], keys: Iterable[str], n: int) -> list[dict[str, Any]]:
    return sorted(records, key=lambda item: number(item, keys), reverse=True)[:n]


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
        "market_cap_float": number(record, ["流通市值"]),
        "market_cap_total": number(record, ["总市值"]),
        "high": number(record, ["最高"]),
        "low": number(record, ["最低"]),
        "open": number(record, ["今开", "开盘"]),
        "prev_close": number(record, ["昨收"]),
    }


def _compact_board(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": text(record, ["板块代码", "代码"]),
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


def _pool_industry_counts(pool_map: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    output: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "name": "",
            "limit_up_count": 0,
            "previous_limit_count": 0,
            "strong_count": 0,
            "broken_limit_count": 0,
        }
    )
    fields = {
        "limit_up": "limit_up_count",
        "previous_limit_up": "previous_limit_count",
        "strong": "strong_count",
        "broken_limit": "broken_limit_count",
    }
    for pool_name, field in fields.items():
        for record in pool_map.get(pool_name, []):
            industry = text(record, ["所属行业", "行业", "板块名称"])
            if not industry:
                continue
            output[industry]["name"] = industry
            output[industry][field] += 1
    return sorted(
        output.values(),
        key=lambda item: (
            item["limit_up_count"],
            item["previous_limit_count"],
            item["strong_count"],
            -item["broken_limit_count"],
        ),
        reverse=True,
    )


def derive_snapshot(frames: dict[str, dict[str, Any]], allow_chinext: bool = False) -> dict[str, Any]:
    stock_records = frames.get("stock_spot", {}).get("records", [])
    tradeable = filter_tradeable(stock_records, allow_chinext=allow_chinext)
    pools = {
        "limit_up": frames.get("limit_up_pool", {}).get("records", []),
        "previous_limit_up": frames.get("previous_limit_up_pool", {}).get("records", []),
        "strong": frames.get("strong_pool", {}).get("records", []),
        "broken_limit": frames.get("broken_limit_pool", {}).get("records", []),
        "dtgc": frames.get("dtgc_pool", {}).get("records", []),
    }
    up_count = sum(1 for record in stock_records if number(record, ["涨跌幅"]) > 0)
    down_count = sum(1 for record in stock_records if number(record, ["涨跌幅"]) < 0)
    limit_up_count = len(pools["limit_up"])
    broken_limit_count = len(pools["broken_limit"])
    market_breadth = round(up_count / max(up_count + down_count, 1), 4)
    broken_limit_ratio = round(broken_limit_count / max(limit_up_count + broken_limit_count, 1), 4)

    industry_boards = frames.get("industry_boards", {}).get("records", [])
    concept_boards = frames.get("concept_boards", {}).get("records", [])
    industry_funds = frames.get("industry_fund_flow_today", {}).get("records", [])
    concept_funds = frames.get("concept_fund_flow_today", {}).get("records", [])
    stock_funds = frames.get("individual_fund_flow_today", {}).get("records", [])

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
            "top_gainers": [_compact_stock(record) for record in _top(tradeable, ["涨跌幅"], 50)],
            "top_amount": [_compact_stock(record) for record in _top(tradeable, ["成交额"], 50)],
            "top_turnover": [_compact_stock(record) for record in _top(tradeable, ["换手率"], 50)],
            "top_volume_ratio": [_compact_stock(record) for record in _top(tradeable, ["量比"], 50)],
            "top_industries": [_compact_board(record) for record in _top(industry_boards, ["涨跌幅"], 50)],
            "top_concepts": [_compact_board(record) for record in _top(concept_boards, ["涨跌幅"], 80)],
            "pool_industry_counts": _pool_industry_counts(pools),
            "top_industry_fund_flow": [_compact_fund_flow(record) for record in _top(industry_funds, ["今日主力净流入-净额", "净额"], 50)],
            "top_concept_fund_flow": [_compact_fund_flow(record) for record in _top(concept_funds, ["今日主力净流入-净额", "净额"], 80)],
            "top_stock_fund_flow": [_compact_fund_flow(record) for record in _top(stock_funds, ["今日主力净流入-净额", "净额"], 100)],
        },
        "pools": pools,
    }
