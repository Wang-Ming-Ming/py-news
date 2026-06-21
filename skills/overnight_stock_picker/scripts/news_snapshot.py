#!/usr/bin/env python3
"""Summarize recent py-study news data for overnight stock-picking analysis."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


THEMES: dict[str, list[str]] = {
    "AI/算力/数据中心": ["人工智能", "AI", "算力", "数据中心", "服务器", "英伟达", "NVIDIA", "GPU"],
    "CPO/光通信/PCB": ["CPO", "光通信", "光模块", "光纤", "光缆", "PCB", "铜连接", "高速连接"],
    "半导体/芯片": ["半导体", "芯片", "晶圆", "存储", "封测", "光刻", "先进封装", "集成电路"],
    "电力/绿电/能源保供": ["电力", "绿电", "迎峰度夏", "能源保供", "用电", "容量电价", "火电", "水电", "风电", "光伏", "储能"],
    "有色/稀土/钨": ["有色", "稀土", "钨", "铜", "铝", "锂", "金属", "矿"],
    "机器人/智能制造": ["机器人", "智能制造", "工业母机", "自动化", "减速器"],
    "消费/白酒/零售": ["消费", "白酒", "零售", "免税", "食品", "家电", "餐饮"],
    "医药/检测/疫苗": ["医药", "疫苗", "检测", "创新药", "病毒", "流感", "医疗", "生物"],
    "军工/地缘": ["军工", "航天", "导弹", "无人机", "地缘", "战争", "制裁", "反制"],
    "地产/基建": ["地产", "房地产", "基建", "城中村", "保障房", "建筑", "水利"],
    "金融/流动性": ["央行", "降准", "降息", "利率", "汇率", "人民币", "证券", "保险", "银行"],
}

HIGH_IMPACT_WORDS = [
    "国家发展改革委",
    "发改委",
    "国务院",
    "工信部",
    "商务部",
    "证监会",
    "央行",
    "政策",
    "通知",
    "会议",
    "反制",
    "制裁",
    "出口管制",
    "突发",
    "涨停",
    "大跌",
    "异动",
    "风险提示",
    "减持",
    "回购",
    "中标",
]


@dataclass(frozen=True)
class NewsItem:
    source: str
    title: str
    publish_time: datetime | None
    content: str
    url: str
    stock_code: str
    stock_name: str
    news_score: int
    news_tier: str
    risk_flags: tuple[str, ...]
    risk_level: str
    is_risk_alert: bool
    is_high_impact: bool

    @property
    def text(self) -> str:
        return f"{self.title} {self.content} {self.stock_name} {self.stock_code}"


def parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, (int, float)):
        # Xiaohongshu-style ms timestamps are not expected here, but support both.
        seconds = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


def load_items(data_dir: Path, days: int) -> list[NewsItem]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    items: list[NewsItem] = []
    seen: set[tuple[str, str, str]] = set()

    for path in sorted(data_dir.glob("*/*.json")):
        if path.name.startswith("."):
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(raw, list):
            continue
        for row in raw:
            if not isinstance(row, dict):
                continue
            title = str(row.get("title") or "").strip()
            if not title:
                continue
            published = parse_time(row.get("publish_time_bj") or row.get("publish_time"))
            if published and published < cutoff:
                continue
            source = str(row.get("source") or path.parent.name)
            url = str(row.get("url") or "")
            key = (source, title, url)
            if key in seen:
                continue
            seen.add(key)
            items.append(
                NewsItem(
                    source=source,
                    title=title,
                    publish_time=published,
                    content=str(row.get("content") or row.get("summary") or ""),
                    url=url,
                    stock_code=str(row.get("stock_code") or ""),
                    stock_name=str(row.get("stock_name") or ""),
                    news_score=_safe_int(row.get("news_score")),
                    news_tier=str(row.get("news_tier") or ""),
                    risk_flags=tuple(str(flag) for flag in row.get("risk_flags") or ()),
                    risk_level=str(row.get("risk_level") or "none"),
                    is_risk_alert=bool(row.get("is_risk_alert")),
                    is_high_impact=bool(row.get("is_high_impact")),
                )
            )

    items.sort(key=lambda item: item.publish_time or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    return items


def theme_hits(items: list[NewsItem]) -> dict[str, list[NewsItem]]:
    hits: dict[str, list[NewsItem]] = defaultdict(list)
    for item in items:
        text = item.text.lower()
        for theme, keywords in THEMES.items():
            if any(keyword.lower() in text for keyword in keywords):
                hits[theme].append(item)
    return hits


def format_time(dt: datetime | None) -> str:
    if not dt:
        return "unknown"
    return dt.astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def item_meta(item: NewsItem) -> str:
    meta: list[str] = []
    if item.news_score:
        meta.append(f"score={item.news_score}")
    if item.news_tier:
        meta.append(f"tier={item.news_tier}")
    if item.risk_flags:
        meta.append(f"risk={','.join(item.risk_flags)}")
    return f" ({'; '.join(meta)})" if meta else ""


def item_line(item: NewsItem) -> str:
    stock = f" [{item.stock_code} {item.stock_name}]" if item.stock_code or item.stock_name else ""
    prefix = "【风险】" if item.is_risk_alert else ""
    return f"- {format_time(item.publish_time)} {item.source}{stock}: {prefix}{item.title}{item_meta(item)}"


def print_markdown(items: list[NewsItem], limit: int) -> None:
    print("# Overnight News Snapshot")
    print()
    print(f"- total_deduped_items: {len(items)}")
    if items:
        print(f"- newest_time: {format_time(items[0].publish_time)}")
        print(f"- oldest_time_included: {format_time(items[-1].publish_time)}")

    source_counts = Counter(item.source for item in items)
    print()
    print("## Sources")
    for source, count in source_counts.most_common():
        print(f"- {source}: {count}")

    hits = theme_hits(items)
    print()
    print("## Theme Heat")
    for theme, rows in sorted(hits.items(), key=lambda pair: len(pair[1]), reverse=True):
        latest = rows[0] if rows else None
        suffix = f" | latest: {latest.title}" if latest else ""
        print(f"- {theme}: {len(rows)}{suffix}")

    print()
    print("## High Impact Items")
    high_impact = [
        item
        for item in items
        if item.is_high_impact
        or item.news_score >= 65
        or any(word.lower() in item.text.lower() for word in HIGH_IMPACT_WORDS)
    ]
    high_impact.sort(
        key=lambda item: (
            item.news_score,
            item.publish_time or datetime.min.replace(tzinfo=timezone.utc),
        ),
        reverse=True,
    )
    for item in high_impact[:limit]:
        print(item_line(item))

    print()
    print("## Risk Alerts")
    risk_items = [item for item in items if item.is_risk_alert or item.risk_flags]
    risk_items.sort(
        key=lambda item: (
            item.risk_level == "high",
            item.news_score,
            item.publish_time or datetime.min.replace(tzinfo=timezone.utc),
        ),
        reverse=True,
    )
    for item in risk_items[:limit]:
        print(item_line(item))

    print()
    print("## Latest Items")
    for item in items[:limit]:
        print(item_line(item))


def print_json(items: list[NewsItem], limit: int) -> None:
    hits = theme_hits(items)
    payload = {
        "total_deduped_items": len(items),
        "newest_time": format_time(items[0].publish_time) if items else None,
        "sources": Counter(item.source for item in items),
        "themes": {theme: len(rows) for theme, rows in hits.items()},
        "latest_items": [
            {
                "source": item.source,
                "title": item.title,
                "publish_time": format_time(item.publish_time),
                "url": item.url,
                "stock_code": item.stock_code,
                "stock_name": item.stock_name,
                "news_score": item.news_score,
                "news_tier": item.news_tier,
                "risk_flags": item.risk_flags,
                "risk_level": item.risk_level,
            }
            for item in items[:limit]
        ],
        "high_impact_items": [
            {
                "source": item.source,
                "title": item.title,
                "publish_time": format_time(item.publish_time),
                "news_score": item.news_score,
                "news_tier": item.news_tier,
                "risk_flags": item.risk_flags,
                "url": item.url,
            }
            for item in sorted(
                [row for row in items if row.is_high_impact or row.news_score >= 65],
                key=lambda row: (row.news_score, row.publish_time or datetime.min.replace(tzinfo=timezone.utc)),
                reverse=True,
            )[:limit]
        ],
        "risk_alerts": [
            {
                "source": item.source,
                "title": item.title,
                "publish_time": format_time(item.publish_time),
                "news_score": item.news_score,
                "risk_flags": item.risk_flags,
                "risk_level": item.risk_level,
                "url": item.url,
            }
            for item in sorted(
                [row for row in items if row.is_risk_alert or row.risk_flags],
                key=lambda row: (
                    row.risk_level == "high",
                    row.news_score,
                    row.publish_time or datetime.min.replace(tzinfo=timezone.utc),
                ),
                reverse=True,
            )[:limit]
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=dict))


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize py-study news data for overnight stock picking.")
    parser.add_argument("--data-dir", default="data_dev", help="Directory containing source/date JSON files.")
    parser.add_argument("--days", type=int, default=15, help="Include news from the last N days.")
    parser.add_argument("--limit", type=int, default=50, help="Number of latest/high-impact items to print.")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    items = load_items(data_dir, args.days)
    if args.format == "json":
        print_json(items, args.limit)
    else:
        print_markdown(items, args.limit)


if __name__ == "__main__":
    main()
