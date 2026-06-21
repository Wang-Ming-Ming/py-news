#!/usr/bin/env python3
"""Sync the objective server data required by the trend skill."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from client.server_data_client import ServerDataClient, sync_with_fallback
from client.server_settings import load_server_settings


def main() -> None:
    settings = load_server_settings()
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default=settings["server"])
    parser.add_argument("--token", default=settings["token"])
    parser.add_argument("--cache-dir", default="data_server_cache")
    args = parser.parse_args()
    started = time.monotonic()
    result = sync_with_fallback(ServerDataClient(args.server, args.token), Path(args.cache_dir), "trend")
    result["sync_duration_seconds"] = round(time.monotonic() - started, 2)
    result["server"] = args.server
    result["connection_config"] = settings["config_path"]
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
