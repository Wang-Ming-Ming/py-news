from __future__ import annotations

from analysis.quality_selloff_reversal_scanner import (
    evaluate_live_repair,
    evaluate_selloff,
)


def observation(
    market_date: str,
    close: float,
    *,
    previous_close: float,
    open_price: float | None = None,
    high: float | None = None,
    low: float | None = None,
    amount: float = 120_000_000,
) -> dict:
    open_value = open_price if open_price is not None else previous_close
    high_value = high if high is not None else max(open_value, close) * 1.01
    low_value = low if low is not None else min(open_value, close) * 0.99
    return {
        "market_date": market_date,
        "close": close,
        "open": open_value,
        "high": high_value,
        "low": low_value,
        "prev_close": previous_close,
        "pct": (close / previous_close - 1) * 100,
        "amount": amount,
        "volume": 0,
    }


def strong_then_selloff() -> list[dict]:
    closes = [
        10.00,
        10.15,
        10.25,
        10.40,
        10.60,
        10.85,
        11.05,
        11.25,
        11.50,
        11.75,
        12.00,
        12.20,
    ]
    observations = []
    previous = 9.90
    for index, close in enumerate(closes, start=1):
        observations.append(
            observation(
                f"2026-06-{index:02d}",
                close,
                previous_close=previous,
            )
        )
        previous = close
    observations.append(
        observation(
            "2026-06-15",
            11.59,
            previous_close=12.20,
            open_price=12.15,
            high=12.25,
            low=11.40,
            amount=180_000_000,
        )
    )
    return observations


def test_strong_stock_selloff_passes_technical_prefilter() -> None:
    result = evaluate_selloff("600001", "强势样本", strong_then_selloff())

    assert result is not None
    assert result["selloff_pct"] == -5.0
    assert result["prior_trend_strong"] is True
    assert result["trend_structure_intact"] is True
    assert result["top_rank_eligible_after_verification"] is True
    assert result["capital_retention_signal"] is True
    assert result["requires_selloff_cause_check"] is True


def test_long_downtrend_does_not_masquerade_as_quality_repair() -> None:
    closes = [15.0, 14.7, 14.4, 14.0, 13.7, 13.3, 13.0, 12.7, 12.4, 12.1, 11.8, 11.5]
    observations = []
    previous = 15.3
    for index, close in enumerate(closes, start=1):
        observations.append(
            observation(
                f"2026-06-{index:02d}",
                close,
                previous_close=previous,
            )
        )
        previous = close
    observations.append(
        observation(
            "2026-06-15",
            10.93,
            previous_close=11.5,
            open_price=11.4,
            high=11.45,
            low=10.8,
        )
    )

    assert evaluate_selloff("600002", "下降样本", observations) is None


def test_live_repair_requires_holding_low_and_reclaiming_selloff_body() -> None:
    candidate = evaluate_selloff("600001", "强势样本", strong_then_selloff())
    assert candidate is not None
    live_row = {
        "最新价": 11.90,
        "今开": 11.66,
        "最高": 11.94,
        "最低": 11.55,
        "昨收": 11.59,
        "涨跌幅": 2.67,
        "成交额": 90_000_000,
        "成交量": 0,
    }

    confirmation = evaluate_live_repair(candidate, live_row, "2026-06-16T09:45:00+08:00")

    assert confirmation["held_selloff_low"] is True
    assert confirmation["live_repair_confirmation"] is True
    assert confirmation["price"] >= confirmation["first_repair_price"]
