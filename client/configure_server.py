#!/usr/bin/env python3
"""Write the shared client server settings to the repository .env file."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from client.server_settings import env_path, load_server_settings


def write_env(target: Path, server: str, token: str) -> None:
    target.write_text(
        f'STOCK_DATA_SERVER="{server.rstrip("/")}"\nSTOCK_DATA_TOKEN="{token}"\n',
        encoding="utf-8",
    )


def main() -> None:
    current = load_server_settings()
    parser = argparse.ArgumentParser(description="Configure the objective stock-data server client.")
    parser.add_argument("--server", default=current["server"])
    parser.add_argument("--token", default="", help="API token; prompts when omitted")
    parser.add_argument("--env-file", default=str(env_path()))
    parser.add_argument("--use-existing-token", action="store_true")
    args = parser.parse_args()
    token = args.token.strip()
    if not token and args.use_existing_token:
        token = str(current.get("token") or "").strip()
    if not token:
        token = getpass.getpass("粘贴 DATA_API_TOKEN（输入不会显示）: ").strip()
    if not token:
        raise SystemExit("令牌不能为空")
    target = Path(args.env_file).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    write_env(target, args.server, token)
    os.chmod(target, 0o600)
    print(f"客户端环境配置已保存: {target}")


if __name__ == "__main__":
    main()
