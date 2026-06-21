from pathlib import Path

from analysis.recommendation_journal import load_journal, record_recommendation, review_context


def payload(prefix: str) -> dict:
    return {
        "decision_time": "2026-06-18T09:20:00+08:00",
        "market_judgment": f"{prefix} market",
        "data_context": {"snapshot_time": "2026-06-18T09:19:00+08:00"},
        "candidates": [
            {
                "rank": rank,
                "code": str(600000 + rank),
                "name": f"{prefix}-{rank}",
                "buy_trigger": "test trigger",
                "abandon_condition": "test abandon",
            }
            for rank in range(1, 8)
        ],
        "focus_codes": ["600001", "600002"],
        "no_trade": False,
        "response_summary": f"{prefix} summary",
    }


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


def test_review_context_uses_today_morning_and_previous_overnight(tmp_path: Path) -> None:
    path = tmp_path / "recommendations.json"
    record_recommendation(path, "overnight", "2026-06-17", payload("overnight"))
    record_recommendation(path, "morning", "2026-06-18", payload("morning"))
    record_recommendation(path, "overnight", "2026-06-18", payload("pending"))

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
    record_recommendation(path, "overnight", "2026-06-16", payload("too-old"))
    record_recommendation(path, "morning", "2026-06-18", payload("morning"))

    result = review_context(path, "2026-06-18", archive)

    assert result["previous_overnight_trade_date"] == "2026-06-17"
    assert result["previous_overnight"] is None
    assert "previous trading day overnight" in result["missing"]
