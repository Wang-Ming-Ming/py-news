#!/usr/bin/env python3
"""Store the server URL and token outside the repository with private permissions."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from client.server_settings import config_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Configure the objective stock-data server client.")
    parser.add_argument("--server", required=True)
    parser.add_argument("--token", default="", help="API token; prompts when omitted")
    args = parser.parse_args()
    token = args.token.strip() or getpass.getpass("粘贴 DATA_API_TOKEN（输入不会显示）: ").strip()
    if not token:
        raise SystemExit("令牌不能为空")
    target = config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({"server": args.server.rstrip("/"), "token": token}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.chmod(target, 0o600)
    print(f"客户端连接配置已保存: {target}")


if __name__ == "__main__":
    main()
