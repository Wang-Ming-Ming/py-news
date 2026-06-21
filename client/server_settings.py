"""Secure local connection settings for the objective data server."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_PATH = Path.home() / ".config" / "stock-data-client" / "config.json"


def config_path() -> Path:
    return Path(os.getenv("STOCK_DATA_CONFIG", str(DEFAULT_CONFIG_PATH))).expanduser()


def load_server_settings() -> dict[str, Any]:
    try:
        payload = json.loads(config_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}
    return {
        "server": os.getenv("STOCK_DATA_SERVER") or str(payload.get("server") or "http://127.0.0.1:8765"),
        "token": os.getenv("STOCK_DATA_TOKEN") or str(payload.get("token") or ""),
        "config_path": str(config_path()),
    }
