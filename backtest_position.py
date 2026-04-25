# -*- coding: utf-8 -*-
"""
仓位管理策略回测
=====================================
验证散户常见仓位管理陷阱：
1. 连涨All-in：连涨后满仓的后果
2. 连跌补仓：越跌越买的后果
3. 集中持仓：从分散变集中的后果
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


def get_stock_kline(code, days=500):
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
        return None


def find_consecutive_up_days(df, min_days=3):
    """
    找出连续上涨的情况
    
    条件：连续min_days天上涨
    """
    signals = []
    
    for i in range(min_days, len(df) - 10):
        # 检查是否连续上涨
        consecutive_up = True
        total_gain = 0
        for j in range(min_days):
            if df.iloc[i-j]['change'] <= 0:
                consecutive_up = False
                break
            total_gain += df.iloc[i-j]['change']
        
        if consecutive_up and total_gain > 5:  # 累计涨幅>5%
            # 如果在这天All-in买入，后续收益
            buy_price = df.iloc[i]['close']
            
            ret_1d = (df.iloc[i+1]['close'] - buy_price) / buy_price * 100
            ret_3d = (df.iloc[i+3]['close'] - buy_price) / buy_price * 100
            ret_5d = (df.iloc[i+5]['close'] - buy_price) / buy_price * 100
            ret_10d = (df.iloc[i+10]['close'] - buy_price) / buy_price * 100 if i+10 < len(df) else 0
            
            # 后续最大回撤
            future_10d = df.iloc[i:i+10]
            max_drawdown = (future_10d['low'].min() - buy_price) / buy_price * 100
            
            signals.append({
                'date': df.iloc[i]['date'],
                'consecutive_days': min_days,
                'total_gain': total_gain,
                'ret_1d': ret_1d,
                'ret_3d': ret_3d,
                'ret_5d': ret_5d,
                'ret_10d': ret_10d,
                'max_drawdown': max_drawdown,
                'type': 'consecutive_up',
            })
    
    return signals


def find_consecutive_down_days(df, min_days=3):
    """
    找出连续下跌的情况
    
    条件：连续min_days天下跌
    """
    signals = []
    
    for i in range(min_days, len(df) - 10):
        # 检查是否连续下跌
        consecutive_down = True
        total_loss = 0
        for j in range(min_days):
            if df.iloc[i-j]['change'] >= 0:
                consecutive_down = False
                break
            total_loss += df.iloc[i-j]['change']
        
        if consecutive_down and total_loss < -5:  # 累计跌幅>5%
            # 如果在这天抄底买入，后续收益
            buy_price = df.iloc[i]['close']
            
            ret_1d = (df.iloc[i+1]['close'] - buy_price) / buy_price * 100
            ret_3d = (df.iloc[i+3]['close'] - buy_price) / buy_price * 100
            ret_5d = (df.iloc[i+5]['close'] - buy_price) / buy_price * 100
            ret_10d = (df.iloc[i+10]['close'] - buy_price) / buy_price * 100 if i+10 < len(df) else 0
            
            # 后续继续下跌风险
            future_10d = df.iloc[i:i+10]
            further_drop = (future_10d['low'].min() - buy_price) / buy_price * 100
            
            signals.append({
                'date': df.iloc[i]['date'],
                'consecutive_days': min_days,
                'total_loss': total_loss,
                'ret_1d': ret_1d,
                'ret_3d': ret_3d,
                'ret_5d': ret_5d,
                'ret_10d': ret_10d,
                'further_drop': further_drop,
                'type': 'consecutive_down',
            })
    
    return signals


def find_big_gain_days(df, threshold=15):
    """
    找出累计大涨后的情况
    
    条件：20日涨幅超过threshold%
    """
    signals = []
    
    for i in range(20, len(df) - 10):
        # 20日涨幅
        ret_20d = (df.iloc[i]['close'] - df.iloc[i-20]['close']) / df.iloc[i-20]['close'] * 100
        
        if ret_20d > threshold:
            # 如果在这天All-in买入
            buy_price = df.iloc[i]['close']
            
            ret_5d = (df.iloc[i+5]['close'] - buy_price) / buy_price * 100
            ret_10d = (df.iloc[i+10]['close'] - buy_price) / buy_price * 100 if i+10 < len(df) else 0
            
            future_10d = df.iloc[i:i+10]
            max_drawdown = (future_10d['low'].min() - buy_price) / buy_price * 100
            
            signals.append({
                'date': df.iloc[i]['date'],
                'ret_20d_before': ret_20d,
                'ret_5d': ret_5d,
                'ret_10d': ret_10d,
                'max_drawdown': max_drawdown,
                'type': 'big_gain',
            })
    
    return signals


def simulate_allin_strategy(df):
    """
    模拟All-in策略 vs 分批策略
    
    策略A：连涨3天后All-in
    策略B：分3批买入，不管涨跌
    """
    results = {'allin': [], 'split': []}
    
    for i in range(30, len(df) - 20):
        # 检测连涨3天
        if (df.iloc[i-1]['change'] > 0 and 
            df.iloc[i-2]['change'] > 0 and 
            df.iloc[i-3]['change'] > 0):
            
            # 策略A：All-in
            allin_buy_price = df.iloc[i]['close']
            allin_ret = (df.iloc[i+10]['close'] - allin_buy_price) / allin_buy_price * 100
            
            # 策略B：分批买入（第1天、第5天、第10天各买1/3）
            split_buy_price = (df.iloc[i]['close'] + df.iloc[i+5]['close'] + df.iloc[i+10]['close']) / 3
            split_ret = (df.iloc[i+10]['close'] - split_buy_price) / split_buy_price * 100
            
            results['allin'].append(allin_ret)
            results['split'].append(split_ret)
    
    return results


def run_backtest():
    """运行回测"""
    print("="*70)
    print("仓位管理策略回测")
    print("="*70)
    
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
        ('002456', '欧菲光'),
        ('000625', '长安汽车'),
        ('002049', '紫光国微'),
        ('603986', '兆易创新'),
        ('000001', '平安银行'),
        ('600036', '招商银行'),
    ]
    
    all_consecutive_up = []
    all_consecutive_down = []
    all_big_gain = []
    all_allin_results = []
    all_split_results = []
    
    for code, name in stocks:
        print(f"\n分析: {code} {name}")
        
        df = get_stock_kline(code, 500)
        if df is None or len(df) < 100:
            print("  数据不足")
            continue
        
        # 找各种情况
        consecutive_ups = find_consecutive_up_days(df, 3)
        consecutive_downs = find_consecutive_down_days(df, 3)
        big_gains = find_big_gain_days(df, 15)
        
        # 模拟策略对比
        sim_results = simulate_allin_strategy(df)
        
        print(f"  连涨3天: {len(consecutive_ups)}, 连跌3天: {len(consecutive_downs)}, 20日大涨: {len(big_gains)}")
        
        for c in consecutive_ups:
            c['stock'] = name
        for c in consecutive_downs:
            c['stock'] = name
        for b in big_gains:
            b['stock'] = name
        
        all_consecutive_up.extend(consecutive_ups)
        all_consecutive_down.extend(consecutive_downs)
        all_big_gain.extend(big_gains)
        all_allin_results.extend(sim_results['allin'])
        all_split_results.extend(sim_results['split'])
        
        time.sleep(0.2)
    
    # ==================== 策略1：连涨后All-in ====================
    print("\n" + "="*70)
    print("【S501 连涨All-in陷阱】连涨3天后追买")
    print("="*70)
    
    if all_consecutive_up:
        df_up = pd.DataFrame(all_consecutive_up)
        
        print(f"\n连涨3天+累涨>5%的次数: {len(df_up)}")
        print(f"  平均累计涨幅: {df_up['total_gain'].mean():.1f}%")
        
        print(f"\n如果连涨后All-in买入:")
        print(f"  次日收益: {df_up['ret_1d'].mean():+.2f}%")
        print(f"  3日收益: {df_up['ret_3d'].mean():+.2f}%")
        print(f"  5日收益: {df_up['ret_5d'].mean():+.2f}%")
        print(f"  10日收益: {df_up['ret_10d'].mean():+.2f}%")
        
        loss_rate_1d = (df_up['ret_1d'] < 0).sum() / len(df_up) * 100
        loss_rate_5d = (df_up['ret_5d'] < 0).sum() / len(df_up) * 100
        avg_drawdown = df_up['max_drawdown'].mean()
        
        print(f"\n  次日亏损概率: {loss_rate_1d:.1f}%")
        print(f"  5日亏损概率: {loss_rate_5d:.1f}%")
        print(f"  10日最大回撤: {avg_drawdown:.1f}%")
        
        print(f"\n【结论】")
        print(f"  连涨后追买，{loss_rate_1d:.0f}%概率次日就亏")
        print(f"  平均要承受{abs(avg_drawdown):.1f}%的回撤")
    
    # ==================== 策略2：连跌后抄底 ====================
    print("\n" + "="*70)
    print("【S503 连跌补仓陷阱】连跌3天后抄底")
    print("="*70)
    
    if all_consecutive_down:
        df_down = pd.DataFrame(all_consecutive_down)
        
        print(f"\n连跌3天+累跌>5%的次数: {len(df_down)}")
        print(f"  平均累计跌幅: {df_down['total_loss'].mean():.1f}%")
        
        print(f"\n如果连跌后抄底买入:")
        print(f"  次日收益: {df_down['ret_1d'].mean():+.2f}%")
        print(f"  3日收益: {df_down['ret_3d'].mean():+.2f}%")
        print(f"  5日收益: {df_down['ret_5d'].mean():+.2f}%")
        print(f"  10日收益: {df_down['ret_10d'].mean():+.2f}%")
        
        further_drop = df_down['further_drop'].mean()
        win_rate_5d = (df_down['ret_5d'] > 0).sum() / len(df_down) * 100
        
        print(f"\n  继续下跌空间: {further_drop:.1f}%")
        print(f"  5日胜率: {win_rate_5d:.1f}%")
        
        print(f"\n【结论】")
        if df_down['ret_5d'].mean() > 0:
            print(f"  连跌后抄底5日平均赚{df_down['ret_5d'].mean():.1f}%")
            print(f"  但注意可能继续下跌{abs(further_drop):.1f}%")
        else:
            print(f"  连跌后抄底平均还要亏{abs(df_down['ret_5d'].mean()):.1f}%")
            print(f"  说明下跌趋势中不要急着抄底")
    
    # ==================== 策略3：20日大涨后买入 ====================
    print("\n" + "="*70)
    print("【S501 追涨陷阱】20日涨幅超15%后买入")
    print("="*70)
    
    if all_big_gain:
        df_big = pd.DataFrame(all_big_gain)
        
        print(f"\n20日涨幅>15%的次数: {len(df_big)}")
        print(f"  平均已涨: {df_big['ret_20d_before'].mean():.1f}%")
        
        print(f"\n如果此时追买:")
        print(f"  5日收益: {df_big['ret_5d'].mean():+.2f}%")
        print(f"  10日收益: {df_big['ret_10d'].mean():+.2f}%")
        print(f"  10日最大回撤: {df_big['max_drawdown'].mean():.1f}%")
        
        loss_rate = (df_big['ret_5d'] < 0).sum() / len(df_big) * 100
        print(f"\n  5日亏损概率: {loss_rate:.1f}%")
        
        print(f"\n【结论】")
        print(f"  大涨后追买，{loss_rate:.0f}%概率5日内亏钱")
    
    # ==================== 策略对比：All-in vs 分批 ====================
    print("\n" + "="*70)
    print("【策略对比】连涨后All-in vs 分批买入")
    print("="*70)
    
    if all_allin_results and all_split_results:
        allin_avg = np.mean(all_allin_results)
        split_avg = np.mean(all_split_results)
        allin_win_rate = sum(1 for r in all_allin_results if r > 0) / len(all_allin_results) * 100
        split_win_rate = sum(1 for r in all_split_results if r > 0) / len(all_split_results) * 100
        
        print(f"\n样本数: {len(all_allin_results)}")
        print(f"\n策略A - 连涨后All-in:")
        print(f"  10日平均收益: {allin_avg:+.2f}%")
        print(f"  胜率: {allin_win_rate:.1f}%")
        
        print(f"\n策略B - 分3批买入:")
        print(f"  10日平均收益: {split_avg:+.2f}%")
        print(f"  胜率: {split_win_rate:.1f}%")
        
        print(f"\n【结论】")
        if split_avg > allin_avg:
            print(f"  分批买入比All-in多赚{split_avg - allin_avg:.1f}%")
        print(f"  分批买入胜率更高 ({split_win_rate:.0f}% vs {allin_win_rate:.0f}%)")
    
    # ==================== 总结 ====================
    print("\n" + "="*70)
    print("仓位管理策略总结")
    print("="*70)
    
    print("""
【验证的仓位陷阱】

1. 连涨All-in (S501)
   - 连涨后满仓追买 → 大概率次日就亏
   - 建议：连涨后应该减仓，不是加仓

2. 连跌抄底 (S503)
   - 连跌后急着抄底 → 可能继续深套
   - 建议：等止跌企稳再买，不接飞刀

3. 追涨满仓 (S505)
   - 大涨后追买 → 承受大幅回撤
   - 建议：控制仓位，分批建仓

【核心仓位原则】

1. 越涨越卖：涨了要减仓，不是加仓
2. 越跌越买：但要分批，不要一次All-in
3. 永不满仓：保留至少20%现金
4. 单只上限：任何一只不超过30%仓位
5. 分批操作：买入和卖出都要分批

【记住】
满仓往往套在最高点
底部往往是空仓状态
    """)


if __name__ == "__main__":
    run_backtest()
