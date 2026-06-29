#!/usr/bin/env python3
"""Discover fast-rising, multi-event market themes before stock ranking."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


DEFAULT_NEWS_INDEX = Path("data_server_cache/latest_news_index.json")
BEIJING = timezone(timedelta(hours=8))

PRIMARY_SOURCES = {
    "cninfo",
    "ndrc",
    "sse",
    "szse",
    "gov",
    "company_ir",
}
OVERSEAS_SOURCES = {"eastmoney_global", "reuters", "company_ir", "ft"}
FOREIGN_PRIMARY_SOURCES = {"reuters", "company_ir", "ft"}

HARD_CUES = (
    "出口管制",
    "出口许可",
    "短缺",
    "断货",
    "供不应求",
    "缺口",
    "涨价",
    "提价",
    "价格上涨",
    "订单",
    "合同",
    "采购",
    "供应协议",
    "积压",
    "扩产",
    "产能",
    "量产",
    "认证",
    "收购",
    "合资",
    "重组",
    "切入",
    "进入供应链",
    "资本开支",
    "政策落地",
    "获批",
    "中标",
    "投产",
)

NEGATIVE_CUES = (
    "不涉及",
    "尚未涉及",
    "未涉及",
    "没有相关",
    "未有生产",
    "影响极小",
    "收入占比较小",
    "风险提示",
    "过度解读",
    "公司澄清",
    "终止",
    "取消",
)

GENERIC_TERMS = {
    "AI",
    "A股",
    "ETF",
    "公司",
    "股份",
    "公告",
    "市场",
    "业务",
    "行业",
    "股票",
    "涨停",
    "投资",
    "科技",
    "材料",
    "芯片",
    "半导体",
    "设备",
    "数据中心",
}

ALIAS_GROUPS: dict[str, tuple[str, ...]] = {
    "磷化铟": ("磷化铟", "indium phosphide", "inp"),
    "电子布": ("玻纤布", "电子布", "glass fiber cloth"),
    "高带宽存储": ("hbm", "高带宽存储", "高带宽内存"),
    "DRAM": ("dram", "动态随机存储", "内存芯片"),
    "NAND": ("nand", "闪存芯片", "nand flash"),
    "存储芯片": ("存储芯片", "存储器", "memory chip"),
    "先进封装": ("先进封装", "2.5d封装", "3d封装", "cowos"),
    "IC载板": ("ic载板", "封装载板", "abf载板"),
    "半导体设备": ("半导体设备", "晶圆设备", "刻蚀设备", "薄膜沉积"),
    "洁净室": ("洁净室", "无尘室", "洁净厂房", "厂务系统"),
    "共封装光学": ("cpo", "共封装光学"),
    "光模块": ("光模块", "optical module"),
    "液冷": ("液冷", "冷板", "浸没式冷却"),
    "固态电池": ("固态电池", "全固态电池"),
    "可控核聚变": ("可控核聚变", "核聚变", "fusion"),
    "核电": ("核电", "核能设备"),
    "人形机器人": ("人形机器人", "具身智能", "humanoid robot"),
    "制冷剂": ("制冷剂", "冷媒", "hfc"),
    "氟化工": ("氟化工", "含氟材料"),
    "稀土": ("稀土", "稀土永磁"),
    "创新药": ("创新药", "抗体药", "小分子药"),
}

LATIN_TECH_RE = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?:CPO|OCS|NPO|LPO|LRO|HBM\d*|DRAM|NAND|InP|GaAs|SiC|GPU|ASIC|"
    r"CoWoS|DDR\d*|LPDDR\d*|1\.6T|3\.2T)"
    r"(?![A-Za-z0-9])",
    re.IGNORECASE,
)
CHINESE_THEME_RE = re.compile(
    r"[\u4e00-\u9fff]{2,8}"
    r"(?:存储|芯片|载板|光模块|制冷剂|电池|机器人|核聚变|核电|稀土|液冷)"
)


@dataclass(frozen=True)
class NewsItem:
    title: str
    source: str
    published_at: datetime
    stock_code: str
    stock_name: str
    url: str


def repair_text(value: Any) -> str:
    """Repair the common UTF-8-as-Latin-1 mojibake found in old indexes."""

    text = str(value or "").strip()
    if not text:
        return ""
    try:
        repaired = text.encode("latin1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text
    chinese_before = len(re.findall(r"[\u4e00-\u9fff]", text))
    chinese_after = len(re.findall(r"[\u4e00-\u9fff]", repaired))
    return repaired if chinese_after >= chinese_before else text


def parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=BEIJING)
    return parsed.astimezone(BEIJING)


def load_news(path: Path) -> list[NewsItem]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    rows = payload.get("data", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []

    result: list[NewsItem] = []
    seen: set[tuple[str, str, str]] = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        title = repair_text(row.get("title"))
        published_at = parse_time(
            row.get("publish_time_bj")
            or row.get("source_time")
            or row.get("publish_time")
        )
        if not title or not published_at:
            continue
        source = str(row.get("source") or "unknown").strip().lower()
        url = str(row.get("url") or "")
        key = (source, title, url)
        if key in seen:
            continue
        seen.add(key)
        result.append(
            NewsItem(
                title=title,
                source=source,
                published_at=published_at,
                stock_code=str(row.get("stock_code") or ""),
                stock_name=repair_text(row.get("stock_name")),
                url=url,
            )
        )
    return result


def normalize_term(term: str) -> str:
    stripped = term.strip(" :，。；;（）()【】[]-'\"")
    lowered = stripped.lower()
    for canonical, aliases in ALIAS_GROUPS.items():
        if lowered in {alias.lower() for alias in aliases}:
            return canonical
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9.]*", stripped):
        return stripped.upper()
    return stripped


def extract_terms(title: str) -> set[str]:
    repaired = repair_text(title)
    lowered = repaired.lower()
    terms: set[str] = set()

    for canonical, aliases in ALIAS_GROUPS.items():
        if any(alias.lower() in lowered for alias in aliases):
            terms.add(canonical)

    terms.update(normalize_term(match.group(0)) for match in LATIN_TECH_RE.finditer(repaired))
    for match in CHINESE_THEME_RE.finditer(repaired):
        phrase = normalize_term(match.group(0))
        if len(phrase) <= 10:
            terms.add(phrase)

    return {
        term
        for term in terms
        if term and len(term) >= 2 and term not in GENERIC_TERMS
    }


def _hard_cue_count(title: str) -> int:
    lowered = title.lower()
    return sum(cue.lower() in lowered for cue in HARD_CUES)


def _event_key(title: str) -> str:
    return re.sub(r"[^A-Za-z0-9\u4e00-\u9fff]+", "", title).lower()


def _negative_event(title: str) -> bool:
    return any(cue in title for cue in NEGATIVE_CUES)


def _theme_stage(
    recent_event_count: int,
    source_count: int,
    primary_count: int,
    hard_event_count: int,
) -> str:
    if recent_event_count >= 3 and source_count >= 2 and hard_event_count >= 2:
        return "emerging"
    if recent_event_count >= 2 and hard_event_count >= 2 and (
        source_count >= 2 or primary_count
    ):
        return "seed"
    return "weak_signal"


def discover_themes(
    items: Iterable[NewsItem],
    as_of: datetime,
    recent_hours: int = 168,
    baseline_days: int = 30,
    limit: int = 15,
) -> list[dict[str, Any]]:
    as_of = as_of.astimezone(BEIJING)
    recent_start = as_of - timedelta(hours=recent_hours)
    baseline_start = recent_start - timedelta(days=baseline_days)
    recent: dict[str, list[NewsItem]] = defaultdict(list)
    baseline: dict[str, list[NewsItem]] = defaultdict(list)

    for item in items:
        if item.published_at > as_of or item.published_at < baseline_start:
            continue
        target = recent if item.published_at >= recent_start else baseline
        for term in extract_terms(item.title):
            if (
                item.stock_name
                and term in item.stock_name
                and item.title.count(term) == 1
                and _hard_cue_count(item.title) == 0
            ):
                continue
            target[term].append(item)

    results: list[dict[str, Any]] = []
    recent_days = max(recent_hours / 24, 0.25)
    for term, rows in recent.items():
        recent_events: dict[str, list[NewsItem]] = defaultdict(list)
        baseline_events: dict[str, list[NewsItem]] = defaultdict(list)
        for row in rows:
            recent_events[_event_key(row.title)].append(row)
        for row in baseline.get(term, []):
            baseline_events[_event_key(row.title)].append(row)

        event_count = len(recent_events)
        baseline_count = len(baseline_events)
        source_count = len({row.source for row in rows})
        primary_count = sum(
            any(row.source in PRIMARY_SOURCES for row in event_rows)
            for event_rows in recent_events.values()
        )
        overseas_count = sum(
            any(row.source in OVERSEAS_SOURCES for row in event_rows)
            for event_rows in recent_events.values()
        )
        foreign_primary_count = sum(
            any(row.source in FOREIGN_PRIMARY_SOURCES for row in event_rows)
            for event_rows in recent_events.values()
        )
        hard_event_count = sum(
            any(_hard_cue_count(row.title) for row in event_rows)
            for event_rows in recent_events.values()
        )
        negative_event_count = sum(
            all(_negative_event(row.title) for row in event_rows)
            for event_rows in recent_events.values()
        )
        positive_event_count = event_count - negative_event_count
        direct_codes = sorted({row.stock_code for row in rows if row.stock_code})
        recent_rate = event_count / recent_days
        baseline_rate = (baseline_count + 0.5) / max(baseline_days, 1)
        velocity = recent_rate / baseline_rate
        score = (
            event_count * 2.0
            + source_count * 2.5
            + primary_count * 2.5
            + min(hard_event_count, 6) * 1.5
            + min(overseas_count, 4)
            + min(math.log1p(velocity) * 2.0, 8.0)
            - negative_event_count * 2.0
        )

        if positive_event_count < 2:
            continue
        if source_count < 2 and not primary_count:
            continue
        if hard_event_count < 2 and not (primary_count and positive_event_count >= 2):
            continue
        if velocity < 2.5:
            continue

        stage = _theme_stage(
            event_count,
            source_count,
            primary_count,
            hard_event_count,
        )
        if stage == "weak_signal":
            continue

        evidence = sorted(
            (
                max(event_rows, key=lambda row: row.published_at)
                for event_rows in recent_events.values()
            ),
            key=lambda row: row.published_at,
            reverse=True,
        )[:5]
        results.append(
            {
                "term": term,
                "stage": stage,
                "score": round(score, 2),
                "recent_count": event_count,
                "raw_mention_count": len(rows),
                "baseline_count": baseline_count,
                "velocity": round(velocity, 2),
                "source_count": source_count,
                "sources": sorted({row.source for row in rows}),
                "primary_count": primary_count,
                "overseas_signal_count": overseas_count,
                "foreign_primary_count": foreign_primary_count,
                "hard_cue_count": hard_event_count,
                "negative_event_count": negative_event_count,
                "direct_stock_codes": direct_codes,
                "needs_external_verification": foreign_primary_count == 0,
                "evidence": [
                    {
                        "published_at": row.published_at.isoformat(),
                        "source": row.source,
                        "title": row.title,
                        "stock_code": row.stock_code,
                        "stock_name": row.stock_name,
                        "url": row.url,
                    }
                    for row in evidence
                ],
            }
        )

    results.sort(
        key=lambda row: (row["stage"] == "emerging", row["score"]),
        reverse=True,
    )
    return results[:limit]


def _default_as_of(items: list[NewsItem]) -> datetime:
    if items:
        return max(item.published_at for item in items)
    return datetime.now(BEIJING)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Find fast-rising multi-event themes before stock ranking."
    )
    parser.add_argument("--news-index", type=Path, default=DEFAULT_NEWS_INDEX)
    parser.add_argument(
        "--as-of",
        help="Decision cutoff in ISO-8601; defaults to the newest indexed item.",
    )
    parser.add_argument("--recent-hours", type=int, default=168)
    parser.add_argument("--baseline-days", type=int, default=30)
    parser.add_argument("--limit", type=int, default=15)
    args = parser.parse_args()

    items = load_news(args.news_index)
    as_of = parse_time(args.as_of) if args.as_of else _default_as_of(items)
    if as_of is None:
        raise SystemExit("invalid --as-of time")
    payload = {
        "as_of": as_of.isoformat(),
        "recent_hours": args.recent_hours,
        "baseline_days": args.baseline_days,
        "themes": discover_themes(
            items,
            as_of,
            recent_hours=args.recent_hours,
            baseline_days=args.baseline_days,
            limit=args.limit,
        ),
    }
    payload["no_new_theme"] = not payload["themes"]
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
