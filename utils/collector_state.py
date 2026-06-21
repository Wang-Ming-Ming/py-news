"""Persistent objective runtime state for source schedulers."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


CST = timezone(timedelta(hours=8))


class CollectorStateStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.payload: dict[str, Any] = {"schema_version": "1.0", "updated_at": None, "sources": {}}
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self.payload.update(data)
                self.payload.setdefault("sources", {})
        except (OSError, json.JSONDecodeError):
            return

    def _save(self) -> None:
        self.payload["updated_at"] = datetime.now(CST).isoformat(timespec="seconds")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        temp_path.write_text(json.dumps(self.payload, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(self.path)

    def _source(self, source: str) -> dict[str, Any]:
        return self.payload["sources"].setdefault(
            source,
            {
                "consecutive_failures": 0,
                "last_attempt_at": None,
                "last_success_at": None,
                "last_failure_at": None,
                "last_error": None,
                "paused_until": None,
            },
        )

    def record_success(self, source: str) -> None:
        now = datetime.now(CST).isoformat(timespec="seconds")
        item = self._source(source)
        item.update(
            {
                "consecutive_failures": 0,
                "last_attempt_at": now,
                "last_success_at": now,
                "last_error": None,
                "paused_until": None,
            }
        )
        self._save()

    def record_failure(self, source: str, error: str, base_interval: int, max_backoff: int = 3600) -> int:
        now = datetime.now(CST)
        item = self._source(source)
        failures = int(item.get("consecutive_failures") or 0) + 1
        backoff = min(max_backoff, max(base_interval, base_interval * (2 ** min(failures, 6))))
        item.update(
            {
                "consecutive_failures": failures,
                "last_attempt_at": now.isoformat(timespec="seconds"),
                "last_failure_at": now.isoformat(timespec="seconds"),
                "last_error": str(error)[:1000],
                "paused_until": (now + timedelta(seconds=backoff)).isoformat(timespec="seconds"),
            }
        )
        self._save()
        return backoff

    def get_sources(self) -> dict[str, Any]:
        return dict(self.payload.get("sources") or {})
