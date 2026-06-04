# -*- coding: utf-8 -*-
"""
轻量新闻源接口。

用于给股票分析系统提供已采集的原始新闻/公告 JSON 数据。
不引入额外 Web 框架，直接使用 Python 标准库 HTTP 服务。
"""

import argparse
import json
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import parse_qs, urlparse

from config import STORAGE_CONFIG


SOURCES = {"cls", "cninfo", "ndrc", "eastmoney_global"}


def _parse_time(value: Any) -> datetime:
    if not value:
        return datetime.min
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return datetime.min


def _repair_mojibake(value: str) -> str:
    if not isinstance(value, str):
        return value
    if "ä" not in value and "ã" not in value and "Â" not in value:
        return value
    try:
        repaired = value.encode("latin1").decode("utf-8")
        return repaired if repaired else value
    except UnicodeError:
        return value


def _normalize_item(item: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(item)
    for field in ("title", "content", "summary"):
        if field in normalized:
            normalized[field] = _repair_mojibake(normalized[field])
    return normalized


def load_news(
    base_path: str,
    source: str = "all",
    limit: int = 100,
    keyword: str = "",
    retention_days: int = 7,
) -> List[Dict[str, Any]]:
    base = Path(base_path)
    selected_sources = SOURCES if source == "all" else {source}
    items: List[Dict[str, Any]] = []
    cutoff = datetime.now() - timedelta(days=retention_days) if retention_days > 0 else datetime.min

    for source_name in selected_sources:
        source_dir = base / source_name
        if not source_dir.exists():
            continue

        for file_path in sorted(source_dir.glob("*.json"), reverse=True):
            try:
                file_date = datetime.strptime(file_path.stem, "%Y-%m-%d")
            except ValueError:
                continue
            if file_date < cutoff.replace(hour=0, minute=0, second=0, microsecond=0):
                continue

            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue

            if not isinstance(data, list):
                continue

            for item in data:
                if not isinstance(item, dict):
                    continue
                normalized = _normalize_item(item)
                text = f"{normalized.get('title', '')} {normalized.get('content', '')}"
                if keyword and keyword not in text:
                    continue
                items.append(normalized)

    items.sort(key=lambda item: _parse_time(item.get("publish_time")), reverse=True)
    return items[:limit]


class NewsAPIHandler(BaseHTTPRequestHandler):
    base_path = STORAGE_CONFIG["base_path"]
    retention_days = STORAGE_CONFIG.get("retention_days", 7)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send_json({"status": "ok", "sources": sorted(SOURCES)})
            return

        if parsed.path != "/news":
            self._send_json({"error": "not found"}, status=404)
            return

        query = parse_qs(parsed.query)
        source = query.get("source", ["all"])[0]
        keyword = query.get("keyword", [""])[0]

        if source != "all" and source not in SOURCES:
            self._send_json({"error": f"invalid source: {source}"}, status=400)
            return

        try:
            limit = int(query.get("limit", ["100"])[0])
        except ValueError:
            limit = 100
        limit = max(1, min(limit, 1000))

        items = load_news(
            self.base_path,
            source=source,
            limit=limit,
            keyword=keyword,
            retention_days=self.retention_days,
        )
        self._send_json({
            "count": len(items),
            "source": source,
            "keyword": keyword,
            "retention_days": self.retention_days,
            "data": items,
        })

    def log_message(self, format, *args):
        return

    def _send_json(self, payload: Dict[str, Any], status: int = 200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    data_dir: str = STORAGE_CONFIG["base_path"],
    retention_days: int = STORAGE_CONFIG.get("retention_days", 7),
) -> ThreadingHTTPServer:
    NewsAPIHandler.base_path = data_dir
    NewsAPIHandler.retention_days = retention_days
    return ThreadingHTTPServer((host, port), NewsAPIHandler)


def main():
    parser = argparse.ArgumentParser(description="股票分析系统新闻源接口")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", default=STORAGE_CONFIG["base_path"])
    parser.add_argument("--retention-days", type=int, default=STORAGE_CONFIG.get("retention_days", 7))
    args = parser.parse_args()

    server = create_server(
        host=args.host,
        port=args.port,
        data_dir=args.data_dir,
        retention_days=args.retention_days,
    )
    print(f"新闻源接口已启动: http://{args.host}:{args.port}/news")
    server.serve_forever()


if __name__ == "__main__":
    main()
