import pytest

from analysis.holding_ledger import buy_position, load_ledger, sell_position, upsert_position


def test_buy_uses_weighted_average_and_full_sell_removes(tmp_path) -> None:
    path = tmp_path / "holdings.json"
    buy_position(path, "1", "平安银行", 100, 10.0)
    result = buy_position(path, "000001", "平安银行", 100, 12.0)

    assert result["code"] == "000001"
    assert result["quantity"] == 200
    assert result["average_cost"] == 11.0

    partial = sell_position(path, "000001", 50)
    assert partial["removed"] is False
    assert partial["quantity"] == 150

    removed = sell_position(path, "000001")
    assert removed["removed"] is True
    assert load_ledger(path)["positions"] == []


def test_upsert_allows_a_confirmed_holding_without_quantity(tmp_path) -> None:
    path = tmp_path / "holdings.json"
    result = upsert_position(path, "600000", "浦发银行", note="数量待用户确认")

    assert result["quantity"] is None
    assert result["average_cost"] is None
    assert result["source"] == "user_confirmed"

    with pytest.raises(ValueError, match="correct it with upsert"):
        buy_position(path, "600000", "浦发银行", 100, 10.0)
    with pytest.raises(ValueError, match="unknown quantity"):
        sell_position(path, "600000", 100)
