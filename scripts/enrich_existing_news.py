#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""回填已有新闻 JSON 的北京时间、风险标记和影响力评分字段。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from filters.news_enricher import enrich_news_item  # noqa: E402


def enrich_file(path: Path, dry_run: bool = False) -> tuple[int, int]:
    source = path.parent.name
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0, 0

    if not isinstance(raw, list):
        return 0, 0

    enriched_rows: List[Dict[str, Any]] = []
    changed = 0
    for row in raw:
        if not isinstance(row, dict):
            enriched_rows.append(row)
            continue
        enriched = enrich_news_item(row, source)
        if enriched != row:
            changed += 1
        enriched_rows.append(enriched)

    if changed and not dry_run:
        path.write_text(
            json.dumps(enriched_rows, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return len(raw), changed


def main() -> None:
    parser = argparse.ArgumentParser(description="回填新闻增强字段")
    parser.add_argument("--data-dir", default="data_dev", help="新闻数据目录，例如 data_dev 或 data")
    parser.add_argument("--dry-run", action="store_true", help="只统计，不写入文件")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.is_absolute():
        data_dir = PROJECT_ROOT / data_dir

    total_rows = 0
    total_changed = 0
    file_count = 0

    for path in sorted(data_dir.glob("*/*.json")):
        if path.name.startswith("."):
            continue
        rows, changed = enrich_file(path, dry_run=args.dry_run)
        if rows:
            file_count += 1
            total_rows += rows
            total_changed += changed
            print(f"{path}: rows={rows}, changed={changed}")

    mode = "dry_run" if args.dry_run else "written"
    print(
        f"done: mode={mode}, files={file_count}, "
        f"rows={total_rows}, changed={total_changed}"
    )


if __name__ == "__main__":
    main()
