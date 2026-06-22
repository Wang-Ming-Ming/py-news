#!/usr/bin/env python3
"""Download, cache, validate, and query objective server data locally."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from client.server_settings import load_server_settings


CST = timezone(timedelta(hours=8))
DEFAULT_CACHE_DIR = Path("data_server_cache")


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_bytes(payload)
    temp_path.replace(path)


def _write_json(path: Path, payload: Any) -> None:
    _atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _item_date(item: dict[str, Any]) -> str:
    for field in ("publish_time_bj", "publish_time", "crawled_at", "collected_at"):
        value = str(item.get(field) or "")
        if len(value) >= 10:
            try:
                return datetime.fromisoformat(value[:10]).date().isoformat()
            except ValueError:
                continue
    return "unknown-date"


def _archive_index_by_date(
    cache_dir: Path,
    payload: dict[str, Any],
    filename: str,
    date_hint: str = "",
) -> list[str]:
    version = str(payload.get("dataset_version") or "unknown")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in payload.get("data") or []:
        grouped.setdefault(_item_date(item), []).append(item)
    if date_hint and date_hint not in grouped:
        grouped[date_hint] = []
    output_dirs: list[str] = []
    for market_date, rows in sorted(grouped.items()):
        target_dir = cache_dir / "archive" / market_date / "news" / version
        dated_payload = {
            "dataset_version": version,
            "market_date": market_date,
            "expected_count": len(rows),
            "actual_count": len(rows),
            "is_complete": True,
            "data": rows,
        }
        target = target_dir / filename
        if not target.exists():
            _write_json(target, dated_payload)
        output_dirs.append(str(target_dir.resolve()))
    return output_dirs


def _parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=CST)
    return parsed.astimezone(CST)


def _item_collected_at(item: dict[str, Any]) -> datetime | None:
    for field in ("collected_at", "crawled_at", "source_time", "publish_time_bj", "publish_time"):
        parsed = _parse_timestamp(item.get(field))
        if parsed is not None:
            return parsed
    return None


def _load_archived_index(
    cache_dir: Path,
    filename: str,
    date_from: str,
    date_to: str,
) -> dict[str, Any]:
    rows: dict[str, dict[str, Any]] = {}
    versions: list[str] = []
    for path in cache_dir.glob(f"archive/*/news/*/{filename}"):
        market_date = path.parts[-4]
        if market_date < date_from or market_date > date_to:
            continue
        payload = _read_json(path, {}) or {}
        version = str(payload.get("dataset_version") or "")
        if version:
            versions.append(version)
        for item in payload.get("data") or []:
            item_id = str(item.get("id") or "")
            if item_id:
                rows[item_id] = item
    return {
        "dataset_version": versions[-1] if versions else "",
        "expected_count": len(rows),
        "actual_count": len(rows),
        "is_complete": True,
        "data": list(rows.values()),
    }


def _merge_index_payloads(
    payloads: list[dict[str, Any]],
    date_from: str,
    date_to: str,
) -> dict[str, Any]:
    rows: dict[str, dict[str, Any]] = {}
    version = ""
    for payload in payloads:
        if not isinstance(payload, dict):
            continue
        version = str(payload.get("dataset_version") or version)
        for item in payload.get("data") or []:
            item_date = _item_date(item)
            if item_date == "unknown-date" or not (date_from <= item_date <= date_to):
                continue
            item_id = str(item.get("id") or "")
            if not item_id:
                item_id = hashlib.sha256(
                    json.dumps(item, ensure_ascii=False, sort_keys=True).encode("utf-8")
                ).hexdigest()[:24]
                item = {**item, "id": item_id}
            rows[item_id] = item
    ordered = sorted(
        rows.values(),
        key=lambda item: _item_collected_at(item) or datetime.min.replace(tzinfo=CST),
        reverse=True,
    )
    return {
        "dataset_version": version,
        "expected_count": len(ordered),
        "actual_count": len(ordered),
        "is_complete": True,
        "data": ordered,
    }


def _sync_incremental_index(
    client: "ServerDataClient",
    cache_dir: Path,
    manifest: dict[str, Any],
    endpoint: str,
    filename: str,
    retention_days: int = 15,
    full_index: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    latest_path = cache_dir / filename
    if full_index:
        payload = client.fetch_all_pages(
            endpoint,
            {"limit": 500},
            checkpoint_path=cache_dir / f".{filename}.pages.json",
        )
        return payload, {
            "strategy": "full",
            "date_from": None,
            "collected_after": None,
            "downloaded_count": payload.get("actual_count", 0),
            "merged_count": payload.get("actual_count", 0),
            "error": None,
        }

    current_date = str(
        manifest.get("generated_at") or datetime.now(CST).isoformat(timespec="seconds")
    )[:10]
    try:
        end_date = datetime.fromisoformat(current_date).date()
    except ValueError:
        end_date = datetime.now(CST).date()
    cutoff_date = end_date - timedelta(days=max(1, retention_days) - 1)
    cutoff = cutoff_date.isoformat()
    end = end_date.isoformat()

    cached = _read_json(latest_path, {}) or {}
    archived = _load_archived_index(cache_dir, filename, cutoff, end)
    base = _merge_index_payloads([cached, archived], cutoff, end)
    newest_collected = max(
        (_item_collected_at(item) for item in base.get("data") or []),
        default=None,
    )
    newest_date = max(
        (_item_date(item) for item in base.get("data") or [] if _item_date(item) != "unknown-date"),
        default=cutoff,
    )

    capabilities = manifest.get("api_capabilities") or {}
    supports_collected_after = bool(capabilities.get("news_collected_after"))
    params: dict[str, Any] = {"limit": 500, "date_to": end}
    collected_after = None
    if supports_collected_after and newest_collected is not None:
        collected_after = (newest_collected - timedelta(minutes=10)).isoformat(timespec="seconds")
        params.update({"date_from": cutoff, "collected_after": collected_after})
        strategy = "collected_after"
    else:
        overlap_start = datetime.fromisoformat(newest_date).date() - timedelta(days=1)
        params["date_from"] = max(cutoff_date, overlap_start).isoformat()
        strategy = "date_overlap"

    try:
        delta = client.fetch_all_pages(
            endpoint,
            params,
            checkpoint_path=cache_dir / f".{filename}.incremental.pages.json",
        )
        merged = _merge_index_payloads([base, delta], cutoff, end)
        metadata = {
            "strategy": strategy,
            "date_from": params.get("date_from"),
            "date_to": end,
            "collected_after": collected_after,
            "downloaded_count": delta.get("actual_count", 0),
            "merged_count": merged.get("actual_count", 0),
            "error": None,
        }
        return merged, metadata
    except Exception as exc:
        if not base.get("data"):
            raise
        return base, {
            "strategy": f"{strategy}_cached_fallback",
            "date_from": params.get("date_from"),
            "date_to": end,
            "collected_after": collected_after,
            "downloaded_count": 0,
            "merged_count": base.get("actual_count", 0),
            "error": str(exc),
        }


class ServerDataClient:
    def __init__(
        self,
        base_url: str,
        token: str = "",
        timeout: int = 30,
        use_system_proxy: bool = False,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.trust_env = use_system_proxy
        retry = Retry(
            total=4,
            connect=4,
            read=4,
            status=4,
            backoff_factor=1.0,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=2, pool_maxsize=2)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"

    def get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = self.session.get(f"{self.base_url}{path}", params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def fetch_all_pages(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        version_field: str = "dataset_version",
        checkpoint_path: Path | None = None,
    ) -> dict[str, Any]:
        query = dict(params or {})
        cursor = ""
        version = ""
        rows: list[dict[str, Any]] = []
        expected = None
        checkpoint_key = hashlib.sha256(
            json.dumps({"path": path, "params": query}, sort_keys=True).encode("utf-8")
        ).hexdigest()
        checkpoint = _read_json(checkpoint_path, {}) if checkpoint_path else {}
        if checkpoint.get("checkpoint_key") == checkpoint_key:
            cursor = str(checkpoint.get("next_cursor") or "")
            version = str(checkpoint.get(version_field) or "")
            rows = list(checkpoint.get("data") or [])
            expected = checkpoint.get("expected_count")
        conflict_restarts = 0
        while True:
            page_params = {**query, "cursor": cursor}
            if version:
                page_params[version_field] = version
            try:
                payload = self.get_json(path, page_params)
            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 409 and conflict_restarts < 2:
                    conflict_restarts += 1
                    cursor = ""
                    version = ""
                    rows = []
                    expected = None
                    if checkpoint_path:
                        checkpoint_path.unlink(missing_ok=True)
                    continue
                raise
            page_version = str(payload.get(version_field) or "")
            if version and page_version != version:
                raise RuntimeError(f"dataset changed during pagination: {version} -> {page_version}")
            version = page_version or version
            page_rows = payload.get("data") or []
            rows.extend(page_rows)
            expected = payload.get("expected_count", expected)
            cursor = payload.get("next_cursor") or ""
            if checkpoint_path and cursor:
                _write_json(
                    checkpoint_path,
                    {
                        "checkpoint_key": checkpoint_key,
                        version_field: version,
                        "expected_count": expected,
                        "next_cursor": cursor,
                        "data": rows,
                    },
                )
            if not cursor:
                break
        if expected is not None and len(rows) != int(expected):
            raise RuntimeError(f"incomplete pagination: expected={expected}, actual={len(rows)}")
        result = {
            version_field: version,
            "expected_count": expected if expected is not None else len(rows),
            "actual_count": len(rows),
            "is_complete": True,
            "data": rows,
        }
        if checkpoint_path:
            checkpoint_path.unlink(missing_ok=True)
        return result

    def download_export(self, snapshot_id: str, dataset: str) -> tuple[bytes, dict[str, str]]:
        response = self.session.get(
            f"{self.base_url}/v1/market/snapshots/{snapshot_id}/export",
            params={"dataset": dataset},
            timeout=max(self.timeout, 120),
        )
        response.raise_for_status()
        payload = response.content
        expected_checksum = response.headers.get("X-Checksum-Sha256")
        if expected_checksum and _sha256(payload) != expected_checksum:
            raise RuntimeError(f"checksum mismatch for {dataset}")
        gzip.decompress(payload)
        return payload, dict(response.headers)

    def download_export_to_file(self, snapshot_id: str, dataset: str, target: Path) -> dict[str, Any]:
        target.parent.mkdir(parents=True, exist_ok=True)
        part_path = target.with_suffix(target.suffix + ".part")
        metadata_path = target.with_suffix(target.suffix + ".meta.json")
        cached_metadata = _read_json(metadata_path, {})
        request_headers: dict[str, str] = {}
        if target.exists() and cached_metadata.get("etag"):
            request_headers["If-None-Match"] = str(cached_metadata["etag"])
        elif part_path.exists() and part_path.stat().st_size > 0:
            request_headers["Range"] = f"bytes={part_path.stat().st_size}-"

        response = self.session.get(
            f"{self.base_url}/v1/market/snapshots/{snapshot_id}/export",
            params={"dataset": dataset},
            headers=request_headers,
            timeout=max(self.timeout, 120),
            stream=True,
        )
        if response.status_code == 304:
            payload = target.read_bytes()
            gzip.decompress(payload)
            return {
                **cached_metadata,
                "path": str(target.resolve()),
                "size_bytes": len(payload),
                "checksum": _sha256(payload),
                "reused": True,
            }
        response.raise_for_status()

        append = response.status_code == 206 and part_path.exists()
        mode = "ab" if append else "wb"
        with part_path.open(mode) as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)

        payload = part_path.read_bytes()
        checksum = _sha256(payload)
        expected_checksum = response.headers.get("X-Checksum-Sha256")
        if expected_checksum and checksum != expected_checksum:
            raise RuntimeError(f"checksum mismatch for {dataset}")
        decompressed = gzip.decompress(payload)
        actual_count = sum(1 for line in decompressed.splitlines() if line.strip())
        expected_count_text = response.headers.get("X-Expected-Count")
        expected_count = int(expected_count_text) if expected_count_text else actual_count
        if actual_count != expected_count:
            raise RuntimeError(
                f"incomplete export for {dataset}: expected={expected_count}, actual={actual_count}"
            )
        part_path.replace(target)
        metadata = {
            "snapshot_id": snapshot_id,
            "dataset": dataset,
            "etag": response.headers.get("ETag"),
            "checksum": checksum,
            "expected_count": expected_count,
            "actual_count": actual_count,
            "size_bytes": len(payload),
            "path": str(target.resolve()),
            "reused": False,
        }
        _write_json(metadata_path, metadata)
        return metadata

    def download_export_with_fallback(self, snapshot_id: str, dataset: str, target: Path) -> dict[str, Any]:
        export_error: Exception | None = None
        for _ in range(2):
            try:
                return self.download_export_to_file(snapshot_id, dataset, target)
            except Exception as exc:
                export_error = exc
        if export_error is None:
            raise RuntimeError("export failed without an error")
        action = "features" if dataset == "features" else "stocks"
        checkpoint = target.with_suffix(target.suffix + ".pages.json")
        paged = self.fetch_all_pages(
            f"/v1/market/snapshots/{snapshot_id}/{action}",
            {"limit": 500},
            version_field="snapshot_id",
            checkpoint_path=checkpoint,
        )
        body = gzip.compress(
            b"".join(
                (json.dumps(row, ensure_ascii=False) + "\n").encode("utf-8")
                for row in paged["data"]
            ),
            mtime=0,
        )
        _atomic_write(target, body)
        metadata = {
            "snapshot_id": snapshot_id,
            "dataset": dataset,
            "checksum": _sha256(body),
            "expected_count": paged["expected_count"],
            "actual_count": paged["actual_count"],
            "size_bytes": len(body),
            "path": str(target.resolve()),
            "fallback": "cursor_pagination",
            "export_error": str(export_error),
        }
        _write_json(target.with_suffix(target.suffix + ".meta.json"), metadata)
        return metadata

    def news_detail(self, item_id: str, announcement: bool = False) -> dict[str, Any]:
        prefix = "/v1/announcements" if announcement else "/v1/news"
        return self.get_json(f"{prefix}/{item_id}")


def _select_snapshot(manifest: dict[str, Any], mode: str) -> dict[str, Any]:
    def recency_key(item: dict[str, Any]) -> tuple[str, str, str]:
        market_date = str(item.get("market_date") or "").replace("-", "")
        source_time = str(item.get("source_time") or "")
        if not market_date and len(source_time) >= 10:
            market_date = source_time[:10].replace("-", "")
        return market_date, source_time, str(item.get("captured_at") or "")

    market = manifest.get("market", {})
    latest = market.get("latest", {})
    if mode == "morning":
        candidates = [latest.get("morning"), latest.get("custom")]
    elif mode == "overnight":
        candidates = [latest.get("overnight"), latest.get("custom")]
    else:
        candidates = list(latest.values())
    valid = [item for item in candidates if isinstance(item, dict) and item.get("snapshot_id")]
    if not valid:
        valid = [
            item
            for item in market.get("snapshots", [])
            if isinstance(item, dict) and item.get("snapshot_id") and item.get("is_complete", True)
        ]
    if not valid:
        raise RuntimeError(f"no valid market snapshot for mode={mode}")
    return max(valid, key=recency_key)


def _archive_recent_snapshot_contexts(
    client: ServerDataClient,
    cache_dir: Path,
    trading_days: int = 15,
) -> list[str]:
    index = client.fetch_all_pages(
        "/v1/market/snapshots",
        {"limit": 200},
        version_field="dataset_version",
        checkpoint_path=cache_dir / ".snapshot_index_pages.json",
    )
    latest_by_date: dict[str, dict[str, Any]] = {}
    for item in index.get("data") or []:
        market_date = str(item.get("market_date") or "")
        if len(market_date) == 8 and market_date.isdigit():
            market_date = f"{market_date[:4]}-{market_date[4:6]}-{market_date[6:8]}"
        if not market_date or not item.get("snapshot_id"):
            continue
        existing = latest_by_date.get(market_date)
        if not existing or str(item.get("captured_at") or "") > str(existing.get("captured_at") or ""):
            latest_by_date[market_date] = item

    paths: list[str] = []
    for market_date in sorted(latest_by_date, reverse=True)[:trading_days]:
        item = latest_by_date[market_date]
        target_dir = cache_dir / "archive" / market_date / "market" / str(item["snapshot_id"])
        context_path = target_dir / "snapshot_context.json"
        if not context_path.exists():
            context = client.get_json(f"/v1/market/snapshots/{item['snapshot_id']}")
            _write_json(context_path, context)
            _write_json(target_dir / "snapshot_metadata.json", item)
        paths.append(str(context_path.resolve()))
    return paths


def sync_data(
    client: ServerDataClient,
    cache_dir: Path,
    mode: str,
    full_index: bool = False,
) -> dict[str, Any]:
    started = time.monotonic()
    health = client.get_json("/v1/health")
    calendar = client.get_json("/v1/calendar")
    manifest = client.get_json("/v1/manifest")
    snapshot = _select_snapshot(manifest, mode)
    snapshot_id = snapshot["snapshot_id"]
    market_date = str(snapshot.get("market_date") or datetime.now(CST).date().isoformat())
    if len(market_date) == 8 and market_date.isdigit():
        market_date = f"{market_date[:4]}-{market_date[4:6]}-{market_date[6:8]}"
    archive_root = cache_dir / "archive" / market_date
    snapshot_dir = archive_root / "market" / snapshot_id
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    _write_json(cache_dir / "latest_health.json", health)
    _write_json(cache_dir / "latest_calendar.json", calendar)
    _write_json(cache_dir / "latest_manifest.json", manifest)

    downloads: dict[str, Any] = {}
    for dataset in ("stocks", "features"):
        target = snapshot_dir / f"{dataset}.ndjson.gz"
        downloads[dataset] = client.download_export_with_fallback(snapshot_id, dataset, target)

    pools = client.get_json("/v1/market/pools", {"snapshot_id": snapshot_id})
    _write_json(snapshot_dir / "pools.json", pools)
    snapshot_context = client.get_json(f"/v1/market/snapshots/{snapshot_id}")
    _write_json(snapshot_dir / "snapshot_context.json", snapshot_context)
    history_snapshot_contexts = _archive_recent_snapshot_contexts(client, cache_dir, trading_days=15)

    manifest_news_version = str(manifest.get("news", {}).get("dataset_version") or "")
    manifest_announcement_version = str(manifest.get("announcements", {}).get("dataset_version") or "")
    news, news_incremental = _sync_incremental_index(
        client,
        cache_dir,
        manifest,
        "/v1/news",
        "latest_news_index.json",
        full_index=full_index,
    )
    announcements, announcement_incremental = _sync_incremental_index(
        client,
        cache_dir,
        manifest,
        "/v1/announcements",
        "latest_announcements_index.json",
        full_index=full_index,
    )
    dataset_version_drift = {
        "news": bool(manifest_news_version and news["dataset_version"] != manifest_news_version),
        "announcements": bool(
            manifest_announcement_version
            and announcements["dataset_version"] != manifest_announcement_version
        ),
    }
    if any(dataset_version_drift.values()):
        manifest = client.get_json("/v1/manifest")
        _write_json(cache_dir / "latest_manifest.json", manifest)
    news_archive_dirs = _archive_index_by_date(cache_dir, news, "news_index.json")
    announcement_archive_dirs = _archive_index_by_date(
        cache_dir,
        announcements,
        "announcements_index.json",
    )
    news_archive_dir = archive_root / "news" / str(news.get("dataset_version") or "unknown")
    _write_json(cache_dir / "latest_news_index.json", news)
    _write_json(cache_dir / "latest_announcements_index.json", announcements)

    summary = {
        "schema_version": "1.0",
        "synced_at": datetime.now(CST).isoformat(timespec="seconds"),
        "mode": mode,
        "server": client.base_url,
        "snapshot": snapshot,
        "archive_date_dir": str(archive_root.resolve()),
        "news_archive_dir": str(news_archive_dir.resolve()),
        "news_archive_dirs": news_archive_dirs,
        "announcement_archive_dirs": announcement_archive_dirs,
        "health_file": str((cache_dir / "latest_health.json").resolve()),
        "calendar_file": str((cache_dir / "latest_calendar.json").resolve()),
        "manifest_file": str((cache_dir / "latest_manifest.json").resolve()),
        "news_index_file": str((cache_dir / "latest_news_index.json").resolve()),
        "announcements_index_file": str((cache_dir / "latest_announcements_index.json").resolve()),
        "pools_file": str((snapshot_dir / "pools.json").resolve()),
        "snapshot_context_file": str((snapshot_dir / "snapshot_context.json").resolve()),
        "history_snapshot_context_files": history_snapshot_contexts,
        "downloads": downloads,
        "news_count": news["actual_count"],
        "announcement_count": announcements["actual_count"],
        "dataset_version_drift": dataset_version_drift,
        "sync_strategy": "full" if full_index else "incremental",
        "news_incremental": news_incremental,
        "announcement_incremental": announcement_incremental,
        "reused_news_index": news_incremental.get("downloaded_count", 0) == 0,
        "reused_announcements_index": announcement_incremental.get("downloaded_count", 0) == 0,
        "using_cached_data": False,
        "sync_error": None,
        "sync_duration_seconds": round(time.monotonic() - started, 2),
    }
    _write_json(cache_dir / "latest_context.json", summary)
    return summary


def sync_with_fallback(
    client: ServerDataClient,
    cache_dir: Path,
    mode: str,
    full_index: bool = False,
) -> dict[str, Any]:
    try:
        return sync_data(client, cache_dir, mode, full_index=full_index)
    except Exception as exc:
        fallback = cache_dir / "latest_context.json"
        if not fallback.exists():
            raise
        payload = _read_json(fallback, {})
        synced_at_text = str(payload.get("synced_at") or "")
        cache_age_minutes = None
        try:
            synced_at = datetime.fromisoformat(synced_at_text)
            if synced_at.tzinfo is None:
                synced_at = synced_at.replace(tzinfo=CST)
            cache_age_minutes = round((datetime.now(CST) - synced_at.astimezone(CST)).total_seconds() / 60, 2)
        except ValueError:
            pass
        payload.update(
            {
                "sync_error": str(exc),
                "using_cached_data": True,
                "cache_age_minutes": cache_age_minutes,
                "cache_context_file": str(fallback.resolve()),
            }
        )
        return payload


def archive_date(client: ServerDataClient, cache_dir: Path, market_date: str) -> dict[str, Any]:
    normalized_date = datetime.strptime(market_date, "%Y-%m-%d").date().isoformat()
    archive_root = cache_dir / "archive" / normalized_date
    snapshots = client.get_json("/v1/market/snapshots", {"market_date": normalized_date}).get("data") or []
    archived_snapshots = []
    for snapshot in snapshots:
        snapshot_id = snapshot["snapshot_id"]
        snapshot_dir = archive_root / "market" / snapshot_id
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        target = snapshot_dir / "stocks.ndjson.gz"
        download = client.download_export_with_fallback(snapshot_id, "stocks", target)
        pools = client.get_json("/v1/market/pools", {"snapshot_id": snapshot_id})
        snapshot_context = client.get_json(f"/v1/market/snapshots/{snapshot_id}")
        _write_json(snapshot_dir / "pools.json", pools)
        _write_json(snapshot_dir / "snapshot_metadata.json", snapshot)
        _write_json(snapshot_dir / "snapshot_context.json", snapshot_context)
        archived_snapshots.append(
            {
                "snapshot_id": snapshot_id,
                "path": str(target.resolve()),
                "size_bytes": download["size_bytes"],
                "checksum": download["checksum"],
                "expected_count": download.get("expected_count"),
            }
        )

    date_params = {"date_from": normalized_date, "date_to": normalized_date}
    news = client.fetch_all_pages(
        "/v1/news",
        {**date_params, "limit": 200},
        checkpoint_path=archive_root / ".news_pages.json",
    )
    announcements = client.fetch_all_pages(
        "/v1/announcements",
        {**date_params, "limit": 100},
        checkpoint_path=archive_root / ".announcement_pages.json",
    )
    news_dirs = _archive_index_by_date(cache_dir, news, "news_index.json", date_hint=normalized_date)
    announcement_dirs = _archive_index_by_date(
        cache_dir,
        announcements,
        "announcements_index.json",
        date_hint=normalized_date,
    )
    result = {
        "market_date": normalized_date,
        "archive_date_dir": str(archive_root.resolve()),
        "snapshot_count": len(archived_snapshots),
        "snapshots": archived_snapshots,
        "news_count": news["actual_count"],
        "announcement_count": announcements["actual_count"],
        "news_archive_dirs": news_dirs,
        "announcement_archive_dirs": announcement_dirs,
        "is_complete": True,
    }
    _write_json(archive_root / "archive_manifest.json", result)
    return result


def _iter_ndjson_gzip(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def query_features(args: argparse.Namespace) -> dict[str, Any]:
    context = _read_json(Path(args.cache_dir) / "latest_context.json", {})
    path = Path(context.get("downloads", {}).get("features", {}).get("path") or "")
    if not path.exists():
        raise RuntimeError("feature cache missing; run sync first")
    rows = []
    for row in _iter_ndjson_gzip(path):
        if args.min_amount is not None and float(row.get("amount") or 0) < args.min_amount:
            continue
        if args.min_pct is not None and float(row.get("pct") or 0) < args.min_pct:
            continue
        if args.max_pct is not None and float(row.get("pct") or 0) > args.max_pct:
            continue
        if args.min_turnover is not None and float(row.get("turnover") or 0) < args.min_turnover:
            continue
        if args.max_range_position is not None:
            value = row.get("range_position_15d")
            if value is None or float(value) > args.max_range_position:
                continue
        rows.append(row)
    rows.sort(key=lambda row: float(row.get(args.sort_by) or 0), reverse=not args.ascending)
    return {"count": min(len(rows), args.limit), "total_matches": len(rows), "data": rows[: args.limit]}


def search_local_news(args: argparse.Namespace) -> dict[str, Any]:
    filename = "latest_announcements_index.json" if args.announcements else "latest_news_index.json"
    payload = _read_json(Path(args.cache_dir) / filename, {})
    rows = []
    keyword = args.keyword.lower()
    for row in payload.get("data") or []:
        if args.source and row.get("source") != args.source:
            continue
        if args.stock_code and str(row.get("stock_code") or "") != args.stock_code:
            continue
        if keyword and keyword not in str(row.get("title") or "").lower():
            continue
        rows.append(row)
    return {"count": min(len(rows), args.limit), "total_matches": len(rows), "data": rows[: args.limit]}


def build_parser() -> argparse.ArgumentParser:
    settings = load_server_settings()
    parser = argparse.ArgumentParser(description="Local client for the objective stock data server.")
    parser.add_argument("--server", default=settings["server"])
    parser.add_argument("--token", default=settings["token"])
    parser.add_argument("--cache-dir", default=str(DEFAULT_CACHE_DIR))
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync = subparsers.add_parser("sync")
    sync.add_argument("--mode", choices=["morning", "overnight", "trend"], required=True)
    sync.add_argument(
        "--full",
        action="store_true",
        help="download the complete retained news/announcement indexes instead of incremental deltas",
    )

    archive = subparsers.add_parser("archive-date")
    archive.add_argument("--date", required=True, help="YYYY-MM-DD")

    feature_query = subparsers.add_parser("query-features")
    feature_query.add_argument("--mode", choices=["morning", "overnight", "trend"], required=True)
    feature_query.add_argument("--min-amount", type=float)
    feature_query.add_argument("--min-pct", type=float)
    feature_query.add_argument("--max-pct", type=float)
    feature_query.add_argument("--min-turnover", type=float)
    feature_query.add_argument("--max-range-position", type=float)
    feature_query.add_argument("--sort-by", default="amount")
    feature_query.add_argument("--ascending", action="store_true")
    feature_query.add_argument("--limit", type=int, default=100)

    news = subparsers.add_parser("search-news")
    news.add_argument("--keyword", default="")
    news.add_argument("--source", default="")
    news.add_argument("--stock-code", default="")
    news.add_argument("--announcements", action="store_true")
    news.add_argument("--limit", type=int, default=100)

    detail = subparsers.add_parser("detail")
    detail.add_argument("item_id")
    detail.add_argument("--announcement", action="store_true")

    stock = subparsers.add_parser("stock")
    stock.add_argument("code")
    stock.add_argument("--days", type=int, default=30)
    stock.add_argument("--date-from", default="")
    stock.add_argument("--date-to", default="")
    stock.add_argument("--market-date", default="")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    cache_dir = Path(args.cache_dir)
    client = ServerDataClient(args.server, args.token)
    try:
        if args.command == "sync":
            result = sync_with_fallback(client, cache_dir, args.mode, full_index=args.full)
        elif args.command == "archive-date":
            result = archive_date(client, cache_dir, args.date)
        elif args.command == "query-features":
            result = query_features(args)
        elif args.command == "search-news":
            result = search_local_news(args)
        elif args.command == "detail":
            result = client.news_detail(args.item_id, announcement=args.announcement)
        elif args.command == "stock":
            result = {
                "daily": client.get_json(
                    f"/v1/market/stocks/{args.code}/daily",
                    {"days": args.days, "date_from": args.date_from, "date_to": args.date_to},
                ),
                "intraday": client.get_json(
                    f"/v1/market/stocks/{args.code}/intraday",
                    {"market_date": args.market_date or datetime.now(CST).date().isoformat()},
                ),
            }
        else:
            parser.error("unknown command")
            return
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2), file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
