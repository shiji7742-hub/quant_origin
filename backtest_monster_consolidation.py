"""妖股震荡低吸策略 - 历史回测
回测逻辑：
1. 找到历史上的妖股（连板或短期暴涨）
2. 找到回调后形成震荡区间的时点
3. 在触及区间低点时模拟买入
4. 统计后续收益（5日、10日、20日）
"""
import akshare as ak
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import threading
import time
import sys
import warnings
warnings.filterwarnings('ignore')


def get_all_stocks():
    """获取所有A股主板股票"""
    print("获取A股列表...")
    df = ak.stock_zh_a_spot_em()
    df = df[df['代码'].str.match(r'^(60|00)')]
    df = df[~df['名称'].str.contains('ST')]
    df = df[df['最新价'].notna() & (df['最新价'] > 0)]
    print(f"共 {len(df)} 只有效主板股票")
    return df[['代码', '名称']].to_dict('records')


def backtest_single_stock(symbol, name):
    """回测单只股票的妖股震荡低吸策略"""
    try:
        # 获取2024年1月到2025年12月的数据
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", 
                                start_date="20240101", end_date="20251231", adjust="qfq")
        if df is None or len(df) < 100:
            return []
        
        df = df.reset_index(drop=True)
        df['日期'] = pd.to_datetime(df['日期'])
        
        trades = []
        
        # 遍历查找连板
        for i in range(60, len(df) - 25):  # 留出前60天找连板，后25天计算收益
            # 检查是否有连板
            consecutive = find_consecutive_limit_at(df, i)
            if consecutive < 2:
                continue
            
            # 找到连板结束后的高点
            limit_end_idx = i + consecutive - 1
            if limit_end_idx + 30 >= len(df):
                continue
            
            # 找高点
            search_end = min(limit_end_idx + 30, len(df) - 20)
            high_idx = df.loc[limit_end_idx:search_end, '最高'].idxmax()
            high_price = df.loc[high_idx, '最高']
            
            # 高点后找震荡区间
            consolidation = find_consolidation_after_high(df, high_idx)
            if not consolidation:
                continue
            
            # 找到触及区间低点的买入信号
            signal_idx = consolidation['signal_idx']
            if signal_idx + 20 >= len(df):
                continue
            
            buy_price = df.loc[signal_idx, '收盘']
            buy_date = df.loc[signal_idx, '日期']
            
            # 计算后续收益
            ret_5d = (df.loc[signal_idx + 5, '收盘'] - buy_price) / buy_price * 100
            ret_10d = (df.loc[signal_idx + 10, '收盘'] - buy_price) / buy_price * 100
            ret_20d = (df.loc[signal_idx + 20, '收盘'] - buy_price) / buy_price * 100
            
            # 计算最大回撤和最大收益
            future_20d = df.loc[signal_idx:signal_idx+20]
            max_gain = (future_20d['最高'].max() - buy_price) / buy_price * 100
            max_drawdown = (future_20d['最低'].min() - buy_price) / buy_price * 100
            
            trades.append({
                '代码': symbol,
                '名称': name,
                '连板数': consecutive,
                '买入日期': buy_date.strftime('%Y-%m-%d'),
                '买入价': round(buy_price, 2),
                '区间下沿': round(consolidation['zone_low'], 2),
                '区间上沿': round(consolidation['zone_high'], 2),
                '5日收益%': round(ret_5d, 2),
                '10日收益%': round(ret_10d, 2),
                '20日收益%': round(ret_20d, 2),
                '最大收益%': round(max_gain, 2),
                '最大回撤%': round(max_drawdown, 2),
            })
        
        return trades
    except Exception as e:
        return []


def find_consecutive_limit_at(df, idx):
    """检查从idx开始是否有连板"""
    if idx < 1 or idx >= len(df):
        return 0
    
    prev_close = df.iloc[idx-1]['收盘']
    curr_close = df.iloc[idx]['收盘']
    gain = (curr_close - prev_close) / prev_close * 100
    
    if gain < 9.5:
        return 0
    
    consecutive = 1
    for j in range(idx + 1, min(idx + 15, len(df))):
        prev = df.iloc[j-1]['收盘']
        curr = df.iloc[j]['收盘']
        g = (curr - prev) / prev * 100
        if g >= 9.5:
            consecutive += 1
        else:
            break
    
    return consecutive


def find_consolidation_after_high(df, high_idx):
    """在高点后找震荡区间和买入信号"""
    if high_idx + 25 >= len(df):
        return None
    
    # 从高点后10天开始找震荡区间
    for start in range(high_idx + 5, min(high_idx + 30, len(df) - 20)):
        # 检查10-15天的震荡区间
        for days in [10, 15]:
            if start + days >= len(df) - 20:
                continue
            
            window = df.loc[start:start+days-1]
            zone_high = window['最高'].max()
            zone_low = window['最低'].min()
            zone_range = (zone_high - zone_low) / zone_low * 100
            
            # 震荡区间振幅 < 15%
            if zone_range >= 15:
                continue
            
            # 找触及区间低点的信号（收盘价距下沿<3%）
            for sig_idx in range(start + days, min(start + days + 10, len(df) - 20)):
                close = df.loc[sig_idx, '收盘']
                dist_to_low = (close - zone_low) / zone_low * 100
                
                if dist_to_low < 3:
                    return {
                        'zone_high': zone_high,
                        'zone_low': zone_low,
                        'signal_idx': sig_idx
                    }
    
    return None


def run_backtest(max_workers=15, max_stocks=None):
    """运行回测"""
    stocks = get_all_stocks()
    if max_stocks:
        stocks = stocks[:max_stocks]
    
    total = len(stocks)
    print(f"\n开始回测，使用 {max_workers} 个线程...")
    print("回测时间范围: 2024年1月 - 2025年12月")
    print("=" * 60)
    
    start_time = time.time()
    all_trades = []
    completed = 0
    lock = threading.Lock()
    
    def worker(stock):
        nonlocal completed
        trades = backtest_single_stock(stock['代码'], stock['名称'])
        
        with lock:
            completed += 1
            if trades:
                all_trades.extend(trades)
                for t in trades:
                    print(f"[{completed}/{total}] ✓ {t['名称']} {t['连板数']}连板 买入:{t['买入日期']} 20日收益:{t['20日收益%']}%")
                    sys.stdout.flush()
            elif completed % 300 == 0:
                print(f"[{completed}/{total}] 进度 {completed/total*100:.1f}%")
                sys.stdout.flush()
        
        return trades
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(worker, stock) for stock in stocks]
        for future in as_completed(futures):
            pass
    
    elapsed = time.time() - start_time
    print("=" * 60)
    print(f"回测完成! 耗时 {elapsed:.1f}秒, 共 {len(all_trades)} 笔交易")
    
    return all_trades


def analyze_results(trades):
    """分析回测结果"""
    if not trades:
        print("没有交易记录")
        return None
    
    df = pd.DataFrame(trades)
    
    print("\n" + "=" * 60)
    print("【妖股震荡低吸策略 - 回测报告】")
    print("=" * 60)
    
    print(f"\n总交易次数: {len(df)}")
    
    # 收益统计
    print("\n【收益统计】")
    for period in ['5日收益%', '10日收益%', '20日收益%']:
        mean_ret = df[period].mean()
        median_ret = df[period].median()
        win_rate = (df[period] > 0).sum() / len(df) * 100
        print(f"  {period}: 平均{mean_ret:.2f}%, 中位数{median_ret:.2f}%, 胜率{win_rate:.1f}%")
    
    # 最大收益和回撤
    print(f"\n【风险收益】")
    print(f"  平均最大收益: {df['最大收益%'].mean():.2f}%")
    print(f"  平均最大回撤: {df['最大回撤%'].mean():.2f}%")
    print(f"  盈亏比(20日): {df[df['20日收益%']>0]['20日收益%'].mean() / abs(df[df['20日收益%']<0]['20日收益%'].mean()):.2f}")
    
    # 按连板数分组
    print("\n【按连板数分组】")
    for n in sorted(df['连板数'].unique()):
        sub = df[df['连板数'] == n]
        if len(sub) >= 3:
            print(f"  {n}连板: {len(sub)}笔, 20日平均收益{sub['20日收益%'].mean():.2f}%, 胜率{(sub['20日收益%']>0).sum()/len(sub)*100:.1f}%")
    
    # 按月份分组
    df['月份'] = pd.to_datetime(df['买入日期']).dt.to_period('M')
    print("\n【按月份分组】")
    monthly = df.groupby('月份').agg({
        '20日收益%': ['count', 'mean'],
    })
    monthly.columns = ['交易数', '平均收益']
    for idx, row in monthly.iterrows():
        if row['交易数'] >= 2:
            print(f"  {idx}: {int(row['交易数'])}笔, 平均收益{row['平均收益']:.2f}%")
    
    # 最佳和最差交易
    print("\n【最佳交易 TOP5】")
    best = df.nlargest(5, '20日收益%')
    for _, row in best.iterrows():
        print(f"  {row['名称']}({row['代码']}) {row['买入日期']} {row['连板数']}连板 -> {row['20日收益%']}%")
    
    print("\n【最差交易 TOP5】")
    worst = df.nsmallest(5, '20日收益%')
    for _, row in worst.iterrows():
        print(f"  {row['名称']}({row['代码']}) {row['买入日期']} {row['连板数']}连板 -> {row['20日收益%']}%")
    
    return df


def save_results(trades, df_analysis):
    """保存结果"""
    if not trades:
        return
    
    df = pd.DataFrame(trades)
    df = df.sort_values('买入日期', ascending=False)
    
    filename = f"妖股震荡低吸_回测_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='交易明细')
        
        # 汇总统计
        summary = pd.DataFrame({
            '指标': ['总交易数', '5日胜率', '10日胜率', '20日胜率', 
                    '5日平均收益', '10日平均收益', '20日平均收益',
                    '平均最大收益', '平均最大回撤'],
            '数值': [
                len(df),
                f"{(df['5日收益%']>0).sum()/len(df)*100:.1f}%",
                f"{(df['10日收益%']>0).sum()/len(df)*100:.1f}%",
                f"{(df['20日收益%']>0).sum()/len(df)*100:.1f}%",
                f"{df['5日收益%'].mean():.2f}%",
                f"{df['10日收益%'].mean():.2f}%",
                f"{df['20日收益%'].mean():.2f}%",
                f"{df['最大收益%'].mean():.2f}%",
                f"{df['最大回撤%'].mean():.2f}%",
            ]
        })
        summary.to_excel(writer, index=False, sheet_name='汇总统计')
    
    print(f"\n结果已保存到: {filename}")


if __name__ == "__main__":
    trades = run_backtest(max_workers=15)
    df = analyze_results(trades)
    save_results(trades, df)
