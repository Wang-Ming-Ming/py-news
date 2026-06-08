# -*- coding: utf-8 -*-
"""
新闻增强模块。

为原始新闻/公告补充四类面向短线分析的结构化字段：
- 统一北京时间
- 本地抓取/入库时间
- 风险公告标记
- 新闻影响力评分
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Tuple


BEIJING_TZ = timezone(timedelta(hours=8))
UTC_TZ = timezone.utc


SOURCE_BASE_SCORE = {
    "ndrc": 35,
    "cls": 25,
    "eastmoney_global": 22,
    "cninfo": 18,
}


RISK_KEYWORDS = {
    "share_reduction": [
        "拟减持",
        "计划减持",
        "被动减持",
        "清仓式减持",
        "股东减持",
        "董监高减持",
        "减持股份",
    ],
    "abnormal_volatility": [
        "异常波动",
        "交易异动",
        "严重异常波动",
        "风险提示公告",
        "股票交易风险提示",
        "非理性炒作",
        "短期涨幅较大",
    ],
    "clarification": [
        "澄清公告",
        "不涉及",
        "暂不涉及",
        "未涉及",
        "无关",
        "传闻不实",
        "未开展",
        "不存在应披露而未披露",
    ],
    "regulatory": [
        "监管函",
        "问询函",
        "关注函",
        "立案",
        "被调查",
        "行政处罚",
        "纪律处分",
        "留置",
    ],
    "performance": [
        "业绩预亏",
        "业绩下降",
        "净利润下降",
        "亏损",
        "商誉减值",
        "计提减值",
    ],
    "legal": [
        "重大诉讼",
        "仲裁",
        "司法冻结",
        "股份冻结",
        "质押",
        "司法拍卖",
    ],
    "delisting": [
        "退市",
        "*ST",
        " ST",
        "终止上市",
        "退市风险警示",
    ],
    "financing_dilution": [
        "向特定对象发行股票",
        "非公开发行股票",
        "定增",
        "增发",
        "摊薄即期回报",
    ],
}

HIGH_RISK_FLAGS = {
    "share_reduction",
    "abnormal_volatility",
    "regulatory",
    "delisting",
}

MEDIUM_RISK_FLAGS = {
    "clarification",
    "performance",
    "legal",
    "financing_dilution",
}

IMPACT_KEYWORD_GROUPS = [
    (
        "policy",
        35,
        [
            "国务院",
            "国家发展改革委",
            "发改委",
            "工信部",
            "商务部",
            "央行",
            "证监会",
            "国家能源局",
            "财政部",
            "国家电网",
            "海关总署",
            "政策",
            "通知",
            "会议",
            "方案",
        ],
    ),
    (
        "market_confirmation",
        30,
        [
            "涨停",
            "跌停",
            "拉升",
            "大涨",
            "大跌",
            "异动",
            "封板",
            "主力资金",
            "净买入",
            "净流入",
            "成交额",
            "午评",
            "复盘",
        ],
    ),
    (
        "industry_catalyst",
        25,
        [
            "短缺",
            "供不应求",
            "涨价",
            "价格上涨",
            "订单",
            "中标",
            "扩产",
            "量产",
            "技术突破",
            "重大突破",
            "AI服务器",
            "数据中心",
            "液冷",
            "PCB",
            "存储",
            "半导体",
            "算力",
        ],
    ),
    (
        "global_macro",
        20,
        [
            "英伟达",
            "NVIDIA",
            "台积电",
            "博通",
            "美联储",
            "特朗普",
            "OPEC",
            "制裁",
            "反制",
            "出口管制",
        ],
    ),
    (
        "company_event",
        15,
        [
            "回购",
            "增持",
            "并购",
            "收购",
            "重大资产重组",
            "投资建设",
            "对外投资",
            "战略合作",
            "重大合同",
            "股权激励",
        ],
    ),
]


def parse_publish_time_to_beijing(value: Any, source: str = "") -> Tuple[datetime | None, str]:
    """
    将不同来源的发布时间统一为北京时间。

    注意：部分源会把北京时间误标为 Z。这里按源做保守处理，
    保留原始 publish_time，额外写入 publish_time_bj 等字段。
    """
    if value is None or value == "":
        return None, "missing_publish_time"

    source_name = str(source or "").lower()

    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(seconds, tz=UTC_TZ).astimezone(BEIJING_TZ), "epoch_as_utc"

    text = str(value).strip()
    if not text:
        return None, "empty_publish_time"

    if text.endswith("Z"):
        raw = text[:-1]
        try:
            if source_name == "cls":
                dt = datetime.fromisoformat(f"{raw}+00:00")
                return dt.astimezone(BEIJING_TZ), "cls_z_as_utc"

            if source_name == "cninfo" and (
                raw.endswith("T16:00:00") or raw.endswith(" 16:00:00")
            ):
                dt = datetime.fromisoformat(f"{raw}+00:00")
                return dt.astimezone(BEIJING_TZ), "cninfo_midnight_z_as_utc"

            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=BEIJING_TZ)
            return dt.astimezone(BEIJING_TZ), f"{source_name or 'unknown'}_z_as_beijing_local"
        except ValueError:
            pass

    normalized = text.replace("/", "-")
    try:
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=BEIJING_TZ), "naive_as_beijing"
        return dt.astimezone(BEIJING_TZ), "timezone_converted_to_beijing"
    except ValueError:
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(normalized, fmt)
            return dt.replace(tzinfo=BEIJING_TZ), f"parsed_{fmt}_as_beijing"
        except ValueError:
            continue

    return None, "unparsed_publish_time"


def normalize_publish_time(data: Dict[str, Any], source: str = "") -> Dict[str, Any]:
    enriched = dict(data)
    source_name = str(source or enriched.get("source") or "")
    dt, note = parse_publish_time_to_beijing(enriched.get("publish_time"), source_name)

    if dt is not None:
        enriched["publish_time_bj"] = dt.isoformat(timespec="seconds")
        enriched["publish_time_bj_display"] = dt.strftime("%Y-%m-%d %H:%M:%S")
        enriched["publish_date_bj"] = dt.strftime("%Y-%m-%d")
        enriched["time_normalized"] = True
    else:
        enriched.setdefault("publish_time_bj", "")
        enriched.setdefault("publish_time_bj_display", "")
        enriched.setdefault("publish_date_bj", "")
        enriched["time_normalized"] = False

    enriched["time_parse_note"] = note
    return enriched


def annotate_crawl_time(
    data: Dict[str, Any],
    source: str = "",
    crawled_at: Any | None = None,
) -> Dict[str, Any]:
    """
    写入本地抓取/入库时间，并计算新闻源发布时间到本地入库的延迟。

    `publish_time*` 表示新闻源发布时间；`crawled_at*` 表示本项目实际抓到并保存前
    处理的时间。旧数据回填时可传入文件修改时间作为近似值。
    """
    enriched = dict(data)

    raw_crawled_at = crawled_at if crawled_at is not None else enriched.get("crawled_at")
    crawled_dt, crawl_note = _coerce_time_to_beijing(raw_crawled_at)
    if crawled_dt is None:
        crawled_dt = datetime.now(BEIJING_TZ)
        crawl_note = "generated_now"

    enriched["crawled_at"] = crawled_dt.isoformat(timespec="seconds")
    enriched["crawled_at_display"] = crawled_dt.strftime("%Y-%m-%d %H:%M:%S")
    enriched["crawled_date_bj"] = crawled_dt.strftime("%Y-%m-%d")
    enriched["crawl_time_note"] = crawl_note
    enriched.setdefault("crawled_at_source", "runtime")

    source_name = str(source or enriched.get("source") or "")
    publish_dt, _ = parse_publish_time_to_beijing(
        enriched.get("publish_time_bj") or enriched.get("publish_time"),
        source_name,
    )
    if publish_dt is None:
        enriched["latency_minutes"] = None
        enriched["latency_level"] = "unknown"
        enriched["latency_note"] = "missing_or_unparsed_publish_time"
        return enriched

    latency_minutes = (crawled_dt - publish_dt).total_seconds() / 60
    enriched["latency_minutes"] = round(latency_minutes, 2)
    enriched["latency_level"] = _resolve_latency_level(latency_minutes)
    enriched["latency_note"] = "crawled_at_minus_publish_time"
    return enriched


def detect_risk_flags(data: Dict[str, Any], source: str = "") -> Dict[str, Any]:
    enriched = dict(data)
    text = _combined_text(enriched)
    flags: List[str] = []
    reasons: List[str] = []

    for flag, keywords in RISK_KEYWORDS.items():
        hits = _find_keywords(text, keywords)
        if hits:
            flags.append(flag)
            reasons.append(f"{flag}: {', '.join(hits[:3])}")

    if any(flag in HIGH_RISK_FLAGS for flag in flags):
        risk_level = "high"
    elif any(flag in MEDIUM_RISK_FLAGS for flag in flags):
        risk_level = "medium"
    elif flags:
        risk_level = "low"
    else:
        risk_level = "none"

    enriched["risk_flags"] = flags
    enriched["risk_reasons"] = reasons
    enriched["risk_level"] = risk_level
    enriched["is_risk_alert"] = risk_level in {"medium", "high"}
    return enriched


def score_news(data: Dict[str, Any], source: str = "") -> Dict[str, Any]:
    enriched = dict(data)
    source_name = str(source or enriched.get("source") or "").lower()
    text = _combined_text(enriched)

    score = SOURCE_BASE_SCORE.get(source_name, 15)
    reasons: List[str] = [f"source_base:{score}"]
    matched_groups: List[str] = []
    group_hits: List[tuple[str, int, List[str]]] = []

    for group_name, weight, keywords in IMPACT_KEYWORD_GROUPS:
        hits = _find_keywords(text, keywords)
        if hits:
            matched_groups.append(group_name)
            group_hits.append((group_name, weight, hits))

    group_hits.sort(key=lambda row: row[1], reverse=True)
    for index, (group_name, weight, hits) in enumerate(group_hits):
        if index == 0:
            applied_weight = weight
        elif index == 1:
            applied_weight = round(weight * 0.6)
        else:
            applied_weight = min(8, round(weight * 0.3))
        score += applied_weight
        reasons.append(f"{group_name}+{applied_weight}: {', '.join(hits[:4])}")

    risk_level = str(enriched.get("risk_level") or "none")
    if risk_level == "high":
        score = max(score, 75)
        reasons.append("risk_alert_floor:75")
    elif risk_level == "medium":
        score = max(score, 65)
        reasons.append("risk_alert_floor:65")

    score = max(0, min(100, score))
    tier = _resolve_news_tier(matched_groups, risk_level)

    enriched["news_score"] = score
    enriched["news_tier"] = tier
    enriched["impact_reasons"] = reasons
    enriched["is_high_impact"] = score >= 65 or risk_level in {"medium", "high"}
    return enriched


def enrich_news_item(data: Dict[str, Any], source: str = "") -> Dict[str, Any]:
    source_name = str(source or data.get("source") or "")
    enriched = dict(data)
    enriched.setdefault("source", source_name)
    enriched = normalize_publish_time(enriched, source_name)
    enriched = annotate_crawl_time(enriched, source_name)
    enriched = detect_risk_flags(enriched, source_name)
    enriched = score_news(enriched, source_name)
    return enriched


def _coerce_time_to_beijing(value: Any) -> Tuple[datetime | None, str]:
    if value is None or value == "":
        return None, "missing_time"

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=BEIJING_TZ), "datetime_naive_as_beijing"
        return value.astimezone(BEIJING_TZ), "datetime_converted_to_beijing"

    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(seconds, tz=UTC_TZ).astimezone(BEIJING_TZ), "epoch_as_utc"

    text = str(value).strip()
    if not text:
        return None, "empty_time"

    normalized = text.replace("/", "-")
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"

    try:
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=BEIJING_TZ), "naive_as_beijing"
        return dt.astimezone(BEIJING_TZ), "timezone_converted_to_beijing"
    except ValueError:
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(normalized, fmt)
            return dt.replace(tzinfo=BEIJING_TZ), f"parsed_{fmt}_as_beijing"
        except ValueError:
            continue

    return None, "unparsed_time"


def _resolve_latency_level(latency_minutes: float) -> str:
    if latency_minutes < -1:
        return "clock_skew"
    if latency_minutes <= 10:
        return "fast"
    if latency_minutes <= 60:
        return "normal"
    if latency_minutes <= 180:
        return "slow"
    return "stale"


def _combined_text(data: Dict[str, Any]) -> str:
    fields = (
        data.get("title"),
        data.get("content"),
        data.get("summary"),
        data.get("stock_name"),
        data.get("stock_code"),
    )
    return " ".join(str(value) for value in fields if value)


def _find_keywords(text: str, keywords: Iterable[str]) -> List[str]:
    text_lower = text.lower()
    return [keyword for keyword in keywords if keyword.lower() in text_lower]


def _resolve_news_tier(matched_groups: List[str], risk_level: str) -> str:
    if risk_level in {"medium", "high"}:
        return "risk_alert"
    for tier in (
        "policy",
        "market_confirmation",
        "industry_catalyst",
        "global_macro",
        "company_event",
    ):
        if tier in matched_groups:
            return tier
    return "general"


__all__ = [
    "BEIJING_TZ",
    "annotate_crawl_time",
    "detect_risk_flags",
    "enrich_news_item",
    "normalize_publish_time",
    "parse_publish_time_to_beijing",
    "score_news",
]
