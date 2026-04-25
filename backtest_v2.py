"""
策略V2.0 回测
验证优化后策略的历史胜率
"""
import requests
import pandas as pd
import numpy as np
import os
from datetime import datetime
import json
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
    """获取日K线"""
    code = str(code).zfill(6)
    kcode = f'sh{code}' if code.startswith('6') else f'sz{code}'
    url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={kcode},day,,,{days},qfq'
    try:
        r = session.get(url, timeout=10)
        data = r.json()
        if not data.get('data'):
            return None
        stock_data = data['data'].get(kcode) or data['data'].get(kcode.upper())
        if not stock_data or 'qfqday' not in stock_data:
            return None
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


def check_signal_v2(df, idx):
    """
    检查某一天是否触发V2信号（用日K模拟分时特征）
    返回评分
    """
    if idx < 20 or idx >= len(df) - 5:
        return 0
    
    row = df.iloc[idx]
    
    # 用日K特征模拟分时托单
    # 1. 下影线明显
    body_low = min(row['开盘'], row['收盘'])
    body_high = max(row['开盘'], row['收盘'])
    lower_shadow = body_low - row['最低']
    upper_shadow = row['最高'] - body_high
    amplitude = row['最高'] - row['最低']
    
    if amplitude <= 0:
        return 0
    
    lower_shadow_ratio = lower_shadow / amplitude
    
    # 2. 近3日波动率
    recent_3d = df.iloc[idx-3:idx+1]
    volatility = (recent_3d['最高'].max() - recent_3d['最低'].min()) / recent_3d['收盘'].mean() * 100
    
    # 3. 量比
    vol_ratio = row['量比'] if pd.notna(row['量比']) else 1
    
    # 4. 收盘位置
    position = (row['收盘'] - row['最低']) / amplitude * 100 if amplitude > 0 else 50
    
    # 5. 涨跌幅
    change = row['涨跌幅'] if pd.notna(row['涨跌幅']) else 0
    
    # 6. 均线位置
    ma5 = df['收盘'].iloc[idx-4:idx+1].mean()
    ma10 = df['收盘'].iloc[idx-9:idx+1].mean()
    above_ma = row['收盘'] > ma5 and row['收盘'] > ma10
    
    # 评分
    score = 0
    
    # 下影线评分
    if lower_shadow_ratio >= 0.5 and lower_shadow > upper_shadow:
        score += 25
    elif lower_shadow_ratio >= 0.3:
        score += 15
    
    # 波动率评分
    if volatility < 4:
        score += 15
    elif volatility < 6:
        score += 10
    
    # 量比评分
    if vol_ratio >= 1.5:
        score += 25
    elif vol_ratio >= 1.2:
        score += 20
    elif vol_ratio >= 1.0:
        score += 10
    
    # 位置评分
    if position >= 80:
        score += 20
    elif position >= 60:
        score += 10
    
    # 均线评分
    if above_ma:
        score += 15
    
    # 涨跌幅惩罚
    if change > 5 or change < -2:
        score -= 20
    
    return score


def check_limit_up_washout_v2(df, idx):
    """检查涨停洗盘信号V2"""
    if idx < 30 or idx >= len(df) - 5:
        return 0
    
    row = df.iloc[idx]
    
    # 找之前的涨停
    for back in range(3, 25):
        if idx - back < 0:
            break
        
        prev_day = df.iloc[idx - back]
        if prev_day['涨跌幅'] > 9.5:
            # 找到涨停
            limit_high = prev_day['最高']
            pullback = (row['收盘'] - limit_high) / limit_high * 100
            
            # 量能萎缩
            vol_recent = df.iloc[idx-4:idx+1]['成交量'].mean()
            vol_limit = df.iloc[idx-back:idx-back+3]['成交量'].mean()
            vol_shrink = vol_recent / vol_limit if vol_limit > 0 else 1
            
            # 波动收窄
            volatility = (df.iloc[idx-4:idx+1]['最高'].max() - df.iloc[idx-4:idx+1]['最低'].min()) / row['收盘'] * 100
            
            # 评分
            score = 0
            
            if -15 <= pullback <= -5:
                score += 25
            elif -20 <= pullback <= -3:
                score += 15
            else:
                return 0
            
            if vol_shrink < 0.5:
                score += 25
            elif vol_shrink < 0.8:
                score += 15
            elif vol_shrink < 1.0:
                score += 10
            
            if volatility < 5:
                score += 15
            elif volatility < 8:
                score += 10
            
            # 均线支撑
            ma5 = df['收盘'].iloc[idx-4:idx+1].mean()
            if row['收盘'] > ma5:
                score += 10
            
            return score
    
    return 0


def backtest_strategy_v2():
    """回测V2策略"""
    log("="*70)
    log("策略V2.0 历史回测")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*70)
    
    # 股票池
    stocks = {
        '人工智能': ['300496', '300474', '002230', '300033'],
        '半导体': ['002371', '603986', '300661', '002049'],
        '机器人': ['300024', '002747', '300527', '002527'],
        '消费电子': ['002456', '002241', '300115', '002475'],
        '新能源车': ['300750', '002594', '300014', '300207'],
        '光伏': ['601012', '002459', '600438', '300274'],
    }
    
    all_signals = []
    
    for sector, codes in stocks.items():
        log(f"\n扫描板块: {sector}")
        
        for code in codes:
            df = get_stock_kline(code, 250)
            if df is None or len(df) < 60:
                continue
            
            name = get_stock_name(code)
            
            # 遍历历史数据找信号
            for idx in range(30, len(df) - 5):
                # 分时托单信号
                support_score = check_signal_v2(df, idx)
                
                # 涨停洗盘信号
                washout_score = check_limit_up_washout_v2(df, idx)
                
                # 取最高分
                score = max(support_score, washout_score)
                signal_type = '托单' if support_score > washout_score else '洗盘'
                
                if score >= 60:  # V2阈值
                    # 计算未来收益
                    entry = df.iloc[idx]['收盘']
                    ret_1d = (df.iloc[idx+1]['收盘'] - entry) / entry * 100
                    ret_3d = (df.iloc[idx+3]['收盘'] - entry) / entry * 100
                    ret_5d = (df.iloc[idx+5]['收盘'] - entry) / entry * 100
                    
                    # 最大回撤（5天内）
                    min_price = df.iloc[idx+1:idx+6]['最低'].min()
                    max_drawdown = (min_price - entry) / entry * 100
                    
                    all_signals.append({
                        'date': df.iloc[idx]['日期'],
                        'code': code,
                        'name': name,
                        'sector': sector,
                        'type': signal_type,
                        'score': score,
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
    log(f"\n共找到 {len(df_signals)} 个历史信号")
    
    # ==================== 整体统计 ====================
    log("\n" + "="*70)
    log("一、整体回测结果")
    log("="*70)
    
    for days, col in [(1, 'ret_1d'), (3, 'ret_3d'), (5, 'ret_5d')]:
        win_rate = (df_signals[col] > 0).sum() / len(df_signals) * 100
        avg_ret = df_signals[col].mean()
        log(f"  {days}日胜率: {win_rate:.1f}%, 均收: {avg_ret:+.2f}%")
    
    avg_dd = df_signals['max_dd'].mean()
    log(f"  平均最大回撤: {avg_dd:.2f}%")
    
    # ==================== 按评分分组 ====================
    log("\n" + "="*70)
    log("二、按评分分组")
    log("="*70)
    
    score_bins = [(60, 70), (70, 80), (80, 90), (90, 100), (100, 200)]
    
    for low, high in score_bins:
        subset = df_signals[(df_signals['score'] >= low) & (df_signals['score'] < high)]
        if len(subset) >= 5:
            win_rate = (subset['ret_3d'] > 0).sum() / len(subset) * 100
            avg_ret = subset['ret_3d'].mean()
            log(f"  评分{low}-{high}: {len(subset)}个信号, 3日胜率{win_rate:.1f}%, 均收{avg_ret:+.2f}%")
    
    # ==================== 按板块分组 ====================
    log("\n" + "="*70)
    log("三、按板块分组")
    log("="*70)
    
    for sector in df_signals['sector'].unique():
        subset = df_signals[df_signals['sector'] == sector]
        if len(subset) >= 5:
            win_rate = (subset['ret_3d'] > 0).sum() / len(subset) * 100
            avg_ret = subset['ret_3d'].mean()
            log(f"  {sector}: {len(subset)}个信号, 3日胜率{win_rate:.1f}%, 均收{avg_ret:+.2f}%")
    
    # ==================== 按信号类型 ====================
    log("\n" + "="*70)
    log("四、按信号类型")
    log("="*70)
    
    for signal_type in ['托单', '洗盘']:
        subset = df_signals[df_signals['type'] == signal_type]
        if len(subset) >= 5:
            win_rate = (subset['ret_3d'] > 0).sum() / len(subset) * 100
            avg_ret = subset['ret_3d'].mean()
            log(f"  {signal_type}信号: {len(subset)}个, 3日胜率{win_rate:.1f}%, 均收{avg_ret:+.2f}%")
    
    # ==================== 高胜率条件组合 ====================
    log("\n" + "="*70)
    log("五、高胜率条件组合")
    log("="*70)
    
    # 高评分
    high_score = df_signals[df_signals['score'] >= 80]
    if len(high_score) >= 5:
        win_rate = (high_score['ret_3d'] > 0).sum() / len(high_score) * 100
        avg_ret = high_score['ret_3d'].mean()
        log(f"  评分≥80: {len(high_score)}个, 3日胜率{win_rate:.1f}%, 均收{avg_ret:+.2f}%")
    
    # 高评分 + 科技板块
    tech_sectors = ['人工智能', '半导体', '机器人']
    high_tech = df_signals[(df_signals['score'] >= 80) & (df_signals['sector'].isin(tech_sectors))]
    if len(high_tech) >= 5:
        win_rate = (high_tech['ret_3d'] > 0).sum() / len(high_tech) * 100
        avg_ret = high_tech['ret_3d'].mean()
        log(f"  评分≥80 + 科技板块: {len(high_tech)}个, 3日胜率{win_rate:.1f}%, 均收{avg_ret:+.2f}%")
    
    # ==================== 近期表现 ====================
    log("\n" + "="*70)
    log("六、近3个月表现")
    log("="*70)
    
    recent = df_signals[df_signals['date'] >= df_signals['date'].max() - pd.Timedelta(days=90)]
    if len(recent) >= 5:
        win_rate = (recent['ret_3d'] > 0).sum() / len(recent) * 100
        avg_ret = recent['ret_3d'].mean()
        log(f"  近3月: {len(recent)}个信号, 3日胜率{win_rate:.1f}%, 均收{avg_ret:+.2f}%")
    
    # ==================== 最佳信号示例 ====================
    log("\n" + "="*70)
    log("七、最佳信号示例（评分最高）")
    log("="*70)
    
    top_signals = df_signals.nlargest(10, 'score')
    for _, s in top_signals.iterrows():
        log(f"  {s['date'].strftime('%Y-%m-%d')} {s['code']} {s['name']}: 评分{s['score']}, 3日{s['ret_3d']:+.1f}%, 5日{s['ret_5d']:+.1f}%")
    
    # ==================== 总结 ====================
    log("\n" + "="*70)
    log("八、回测总结")
    log("="*70)
    
    overall_winrate = (df_signals['ret_3d'] > 0).sum() / len(df_signals) * 100
    high_score_winrate = (high_score['ret_3d'] > 0).sum() / len(high_score) * 100 if len(high_score) >= 5 else 0
    
    log(f"\n  V2.0策略整体3日胜率: {overall_winrate:.1f}%")
    log(f"  高评分(≥80)3日胜率: {high_score_winrate:.1f}%")
    
    if overall_winrate >= 55:
        log(f"\n  ★ 策略有效，建议继续使用")
    elif overall_winrate >= 50:
        log(f"\n  ○ 策略边际有效，建议只用高评分信号")
    else:
        log(f"\n  ✗ 策略需要进一步优化")
    
    return df_signals


if __name__ == "__main__":
    backtest_strategy_v2()
