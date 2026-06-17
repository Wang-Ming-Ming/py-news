#!/usr/bin/env python3
"""Fetch social sources through Agent-Reach tools and extract market signals."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from zoneinfo import ZoneInfo


CN_TZ = ZoneInfo("Asia/Shanghai")

THEME_PATTERNS = {
    "PCB": r"PCB|覆铜板|CCL|电子布|铜箔|玻纤布|高频高速板",
    "半导体材料": r"半导体材料|电子特气|特气|六氟化钨|WF6|光刻胶|晶圆|硅片|先进封装",
    "存储/HBM": r"存储|HBM|DRAM|NAND|闪存|海力士|三星|内存",
    "AI算力": r"算力|AI服务器|数据中心|GPU|英伟达|OpenAI|液冷|光模块|CPO",
    "机器人": r"机器人|具身智能|人形机器人|减速器|丝杠|执行器",
    "稀土/小金属": r"稀土|小金属|钨|钼|锑|锗|镓|铟|磁材",
    "有色金属": r"有色|铜|铝|锌|黄金|白银|贵金属|工业金属",
    "化工/涨价": r"化工|涨价|价格上调|供需|产能|库存|环氧|氟化工|磷化工",
    "政策/宏观": r"政策|国常会|发改委|央行|利率|汇率|关税|出口|消费",
}

SIGNAL_KEYWORDS = {
    "hard": ["订单", "中标", "涨价", "供需", "缺口", "产能", "扩产", "政策", "公告", "合同", "业绩", "国产替代"],
    "emotion": ["爆发", "龙头", "起飞", "翻倍", "主线", "最强", "无脑", "梭哈", "必涨", "涨停"],
    "risk": ["风险", "减持", "澄清", "监管", "异动", "高位", "兑现", "退潮", "分歧", "出货"],
}

STOCK_CODE_RE = re.compile(r"(?<!\d)([036]\d{5}|[123]\d{5}|688\d{3}|8\d{5}|9\d{5})(?!\d)")
MARKET_RELEVANCE_RE = re.compile(
    r"股市|股票|A股|证券|财经|炒股|板块|主线|涨停|高开|低开|短线|T\+1|"
    r"PCB|半导体|芯片|算力|机器人|有色|稀土|煤炭|化工|涨价|订单|政策|关税|汇率|利率",
    re.I,
)

HOME = Path.home()
CODEX_NODE_BIN = Path("/Applications/Codex.app/Contents/Resources/cua_node/bin")
AGENT_REACH_NODE_BIN = HOME / ".agent-reach" / "node" / "bin"
AGENT_REACH_VENV_BIN = HOME / ".agent-reach-venv" / "bin"
PRIVATE_ENV_FILES = [
    HOME / ".agent-reach" / "douyin.env",
]


def tool_path(name: str) -> Optional[str]:
    found = shutil.which(name)
    if found:
        return found
    for base in (AGENT_REACH_NODE_BIN, AGENT_REACH_VENV_BIN, HOME / ".local" / "bin"):
        candidate = base / name
        if candidate.exists():
            return str(candidate)
    return None


def load_env_file(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    env: Dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key:
            env[key] = value
    return env


def command_env() -> Dict[str, str]:
    env = os.environ.copy()
    for env_file in PRIVATE_ENV_FILES:
        for key, value in load_env_file(env_file).items():
            env.setdefault(key, value)
    extra_paths = [str(CODEX_NODE_BIN), str(AGENT_REACH_NODE_BIN), str(AGENT_REACH_VENV_BIN)]
    env["PATH"] = ":".join(extra_paths + [env.get("PATH", "")])
    return env


def now_iso() -> str:
    return datetime.now(CN_TZ).isoformat(timespec="seconds")


def load_sources(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Sources file not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Sources JSON must be a list")
    return data


def run_cmd(args: List[str], timeout: int = 60) -> Dict[str, Any]:
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout, env=command_env())
        return {
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except Exception as exc:
        return {"returncode": -1, "stdout": "", "stderr": repr(exc)}


def parse_jsonish(text: str) -> Optional[Any]:
    text = text.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return None


def mcp_call(tool_name: str, **params: Any) -> str:
    rendered = ", ".join(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in params.items())
    return f"{tool_name}({rendered})"


def resolve_url(url: str) -> str:
    curl = tool_path("curl")
    if not curl:
        return ""
    result = run_cmd([curl, "-L", "-I", "-s", "-o", "/dev/null", "-w", "%{url_effective}", url], timeout=30)
    if result["returncode"] != 0:
        return ""
    return result["stdout"].strip()


def is_douyin_profile_url(url: str) -> bool:
    return any(part in url for part in ("/share/user/", "/user/"))


def is_market_relevant(text: str) -> bool:
    return bool(MARKET_RELEVANCE_RE.search(text or ""))


def fetch_douyin_video(source: Dict[str, Any], url: str) -> Dict[str, Any]:
    mcporter = tool_path("mcporter")
    if not mcporter:
        return fail_record(source, "pending_tool_setup", "mcporter not found; configure Agent-Reach douyin MCP first")

    info_cmd = [mcporter, "call", mcp_call("douyin.parse_douyin_video_info", share_link=url)]
    info_result = run_cmd(info_cmd)
    info_text = info_result["stdout"].strip()
    if info_result["returncode"] != 0:
        final_url = resolve_url(url)
        if is_douyin_profile_url(final_url):
            return fail_record(
                source,
                "profile_pending_backend",
                f"Douyin profile link resolved to {final_url}; current douyin MCP only supports single video links.",
            )
        return fail_record(source, "fetch_failed", info_result["stderr"] or info_result["stdout"] or "douyin parse failed")

    if source.get("skip_irrelevant", True) and info_text and not is_market_relevant(info_text):
        return raw_record(
            source,
            "ignored_irrelevant",
            "mcporter:douyin.parse_douyin_video_info",
            info_text,
            {"parse_info": parse_jsonish(info_text)},
            None,
        )

    text_cmd = [mcporter, "call", mcp_call("douyin.extract_douyin_text", share_link=url)]
    text_result = run_cmd(text_cmd, timeout=180)

    raw_text = text_result["stdout"].strip()
    raw_json = {
        "extract_text": parse_jsonish(text_result["stdout"]),
        "parse_info": parse_jsonish(info_result["stdout"]),
        "extract_text_stderr": text_result["stderr"],
        "parse_info_stderr": info_result["stderr"],
    }
    ok = text_result["returncode"] == 0 and bool(raw_text)
    if not ok:
        missing_key_hint = "DASHSCOPE_API_KEY" if "DASHSCOPE_API_KEY" in (text_result["stderr"] + text_result["stdout"]) else ""
        error = text_result["stderr"] or text_result["stdout"] or "douyin fetch failed"
        if missing_key_hint:
            error = f"{error}; configure DASHSCOPE_API_KEY in ~/.agent-reach/douyin.env or environment"
        return fail_record(source, "fetch_failed", error)

    return raw_record(source, "success", "mcporter:douyin", raw_text, raw_json, None)


def fetch_douyin(source: Dict[str, Any]) -> Dict[str, Any]:
    url = source["source_url"]
    video_urls = source.get("video_urls") or []
    source_type = (source.get("source_type") or "").lower()

    if video_urls:
        child_records = []
        for index, video_url in enumerate(video_urls[: int(source.get("max_videos", 8))], start=1):
            child_source = dict(source)
            child_source["source_url"] = video_url
            child_source["source_name"] = f"{source.get('source_name')} video {index}"
            child_records.append(fetch_douyin_video(child_source, video_url))
            time.sleep(float(source.get("request_interval_seconds", 2)))
        combined = "\n\n".join(row.get("raw_text") or row.get("error") or "" for row in child_records)
        status = "success" if any(row.get("fetch_status") == "success" for row in child_records) else child_records[0].get("fetch_status", "fetch_failed")
        return raw_record(source, status, "mcporter:douyin.batch", combined, {"items": child_records}, None)

    if source_type == "profile":
        final_url = resolve_url(url)
        return fail_record(
            source,
            "profile_pending_backend",
            f"Douyin profile link cannot be enumerated by current douyin MCP. Resolved URL: {final_url or 'unknown'}. Add single video links to video_urls or configure a profile-capable backend.",
        )

    return fetch_douyin_video(source, url)


def xhs_note_url(note_id: str, xsec_token: str) -> str:
    return f"https://www.xiaohongshu.com/explore/{note_id}?xsec_token={xsec_token}&xsec_source=pc_search"


def xhs_card_text(item: Dict[str, Any]) -> str:
    card = item.get("note_card") or {}
    title = card.get("display_title") or card.get("title") or ""
    desc = card.get("desc") or ""
    tags = " ".join(tag.get("name", "") for tag in card.get("tag_list") or [] if isinstance(tag, dict))
    time_text = " ".join(info.get("text", "") for info in card.get("corner_tag_info") or [] if isinstance(info, dict))
    user = card.get("user") or {}
    author = user.get("nickname") or user.get("nick_name") or ""
    return " ".join(part for part in [title, desc, tags, time_text, author] if part)


def extract_xhs_note_refs(search_json: Any, source_name: str, limit: int) -> List[Dict[str, str]]:
    items = ((search_json or {}).get("data") or {}).get("items") or []
    refs: List[Dict[str, str]] = []
    for item in items:
        if item.get("model_type") != "note":
            continue
        note_id = item.get("id")
        xsec_token = item.get("xsec_token")
        if not note_id or not xsec_token:
            continue
        card = item.get("note_card") or {}
        user = card.get("user") or {}
        author = user.get("nickname") or user.get("nick_name") or ""
        text = xhs_card_text(item)
        if source_name and author and source_name not in author:
            continue
        if not is_market_relevant(text):
            continue
        refs.append(
            {
                "id": note_id,
                "xsec_token": xsec_token,
                "url": xhs_note_url(note_id, xsec_token),
                "title": card.get("display_title") or card.get("title") or "",
                "publish_time_text": " ".join(
                    info.get("text", "") for info in card.get("corner_tag_info") or [] if isinstance(info, dict)
                ),
            }
        )
        if len(refs) >= limit:
            break
    return refs


def fetch_xhs(source: Dict[str, Any]) -> Dict[str, Any]:
    url = source["source_url"]
    xhs = tool_path("xhs")
    if not xhs:
        return fail_record(source, "pending_tool_setup", "xhs command not found; install/configure xiaohongshu-cli and login first")

    # Direct profile reads can be unstable. Try read first, then search by source name.
    read_result = run_cmd([xhs, "read", url, "--json"], timeout=90)
    raw_text = read_result["stdout"].strip()
    if read_result["returncode"] != 0 or not raw_text:
        name = source.get("source_name") or url
        search_result = run_cmd([xhs, "search", name, "--sort", "latest", "--json"], timeout=90)
        raw_text = search_result["stdout"].strip()
        search_json = parse_jsonish(raw_text)
        detail_rows = []
        for ref in extract_xhs_note_refs(search_json, str(name), int(source.get("max_notes", 5))):
            detail_result = run_cmd([xhs, "read", ref["url"], "--json"], timeout=90)
            detail_rows.append(
                {
                    "ref": ref,
                    "returncode": detail_result["returncode"],
                    "stdout": detail_result["stdout"],
                    "stderr": detail_result["stderr"],
                    "json": parse_jsonish(detail_result["stdout"]),
                }
            )
            time.sleep(float(source.get("request_interval_seconds", 2)))
        detail_text = "\n\n".join(
            json.dumps(row.get("json") or row.get("stdout") or row.get("stderr"), ensure_ascii=False)
            for row in detail_rows
            if row.get("returncode") == 0
        )
        combined_text = "\n\n".join(part for part in [raw_text, detail_text] if part)
        raw_json = {
            "read": parse_jsonish(read_result["stdout"]),
            "search": search_json,
            "details": detail_rows,
            "read_stderr": read_result["stderr"],
            "search_stderr": search_result["stderr"],
        }
        ok = search_result["returncode"] == 0 and bool(combined_text)
        if not ok:
            return fail_record(source, "fetch_failed", search_result["stderr"] or read_result["stderr"] or "xhs fetch failed")
        return raw_record(source, "success", "xhs:search+read_details", combined_text, raw_json, None)

    return raw_record(source, "success", "xhs:read", raw_text, {"read": parse_jsonish(raw_text)}, None)


def fetch_web(source: Dict[str, Any]) -> Dict[str, Any]:
    if not shutil.which("curl"):
        return fail_record(source, "pending_tool_setup", "curl not found")
    url = source["source_url"]
    jina_url = "https://r.jina.ai/http://" + url.removeprefix("https://").removeprefix("http://")
    result = run_cmd(["curl", "-L", "--max-time", "30", jina_url], timeout=40)
    if result["returncode"] != 0 or not result["stdout"].strip():
        return fail_record(source, "fetch_failed", result["stderr"] or "web fetch failed")
    return raw_record(source, "success", "curl:jina", result["stdout"].strip(), None, None)


def raw_record(
    source: Dict[str, Any],
    status: str,
    tool: str,
    raw_text: str,
    raw_json: Optional[Any],
    error: Optional[str],
) -> Dict[str, Any]:
    return {
        "platform": source.get("platform"),
        "source_name": source.get("source_name"),
        "source_url": source.get("source_url"),
        "focus": source.get("focus"),
        "fetched_at": now_iso(),
        "fetch_status": status,
        "tool_used": tool,
        "raw_text": raw_text,
        "raw_json": raw_json,
        "error": error,
    }


def fail_record(source: Dict[str, Any], status: str, error: str) -> Dict[str, Any]:
    return raw_record(source, status, "none", "", None, error)


def fetch_source(source: Dict[str, Any], fetch: bool) -> Dict[str, Any]:
    if not fetch:
        return fail_record(source, "pending_fetch", "fetch disabled")
    platform = (source.get("platform") or "").lower()
    if platform == "douyin":
        return fetch_douyin(source)
    if platform in {"xiaohongshu", "xhs"}:
        return fetch_xhs(source)
    return fetch_web(source)


def keyword_hits(text: str, keywords: Iterable[str]) -> List[str]:
    return [kw for kw in keywords if kw in text]


def extract_signal(raw: Dict[str, Any]) -> Dict[str, Any]:
    text = raw.get("raw_text") or ""
    mentioned_themes = []
    mentioned_keywords = []
    for theme, pattern in THEME_PATTERNS.items():
        if re.search(pattern, text, re.I):
            mentioned_themes.append(theme)
            mentioned_keywords.extend(re.findall(pattern, text, re.I)[:8])

    mentioned_codes = sorted(set(STOCK_CODE_RE.findall(text)))
    hard_hits = keyword_hits(text, SIGNAL_KEYWORDS["hard"])
    emotion_hits = keyword_hits(text, SIGNAL_KEYWORDS["emotion"])
    risk_hits = keyword_hits(text, SIGNAL_KEYWORDS["risk"])

    content_available = raw.get("fetch_status") == "success" and bool(text.strip())
    hard_score = min(100, 15 * len(set(hard_hits)) + 10 * len(set(mentioned_themes)))
    emotion_score = min(100, 18 * len(set(emotion_hits)))
    if not content_available:
        trade_value = "pending_fetch"
        signal_type = "unknown"
        freshness = "unknown"
        crowding = "unknown"
    else:
        signal_type = "risk" if risk_hits else ("opinion" if mentioned_themes or hard_hits else "sentiment")
        crowding = "high" if emotion_score >= 55 else ("medium" if emotion_score >= 25 else "low")
        freshness = "unknown"
        trade_value = "usable_signal" if hard_score >= 50 and mentioned_themes else ("watch_only" if mentioned_themes else "sentiment_only")

    core_view = ""
    if content_available:
        snippet = re.sub(r"\s+", " ", text).strip()[:240]
        core_view = snippet
    else:
        core_view = f"Content not fetched: {raw.get('error')}"

    return {
        "platform": raw.get("platform"),
        "source_name": raw.get("source_name"),
        "source_url": raw.get("source_url"),
        "focus": raw.get("focus"),
        "publish_time": None,
        "fetched_at": raw.get("fetched_at"),
        "extracted_at": now_iso(),
        "content_available": content_available,
        "fetch_status": raw.get("fetch_status"),
        "tool_used": raw.get("tool_used"),
        "mentioned_stocks": [{"code": code, "name": None} for code in mentioned_codes],
        "mentioned_themes": mentioned_themes,
        "mentioned_keywords": sorted(set(str(x) for x in mentioned_keywords if x)),
        "core_view": core_view,
        "evidence": sorted(set(hard_hits + risk_hits)),
        "signal_type": signal_type,
        "hard_logic_score": hard_score,
        "emotion_score": emotion_score,
        "crowding_risk": crowding,
        "freshness": freshness,
        "trade_value": trade_value,
        "risk_notes": risk_hits or ([] if content_available else [raw.get("error")]),
        "usable_for_trading_skills": content_available and trade_value in {"usable_signal", "watch_only"},
    }


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources-json", default="data_social/sources/social_sources.json")
    parser.add_argument("--output-dir", default="data_social")
    parser.add_argument("--date", default=datetime.now(CN_TZ).date().isoformat())
    parser.add_argument("--fetch", action="store_true")
    args = parser.parse_args()

    sources_path = Path(args.sources_json)
    out_dir = Path(args.output_dir)
    sources = load_sources(sources_path)

    raw_rows = [fetch_source(source, args.fetch) for source in sources]
    signal_rows = [extract_signal(row) for row in raw_rows]

    raw_path = out_dir / "raw" / args.date / "raw_fetches.jsonl"
    extracted_path = out_dir / "extracted" / f"{args.date}.jsonl"
    latest_path = out_dir / "latest_social_signals.json"
    report_path = out_dir / f"fetch_report_{args.date}.json"

    write_jsonl(raw_path, raw_rows)
    write_jsonl(extracted_path, signal_rows)
    latest_path.write_text(json.dumps(signal_rows, ensure_ascii=False, indent=2), encoding="utf-8")

    report = {
        "generated_at": now_iso(),
        "sources_path": str(sources_path),
        "raw_path": str(raw_path),
        "extracted_path": str(extracted_path),
        "latest_path": str(latest_path),
        "total_sources": len(sources),
        "status_counts": {},
        "tool_availability": {
            "mcporter": bool(tool_path("mcporter")),
            "xhs": bool(tool_path("xhs")),
            "curl": bool(tool_path("curl")),
        },
    }
    for row in raw_rows:
        status = row.get("fetch_status")
        report["status_counts"][status] = report["status_counts"].get(status, 0) + 1
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
