#!/usr/bin/env python3
"""Cached A-share trading calendar used by schedulers and the read-only API."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable


CST = timezone(timedelta(hours=8))
DEFAULT_CACHE_PATH = Path("data_market/trading_calendar.json")
DEFAULT_OVERRIDE_PATH = Path("market_calendar_overrides.json")


def _coerce_date(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()[:10]
    return datetime.strptime(text, "%Y-%m-%d").date()


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


@dataclass(frozen=True)
class CalendarInfo:
    available: bool
    source: str
    fetched_at: str | None
    trade_date_count: int
    first_trade_date: str | None
    last_trade_date: str | None
    error: str | None = None


class TradingCalendar:
    def __init__(
        self,
        cache_path: str | Path = DEFAULT_CACHE_PATH,
        allow_weekday_fallback: bool | None = None,
        override_path: str | Path | None = None,
    ) -> None:
        self.cache_path = Path(cache_path)
        self.allow_weekday_fallback = (
            os.getenv("TRADE_CALENDAR_ALLOW_WEEKDAY_FALLBACK", "0") == "1"
            if allow_weekday_fallback is None
            else allow_weekday_fallback
        )
        self.trade_dates: set[date] = set()
        self.closed_dates: set[date] = set()
        self.open_dates: set[date] = set()
        self.covered_years: set[int] = set()
        self.override_source = ""
        self.override_path = Path(
            override_path or os.getenv("TRADE_CALENDAR_OVERRIDES", str(DEFAULT_OVERRIDE_PATH))
        )
        self.source = "unavailable"
        self.fetched_at: str | None = None
        self.error: str | None = None
        self.load_overrides()
        self.load()

    @property
    def available(self) -> bool:
        return bool(self.trade_dates) or bool(self.covered_years) or self.allow_weekday_fallback

    def load_overrides(self) -> bool:
        if not self.override_path.exists():
            return False
        try:
            payload = json.loads(self.override_path.read_text(encoding="utf-8"))
            self.closed_dates = {_coerce_date(value) for value in payload.get("closed_dates") or []}
            self.open_dates = {_coerce_date(value) for value in payload.get("open_dates") or []}
            self.covered_years = {int(value) for value in payload.get("covered_years") or []}
            self.override_source = str(payload.get("source") or "override_file")
            return bool(self.covered_years)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            self.error = f"calendar override load failed: {exc}"
            return False

    def load(self) -> bool:
        if not self.cache_path.exists():
            return False
        try:
            payload = json.loads(self.cache_path.read_text(encoding="utf-8"))
            rows = payload.get("trade_dates") or []
            self.trade_dates = {_coerce_date(value) for value in rows}
            self.source = str(payload.get("source") or "cache")
            self.fetched_at = payload.get("fetched_at")
            self.error = None
            return bool(self.trade_dates)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            self.error = f"calendar cache load failed: {exc}"
            return False

    def refresh(self) -> bool:
        """Refresh the objective trade-date list from AKShare/Sina and cache it."""
        try:
            import akshare as ak

            frame = ak.tool_trade_date_hist_sina()
            column = "trade_date" if "trade_date" in frame.columns else frame.columns[0]
            dates = sorted({_coerce_date(value) for value in frame[column].tolist()})
            if len(dates) < 100:
                raise RuntimeError(f"calendar returned too few rows: {len(dates)}")
            fetched_at = datetime.now(CST).isoformat(timespec="seconds")
            payload = {
                "schema_version": "1.0",
                "source": "akshare.tool_trade_date_hist_sina",
                "fetched_at": fetched_at,
                "trade_dates": [value.isoformat() for value in dates],
            }
            _atomic_write_json(self.cache_path, payload)
            self.trade_dates = set(dates)
            self.source = payload["source"]
            self.fetched_at = fetched_at
            self.error = None
            return True
        except Exception as exc:
            self.error = f"calendar refresh failed: {exc}"
            return False

    def ensure(self, refresh_if_missing: bool = True) -> bool:
        if self.trade_dates:
            return True
        if refresh_if_missing and self.refresh():
            return True
        return self.available

    def is_trade_day(self, value: date | datetime | str) -> bool:
        target = _coerce_date(value)
        if target in self.open_dates:
            return True
        if target in self.closed_dates or target.weekday() >= 5:
            return False
        if target in self.trade_dates:
            return True
        if target.year in self.covered_years:
            return True
        if self.allow_weekday_fallback:
            return target.weekday() < 5
        return False

    def previous_trade_day(self, value: date | datetime | str, include_current: bool = False) -> date | None:
        target = _coerce_date(value)
        if include_current and self.is_trade_day(target):
            return target
        current = target - timedelta(days=1)
        for _ in range(400):
            if self.is_trade_day(current):
                return current
            current -= timedelta(days=1)
        return None

    def next_trade_day(self, value: date | datetime | str, include_current: bool = False) -> date | None:
        target = _coerce_date(value)
        if include_current and self.is_trade_day(target):
            return target
        current = target + timedelta(days=1)
        for _ in range(400):
            if self.is_trade_day(current):
                return current
            current += timedelta(days=1)
        return None

    def info(self) -> CalendarInfo:
        dates = sorted(self.trade_dates)
        return CalendarInfo(
            available=self.available,
            source=(
                self.source
                if self.trade_dates
                else (self.override_source if self.covered_years else ("weekday_fallback" if self.allow_weekday_fallback else "unavailable"))
            ),
            fetched_at=self.fetched_at,
            trade_date_count=len(dates),
            first_trade_date=dates[0].isoformat() if dates else None,
            last_trade_date=dates[-1].isoformat() if dates else None,
            error=self.error,
        )


def calendar_payload(calendar: TradingCalendar, now: datetime | None = None) -> dict:
    current = (now or datetime.now(CST)).astimezone(CST)
    today = current.date()
    previous_day = calendar.previous_trade_day(today, include_current=False)
    next_day = calendar.next_trade_day(today, include_current=False)
    info = calendar.info()
    return {
        "current_time": current.isoformat(timespec="seconds"),
        "current_date": today.isoformat(),
        "is_trade_day": calendar.is_trade_day(today),
        "previous_trade_day": previous_day.isoformat() if previous_day else None,
        "next_trade_day": next_day.isoformat() if next_day else None,
        "calendar": info.__dict__,
        "override": {
            "path": str(calendar.override_path),
            "covered_years": sorted(calendar.covered_years),
            "closed_date_count": len(calendar.closed_dates),
            "open_date_count": len(calendar.open_dates),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh or inspect the cached A-share trading calendar.")
    parser.add_argument("--cache", default=str(DEFAULT_CACHE_PATH))
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--allow-weekday-fallback", action="store_true")
    args = parser.parse_args()

    calendar = TradingCalendar(args.cache, allow_weekday_fallback=args.allow_weekday_fallback)
    if args.refresh:
        calendar.refresh()
    else:
        calendar.ensure(refresh_if_missing=True)
    print(json.dumps(calendar_payload(calendar), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
