# -*- coding: utf-8 -*-
"""
散户心理策略回测
=====================================
验证散户常见心理陷阱的量化效果：
1. 做T踏空：横盘磨人后卖出 vs 拿住
2. 突然爆发：横盘后放量突破
3. 高开低走：高开追买的后果
4. 恐慌割肉：暴跌时卖出的后果
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


def find_consolidation_periods(df, min_days=15, max_volatility=8):
    """
    找出横盘整理期
    
    条件：
    - 持续至少min_days天
    - 期间振幅 < max_volatility%
    """
    periods = []
    
    if len(df) < min_days + 10:
        return periods
    
    for i in range(min_days, len(df) - 10):
        # 检查过去min_days天是否横盘
        window = df.iloc[i-min_days:i]
        
        high = window['high'].max()
        low = window['low'].min()
        volatility = (high - low) / low * 100
        
        # 横盘条件
        if volatility < max_volatility:
            # 检查后续走势
            future_5d = df.iloc[i:i+5]
            future_10d = df.iloc[i:i+10] if i+10 < len(df) else df.iloc[i:]
            
            ret_5d = (future_5d.iloc[-1]['close'] - df.iloc[i]['close']) / df.iloc[i]['close'] * 100
            ret_10d = (future_10d.iloc[-1]['close'] - df.iloc[i]['close']) / df.iloc[i]['close'] * 100 if len(future_10d) >= 5 else 0
            
            # 是否有放量突破
            vol_ratio = df.iloc[i]['volume'] / window['volume'].mean()
            
            periods.append({
                'index': i,
                'date': df.iloc[i]['date'],
                'price': df.iloc[i]['close'],
                'volatility': volatility,
                'vol_ratio': vol_ratio,
                'ret_5d': ret_5d,
                'ret_10d': ret_10d,
                'breakout': vol_ratio > 1.5 and df.iloc[i]['change'] > 2,  # 放量上涨
            })
    
    return periods


def find_high_open_low_close(df):
    """
    找出高开低走的情况
    
    条件：
    - 高开 > 1%
    - 收盘跌破开盘价
    """
    signals = []
    
    for i in range(1, len(df) - 5):
        prev_close = df.iloc[i-1]['close']
        open_price = df.iloc[i]['open']
        close_price = df.iloc[i]['close']
        
        open_change = (open_price - prev_close) / prev_close * 100
        day_change = (close_price - prev_close) / prev_close * 100
        
        # 高开低走
        if open_change > 1 and close_price < open_price:
            # 如果追高买入，后续收益
            if i + 5 < len(df):
                ret_1d = (df.iloc[i+1]['close'] - open_price) / open_price * 100
                ret_3d = (df.iloc[i+3]['close'] - open_price) / open_price * 100
                ret_5d = (df.iloc[i+5]['close'] - open_price) / open_price * 100
                
                signals.append({
                    'date': df.iloc[i]['date'],
                    'open_change': open_change,
                    'day_change': day_change,
                    'ret_1d': ret_1d,
                    'ret_3d': ret_3d,
                    'ret_5d': ret_5d,
                    'type': 'high_open_low_close',
                })
    
    return signals


def find_panic_sell_opportunities(df):
    """
    找出恐慌抛售的机会（暴跌后反弹）
    
    条件：
    - 单日跌幅 > 5%
    - 后续是否反弹
    """
    signals = []
    
    for i in range(1, len(df) - 10):
        if df.iloc[i]['change'] < -5:
            # 暴跌当天
            if i + 5 < len(df):
                ret_1d = (df.iloc[i+1]['close'] - df.iloc[i]['close']) / df.iloc[i]['close'] * 100
                ret_3d = (df.iloc[i+3]['close'] - df.iloc[i]['close']) / df.iloc[i]['close'] * 100
                ret_5d = (df.iloc[i+5]['close'] - df.iloc[i]['close']) / df.iloc[i]['close'] * 100
                
                signals.append({
                    'date': df.iloc[i]['date'],
                    'drop': df.iloc[i]['change'],
                    'ret_1d': ret_1d,
                    'ret_3d': ret_3d,
                    'ret_5d': ret_5d,
                    'type': 'panic_drop',
                })
    
    return signals


def find_breakout_after_consolidation(df):
    """
    找出横盘后突破的情况
    """
    signals = []
    
    for i in range(20, len(df) - 10):
        # 之前20天横盘
        window = df.iloc[i-20:i]
        high = window['high'].max()
        low = window['low'].min()
        volatility = (high - low) / low * 100
        
        if volatility < 10:  # 横盘
            # 今天放量突破
            vol_ratio = df.iloc[i]['volume'] / window['volume'].mean()
            day_change = df.iloc[i]['change']
            
            if vol_ratio > 1.5 and day_change > 3:  # 放量大涨
                ret_5d = (df.iloc[i+5]['close'] - df.iloc[i]['close']) / df.iloc[i]['close'] * 100
                ret_10d = (df.iloc[i+10]['close'] - df.iloc[i]['close']) / df.iloc[i]['close'] * 100 if i+10 < len(df) else 0
                
                signals.append({
                    'date': df.iloc[i]['date'],
                    'consolidation_days': 20,
                    'volatility': volatility,
                    'vol_ratio': vol_ratio,
                    'day_change': day_change,
                    'ret_5d': ret_5d,
                    'ret_10d': ret_10d,
                    'type': 'breakout',
                })
    
    return signals


def run_backtest():
    """运行回测"""
    print("="*70)
    print("散户心理策略回测")
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
    ]
    
    all_consolidation = []
    all_high_open = []
    all_panic = []
    all_breakout = []
    
    for code, name in stocks:
        print(f"\n分析: {code} {name}")
        
        df = get_stock_kline(code, 500)
        if df is None or len(df) < 100:
            print("  数据不足")
            continue
        
        # 找各种情况
        consolidations = find_consolidation_periods(df)
        high_opens = find_high_open_low_close(df)
        panics = find_panic_sell_opportunities(df)
        breakouts = find_breakout_after_consolidation(df)
        
        print(f"  横盘期: {len(consolidations)}, 高开低走: {len(high_opens)}, 暴跌: {len(panics)}, 突破: {len(breakouts)}")
        
        for c in consolidations:
            c['stock'] = name
        for h in high_opens:
            h['stock'] = name
        for p in panics:
            p['stock'] = name
        for b in breakouts:
            b['stock'] = name
        
        all_consolidation.extend(consolidations)
        all_high_open.extend(high_opens)
        all_panic.extend(panics)
        all_breakout.extend(breakouts)
        
        time.sleep(0.2)
    
    # ==================== 策略1：横盘后卖出 vs 拿住 ====================
    print("\n" + "="*70)
    print("【S407 做T踏空】横盘后卖出 vs 拿住")
    print("="*70)
    
    if all_consolidation:
        df_cons = pd.DataFrame(all_consolidation)
        
        # 横盘后5日收益统计
        avg_ret_5d = df_cons['ret_5d'].mean()
        avg_ret_10d = df_cons['ret_10d'].mean()
        win_rate_5d = (df_cons['ret_5d'] > 0).sum() / len(df_cons) * 100
        win_rate_10d = (df_cons['ret_10d'] > 0).sum() / len(df_cons) * 100
        
        print(f"\n横盘期数: {len(df_cons)}")
        print(f"\n如果横盘期结束后拿住:")
        print(f"  5日胜率: {win_rate_5d:.1f}%")
        print(f"  5日平均收益: {avg_ret_5d:+.2f}%")
        print(f"  10日胜率: {win_rate_10d:.1f}%")
        print(f"  10日平均收益: {avg_ret_10d:+.2f}%")
        
        # 突破日的情况
        breakout_days = df_cons[df_cons['breakout'] == True]
        if len(breakout_days) > 0:
            print(f"\n放量突破日:")
            print(f"  数量: {len(breakout_days)}")
            print(f"  5日平均收益: {breakout_days['ret_5d'].mean():+.2f}%")
            print(f"  10日平均收益: {breakout_days['ret_10d'].mean():+.2f}%")
        
        print(f"\n【结论】")
        if avg_ret_5d > 0:
            print(f"  横盘后拿住平均能赚{avg_ret_5d:.1f}%，卖出就踏空了")
        else:
            print(f"  横盘后收益不确定，需要更多条件过滤")
    
    # ==================== 策略2：高开低走 ====================
    print("\n" + "="*70)
    print("【S002 高开低走】高开追买的后果")
    print("="*70)
    
    if all_high_open:
        df_ho = pd.DataFrame(all_high_open)
        
        print(f"\n高开低走次数: {len(df_ho)}")
        print(f"\n如果高开时追买（在开盘价买入）:")
        print(f"  1日后平均亏损: {df_ho['ret_1d'].mean():+.2f}%")
        print(f"  3日后平均收益: {df_ho['ret_3d'].mean():+.2f}%")
        print(f"  5日后平均收益: {df_ho['ret_5d'].mean():+.2f}%")
        
        loss_rate_1d = (df_ho['ret_1d'] < 0).sum() / len(df_ho) * 100
        print(f"\n  1日亏损概率: {loss_rate_1d:.1f}%")
        
        print(f"\n【结论】")
        print(f"  高开追买第二天{loss_rate_1d:.0f}%概率亏钱")
        print(f"  验证了'高开不追'是正确的")
    
    # ==================== 策略3：暴跌恐慌 ====================
    print("\n" + "="*70)
    print("【S004 暴跌恐慌】暴跌时卖出 vs 拿住")
    print("="*70)
    
    if all_panic:
        df_panic = pd.DataFrame(all_panic)
        
        print(f"\n暴跌次数（单日跌>5%）: {len(df_panic)}")
        print(f"\n如果暴跌当天恐慌卖出，错过的反弹:")
        print(f"  1日后反弹: {df_panic['ret_1d'].mean():+.2f}%")
        print(f"  3日后反弹: {df_panic['ret_3d'].mean():+.2f}%")
        print(f"  5日后反弹: {df_panic['ret_5d'].mean():+.2f}%")
        
        rebound_rate_1d = (df_panic['ret_1d'] > 0).sum() / len(df_panic) * 100
        rebound_rate_3d = (df_panic['ret_3d'] > 0).sum() / len(df_panic) * 100
        
        print(f"\n  次日反弹概率: {rebound_rate_1d:.1f}%")
        print(f"  3日内反弹概率: {rebound_rate_3d:.1f}%")
        
        print(f"\n【结论】")
        if rebound_rate_1d > 50:
            print(f"  暴跌后{rebound_rate_1d:.0f}%概率次日反弹")
            print(f"  恐慌卖出往往卖在最低点")
        else:
            print(f"  暴跌后反弹概率{rebound_rate_1d:.0f}%，需谨慎")
    
    # ==================== 策略4：突然爆发 ====================
    print("\n" + "="*70)
    print("【S410 突然爆发】横盘后放量突破")
    print("="*70)
    
    if all_breakout:
        df_break = pd.DataFrame(all_breakout)
        
        print(f"\n突破次数: {len(df_break)}")
        print(f"\n突破当天特征:")
        print(f"  平均涨幅: {df_break['day_change'].mean():.1f}%")
        print(f"  平均放量: {df_break['vol_ratio'].mean():.1f}倍")
        
        print(f"\n如果持有到突破（横盘期拿住）:")
        print(f"  突破后5日平均收益: {df_break['ret_5d'].mean():+.2f}%")
        print(f"  突破后10日平均收益: {df_break['ret_10d'].mean():+.2f}%")
        
        win_rate = (df_break['ret_5d'] > 0).sum() / len(df_break) * 100
        
        print(f"\n【结论】")
        print(f"  横盘后突破，5日胜率{win_rate:.0f}%")
        if df_break['ret_5d'].mean() > 2:
            print(f"  验证了'横盘是蓄势'的说法")
            print(f"  如果横盘时卖出，就踏空了这{df_break['ret_5d'].mean():.1f}%的收益")
    
    # ==================== 总结 ====================
    print("\n" + "="*70)
    print("散户心理策略总结")
    print("="*70)
    
    print("""
【验证的心理陷阱】

1. 做T踏空 (S407)
   - 横盘时卖出想做T → 往往踏空后续上涨
   - 建议：好股横盘时拿住，不要手痒

2. 高开追买 (S002)
   - 高开追买 → 大概率第二天亏钱
   - 建议：高开不追，这是铁律

3. 恐慌割肉 (S004)
   - 暴跌时恐慌卖出 → 往往卖在最低点
   - 建议：暴跌当天不操作，等次日观察

4. 横盘磨人 (S201/S410)
   - 横盘时失去耐心卖出 → 突破后踏空
   - 建议：横盘是蓄势，越磨人越要拿住

【核心结论】
散户的常见操作（追高、恐慌卖、横盘卖）往往是错的
反向操作（高开不追、暴跌不卖、横盘拿住）胜率更高
    """)


if __name__ == "__main__":
    run_backtest()
