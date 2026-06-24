from __future__ import annotations

from analysis.low_pin_reversal_scanner import evaluate_series, macd


def observation(day: int, close: float, low: float | None = None, amount: float = 100_000_000):
    return {
        "market_date": f"2026-06-{day:02d}",
        "close": close,
        "open": close - 0.02,
        "high": close + 0.08,
        "low": low if low is not None else close - 0.08,
        "prev_close": close - 0.01,
        "pct": 0.1,
        "amount": amount,
        "volume": amount / close,
    }


def test_macd_detects_bottom_turn_or_expansion() -> None:
    values = [10, 9.8, 9.5, 9.2, 8.9, 8.6, 8.3, 8.0, 7.8, 7.6, 7.45, 7.35, 7.3, 7.31, 7.34, 7.38, 7.43]
    result = macd(values)
    assert result["state"] in {"red_turn", "red_expanding", "green_contracting"}
    assert result["dif"] is not None


def test_pin_evidence_rejects_high_position_even_with_lower_shadow() -> None:
    rows = [observation(index, 7 + index * 0.2) for index in range(1, 16)]
    rows[-1] = observation(16, 10.1, low=9.4)
    result = evaluate_series("600000", "测试股份", rows)
    assert result is not None
    assert result["lower_shadow_ratio"] > 0.28
    assert result["shape_pass"] is False


def test_recent_pin_then_breakout_is_confirmed() -> None:
    closes = [
        9.0, 8.8, 8.6, 8.4, 8.2, 8.05, 7.9, 7.75, 7.65, 7.55, 7.5,
        7.48, 7.46, 7.44, 7.43, 7.42, 7.41, 7.4, 7.39, 7.46, 7.42, 7.82,
    ]
    rows = [observation(index, close) for index, close in enumerate(closes, 1)]
    rows[-2].update(
        open=7.41,
        high=7.43,
        low=7.16,
        close=7.42,
        prev_close=7.46,
        amount=180_000_000,
    )
    rows[-1].update(
        open=7.43,
        high=8.06,
        low=7.43,
        close=7.82,
        prev_close=7.42,
        amount=450_000_000,
    )

    result = evaluate_series("600867", "通化东宝", rows)

    assert result is not None
    assert result["pattern_date"] == rows[-2]["market_date"]
    assert result["days_since_pin"] == 1
    assert result["shape_pass"] is True
    assert result["breakout_confirmation"] is True
    assert result["macd_confirmed"] is True
