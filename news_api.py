# -*- coding: utf-8 -*-
"""Read-only objective data API for news, announcements, and A-share snapshots."""

from __future__ import annotations

import argparse
import base64
from collections import OrderedDict
import gzip
import hashlib
import json
import os
import shutil
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from config import STORAGE_CONFIG
from market_data.market_filters import get_code
from market_data.market_derivation import number
from market_data.objective_features import build_objective_features, discover_daily_snapshots
from market_data.trading_calendar import TradingCalendar, calendar_payload


SOURCES = {"cls", "cninfo", "ndrc", "eastmoney_global"}
SOURCE_STALE_MINUTES = {"cls": 30, "eastmoney_global": 60, "cninfo": 180, "ndrc": 480}
BEIJING_TZ = timezone(timedelta(hours=8))
ANALYSIS_FIELDS = {
    "risk_flags",
    "risk_reasons",
    "risk_level",
    "is_risk_alert",
    "news_score",
    "news_tier",
    "impact_reasons",
    "is_high_impact",
    "market_score",
    "next_day_accept_score",
    "high_open_score",
    "execution_grade",
    "rotation_risk",
    "next_day_fund_sources",
    "high_open_reasons",
    "requires_news_catalyst",
    "score_reasons",
    "risk_notes",
}


def _parse_time(value: Any) -> datetime:
    if not value:
        return datetime.min
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt
        return dt.astimezone(BEIJING_TZ).replace(tzinfo=None)
    except ValueError:
        return datetime.min


def _repair_mojibake(value: Any) -> Any:
    if not isinstance(value, str) or not any(marker in value for marker in ("ä", "ã", "Â")):
        return value
    try:
        repaired = value.encode("latin1").decode("utf-8")
        return repaired or value
    except UnicodeError:
        return value


def _objective_item(item: dict[str, Any]) -> dict[str, Any]:
    normalized = {key: value for key, value in item.items() if key not in ANALYSIS_FIELDS}
    for field in ("title", "content", "summary"):
        if field in normalized:
            normalized[field] = _repair_mojibake(normalized[field])
    return normalized


def _objective_derived(derived: dict[str, Any]) -> dict[str, Any]:
    output = dict(derived or {})
    rankings = dict(output.get("rankings") or {})
    for field in ("active_candidates", "overnight_candidates", "pool_industry_heat"):
        rankings.pop(field, None)
    output["rankings"] = rankings
    return output


def _public_snapshot(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    return {key: value for key, value in item.items() if key != "path"}


def _item_time(item: dict[str, Any]) -> datetime:
    return _parse_time(item.get("publish_time_bj") or item.get("publish_time"))


def _item_id(item: dict[str, Any]) -> str:
    raw = "|".join(
        str(item.get(field) or "")
        for field in ("source", "stock_code", "title", "publish_time", "url")
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


@lru_cache(maxsize=256)
def _sha256_file_cached(path_text: str, size: int, mtime_ns: int) -> str:
    digest = hashlib.sha256()
    with open(path_text, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_checksum(path: Path) -> str:
    stat = path.stat()
    return _sha256_file_cached(str(path), stat.st_size, stat.st_mtime_ns)


def _encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode("ascii")).decode("ascii").rstrip("=")


def _decode_cursor(value: str) -> int:
    if not value:
        return 0
    padding = "=" * (-len(value) % 4)
    return max(0, int(base64.urlsafe_b64decode(value + padding).decode("ascii")))


def _json_version(paths: list[Path]) -> str:
    parts = []
    for path in sorted(paths):
        try:
            stat = path.stat()
        except OSError:
            continue
        parts.append(f"{path}:{stat.st_size}:{stat.st_mtime_ns}")
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:20]


def _combined_checksum(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        try:
            digest.update(path.name.encode("utf-8"))
            digest.update(_file_checksum(path).encode("ascii"))
        except OSError:
            continue
    return digest.hexdigest()


class DataRepository:
    def __init__(
        self,
        data_dir: str,
        market_dir: str,
        retention_days: int,
        calendar_cache: str,
        collector_state: str,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.market_dir = Path(market_dir)
        self.retention_days = retention_days
        self.calendar = TradingCalendar(calendar_cache)
        self.calendar.ensure(refresh_if_missing=False)
        self.collector_state_path = Path(collector_state)
        self._snapshot_cache_signature: tuple[tuple[str, int, int], ...] | None = None
        self._snapshot_cache: list[dict[str, Any]] = []
        self._export_cache: OrderedDict[tuple[str, str], tuple[bytes, int]] = OrderedDict()
        self._source_health_cache_signature: tuple[tuple[str, int, int], ...] | None = None
        self._source_health_cache: dict[str, Any] = {}
        self._manifest_cache_signature: tuple[Any, ...] | None = None
        self._manifest_cache: dict[str, Any] = {}

    def news_files(
        self,
        source: str = "all",
        date_from: str = "",
        date_to: str = "",
    ) -> list[Path]:
        selected = SOURCES if source == "all" else {source}
        cutoff = (datetime.now(BEIJING_TZ) - timedelta(days=self.retention_days)).date()
        from_date = datetime.strptime(date_from, "%Y-%m-%d").date() if date_from else None
        to_date = datetime.strptime(date_to, "%Y-%m-%d").date() if date_to else None
        paths: list[Path] = []
        for source_name in selected:
            source_dir = self.data_dir / source_name
            if not source_dir.exists():
                continue
            for path in source_dir.glob("*.json"):
                try:
                    file_date = datetime.strptime(path.stem, "%Y-%m-%d").date()
                except ValueError:
                    continue
                if from_date and file_date < from_date:
                    continue
                if to_date and file_date > to_date:
                    continue
                if not from_date and not to_date and self.retention_days > 0 and file_date < cutoff:
                    continue
                paths.append(path)
        return sorted(paths)

    def load_news(
        self,
        source: str = "all",
        keyword: str = "",
        stock_code: str = "",
        date_from: str = "",
        date_to: str = "",
    ) -> tuple[list[dict[str, Any]], str]:
        paths = self.news_files(source, date_from=date_from, date_to=date_to)
        items: list[dict[str, Any]] = []
        for path in paths:
            try:
                rows = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                item = _objective_item(row)
                text = f"{item.get('title', '')} {item.get('content', '')} {item.get('summary', '')}"
                if keyword and keyword not in text:
                    continue
                if stock_code and str(item.get("stock_code") or "") != stock_code:
                    continue
                item["id"] = _item_id(item)
                items.append(item)
        items.sort(key=_item_time, reverse=True)
        return items, _json_version(paths)

    def source_health(self) -> dict[str, Any]:
        all_paths = self.news_files("all")
        signature = tuple(
            sorted((str(path), path.stat().st_size, path.stat().st_mtime_ns) for path in all_paths)
        )
        if signature == self._source_health_cache_signature:
            return {source: dict(item) for source, item in self._source_health_cache.items()}
        output: dict[str, Any] = {}
        for source in sorted(SOURCES):
            paths = self.news_files(source)
            newest_item_time = None
            item_count = 0
            if paths:
                rows, _ = self.load_news(source)
                item_count = len(rows)
                newest_item_time = (
                    rows[0].get("publish_time_bj") or rows[0].get("publish_time") if rows else None
                )
            newest_file = max(paths, key=lambda path: path.stat().st_mtime_ns) if paths else None
            archive_dates = sorted(
                datetime.strptime(path.stem, "%Y-%m-%d").date()
                for path in paths
            )
            output[source] = {
                "files": len(paths),
                "items": item_count,
                "newest_publish_time": newest_item_time,
                "coverage_start_date": archive_dates[0].isoformat() if archive_dates else None,
                "coverage_end_date": archive_dates[-1].isoformat() if archive_dates else None,
                "covered_calendar_days": (
                    (archive_dates[-1] - archive_dates[0]).days + 1 if archive_dates else 0
                ),
                "newest_file_mtime": (
                    datetime.fromtimestamp(newest_file.stat().st_mtime, tz=BEIJING_TZ).isoformat(timespec="seconds")
                    if newest_file
                    else None
                ),
            }
        self._source_health_cache_signature = signature
        self._source_health_cache = output
        return {source: dict(item) for source, item in output.items()}

    def _snapshot_candidates(self) -> list[Path]:
        paths: dict[str, Path] = {}
        for path in self.market_dir.glob("latest_*_snapshot.json"):
            paths[str(path.resolve())] = path
        for path in self.market_dir.glob("20??-??-??/*.json"):
            if "failed" not in path.name:
                paths[str(path.resolve())] = path
        return list(paths.values())

    def snapshot_index(self) -> list[dict[str, Any]]:
        candidates = self._snapshot_candidates()
        signature_rows = []
        for path in candidates:
            try:
                stat = path.stat()
            except OSError:
                continue
            signature_rows.append((str(path), stat.st_size, stat.st_mtime_ns))
        signature = tuple(sorted(signature_rows))
        if signature == self._snapshot_cache_signature:
            return list(self._snapshot_cache)

        index: dict[str, dict[str, Any]] = {}
        for path in candidates:
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            metadata = dict(payload.get("metadata") or {})
            summary = payload.get("derived", {}).get("summary", {})
            if int(summary.get("stock_count") or 0) < 1000:
                continue
            snapshot_id = metadata.get("snapshot_id")
            if not snapshot_id:
                raw = f"{metadata.get('mode')}|{metadata.get('captured_at')}"
                snapshot_id = f"legacy_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"
            item = {
                "snapshot_id": snapshot_id,
                "mode": metadata.get("mode"),
                "captured_at": metadata.get("captured_at"),
                "source_time": metadata.get("source_time") or metadata.get("captured_at"),
                "market_date": metadata.get("market_date"),
                "window_valid": metadata.get("window_valid", True),
                "stock_count": summary.get("stock_count"),
                "tradeable_stock_count": summary.get("tradeable_stock_count"),
                "expected_count": summary.get("stock_count"),
                "actual_count": summary.get("stock_count"),
                "is_complete": bool(metadata.get("window_valid", True)) and int(summary.get("stock_count") or 0) >= 1000,
                "path": str(path),
                "size_bytes": path.stat().st_size,
                "checksum": _file_checksum(path),
                "download_url": f"/v1/market/snapshots/{snapshot_id}/export?dataset=stocks",
            }
            existing = index.get(snapshot_id)
            if not existing or ("latest_" not in path.name and "latest_" in Path(existing["path"]).name):
                index[snapshot_id] = item
        result = sorted(index.values(), key=lambda item: item.get("captured_at") or "", reverse=True)
        self._snapshot_cache_signature = signature
        self._snapshot_cache = result
        return list(result)

    def load_snapshot(self, snapshot_id: str) -> tuple[dict[str, Any], Path]:
        for item in self.snapshot_index():
            if item["snapshot_id"] == snapshot_id:
                path = Path(item["path"])
                payload = json.loads(path.read_text(encoding="utf-8"))
                payload.setdefault("metadata", {})["snapshot_id"] = snapshot_id
                return payload, path
        raise KeyError(snapshot_id)

    def latest_snapshot(self, mode: str = "") -> dict[str, Any] | None:
        for item in self.snapshot_index():
            if not mode or item.get("mode") == mode:
                return item
        return None

    def objective_features(self, snapshot_id: str) -> dict[str, Any]:
        snapshot, _ = self.load_snapshot(snapshot_id)
        history = discover_daily_snapshots(self.market_dir, days=25)
        current_market_date = str(snapshot.get("metadata", {}).get("market_date") or "").replace("-", "")
        if current_market_date:
            history = [
                item
                for item in history
                if str(item.get("metadata", {}).get("market_date") or "").replace("-", "")
                <= current_market_date
            ]
        return build_objective_features(snapshot, history)

    def export_dataset(self, snapshot_id: str, dataset: str) -> tuple[bytes, int]:
        if dataset not in {"stocks", "features"}:
            raise ValueError(f"invalid export dataset: {dataset}")
        key = (snapshot_id, dataset)
        cached = self._export_cache.get(key)
        if cached is not None:
            self._export_cache.move_to_end(key)
            return cached
        snapshot, _ = self.load_snapshot(snapshot_id)
        rows = (
            self.objective_features(snapshot_id)["data"]
            if dataset == "features"
            else snapshot.get("raw", {}).get("stock_spot", [])
        )
        body = gzip.compress(
            b"".join((json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8") for row in rows),
            mtime=0,
        )
        result = (body, len(rows))
        self._export_cache[key] = result
        self._export_cache.move_to_end(key)
        while len(self._export_cache) > 32:
            self._export_cache.popitem(last=False)
        return result

    def stock_daily(
        self,
        code: str,
        days: int = 30,
        date_from: str = "",
        date_to: str = "",
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for snapshot in discover_daily_snapshots(self.market_dir, days=days):
            metadata = snapshot.get("metadata", {})
            market_date = str(metadata.get("market_date") or "")
            normalized_date = (
                f"{market_date[:4]}-{market_date[4:6]}-{market_date[6:8]}"
                if len(market_date) == 8 and market_date.isdigit()
                else market_date
            )
            if date_from and normalized_date < date_from:
                continue
            if date_to and normalized_date > date_to:
                continue
            for row in snapshot.get("raw", {}).get("stock_spot", []):
                if get_code(row) == code:
                    rows.append(
                        {
                            "market_date": metadata.get("market_date"),
                            "source_time": metadata.get("source_time") or metadata.get("captured_at"),
                            "data": row,
                        }
                    )
                    break
        return rows

    def stock_intraday(self, code: str, market_date: str) -> list[dict[str, Any]]:
        normalized = market_date.replace("-", "")
        rows: list[dict[str, Any]] = []
        for item in reversed(self.snapshot_index()):
            if str(item.get("market_date") or "").replace("-", "") != normalized:
                continue
            snapshot, _ = self.load_snapshot(item["snapshot_id"])
            for row in snapshot.get("raw", {}).get("stock_spot", []):
                if get_code(row) == code:
                    rows.append(
                        {
                            "snapshot_id": item["snapshot_id"],
                            "source_time": item["source_time"],
                            "mode": item["mode"],
                            "data": row,
                        }
                    )
                    break
        first_price = 0.0
        first_amount = 0.0
        previous_price = 0.0
        previous_amount = 0.0
        for index, item in enumerate(rows):
            data = item.get("data") or {}
            price = number(data, ["最新价", "收盘"])
            amount = number(data, ["成交额"])
            if index == 0:
                first_price = price
                first_amount = amount
            item["price"] = price
            item["amount"] = amount
            item["price_change_from_previous"] = round(price - previous_price, 4) if index else None
            item["amount_change_from_previous"] = round(amount - previous_amount, 2) if index else None
            item["price_change_from_first"] = round(price - first_price, 4)
            item["amount_change_from_first"] = round(amount - first_amount, 2)
            previous_price = price
            previous_amount = amount
        return rows

    def collector_state(self) -> dict[str, Any]:
        if not self.collector_state_path.exists():
            return {"sources": {}, "updated_at": None}
        try:
            payload = json.loads(self.collector_state_path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {"sources": {}, "updated_at": None}
        except (OSError, json.JSONDecodeError):
            return {"sources": {}, "updated_at": None}

    def history_bootstrap_state(self) -> dict[str, Any]:
        status_path = self.market_dir / "bootstrap_status.json"
        payload: dict[str, Any] = {}
        if status_path.exists():
            try:
                loaded = json.loads(status_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    payload = loaded
            except (OSError, json.JSONDecodeError):
                payload = {"status": "unreadable", "is_ready": False}
        complete_dates = sorted(
            {
                str(item.get("market_date") or "")
                for item in self.snapshot_index()
                if item.get("is_complete")
                and item.get("market_date")
                and (
                    item.get("mode") == "historical"
                    or _parse_time(item.get("source_time")).time() >= datetime.min.time().replace(hour=14, minute=55)
                )
            }
        )
        normalized_dates = [
            f"{value[:4]}-{value[4:6]}-{value[6:8]}"
            if len(value) == 8 and value.isdigit()
            else value
            for value in complete_dates
        ]
        payload.setdefault("status", "not_started")
        payload.setdefault("is_ready", False)
        payload["available_complete_dates"] = normalized_dates
        payload["available_complete_day_count"] = len(normalized_dates)
        return payload

    def health(self) -> dict[str, Any]:
        self.calendar.load()
        source_health = self.source_health()
        collector = self.collector_state()
        for source, state in (collector.get("sources") or {}).items():
            source_health.setdefault(source, {}).update(
                {
                    "last_success_at": state.get("last_success_at"),
                    "consecutive_failures": int(state.get("consecutive_failures") or 0),
                    "last_error": state.get("last_error"),
                    "paused_until": state.get("paused_until"),
                }
            )
        now_naive = datetime.now(BEIJING_TZ).replace(tzinfo=None)
        for source, item in source_health.items():
            reference = _parse_time(item.get("last_success_at") or item.get("newest_file_mtime"))
            age_minutes = None if reference == datetime.min else round((now_naive - reference).total_seconds() / 60, 2)
            threshold = SOURCE_STALE_MINUTES.get(source, 240)
            item["age_minutes"] = age_minutes
            item["stale_after_minutes"] = threshold
            item["missing"] = int(item.get("files") or 0) == 0
            item["is_stale"] = age_minutes is None or age_minutes > threshold
        latest_market = {
            mode: _public_snapshot(self.latest_snapshot(mode))
            for mode in ("morning", "midday", "overnight", "custom")
        }
        newest_market = max(
            (item for item in latest_market.values() if item),
            key=lambda item: item.get("captured_at") or "",
            default=None,
        )
        newest_time = _parse_time(newest_market.get("captured_at")) if newest_market else datetime.min
        latest_source_status: dict[str, Any] = {}
        if newest_market:
            try:
                latest_payload, _ = self.load_snapshot(str(newest_market["snapshot_id"]))
                latest_source_status = dict(latest_payload.get("source_status") or {})
            except (KeyError, OSError, json.JSONDecodeError):
                latest_source_status = {}
        missing_market_interfaces = [
            name for name, status in latest_source_status.items() if not bool((status or {}).get("ok"))
        ]
        market_delay_minutes = None
        if newest_time != datetime.min:
            market_delay_minutes = round(
                (datetime.now(BEIJING_TZ).replace(tzinfo=None) - newest_time).total_seconds() / 60,
                2,
            )
        disk = shutil.disk_usage(self.data_dir if self.data_dir.exists() else self.data_dir.parent)
        return {
            "status": "ok",
            "server_time": datetime.now(BEIJING_TZ).isoformat(timespec="seconds"),
            "timezone": "Asia/Shanghai",
            "calendar": calendar_payload(self.calendar),
            "sources": source_health,
            "collector": collector,
            "history_bootstrap": self.history_bootstrap_state(),
            "latest_market": latest_market,
            "market_status": {
                "latest_source_time": newest_market.get("source_time") if newest_market else None,
                "latest_stock_count": newest_market.get("stock_count") if newest_market else 0,
                "delay_minutes": market_delay_minutes,
                "missing": newest_market is None,
                "source_status": latest_source_status,
                "missing_interfaces": missing_market_interfaces,
            },
            "storage": {
                "total_bytes": disk.total,
                "used_bytes": disk.used,
                "free_bytes": disk.free,
            },
        }

    def manifest(self) -> dict[str, Any]:
        news_paths = self.news_files("all")
        news_version = _json_version(news_paths)
        announcement_paths = self.news_files("cninfo")
        snapshots = self.snapshot_index()
        history_bootstrap = self.history_bootstrap_state()
        signature = (
            news_version,
            tuple((item.get("snapshot_id"), item.get("checksum")) for item in snapshots),
            json.dumps(history_bootstrap, ensure_ascii=False, sort_keys=True),
        )
        if signature == self._manifest_cache_signature:
            return self._manifest_cache
        news_rows, _ = self.load_news("all")
        announcement_rows, announcement_version = self.load_news("cninfo")
        latest_news = news_rows[0] if news_rows else {}
        latest_announcement = announcement_rows[0] if announcement_rows else {}
        payload = {
            "schema_version": "1.0",
            "generated_at": datetime.now(BEIJING_TZ).isoformat(timespec="seconds"),
            "news": {
                "dataset_version": news_version,
                "files": len(news_paths),
                "source_time": latest_news.get("publish_time_bj") or latest_news.get("publish_time"),
                "collected_at": latest_news.get("crawled_at"),
                "expected_count": len(news_rows),
                "actual_count": len(news_rows),
                "checksum": _combined_checksum(news_paths),
                "is_complete": True,
                "size_bytes": sum(path.stat().st_size for path in news_paths),
                "download_url": "/v1/news",
                "next_cursor": _encode_cursor(200) if len(news_rows) > 200 else None,
            },
            "announcements": {
                "dataset_version": announcement_version,
                "files": len(announcement_paths),
                "source_time": latest_announcement.get("publish_time_bj") or latest_announcement.get("publish_time"),
                "collected_at": latest_announcement.get("crawled_at"),
                "expected_count": len(announcement_rows),
                "actual_count": len(announcement_rows),
                "checksum": _combined_checksum(announcement_paths),
                "is_complete": True,
                "size_bytes": sum(path.stat().st_size for path in announcement_paths),
                "download_url": "/v1/announcements",
                "next_cursor": _encode_cursor(100) if len(announcement_rows) > 100 else None,
            },
            "market": {
                "snapshots": [_public_snapshot(item) for item in snapshots[:40]],
                "latest": {
                    mode: _public_snapshot(self.latest_snapshot(mode))
                    for mode in ("morning", "midday", "overnight", "custom")
                },
                "history_bootstrap": history_bootstrap,
            },
        }
        self._manifest_cache_signature = signature
        self._manifest_cache = payload
        return payload


def load_news(
    base_path: str,
    source: str = "all",
    limit: int = 100,
    keyword: str = "",
    retention_days: int = 15,
) -> list[dict[str, Any]]:
    repository = DataRepository(base_path, "data_market", retention_days, "data_market/trading_calendar.json", "data/collector_health.json")
    items, _ = repository.load_news(source=source, keyword=keyword)
    return items[:limit]


class DataAPIHandler(BaseHTTPRequestHandler):
    repository: DataRepository
    api_token = ""

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        query = parse_qs(parsed.query)

        if self.api_token and not self._authorized():
            self._send_json({"error": "unauthorized"}, status=401)
            return

        try:
            if path == "/health":
                self._send_json(self.repository.health())
            elif path == "/news":
                self._legacy_news(query)
            elif path == "/v1/health":
                self._send_json(self.repository.health())
            elif path == "/v1/calendar":
                self.repository.calendar.load()
                self._send_json(calendar_payload(self.repository.calendar))
            elif path == "/v1/manifest":
                self._send_json(self.repository.manifest())
            elif path == "/v1/news":
                self._news_page(query, source_default="all")
            elif path.startswith("/v1/news/"):
                self._news_detail(path.rsplit("/", 1)[-1], source="all")
            elif path == "/v1/announcements":
                self._news_page(query, source_default="cninfo")
            elif path.startswith("/v1/announcements/"):
                self._news_detail(path.rsplit("/", 1)[-1], source="cninfo")
            elif path == "/v1/market/snapshots":
                rows = self.repository.snapshot_index()
                market_date = query.get("market_date", [""])[0].replace("-", "")
                mode = query.get("mode", [""])[0]
                if market_date:
                    rows = [item for item in rows if str(item.get("market_date") or "").replace("-", "") == market_date]
                if mode:
                    rows = [item for item in rows if item.get("mode") == mode]
                version = hashlib.sha256(
                    "|".join(str(item.get("snapshot_id") or "") for item in rows).encode("utf-8")
                ).hexdigest()[:20]
                requested_version = query.get("dataset_version", [""])[0]
                if requested_version and requested_version != version:
                    self._send_json({"error": "dataset version changed", "dataset_version": version}, status=409)
                    return
                limit = max(1, min(int(query.get("limit", ["200"])[0]), 500))
                offset = _decode_cursor(query.get("cursor", [""])[0])
                page = [_public_snapshot(item) for item in rows[offset : offset + limit]]
                next_offset = offset + len(page)
                self._send_json(
                    {
                        "dataset_version": version,
                        "expected_count": len(rows),
                        "returned_count": len(page),
                        "next_cursor": _encode_cursor(next_offset) if next_offset < len(rows) else None,
                        "is_complete": next_offset >= len(rows),
                        "data": page,
                    }
                )
            elif path == "/v1/market/pools":
                self._market_pools(query)
            elif path.startswith("/v1/market/snapshots/"):
                self._market_snapshot_route(path, query)
            elif path.startswith("/v1/market/stocks/"):
                self._stock_route(path, query)
            else:
                self._send_json({"error": "not found"}, status=404)
        except KeyError as exc:
            self._send_json({"error": f"not found: {exc}"}, status=404)
        except (ValueError, TypeError) as exc:
            self._send_json({"error": str(exc)}, status=400)
        except Exception as exc:
            self._send_json({"error": f"internal error: {exc}"}, status=500)

    def _authorized(self) -> bool:
        if not self.api_token:
            return True
        bearer = self.headers.get("Authorization", "")
        token = self.headers.get("X-API-Token", "")
        return token == self.api_token or bearer == f"Bearer {self.api_token}"

    def _legacy_news(self, query: dict[str, list[str]]) -> None:
        source = query.get("source", ["all"])[0]
        keyword = query.get("keyword", [""])[0]
        limit = max(1, min(int(query.get("limit", ["100"])[0]), 1000))
        items, _ = self.repository.load_news(source=source, keyword=keyword)
        self._send_json({"count": min(limit, len(items)), "source": source, "keyword": keyword, "data": items[:limit]})

    def _news_page(self, query: dict[str, list[str]], source_default: str) -> None:
        source = query.get("source", [source_default])[0]
        if source != "all" and source not in SOURCES:
            raise ValueError(f"invalid source: {source}")
        keyword = query.get("keyword", [""])[0]
        stock_code = query.get("stock_code", [""])[0]
        date_from = query.get("date_from", [""])[0]
        date_to = query.get("date_to", [""])[0]
        limit = max(1, min(int(query.get("limit", ["200"])[0]), 500))
        offset = _decode_cursor(query.get("cursor", [""])[0])
        include_content = query.get("include_content", ["0"])[0] == "1"
        requested_version = query.get("dataset_version", [""])[0]
        items, version = self.repository.load_news(
            source=source,
            keyword=keyword,
            stock_code=stock_code,
            date_from=date_from,
            date_to=date_to,
        )
        if requested_version and requested_version != version:
            self._send_json({"error": "dataset version changed", "dataset_version": version}, status=409)
            return
        page = items[offset : offset + limit]
        if not include_content:
            page = [
                {
                    key: item.get(key)
                    for key in (
                        "id",
                        "source",
                        "title",
                        "publish_time",
                        "publish_time_bj",
                        "source_time",
                        "crawled_at",
                        "collected_at",
                        "stock_code",
                        "stock_name",
                        "announcement_type",
                        "url",
                        "source_urls",
                    )
                    if item.get(key) not in (None, "")
                }
                for item in page
            ]
        next_offset = offset + len(page)
        self._send_json(
            {
                "dataset_version": version,
                "expected_count": len(items),
                "returned_count": len(page),
                "cursor": _encode_cursor(offset),
                "next_cursor": _encode_cursor(next_offset) if next_offset < len(items) else None,
                "is_complete": next_offset >= len(items),
                "data": page,
            }
        )

    def _news_detail(self, item_id: str, source: str) -> None:
        items, version = self.repository.load_news(source=source, date_from="1900-01-01")
        for item in items:
            if item.get("id") == item_id:
                self._send_json({"dataset_version": version, "data": item})
                return
        raise KeyError(item_id)

    def _market_snapshot_route(self, path: str, query: dict[str, list[str]]) -> None:
        parts = path.split("/")
        if len(parts) < 5:
            raise ValueError("missing snapshot id")
        snapshot_id = parts[4]
        action = parts[5] if len(parts) > 5 else ""
        snapshot, snapshot_path = self.repository.load_snapshot(snapshot_id)
        if action == "stocks":
            rows = snapshot.get("raw", {}).get("stock_spot", [])
            self._paged_rows(rows, snapshot_id, query)
        elif action == "features":
            payload = self.repository.objective_features(snapshot_id)
            self._paged_rows(payload["data"], snapshot_id, query, extra={"history_dates": payload["history_dates"]})
        elif action == "export":
            dataset = query.get("dataset", ["stocks"])[0]
            body, expected_count = self.repository.export_dataset(snapshot_id, dataset)
            self._send_bytes(
                body,
                content_type="application/gzip",
                headers={
                    "X-Snapshot-Id": snapshot_id,
                    "X-Expected-Count": str(expected_count),
                    "X-Checksum-Sha256": _sha256_bytes(body),
                    "ETag": f'"{_sha256_bytes(body)}"',
                },
            )
        elif not action:
            self._send_json(
                {
                    "metadata": snapshot.get("metadata"),
                    "derived": _objective_derived(snapshot.get("derived", {})),
                    "source_status": snapshot.get("source_status"),
                }
            )
        else:
            raise KeyError(action)

    def _paged_rows(
        self,
        rows: list[dict[str, Any]],
        version: str,
        query: dict[str, list[str]],
        extra: dict[str, Any] | None = None,
    ) -> None:
        requested_version = query.get("snapshot_id", [""])[0]
        if requested_version and requested_version != version:
            self._send_json({"error": "snapshot id mismatch", "snapshot_id": version}, status=409)
            return
        limit = max(1, min(int(query.get("limit", ["500"])[0]), 1000))
        offset = _decode_cursor(query.get("cursor", [""])[0])
        page = rows[offset : offset + limit]
        next_offset = offset + len(page)
        payload = {
            "snapshot_id": version,
            "expected_count": len(rows),
            "returned_count": len(page),
            "next_cursor": _encode_cursor(next_offset) if next_offset < len(rows) else None,
            "is_complete": next_offset >= len(rows),
            "data": page,
        }
        if extra:
            payload.update(extra)
        self._send_json(payload)

    def _market_pools(self, query: dict[str, list[str]]) -> None:
        snapshot_id = query.get("snapshot_id", [""])[0]
        if not snapshot_id:
            latest = self.repository.latest_snapshot()
            if not latest:
                raise KeyError("latest snapshot")
            snapshot_id = latest["snapshot_id"]
        snapshot, _ = self.repository.load_snapshot(snapshot_id)
        self._send_json(
            {
                "snapshot_id": snapshot_id,
                "data": snapshot.get("derived", {}).get("pools", {}) or snapshot.get("pools", {}),
            }
        )

    def _stock_route(self, path: str, query: dict[str, list[str]]) -> None:
        parts = path.split("/")
        if len(parts) < 6:
            raise ValueError("missing stock action")
        code = parts[4]
        if not (len(code) == 6 and code.isdigit()):
            raise ValueError("stock code must be a six-digit string")
        action = parts[5]
        if action == "daily":
            days = max(1, min(int(query.get("days", ["30"])[0]), 365))
            date_from = query.get("date_from", [""])[0]
            date_to = query.get("date_to", [""])[0]
            self._send_json(
                {
                    "code": code,
                    "date_from": date_from or None,
                    "date_to": date_to or None,
                    "data": self.repository.stock_daily(
                        code,
                        days=days,
                        date_from=date_from,
                        date_to=date_to,
                    ),
                }
            )
        elif action == "intraday":
            market_date = query.get("market_date", [datetime.now(BEIJING_TZ).date().isoformat()])[0]
            self._send_json({"code": code, "market_date": market_date, "data": self.repository.stock_intraday(code, market_date)})
        else:
            raise KeyError(action)

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send_bytes(
            body,
            "application/json; charset=utf-8",
            status=status,
            headers={"ETag": f'"{_sha256_bytes(body)}"'},
        )

    def _send_bytes(
        self,
        body: bytes,
        content_type: str,
        status: int = 200,
        content_encoding: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        response_headers = dict(headers or {})
        etag = response_headers.get("ETag") or f'"{_sha256_bytes(body)}"'
        response_headers["ETag"] = etag
        response_headers.setdefault("Accept-Ranges", "bytes")
        if self.headers.get("If-None-Match") == etag:
            self.send_response(304)
            self.send_header("ETag", etag)
            self.end_headers()
            return

        range_header = self.headers.get("Range", "")
        if status == 200 and range_header.startswith("bytes=") and range_header.endswith("-"):
            try:
                start = int(range_header[6:-1])
            except ValueError:
                start = -1
            if 0 <= start < len(body):
                response_headers["Content-Range"] = f"bytes {start}-{len(body) - 1}/{len(body)}"
                body = body[start:]
                status = 206
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        if content_encoding:
            self.send_header("Content-Encoding", content_encoding)
        for key, value in response_headers.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)


def create_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    data_dir: str = STORAGE_CONFIG["base_path"],
    retention_days: int = 15,
    market_dir: str = "data_market",
    calendar_cache: str = "data_market/trading_calendar.json",
    collector_state: str = "data/collector_health.json",
    api_token: str = "",
) -> ThreadingHTTPServer:
    repository = DataRepository(data_dir, market_dir, retention_days, calendar_cache, collector_state)

    class Handler(DataAPIHandler):
        pass

    Handler.repository = repository
    Handler.api_token = api_token or os.getenv("DATA_API_TOKEN", "")
    return ThreadingHTTPServer((host, port), Handler)


def main() -> None:
    parser = argparse.ArgumentParser(description="股票分析系统只读数据接口")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", default=STORAGE_CONFIG["base_path"])
    parser.add_argument("--market-dir", default="data_market")
    parser.add_argument("--retention-days", type=int, default=15, help="API 默认新闻查询窗口；原始文件永久保留")
    parser.add_argument("--calendar-cache", default="data_market/trading_calendar.json")
    parser.add_argument("--collector-state", default="data/collector_health.json")
    parser.add_argument("--api-token", default="")
    args = parser.parse_args()
    server = create_server(
        host=args.host,
        port=args.port,
        data_dir=args.data_dir,
        retention_days=args.retention_days,
        market_dir=args.market_dir,
        calendar_cache=args.calendar_cache,
        collector_state=args.collector_state,
        api_token=args.api_token,
    )
    print(f"只读数据接口已启动: http://{args.host}:{args.port}/v1/manifest")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
