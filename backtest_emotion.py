# -*- coding: utf-8 -*-
"""
情绪周期策略回测
=====================================
核心逻辑：
- 下跌 + 放量 = 还在抛售（骂得凶）
- 下跌 + 缩量 = 卖盘枯竭（沉默底）→ 买入信号
- 上涨 + 放量 = 追涨狂热 → 卖出信号

用成交量变化模拟评论区活跃度
"""
import requests
import pandas as pd
import numpy as np
import os
from datetime import datetime
import time

for key in list(os.environ.keys()):
    if 'proxy' in key.lower():
        del os.environ[key]

session = requests.Session()
session.trust_env = False
session.headers.update({'User-Agent': 'Mozilla/5.0'})


def get_stock_kline(code, days=250):
    code = str(code).zfill(6)
    kcode = f'sh{code}' if code.startswith('6') else f'sz{code}'
    url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={kcode},day,,,{days},qfq'
    try:
        r = session.get(url, timeout=15)
        data = r.json()
        if not data.get('data'):
            return None
        stock_data = data['data'].get(kcode) or data['data'].get(kcode.upper())
        if not stock_data or 'qfqday' not in stock_data:
            return None
        days_data = stock_data['qfqday']
        df = pd.DataFrame([d[:6] for d in days_data], 
                        columns=['date','open','close','high','low','volume'])
        for col in ['open','close','high','low','volume']:
            df[col] = df[col].astype(float)
        df['date'] = pd.to_datetime(df['date'])
        df['change'] = df['close'].pct_change() * 100
        return df
    except Exception as e:
        print(f"获取数据失败: {e}")
        return None


def find_silence_bottom(df, lookback=20):
    """
    寻找沉默底信号
    
    条件：
    1. 近期下跌（5日累计跌幅 < -5%）
    2. 之前放量（前5日平均成交量 > 20日平均的1.3倍）
    3. 现在缩量（当前5日平均成交量 < 前5日平均的0.6倍）
    4. 股价接近近期低点
    
    返回: list of (index, signal_info)
    """
    signals = []
    
    if len(df) < lookback + 10:
        return signals
    
    for i in range(lookback + 5, len(df) - 5):
        # 计算各项指标
        current_price = df.iloc[i]['close']
        
        # 5日累计涨跌
        ret_5d = (df.iloc[i]['close'] - df.iloc[i-5]['close']) / df.iloc[i-5]['close'] * 100
        
        # 10日累计涨跌
        ret_10d = (df.iloc[i]['close'] - df.iloc[i-10]['close']) / df.iloc[i-10]['close'] * 100
        
        # 成交量分析
        vol_20d_avg = df['volume'].iloc[i-20:i].mean()
        vol_prev_5d = df['volume'].iloc[i-10:i-5].mean()  # 前5日（下跌放量期）
        vol_curr_5d = df['volume'].iloc[i-5:i].mean()     # 最近5日（缩量期）
        vol_today = df.iloc[i]['volume']
        
        # 20日最低价
        low_20d = df['low'].iloc[i-20:i+1].min()
        
        # 价格位置（距离20日低点）
        price_pos = (current_price - low_20d) / low_20d * 100 if low_20d > 0 else 0
        
        # 沉默底条件
        cond1 = ret_10d < -8                              # 近期有较大跌幅
        cond2 = vol_prev_5d > vol_20d_avg * 1.2           # 前期放量（恐慌抛售）
        cond3 = vol_curr_5d < vol_prev_5d * 0.65          # 近期缩量（沉默）
        cond4 = price_pos < 5                             # 接近低点
        cond5 = ret_5d > -3                               # 最近5日止跌企稳
        
        if cond1 and cond2 and cond3 and cond4 and cond5:
            signals.append({
                'index': i,
                'date': df.iloc[i]['date'],
                'price': current_price,
                'ret_10d': ret_10d,
                'vol_shrink': vol_curr_5d / vol_prev_5d,
                'type': 'silence_bottom',
            })
    
    return signals


def find_euphoria_top(df, lookback=20):
    """
    寻找狂热顶信号
    
    条件：
    1. 近期大涨（10日累计涨幅 > 15%）
    2. 成交量激增（当前5日平均 > 20日平均的1.8倍）
    3. 股价接近近期高点
    
    返回: list of (index, signal_info)
    """
    signals = []
    
    if len(df) < lookback + 10:
        return signals
    
    for i in range(lookback + 5, len(df) - 5):
        current_price = df.iloc[i]['close']
        
        # 10日累计涨跌
        ret_10d = (df.iloc[i]['close'] - df.iloc[i-10]['close']) / df.iloc[i-10]['close'] * 100
        
        # 成交量分析
        vol_20d_avg = df['volume'].iloc[i-20:i].mean()
        vol_curr_5d = df['volume'].iloc[i-5:i].mean()
        
        # 20日最高价
        high_20d = df['high'].iloc[i-20:i+1].max()
        
        # 价格位置
        price_pos = (current_price - df['low'].iloc[i-20:i+1].min()) / (high_20d - df['low'].iloc[i-20:i+1].min()) * 100 if high_20d > df['low'].iloc[i-20:i+1].min() else 50
        
        # 狂热顶条件
        cond1 = ret_10d > 15                              # 近期大涨
        cond2 = vol_curr_5d > vol_20d_avg * 1.8           # 成交量激增
        cond3 = price_pos > 90                            # 接近高点
        
        if cond1 and cond2 and cond3:
            signals.append({
                'index': i,
                'date': df.iloc[i]['date'],
                'price': current_price,
                'ret_10d': ret_10d,
                'vol_ratio': vol_curr_5d / vol_20d_avg,
                'type': 'euphoria_top',
            })
    
    return signals


def backtest_signals(df, signals, hold_days=5):
    """
    回测信号表现
    
    参数:
        df: 价格数据
        signals: 信号列表
        hold_days: 持有天数
    
    返回:
        dict: 回测结果
    """
    results = []
    
    for sig in signals:
        idx = sig['index']
        
        if idx + hold_days >= len(df):
            continue
        
        entry_price = sig['price']
        
        # 计算不同持有期的收益
        returns = {}
        for days in [1, 3, 5, 10]:
            if idx + days < len(df):
                exit_price = df.iloc[idx + days]['close']
                ret = (exit_price - entry_price) / entry_price * 100
                returns[f'ret_{days}d'] = ret
        
        # 最大回撤和最大盈利
        if idx + 10 < len(df):
            future_prices = df['close'].iloc[idx:idx+11].values
            future_highs = df['high'].iloc[idx:idx+11].values
            future_lows = df['low'].iloc[idx:idx+11].values
            
            max_gain = (max(future_highs) - entry_price) / entry_price * 100
            max_loss = (min(future_lows) - entry_price) / entry_price * 100
        else:
            max_gain = 0
            max_loss = 0
        
        results.append({
            **sig,
            **returns,
            'max_gain': max_gain,
            'max_loss': max_loss,
        })
    
    return results


def analyze_results(results, signal_type):
    """分析回测结果"""
    if not results:
        return None
    
    df = pd.DataFrame(results)
    
    # 过滤指定类型
    df = df[df['type'] == signal_type]
    
    if len(df) == 0:
        return None
    
    # 统计
    stats = {
        'total_signals': len(df),
    }
    
    for days in [1, 3, 5, 10]:
        col = f'ret_{days}d'
        if col in df.columns:
            valid = df[col].dropna()
            if len(valid) > 0:
                stats[f'win_rate_{days}d'] = (valid > 0).sum() / len(valid) * 100
                stats[f'avg_ret_{days}d'] = valid.mean()
                stats[f'median_ret_{days}d'] = valid.median()
    
    if 'max_gain' in df.columns:
        stats['avg_max_gain'] = df['max_gain'].mean()
        stats['avg_max_loss'] = df['max_loss'].mean()
    
    return stats


def run_backtest():
    """运行回测"""
    print("="*70)
    print("情绪周期策略回测")
    print("="*70)
    print("\n策略逻辑:")
    print("  沉默底: 下跌放量后 → 缩量企稳 = 卖盘枯竭 = 买入")
    print("  狂热顶: 上涨 + 放量激增 = 追涨狂热 = 卖出")
    print()
    
    # 测试股票池
    stocks = [
        ('002230', '科大讯飞'),
        ('002371', '北方华创'),
        ('002594', '比亚迪'),
        ('600519', '贵州茅台'),
        ('000858', '五粮液'),
        ('002415', '海康威视'),
        ('300750', '宁德时代'),
        ('002475', '立讯精密'),
        ('601012', '隆基绿能'),
        ('000538', '云南白药'),
    ]
    
    all_silence_results = []
    all_euphoria_results = []
    
    for code, name in stocks:
        print(f"\n分析: {code} {name}")
        
        df = get_stock_kline(code, 500)
        if df is None or len(df) < 100:
            print(f"  数据不足")
            continue
        
        # 寻找信号
        silence_signals = find_silence_bottom(df)
        euphoria_signals = find_euphoria_top(df)
        
        print(f"  沉默底信号: {len(silence_signals)}个")
        print(f"  狂热顶信号: {len(euphoria_signals)}个")
        
        # 回测
        if silence_signals:
            results = backtest_signals(df, silence_signals)
            for r in results:
                r['stock'] = f"{code} {name}"
            all_silence_results.extend(results)
        
        if euphoria_signals:
            results = backtest_signals(df, euphoria_signals)
            for r in results:
                r['stock'] = f"{code} {name}"
            all_euphoria_results.extend(results)
        
        time.sleep(0.2)
    
    # 汇总分析
    print("\n" + "="*70)
    print("沉默底策略回测结果（买入信号）")
    print("="*70)
    
    if all_silence_results:
        stats = analyze_results(all_silence_results, 'silence_bottom')
        if stats:
            print(f"\n总信号数: {stats['total_signals']}")
            print(f"\n持有期胜率和收益:")
            for days in [1, 3, 5, 10]:
                wr = stats.get(f'win_rate_{days}d', 0)
                avg = stats.get(f'avg_ret_{days}d', 0)
                print(f"  {days}日: 胜率 {wr:.1f}%, 平均收益 {avg:+.2f}%")
            
            print(f"\n风险收益:")
            print(f"  平均最大盈利: {stats.get('avg_max_gain', 0):+.2f}%")
            print(f"  平均最大回撤: {stats.get('avg_max_loss', 0):+.2f}%")
            
            # 显示一些具体案例
            print(f"\n近期信号案例:")
            recent = sorted(all_silence_results, key=lambda x: x['date'], reverse=True)[:5]
            for r in recent:
                print(f"  {r['date'].strftime('%Y-%m-%d')} {r['stock']}")
                print(f"    价格:{r['price']:.2f}, 缩量比:{r['vol_shrink']:.2f}")
                ret5 = r.get('ret_5d', 0)
                print(f"    5日收益: {ret5:+.2f}%")
    else:
        print("无沉默底信号")
    
    print("\n" + "="*70)
    print("狂热顶策略回测结果（卖出信号）")
    print("="*70)
    
    if all_euphoria_results:
        stats = analyze_results(all_euphoria_results, 'euphoria_top')
        if stats:
            print(f"\n总信号数: {stats['total_signals']}")
            print(f"\n持有期收益（负值表示策略正确，应该卖出）:")
            for days in [1, 3, 5, 10]:
                wr = stats.get(f'win_rate_{days}d', 0)
                avg = stats.get(f'avg_ret_{days}d', 0)
                # 对于卖出信号，后续下跌才是正确的
                sell_correct = 100 - wr
                print(f"  {days}日: 卖出正确率 {sell_correct:.1f}%, 平均跌幅 {avg:+.2f}%")
            
            print(f"\n近期信号案例:")
            recent = sorted(all_euphoria_results, key=lambda x: x['date'], reverse=True)[:5]
            for r in recent:
                print(f"  {r['date'].strftime('%Y-%m-%d')} {r['stock']}")
                print(f"    价格:{r['price']:.2f}, 放量比:{r['vol_ratio']:.2f}")
                ret5 = r.get('ret_5d', 0)
                print(f"    5日后走势: {ret5:+.2f}%")
    else:
        print("无狂热顶信号")
    
    # 策略总结
    print("\n" + "="*70)
    print("策略总结")
    print("="*70)
    
    if all_silence_results:
        silence_stats = analyze_results(all_silence_results, 'silence_bottom')
        if silence_stats:
            wr5 = silence_stats.get('win_rate_5d', 0)
            avg5 = silence_stats.get('avg_ret_5d', 0)
            print(f"\n沉默底（买入）:")
            print(f"  5日胜率: {wr5:.1f}%")
            print(f"  5日平均收益: {avg5:+.2f}%")
            
            if wr5 > 55:
                print(f"  评价: 有效策略，可以使用")
            elif wr5 > 50:
                print(f"  评价: 边际有效，需配合其他指标")
            else:
                print(f"  评价: 效果一般，需优化条件")
    
    if all_euphoria_results:
        euphoria_stats = analyze_results(all_euphoria_results, 'euphoria_top')
        if euphoria_stats:
            avg5 = euphoria_stats.get('avg_ret_5d', 0)
            print(f"\n狂热顶（卖出）:")
            print(f"  5日后平均跌幅: {avg5:+.2f}%")
            
            if avg5 < -2:
                print(f"  评价: 有效卖出信号")
            elif avg5 < 0:
                print(f"  评价: 边际有效")
            else:
                print(f"  评价: 不是好的卖出信号")


if __name__ == "__main__":
    run_backtest()
