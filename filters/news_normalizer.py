"""Objective news time/provenance normalization with no impact or risk analysis."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


BEIJING_TZ = timezone(timedelta(hours=8))
UTC_TZ = timezone.utc


def parse_publish_time_to_beijing(value: Any, source: str = "") -> tuple[datetime | None, str]:
    if value in (None, ""):
        return None, "missing_publish_time"
    source_name = str(source or "").lower()
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(seconds, tz=UTC_TZ).astimezone(BEIJING_TZ), "epoch_as_utc"
    text = str(value).strip()
    if text.endswith("Z"):
        raw = text[:-1]
        try:
            if source_name == "cls" or (
                source_name == "cninfo" and (raw.endswith("T16:00:00") or raw.endswith(" 16:00:00"))
            ):
                return datetime.fromisoformat(f"{raw}+00:00").astimezone(BEIJING_TZ), f"{source_name}_z_as_utc"
            dt = datetime.fromisoformat(raw)
            return dt.replace(tzinfo=BEIJING_TZ) if dt.tzinfo is None else dt.astimezone(BEIJING_TZ), f"{source_name}_z_as_beijing_local"
        except ValueError:
            pass
    normalized = text.replace("/", "-")
    try:
        dt = datetime.fromisoformat(normalized)
        return (dt.replace(tzinfo=BEIJING_TZ), "naive_as_beijing") if dt.tzinfo is None else (dt.astimezone(BEIJING_TZ), "timezone_converted_to_beijing")
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(normalized, fmt).replace(tzinfo=BEIJING_TZ), f"parsed_{fmt}_as_beijing"
        except ValueError:
            continue
    return None, "unparsed_publish_time"


def _crawl_time(value: Any) -> tuple[datetime | None, str]:
    if value in (None, ""):
        return None, "missing_time"
    if isinstance(value, datetime):
        return (value.replace(tzinfo=BEIJING_TZ), "datetime_naive_as_beijing") if value.tzinfo is None else (value.astimezone(BEIJING_TZ), "datetime_converted_to_beijing")
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(seconds, tz=UTC_TZ).astimezone(BEIJING_TZ), "epoch_as_utc"
    text = str(value).strip().replace("/", "-")
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        dt = datetime.fromisoformat(text)
        return (dt.replace(tzinfo=BEIJING_TZ), "naive_as_beijing") if dt.tzinfo is None else (dt.astimezone(BEIJING_TZ), "timezone_converted_to_beijing")
    except ValueError:
        return None, "unparsed_time"


def normalize_news_item(data: dict[str, Any], source: str = "") -> dict[str, Any]:
    source_name = str(source or data.get("source") or "")
    normalized = dict(data)
    normalized.setdefault("source", source_name)
    stock_code = str(normalized.get("stock_code") or "").strip()
    if stock_code.isdigit() and len(stock_code) <= 6:
        normalized["stock_code"] = stock_code.zfill(6)
    publish_dt, publish_note = parse_publish_time_to_beijing(normalized.get("publish_time"), source_name)
    if publish_dt:
        normalized["publish_time_bj"] = publish_dt.isoformat(timespec="seconds")
        normalized["publish_time_bj_display"] = publish_dt.strftime("%Y-%m-%d %H:%M:%S")
        normalized["publish_date_bj"] = publish_dt.strftime("%Y-%m-%d")
        normalized["time_normalized"] = True
    else:
        normalized.update({"publish_time_bj": "", "publish_time_bj_display": "", "publish_date_bj": "", "time_normalized": False})
    normalized["time_parse_note"] = publish_note

    crawled_dt, crawl_note = _crawl_time(normalized.get("crawled_at"))
    if crawled_dt is None:
        crawled_dt = datetime.now(BEIJING_TZ)
        crawl_note = "generated_now"
    normalized["crawled_at"] = crawled_dt.isoformat(timespec="seconds")
    normalized["collected_at"] = normalized["crawled_at"]
    normalized["crawled_at_display"] = crawled_dt.strftime("%Y-%m-%d %H:%M:%S")
    normalized["crawled_date_bj"] = crawled_dt.strftime("%Y-%m-%d")
    normalized["crawl_time_note"] = crawl_note
    normalized.setdefault("crawled_at_source", "runtime")
    normalized["latency_minutes"] = round((crawled_dt - publish_dt).total_seconds() / 60, 2) if publish_dt else None
    normalized["latency_note"] = "crawled_at_minus_publish_time" if publish_dt else "missing_or_unparsed_publish_time"
    normalized["source_time"] = normalized.get("publish_time_bj") or normalized.get("publish_time") or ""
    source_url = str(normalized.get("url") or "").strip()
    existing_urls = normalized.get("source_urls") if isinstance(normalized.get("source_urls"), list) else []
    normalized["source_urls"] = list(dict.fromkeys([url for url in [*existing_urls, source_url] if url]))

    for field in (
        "risk_flags",
        "risk_reasons",
        "risk_level",
        "is_risk_alert",
        "news_score",
        "news_tier",
        "impact_reasons",
        "is_high_impact",
        "latency_level",
    ):
        normalized.pop(field, None)
    return normalized


__all__ = ["BEIJING_TZ", "normalize_news_item", "parse_publish_time_to_beijing"]
