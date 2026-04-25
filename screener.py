"""股票筛选模块"""
import pandas as pd
from data_fetcher import MarketDataError, get_all_stocks, get_stock_history
from indicators import calculate_indicators
from config import MAX_STOCKS


def _build_candidate_frame() -> pd.DataFrame:
    """从全市场实时行情中构建候选池。"""
    df = get_all_stocks()

    if df is None or df.empty:
        raise MarketDataError("实时行情暂不可用，请稍后重试")

    required_columns = {'代码', '涨跌幅', '成交额'}
    missing_columns = required_columns - set(df.columns)
    if missing_columns:
        raise MarketDataError(f"实时行情字段缺失: {', '.join(sorted(missing_columns))}")

    df = df.copy()
    for column in ('涨跌幅', '成交额', '换手率'):
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors='coerce')

    filters = (
        (df['涨跌幅'] > -3) &
        (df['涨跌幅'] < 7) &
        (df['成交额'] > 1e8)
    )

    if '换手率' in df.columns:
        filters &= df['换手率'] > 1

    return df[filters].sort_values('成交额', ascending=False)


def screen_stocks(limit=MAX_STOCKS) -> list:
    """
    初步筛选股票。

    limit 为 None 时返回完整候选池，用于真正的全市场策略扫描；
    其他场景仍保留原先的小样本快速模式。
    """
    df = _build_candidate_frame()

    if limit is None:
        return df['代码'].tolist()

    limit = max(int(limit), 0)
    if limit == 0:
        return []

    df = df.head(limit)
    return df['代码'].tolist()


def screen_all_stocks() -> list:
    """返回通过基础过滤后的完整候选池。"""
    return screen_stocks(limit=None)

def analyze_stock(symbol: str) -> dict:
    """分析单只股票，返回技术面数据"""
    df = get_stock_history(symbol, days=60)
    if df is None or len(df) < 20:
        return None
    
    df = calculate_indicators(df)
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    return {
        "代码": symbol,
        "最新价": latest['收盘'],
        "涨跌幅": round((latest['收盘'] - prev['收盘']) / prev['收盘'] * 100, 2),
        "MA5": round(latest['MA5'], 2),
        "MA10": round(latest['MA10'], 2),
        "MA20": round(latest['MA20'], 2),
        "MACD": round(latest['MACD'], 4),
        "RSI": round(latest['RSI'], 2),
        "成交量比": round(latest['成交量'] / latest['VOL_MA5'], 2) if latest['VOL_MA5'] > 0 else 0,
        "均线多头": latest['MA5'] > latest['MA10'] > latest['MA20'],
        "MACD金叉": latest['MACD'] > latest['MACD_signal'] and prev['MACD'] <= prev['MACD_signal'],
    }
