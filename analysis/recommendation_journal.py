#!/usr/bin/env python3
"""Append-only journal for sealed stock recommendations."""

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
VALID_MODES = {"morning", "overnight", "trend"}
EXECUTION_FRESHNESS_CLASSES = {
    "new_material_fact",
    "new_certainty_upgrade",
    "new_external_causal_shock",
    "scheduled_repricing",
    "confirmed_fact",
    "high_quality_expectation",
    "old_fact_new_context",
}
MATERIALITY_GRADES = {"A", "B+", "B"}
EXECUTION_PATHS = {
    "major_fact",
    "theme_cluster_repricing",
    "verified_chain_expansion",
    "trend_continuation",
    "pre_activation",
}
THEME_LED_PATHS = {
    "theme_cluster_repricing",
    "verified_chain_expansion",
    "trend_continuation",
    "pre_activation",
}
VERIFIED_CHAIN_LEVELS = {"tier1_direct", "tier2_verified"}
SPECIAL_SLOT_TYPES = {
    6: "stabilization_ignition",
    7: "strong_anchor_low_position_acceptance",
    8: "low_pin_reversal",
}


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


def require_text(record: dict[str, Any], field: str, label: str) -> str:
    value = str(record.get(field) or "").strip()
    if not value:
        raise ValueError(f"{label} requires {field}")
    return value


def validate_execution_evidence(
    candidate: dict[str, Any],
    code: str,
    *,
    is_new_theme: bool,
) -> None:
    first_disclosure = (
        candidate.get("first_signal_time")
        if is_new_theme
        else candidate.get("fact_first_disclosed_at")
    )
    if not str(first_disclosure or "").strip():
        field = "first_signal_time" if is_new_theme else "fact_first_disclosed_at"
        raise ValueError(f"focus candidate {code} requires {field}")

    freshness_class = str(candidate.get("freshness_class") or "").strip()
    if freshness_class not in EXECUTION_FRESHNESS_CLASSES:
        raise ValueError(
            f"focus candidate {code} requires an execution-grade freshness_class"
        )
    if str(candidate.get("materiality_grade") or "").strip() not in MATERIALITY_GRADES:
        raise ValueError(f"focus candidate {code} requires materiality_grade A, B+ or B")

    source_verified = (
        candidate.get("primary_source_verified")
        if is_new_theme
        else candidate.get("original_source_verified")
    )
    if source_verified is not True:
        field = "primary_source_verified" if is_new_theme else "original_source_verified"
        raise ValueError(f"focus candidate {code} requires {field}=true")

    for field in (
        "incremental_change",
        "economic_magnitude",
        "market_confirmation",
        "buyability",
        "next_buyer",
        "t1_survivability",
    ):
        require_text(candidate, field, f"focus candidate {code}")


def validate_primary_pick(
    primary_pick: Any,
    *,
    candidates: list[dict[str, Any]],
    new_theme_candidate: dict[str, Any] | None,
    provisional_focus_codes: list[str],
    focus_codes: list[str],
    risk_gate: dict[str, Any],
) -> dict[str, Any] | None:
    if primary_pick is None:
        if provisional_focus_codes or focus_codes:
            raise ValueError("focus codes require a non-null primary_pick")
        return None
    if not isinstance(primary_pick, dict):
        raise ValueError("primary_pick must be an object or null")

    code = normalize_code(primary_pick.get("code"))
    candidate_rank = next(
        (item["rank"] for item in candidates if item["code"] == code),
        None,
    )
    is_new_theme = bool(
        isinstance(new_theme_candidate, dict)
        and new_theme_candidate.get("code") == code
    )
    if candidate_rank is None and not is_new_theme:
        raise ValueError("primary_pick must be present in candidates")

    trigger_status = str(primary_pick.get("trigger_status") or "").strip()
    if trigger_status == "pending":
        if not provisional_focus_codes or provisional_focus_codes[0] != code:
            raise ValueError(
                "pending primary_pick must be first in provisional_focus_codes"
            )
        if focus_codes:
            raise ValueError("pending primary_pick cannot have executable focus_codes")
        if candidate_rank != 1 and not is_new_theme:
            raise ValueError(
                "pre-confirmation primary_pick must be regular rank 1 or slot 9"
            )
    elif trigger_status == "triggered":
        if not focus_codes or focus_codes[0] != code:
            raise ValueError("triggered primary_pick must be first in focus_codes")
    else:
        raise ValueError("primary_pick trigger_status must be pending or triggered")

    freshness_class = str(primary_pick.get("freshness_class") or "").strip()
    if freshness_class not in EXECUTION_FRESHNESS_CLASSES:
        raise ValueError("primary_pick requires an execution-grade freshness_class")
    materiality_grade = str(primary_pick.get("materiality_grade") or "").strip()
    if materiality_grade not in MATERIALITY_GRADES:
        raise ValueError("primary_pick requires materiality_grade A, B+ or B")
    if primary_pick.get("original_source_verified") is not True:
        raise ValueError("primary_pick requires original_source_verified=true")

    execution_path = str(primary_pick.get("execution_path") or "").strip()
    if not execution_path:
        execution_path = "major_fact" if materiality_grade == "A" else ""
    if execution_path not in EXECUTION_PATHS:
        raise ValueError("primary_pick requires a valid execution_path")

    lookback_days = int(primary_pick.get("freshness_lookback_days") or 0)
    minimum_lookback = 120 if materiality_grade == "A" else 30
    if lookback_days < minimum_lookback:
        raise ValueError(
            f"primary_pick {materiality_grade} requires at least a "
            f"{minimum_lookback}-day freshness lookback"
        )

    for field in (
        "name",
        "latest_article_at",
        "fact_first_disclosed_at",
        "oldest_matching_disclosure",
        "incremental_change",
        "economic_magnitude",
        "counterevidence",
        "market_confirmation",
        "buyability",
        "next_buyer",
        "t1_survivability",
        "why_first",
    ):
        primary_pick[field] = require_text(primary_pick, field, "primary_pick")

    max_position_pct = float(primary_pick.get("max_position_pct") or 0)
    if max_position_pct <= 0 or max_position_pct > 15:
        raise ValueError("primary_pick max_position_pct must be within (0, 15]")

    if materiality_grade in {"B+", "B"}:
        if execution_path not in THEME_LED_PATHS:
            raise ValueError(
                "B+/B primary_pick must use a theme, verified-chain, trend, "
                "or pre-activation execution_path"
            )
        if int(primary_pick.get("independent_theme_evidence_count") or 0) < 2:
            raise ValueError(
                "B+/B primary_pick requires at least two independent theme evidence events"
            )
        chain_level = str(primary_pick.get("chain_evidence_level") or "").strip()
        if chain_level not in VERIFIED_CHAIN_LEVELS:
            raise ValueError(
                "B+/B primary_pick requires tier1_direct or tier2_verified "
                "chain_evidence_level"
            )
        require_text(primary_pick, "trend_confirmation", "B+/B primary_pick")
        if max_position_pct > 5:
            raise ValueError("B+/B primary_pick max_position_pct must be <= 5")

    if trigger_status == "triggered" and candidate_rank != 1:
        require_text(
            primary_pick,
            "promotion_evidence",
            "triggered non-rank-1 primary_pick",
        )

    breadth = risk_gate.get("market_breadth_pct")
    risk_off = risk_gate["risk_off"] or (
        isinstance(breadth, (int, float)) and breadth < 30
    )
    if risk_off:
        if trigger_status == "pending":
            if max_position_pct > 3:
                raise ValueError(
                    "risk-off pending primary_pick max_position_pct must be <= 3"
                )
        elif risk_gate["countertrend_exception"] is not True or max_position_pct > 5:
            raise ValueError(
                "risk-off/under-30% breadth triggered primary_pick requires a "
                "countertrend exception and max_position_pct <= 5"
            )

    primary_pick["code"] = code
    primary_pick["trigger_status"] = trigger_status
    primary_pick["freshness_class"] = freshness_class
    primary_pick["materiality_grade"] = materiality_grade
    primary_pick["execution_path"] = execution_path
    primary_pick["freshness_lookback_days"] = lookback_days
    primary_pick["max_position_pct"] = max_position_pct
    return primary_pick


def validate_payload(payload: dict[str, Any], mode: str | None = None) -> dict[str, Any]:
    result = deepcopy(payload)
    candidates = result.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("recommendation record candidates must be a list")
    if mode in {"morning", "overnight"} and len(candidates) != 8:
        raise ValueError(f"{mode} recommendation record must contain exactly eight candidates")
    if mode not in {"morning", "overnight"} and not 2 <= len(candidates) <= 8:
        raise ValueError("trend recommendation record must contain two to eight candidates")

    ranks: set[int] = set()
    candidate_codes: set[str] = set()
    expected_ranks = set(range(1, len(candidates) + 1))
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError("each candidate must be a JSON object")
        rank = int(candidate.get("rank") or 0)
        if rank not in expected_ranks or rank in ranks:
            raise ValueError("candidate ranks must be unique consecutive integers")
        name = str(candidate.get("name") or "").strip()
        if not name:
            raise ValueError(f"candidate rank {rank} is missing name")
        code = normalize_code(candidate.get("code"))
        candidate["rank"] = rank
        candidate["code"] = code
        candidate["name"] = name
        ranks.add(rank)
        if code in candidate_codes:
            raise ValueError("candidate codes must be unique")
        candidate_codes.add(code)

    if ranks != expected_ranks:
        raise ValueError("candidate ranks must cover 1 through candidate count")
    candidates.sort(key=lambda item: item["rank"])
    if mode in {"morning", "overnight"}:
        for rank, slot_type in SPECIAL_SLOT_TYPES.items():
            candidate = next(item for item in candidates if item["rank"] == rank)
            if str(candidate.get("slot_type") or "").strip() != slot_type:
                raise ValueError(
                    f"{mode} candidate rank {rank} requires slot_type={slot_type}"
                )

    new_theme_candidate = result.get("new_theme_candidate")
    if mode == "morning":
        if "new_theme_candidate" not in result:
            raise ValueError("morning record requires new_theme_candidate")
        if new_theme_candidate is not None:
            if not isinstance(new_theme_candidate, dict):
                raise ValueError("new_theme_candidate must be an object or null")
            if int(new_theme_candidate.get("slot") or 0) != 9:
                raise ValueError("new_theme_candidate must use dedicated slot 9")
            code = normalize_code(new_theme_candidate.get("code"))
            name = str(new_theme_candidate.get("name") or "").strip()
            if not name:
                raise ValueError("new_theme_candidate is missing name")
            if code in candidate_codes:
                raise ValueError("new_theme_candidate must not duplicate regular candidates")
            theme_stage = str(new_theme_candidate.get("theme_stage") or "").strip()
            if theme_stage not in {"emerging", "confirmed"}:
                raise ValueError(
                    "new_theme_candidate requires emerging or confirmed theme_stage"
                )
            if int(new_theme_candidate.get("independent_evidence_count") or 0) < 2:
                raise ValueError(
                    "new_theme_candidate requires at least two independent evidence events"
                )
            for flag in (
                "public_at_cutoff",
                "primary_source_verified",
                "novelty_verified",
            ):
                if new_theme_candidate.get(flag) is not True:
                    raise ValueError(f"new_theme_candidate requires {flag}=true")
            if new_theme_candidate.get("denial_or_loose_mapping") is not False:
                raise ValueError(
                    "new_theme_candidate requires denial_or_loose_mapping=false"
                )
            for field in (
                "theme_name",
                "first_signal_time",
                "overseas_hard_evidence",
                "direct_company_evidence",
                "market_confirmation",
                "buyability",
                "buy_trigger",
                "abandon_condition",
                "t1_survivability",
            ):
                if not str(new_theme_candidate.get(field) or "").strip():
                    raise ValueError(f"new_theme_candidate requires {field}")
            new_theme_candidate["slot"] = 9
            new_theme_candidate["code"] = code
            new_theme_candidate["name"] = name
            candidate_codes.add(code)
    result["new_theme_candidate"] = new_theme_candidate

    focus_codes = [normalize_code(value) for value in result.get("focus_codes") or []]
    if len(focus_codes) > 2:
        raise ValueError("focus_codes can contain at most two stocks")
    if len(focus_codes) != len(set(focus_codes)):
        raise ValueError("focus_codes must be unique")
    if not set(focus_codes).issubset(candidate_codes):
        raise ValueError("focus_codes must be present in candidates")
    result["focus_codes"] = focus_codes
    candidates_by_code = {item["code"]: item for item in candidates}
    if isinstance(new_theme_candidate, dict):
        candidates_by_code[new_theme_candidate["code"]] = new_theme_candidate
    for code in focus_codes:
        if not str(candidates_by_code[code].get("t1_survivability") or "").strip():
            raise ValueError(f"executable focus {code} requires t1_survivability")
    provisional_focus_codes = [
        normalize_code(value) for value in result.get("provisional_focus_codes") or []
    ]
    if len(provisional_focus_codes) > 2:
        raise ValueError("provisional_focus_codes can contain at most two stocks")
    if len(provisional_focus_codes) != len(set(provisional_focus_codes)):
        raise ValueError("provisional_focus_codes must be unique")
    if not set(provisional_focus_codes).issubset(candidate_codes):
        raise ValueError("provisional_focus_codes must be present in candidates")
    result["provisional_focus_codes"] = provisional_focus_codes
    no_trade = bool(result.get("no_trade", False))
    if no_trade and (focus_codes or provisional_focus_codes):
        raise ValueError("no_trade record cannot contain focus codes")
    result["market_judgment"] = str(result.get("market_judgment") or "").strip()
    result["response_summary"] = str(result.get("response_summary") or "").strip()
    result["no_trade"] = no_trade
    result.setdefault("data_context", {})
    if mode == "morning":
        for field in ("theme_radar", "overseas_sector_context", "holding_actions"):
            if not isinstance(result.get(field), list):
                raise ValueError(f"morning record requires {field} as a list")
        risk_gate = result.get("risk_gate")
        if not isinstance(risk_gate, dict):
            raise ValueError("morning record requires risk_gate as an object")
        for flag in ("risk_off", "countertrend_exception"):
            if not isinstance(risk_gate.get(flag), bool):
                raise ValueError(f"risk_gate requires boolean {flag}")
        require_text(risk_gate, "basis", "risk_gate")
        breadth = risk_gate.get("market_breadth_pct")
        if breadth is not None:
            if not isinstance(breadth, (int, float)) or not 0 <= breadth <= 100:
                raise ValueError("risk_gate market_breadth_pct must be null or 0-100")

        if "primary_pick" not in result:
            raise ValueError("morning record requires primary_pick")
        result["primary_pick"] = validate_primary_pick(
            result.get("primary_pick"),
            candidates=candidates,
            new_theme_candidate=new_theme_candidate,
            provisional_focus_codes=provisional_focus_codes,
            focus_codes=focus_codes,
            risk_gate=risk_gate,
        )
    for code in dict.fromkeys(provisional_focus_codes + focus_codes):
        candidate = candidates_by_code[code]
        validate_execution_evidence(
            candidate,
            code,
            is_new_theme=bool(
                isinstance(new_theme_candidate, dict)
                and new_theme_candidate.get("code") == code
            ),
        )
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
    day_bucket = journal["days"].setdefault(
        trade_date,
        {"morning": [], "overnight": [], "trend": []},
    )
    for valid_mode in VALID_MODES:
        day_bucket.setdefault(valid_mode, [])
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
