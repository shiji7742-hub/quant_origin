"""妖股震荡低吸策略 - 参数优化回测
策略逻辑：
1. 找到短期暴涨的妖股（有连板、涨幅大）
2. 等待回调进入震荡区间
3. 在震荡区间低点买入

回测参数：
- 回调幅度：20%, 30%, 40%, 50%
- 震荡天数：5, 10, 15, 20天
- 低点定义：区间最低价附近3%, 5%, 8%
"""
import akshare as ak
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
import threading
import time
import json

# 回测参数组合（精简版，加快测试）
PULLBACK_RATIOS = [0.30, 0.40]  # 回调幅度
CONSOLIDATION_DAYS = [10, 15]  # 震荡天数
LOW_THRESHOLDS = [0.05]  # 低点阈值（距离区间低点的百分比）

# 持有期收益计算
HOLD_DAYS = [3, 5, 10, 20]  # 持有天数


def get_all_stocks():
    """获取所有A股主板股票"""
    print("获取A股列表...")
    df = ak.stock_zh_a_spot_em()
    df = df[df['代码'].str.match(r'^(60|00)')]
    df = df[~df['名称'].str.contains('ST')]
    df = df[df['最新价'].notna() & (df['最新价'] > 0)]
    print(f"共 {len(df)} 只主板股票")
    return df[['代码', '名称']].to_dict('records')


def is_monster_stock(df, idx):
    """
    判断是否是妖股（短期暴涨）
    条件：
    1. 20天内涨幅超过50%（2-4倍的起点）
    2. 有连板（至少2个涨停）
    3. 或者单日涨幅超过15%的异动
    """
    if idx < 20:
        return False, None
    
    # 计算20天涨幅
    start_price = df.iloc[idx - 20]['收盘']
    peak_price = df.iloc[idx]['收盘']
    gain_20d = (peak_price - start_price) / start_price
    
    if gain_20d < 0.5:  # 20天涨幅不足50%
        return False, None
    
    # 检查是否有连板或大涨
    limit_up_count = 0
    big_gain_count = 0
    
    for i in range(idx - 20, idx + 1):
        if i <= 0:
            continue
        prev_close = df.iloc[i - 1]['收盘']
        curr_close = df.iloc[i]['收盘']
        daily_gain = (curr_close - prev_close) / prev_close
        
        if daily_gain >= 0.095:  # 涨停
            limit_up_count += 1
        if daily_gain >= 0.15:  # 大涨
            big_gain_count += 1
    
    # 至少2个涨停或1次大涨
    is_monster = limit_up_count >= 2 or big_gain_count >= 1
    
    if is_monster:
        return True, {
            '20日涨幅': round(gain_20d * 100, 1),
            '涨停次数': limit_up_count,
            '大涨次数': big_gain_count,
            '高点价格': peak_price
        }
    return False, None


def find_consolidation_zone(df, peak_idx, pullback_ratio, consolidation_days):
    """
    找到震荡区间
    1. 从高点回调指定幅度
    2. 在低位横盘指定天数
    返回：震荡区间的高点和低点
    """
    if peak_idx + consolidation_days + 10 >= len(df):
        return None
    
    peak_price = df.iloc[peak_idx]['收盘']
    target_low = peak_price * (1 - pullback_ratio)
    
    # 找到回调到位的点
    pullback_idx = None
    for i in range(peak_idx + 1, min(peak_idx + 60, len(df))):
        if df.iloc[i]['最低'] <= target_low:
            pullback_idx = i
            break
    
    if pullback_idx is None:
        return None
    
    # 检查是否形成震荡区间
    zone_start = pullback_idx
    zone_end = min(zone_start + consolidation_days, len(df) - 1)
    
    if zone_end - zone_start < consolidation_days - 2:
        return None
    
    zone_data = df.iloc[zone_start:zone_end + 1]
    zone_high = zone_data['最高'].max()
    zone_low = zone_data['最低'].min()
    
    # 震荡幅度不能太大（<20%），否则不算横盘
    zone_range = (zone_high - zone_low) / zone_low
    if zone_range > 0.20:
        return None
    
    return {
        'zone_start': zone_start,
        'zone_end': zone_end,
        'zone_high': zone_high,
        'zone_low': zone_low,
        'zone_range': zone_range
    }


def find_buy_signals(df, zone_info, low_threshold):
    """
    在震荡区间内找买入信号
    条件：价格接近区间低点
    """
    signals = []
    zone_low = zone_info['zone_low']
    buy_threshold = zone_low * (1 + low_threshold)
    
    # 在震荡区间结束后寻找买点
    for i in range(zone_info['zone_end'], min(zone_info['zone_end'] + 30, len(df))):
        row = df.iloc[i]
        # 价格触及低点附近
        if row['最低'] <= buy_threshold:
            signals.append({
                'buy_idx': i,
                'buy_date': row.get('日期', ''),
                'buy_price': row['收盘'],  # 以收盘价买入
                'zone_low': zone_low
            })
    
    return signals


def calculate_returns(df, buy_idx, hold_days_list):
    """计算不同持有期的收益"""
    returns = {}
    buy_price = df.iloc[buy_idx]['收盘']
    
    for days in hold_days_list:
        sell_idx = buy_idx + days
        if sell_idx < len(df):
            sell_price = df.iloc[sell_idx]['收盘']
            ret = (sell_price - buy_price) / buy_price * 100
            returns[f'{days}日收益'] = round(ret, 2)
        else:
            returns[f'{days}日收益'] = None
    
    # 计算最大回撤
    max_drawdown = 0
    for i in range(buy_idx + 1, min(buy_idx + 20, len(df))):
        low = df.iloc[i]['最低']
        dd = (low - buy_price) / buy_price * 100
        if dd < max_drawdown:
            max_drawdown = dd
    returns['最大回撤'] = round(max_drawdown, 2)
    
    return returns


def backtest_single_stock(symbol, name, params):
    """对单只股票进行回测"""
    try:
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily",
                                start_date="20240101", end_date="20260115", adjust="qfq")
        if df is None or len(df) < 100:
            return []
        
        df = df.reset_index(drop=True)
        results = []
        
        pullback_ratio = params['pullback_ratio']
        consolidation_days = params['consolidation_days']
        low_threshold = params['low_threshold']
        
        # 遍历寻找妖股高点
        for i in range(30, len(df) - 60):
            is_monster, monster_info = is_monster_stock(df, i)
            if not is_monster:
                continue
            
            # 确认是阶段高点（后5天没有更高）
            is_peak = True
            for j in range(i + 1, min(i + 6, len(df))):
                if df.iloc[j]['最高'] > df.iloc[i]['最高'] * 1.02:
                    is_peak = False
                    break
            
            if not is_peak:
                continue
            
            # 找震荡区间
            zone_info = find_consolidation_zone(df, i, pullback_ratio, consolidation_days)
            if zone_info is None:
                continue
            
            # 找买入信号
            signals = find_buy_signals(df, zone_info, low_threshold)
            
            for signal in signals:
                returns = calculate_returns(df, signal['buy_idx'], HOLD_DAYS)
                
                results.append({
                    '代码': symbol,
                    '名称': name,
                    '高点日期': df.iloc[i].get('日期', ''),
                    '高点价格': round(df.iloc[i]['收盘'], 2),
                    '20日涨幅': monster_info['20日涨幅'],
                    '涨停次数': monster_info['涨停次数'],
                    '买入日期': signal['buy_date'],
                    '买入价格': round(signal['buy_price'], 2),
                    '区间低点': round(signal['zone_low'], 2),
                    '回调幅度': pullback_ratio,
                    '震荡天数': consolidation_days,
                    '低点阈值': low_threshold,
                    **returns
                })
        
        return results
    except Exception as e:
        return []


class ProgressCounter:
    def __init__(self, total):
        self.completed = 0
        self.total = total
        self.lock = threading.Lock()
    
    def increment(self):
        with self.lock:
            self.completed += 1
            return self.completed


def run_backtest(params, stocks, max_workers=10):
    """运行单组参数的回测"""
    all_results = []
    counter = ProgressCounter(len(stocks))
    results_lock = threading.Lock()
    
    def worker(stock):
        results = backtest_single_stock(stock['代码'], stock['名称'], params)
        completed = counter.increment()
        
        if results:
            with results_lock:
                all_results.extend(results)
        
        return results
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(worker, stock) for stock in stocks]
        for future in as_completed(futures):
            pass
    
    return all_results


def analyze_results(results):
    """分析回测结果"""
    if not results:
        return None
    
    df = pd.DataFrame(results)
    
    analysis = {
        '样本数': len(df),
        '3日胜率': (df['3日收益'] > 0).mean() * 100 if '3日收益' in df else 0,
        '5日胜率': (df['5日收益'] > 0).mean() * 100 if '5日收益' in df else 0,
        '10日胜率': (df['10日收益'] > 0).mean() * 100 if '10日收益' in df else 0,
        '20日胜率': (df['20日收益'] > 0).mean() * 100 if '20日收益' in df else 0,
        '3日平均收益': df['3日收益'].mean() if '3日收益' in df else 0,
        '5日平均收益': df['5日收益'].mean() if '5日收益' in df else 0,
        '10日平均收益': df['10日收益'].mean() if '10日收益' in df else 0,
        '20日平均收益': df['20日收益'].mean() if '20日收益' in df else 0,
        '平均最大回撤': df['最大回撤'].mean() if '最大回撤' in df else 0,
    }
    
    return analysis


def main():
    """主函数：遍历所有参数组合进行回测"""
    print("=" * 70)
    print("妖股震荡低吸策略 - 参数优化回测")
    print("=" * 70)
    
    stocks = get_all_stocks()
    # 采样加快测试速度
    import random
    random.seed(42)
    stocks = random.sample(stocks, min(300, len(stocks)))
    print(f"采样 {len(stocks)} 只股票进行回测")
    
    all_param_results = []
    total_combinations = len(PULLBACK_RATIOS) * len(CONSOLIDATION_DAYS) * len(LOW_THRESHOLDS)
    current = 0
    
    print(f"\n共 {total_combinations} 种参数组合需要测试")
    print("-" * 70)
    
    start_time = time.time()
    
    for pullback in PULLBACK_RATIOS:
        for cons_days in CONSOLIDATION_DAYS:
            for low_thresh in LOW_THRESHOLDS:
                current += 1
                params = {
                    'pullback_ratio': pullback,
                    'consolidation_days': cons_days,
                    'low_threshold': low_thresh
                }
                
                print(f"\n[{current}/{total_combinations}] 测试参数: 回调{int(pullback*100)}%, 震荡{cons_days}天, 低点阈值{int(low_thresh*100)}%")
                
                results = run_backtest(params, stocks, max_workers=15)
                analysis = analyze_results(results)
                
                if analysis and analysis['样本数'] >= 10:
                    param_result = {
                        '回调幅度': f"{int(pullback*100)}%",
                        '震荡天数': cons_days,
                        '低点阈值': f"{int(low_thresh*100)}%",
                        **analysis
                    }
                    all_param_results.append(param_result)
                    
                    print(f"   样本数: {analysis['样本数']}")
                    print(f"   5日胜率: {analysis['5日胜率']:.1f}%, 平均收益: {analysis['5日平均收益']:.2f}%")
                    print(f"   10日胜率: {analysis['10日胜率']:.1f}%, 平均收益: {analysis['10日平均收益']:.2f}%")
                else:
                    print(f"   样本数不足，跳过")
    
    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print(f"回测完成！耗时 {elapsed/60:.1f} 分钟")
    print("=" * 70)
    
    # 保存结果
    if all_param_results:
        result_df = pd.DataFrame(all_param_results)
        
        # 按5日平均收益排序
        result_df = result_df.sort_values('5日平均收益', ascending=False)
        
        # 保存到Excel
        filename = f"妖股策略参数优化_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        result_df.to_excel(filename, index=False)
        print(f"\n结果已保存到: {filename}")
        
        # 打印最优参数
        print("\n" + "=" * 70)
        print("最优参数组合 TOP 5（按5日平均收益排序）:")
        print("-" * 70)
        for i, row in result_df.head(5).iterrows():
            print(f"\n参数: 回调{row['回调幅度']}, 震荡{row['震荡天数']}天, 低点阈值{row['低点阈值']}")
            print(f"  样本数: {row['样本数']}")
            print(f"  5日: 胜率{row['5日胜率']:.1f}%, 收益{row['5日平均收益']:.2f}%")
            print(f"  10日: 胜率{row['10日胜率']:.1f}%, 收益{row['10日平均收益']:.2f}%")
            print(f"  最大回撤: {row['平均最大回撤']:.2f}%")
        
        # 保存详细JSON
        json_file = f"妖股策略参数优化_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(all_param_results, f, ensure_ascii=False, indent=2)
        print(f"\n详细数据已保存到: {json_file}")
    
    return all_param_results


if __name__ == "__main__":
    main()
