"""Thin AkShare wrapper for market snapshots.

The project keeps news/policy data in ``data_dev``.  This module only fetches
market data so the two data domains stay separate.
"""

from __future__ import annotations

import json
import math
import os
import subprocess
import time
from datetime import date, datetime
from typing import Any, Callable, Dict
from urllib.parse import urlencode

import akshare as ak
import pandas as pd
import requests


_ORIGINAL_SESSION_INIT = requests.Session.__init__
PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
)
LOCAL_ADAPTER_DEFAULT_URL = "http://127.0.0.1:8000"

EASTMONEY_SPOT_URL = "https://82.push2.eastmoney.com/api/qt/clist/get"
EASTMONEY_SPOT_PARAMS = {
    "pn": "1",
    "pz": "10000",
    "po": "1",
    "np": "1",
    "ut": "bd1d9ddb04089700cf9c27f6f7426281",
    "fltt": "2",
    "invt": "2",
    "fid": "f12",
    "fs": "m:0 t:6,m:0 t:80,m:1 t:2,m:1 t:23,m:0 t:81 s:2048",
    "fields": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,f20,f21,f23,f24,f25,f22,f11,f62,f128,f136,f115,f152",
}

EASTMONEY_CLIST_URL = "https://push2.eastmoney.com/api/qt/clist/get"
EASTMONEY_BOARD_URLS = {
    "industry": "https://17.push2.eastmoney.com/api/qt/clist/get",
    "concept": "https://79.push2.eastmoney.com/api/qt/clist/get",
}

EASTMONEY_FIELD_MAP = {
    "代码": "f12",
    "名称": "f14",
    "最新价": "f2",
    "涨跌幅": "f3",
    "涨跌额": "f4",
    "成交量": "f5",
    "成交额": "f6",
    "振幅": "f7",
    "换手率": "f8",
    "市盈率-动态": "f9",
    "量比": "f10",
    "最高": "f15",
    "最低": "f16",
    "今开": "f17",
    "昨收": "f18",
    "总市值": "f20",
    "流通市值": "f21",
    "市净率": "f23",
    "60日涨跌幅": "f24",
    "年初至今涨跌幅": "f25",
    "涨速": "f22",
    "5分钟涨跌": "f11",
    "主力净流入": "f62",
}

EASTMONEY_BOARD_FIELDS = (
    "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f12,f13,f14,f15,f16,f17,f18,"
    "f20,f21,f23,f24,f25,f26,f22,f33,f11,f62,f128,f136,f115,f152,"
    "f124,f107,f104,f105,f140,f141,f207,f208,f209,f222"
)

EASTMONEY_STOCK_FUND_FIELDS = (
    "f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f204,f205,f124"
)

EASTMONEY_STOCK_FUND_5D_FIELDS = (
    "f12,f14,f2,f109,f164,f165,f166,f167,f168,f169,f170,f171,f172,f173,f257,f258,f124"
)

EASTMONEY_BOARD_FUND_FIELDS = (
    "f12,f14,f2,f3,f62,f184,f66,f69,f72,f75,f78,f81,f84,f87,f204,f205,f124"
)


def _network_mode() -> str:
    return str(os.getenv("MARKET_NETWORK_MODE") or "system_proxy").strip().lower()


def _custom_proxy() -> str:
    return str(
        os.getenv("MARKET_PROXY")
        or os.getenv("MARKET_HTTPS_PROXY")
        or os.getenv("MARKET_HTTP_PROXY")
        or ""
    ).strip()


def _configure_requests_network() -> None:
    """Configure proxy behavior for market data.

    Modes:
    - system_proxy: keep environment proxy settings and let requests/curl use them.
    - custom_proxy: set MARKET_PROXY/MARKET_HTTP_PROXY/MARKET_HTTPS_PROXY.
    - direct: bypass proxy explicitly.
    - local_adapter: use local adapter for stock_spot and system proxy for fallbacks.
    """
    mode = _network_mode()
    if mode == "direct":
        for key in PROXY_ENV_KEYS:
            os.environ.pop(key, None)
        os.environ["NO_PROXY"] = "*"
        os.environ["no_proxy"] = "*"
        trust_env = False
    elif mode == "custom_proxy":
        proxy = _custom_proxy()
        if proxy:
            os.environ["HTTP_PROXY"] = proxy
            os.environ["HTTPS_PROXY"] = proxy
            os.environ["http_proxy"] = proxy
            os.environ["https_proxy"] = proxy
        os.environ["NO_PROXY"] = "127.0.0.1,localhost"
        os.environ["no_proxy"] = "127.0.0.1,localhost"
        trust_env = True
    else:
        trust_env = True

    def _session_init(self, *args: Any, **kwargs: Any) -> None:
        _ORIGINAL_SESSION_INIT(self, *args, **kwargs)
        self.trust_env = trust_env
        if not trust_env:
            self.proxies.clear()

    requests.Session.__init__ = _session_init


_configure_requests_network()


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if pd.isna(value):
        return None
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            return str(value)
    return value


def dataframe_to_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Convert a DataFrame to JSON-safe records."""
    if df is None or df.empty:
        return []
    safe_df = df.copy()
    safe_df = safe_df.where(pd.notna(safe_df), None)
    records = safe_df.to_dict(orient="records")
    return [{str(k): _json_safe(v) for k, v in row.items()} for row in records]


def fetch_frame(name: str, fetcher: Callable[..., pd.DataFrame], *args: Any, **kwargs: Any) -> Dict[str, Any]:
    """Fetch one AkShare frame and return a structured result."""
    started = time.time()
    try:
        frame = fetcher(*args, **kwargs)
        rows = dataframe_to_records(frame)
        return {
            "ok": True,
            "name": name,
            "rows": len(rows),
            "columns": [str(col) for col in frame.columns] if frame is not None else [],
            "duration_sec": round(time.time() - started, 3),
            "records": rows,
        }
    except Exception as exc:  # AkShare interfaces can fail independently.
        return {
            "ok": False,
            "name": name,
            "rows": 0,
            "columns": [],
            "duration_sec": round(time.time() - started, 3),
            "error": f"{type(exc).__name__}: {exc}",
            "records": [],
        }


def _eastmoney_get_json(url: str, params: dict[str, Any]) -> dict[str, Any]:
    try:
        response = requests.get(
            url,
            params=params,
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Referer": "https://quote.eastmoney.com/",
            },
        )
        response.raise_for_status()
        return response.json()
    except Exception as requests_error:
        query = urlencode(params)
        full_url = f"{url}?{query}" if query else url
        command = [
            "curl",
            "--silent",
            "--show-error",
            "--location",
            "--ipv4",
            "--max-time",
            "30",
            "--header",
            "accept: application/json",
            "--header",
            "user-agent: Mozilla/5.0",
            full_url,
        ]
        mode = _network_mode()
        if mode == "direct":
            command[4:4] = ["--noproxy", "*"]
        elif mode == "custom_proxy" and _custom_proxy():
            command[4:4] = ["--proxy", _custom_proxy()]
        try:
            completed = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            return json.loads((completed.stdout or "").strip())
        except Exception as curl_error:
            raise RuntimeError(f"requests={requests_error}; curl={curl_error}") from curl_error


def _eastmoney_fetch_pages(
    url: str,
    params: dict[str, Any],
    mapper: dict[str, str],
    max_pages: int = 80,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    total = None
    page = 1
    page_size = int(params.get("pz") or 100)

    while page <= max_pages:
        page_params = {**params, "pn": str(page), "pz": str(page_size)}
        payload = _eastmoney_get_json(url, page_params)
        data = payload.get("data") or {}
        records = data.get("diff") or []
        if total is None:
            total = int(data.get("total") or 0)
        if not records:
            break

        rows.extend(
            {
                column_name: item.get(field_name)
                for column_name, field_name in mapper.items()
            }
            for item in records
        )

        if total and len(rows) >= total:
            break
        page += 1

    if not rows:
        raise RuntimeError("Eastmoney clist returned no records")
    return pd.DataFrame(rows)


def load_eastmoney_spot_df() -> pd.DataFrame:
    """Fetch the full A-share spot snapshot directly from Eastmoney."""
    return _eastmoney_fetch_pages(
        EASTMONEY_SPOT_URL,
        EASTMONEY_SPOT_PARAMS,
        EASTMONEY_FIELD_MAP,
    )


def load_local_adapter_spot_df() -> pd.DataFrame:
    """Load A-share spot data from the optional local AKShare adapter."""
    base_url = str(os.getenv("MARKET_LOCAL_ADAPTER_URL") or LOCAL_ADAPTER_DEFAULT_URL).rstrip("/")
    session = requests.Session()
    session.trust_env = False
    response = session.get(f"{base_url}/quotes/snapshot", timeout=30)
    response.raise_for_status()
    payload = response.json()
    rows = payload.get("quotes") or []
    if not rows:
        raise RuntimeError("Local adapter returned no quotes")

    records: list[dict[str, Any]] = []
    for item in rows:
        raw = item.get("raw") or {}
        records.append(
            {
                "代码": item.get("code"),
                "名称": item.get("name"),
                "最新价": item.get("latestPrice"),
                "涨跌幅": item.get("changePercent"),
                "涨跌额": item.get("change"),
                "成交量": item.get("volume"),
                "成交额": item.get("turnover"),
                "振幅": item.get("amplitude"),
                "换手率": item.get("turnoverRate"),
                "市盈率-动态": item.get("pe"),
                "量比": item.get("volumeRatio"),
                "最高": item.get("high"),
                "最低": item.get("low"),
                "今开": item.get("open"),
                "昨收": item.get("previousClose"),
                "总市值": raw.get("totalMarketCap"),
                "流通市值": raw.get("circulatingMarketCap"),
                "市净率": item.get("pb"),
                "60日涨跌幅": raw.get("change60d"),
                "年初至今涨跌幅": raw.get("changeYtd"),
                "涨速": raw.get("speed"),
                "5分钟涨跌": raw.get("change5m"),
            }
        )
    return pd.DataFrame(records)


def load_eastmoney_board_df(kind: str) -> pd.DataFrame:
    is_industry = kind == "industry"
    return _eastmoney_fetch_pages(
        EASTMONEY_BOARD_URLS["industry" if is_industry else "concept"],
        {
            "pn": "1",
            "pz": "100",
            "po": "1",
            "np": "1",
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            "fltt": "2",
            "invt": "2",
            "fid": "f3" if is_industry else "f12",
            "fs": "m:90 t:2 f:!50" if is_industry else "m:90 t:3 f:!50",
            "fields": EASTMONEY_BOARD_FIELDS,
        },
        {
            "板块名称": "f14",
            "涨跌幅": "f3",
            "成交额": "f6",
            "换手率": "f8",
            "上涨家数": "f104",
            "下跌家数": "f105",
            "领涨股票": "f128",
            "领涨股票-涨跌幅": "f136",
            "板块代码": "f12",
        },
    )


def load_eastmoney_stock_fund_flow_df(indicator: str = "今日") -> pd.DataFrame:
    is_today = indicator == "今日"
    mapper = {
        "代码": "f12",
        "名称": "f14",
        "涨跌幅": "f3" if is_today else "f109",
        "今日主力净流入-净额": "f62" if is_today else "f164",
        "今日主力净流入-净占比": "f184" if is_today else "f165",
        "今日超大单净流入-净额": "f66" if is_today else "f166",
        "今日大单净流入-净额": "f72" if is_today else "f168",
    }
    return _eastmoney_fetch_pages(
        EASTMONEY_CLIST_URL,
        {
            "fid": "f62" if is_today else "f164",
            "po": "1",
            "pz": "100",
            "pn": "1",
            "np": "1",
            "fltt": "2",
            "invt": "2",
            "ut": "b2884a393a59ad64002292a3e90d46a5",
            "fs": "m:0 t:6 f:!2,m:0 t:13 f:!2,m:0 t:80 f:!2,m:1 t:2 f:!2,m:1 t:23 f:!2,m:0 t:7 f:!2,m:1 t:3 f:!2",
            "fields": EASTMONEY_STOCK_FUND_FIELDS if is_today else EASTMONEY_STOCK_FUND_5D_FIELDS,
        },
        mapper,
    )


def load_eastmoney_sector_fund_flow_df(sector_type: str = "行业资金流") -> pd.DataFrame:
    is_industry = sector_type == "行业资金流"
    return _eastmoney_fetch_pages(
        EASTMONEY_CLIST_URL,
        {
            "pn": "1",
            "pz": "100",
            "po": "1",
            "np": "1",
            "ut": "b2884a393a59ad64002292a3e90d46a5",
            "fltt": "2",
            "invt": "2",
            "fid0": "f62",
            "fs": "m:90 t:2" if is_industry else "m:90 t:3",
            "stat": "1",
            "fields": EASTMONEY_BOARD_FUND_FIELDS,
        },
        {
            "代码": "f12",
            "名称": "f14",
            "板块名称": "f14",
            "涨跌幅": "f3",
            "今日主力净流入-净额": "f62",
            "今日主力净流入-净占比": "f184",
            "今日超大单净流入-净额": "f66",
            "今日大单净流入-净额": "f72",
        },
    )


def load_stock_spot_df() -> pd.DataFrame:
    """Load full A-share spot data with direct Eastmoney first, AkShare fallback."""
    local_adapter_error = None
    if _network_mode() == "local_adapter":
        try:
            return load_local_adapter_spot_df()
        except Exception as exc:
            local_adapter_error = exc

    direct_error = None
    try:
        return load_eastmoney_spot_df()
    except Exception as exc:
        direct_error = exc

    akshare_em_error = None
    try:
        return ak.stock_zh_a_spot_em()
    except Exception as exc:
        akshare_em_error = exc

    try:
        return ak.stock_zh_a_spot()
    except Exception as exc:
        raise RuntimeError(
            "Spot data providers failed: "
            f"local_adapter={local_adapter_error}; "
            f"eastmoney_direct={direct_error}; "
            f"stock_zh_a_spot_em={akshare_em_error}; "
            f"stock_zh_a_spot={exc}"
        ) from exc


def load_industry_board_df() -> pd.DataFrame:
    direct_error = None
    try:
        return load_eastmoney_board_df("industry")
    except Exception as exc:
        direct_error = exc
    try:
        return ak.stock_board_industry_name_em()
    except Exception as exc:
        raise RuntimeError(f"Industry board providers failed: eastmoney_direct={direct_error}; akshare={exc}") from exc


def load_concept_board_df() -> pd.DataFrame:
    direct_error = None
    try:
        return load_eastmoney_board_df("concept")
    except Exception as exc:
        direct_error = exc
    try:
        return ak.stock_board_concept_name_em()
    except Exception as exc:
        raise RuntimeError(f"Concept board providers failed: eastmoney_direct={direct_error}; akshare={exc}") from exc


def load_stock_fund_flow_df(indicator: str = "今日") -> pd.DataFrame:
    direct_error = None
    try:
        return load_eastmoney_stock_fund_flow_df(indicator)
    except Exception as exc:
        direct_error = exc
    try:
        return ak.stock_individual_fund_flow_rank(indicator=indicator)
    except Exception as exc:
        raise RuntimeError(f"Stock fund flow providers failed: eastmoney_direct={direct_error}; akshare={exc}") from exc


def load_sector_fund_flow_df(indicator: str = "今日", sector_type: str = "行业资金流") -> pd.DataFrame:
    direct_error = None
    try:
        return load_eastmoney_sector_fund_flow_df(sector_type)
    except Exception as exc:
        direct_error = exc
    try:
        return ak.stock_sector_fund_flow_rank(indicator=indicator, sector_type=sector_type)
    except Exception as exc:
        raise RuntimeError(f"Sector fund flow providers failed: eastmoney_direct={direct_error}; akshare={exc}") from exc


def fetch_market_frames(snapshot_date: str) -> Dict[str, Dict[str, Any]]:
    """Fetch the first-stage market data used by morning/overnight skills."""
    return {
        "stock_spot": fetch_frame("stock_spot_direct_or_akshare", load_stock_spot_df),
        "industry_boards": fetch_frame("stock_board_industry_direct_or_akshare", load_industry_board_df),
        "concept_boards": fetch_frame("stock_board_concept_direct_or_akshare", load_concept_board_df),
        "individual_fund_flow_today": fetch_frame(
            "stock_individual_fund_flow_rank_today_direct_or_akshare",
            load_stock_fund_flow_df,
            "今日",
        ),
        "individual_fund_flow_5d": fetch_frame(
            "stock_individual_fund_flow_rank_5d_direct_or_akshare",
            load_stock_fund_flow_df,
            "5日",
        ),
        "industry_fund_flow_today": fetch_frame(
            "stock_sector_fund_flow_rank_industry_today_direct_or_akshare",
            load_sector_fund_flow_df,
            "今日",
            "行业资金流",
        ),
        "concept_fund_flow_today": fetch_frame(
            "stock_sector_fund_flow_rank_concept_today_direct_or_akshare",
            load_sector_fund_flow_df,
            "今日",
            "概念资金流",
        ),
        "limit_up_pool": fetch_frame("stock_zt_pool_em", ak.stock_zt_pool_em, date=snapshot_date),
        "previous_limit_up_pool": fetch_frame(
            "stock_zt_pool_previous_em",
            ak.stock_zt_pool_previous_em,
            date=snapshot_date,
        ),
        "strong_pool": fetch_frame("stock_zt_pool_strong_em", ak.stock_zt_pool_strong_em, date=snapshot_date),
        "broken_limit_pool": fetch_frame("stock_zt_pool_zbgc_em", ak.stock_zt_pool_zbgc_em, date=snapshot_date),
        "dtgc_pool": fetch_frame("stock_zt_pool_dtgc_em", ak.stock_zt_pool_dtgc_em, date=snapshot_date),
    }
