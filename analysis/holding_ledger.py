#!/usr/bin/env python3
"""Maintain the user's explicitly confirmed current A-share holdings."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


CST = timezone(timedelta(hours=8))
DEFAULT_LEDGER = Path("data_portfolio/current_holdings.json")


def now_iso() -> str:
    return datetime.now(CST).isoformat(timespec="seconds")


def normalize_code(value: Any) -> str:
    text = str(value or "").strip()
    if text.isdigit():
        text = text.zfill(6)
    if not re.fullmatch(r"\d{6}", text):
        raise ValueError(f"invalid A-share code: {value!r}")
    return text


def empty_ledger() -> dict[str, Any]:
    return {"schema_version": "1.0", "updated_at": None, "positions": []}


def load_ledger(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_ledger()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("positions"), list):
        raise ValueError(f"invalid holdings ledger: {path}")
    payload.setdefault("schema_version", "1.0")
    payload.setdefault("updated_at", None)
    return payload


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def find_position(ledger: dict[str, Any], code: str) -> dict[str, Any] | None:
    return next((item for item in ledger["positions"] if item.get("code") == code), None)


def sort_positions(ledger: dict[str, Any]) -> None:
    ledger["positions"].sort(key=lambda item: item["code"])


def upsert_position(
    path: Path,
    code: str,
    name: str,
    quantity: int | None = None,
    average_cost: float | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    code = normalize_code(code)
    name = name.strip()
    if not name:
        raise ValueError("name is required")
    if quantity is not None and quantity <= 0:
        raise ValueError("quantity must be positive")
    if average_cost is not None and average_cost <= 0:
        raise ValueError("average_cost must be positive")

    ledger = load_ledger(path)
    position = find_position(ledger, code)
    timestamp = now_iso()
    if position is None:
        position = {
            "code": code,
            "name": name,
            "quantity": quantity,
            "average_cost": average_cost,
            "opened_at": timestamp,
            "last_updated_at": timestamp,
            "source": "user_confirmed",
        }
        ledger["positions"].append(position)
    else:
        position.update({"name": name, "last_updated_at": timestamp})
        if quantity is not None:
            position["quantity"] = quantity
        if average_cost is not None:
            position["average_cost"] = average_cost
    if note is not None:
        position["note"] = note.strip() or None
    ledger["updated_at"] = timestamp
    sort_positions(ledger)
    atomic_write(path, ledger)
    return position


def buy_position(
    path: Path,
    code: str,
    name: str,
    quantity: int,
    price: float,
) -> dict[str, Any]:
    if quantity <= 0 or price <= 0:
        raise ValueError("quantity and price must be positive")
    code = normalize_code(code)
    ledger = load_ledger(path)
    existing = find_position(ledger, code)
    if existing is None:
        return upsert_position(path, code, name, quantity, price)
    if existing.get("quantity") is None or existing.get("average_cost") is None:
        raise ValueError(
            f"holding {code} has unknown quantity/cost; correct it with upsert before recording an add"
        )

    old_quantity = int(existing["quantity"])
    new_quantity = old_quantity + quantity
    weighted_cost = (old_quantity * float(existing["average_cost"]) + quantity * price) / new_quantity
    return upsert_position(path, code, name, new_quantity, round(weighted_cost, 4))


def sell_position(path: Path, code: str, quantity: int | None = None) -> dict[str, Any]:
    code = normalize_code(code)
    if quantity is not None and quantity <= 0:
        raise ValueError("quantity must be positive")
    ledger = load_ledger(path)
    position = find_position(ledger, code)
    if position is None:
        raise ValueError(f"holding not found: {code}")

    held_quantity = position.get("quantity")
    timestamp = now_iso()
    if quantity is not None and held_quantity is None:
        raise ValueError(
            f"holding {code} has unknown quantity; use sell without quantity for a confirmed full exit"
        )
    if quantity is None or quantity >= int(held_quantity):
        ledger["positions"] = [item for item in ledger["positions"] if item.get("code") != code]
        result = {"code": code, "name": position.get("name"), "removed": True, "quantity": 0}
    else:
        position["quantity"] = int(held_quantity) - quantity
        position["last_updated_at"] = timestamp
        result = {**position, "removed": False}
    ledger["updated_at"] = timestamp
    sort_positions(ledger)
    atomic_write(path, ledger)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Maintain confirmed current A-share holdings.")
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("show", help="show current holdings")

    upsert = commands.add_parser("upsert", help="create or correct one current holding")
    upsert.add_argument("--code", required=True)
    upsert.add_argument("--name", required=True)
    upsert.add_argument("--quantity", type=int)
    upsert.add_argument("--average-cost", type=float)
    upsert.add_argument("--note")

    buy = commands.add_parser("buy", help="record a buy and calculate weighted average cost")
    buy.add_argument("--code", required=True)
    buy.add_argument("--name", required=True)
    buy.add_argument("--quantity", type=int, required=True)
    buy.add_argument("--price", type=float, required=True)

    sell = commands.add_parser("sell", help="record a partial sale or remove a fully sold holding")
    sell.add_argument("--code", required=True)
    sell.add_argument("--quantity", type=int)

    args = parser.parse_args()
    path = Path(args.ledger)
    if args.command == "show":
        result = load_ledger(path)
    elif args.command == "upsert":
        result = upsert_position(
            path,
            args.code,
            args.name,
            args.quantity,
            args.average_cost,
            args.note,
        )
    elif args.command == "buy":
        result = buy_position(path, args.code, args.name, args.quantity, args.price)
    else:
        result = sell_position(path, args.code, args.quantity)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
