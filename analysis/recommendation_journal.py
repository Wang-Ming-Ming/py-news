#!/usr/bin/env python3
"""Append-only journal for sealed morning and overnight recommendations."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import uuid
from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


CST = timezone(timedelta(hours=8))
DEFAULT_JOURNAL = Path("data_recommendations/daily_recommendations.json")
DEFAULT_MARKET_ARCHIVE = Path("data_server_cache/archive")
VALID_MODES = {"morning", "overnight"}


def now_iso() -> str:
    return datetime.now(CST).isoformat(timespec="seconds")


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def empty_journal() -> dict[str, Any]:
    return {"schema_version": "1.0", "updated_at": None, "days": {}}


def load_journal(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_journal()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("days"), dict):
        raise ValueError(f"invalid recommendation journal: {path}")
    payload.setdefault("schema_version", "1.0")
    payload.setdefault("updated_at", None)
    return payload


def load_input(path_text: str) -> dict[str, Any]:
    if path_text == "-":
        payload = json.load(sys.stdin)
    else:
        payload = json.loads(Path(path_text).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("record input must be a JSON object")
    return payload


def normalize_code(value: Any) -> str:
    text = str(value or "").strip()
    if text.isdigit():
        text = text.zfill(6)
    if not re.fullmatch(r"\d{6}", text):
        raise ValueError(f"invalid A-share code: {value!r}")
    return text


def validate_payload(payload: dict[str, Any], mode: str | None = None) -> dict[str, Any]:
    result = deepcopy(payload)
    candidates = result.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 8:
        raise ValueError("morning/overnight record must contain exactly eight candidates")

    ranks: set[int] = set()
    candidate_codes: set[str] = set()
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError("each candidate must be a JSON object")
        rank = int(candidate.get("rank") or 0)
        if rank not in range(1, 9) or rank in ranks:
            raise ValueError("candidate ranks must be unique integers 1-8")
        name = str(candidate.get("name") or "").strip()
        if not name:
            raise ValueError(f"candidate rank {rank} is missing name")
        code = normalize_code(candidate.get("code"))
        candidate["rank"] = rank
        candidate["code"] = code
        candidate["name"] = name
        ranks.add(rank)
        candidate_codes.add(code)

    if ranks != set(range(1, 9)):
        raise ValueError("candidate ranks must cover 1-8")
    candidates.sort(key=lambda item: item["rank"])

    focus_codes = [normalize_code(value) for value in result.get("focus_codes") or []]
    if len(focus_codes) > 3:
        raise ValueError("focus_codes can contain at most three stocks")
    if not set(focus_codes).issubset(candidate_codes):
        raise ValueError("focus_codes must be present in candidates")
    result["focus_codes"] = focus_codes
    result["market_judgment"] = str(result.get("market_judgment") or "").strip()
    result["response_summary"] = str(result.get("response_summary") or "").strip()
    result["no_trade"] = bool(result.get("no_trade", False))
    result.setdefault("data_context", {})
    if mode == "morning":
        for field in ("overseas_sector_context", "holding_actions"):
            if not isinstance(result.get(field), list):
                raise ValueError(f"morning record requires {field} as a list")
    return result


def record_recommendation(
    path: Path,
    mode: str,
    trade_date: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if mode not in VALID_MODES:
        raise ValueError(f"mode must be one of {sorted(VALID_MODES)}")
    date.fromisoformat(trade_date)
    content = validate_payload(payload, mode)
    recorded_at = now_iso()
    run_id = f"{trade_date}-{mode}-{datetime.now(CST).strftime('%H%M%S')}-{uuid.uuid4().hex[:8]}"
    digest_source = json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    entry = {
        "run_id": run_id,
        "mode": mode,
        "trade_date": trade_date,
        "recorded_at": recorded_at,
        "decision_time": content.pop("decision_time", recorded_at),
        "status": "active",
        "superseded_by": None,
        "sealed": True,
        "content_sha256": hashlib.sha256(digest_source.encode("utf-8")).hexdigest(),
        **content,
    }

    journal = load_journal(path)
    day_bucket = journal["days"].setdefault(trade_date, {"morning": [], "overnight": []})
    day_bucket.setdefault("morning", [])
    day_bucket.setdefault("overnight", [])
    for existing in day_bucket[mode]:
        if existing.get("status") == "active":
            existing["status"] = "superseded"
            existing["superseded_by"] = run_id
    day_bucket[mode].append(entry)
    journal["updated_at"] = recorded_at
    atomic_write(path, journal)
    return entry


def active_run(runs: list[dict[str, Any]]) -> dict[str, Any] | None:
    active = [item for item in runs if item.get("status") == "active"]
    if active:
        return active[-1]
    return runs[-1] if runs else None


def previous_market_date(archive_root: Path, review_date: str) -> str | None:
    candidates = {
        path.parts[-4]
        for path in archive_root.glob("*/market/*/stocks.ndjson.gz")
        if len(path.parts) >= 4 and path.parts[-4] < review_date
    }
    return max(candidates) if candidates else None


def review_context(
    path: Path,
    review_date: str,
    market_archive_root: Path | None = None,
) -> dict[str, Any]:
    date.fromisoformat(review_date)
    journal = load_journal(path)
    days = journal["days"]
    today = days.get(review_date) or {}
    morning = active_run(list(today.get("morning") or []))

    archived_previous_date = (
        previous_market_date(market_archive_root, review_date) if market_archive_root else None
    )
    previous_dates = sorted(
        day for day in days if day < review_date and (days[day].get("overnight") or [])
    )
    previous_overnight_date = archived_previous_date or (previous_dates[-1] if previous_dates else None)
    overnight = (
        active_run(list((days.get(previous_overnight_date) or {}).get("overnight") or []))
        if previous_overnight_date
        else None
    )
    pending_overnight = active_run(list(today.get("overnight") or []))

    missing = []
    if morning is None:
        missing.append(f"{review_date} morning")
    if overnight is None:
        missing.append("previous trading day overnight")
    return {
        "schema_version": "1.0",
        "generated_at": now_iso(),
        "review_date": review_date,
        "morning": morning,
        "previous_overnight_trade_date": previous_overnight_date,
        "previous_trade_date_source": "market_archive" if archived_previous_date else "journal_fallback",
        "previous_overnight": overnight,
        "pending_current_overnight": pending_overnight,
        "missing": missing,
        "review_rule": "review current trade-date morning and latest earlier trade-date overnight; current-date overnight remains pending",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seal and read daily stock recommendation records.")
    parser.add_argument("--journal", default=str(DEFAULT_JOURNAL))
    subparsers = parser.add_subparsers(dest="command", required=True)

    record_parser = subparsers.add_parser("record", help="append and seal a recommendation run")
    record_parser.add_argument("--mode", choices=sorted(VALID_MODES), required=True)
    record_parser.add_argument("--trade-date", required=True)
    record_parser.add_argument("--input", required=True, help="JSON file path, or - for stdin")

    show_parser = subparsers.add_parser("show", help="show all records for one date")
    show_parser.add_argument("--date", required=True)

    review_parser = subparsers.add_parser("review-context", help="build the 22:00 review input")
    review_parser.add_argument("--date", default=datetime.now(CST).date().isoformat())
    review_parser.add_argument("--output")
    review_parser.add_argument("--market-archive", default=str(DEFAULT_MARKET_ARCHIVE))

    args = parser.parse_args()
    journal_path = Path(args.journal)

    if args.command == "record":
        result = record_recommendation(journal_path, args.mode, args.trade_date, load_input(args.input))
    elif args.command == "show":
        result = load_journal(journal_path)["days"].get(args.date) or {}
    else:
        result = review_context(journal_path, args.date, Path(args.market_archive))
        if args.output:
            atomic_write(Path(args.output), result)

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
