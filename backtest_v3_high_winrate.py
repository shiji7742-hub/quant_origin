"""
策略V3.0 - 高胜率版本
目标：通过更严格的条件筛选，将胜率提升到65%+
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
        df['量比'] = df['成交量'] / df['成交量'].rolling(20).mean()
        return df
    except:
        return None


def get_index_kline(code='000001', days=250):
    """获取大盘数据"""
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


def check_market_condition(df_index, idx):
    """
    检查大盘环境
    返回: 'bull'(牛市), 'bear'(熊市), 'neutral'(震荡)
    """
    if idx < 20:
        return 'neutral'
    
    row = df_index.iloc[idx]
    
    # 均线
    ma5 = df_index['收盘'].iloc[idx-4:idx+1].mean()
    ma10 = df_index['收盘'].iloc[idx-9:idx+1].mean()
    ma20 = df_index['收盘'].iloc[idx-19:idx+1].mean()
    
    # 近期涨跌
    ret_5d = (row['收盘'] - df_index.iloc[idx-5]['收盘']) / df_index.iloc[idx-5]['收盘'] * 100
    ret_10d = (row['收盘'] - df_index.iloc[idx-10]['收盘']) / df_index.iloc[idx-10]['收盘'] * 100
    
    # 判断
    if row['收盘'] > ma5 > ma10 and ret_5d > 0:
        return 'bull'
    elif row['收盘'] < ma5 < ma10 and ret_5d < -2:
        return 'bear'
    else:
        return 'neutral'


def check_signal_v3(df, idx, df_index=None):
    """
    V3高胜率信号检测
    更严格的条件
    """
    if idx < 25 or idx >= len(df) - 5:
        return 0, {}
    
    row = df.iloc[idx]
    
    # ==================== 基础指标 ====================
    body_low = min(row['开盘'], row['收盘'])
    body_high = max(row['开盘'], row['收盘'])
    lower_shadow = body_low - row['最低']
    upper_shadow = row['最高'] - body_high
    amplitude = row['最高'] - row['最低']
    
    if amplitude <= 0:
        return 0, {}
    
    lower_shadow_ratio = lower_shadow / amplitude
    upper_shadow_ratio = upper_shadow / amplitude
    
    # 近期数据
    recent_5d = df.iloc[idx-5:idx]
    recent_10d = df.iloc[idx-10:idx]
    
    # 波动率
    volatility_5d = (recent_5d['最高'].max() - recent_5d['最低'].min()) / recent_5d['收盘'].mean() * 100
    
    # 量比
    vol_ratio = row['量比'] if pd.notna(row['量比']) else 1
    
    # 收盘位置
    position = (row['收盘'] - row['最低']) / amplitude * 100
    
    # 涨跌幅
    change = row['涨跌幅'] if pd.notna(row['涨跌幅']) else 0
    
    # 均线
    ma5 = df['收盘'].iloc[idx-4:idx+1].mean()
    ma10 = df['收盘'].iloc[idx-9:idx+1].mean()
    ma20 = df['收盘'].iloc[idx-19:idx+1].mean()
    
    # 近期走势
    ret_5d = (row['收盘'] - df.iloc[idx-5]['收盘']) / df.iloc[idx-5]['收盘'] * 100
    ret_10d = (row['收盘'] - df.iloc[idx-10]['收盘']) / df.iloc[idx-10]['收盘'] * 100
    
    # 连续下跌天数
    down_days = 0
    for i in range(1, 6):
        if df.iloc[idx-i]['涨跌幅'] < 0:
            down_days += 1
        else:
            break
    
    # ==================== 大盘过滤 ====================
    market_condition = 'neutral'
    if df_index is not None and len(df_index) > idx:
        market_condition = check_market_condition(df_index, idx)
    
    # ==================== 严格条件检查 ====================
    conditions = {
        # 必须条件
        '下影线明显': lower_shadow_ratio >= 0.4 and lower_shadow > upper_shadow,
        '收盘位置高': position >= 70,
        '量比适中': 1.0 <= vol_ratio <= 3.0,
        '涨跌幅适中': -2 <= change <= 3,
        '波动不大': volatility_5d < 8,
        
        # 趋势条件
        '站上均线': row['收盘'] > ma5,
        '均线多头': ma5 >= ma10,
        
        # 企稳条件
        '近5日不大跌': ret_5d > -5,
        '近10日不大跌': ret_10d > -10,
        
        # 大盘条件
        '大盘非熊市': market_condition != 'bear',
    }
    
    passed = sum(conditions.values())
    
    # ==================== 评分系统 ====================
    score = 0
    
    # 下影线评分（核心）
    if lower_shadow_ratio >= 0.6 and lower_shadow > upper_shadow * 2:
        score += 30
    elif lower_shadow_ratio >= 0.5 and lower_shadow > upper_shadow:
        score += 25
    elif lower_shadow_ratio >= 0.4:
        score += 15
    
    # 收盘位置评分
    if position >= 90:
        score += 25
    elif position >= 80:
        score += 20
    elif position >= 70:
        score += 15
    
    # 量比评分
    if 1.2 <= vol_ratio <= 2.0:
        score += 25  # 最佳区间
    elif 1.0 <= vol_ratio <= 2.5:
        score += 15
    elif vol_ratio > 2.5:
        score += 5  # 量太大扣分
    
    # 均线评分
    if row['收盘'] > ma5 > ma10 > ma20:
        score += 20  # 完美多头
    elif row['收盘'] > ma5 > ma10:
        score += 15
    elif row['收盘'] > ma5:
        score += 10
    
    # 连续下跌后反弹（加分）
    if down_days >= 2 and change > 0:
        score += 10
    
    # 大盘加分
    if market_condition == 'bull':
        score += 15
    elif market_condition == 'bear':
        score -= 20
    
    # 惩罚项
    if change > 4:
        score -= 15  # 涨太多
    if change < -1:
        score -= 10  # 当日下跌
    if ret_5d < -8:
        score -= 15  # 近期跌太多
    if volatility_5d > 10:
        score -= 15  # 波动太大
    
    return score, conditions


def backtest_v3():
    """V3高胜率回测"""
    log("="*70)
    log("策略V3.0 高胜率回测")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*70)
    
    # 获取大盘数据
    log("\n获取大盘数据...")
    df_index = get_index_kline('000001', 250)
    
    # 股票池（只保留效果好的板块）
    stocks = {
        '人工智能': ['300496', '300474', '002230', '300033', '688111'],
        '半导体': ['002371', '603986', '300661', '002049'],
        '机器人': ['300024', '002747', '002527', '688165'],
    }
    
    all_signals = []
    
    for sector, codes in stocks.items():
        log(f"\n扫描板块: {sector}")
        
        for code in codes:
            df = get_stock_kline(code, 250)
            if df is None or len(df) < 60:
                continue
            
            name = get_stock_name(code)
            
            for idx in range(30, len(df) - 5):
                score, conditions = check_signal_v3(df, idx, df_index)
                
                # V3更高的阈值
                if score >= 70 and sum(conditions.values()) >= 7:
                    entry = df.iloc[idx]['收盘']
                    ret_1d = (df.iloc[idx+1]['收盘'] - entry) / entry * 100
                    ret_3d = (df.iloc[idx+3]['收盘'] - entry) / entry * 100
                    ret_5d = (df.iloc[idx+5]['收盘'] - entry) / entry * 100
                    
                    min_price = df.iloc[idx+1:idx+6]['最低'].min()
                    max_drawdown = (min_price - entry) / entry * 100
                    
                    # 大盘状态
                    market = 'neutral'
                    if df_index is not None and len(df_index) > idx:
                        market = check_market_condition(df_index, idx)
                    
                    all_signals.append({
                        'date': df.iloc[idx]['日期'],
                        'code': code,
                        'name': name,
                        'sector': sector,
                        'score': score,
                        'passed': sum(conditions.values()),
                        'market': market,
                        'ret_1d': ret_1d,
                        'ret_3d': ret_3d,
                        'ret_5d': ret_5d,
                        'max_dd': max_drawdown,
                    })
            
            time.sleep(0.1)
    
    if not all_signals:
        log("无历史信号")
        return
    
    df_signals = pd.DataFrame(all_signals)
    log(f"\n共找到 {len(df_signals)} 个高质量信号")
    
    # ==================== 整体统计 ====================
    log("\n" + "="*70)
    log("一、V3整体回测结果")
    log("="*70)
    
    for days, col in [(1, 'ret_1d'), (3, 'ret_3d'), (5, 'ret_5d')]:
        win_rate = (df_signals[col] > 0).sum() / len(df_signals) * 100
        avg_ret = df_signals[col].mean()
        log(f"  {days}日胜率: {win_rate:.1f}%, 均收: {avg_ret:+.2f}%")
    
    log(f"  平均最大回撤: {df_signals['max_dd'].mean():.2f}%")
    
    # ==================== 按评分分组 ====================
    log("\n" + "="*70)
    log("二、按评分分组")
    log("="*70)
    
    for threshold in [70, 80, 90, 100]:
        subset = df_signals[df_signals['score'] >= threshold]
        if len(subset) >= 3:
            win_rate = (subset['ret_3d'] > 0).sum() / len(subset) * 100
            avg_ret = subset['ret_3d'].mean()
            log(f"  评分≥{threshold}: {len(subset)}个信号, 3日胜率{win_rate:.1f}%, 均收{avg_ret:+.2f}%")
    
    # ==================== 按大盘分组 ====================
    log("\n" + "="*70)
    log("三、按大盘环境分组")
    log("="*70)
    
    for market in ['bull', 'neutral', 'bear']:
        subset = df_signals[df_signals['market'] == market]
        if len(subset) >= 3:
            win_rate = (subset['ret_3d'] > 0).sum() / len(subset) * 100
            avg_ret = subset['ret_3d'].mean()
            label = {'bull': '牛市', 'neutral': '震荡', 'bear': '熊市'}[market]
            log(f"  {label}: {len(subset)}个信号, 3日胜率{win_rate:.1f}%, 均收{avg_ret:+.2f}%")
    
    # ==================== 最佳组合 ====================
    log("\n" + "="*70)
    log("四、最佳条件组合")
    log("="*70)
    
    # 高评分 + 牛市/震荡
    best = df_signals[(df_signals['score'] >= 80) & (df_signals['market'] != 'bear')]
    if len(best) >= 3:
        win_rate = (best['ret_3d'] > 0).sum() / len(best) * 100
        avg_ret = best['ret_3d'].mean()
        log(f"  评分≥80 + 非熊市: {len(best)}个, 3日胜率{win_rate:.1f}%, 均收{avg_ret:+.2f}%")
    
    # 高评分 + 牛市
    bull_best = df_signals[(df_signals['score'] >= 80) & (df_signals['market'] == 'bull')]
    if len(bull_best) >= 3:
        win_rate = (bull_best['ret_3d'] > 0).sum() / len(bull_best) * 100
        avg_ret = bull_best['ret_3d'].mean()
        log(f"  评分≥80 + 牛市: {len(bull_best)}个, 3日胜率{win_rate:.1f}%, 均收{avg_ret:+.2f}%")
    
    # ==================== 信号示例 ====================
    log("\n" + "="*70)
    log("五、高分信号示例")
    log("="*70)
    
    top = df_signals.nlargest(15, 'score')
    for _, s in top.iterrows():
        result = '✓' if s['ret_3d'] > 0 else '✗'
        log(f"  {result} {s['date'].strftime('%Y-%m-%d')} {s['code']} {s['name']}: 评分{s['score']}, 大盘{s['market']}, 3日{s['ret_3d']:+.1f}%")
    
    # ==================== 失败案例分析 ====================
    log("\n" + "="*70)
    log("六、失败案例分析")
    log("="*70)
    
    failed = df_signals[df_signals['ret_3d'] < -3].nlargest(5, 'score')
    if len(failed) > 0:
        log("\n  大亏案例（亏损>3%）:")
        for _, s in failed.iterrows():
            log(f"  ✗ {s['date'].strftime('%Y-%m-%d')} {s['code']} {s['name']}: 大盘{s['market']}, 3日{s['ret_3d']:.1f}%")
    
    bear_failed = df_signals[df_signals['market'] == 'bear']
    if len(bear_failed) > 0:
        bear_winrate = (bear_failed['ret_3d'] > 0).sum() / len(bear_failed) * 100
        log(f"\n  熊市信号胜率: {bear_winrate:.1f}% → 建议熊市不操作")
    
    # ==================== 总结 ====================
    log("\n" + "="*70)
    log("七、回测总结")
    log("="*70)
    
    overall = (df_signals['ret_3d'] > 0).sum() / len(df_signals) * 100
    log(f"\n  V3策略整体3日胜率: {overall:.1f}%")
    
    if len(best) >= 3:
        best_wr = (best['ret_3d'] > 0).sum() / len(best) * 100
        log(f"  最佳组合(评分≥80+非熊市)胜率: {best_wr:.1f}%")
    
    log(f"\n  【使用建议】")
    log(f"  1. 只在大盘非熊市时操作")
    log(f"  2. 只选择评分≥80的信号")
    log(f"  3. 重点关注人工智能、机器人板块")
    log(f"  4. 信号数量少但质量高")
    
    return df_signals


if __name__ == "__main__":
    backtest_v3()
