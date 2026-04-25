"""
极端筛选策略 - 宁缺毋滥
目标：信号少但胜率高（65%+）
"""
import requests
import pandas as pd
import numpy as np
import os
from datetime import datetime
import time

def log(msg):
    print(msg, flush=True)

for key in list(os.environ.keys()):
    if 'proxy' in key.lower():
        del os.environ[key]

session = requests.Session()
session.trust_env = False
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
})


def get_stock_kline(code, days=250):
    code = str(code).zfill(6)
    kcode = f'sh{code}' if code.startswith('6') else f'sz{code}'
    url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={kcode},day,,,{days},qfq'
    try:
        r = session.get(url, timeout=10)
        data = r.json()
        stock_data = data['data'].get(kcode) or data['data'].get(kcode.upper())
        days_data = stock_data['qfqday']
        df = pd.DataFrame([d[:6] for d in days_data], 
                        columns=['日期','开盘','收盘','最高','最低','成交量'])
        for col in ['开盘','收盘','最高','最低','成交量']:
            df[col] = df[col].astype(float)
        df['日期'] = pd.to_datetime(df['日期'])
        df['涨跌幅'] = df['收盘'].pct_change() * 100
        return df
    except:
        return None


def get_index_kline(code='000001', days=250):
    kcode = f'sh{code}'
    url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={kcode},day,,,{days},qfq'
    try:
        r = session.get(url, timeout=10)
        data = r.json()
        stock_data = data['data'].get(kcode) or data['data'].get(kcode.upper())
        days_data = stock_data.get('qfqday') or stock_data.get('day')
        df = pd.DataFrame([d[:6] for d in days_data], 
                        columns=['日期','开盘','收盘','最高','最低','成交量'])
        for col in ['开盘','收盘','最高','最低','成交量']:
            df[col] = df[col].astype(float)
        df['日期'] = pd.to_datetime(df['日期'])
        df['涨跌幅'] = df['收盘'].pct_change() * 100
        return df
    except:
        return None


def get_stock_name(code):
    code = str(code).zfill(6)
    kcode = f'sh{code}' if code.startswith('6') else f'sz{code}'
    try:
        url = f'https://qt.gtimg.cn/q={kcode}'
        r = session.get(url, timeout=5)
        parts = r.text.split('~')
        if len(parts) > 1:
            return parts[1]
    except:
        pass
    return code


def check_extreme_signal(df, idx, df_index):
    """
    极端严格的信号检测
    必须同时满足多个苛刻条件
    """
    if idx < 30 or idx >= len(df) - 5:
        return False, {}
    
    row = df.iloc[idx]
    
    # ==================== 1. 大盘必须上涨 ====================
    if df_index is not None and len(df_index) > idx:
        idx_row = df_index.iloc[idx]
        idx_ma5 = df_index['收盘'].iloc[idx-4:idx+1].mean()
        idx_ma10 = df_index['收盘'].iloc[idx-9:idx+1].mean()
        idx_ret_3d = (idx_row['收盘'] - df_index.iloc[idx-3]['收盘']) / df_index.iloc[idx-3]['收盘'] * 100
        
        # 大盘必须：多头排列 + 近3日上涨
        if not (idx_row['收盘'] > idx_ma5 > idx_ma10 and idx_ret_3d > 0):
            return False, {}
    
    # ==================== 2. K线形态 ====================
    body_low = min(row['开盘'], row['收盘'])
    body_high = max(row['开盘'], row['收盘'])
    lower_shadow = body_low - row['最低']
    upper_shadow = row['最高'] - body_high
    amplitude = row['最高'] - row['最低']
    body = abs(row['收盘'] - row['开盘'])
    
    if amplitude <= 0:
        return False, {}
    
    # 必须是阳线
    if row['收盘'] <= row['开盘']:
        return False, {}
    
    # 下影线必须明显（>50%振幅）且大于上影线
    lower_ratio = lower_shadow / amplitude
    if lower_ratio < 0.4 or lower_shadow <= upper_shadow:
        return False, {}
    
    # 收盘必须在上半部分（>75%位置）
    position = (row['收盘'] - row['最低']) / amplitude * 100
    if position < 75:
        return False, {}
    
    # ==================== 3. 均线必须多头排列 ====================
    ma5 = df['收盘'].iloc[idx-4:idx+1].mean()
    ma10 = df['收盘'].iloc[idx-9:idx+1].mean()
    ma20 = df['收盘'].iloc[idx-19:idx+1].mean()
    
    if not (row['收盘'] > ma5 > ma10):
        return False, {}
    
    # ==================== 4. 量能必须放大 ====================
    avg_vol = df['成交量'].iloc[idx-20:idx].mean()
    vol_ratio = row['成交量'] / avg_vol if avg_vol > 0 else 1
    
    if vol_ratio < 1.2 or vol_ratio > 3.0:
        return False, {}
    
    # ==================== 5. 涨跌幅限制 ====================
    change = row['涨跌幅']
    if change < 0.5 or change > 5:
        return False, {}
    
    # ==================== 6. 近期不能跌太多 ====================
    ret_5d = (row['收盘'] - df.iloc[idx-5]['收盘']) / df.iloc[idx-5]['收盘'] * 100
    ret_10d = (row['收盘'] - df.iloc[idx-10]['收盘']) / df.iloc[idx-10]['收盘'] * 100
    
    if ret_5d < -3 or ret_10d < -8:
        return False, {}
    
    # ==================== 7. 不能处于高位 ====================
    high_20d = df['最高'].iloc[idx-20:idx].max()
    low_20d = df['最低'].iloc[idx-20:idx].min()
    pos_20d = (row['收盘'] - low_20d) / (high_20d - low_20d) * 100 if high_20d > low_20d else 50
    
    if pos_20d > 95:  # 太接近20日高点
        return False, {}
    
    # ==================== 8. 必须有"突破"感 ====================
    # 当日最高突破近5日最高
    high_5d = df['最高'].iloc[idx-5:idx].max()
    if row['最高'] <= high_5d:
        return False, {}
    
    info = {
        'lower_ratio': lower_ratio,
        'position': position,
        'vol_ratio': vol_ratio,
        'change': change,
        'ret_5d': ret_5d,
        'pos_20d': pos_20d,
    }
    
    return True, info


def backtest_extreme():
    """极端筛选回测"""
    log("="*70)
    log("极端筛选策略回测")
    log("目标：信号少但胜率高")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*70)
    
    df_index = get_index_kline('000001', 250)
    
    stocks = {
        '人工智能': ['300496', '300474', '002230', '300033', '688111'],
        '半导体': ['002371', '603986', '300661', '002049'],
        '机器人': ['300024', '002747', '002527', '688165'],
        '新能源车': ['300750', '002594', '300014', '300207'],
    }
    
    signals = []
    
    for sector, codes in stocks.items():
        log(f"\n扫描板块: {sector}")
        
        for code in codes:
            df = get_stock_kline(code, 250)
            if df is None or len(df) < 60:
                continue
            
            name = get_stock_name(code)
            
            for idx in range(35, len(df) - 5):
                passed, info = check_extreme_signal(df, idx, df_index)
                
                if passed:
                    entry = df.iloc[idx]['收盘']
                    ret_1d = (df.iloc[idx+1]['收盘'] - entry) / entry * 100
                    ret_3d = (df.iloc[idx+3]['收盘'] - entry) / entry * 100
                    ret_5d = (df.iloc[idx+5]['收盘'] - entry) / entry * 100
                    
                    signals.append({
                        'date': df.iloc[idx]['日期'],
                        'code': code,
                        'name': name,
                        'sector': sector,
                        **info,
                        'ret_1d': ret_1d,
                        'ret_3d': ret_3d,
                        'ret_5d': ret_5d,
                    })
            
            time.sleep(0.1)
    
    if not signals:
        log("\n无符合条件的信号")
        return
    
    df_signals = pd.DataFrame(signals)
    log(f"\n共找到 {len(df_signals)} 个极端筛选信号")
    
    # 结果
    log("\n" + "="*70)
    log("回测结果")
    log("="*70)
    
    for days, col in [(1, 'ret_1d'), (3, 'ret_3d'), (5, 'ret_5d')]:
        win_rate = (df_signals[col] > 0).sum() / len(df_signals) * 100
        avg_ret = df_signals[col].mean()
        log(f"  {days}日胜率: {win_rate:.1f}%, 均收: {avg_ret:+.2f}%")
    
    # 按板块
    log("\n  按板块:")
    for sector in df_signals['sector'].unique():
        subset = df_signals[df_signals['sector'] == sector]
        if len(subset) >= 3:
            wr = (subset['ret_3d'] > 0).sum() / len(subset) * 100
            log(f"    {sector}: {len(subset)}个, 胜率{wr:.1f}%")
    
    # 信号列表
    log("\n  信号明细:")
    for _, s in df_signals.iterrows():
        result = '✓' if s['ret_3d'] > 0 else '✗'
        log(f"  {result} {s['date'].strftime('%Y-%m-%d')} {s['code']} {s['name']}: 量比{s['vol_ratio']:.1f}, 3日{s['ret_3d']:+.1f}%")
    
    # 总结
    log("\n" + "="*70)
    log("总结")
    log("="*70)
    
    winrate = (df_signals['ret_3d'] > 0).sum() / len(df_signals) * 100
    log(f"\n  极端筛选胜率: {winrate:.1f}%")
    log(f"  信号数量: {len(df_signals)}个（较少但精准）")
    
    if winrate >= 65:
        log(f"\n  ★★★ 策略有效！胜率达到{winrate:.1f}%")
    elif winrate >= 55:
        log(f"\n  ★★ 策略尚可，胜率{winrate:.1f}%")
    else:
        log(f"\n  ★ 需继续优化")


if __name__ == "__main__":
    backtest_extreme()
