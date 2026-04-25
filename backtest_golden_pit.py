"""
黄金坑突破策略 - 追求更高胜率
核心逻辑：
1. 前期有上涨趋势
2. 快速下跌挖坑（3-7天，跌幅5-15%）
3. 快速反弹站回起跌点
4. 在突破确认时买入
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


def find_golden_pit(df, idx):
    """
    检测黄金坑形态
    返回: (score, pit_info)
    """
    if idx < 30 or idx >= len(df) - 5:
        return 0, None
    
    row = df.iloc[idx]
    
    # ==================== 寻找坑 ====================
    # 向前找最近的高点（坑的起点）
    high_idx = None
    high_price = 0
    
    for back in range(3, 20):
        if idx - back < 10:
            break
        
        # 找近期高点
        window = df.iloc[idx-back-5:idx-back+1]
        if len(window) < 5:
            continue
            
        local_high = window['最高'].max()
        local_high_idx = window['最高'].idxmax()
        
        # 确认是高点（之后开始下跌）
        if local_high > high_price:
            # 检查高点之后是否下跌
            after_high = df.iloc[df.index.get_loc(local_high_idx):idx]
            if len(after_high) >= 3:
                min_after = after_high['最低'].min()
                drop = (min_after - local_high) / local_high * 100
                
                if drop < -5:  # 至少下跌5%
                    high_price = local_high
                    high_idx = df.index.get_loc(local_high_idx)
    
    if high_idx is None:
        return 0, None
    
    # ==================== 分析坑的形态 ====================
    pit_data = df.iloc[high_idx:idx+1]
    
    # 坑底
    pit_low = pit_data['最低'].min()
    pit_low_idx = pit_data['最低'].idxmin()
    pit_low_loc = df.index.get_loc(pit_low_idx)
    
    # 挖坑深度
    pit_depth = (pit_low - high_price) / high_price * 100
    
    # 挖坑时间（从高点到低点）
    dig_days = pit_low_loc - high_idx
    
    # 反弹情况
    recover_data = df.iloc[pit_low_loc:idx+1]
    recover_days = len(recover_data)
    recover_pct = (row['收盘'] - pit_low) / pit_low * 100
    
    # 是否站回起跌点
    stand_back = row['收盘'] >= high_price * 0.95  # 站回95%以上
    
    # ==================== 评分 ====================
    score = 0
    
    # 坑的深度评分（最佳5-12%）
    if -12 <= pit_depth <= -5:
        score += 30
    elif -15 <= pit_depth <= -3:
        score += 20
    elif pit_depth < -15 or pit_depth > -3:
        return 0, None  # 坑太深或太浅
    
    # 挖坑时间（最佳3-8天）
    if 3 <= dig_days <= 8:
        score += 25
    elif 2 <= dig_days <= 12:
        score += 15
    else:
        score -= 10
    
    # 反弹时间（快速反弹更好）
    if 1 <= recover_days <= 5:
        score += 25
    elif recover_days <= 8:
        score += 15
    
    # 站回起跌点
    if stand_back:
        score += 30
    elif row['收盘'] >= high_price * 0.90:
        score += 15
    
    # 当日涨幅（突破确认）
    if 1 <= row['涨跌幅'] <= 5:
        score += 20
    elif 0 <= row['涨跌幅'] <= 7:
        score += 10
    
    # 量能配合
    avg_vol = df.iloc[idx-20:idx]['成交量'].mean()
    if row['成交量'] > avg_vol * 1.5:
        score += 15  # 放量突破
    elif row['成交量'] > avg_vol:
        score += 10
    
    pit_info = {
        'high_price': high_price,
        'pit_low': pit_low,
        'pit_depth': pit_depth,
        'dig_days': dig_days,
        'recover_days': recover_days,
        'stand_back': stand_back,
    }
    
    return score, pit_info


def find_breakout_pullback(df, idx):
    """
    突破回踩策略
    1. 突破前期高点
    2. 回踩确认（不破前高）
    3. 再次拉升
    """
    if idx < 30 or idx >= len(df) - 5:
        return 0, None
    
    row = df.iloc[idx]
    
    # 找20日前的高点
    prev_20d = df.iloc[idx-25:idx-5]
    if len(prev_20d) < 10:
        return 0, None
    
    prev_high = prev_20d['最高'].max()
    prev_high_idx = prev_20d['最高'].idxmax()
    
    # 近5日是否突破过
    recent_5d = df.iloc[idx-5:idx]
    breakthrough = recent_5d['最高'].max() > prev_high
    
    if not breakthrough:
        return 0, None
    
    # 当前是否在回踩后企稳
    pullback_low = recent_5d['最低'].min()
    pullback_depth = (pullback_low - prev_high) / prev_high * 100
    
    # 回踩不能跌破前高太多
    if pullback_depth < -5:
        return 0, None
    
    # 当日站稳
    if row['收盘'] < prev_high * 0.98:
        return 0, None
    
    # 评分
    score = 0
    
    # 突破后回踩幅度
    if -3 <= pullback_depth <= 0:
        score += 30
    elif -5 <= pullback_depth <= 2:
        score += 20
    
    # 当日收盘位置
    position = (row['收盘'] - row['最低']) / (row['最高'] - row['最低']) * 100 if row['最高'] > row['最低'] else 50
    if position >= 70:
        score += 25
    elif position >= 50:
        score += 15
    
    # 放量
    avg_vol = df.iloc[idx-20:idx]['成交量'].mean()
    if row['成交量'] > avg_vol * 1.3:
        score += 20
    
    # 均线多头
    ma5 = df['收盘'].iloc[idx-4:idx+1].mean()
    ma10 = df['收盘'].iloc[idx-9:idx+1].mean()
    if row['收盘'] > ma5 > ma10:
        score += 15
    
    info = {
        'prev_high': prev_high,
        'pullback_depth': pullback_depth,
        'position': position,
    }
    
    return score, info


def backtest_patterns():
    """回测形态策略"""
    log("="*70)
    log("形态策略回测（黄金坑 + 突破回踩）")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*70)
    
    # 获取大盘
    df_index = get_index_kline('000001', 250)
    
    # 股票池
    stocks = {
        '人工智能': ['300496', '300474', '002230', '300033', '688111'],
        '半导体': ['002371', '603986', '300661', '002049'],
        '机器人': ['300024', '002747', '002527', '688165'],
        '新能源车': ['300750', '002594', '300014', '300207'],
    }
    
    pit_signals = []
    breakout_signals = []
    
    for sector, codes in stocks.items():
        log(f"\n扫描板块: {sector}")
        
        for code in codes:
            df = get_stock_kline(code, 250)
            if df is None or len(df) < 60:
                continue
            
            name = get_stock_name(code)
            
            for idx in range(35, len(df) - 5):
                # 黄金坑
                pit_score, pit_info = find_golden_pit(df, idx)
                if pit_score >= 70:
                    entry = df.iloc[idx]['收盘']
                    ret_3d = (df.iloc[idx+3]['收盘'] - entry) / entry * 100
                    ret_5d = (df.iloc[idx+5]['收盘'] - entry) / entry * 100
                    
                    pit_signals.append({
                        'date': df.iloc[idx]['日期'],
                        'code': code,
                        'name': name,
                        'sector': sector,
                        'type': '黄金坑',
                        'score': pit_score,
                        'pit_depth': pit_info['pit_depth'],
                        'stand_back': pit_info['stand_back'],
                        'ret_3d': ret_3d,
                        'ret_5d': ret_5d,
                    })
                
                # 突破回踩
                br_score, br_info = find_breakout_pullback(df, idx)
                if br_score >= 60:
                    entry = df.iloc[idx]['收盘']
                    ret_3d = (df.iloc[idx+3]['收盘'] - entry) / entry * 100
                    ret_5d = (df.iloc[idx+5]['收盘'] - entry) / entry * 100
                    
                    breakout_signals.append({
                        'date': df.iloc[idx]['日期'],
                        'code': code,
                        'name': name,
                        'sector': sector,
                        'type': '突破回踩',
                        'score': br_score,
                        'pullback': br_info['pullback_depth'],
                        'ret_3d': ret_3d,
                        'ret_5d': ret_5d,
                    })
            
            time.sleep(0.1)
    
    # ==================== 黄金坑结果 ====================
    log("\n" + "="*70)
    log("一、黄金坑策略结果")
    log("="*70)
    
    if pit_signals:
        df_pit = pd.DataFrame(pit_signals)
        log(f"\n  共 {len(df_pit)} 个黄金坑信号")
        
        win_3d = (df_pit['ret_3d'] > 0).sum() / len(df_pit) * 100
        win_5d = (df_pit['ret_5d'] > 0).sum() / len(df_pit) * 100
        avg_3d = df_pit['ret_3d'].mean()
        avg_5d = df_pit['ret_5d'].mean()
        
        log(f"  3日胜率: {win_3d:.1f}%, 均收: {avg_3d:+.2f}%")
        log(f"  5日胜率: {win_5d:.1f}%, 均收: {avg_5d:+.2f}%")
        
        # 站回起跌点的
        stand_back = df_pit[df_pit['stand_back'] == True]
        if len(stand_back) >= 3:
            sb_win = (stand_back['ret_3d'] > 0).sum() / len(stand_back) * 100
            sb_avg = stand_back['ret_3d'].mean()
            log(f"\n  站回起跌点: {len(stand_back)}个, 3日胜率{sb_win:.1f}%, 均收{sb_avg:+.2f}%")
        
        # 高分信号
        high_pit = df_pit[df_pit['score'] >= 90]
        if len(high_pit) >= 3:
            hp_win = (high_pit['ret_3d'] > 0).sum() / len(high_pit) * 100
            hp_avg = high_pit['ret_3d'].mean()
            log(f"  高分(≥90): {len(high_pit)}个, 3日胜率{hp_win:.1f}%, 均收{hp_avg:+.2f}%")
        
        log("\n  最佳案例:")
        for _, s in df_pit.nlargest(5, 'ret_3d').iterrows():
            log(f"    ✓ {s['date'].strftime('%Y-%m-%d')} {s['name']}: 坑深{s['pit_depth']:.1f}%, 3日+{s['ret_3d']:.1f}%")
    else:
        log("  无黄金坑信号")
    
    # ==================== 突破回踩结果 ====================
    log("\n" + "="*70)
    log("二、突破回踩策略结果")
    log("="*70)
    
    if breakout_signals:
        df_br = pd.DataFrame(breakout_signals)
        log(f"\n  共 {len(df_br)} 个突破回踩信号")
        
        win_3d = (df_br['ret_3d'] > 0).sum() / len(df_br) * 100
        win_5d = (df_br['ret_5d'] > 0).sum() / len(df_br) * 100
        avg_3d = df_br['ret_3d'].mean()
        avg_5d = df_br['ret_5d'].mean()
        
        log(f"  3日胜率: {win_3d:.1f}%, 均收: {avg_3d:+.2f}%")
        log(f"  5日胜率: {win_5d:.1f}%, 均收: {avg_5d:+.2f}%")
        
        # 高分
        high_br = df_br[df_br['score'] >= 70]
        if len(high_br) >= 3:
            hb_win = (high_br['ret_3d'] > 0).sum() / len(high_br) * 100
            hb_avg = high_br['ret_3d'].mean()
            log(f"\n  高分(≥70): {len(high_br)}个, 3日胜率{hb_win:.1f}%, 均收{hb_avg:+.2f}%")
        
        log("\n  最佳案例:")
        for _, s in df_br.nlargest(5, 'ret_3d').iterrows():
            log(f"    ✓ {s['date'].strftime('%Y-%m-%d')} {s['name']}: 回踩{s['pullback']:.1f}%, 3日+{s['ret_3d']:.1f}%")
    else:
        log("  无突破回踩信号")
    
    # ==================== 综合对比 ====================
    log("\n" + "="*70)
    log("三、策略对比总结")
    log("="*70)
    
    results = []
    if pit_signals:
        df_pit = pd.DataFrame(pit_signals)
        results.append(('黄金坑', len(df_pit), 
                       (df_pit['ret_3d'] > 0).sum() / len(df_pit) * 100,
                       df_pit['ret_3d'].mean()))
    
    if breakout_signals:
        df_br = pd.DataFrame(breakout_signals)
        results.append(('突破回踩', len(df_br),
                       (df_br['ret_3d'] > 0).sum() / len(df_br) * 100,
                       df_br['ret_3d'].mean()))
    
    log("\n  策略         信号数   3日胜率   3日均收")
    log("  " + "-"*45)
    for name, count, winrate, avg_ret in results:
        log(f"  {name:10} {count:6}   {winrate:5.1f}%   {avg_ret:+.2f}%")
    
    # 最佳策略建议
    if results:
        best = max(results, key=lambda x: x[2])
        log(f"\n  【最佳策略】{best[0]}，胜率{best[2]:.1f}%")


if __name__ == "__main__":
    backtest_patterns()
