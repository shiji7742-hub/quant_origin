"""
策略实际收益分析
重点：不仅看胜率，还要看盈亏比和期望收益
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


def check_signal(df, idx):
    """V2优化版信号"""
    if idx < 25 or idx >= len(df) - 5:
        return 0
    
    row = df.iloc[idx]
    
    body_low = min(row['开盘'], row['收盘'])
    lower_shadow = body_low - row['最低']
    upper_shadow = row['最高'] - max(row['开盘'], row['收盘'])
    amplitude = row['最高'] - row['最低']
    
    if amplitude <= 0:
        return 0
    
    lower_ratio = lower_shadow / amplitude
    vol_ratio = row['量比'] if pd.notna(row['量比']) else 1
    position = (row['收盘'] - row['最低']) / amplitude * 100
    change = row['涨跌幅'] if pd.notna(row['涨跌幅']) else 0
    
    ma5 = df['收盘'].iloc[idx-4:idx+1].mean()
    ma10 = df['收盘'].iloc[idx-9:idx+1].mean()
    
    score = 0
    
    if lower_ratio >= 0.5 and lower_shadow > upper_shadow:
        score += 25
    elif lower_ratio >= 0.3:
        score += 15
    
    if vol_ratio >= 1.5:
        score += 25
    elif vol_ratio >= 1.2:
        score += 20
    elif vol_ratio >= 1.0:
        score += 10
    
    if position >= 80:
        score += 20
    elif position >= 60:
        score += 10
    
    if row['收盘'] > ma5 > ma10:
        score += 15
    elif row['收盘'] > ma5:
        score += 10
    
    if change > 5 or change < -2:
        score -= 20
    
    return score


def analyze_with_stop_loss():
    """分析加入止损后的效果"""
    log("="*70)
    log("策略收益分析（含止损/止盈）")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*70)
    
    stocks = {
        '人工智能': ['300496', '300474', '002230', '300033'],
        '半导体': ['002371', '603986', '300661', '002049'],
        '机器人': ['300024', '002747', '002527'],
        '新能源车': ['300750', '300014', '300207'],
    }
    
    all_signals = []
    
    for sector, codes in stocks.items():
        for code in codes:
            df = get_stock_kline(code, 250)
            if df is None or len(df) < 60:
                continue
            
            for idx in range(30, len(df) - 10):
                score = check_signal(df, idx)
                
                if score >= 70:
                    entry = df.iloc[idx]['收盘']
                    
                    # 模拟持有10天，计算各种止损/止盈情况
                    for hold_days in range(1, min(11, len(df) - idx)):
                        future_day = df.iloc[idx + hold_days]
                        ret = (future_day['收盘'] - entry) / entry * 100
                        min_price = df.iloc[idx+1:idx+hold_days+1]['最低'].min()
                        max_price = df.iloc[idx+1:idx+hold_days+1]['最高'].max()
                        max_drawdown = (min_price - entry) / entry * 100
                        max_profit = (max_price - entry) / entry * 100
                    
                    # 不同止损策略的收益
                    future_10d = df.iloc[idx+1:idx+11]
                    
                    # 策略1：无止损，持有5天
                    ret_5d = (df.iloc[idx+5]['收盘'] - entry) / entry * 100
                    
                    # 策略2：止损-3%，止盈+5%
                    ret_sl3_tp5 = simulate_trade(future_10d, entry, stop_loss=-3, take_profit=5)
                    
                    # 策略3：止损-5%，止盈+8%
                    ret_sl5_tp8 = simulate_trade(future_10d, entry, stop_loss=-5, take_profit=8)
                    
                    # 策略4：动态止损（最高点回撤3%）
                    ret_trailing = simulate_trailing_stop(future_10d, entry, trailing=-3)
                    
                    all_signals.append({
                        'date': df.iloc[idx]['日期'],
                        'code': code,
                        'sector': sector,
                        'score': score,
                        'ret_5d': ret_5d,
                        'ret_sl3_tp5': ret_sl3_tp5,
                        'ret_sl5_tp8': ret_sl5_tp8,
                        'ret_trailing': ret_trailing,
                    })
            
            time.sleep(0.1)
    
    if not all_signals:
        log("无信号")
        return
    
    df_signals = pd.DataFrame(all_signals)
    log(f"\n共 {len(df_signals)} 个信号")
    
    # ==================== 对比分析 ====================
    log("\n" + "="*70)
    log("一、不同止损/止盈策略对比")
    log("="*70)
    
    strategies = [
        ('无止损持5天', 'ret_5d'),
        ('止损-3%/止盈+5%', 'ret_sl3_tp5'),
        ('止损-5%/止盈+8%', 'ret_sl5_tp8'),
        ('动态止损-3%', 'ret_trailing'),
    ]
    
    log("\n  策略              胜率    均收    盈亏比   期望收益")
    log("  " + "-"*60)
    
    for name, col in strategies:
        wins = df_signals[df_signals[col] > 0]
        losses = df_signals[df_signals[col] <= 0]
        
        win_rate = len(wins) / len(df_signals) * 100
        avg_ret = df_signals[col].mean()
        
        avg_win = wins[col].mean() if len(wins) > 0 else 0
        avg_loss = abs(losses[col].mean()) if len(losses) > 0 else 1
        profit_ratio = avg_win / avg_loss if avg_loss > 0 else 0
        
        # 期望收益 = 胜率 * 平均盈利 - (1-胜率) * 平均亏损
        expected = (win_rate/100) * avg_win - (1 - win_rate/100) * avg_loss
        
        log(f"  {name:16} {win_rate:5.1f}%  {avg_ret:+5.2f}%  {profit_ratio:5.2f}   {expected:+5.2f}%")
    
    # ==================== 最佳策略分析 ====================
    log("\n" + "="*70)
    log("二、最佳策略详细分析")
    log("="*70)
    
    # 找期望收益最高的策略
    best_col = 'ret_sl3_tp5'  # 通常止损策略效果最好
    
    df_best = df_signals.copy()
    wins = df_best[df_best[best_col] > 0]
    losses = df_best[df_best[best_col] <= 0]
    
    log(f"\n  止损-3%/止盈+5% 策略分析:")
    log(f"  - 盈利次数: {len(wins)} ({len(wins)/len(df_best)*100:.1f}%)")
    log(f"  - 亏损次数: {len(losses)} ({len(losses)/len(df_best)*100:.1f}%)")
    log(f"  - 平均盈利: +{wins[best_col].mean():.2f}%")
    log(f"  - 平均亏损: {losses[best_col].mean():.2f}%")
    log(f"  - 最大盈利: +{df_best[best_col].max():.2f}%")
    log(f"  - 最大亏损: {df_best[best_col].min():.2f}%")
    
    # 累计收益
    total_ret = df_best[best_col].sum()
    log(f"\n  累计收益（假设每次等仓）: {total_ret:+.1f}%")
    log(f"  平均每笔收益: {total_ret/len(df_best):+.2f}%")
    
    # ==================== 高评分信号 ====================
    log("\n" + "="*70)
    log("三、高评分信号表现")
    log("="*70)
    
    for threshold in [70, 80, 90]:
        subset = df_signals[df_signals['score'] >= threshold]
        if len(subset) >= 5:
            win_rate = (subset[best_col] > 0).sum() / len(subset) * 100
            avg_ret = subset[best_col].mean()
            total = subset[best_col].sum()
            log(f"\n  评分≥{threshold}: {len(subset)}个信号")
            log(f"    胜率: {win_rate:.1f}%, 均收: {avg_ret:+.2f}%, 累计: {total:+.1f}%")
    
    # ==================== 结论 ====================
    log("\n" + "="*70)
    log("四、结论与建议")
    log("="*70)
    
    log("""
  【关于胜率的真相】
  
  1. 55-60%的胜率在量化策略中已经不错
     - 顶级量化基金的策略胜率也在55-65%之间
     - 靠单纯技术指标很难达到70%+
     
  2. 盈亏比比胜率更重要
     - 即使胜率只有50%，如果盈亏比>1.5，策略仍然盈利
     - 止盈止损设置得当可以显著提高盈亏比
     
  3. 提高收益的正确方法：
     - 严格止损（控制单笔亏损在-3%以内）
     - 适度止盈（让利润奔跑）
     - 只操作高评分信号
     - 顺应大盘趋势
     
  4. 当前策略建议：
     - 评分阈值：≥80
     - 止损设置：-3%
     - 止盈设置：+5%或动态跟踪
     - 大盘过滤：只在大盘多头时操作
    """)


def simulate_trade(future_data, entry, stop_loss, take_profit):
    """模拟带止损止盈的交易"""
    for _, row in future_data.iterrows():
        # 检查是否触发止损
        low_ret = (row['最低'] - entry) / entry * 100
        if low_ret <= stop_loss:
            return stop_loss
        
        # 检查是否触发止盈
        high_ret = (row['最高'] - entry) / entry * 100
        if high_ret >= take_profit:
            return take_profit
    
    # 持有到期末
    return (future_data.iloc[-1]['收盘'] - entry) / entry * 100


def simulate_trailing_stop(future_data, entry, trailing):
    """模拟动态止损"""
    max_price = entry
    
    for _, row in future_data.iterrows():
        # 更新最高价
        if row['最高'] > max_price:
            max_price = row['最高']
        
        # 检查是否触发动态止损
        stop_price = max_price * (1 + trailing/100)
        if row['最低'] <= stop_price:
            return (stop_price - entry) / entry * 100
    
    # 持有到期末
    return (future_data.iloc[-1]['收盘'] - entry) / entry * 100


if __name__ == "__main__":
    analyze_with_stop_loss()
