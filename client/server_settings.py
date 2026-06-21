"""Connection settings shared by every local stock-data client and skill."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_PATH = Path.home() / ".config" / "stock-data-client" / "config.json"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENV_PATH = PROJECT_ROOT / ".env"


def config_path() -> Path:
    return Path(os.getenv("STOCK_DATA_CONFIG", str(DEFAULT_CONFIG_PATH))).expanduser()


def env_path() -> Path:
    return Path(os.getenv("STOCK_DATA_ENV_FILE", str(DEFAULT_ENV_PATH))).expanduser()


def load_env_file(path: Path | None = None) -> dict[str, str]:
    target = path or env_path()
    try:
        lines = target.read_text(encoding="utf-8").splitlines()
    except OSError:
        return {}

    values: dict[str, str] = {}
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def load_server_settings() -> dict[str, Any]:
    file_values = load_env_file()
    try:
        payload = json.loads(config_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        payload = {}

    process_server = os.getenv("STOCK_DATA_SERVER")
    process_token = os.getenv("STOCK_DATA_TOKEN")
    file_server = file_values.get("STOCK_DATA_SERVER")
    file_token = file_values.get("STOCK_DATA_TOKEN")
    json_server = str(payload.get("server") or "")
    json_token = str(payload.get("token") or "")

    if process_server or process_token:
        source = "process_environment"
    elif file_server or file_token:
        source = "project_env_file"
    elif json_server or json_token:
        source = "legacy_user_json"
    else:
        source = "default"

    return {
        "server": (process_server or file_server or json_server or "http://127.0.0.1:8765").rstrip("/"),
        "token": process_token or file_token or json_token,
        "source": source,
        "env_path": str(env_path()),
        "config_path": str(config_path()),
    }
