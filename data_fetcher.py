"""数据获取模块 - 使用AKShare"""
from contextlib import contextmanager
from contextlib import redirect_stdout
import io
import json
import os
import re
import threading
import time

import akshare as ak
import pandas as pd
import requests

from config import MAINBOARD_PATTERN

PROXY_ENV_KEYS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "http_proxy",
    "https_proxy",
    "all_proxy",
    "NO_PROXY",
    "no_proxy",
)

_proxy_env_lock = threading.Lock()
CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
ALL_STOCKS_CACHE_FILE = os.path.join(CACHE_DIR, "all_stocks.csv")
ALL_STOCKS_CACHE_MAX_AGE_SECONDS = 12 * 60 * 60
ALL_STOCKS_CACHE_PREFERRED_AGE_SECONDS = 60
HISTORY_CACHE_DIR = os.path.join(CACHE_DIR, "history")
HISTORY_CACHE_MAX_AGE_SECONDS = 5 * 60
HISTORY_STALE_CACHE_MAX_AGE_SECONDS = 12 * 60 * 60
STOCK_BOARD_CACHE_MAX_AGE_SECONDS = 30 * 60
EASTMONEY_QUOTE_UT = "fa5fd1943c7b386f172d6893dbfba10b"
EASTMONEY_HEADERS = {"User-Agent": "Mozilla/5.0"}
_stock_board_cache = {}
_stock_board_cache_lock = threading.Lock()


class MarketDataError(RuntimeError):
    """行情数据不可用或连接失败。"""


@contextmanager
def _without_proxy_env():
    """临时禁用代理环境变量，避免 AKShare 走到异常代理。"""
    with _proxy_env_lock:
        saved_env = {key: os.environ[key] for key in PROXY_ENV_KEYS if key in os.environ}

        for key in PROXY_ENV_KEYS:
            os.environ.pop(key, None)

        os.environ["NO_PROXY"] = "*"
        os.environ["no_proxy"] = "*"

        try:
            yield
        finally:
            for key in PROXY_ENV_KEYS:
                os.environ.pop(key, None)
            for key, value in saved_env.items():
                os.environ[key] = value


def _retry_akshare_fetch(
    fetcher,
    description: str,
    retries: int = 3,
    delay: float = 1.5,
    disable_proxy: bool = True,
):
    """对不稳定的行情接口做有限重试。"""
    last_error = None

    for attempt in range(1, retries + 1):
        try:
            if disable_proxy:
                with _without_proxy_env():
                    return fetcher()
            return fetcher()
        except Exception as exc:
            last_error = exc
            if attempt < retries:
                wait_seconds = delay * attempt
                print(f"{description}失败，第{attempt}次重试前等待{wait_seconds:.1f}秒: {exc}")
                time.sleep(wait_seconds)

    raise MarketDataError(f"{description}失败: {last_error}") from last_error


def _get_all_stocks_fallback():
    """备用行情源。"""
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        return ak.stock_zh_a_spot()


def _save_all_stocks_cache(df: pd.DataFrame):
    """缓存最近一次成功获取的股票池。"""
    if df is None or df.empty:
        return

    os.makedirs(CACHE_DIR, exist_ok=True)
    df.to_csv(ALL_STOCKS_CACHE_FILE, index=False, encoding="utf-8-sig")


def _load_all_stocks_cache(max_age_seconds: int = ALL_STOCKS_CACHE_MAX_AGE_SECONDS):
    """读取最近一次成功获取的股票池缓存。"""
    if not os.path.exists(ALL_STOCKS_CACHE_FILE):
        return None

    cache_age = time.time() - os.path.getmtime(ALL_STOCKS_CACHE_FILE)
    if cache_age > max_age_seconds:
        return None

    df = pd.read_csv(ALL_STOCKS_CACHE_FILE, dtype={"代码": str})
    if df is None or df.empty:
        return None
    return df


def _history_cache_file(symbol: str) -> str:
    return os.path.join(HISTORY_CACHE_DIR, f"{symbol}.csv")


def _save_stock_history_cache(symbol: str, df: pd.DataFrame):
    """缓存单只股票的历史K线。"""
    if df is None or df.empty:
        return

    os.makedirs(HISTORY_CACHE_DIR, exist_ok=True)
    df.to_csv(_history_cache_file(symbol), index=False, encoding="utf-8-sig")


def _load_stock_history_cache(symbol: str, max_age_seconds: int | None = None):
    """读取单只股票历史K线缓存。"""
    cache_file = _history_cache_file(symbol)
    if not os.path.exists(cache_file):
        return None

    if max_age_seconds is not None:
        cache_age = time.time() - os.path.getmtime(cache_file)
        if cache_age > max_age_seconds:
            return None

    df = pd.read_csv(cache_file)
    if df is None or df.empty:
        return None
    return df


def _to_tx_symbol(symbol: str) -> str:
    code = str(symbol).zfill(6)
    return f"sh{code}" if code.startswith("6") else f"sz{code}"


def _to_em_secid(symbol: str) -> str:
    code = str(symbol).zfill(6)
    market = 1 if code.startswith("6") else 0
    return f"{market}.{code}"


def _normalize_board_name(name: str) -> str:
    return re.sub(r"_+$", "", str(name or "").strip())


def _load_stock_board_cache(symbol: str):
    with _stock_board_cache_lock:
        entry = _stock_board_cache.get(symbol)
        if not entry:
            return None
        if time.time() - entry["timestamp"] > STOCK_BOARD_CACHE_MAX_AGE_SECONDS:
            _stock_board_cache.pop(symbol, None)
            return None
        return list(entry["boards"])


def _save_stock_board_cache(symbol: str, boards: list[str]):
    with _stock_board_cache_lock:
        _stock_board_cache[symbol] = {
            "timestamp": time.time(),
            "boards": list(boards),
        }


def get_stock_related_boards(symbol: str, limit: int = 12) -> list[str]:
    """获取个股所属板块列表。"""
    code = str(symbol).zfill(6)
    cached = _load_stock_board_cache(code)
    if cached is not None:
        return cached[:limit]

    params = {
        "secid": _to_em_secid(code),
        "fields": "f12,f14",
        "ut": EASTMONEY_QUOTE_UT,
        "pi": "0",
        "po": "1",
        "np": "1",
        "pz": str(max(limit, 20)),
        "spt": "3",
        "fltt": "1",
        "invt": "2",
        "wbp2u": "|0|0|0|web",
    }

    with _without_proxy_env():
        response = requests.get(
            "https://push2.eastmoney.com/api/qt/slist/get",
            params=params,
            headers=EASTMONEY_HEADERS,
            timeout=10,
        )
        response.raise_for_status()
        data_json = response.json()

    diff = data_json.get("data", {}).get("diff", [])
    boards = []
    seen = set()
    for item in diff:
        name = _normalize_board_name(item.get("f14", ""))
        if not name or name in seen:
            continue
        seen.add(name)
        boards.append(name)
        if len(boards) >= limit:
            break

    if boards:
        _save_stock_board_cache(code, boards)

    return boards


def get_stock_quote_board(symbol: str) -> str:
    """从东方财富个股页提取主行业板块。"""
    code = str(symbol).zfill(6)
    prefix = "sh" if code.startswith("6") else "sz"

    with _without_proxy_env():
        response = requests.get(
            f"https://quote.eastmoney.com/concept/{prefix}{code}.html",
            headers=EASTMONEY_HEADERS,
            timeout=10,
        )
        response.raise_for_status()
        html = response.text

    match = re.search(r"var\s+quotedata\s*=\s*(\{.*?\});", html)
    if not match:
        return ""

    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return ""

    return _normalize_board_name(data.get("bk_name", ""))


def _normalize_stock_history_frame(df: pd.DataFrame) -> pd.DataFrame:
    """统一不同数据源的历史K线字段。"""
    if df is None or df.empty:
        return df

    rename_map = {
        "date": "日期",
        "open": "开盘",
        "close": "收盘",
        "high": "最高",
        "low": "最低",
        "amount": "成交量",
    }

    normalized = df.rename(columns=rename_map).copy()
    for column in ("开盘", "收盘", "最高", "最低", "成交量"):
        if column in normalized.columns:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    return normalized


def _get_history_provider_order():
    """返回历史K线数据源优先级。"""
    provider = os.getenv("STOCK_HISTORY_PROVIDER", "tx").strip().lower()
    if provider == "em":
        return ("em", "tx")
    return ("tx", "em")


def get_all_stocks():
    """获取所有A股实时行情，只保留主板。"""
    cached_df = _load_all_stocks_cache(ALL_STOCKS_CACHE_PREFERRED_AGE_SECONDS)
    if cached_df is not None:
        return cached_df

    try:
        df = _retry_akshare_fetch(
            lambda: ak.stock_zh_a_spot_em(),
            "获取全市场实时行情",
            retries=3,
            delay=2,
        )
    except MarketDataError as primary_error:
        print(f"东方财富实时行情失败，切换备用源: {primary_error}")
        try:
            df = _retry_akshare_fetch(
                _get_all_stocks_fallback,
                "获取全市场实时行情(备用源)",
                retries=2,
                delay=3,
                disable_proxy=False,
            )
        except MarketDataError as fallback_error:
            cached_df = _load_all_stocks_cache()
            if cached_df is not None:
                print(f"实时行情全部失败，使用本地缓存股票池: {fallback_error}")
                df = cached_df
            else:
                raise fallback_error

    if df is None or df.empty:
        raise MarketDataError("未获取到实时行情数据，请稍后重试")

    if "代码" not in df.columns:
        raise MarketDataError("实时行情数据格式异常，缺少代码字段")

    df = df.copy()
    df["代码"] = (
        df["代码"]
        .astype(str)
        .str.extract(r"(\d{6})", expand=False)
        .fillna(df["代码"].astype(str))
    )
    df = df[df["代码"].astype(str).str.match(MAINBOARD_PATTERN, na=False)]
    _save_all_stocks_cache(df)
    return df


def get_stock_history(symbol: str, days: int = 60) -> pd.DataFrame:
    """获取单只股票历史K线。"""
    cached_df = _load_stock_history_cache(symbol, HISTORY_CACHE_MAX_AGE_SECONDS)
    if cached_df is not None:
        return cached_df.tail(days)

    fetchers = {
        "tx": (
            lambda: ak.stock_zh_a_hist_tx(
                symbol=_to_tx_symbol(symbol),
                adjust="qfq",
                timeout=10,
            ),
            f"获取 {symbol} 历史K线(腾讯源)",
            1,
            1,
            False,
        ),
        "em": (
            lambda: ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq"),
            f"获取 {symbol} 历史K线",
            2,
            1,
            True,
        ),
    }

    df = None
    last_error = None
    for provider in _get_history_provider_order():
        fetcher, description, retries, delay, disable_proxy = fetchers[provider]
        try:
            df = _retry_akshare_fetch(
                fetcher,
                description,
                retries=retries,
                delay=delay,
                disable_proxy=disable_proxy,
            )
            df = _normalize_stock_history_frame(df)
            break
        except MarketDataError as exc:
            last_error = exc
            print(exc)

    if df is None:
        cached_df = _load_stock_history_cache(symbol, HISTORY_STALE_CACHE_MAX_AGE_SECONDS)
        if cached_df is not None:
            print(f"{symbol} 历史K线接口失败，回退到本地缓存")
            return cached_df.tail(days)
        if last_error is not None:
            print(last_error)
        return None

    if df is not None and len(df) > 0:
        _save_stock_history_cache(symbol, df)
        return df.tail(days)
    return None


def get_stock_info(symbol: str) -> dict:
    """获取股票基本信息。"""
    try:
        df = _retry_akshare_fetch(
            lambda: ak.stock_individual_info_em(symbol=symbol),
            f"获取 {symbol} 股票信息",
            retries=2,
            delay=1,
        )
        info = dict(zip(df["item"], df["value"]))
    except Exception:
        info = {}

    try:
        primary_board = get_stock_quote_board(symbol)
    except Exception:
        primary_board = ""

    try:
        boards = get_stock_related_boards(symbol)
    except Exception:
        boards = []

    industry = str(info.get("行业", "")).strip()
    if primary_board:
        info["行业板块"] = primary_board

    if boards:
        related_boards = [
            board for board in boards
            if board and board != primary_board and board != industry
        ]
        info["所属板块"] = "、".join(boards)
        if related_boards:
            info["概念板块"] = "、".join(related_boards[:8])

    return info


def get_intraday_data(symbol: str, days: int = 30) -> pd.DataFrame:
    """获取分时数据。

    Args:
        symbol: 股票代码
        days: 获取天数，默认30天，最多约31天
    """
    try:
        df = _retry_akshare_fetch(
            lambda: ak.stock_zh_a_hist_min_em(symbol=symbol, period="5", adjust=""),
            f"获取 {symbol} 分时数据",
            retries=2,
            delay=1,
        )
        if df is not None and len(df) > 0:
            bars_per_day = 48
            return df.tail(days * bars_per_day)
        return df
    except Exception:
        return None


def get_daily_kline(symbol: str, days: int = 30) -> pd.DataFrame:
    """获取日K线数据。"""
    try:
        df = _retry_akshare_fetch(
            lambda: ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq"),
            f"获取 {symbol} 日K线",
            retries=2,
            delay=1,
        )
        if df is not None and len(df) > 0:
            return df.tail(days)
        return df
    except Exception:
        return None
