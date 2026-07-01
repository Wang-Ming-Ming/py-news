from pathlib import Path

import pytest

from analysis.recommendation_journal import load_journal, record_recommendation, review_context


def payload(prefix: str) -> dict:
    return {
        "decision_time": "2026-06-18T09:20:00+08:00",
        "market_judgment": f"{prefix} market",
        "data_context": {"snapshot_time": "2026-06-18T09:19:00+08:00"},
        "theme_radar": [],
        "overseas_sector_context": [],
        "holding_actions": [],
        "new_theme_candidate": None,
        "candidates": [
            {
                "rank": rank,
                "code": str(600000 + rank),
                "name": f"{prefix}-{rank}",
                "slot_type": {
                    6: "stabilization_ignition",
                    7: "quality_selloff_reversal",
                    8: "low_pin_reversal",
                }.get(rank, "main_candidate"),
                "candidate_path": (
                    "major_fact" if rank == 1 else "theme_cluster_repricing"
                ),
                "chain_evidence_level": "tier1_direct",
                "fact_first_disclosed_at": "2026-06-17T18:00:00+08:00",
                "freshness_class": "new_material_fact",
                "materiality_grade": "A" if rank == 1 else "B+" if rank <= 5 else "B",
                "original_source_verified": True,
                "incremental_change": "new quantified order confirmed after the close",
                "economic_magnitude": "contract value is material to annual revenue",
                "market_confirmation": "auction and theme breadth confirmed",
                "buyability": "liquid and below the no-chase gap",
                "next_buyer": "theme followers and trend funds have room to add",
                "buy_trigger": "test trigger",
                "abandon_condition": "test abandon",
                "t1_survivability": "catalyst and liquidity remain valid through next session",
                **(
                    {
                        "selloff_date": "2026-06-17",
                        "selloff_pct": -5.2,
                        "selloff_cause_assessed": "market divergence, no company negative",
                        "thesis_intact": True,
                        "hard_risk_checked": True,
                        "repair_trigger": "reclaim VWAP and one-third of the selloff body",
                        "structural_invalidation": "break the selloff low and MA20",
                    }
                    if rank == 7
                    else {}
                ),
            }
            for rank in range(1, 9)
        ],
        "risk_gate": {
            "market_breadth_pct": 55.0,
            "risk_off": False,
            "countertrend_exception": False,
            "basis": "broad market and overseas benchmarks are stable",
        },
        "primary_pick": {
            "code": "600001",
            "name": f"{prefix}-1",
            "trigger_status": "triggered",
            "latest_article_at": "2026-06-18T08:00:00+08:00",
            "fact_first_disclosed_at": "2026-06-17T18:00:00+08:00",
            "oldest_matching_disclosure": "120-day search found no earlier matching fact",
            "freshness_lookback_days": 180,
            "freshness_class": "new_material_fact",
            "materiality_grade": "A",
            "original_source_verified": True,
            "incremental_change": "new quantified order confirmed after the close",
            "economic_magnitude": "contract value is material to annual revenue",
            "counterevidence": "gap risk and contract execution uncertainty checked",
            "market_confirmation": "auction and theme breadth confirmed",
            "buyability": "liquid and below the no-chase gap",
            "next_buyer": "theme followers and trend funds have room to add",
            "t1_survivability": "catalyst and liquidity remain valid through next session",
            "why_first": "strongest verified repricing path and execution quality",
            "max_position_pct": 10,
        },
        "provisional_focus_codes": [],
        "focus_codes": ["600001", "600002"],
        "no_trade": False,
        "response_summary": f"{prefix} summary",
    }


def overnight_payload(prefix: str) -> dict:
    record = payload(prefix)
    record["candidates"][6]["slot_type"] = "strong_anchor_low_position_acceptance"
    return record


def test_record_keeps_revisions_and_seals_latest(tmp_path: Path) -> None:
    path = tmp_path / "recommendations.json"
    first = record_recommendation(path, "morning", "2026-06-18", payload("first"))
    second = record_recommendation(path, "morning", "2026-06-18", payload("second"))

    runs = load_journal(path)["days"]["2026-06-18"]["morning"]
    assert len(runs) == 2
    assert runs[0]["status"] == "superseded"
    assert runs[0]["superseded_by"] == second["run_id"]
    assert runs[1]["status"] == "active"
    assert runs[1]["sealed"] is True
    assert first["content_sha256"] != second["content_sha256"]


def test_morning_record_requires_overseas_and_holding_context(tmp_path: Path) -> None:
    path = tmp_path / "recommendations.json"
    missing = payload("missing")
    missing.pop("holding_actions")

    with pytest.raises(ValueError, match="holding_actions"):
        record_recommendation(path, "morning", "2026-06-18", missing)


def test_morning_record_requires_theme_radar(tmp_path: Path) -> None:
    path = tmp_path / "recommendations.json"
    missing = payload("missing-theme")
    missing.pop("theme_radar")

    with pytest.raises(ValueError, match="theme_radar"):
        record_recommendation(path, "morning", "2026-06-18", missing)


def test_morning_record_requires_optional_ninth_slot_field(tmp_path: Path) -> None:
    path = tmp_path / "recommendations.json"
    missing = payload("missing-slot")
    missing.pop("new_theme_candidate")

    with pytest.raises(ValueError, match="new_theme_candidate"):
        record_recommendation(path, "morning", "2026-06-18", missing)


def test_new_theme_slot_requires_strict_evidence_and_can_be_focus(
    tmp_path: Path,
) -> None:
    path = tmp_path / "recommendations.json"
    record = payload("theme-slot")
    record["focus_codes"] = ["002674"]
    record["new_theme_candidate"] = {
        "slot": 9,
        "code": "002674",
        "name": "兴业科技",
        "theme_name": "磷化铟",
        "theme_stage": "emerging",
        "first_signal_time": "2026-06-16T01:12:34+08:00",
        "independent_evidence_count": 3,
        "public_at_cutoff": True,
        "primary_source_verified": True,
        "novelty_verified": True,
        "denial_or_loose_mapping": False,
        "freshness_class": "new_external_causal_shock",
        "materiality_grade": "A",
        "incremental_change": "overseas supply shock created a new domestic repricing path",
        "economic_magnitude": "supply constraint can materially change product pricing",
        "overseas_hard_evidence": "海外公司扩产且出口许可影响交付",
        "direct_company_evidence": "公司公告直接取得相关经营业务",
        "market_confirmation": "题材已有直接锚点并获得资金确认",
        "buyability": "非一字，存在可成交窗口",
        "next_buyer": "主题扩散资金和趋势资金",
        "buy_trigger": "主题与个股开盘同步确认",
        "abandon_condition": "题材锚点转弱或个股失去均价",
        "t1_survivability": "主题证据与流动性可维持至下一交易日",
    }
    record["primary_pick"].update(
        {
            "code": "002674",
            "name": "兴业科技",
            "latest_article_at": "2026-06-18T08:10:00+08:00",
            "fact_first_disclosed_at": "2026-06-16T01:12:34+08:00",
            "oldest_matching_disclosure": "180-day search found this as the first signal",
            "freshness_class": "new_external_causal_shock",
            "incremental_change": "overseas supply shock created a new domestic repricing path",
            "economic_magnitude": "supply constraint can materially change product pricing",
            "promotion_evidence": "slot 9 led the confirmed new theme after the open",
        }
    )

    saved = record_recommendation(path, "morning", "2026-06-18", record)

    assert saved["new_theme_candidate"]["slot"] == 9
    assert saved["new_theme_candidate"]["code"] == "002674"
    assert saved["focus_codes"] == ["002674"]


def test_new_theme_slot_rejects_loose_or_unverified_theme(tmp_path: Path) -> None:
    path = tmp_path / "recommendations.json"
    record = payload("weak-theme")
    record["focus_codes"] = []
    record["new_theme_candidate"] = {
        "slot": 9,
        "code": "002674",
        "name": "兴业科技",
        "theme_name": "磷化铟",
        "theme_stage": "seed",
        "independent_evidence_count": 1,
    }

    with pytest.raises(ValueError, match="theme_stage"):
        record_recommendation(path, "morning", "2026-06-18", record)


def test_provisional_focus_is_normalized_and_limited(tmp_path: Path) -> None:
    path = tmp_path / "recommendations.json"
    record = payload("provisional")
    record["focus_codes"] = []
    record["provisional_focus_codes"] = ["600001", "600002"]
    record["primary_pick"]["trigger_status"] = "pending"
    record["primary_pick"]["market_confirmation"] = "pending auction confirmation"

    saved = record_recommendation(path, "morning", "2026-06-18", record)

    assert saved["focus_codes"] == []
    assert saved["provisional_focus_codes"] == ["600001", "600002"]


def test_no_trade_rejects_executable_focus(tmp_path: Path) -> None:
    path = tmp_path / "recommendations.json"
    record = payload("no-trade")
    record["no_trade"] = True

    with pytest.raises(ValueError, match="cannot contain focus codes"):
        record_recommendation(path, "morning", "2026-06-18", record)


def test_morning_record_requires_exactly_eight_candidates(tmp_path: Path) -> None:
    path = tmp_path / "recommendations.json"
    record = payload("short-list")
    record["candidates"] = record["candidates"][:2]
    record["provisional_focus_codes"] = ["600001"]
    record["focus_codes"] = []
    record["primary_pick"]["trigger_status"] = "pending"
    record["primary_pick"]["market_confirmation"] = "pending auction confirmation"

    with pytest.raises(ValueError, match="exactly eight"):
        record_recommendation(path, "morning", "2026-06-18", record)


def test_empty_candidate_list_is_rejected_even_for_no_trade(tmp_path: Path) -> None:
    path = tmp_path / "recommendations.json"
    record = payload("empty")
    record["candidates"] = []
    record["provisional_focus_codes"] = []
    record["focus_codes"] = []
    record["primary_pick"] = None

    with pytest.raises(ValueError, match="exactly eight"):
        record_recommendation(path, "morning", "2026-06-18", record)

    record["no_trade"] = True
    with pytest.raises(ValueError, match="exactly eight"):
        record_recommendation(path, "morning", "2026-06-18", record)


def test_overnight_record_requires_exactly_eight_candidates(tmp_path: Path) -> None:
    path = tmp_path / "recommendations.json"
    record = overnight_payload("overnight-short")
    record["candidates"] = record["candidates"][:5]
    record["focus_codes"] = []
    record["provisional_focus_codes"] = []

    with pytest.raises(ValueError, match="exactly eight"):
        record_recommendation(path, "overnight", "2026-06-18", record)


def test_morning_special_slots_cannot_drift_into_generic_candidates(
    tmp_path: Path,
) -> None:
    path = tmp_path / "recommendations.json"
    record = payload("slot-drift")
    record["candidates"][5]["slot_type"] = "main_candidate"

    with pytest.raises(ValueError, match="rank 6 requires slot_type"):
        record_recommendation(path, "morning", "2026-06-18", record)


def test_morning_top_five_rejects_b_grade_filler(tmp_path: Path) -> None:
    path = tmp_path / "recommendations.json"
    record = payload("weak-top-five")
    record["candidates"][4]["materiality_grade"] = "B"

    with pytest.raises(ValueError, match="materiality_grade A or B\\+"):
        record_recommendation(path, "morning", "2026-06-18", record)


def test_quality_selloff_slot_requires_intact_thesis_and_risk_check(
    tmp_path: Path,
) -> None:
    path = tmp_path / "recommendations.json"
    record = payload("bad-selloff")
    record["candidates"][6]["thesis_intact"] = False

    with pytest.raises(ValueError, match="thesis_intact=true"):
        record_recommendation(path, "morning", "2026-06-18", record)


def test_quality_selloff_b_plus_can_be_promoted_after_live_repair(
    tmp_path: Path,
) -> None:
    path = tmp_path / "recommendations.json"
    record = payload("selloff-promotion")
    record["candidates"][6]["materiality_grade"] = "B+"
    record["focus_codes"] = ["600007"]
    record["primary_pick"].update(
        {
            "code": "600007",
            "name": "selloff-promotion-7",
            "materiality_grade": "B+",
            "execution_path": "quality_selloff_reversal",
            "freshness_lookback_days": 30,
            "quality_repair_evidence_count": 3,
            "chain_evidence_level": "tier1_direct",
            "trend_confirmation": "held the selloff low and reclaimed VWAP",
            "thesis_intact": True,
            "hard_risk_checked": True,
            "selloff_cause_assessed": "crowded unwind without a company negative",
            "repair_confirmation": "reclaimed half of the selloff body on volume",
            "promotion_evidence": "live repair led the theme after the open",
            "max_position_pct": 5,
        }
    )

    saved = record_recommendation(path, "morning", "2026-06-18", record)

    assert saved["primary_pick"]["code"] == "600007"
    assert saved["primary_pick"]["execution_path"] == "quality_selloff_reversal"


def test_executable_focus_requires_t1_survivability(tmp_path: Path) -> None:
    path = tmp_path / "recommendations.json"
    record = payload("t1")
    record["candidates"][0].pop("t1_survivability")

    with pytest.raises(ValueError, match="requires t1_survivability"):
        record_recommendation(path, "morning", "2026-06-18", record)


def test_primary_pick_rejects_stale_republication(tmp_path: Path) -> None:
    path = tmp_path / "recommendations.json"
    record = payload("stale")
    record["candidates"][0]["freshness_class"] = "stale_republication"
    record["primary_pick"]["freshness_class"] = "stale_republication"

    with pytest.raises(ValueError, match="execution-grade freshness_class"):
        record_recommendation(path, "morning", "2026-06-18", record)


def test_primary_pick_must_be_first_execution_code(tmp_path: Path) -> None:
    path = tmp_path / "recommendations.json"
    record = payload("order")
    record["primary_pick"]["code"] = "600002"
    record["primary_pick"]["name"] = "order-2"

    with pytest.raises(ValueError, match="must be first in focus_codes"):
        record_recommendation(path, "morning", "2026-06-18", record)


def test_pending_primary_cannot_promote_special_role_candidate(
    tmp_path: Path,
) -> None:
    path = tmp_path / "recommendations.json"
    record = payload("premarket-promotion")
    record["focus_codes"] = []
    record["provisional_focus_codes"] = ["600006"]
    record["primary_pick"].update(
        {
            "code": "600006",
            "name": "premarket-promotion-6",
            "trigger_status": "pending",
            "market_confirmation": "pending auction confirmation",
        }
    )

    with pytest.raises(ValueError, match="regular rank 1 or slot 9"):
        record_recommendation(path, "morning", "2026-06-18", record)


def test_triggered_rank_six_promotion_requires_new_market_evidence(
    tmp_path: Path,
) -> None:
    path = tmp_path / "recommendations.json"
    record = payload("opening-promotion")
    record["focus_codes"] = ["600006"]
    record["primary_pick"].update(
        {
            "code": "600006",
            "name": "opening-promotion-6",
        }
    )

    with pytest.raises(ValueError, match="promotion_evidence"):
        record_recommendation(path, "morning", "2026-06-18", record)

    record["primary_pick"]["promotion_evidence"] = (
        "after the open, rank 6 led its theme, held VWAP, and broke the attack high"
    )
    saved = record_recommendation(path, "morning", "2026-06-18", record)
    assert saved["primary_pick"]["code"] == "600006"


def test_weak_breadth_allows_only_triggered_small_countertrend_exception(
    tmp_path: Path,
) -> None:
    path = tmp_path / "recommendations.json"
    record = payload("risk-off")
    record["risk_gate"]["market_breadth_pct"] = 26.2
    record["risk_gate"]["risk_off"] = True

    with pytest.raises(ValueError, match="countertrend exception"):
        record_recommendation(path, "morning", "2026-06-18", record)

    record["risk_gate"]["countertrend_exception"] = True
    record["primary_pick"]["max_position_pct"] = 5
    saved = record_recommendation(path, "morning", "2026-06-18", record)
    assert saved["primary_pick"]["max_position_pct"] == 5


def test_theme_cluster_b_plus_can_be_primary_with_strict_evidence(
    tmp_path: Path,
) -> None:
    path = tmp_path / "recommendations.json"
    record = payload("theme-cluster")
    record["candidates"][0]["materiality_grade"] = "B+"
    record["candidates"][0]["freshness_class"] = "old_fact_new_context"
    record["primary_pick"].update(
        {
            "freshness_class": "old_fact_new_context",
            "materiality_grade": "B+",
            "execution_path": "theme_cluster_repricing",
            "freshness_lookback_days": 30,
            "independent_theme_evidence_count": 3,
            "chain_evidence_level": "tier2_verified",
            "trend_confirmation": "theme breadth expanded and the stock held VWAP",
            "max_position_pct": 5,
        }
    )

    saved = record_recommendation(path, "morning", "2026-06-18", record)

    assert saved["primary_pick"]["materiality_grade"] == "B+"
    assert saved["primary_pick"]["execution_path"] == "theme_cluster_repricing"


def test_theme_cluster_primary_requires_two_events_and_small_position(
    tmp_path: Path,
) -> None:
    path = tmp_path / "recommendations.json"
    record = payload("weak-cluster")
    record["primary_pick"].update(
        {
            "materiality_grade": "B",
            "execution_path": "trend_continuation",
            "freshness_lookback_days": 30,
            "independent_theme_evidence_count": 1,
            "chain_evidence_level": "tier1_direct",
            "trend_confirmation": "trend remains healthy",
            "max_position_pct": 6,
        }
    )

    with pytest.raises(ValueError, match="at least two independent"):
        record_recommendation(path, "morning", "2026-06-18", record)


def test_risk_off_pending_research_pick_allows_three_percent(
    tmp_path: Path,
) -> None:
    path = tmp_path / "recommendations.json"
    record = payload("risk-off-pending")
    record["risk_gate"]["market_breadth_pct"] = 25
    record["risk_gate"]["risk_off"] = True
    record["focus_codes"] = []
    record["provisional_focus_codes"] = ["600001"]
    record["primary_pick"]["trigger_status"] = "pending"
    record["primary_pick"]["max_position_pct"] = 3

    saved = record_recommendation(path, "morning", "2026-06-18", record)

    assert saved["primary_pick"]["max_position_pct"] == 3


def test_trend_mode_is_supported(tmp_path: Path) -> None:
    path = tmp_path / "recommendations.json"
    record = payload("trend")
    for field in (
        "theme_radar",
        "overseas_sector_context",
        "holding_actions",
        "new_theme_candidate",
        "risk_gate",
        "primary_pick",
    ):
        record.pop(field)

    saved = record_recommendation(path, "trend", "2026-06-18", record)

    assert saved["mode"] == "trend"
    assert len(saved["candidates"]) == 8


def test_review_context_uses_today_morning_and_previous_overnight(tmp_path: Path) -> None:
    path = tmp_path / "recommendations.json"
    record_recommendation(
        path,
        "overnight",
        "2026-06-17",
        overnight_payload("overnight"),
    )
    record_recommendation(path, "morning", "2026-06-18", payload("morning"))
    record_recommendation(
        path,
        "overnight",
        "2026-06-18",
        overnight_payload("pending"),
    )

    result = review_context(path, "2026-06-18")

    assert result["morning"]["market_judgment"] == "morning market"
    assert result["previous_overnight_trade_date"] == "2026-06-17"
    assert result["previous_overnight"]["market_judgment"] == "overnight market"
    assert result["pending_current_overnight"]["market_judgment"] == "pending market"
    assert result["missing"] == []


def test_review_context_does_not_substitute_an_older_overnight(tmp_path: Path) -> None:
    path = tmp_path / "recommendations.json"
    archive = tmp_path / "archive"
    snapshot = archive / "2026-06-17" / "market" / "snapshot"
    snapshot.mkdir(parents=True)
    (snapshot / "stocks.ndjson.gz").touch()
    record_recommendation(
        path,
        "overnight",
        "2026-06-16",
        overnight_payload("too-old"),
    )
    record_recommendation(path, "morning", "2026-06-18", payload("morning"))

    result = review_context(path, "2026-06-18", archive)

    assert result["previous_overnight_trade_date"] == "2026-06-17"
    assert result["previous_overnight"] is None
    assert "previous trading day overnight" in result["missing"]
