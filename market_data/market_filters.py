"""Reusable filters for A-share market snapshots."""

from __future__ import annotations

from typing import Any


RESTRICTED_PREFIXES = (
    "300",
    "301",
    "688",
    "689",
    "8",
    "4",
    "920",
)


def get_code(record: dict[str, Any]) -> str:
    code = str(record.get("代码") or record.get("证券代码") or record.get("股票代码") or "").strip()
    lowered = code.lower()
    for prefix in ("sh", "sz", "bj"):
        if lowered.startswith(prefix):
            return code[len(prefix):].strip()
    return code


def get_name(record: dict[str, Any]) -> str:
    return str(record.get("名称") or record.get("证券简称") or record.get("股票简称") or "").strip()


def is_st_or_delisting(name: str) -> bool:
    upper_name = name.upper()
    return "ST" in upper_name or "退" in name


def is_restricted_code(code: str, allow_chinext: bool = False) -> bool:
    if not code:
        return True
    if allow_chinext and (code.startswith("300") or code.startswith("301")):
        return False
    return code.startswith(RESTRICTED_PREFIXES)


def is_tradeable_main_market(record: dict[str, Any], allow_chinext: bool = False) -> bool:
    code = get_code(record)
    name = get_name(record)
    if is_restricted_code(code, allow_chinext=allow_chinext):
        return False
    if is_st_or_delisting(name):
        return False
    return True


def filter_tradeable(records: list[dict[str, Any]], allow_chinext: bool = False) -> list[dict[str, Any]]:
    return [record for record in records if is_tradeable_main_market(record, allow_chinext=allow_chinext)]
