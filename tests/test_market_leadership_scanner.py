from analysis.market_leadership_scanner import score_row


def row(**overrides):
    payload = {
        "code": "002366",
        "name": "测试股份",
        "price": 10.8,
        "pct": 4.85,
        "amount": 180_000_000,
        "amount_ratio_5d": 0.9,
        "volume": 170_000,
        "open": 10.35,
        "high": 10.9,
        "low": 10.2,
        "prev_close": 10.3,
        "history_points": 25,
        "range_position_15d": 0.68,
        "return_5d": 8.0,
        "return_10d": 14.0,
        "return_15d": 18.0,
        "ma5": 10.2,
        "ma10": 9.9,
        "ma20": 9.5,
    }
    payload.update(overrides)
    return payload


def test_scanner_finds_early_repricing_leader() -> None:
    result = score_row(row(), "morning")

    assert result is not None
    assert result["code"] == "002366"
    assert result["lane"] in {"early_repricing", "trend_continuation"}


def test_scanner_does_not_mechanically_reject_strong_trend() -> None:
    result = score_row(
        row(
            price=14.0,
            open=13.5,
            high=14.2,
            low=13.4,
            prev_close=13.3,
            pct=5.26,
            range_position_15d=0.96,
            return_5d=24.0,
            return_10d=48.0,
            return_15d=72.0,
            ma5=13.2,
            ma10=12.1,
            ma20=10.8,
            amount=600_000_000,
            volume=440_000,
        ),
        "morning",
    )

    assert result is not None
    assert result["lane"] == "trend_continuation"


def test_scanner_excludes_permission_boards_by_default() -> None:
    assert score_row(row(code="300001"), "morning") is None
    assert score_row(row(code="688001"), "morning") is None


def test_scanner_prioritizes_small_gain_expectation_trend_setup() -> None:
    result = score_row(
        row(
            price=10.55,
            open=10.43,
            high=10.62,
            low=10.38,
            prev_close=10.43,
            pct=1.15,
            range_position_15d=0.66,
            return_5d=2.0,
            return_10d=6.0,
            return_15d=11.0,
            ma5=10.35,
            ma10=10.15,
            ma20=9.9,
            amount_ratio_5d=0.82,
            volume=172_000,
        ),
        "morning",
    )

    assert result is not None
    assert result["lane"] == "expectation_trend_theme"
    assert result["expectation_trend_candidate"] is True
    assert result["capital_retention_signal"] is True
