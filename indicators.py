"""技术指标计算模块"""
import pandas as pd
import ta

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """计算常用技术指标"""
    if df is None or len(df) < 20:
        return df
    
    # 确保列名统一
    df = df.copy()
    close = df['收盘']
    high = df['最高']
    low = df['最低']
    volume = df['成交量']
    
    # 均线
    df['MA5'] = close.rolling(5).mean()
    df['MA10'] = close.rolling(10).mean()
    df['MA20'] = close.rolling(20).mean()
    
    # MACD
    macd = ta.trend.MACD(close)
    df['MACD'] = macd.macd()
    df['MACD_signal'] = macd.macd_signal()
    df['MACD_hist'] = macd.macd_diff()
    
    # RSI
    df['RSI'] = ta.momentum.RSIIndicator(close).rsi()
    
    # 布林带
    bb = ta.volatility.BollingerBands(close)
    df['BB_upper'] = bb.bollinger_hband()
    df['BB_lower'] = bb.bollinger_lband()
    
    # 成交量均线
    df['VOL_MA5'] = volume.rolling(5).mean()
    
    return df
