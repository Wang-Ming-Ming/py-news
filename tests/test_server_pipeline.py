import json
import tempfile
import threading
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

from filters.news_normalizer import normalize_news_item
from client.server_data_client import (
    ServerDataClient,
    _archive_index_by_date,
    _merge_index_payloads,
    _select_snapshot,
    _sync_incremental_index,
    sync_with_fallback,
)
from market_data.market_snapshot import is_mode_window_valid
from market_data.market_derivation import derive_snapshot
from market_data.history_bootstrap import (
    HistorySourceRouter,
    build_historical_snapshot,
    completed_trade_dates,
    parse_kline_payload,
    parse_tencent_kline_payload,
)
from market_data.objective_features import build_objective_features
from market_data.trading_calendar import TradingCalendar
from news_api import DataRepository, create_server
from scheduler import _effective_interval, _next_market_run
from utils.collector_state import CollectorStateStore
from utils.exceptions import APIException
from utils.retry import RetryHandler


def make_snapshot(day: str, close: float, amount: float = 100.0):
    market_date = day.replace("-", "")
    return {
        "metadata": {
            "snapshot_id": f"{market_date}-close",
            "mode": "custom",
            "captured_at": f"{day}T15:00:00+08:00",
            "source_time": f"{day}T15:00:00+08:00",
            "market_date": market_date,
        },
        "derived": {"summary": {"stock_count": 2000, "tradeable_stock_count": 1000}},
        "raw": {
            "stock_spot": [
                {
                    "代码": "600000",
                    "名称": "测试股份",
                    "最新价": close,
                    "涨跌幅": 1.0,
                    "成交额": amount,
                    "成交量": amount / 10,
                    "换手率": 2.0,
                    "量比": 1.1,
                    "振幅": 3.0,
                    "今开": close - 0.5,
                    "最高": close + 1,
                    "最低": close - 1,
                    "昨收": close - 0.2,
                }
            ]
        },
    }


class ServerPipelineTest(unittest.TestCase):
    def test_server_client_bypasses_system_proxy_by_default(self):
        client = ServerDataClient("http://127.0.0.1:8765")
        self.assertFalse(client.session.trust_env)

    def test_trend_sync_falls_back_to_latest_historical_snapshot(self):
        older_snapshot = {
            "snapshot_id": "historical-1",
            "mode": "historical",
            "captured_at": "2026-06-21T10:01:00+08:00",
            "source_time": "2026-06-17T15:00:00+08:00",
            "market_date": "20260617",
            "is_complete": True,
        }
        newest_snapshot = {
            "snapshot_id": "historical-2",
            "mode": "historical",
            "captured_at": "2026-06-21T10:00:00+08:00",
            "source_time": "2026-06-18T15:00:00+08:00",
            "market_date": "20260618",
            "is_complete": True,
        }
        selected = _select_snapshot(
            {"market": {"latest": {}, "snapshots": [older_snapshot, newest_snapshot]}},
            "trend",
        )
        self.assertEqual(selected["snapshot_id"], "historical-2")

    def test_morning_sync_can_use_latest_complete_historical_snapshot(self):
        snapshot = {
            "snapshot_id": "historical-1",
            "mode": "historical",
            "source_time": "2026-06-18T15:00:00+08:00",
            "market_date": "20260618",
            "is_complete": True,
        }
        selected = _select_snapshot(
            {"market": {"latest": {}, "snapshots": [snapshot]}},
            "morning",
        )
        self.assertEqual(selected["snapshot_id"], "historical-1")

    def test_history_bootstrap_parses_real_daily_kline_fields(self):
        payload = {
            "data": {
                "code": "600000",
                "name": "浦发银行",
                "klines": ["2026-06-19,10.00,10.20,10.30,9.90,123,456789,4.00,2.00,0.20,1.50"],
            }
        }
        rows = parse_kline_payload(payload, "600000", "浦发银行")
        self.assertEqual(rows[0]["交易日期"], "2026-06-19")
        self.assertEqual(rows[0]["最新价"], 10.2)
        self.assertEqual(rows[0]["昨收"], 10.0)
        self.assertEqual(rows[0]["成交额"], 456789.0)

    def test_history_bootstrap_parses_tencent_daily_kline_fields(self):
        payload = {
            "data": {
                "sh600000": {
                    "qfqday": [
                        ["2026-06-18", "10.00", "10.10", "10.20", "9.90", "123"],
                        ["2026-06-19", "10.10", "10.30", "10.40", "10.00", "456"],
                    ]
                }
            }
        }
        rows = parse_tencent_kline_payload(payload, "600000", "浦发银行")
        self.assertEqual(rows[1]["交易日期"], "2026-06-19")
        self.assertEqual(rows[1]["最新价"], 10.3)
        self.assertEqual(rows[1]["昨收"], 10.1)
        self.assertEqual(rows[1]["历史数据源"], "tencent_qfq_daily_history")

    def test_history_source_router_rejects_unknown_provider(self):
        with self.assertRaises(ValueError):
            HistorySourceRouter("unknown")

    def test_history_bootstrap_selects_completed_trade_days(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "calendar.json"
            cache.write_text(
                json.dumps(
                    {
                        "source": "test",
                        "trade_dates": [
                            "2026-06-17",
                            "2026-06-18",
                            "2026-06-19",
                            "2026-06-22",
                        ],
                    }
                ),
                encoding="utf-8",
            )
            calendar = TradingCalendar(cache, override_path=Path(tmp) / "no-overrides.json")
            before_close = datetime(2026, 6, 22, 14, 30, tzinfo=timezone(timedelta(hours=8)))
            after_close = datetime(2026, 6, 22, 15, 20, tzinfo=timezone(timedelta(hours=8)))
            self.assertEqual(
                completed_trade_dates(calendar, 3, before_close),
                [date(2026, 6, 17), date(2026, 6, 18), date(2026, 6, 19)],
            )
            self.assertEqual(
                completed_trade_dates(calendar, 3, after_close),
                [date(2026, 6, 18), date(2026, 6, 19), date(2026, 6, 22)],
            )

    def test_historical_snapshot_is_objective_and_date_bound(self):
        rows = [
            {
                "代码": f"{600000 + index:06d}",
                "名称": "测试股份",
                "最新价": 10.0,
                "收盘": 10.0,
                "今开": 9.8,
                "最高": 10.2,
                "最低": 9.7,
                "昨收": 9.9,
                "涨跌幅": 1.01,
                "成交量": 100.0,
                "成交额": 1000.0,
            }
            for index in range(1001)
        ]
        snapshot = build_historical_snapshot(
            date(2026, 6, 19),
            rows,
            {},
            datetime(2026, 6, 20, 10, 0, tzinfo=timezone(timedelta(hours=8))),
            20,
        )
        self.assertEqual(snapshot["metadata"]["market_date"], "20260619")
        self.assertEqual(snapshot["metadata"]["mode"], "historical")
        self.assertEqual(snapshot["metadata"]["history_adjustment"], "qfq")
        self.assertEqual(snapshot["derived"]["summary"]["stock_count"], 1001)
        self.assertNotIn("recommended_candidate", json.dumps(snapshot, ensure_ascii=False))

    def test_market_derivation_has_no_candidate_scores(self):
        frames = {
            "stock_spot": {
                "records": [
                    {
                        "代码": "600000",
                        "名称": "测试股份",
                        "最新价": 10,
                        "涨跌幅": 1,
                        "成交额": 100000000,
                    }
                ]
            }
        }
        derived = derive_snapshot(frames)
        self.assertNotIn("active_candidates", derived["rankings"])
        self.assertNotIn("overnight_candidates", derived["rankings"])
        self.assertNotIn("market_score", json.dumps(derived, ensure_ascii=False))

    def test_calendar_skips_holiday_and_weekend(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "calendar.json"
            cache.write_text(
                json.dumps(
                    {
                        "source": "test",
                        "fetched_at": "2026-06-20T10:00:00+08:00",
                        "trade_dates": ["2026-06-18", "2026-06-22", "2026-06-23"],
                    }
                ),
                encoding="utf-8",
            )
            calendar = TradingCalendar(cache)
            self.assertFalse(calendar.is_trade_day(date(2026, 6, 19)))
            self.assertEqual(calendar.next_trade_day("2026-06-18"), date(2026, 6, 22))
            run_at, mode = _next_market_run(
                [("09:15", "morning")],
                now=datetime(2026, 6, 18, 15, 1),
                calendar=calendar,
            )
            self.assertEqual(run_at, datetime(2026, 6, 22, 9, 15))
            self.assertEqual(mode, "morning")

    def test_override_calendar_covers_major_2026_holidays(self):
        with tempfile.TemporaryDirectory() as tmp:
            calendar = TradingCalendar(
                Path(tmp) / "calendar.json",
                allow_weekday_fallback=False,
                override_path=Path(__file__).resolve().parents[1] / "market_calendar_overrides.json",
            )
            self.assertFalse(calendar.is_trade_day("2026-02-16"))
            self.assertFalse(calendar.is_trade_day("2026-06-19"))
            self.assertFalse(calendar.is_trade_day("2026-10-01"))
            self.assertTrue(calendar.is_trade_day("2026-06-18"))

    def test_snapshot_mode_windows(self):
        self.assertTrue(is_mode_window_valid("morning", datetime(2026, 6, 18, 9, 25)))
        self.assertFalse(is_mode_window_valid("morning", datetime(2026, 6, 18, 8, 44)))
        self.assertTrue(is_mode_window_valid("overnight", datetime(2026, 6, 18, 14, 50)))
        self.assertFalse(is_mode_window_valid("overnight", datetime(2026, 6, 18, 23, 8)))

    def test_objective_features_are_math_only(self):
        snapshots = [make_snapshot(f"2026-06-{day:02d}", 10 + day, 100 + day) for day in range(1, 21)]
        payload = build_objective_features(snapshots[-1], snapshots[:-1])
        row = payload["data"][0]
        self.assertEqual(row["history_points"], 20)
        self.assertIsNotNone(row["ma5"])
        self.assertIsNotNone(row["ma20"])
        self.assertIsNotNone(row["return_5d"])
        self.assertIsNotNone(row["return_15d"])
        self.assertIsNotNone(row["atr14"])
        self.assertIsNotNone(row["average_volume_5d"])
        self.assertGreater(row["consecutive_volume_increases"], 0)
        self.assertEqual(len(row["recent_high_series"]), 15)
        self.assertNotIn("is_stabilized", row)
        self.assertNotIn("risk", row)

    def test_objective_features_tolerate_missing_values(self):
        snapshots = [make_snapshot(f"2026-06-{day:02d}", 10 + day) for day in range(1, 5)]
        snapshots[-1]["raw"]["stock_spot"][0]["成交量"] = "-"
        snapshots[-1]["raw"]["stock_spot"][0]["最高"] = None
        payload = build_objective_features(snapshots[-1], snapshots[:-1])
        row = payload["data"][0]
        self.assertEqual(row["volume"], 0)
        self.assertIsNone(row["upper_shadow_ratio"])
        self.assertIsNone(row["ma5"])
        self.assertIsNone(row["atr14"])
        self.assertIsNone(row["average_volume_5d"])

    def test_objective_news_normalizer_removes_analysis(self):
        item = normalize_news_item(
            {
                "source": "cninfo",
                "title": "股东拟减持公告",
                "publish_time": "2026-06-18T09:00:00+08:00",
                "risk_level": "high",
                "news_score": 90,
            },
            "cninfo",
        )
        self.assertNotIn("risk_level", item)
        self.assertNotIn("news_score", item)
        self.assertIn("publish_time_bj", item)

    def test_repository_strips_legacy_analysis_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_dir = root / "news" / "cninfo"
            source_dir.mkdir(parents=True)
            (source_dir / "2026-06-18.json").write_text(
                json.dumps(
                    [
                        {
                            "source": "cninfo",
                            "title": "测试公告",
                            "publish_time": "2026-06-18T09:00:00+08:00",
                            "risk_flags": ["legacy"],
                            "news_score": 99,
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            market = root / "market"
            market.mkdir()
            repository = DataRepository(
                str(root / "news"),
                str(market),
                30,
                str(root / "calendar.json"),
                str(root / "collector.json"),
            )
            rows, _ = repository.load_news("cninfo")
            self.assertEqual(len(rows), 1)
            self.assertNotIn("risk_flags", rows[0])
            self.assertNotIn("news_score", rows[0])

    def test_historical_features_do_not_include_future_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            market = root / "market"
            for day, close in (("2026-06-17", 10.0), ("2026-06-18", 99.0)):
                date_dir = market / day
                date_dir.mkdir(parents=True)
                snapshot = make_snapshot(day, close)
                date_dir.joinpath(f"custom_150000_{day}.json").write_text(
                    json.dumps(snapshot, ensure_ascii=False),
                    encoding="utf-8",
                )
            repository = DataRepository(
                str(root / "data"),
                str(market),
                0,
                str(root / "calendar.json"),
                str(root / "collector.json"),
            )
            payload = repository.objective_features("20260617-close")
            self.assertEqual(payload["history_dates"], ["2026-06-17"])
            self.assertEqual(payload["data"][0]["price"], 10.0)

    def test_collector_state_persists_backoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "collector.json"
            store = CollectorStateStore(path)
            backoff = store.record_failure("cls", "test", base_interval=60)
            self.assertEqual(backoff, 120)
            loaded = CollectorStateStore(path).get_sources()["cls"]
            self.assertEqual(loaded["consecutive_failures"], 1)
            store.record_success("cls")
            self.assertEqual(CollectorStateStore(path).get_sources()["cls"]["consecutive_failures"], 0)

    def test_retry_handler_does_not_repeat_403_or_429(self):
        for status in (403, 429):
            calls = []

            def fail():
                calls.append(status)
                raise APIException("limited", status_code=status, retry_after=60)

            with self.assertRaises(APIException):
                RetryHandler(max_retries=3, delays=[0, 0, 0]).execute_with_retry(fail)
            self.assertEqual(calls, [status])

    def test_weekend_news_intervals_are_reduced(self):
        with tempfile.TemporaryDirectory() as tmp:
            calendar = TradingCalendar(Path(tmp) / "missing.json", allow_weekday_fallback=True)
            saturday = datetime(2026, 6, 20, 10, 0)
            self.assertEqual(_effective_interval("cls", 300, saturday, calendar), 900)
            self.assertEqual(_effective_interval("ndrc", 3600, saturday, calendar), 7200)

    def test_local_news_archive_is_split_by_publish_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = _archive_index_by_date(
                root,
                {
                    "dataset_version": "v1",
                    "data": [
                        {"id": "a", "publish_time_bj": "2026-06-17T10:00:00+08:00"},
                        {"id": "b", "publish_time_bj": "2026-06-18T10:00:00+08:00"},
                    ],
                },
                "news_index.json",
            )
            self.assertEqual(len(paths), 2)
            self.assertTrue((root / "archive" / "2026-06-17" / "news" / "v1" / "news_index.json").exists())
            self.assertTrue((root / "archive" / "2026-06-18" / "news" / "v1" / "news_index.json").exists())

    def test_incremental_index_merges_cache_and_only_requests_missing_window(self):
        class IncrementalClient:
            def __init__(self):
                self.calls = []

            def fetch_all_pages(self, path, params, checkpoint_path=None):
                self.calls.append((path, params, checkpoint_path))
                return {
                    "dataset_version": "v2",
                    "expected_count": 1,
                    "actual_count": 1,
                    "is_complete": True,
                    "data": [
                        {
                            "id": "new",
                            "title": "new item",
                            "publish_time_bj": "2026-06-22T10:05:00+08:00",
                            "collected_at": "2026-06-22T10:06:00+08:00",
                        }
                    ],
                }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("latest_news_index.json").write_text(
                json.dumps(
                    {
                        "dataset_version": "v1",
                        "is_complete": True,
                        "data": [
                            {
                                "id": "old",
                                "title": "old item",
                                "publish_time_bj": "2026-06-22T09:00:00+08:00",
                                "collected_at": "2026-06-22T09:01:00+08:00",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            client = IncrementalClient()
            payload, metadata = _sync_incremental_index(
                client,
                root,
                {
                    "generated_at": "2026-06-22T10:10:00+08:00",
                    "api_capabilities": {"news_collected_after": True},
                },
                "/v1/news",
                "latest_news_index.json",
            )
            self.assertEqual({item["id"] for item in payload["data"]}, {"old", "new"})
            self.assertEqual(metadata["strategy"], "collected_after")
            self.assertEqual(metadata["downloaded_count"], 1)
            self.assertEqual(client.calls[0][1]["collected_after"], "2026-06-22T08:51:00+08:00")

    def test_incremental_index_uses_one_day_overlap_for_older_server(self):
        class LegacyClient:
            def __init__(self):
                self.params = None

            def fetch_all_pages(self, path, params, checkpoint_path=None):
                self.params = params
                return {
                    "dataset_version": "v2",
                    "expected_count": 0,
                    "actual_count": 0,
                    "is_complete": True,
                    "data": [],
                }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("latest_news_index.json").write_text(
                json.dumps(
                    {
                        "dataset_version": "v1",
                        "is_complete": True,
                        "data": [
                            {
                                "id": "old",
                                "publish_time_bj": "2026-06-21T09:00:00+08:00",
                                "collected_at": "2026-06-21T09:01:00+08:00",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            client = LegacyClient()
            _, metadata = _sync_incremental_index(
                client,
                root,
                {"generated_at": "2026-06-22T10:10:00+08:00"},
                "/v1/news",
                "latest_news_index.json",
            )
            self.assertEqual(metadata["strategy"], "date_overlap")
            self.assertEqual(client.params["date_from"], "2026-06-20")

    def test_merge_index_payloads_deduplicates_and_prunes_old_dates(self):
        payload = _merge_index_payloads(
            [
                {
                    "dataset_version": "v1",
                    "data": [
                        {"id": "old", "publish_time_bj": "2026-06-01T10:00:00+08:00"},
                        {"id": "same", "publish_time_bj": "2026-06-21T10:00:00+08:00"},
                    ],
                },
                {
                    "dataset_version": "v2",
                    "data": [
                        {
                            "id": "same",
                            "title": "updated",
                            "publish_time_bj": "2026-06-21T10:00:00+08:00",
                        }
                    ],
                },
            ],
            "2026-06-08",
            "2026-06-22",
        )
        self.assertEqual(payload["dataset_version"], "v2")
        self.assertEqual(payload["actual_count"], 1)
        self.assertEqual(payload["data"][0]["title"], "updated")

    def test_skill_sync_reports_cache_age_on_server_failure(self):
        class BrokenClient:
            def get_json(self, *args, **kwargs):
                raise RuntimeError("offline")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.joinpath("latest_context.json").write_text(
                json.dumps({"synced_at": "2026-06-20T10:00:00+08:00", "mode": "morning"}),
                encoding="utf-8",
            )
            payload = sync_with_fallback(BrokenClient(), root, "morning")
            self.assertTrue(payload["using_cached_data"])
            self.assertIn("cache_age_minutes", payload)

    def test_api_auth_etag_range_and_fixed_pagination(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            news_dir = root / "data" / "cls"
            news_dir.mkdir(parents=True)
            news_dir.joinpath("2026-06-18.json").write_text(
                json.dumps(
                    [
                        {
                            "source": "cls",
                            "title": "A",
                            "publish_time": "2026-06-18T09:00:00+08:00",
                            "crawled_at": "2026-06-18T09:05:00+08:00",
                        },
                        {
                            "source": "cls",
                            "title": "B",
                            "publish_time": "2026-06-18T10:00:00+08:00",
                            "crawled_at": "2026-06-18T10:05:00+08:00",
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            market_dir = root / "market" / "2026-06-18"
            market_dir.mkdir(parents=True)
            root.joinpath("market", "bootstrap_status.json").write_text(
                json.dumps(
                    {
                        "status": "complete",
                        "is_ready": True,
                        "completed_dates": ["2026-06-17", "2026-06-18"],
                    }
                ),
                encoding="utf-8",
            )
            snapshot = make_snapshot("2026-06-18", 12.0)
            snapshot["metadata"]["snapshot_id"] = "test-snapshot"
            snapshot["source_status"] = {
                "stock_spot": {"ok": True, "rows": 1},
                "concept_boards": {"ok": False, "rows": 0, "error": "test"},
            }
            market_dir.joinpath("custom_150000_test-snapshot.json").write_text(
                json.dumps(snapshot, ensure_ascii=False),
                encoding="utf-8",
            )
            server = create_server(
                host="127.0.0.1",
                port=0,
                data_dir=str(root / "data"),
                retention_days=0,
                market_dir=str(root / "market"),
                calendar_cache=str(root / "calendar.json"),
                collector_state=str(root / "collector.json"),
                api_token="secret",
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_address[1]}"
            headers = {"Authorization": "Bearer secret"}
            try:
                self.assertEqual(requests.get(f"{base}/news", timeout=5).status_code, 401)
                health = requests.get(f"{base}/v1/health", headers=headers, timeout=5).json()
                self.assertEqual(health["market_status"]["missing_interfaces"], ["concept_boards"])
                self.assertTrue(health["history_bootstrap"]["is_ready"])
                manifest_response = requests.get(f"{base}/v1/manifest", headers=headers, timeout=5)
                manifest_etag = manifest_response.headers["ETag"]
                self.assertEqual(
                    requests.get(
                        f"{base}/v1/manifest",
                        headers={**headers, "If-None-Match": manifest_etag},
                        timeout=5,
                    ).status_code,
                    304,
                )
                first = requests.get(f"{base}/v1/news", params={"limit": 1}, headers=headers, timeout=5)
                self.assertEqual(first.status_code, 200)
                first_payload = first.json()
                self.assertIsNotNone(first_payload["next_cursor"])
                second = requests.get(
                    f"{base}/v1/news",
                    params={
                        "limit": 1,
                        "cursor": first_payload["next_cursor"],
                        "dataset_version": first_payload["dataset_version"],
                    },
                    headers=headers,
                    timeout=5,
                )
                self.assertEqual(second.status_code, 200)
                self.assertIsNone(second.json()["next_cursor"])
                incremental = requests.get(
                    f"{base}/v1/news",
                    params={
                        "limit": 10,
                        "date_from": "2026-06-18",
                        "date_to": "2026-06-18",
                        "collected_after": "2026-06-18T09:30:00+08:00",
                    },
                    headers=headers,
                    timeout=5,
                )
                self.assertEqual(incremental.status_code, 200)
                self.assertEqual([item["title"] for item in incremental.json()["data"]], ["B"])

                export = requests.get(
                    f"{base}/v1/market/snapshots/test-snapshot/export",
                    params={"dataset": "stocks"},
                    headers=headers,
                    timeout=5,
                )
                self.assertEqual(export.status_code, 200)
                etag = export.headers["ETag"]
                unchanged = requests.get(
                    f"{base}/v1/market/snapshots/test-snapshot/export",
                    params={"dataset": "stocks"},
                    headers={**headers, "If-None-Match": etag},
                    timeout=5,
                )
                self.assertEqual(unchanged.status_code, 304)
                resumed = requests.get(
                    f"{base}/v1/market/snapshots/test-snapshot/export",
                    params={"dataset": "stocks"},
                    headers={**headers, "Range": "bytes=10-"},
                    timeout=5,
                )
                self.assertEqual(resumed.status_code, 206)
                self.assertTrue(resumed.headers["Content-Range"].startswith("bytes 10-"))
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=5)


if __name__ == "__main__":
    unittest.main()
