#!/usr/bin/env python3
"""Backfill real end-of-day A-share data before incremental snapshots begin."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import random
import sys
import time
from datetime import date, datetime, time as datetime_time, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from market_data.akshare_client import (
    _eastmoney_get_json,
    dataframe_to_records,
    load_stock_spot_df,
)
from market_data.market_derivation import derive_snapshot
from market_data.market_filters import get_code, get_name
from market_data.trading_calendar import TradingCalendar
from utils.request_pacer import RequestPacer


CST = timezone(timedelta(hours=8))
EASTMONEY_KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
TENCENT_KLINE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
POOL_FETCHERS = {
    "limit_up_pool": "stock_zt_pool_em",
    "previous_limit_up_pool": "stock_zt_pool_previous_em",
    "strong_pool": "stock_zt_pool_strong_em",
    "broken_limit_pool": "stock_zt_pool_zbgc_em",
    "dtgc_pool": "stock_zt_pool_dtgc_em",
}


def now_cst() -> datetime:
    return datetime.now(CST)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def _number(value: Any) -> float | None:
    if value in (None, "", "-"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _market_prefix(code: str) -> str:
    return "1" if code.startswith(("5", "6", "9")) else "0"


def parse_kline_payload(payload: dict[str, Any], fallback_code: str, fallback_name: str) -> list[dict[str, Any]]:
    data = payload.get("data") or {}
    code = str(data.get("code") or fallback_code).zfill(6)
    name = str(data.get("name") or fallback_name)
    rows: list[dict[str, Any]] = []
    for raw in data.get("klines") or []:
        fields = str(raw).split(",")
        if len(fields) < 11:
            continue
        trade_date, open_text, close_text, high_text, low_text = fields[:5]
        volume_text, amount_text, amplitude_text, pct_text, change_text, turnover_text = fields[5:11]
        close = _number(close_text)
        change = _number(change_text)
        pct = _number(pct_text)
        previous_close = None
        if close is not None and change is not None:
            previous_close = close - change
        elif close is not None and pct is not None and pct != -100:
            previous_close = close / (1 + pct / 100)
        rows.append(
            {
                "交易日期": trade_date,
                "代码": code,
                "名称": name,
                "今开": _number(open_text),
                "开盘": _number(open_text),
                "最新价": close,
                "收盘": close,
                "最高": _number(high_text),
                "最低": _number(low_text),
                "成交量": _number(volume_text),
                "成交额": _number(amount_text),
                "振幅": _number(amplitude_text),
                "涨跌幅": pct,
                "涨跌额": change,
                "换手率": _number(turnover_text),
                "昨收": round(previous_close, 4) if previous_close is not None else None,
            }
        )
    return rows


def _tencent_symbol(code: str) -> str:
    if code.startswith(("4", "8")):
        return f"bj{code}"
    return f"sh{code}" if code.startswith(("5", "6", "9")) else f"sz{code}"


def parse_tencent_kline_payload(
    payload: dict[str, Any],
    fallback_code: str,
    fallback_name: str,
) -> list[dict[str, Any]]:
    symbol = _tencent_symbol(fallback_code)
    data = (payload.get("data") or {}).get(symbol) or {}
    raw_rows = data.get("qfqday") or data.get("day") or []
    parsed: list[dict[str, Any]] = []
    previous_close: float | None = None
    for raw in raw_rows:
        fields = list(raw) if isinstance(raw, (list, tuple)) else str(raw).split(",")
        if len(fields) < 6:
            continue
        trade_date, open_text, close_text, high_text, low_text, volume_text = fields[:6]
        close = _number(close_text)
        change = close - previous_close if close is not None and previous_close is not None else None
        pct = change / previous_close * 100 if change is not None and previous_close else None
        parsed.append(
            {
                "交易日期": str(trade_date),
                "代码": fallback_code,
                "名称": fallback_name,
                "今开": _number(open_text),
                "开盘": _number(open_text),
                "最新价": close,
                "收盘": close,
                "最高": _number(high_text),
                "最低": _number(low_text),
                "成交量": _number(volume_text),
                "成交额": _number(fields[6]) if len(fields) > 6 else None,
                "振幅": None,
                "涨跌幅": round(pct, 4) if pct is not None else None,
                "涨跌额": round(change, 4) if change is not None else None,
                "换手率": None,
                "昨收": previous_close,
                "历史数据源": "tencent_qfq_daily_history",
            }
        )
        if close is not None:
            previous_close = close
    return parsed


def completed_trade_dates(
    calendar: TradingCalendar,
    trading_days: int,
    current: datetime | None = None,
) -> list[date]:
    now = (current or now_cst()).astimezone(CST)
    include_today = calendar.is_trade_day(now.date()) and now.time() >= datetime_time(15, 10)
    cursor = calendar.previous_trade_day(now.date(), include_current=include_today)
    selected: list[date] = []
    while cursor is not None and len(selected) < trading_days:
        selected.append(cursor)
        cursor = calendar.previous_trade_day(cursor)
    return list(reversed(selected))


def _snapshot_is_complete(path: Path, minimum_stocks: int) -> bool:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        metadata = payload.get("metadata", {})
        count = int(payload.get("derived", {}).get("summary", {}).get("stock_count") or 0)
        source_time = str(metadata.get("source_time") or metadata.get("captured_at") or "")
        try:
            source_clock = datetime.fromisoformat(source_time).astimezone(CST).time()
        except ValueError:
            source_clock = datetime_time.min
        is_close_data = metadata.get("mode") == "historical" or source_clock >= datetime_time(14, 55)
        return count >= minimum_stocks and bool(metadata.get("window_valid", True)) and is_close_data
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False


def existing_complete_dates(output_dir: Path, minimum_stocks: int) -> set[str]:
    complete: set[str] = set()
    if not output_dir.exists():
        return complete
    for date_dir in output_dir.glob("20??-??-??"):
        if any(
            _snapshot_is_complete(path, minimum_stocks)
            for path in date_dir.glob("*_snapshot.json")
            if "failed" not in path.name
        ):
            complete.add(date_dir.name)
    return complete


def _load_cached_rows(path: Path, target_dates: set[str]) -> list[dict[str, Any]] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload.get("rows") or []
        requested_begin = min(target_dates).replace("-", "")
        requested_end = max(target_dates).replace("-", "")
        cached_begin = str(payload.get("begin") or "")
        cached_end = str(payload.get("end") or "")
        if cached_begin <= requested_begin and cached_end >= requested_end:
            return rows
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return None


def fetch_stock_history(
    code: str,
    name: str,
    begin: str,
    end: str,
    pacer: RequestPacer,
    retries: int = 3,
    fetch_json: Callable[[str, dict[str, Any]], dict[str, Any]] = _eastmoney_get_json,
) -> list[dict[str, Any]]:
    params = {
        "secid": f"{_market_prefix(code)}.{code}",
        "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        "fields1": "f1,f2,f3,f4,f5,f6",
        "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        "klt": "101",
        "fqt": "1",
        "beg": begin,
        "end": end,
        "lmt": "100",
    }
    last_error: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            pacer.wait()
            payload = fetch_json(EASTMONEY_KLINE_URL, params)
            rows = parse_kline_payload(payload, code, name)
            if not rows:
                raise RuntimeError("history endpoint returned no rows")
            return rows
        except Exception as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(min(20.0, (2 ** attempt) + random.uniform(0.1, 0.8)))
    raise RuntimeError(f"history fetch failed for {code}: {last_error}")


def fetch_tencent_stock_history(
    code: str,
    name: str,
    begin: str,
    end: str,
    pacer: RequestPacer,
    retries: int = 3,
    fetch_json: Callable[[str, dict[str, Any]], dict[str, Any]] = _eastmoney_get_json,
) -> list[dict[str, Any]]:
    symbol = _tencent_symbol(code)
    begin_date = datetime.strptime(begin, "%Y%m%d").date() - timedelta(days=10)
    end_date = datetime.strptime(end, "%Y%m%d").date()
    params = {
        "param": (
            f"{symbol},day,{begin_date.isoformat()},{end_date.isoformat()},100,qfq"
        )
    }
    last_error: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            pacer.wait()
            payload = fetch_json(TENCENT_KLINE_URL, params)
            rows = parse_tencent_kline_payload(payload, code, name)
            if not rows:
                raise RuntimeError("Tencent history endpoint returned no rows")
            return rows
        except Exception as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(min(20.0, (2 ** attempt) + random.uniform(0.1, 0.8)))
    raise RuntimeError(f"Tencent history fetch failed for {code}: {last_error}")


class HistorySourceRouter:
    """Keep using the first working objective source and fail over when it breaks."""

    def __init__(self, provider: str = "auto") -> None:
        if provider not in {"auto", "eastmoney", "tencent"}:
            raise ValueError(f"Unsupported history provider: {provider}")
        self.configured_provider = provider
        self.preferred_provider: str | None = None if provider == "auto" else provider

    def fetch(
        self,
        code: str,
        name: str,
        begin: str,
        end: str,
        pacer: RequestPacer,
        retries: int,
    ) -> tuple[list[dict[str, Any]], str]:
        providers = [self.preferred_provider] if self.preferred_provider else []
        if self.configured_provider == "auto":
            providers.extend(item for item in ("eastmoney", "tencent") if item not in providers)
        errors: list[str] = []
        for provider in providers:
            try:
                if provider == "tencent":
                    rows = fetch_tencent_stock_history(code, name, begin, end, pacer, retries)
                else:
                    rows = fetch_stock_history(code, name, begin, end, pacer, retries)
                    for row in rows:
                        row["历史数据源"] = "eastmoney_qfq_daily_history"
                self.preferred_provider = provider
                return rows, provider
            except Exception as exc:
                errors.append(f"{provider}: {exc}")
        raise RuntimeError("; ".join(errors))


def _fetch_pool_frame(name: str, function_name: str, market_date: str, pacer: RequestPacer) -> dict[str, Any]:
    started = time.time()
    try:
        import akshare as ak

        pacer.wait()
        frame = getattr(ak, function_name)(date=market_date)
        rows = dataframe_to_records(frame)
        return {
            "ok": True,
            "name": function_name,
            "rows": len(rows),
            "columns": [str(column) for column in frame.columns],
            "duration_sec": round(time.time() - started, 3),
            "records": rows,
        }
    except Exception as exc:
        return {
            "ok": False,
            "name": name,
            "rows": 0,
            "columns": [],
            "duration_sec": round(time.time() - started, 3),
            "error": f"{type(exc).__name__}: {exc}",
            "records": [],
        }


def build_historical_snapshot(
    market_day: date,
    stock_rows: list[dict[str, Any]],
    pool_frames: dict[str, dict[str, Any]],
    captured_at: datetime,
    requested_days: int,
) -> dict[str, Any]:
    history_sources = sorted(
        {
            str(row.get("历史数据源"))
            for row in stock_rows
            if row.get("历史数据源")
        }
    )
    source_name = "+".join(history_sources) or "objective_qfq_daily_history"
    frames: dict[str, dict[str, Any]] = {
        "stock_spot": {
            "ok": len(stock_rows) >= 1000,
            "name": source_name,
            "rows": len(stock_rows),
            "columns": sorted({key for row in stock_rows for key in row}),
            "duration_sec": 0.0,
            "records": stock_rows,
        },
        **pool_frames,
    }
    derived = derive_snapshot(frames)
    market_date = market_day.strftime("%Y%m%d")
    identity = hashlib.sha256(
        f"{source_name}|{market_date}|{len(stock_rows)}".encode("utf-8")
    ).hexdigest()[:16]
    source_time = datetime.combine(market_day, datetime_time(15, 0), tzinfo=CST)
    return {
        "metadata": {
            "source": source_name,
            "schema_version": "2.0",
            "snapshot_id": f"{market_date}_historical_{identity}",
            "dataset_version": f"{market_date}_historical_{identity}",
            "mode": "historical",
            "captured_at": captured_at.isoformat(timespec="seconds"),
            "source_time": source_time.isoformat(timespec="seconds"),
            "market_date": market_date,
            "window_valid": True,
            "is_bootstrap_history": True,
            "history_adjustment": "qfq",
            "requested_trading_days": requested_days,
            "units": {
                "price": "CNY_per_share_qfq",
                "pct": "percent",
                "amount": "CNY",
                "volume": "upstream_native_unit",
            },
            "limitations": [
                "Historical company names use the current stock universe response.",
                "Historical industry/concept boards and fund-flow rankings are not synthesized.",
                "Some fallback history sources do not provide historical amount or turnover fields; missing values remain null.",
            ],
        },
        "source_status": {
            key: {
                "ok": value.get("ok"),
                "rows": value.get("rows"),
                "duration_sec": value.get("duration_sec"),
                "error": value.get("error"),
                "columns": value.get("columns"),
            }
            for key, value in frames.items()
        },
        "derived": derived,
        "raw": {key: value.get("records", []) for key, value in frames.items()},
        "errors": {
            key: value.get("error")
            for key, value in frames.items()
            if not value.get("ok")
        },
    }


def run_bootstrap(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = Path(args.output_dir)
    work_dir = output_dir / ".history_bootstrap"
    cache_dir = work_dir / "stocks"
    status_path = output_dir / "bootstrap_status.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    calendar = TradingCalendar(args.calendar_cache)
    if not calendar.ensure(refresh_if_missing=True):
        raise RuntimeError(f"交易日历不可用: {calendar.error}")
    target_days = completed_trade_dates(calendar, args.trading_days)
    if len(target_days) < args.minimum_days:
        raise RuntimeError(f"只能确认 {len(target_days)} 个交易日，少于最低要求 {args.minimum_days}")
    target_dates = {day.isoformat() for day in target_days}
    complete_before = existing_complete_dates(output_dir, args.minimum_stocks)
    missing_dates = target_dates - complete_before
    started_at = now_cst()
    status: dict[str, Any] = {
        "schema_version": "1.0",
        "status": "running" if missing_dates else "complete",
        "started_at": started_at.isoformat(timespec="seconds"),
        "updated_at": started_at.isoformat(timespec="seconds"),
        "requested_trading_days": args.trading_days,
        "minimum_required_days": args.minimum_days,
        "target_dates": sorted(target_dates),
        "completed_dates": sorted(target_dates & complete_before),
        "missing_dates": sorted(missing_dates),
        "stock_universe_count": 0,
        "stocks_processed": 0,
        "stocks_downloaded": 0,
        "stocks_from_cache": 0,
        "stock_errors": [],
        "history_provider_config": args.history_provider,
        "history_provider_active": None,
        "history_provider_counts": {},
        "is_ready": len(target_dates & complete_before) >= args.minimum_days,
    }
    write_json(status_path, status)
    if not missing_dates:
        return status

    spot_rows = dataframe_to_records(load_stock_spot_df())
    universe: dict[str, str] = {}
    for row in spot_rows:
        code = get_code(row)
        if len(code) == 6 and code.isdigit():
            universe[code] = get_name(row)
    if len(universe) < args.minimum_stocks:
        raise RuntimeError(f"股票列表仅 {len(universe)} 条，拒绝生成不完整历史数据")
    write_json(work_dir / "universe.json", {"captured_at": now_cst().isoformat(), "stocks": universe})
    status["stock_universe_count"] = len(universe)
    required_stock_count = max(args.minimum_stocks, int(len(universe) * args.minimum_coverage_ratio))
    status["minimum_stock_count_per_day"] = required_stock_count
    status["minimum_stock_coverage_ratio"] = args.minimum_coverage_ratio
    write_json(status_path, status)

    target_text = {day.isoformat() for day in target_days}
    begin = target_days[0].strftime("%Y%m%d")
    end = target_days[-1].strftime("%Y%m%d")
    rows_by_date: dict[str, list[dict[str, Any]]] = {day: [] for day in missing_dates}
    pacer = RequestPacer(args.minimum_interval)
    source_router = HistorySourceRouter(args.history_provider)
    consecutive_download_errors = 0

    for index, (code, name) in enumerate(sorted(universe.items()), start=1):
        cache_path = cache_dir / f"{code}.json"
        rows = _load_cached_rows(cache_path, target_text)
        if rows is not None:
            status["stocks_from_cache"] += 1
            cached_sources = {
                str(row.get("历史数据源") or "")
                for row in rows
                if row.get("历史数据源")
            }
            if cached_sources:
                status["history_provider_active"] = "+".join(sorted(cached_sources))
            consecutive_download_errors = 0
        else:
            try:
                rows, provider = source_router.fetch(code, name, begin, end, pacer, retries=args.retries)
                status["history_provider_active"] = source_router.preferred_provider
                provider_counts = status["history_provider_counts"]
                provider_counts[provider] = int(provider_counts.get(provider) or 0) + 1
                write_json(
                    cache_path,
                    {
                        "code": code,
                        "name": name,
                        "fetched_at": now_cst().isoformat(timespec="seconds"),
                        "begin": begin,
                        "end": end,
                        "adjustment": "qfq",
                        "rows": rows,
                    },
                )
                status["stocks_downloaded"] += 1
                consecutive_download_errors = 0
            except Exception as exc:
                consecutive_download_errors += 1
                if len(status["stock_errors"]) < 100:
                    status["stock_errors"].append({"code": code, "error": str(exc)})
                rows = []
                if consecutive_download_errors >= args.max_consecutive_errors:
                    status["updated_at"] = now_cst().isoformat(timespec="seconds")
                    usable_stock_count = int(status["stocks_downloaded"]) + int(status["stocks_from_cache"])
                    if usable_stock_count >= required_stock_count:
                        status["coverage_target_reached"] = True
                        status["download_stopped_after_consecutive_errors"] = consecutive_download_errors
                        status["stocks_processed"] = index
                        write_json(status_path, status)
                        break
                    write_json(status_path, status)
                    raise RuntimeError(
                        f"历史行情来源连续失败 {consecutive_download_errors} 次，停止本轮并保留检查点"
                    )
        for row in rows:
            trade_date = str(row.get("交易日期") or "")
            if trade_date in rows_by_date:
                rows_by_date[trade_date].append(row)
        status["stocks_processed"] = index
        if index % 25 == 0 or index == len(universe):
            status["updated_at"] = now_cst().isoformat(timespec="seconds")
            write_json(status_path, status)

    captured_at = now_cst()
    pool_pacer = RequestPacer(max(args.minimum_interval, 0.5))
    created_dates: list[str] = []
    incomplete_dates: dict[str, int] = {}
    for market_day in target_days:
        day_text = market_day.isoformat()
        if day_text not in missing_dates:
            continue
        stock_rows = rows_by_date.get(day_text, [])
        if len(stock_rows) < required_stock_count:
            incomplete_dates[day_text] = len(stock_rows)
            continue
        market_date = market_day.strftime("%Y%m%d")
        pool_frames = {
            name: _fetch_pool_frame(name, function_name, market_date, pool_pacer)
            for name, function_name in POOL_FETCHERS.items()
        }
        snapshot = build_historical_snapshot(
            market_day,
            stock_rows,
            pool_frames,
            captured_at,
            args.trading_days,
        )
        date_dir = output_dir / day_text
        write_json(date_dir / "historical_snapshot.json", snapshot)
        created_dates.append(day_text)

    complete_after = existing_complete_dates(output_dir, required_stock_count)
    completed_targets = sorted(target_dates & complete_after)
    missing_after = sorted(target_dates - complete_after)
    status.update(
        {
            "status": "complete" if not missing_after else "partial",
            "updated_at": now_cst().isoformat(timespec="seconds"),
            "finished_at": now_cst().isoformat(timespec="seconds"),
            "created_dates": created_dates,
            "completed_dates": completed_targets,
            "missing_dates": missing_after,
            "incomplete_stock_counts": incomplete_dates,
            "is_ready": len(completed_targets) >= args.minimum_days,
        }
    )
    write_json(status_path, status)
    return status


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="首次部署时回填真实全市场日线数据。")
    parser.add_argument("--output-dir", default="data_market")
    parser.add_argument("--calendar-cache", default="data_market/trading_calendar.json")
    parser.add_argument("--trading-days", type=int, default=20, help="默认保存 20 个交易日，覆盖 MA20。")
    parser.add_argument("--minimum-days", type=int, default=15, help="就绪状态至少要求 15 个交易日。")
    parser.add_argument("--minimum-stocks", type=int, default=4000)
    parser.add_argument("--minimum-coverage-ratio", type=float, default=0.90)
    parser.add_argument(
        "--minimum-interval",
        type=float,
        default=float(os.getenv("MARKET_HISTORY_MIN_INTERVAL_SECONDS", "0.35")),
        help="同一历史行情来源两次请求之间的最短秒数。",
    )
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--max-consecutive-errors", type=int, default=8)
    parser.add_argument(
        "--history-provider",
        choices=("auto", "eastmoney", "tencent"),
        default=os.getenv("MARKET_HISTORY_PROVIDER", "auto"),
        help="历史日线来源；auto 会在来源不可用时自动切换。",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.trading_days < args.minimum_days or args.minimum_days < 1:
        raise SystemExit("--trading-days 必须不小于 --minimum-days，且二者必须为正数")
    lock_path = Path(args.output_dir) / ".history_bootstrap.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("w", encoding="utf-8") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            print(json.dumps({"status": "already_running"}, ensure_ascii=False))
            return
        try:
            status = run_bootstrap(args)
        except Exception as exc:
            status_path = Path(args.output_dir) / "bootstrap_status.json"
            try:
                existing = json.loads(status_path.read_text(encoding="utf-8"))
                failure = existing if isinstance(existing, dict) else {}
            except (OSError, json.JSONDecodeError):
                failure = {}
            failure.update(
                {
                    "schema_version": "1.0",
                    "status": "failed",
                    "updated_at": now_cst().isoformat(timespec="seconds"),
                    "is_ready": False,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
            write_json(status_path, failure)
            print(json.dumps(failure, ensure_ascii=False, indent=2))
            raise SystemExit(2) from exc
    print(json.dumps(status, ensure_ascii=False, indent=2))
    if not status.get("is_ready"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
