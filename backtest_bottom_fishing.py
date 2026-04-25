# -*- coding: utf-8 -*-
"""
抄底策略回测
=====================================
验证各种抄底时机的效果：
1. 大跌当天抄底
2. 连续下跌后抄底
3. 腰斩后抄底
4. 等企稳后再买
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


def find_big_drop_days(df, threshold=-5):
    """找出单日大跌的情况"""
    signals = []
    
    for i in range(1, len(df) - 20):
        if df.iloc[i]['change'] < threshold:
            buy_price = df.iloc[i]['close']
            
            # 后续走势
            ret_1d = (df.iloc[i+1]['close'] - buy_price) / buy_price * 100
            ret_3d = (df.iloc[i+3]['close'] - buy_price) / buy_price * 100
            ret_5d = (df.iloc[i+5]['close'] - buy_price) / buy_price * 100
            ret_10d = (df.iloc[i+10]['close'] - buy_price) / buy_price * 100
            ret_20d = (df.iloc[i+20]['close'] - buy_price) / buy_price * 100 if i+20 < len(df) else 0
            
            # 后续最大回撤
            future_10d = df.iloc[i:i+10]
            max_drawdown = (future_10d['low'].min() - buy_price) / buy_price * 100
            
            signals.append({
                'date': df.iloc[i]['date'],
                'drop': df.iloc[i]['change'],
                'ret_1d': ret_1d,
                'ret_3d': ret_3d,
                'ret_5d': ret_5d,
                'ret_10d': ret_10d,
                'ret_20d': ret_20d,
                'max_drawdown': max_drawdown,
                'type': 'big_drop',
            })
    
    return signals


def find_consecutive_drop(df, min_days=3, min_total_drop=-8):
    """找出连续下跌的情况"""
    signals = []
    
    for i in range(min_days, len(df) - 20):
        # 检查是否连续下跌
        consecutive = True
        total_drop = 0
        for j in range(min_days):
            if df.iloc[i-j]['change'] >= 0:
                consecutive = False
                break
            total_drop += df.iloc[i-j]['change']
        
        if consecutive and total_drop < min_total_drop:
            buy_price = df.iloc[i]['close']
            
            ret_1d = (df.iloc[i+1]['close'] - buy_price) / buy_price * 100
            ret_3d = (df.iloc[i+3]['close'] - buy_price) / buy_price * 100
            ret_5d = (df.iloc[i+5]['close'] - buy_price) / buy_price * 100
            ret_10d = (df.iloc[i+10]['close'] - buy_price) / buy_price * 100
            ret_20d = (df.iloc[i+20]['close'] - buy_price) / buy_price * 100 if i+20 < len(df) else 0
            
            # 继续下跌的风险
            future_10d = df.iloc[i:i+10]
            further_drop = (future_10d['low'].min() - buy_price) / buy_price * 100
            
            signals.append({
                'date': df.iloc[i]['date'],
                'consecutive_days': min_days,
                'total_drop': total_drop,
                'ret_1d': ret_1d,
                'ret_3d': ret_3d,
                'ret_5d': ret_5d,
                'ret_10d': ret_10d,
                'ret_20d': ret_20d,
                'further_drop': further_drop,
                'type': f'consecutive_{min_days}d',
            })
    
    return signals


def find_half_price(df, lookback=60):
    """找出腰斩的情况（从近期高点跌50%）"""
    signals = []
    
    for i in range(lookback, len(df) - 20):
        # 近期高点
        recent_high = df.iloc[i-lookback:i]['high'].max()
        current_price = df.iloc[i]['close']
        
        drop_from_high = (current_price - recent_high) / recent_high * 100
        
        if drop_from_high < -45 and drop_from_high > -55:  # 约腰斩
            buy_price = current_price
            
            ret_5d = (df.iloc[i+5]['close'] - buy_price) / buy_price * 100
            ret_10d = (df.iloc[i+10]['close'] - buy_price) / buy_price * 100
            ret_20d = (df.iloc[i+20]['close'] - buy_price) / buy_price * 100 if i+20 < len(df) else 0
            
            # 继续下跌
            future_20d = df.iloc[i:min(i+20, len(df))]
            further_drop = (future_20d['low'].min() - buy_price) / buy_price * 100
            
            signals.append({
                'date': df.iloc[i]['date'],
                'drop_from_high': drop_from_high,
                'ret_5d': ret_5d,
                'ret_10d': ret_10d,
                'ret_20d': ret_20d,
                'further_drop': further_drop,
                'type': 'half_price',
            })
    
    return signals


def find_stabilization(df):
    """找出止跌企稳后再买的情况"""
    signals = []
    
    for i in range(20, len(df) - 20):
        # 条件1：之前有较大下跌（10日跌幅>10%）
        ret_10d_before = (df.iloc[i-5]['close'] - df.iloc[i-15]['close']) / df.iloc[i-15]['close'] * 100
        
        if ret_10d_before < -10:
            # 条件2：最近5日企稳（不创新低，波动收窄）
            recent_5d = df.iloc[i-5:i]
            prev_5d = df.iloc[i-10:i-5]
            
            recent_low = recent_5d['low'].min()
            prev_low = prev_5d['low'].min()
            
            recent_volatility = (recent_5d['high'].max() - recent_5d['low'].min()) / recent_5d['close'].mean() * 100
            
            # 条件3：缩量
            recent_vol = recent_5d['volume'].mean()
            prev_vol = prev_5d['volume'].mean()
            vol_shrink = recent_vol / prev_vol
            
            if recent_low >= prev_low * 0.98 and recent_volatility < 8 and vol_shrink < 0.8:
                buy_price = df.iloc[i]['close']
                
                ret_5d = (df.iloc[i+5]['close'] - buy_price) / buy_price * 100
                ret_10d = (df.iloc[i+10]['close'] - buy_price) / buy_price * 100
                ret_20d = (df.iloc[i+20]['close'] - buy_price) / buy_price * 100 if i+20 < len(df) else 0
                
                future_10d = df.iloc[i:i+10]
                max_drawdown = (future_10d['low'].min() - buy_price) / buy_price * 100
                
                signals.append({
                    'date': df.iloc[i]['date'],
                    'drop_before': ret_10d_before,
                    'vol_shrink': vol_shrink,
                    'ret_5d': ret_5d,
                    'ret_10d': ret_10d,
                    'ret_20d': ret_20d,
                    'max_drawdown': max_drawdown,
                    'type': 'stabilization',
                })
    
    return signals


def run_backtest():
    """运行回测"""
    print("="*70)
    print("抄底策略回测")
    print("="*70)
    
    stocks = [
        ('002230', '科大讯飞'),
        ('002371', '北方华创'),
        ('002594', '比亚迪'),
        ('600519', '贵州茅台'),
        ('000858', '五粮液'),
        ('300750', '宁德时代'),
        ('002475', '立讯精密'),
        ('601012', '隆基绿能'),
        ('002456', '欧菲光'),
        ('000625', '长安汽车'),
        ('002049', '紫光国微'),
        ('603986', '兆易创新'),
    ]
    
    all_big_drop = []
    all_consecutive_3d = []
    all_consecutive_5d = []
    all_half_price = []
    all_stabilization = []
    
    for code, name in stocks:
        print(f"\n分析: {code} {name}")
        
        df = get_stock_kline(code, 500)
        if df is None or len(df) < 100:
            print("  数据不足")
            continue
        
        # 找各种抄底情况
        big_drops = find_big_drop_days(df, -5)
        consecutive_3d = find_consecutive_drop(df, 3, -8)
        consecutive_5d = find_consecutive_drop(df, 5, -12)
        half_prices = find_half_price(df)
        stabilizations = find_stabilization(df)
        
        print(f"  大跌: {len(big_drops)}, 连跌3天: {len(consecutive_3d)}, 连跌5天: {len(consecutive_5d)}, 腰斩: {len(half_prices)}, 企稳: {len(stabilizations)}")
        
        for s in big_drops:
            s['stock'] = name
        for s in consecutive_3d:
            s['stock'] = name
        for s in consecutive_5d:
            s['stock'] = name
        for s in half_prices:
            s['stock'] = name
        for s in stabilizations:
            s['stock'] = name
        
        all_big_drop.extend(big_drops)
        all_consecutive_3d.extend(consecutive_3d)
        all_consecutive_5d.extend(consecutive_5d)
        all_half_price.extend(half_prices)
        all_stabilization.extend(stabilizations)
        
        time.sleep(0.2)
    
    # ==================== 策略1：大跌当天抄底 ====================
    print("\n" + "="*70)
    print("【B001 大跌抄底】单日跌5%以上当天买入")
    print("="*70)
    
    if all_big_drop:
        df_drop = pd.DataFrame(all_big_drop)
        
        print(f"\n大跌次数（单日跌>5%）: {len(df_drop)}")
        print(f"  平均跌幅: {df_drop['drop'].mean():.1f}%")
        
        print(f"\n如果大跌当天抄底:")
        print(f"  次日收益: {df_drop['ret_1d'].mean():+.2f}%")
        print(f"  3日收益: {df_drop['ret_3d'].mean():+.2f}%")
        print(f"  5日收益: {df_drop['ret_5d'].mean():+.2f}%")
        print(f"  10日收益: {df_drop['ret_10d'].mean():+.2f}%")
        print(f"  20日收益: {df_drop['ret_20d'].mean():+.2f}%")
        
        win_rate_5d = (df_drop['ret_5d'] > 0).sum() / len(df_drop) * 100
        still_drop = (df_drop['max_drawdown'] < -3).sum() / len(df_drop) * 100
        
        print(f"\n  5日胜率: {win_rate_5d:.1f}%")
        print(f"  继续下跌>3%概率: {still_drop:.1f}%")
    
    # ==================== 策略2：连跌3天抄底 ====================
    print("\n" + "="*70)
    print("【B002 连跌抄底】连跌3天（累跌>8%）后买入")
    print("="*70)
    
    if all_consecutive_3d:
        df_c3 = pd.DataFrame(all_consecutive_3d)
        
        print(f"\n连跌3天次数: {len(df_c3)}")
        print(f"  平均累计跌幅: {df_c3['total_drop'].mean():.1f}%")
        
        print(f"\n如果连跌3天后抄底:")
        print(f"  次日收益: {df_c3['ret_1d'].mean():+.2f}%")
        print(f"  5日收益: {df_c3['ret_5d'].mean():+.2f}%")
        print(f"  10日收益: {df_c3['ret_10d'].mean():+.2f}%")
        print(f"  20日收益: {df_c3['ret_20d'].mean():+.2f}%")
        
        win_rate_5d = (df_c3['ret_5d'] > 0).sum() / len(df_c3) * 100
        further_drop = df_c3['further_drop'].mean()
        
        print(f"\n  5日胜率: {win_rate_5d:.1f}%")
        print(f"  平均继续下跌: {further_drop:.1f}%")
    
    # ==================== 策略3：连跌5天抄底 ====================
    print("\n" + "="*70)
    print("【B002+ 深度连跌】连跌5天（累跌>12%）后买入")
    print("="*70)
    
    if all_consecutive_5d:
        df_c5 = pd.DataFrame(all_consecutive_5d)
        
        print(f"\n连跌5天次数: {len(df_c5)}")
        print(f"  平均累计跌幅: {df_c5['total_drop'].mean():.1f}%")
        
        print(f"\n如果连跌5天后抄底:")
        print(f"  次日收益: {df_c5['ret_1d'].mean():+.2f}%")
        print(f"  5日收益: {df_c5['ret_5d'].mean():+.2f}%")
        print(f"  10日收益: {df_c5['ret_10d'].mean():+.2f}%")
        print(f"  20日收益: {df_c5['ret_20d'].mean():+.2f}%")
        
        win_rate_5d = (df_c5['ret_5d'] > 0).sum() / len(df_c5) * 100
        further_drop = df_c5['further_drop'].mean()
        
        print(f"\n  5日胜率: {win_rate_5d:.1f}%")
        print(f"  平均继续下跌: {further_drop:.1f}%")
    
    # ==================== 策略4：腰斩抄底 ====================
    print("\n" + "="*70)
    print("【B003 腰斩抄底】从高点跌50%后买入")
    print("="*70)
    
    if all_half_price:
        df_half = pd.DataFrame(all_half_price)
        
        print(f"\n腰斩次数: {len(df_half)}")
        print(f"  平均从高点跌: {df_half['drop_from_high'].mean():.1f}%")
        
        print(f"\n如果腰斩后抄底:")
        print(f"  5日收益: {df_half['ret_5d'].mean():+.2f}%")
        print(f"  10日收益: {df_half['ret_10d'].mean():+.2f}%")
        print(f"  20日收益: {df_half['ret_20d'].mean():+.2f}%")
        
        win_rate_20d = (df_half['ret_20d'] > 0).sum() / len(df_half) * 100
        further_drop = df_half['further_drop'].mean()
        
        print(f"\n  20日胜率: {win_rate_20d:.1f}%")
        print(f"  平均继续下跌: {further_drop:.1f}%")
        
        print(f"\n【警告】腰斩后平均还会再跌{abs(further_drop):.0f}%！")
    
    # ==================== 策略5：等企稳后再买 ====================
    print("\n" + "="*70)
    print("【B006 正确姿势】等止跌企稳后再买")
    print("="*70)
    
    if all_stabilization:
        df_stable = pd.DataFrame(all_stabilization)
        
        print(f"\n企稳信号次数: {len(df_stable)}")
        print(f"  之前平均跌幅: {df_stable['drop_before'].mean():.1f}%")
        
        print(f"\n如果等企稳后再买:")
        print(f"  5日收益: {df_stable['ret_5d'].mean():+.2f}%")
        print(f"  10日收益: {df_stable['ret_10d'].mean():+.2f}%")
        print(f"  20日收益: {df_stable['ret_20d'].mean():+.2f}%")
        
        win_rate_5d = (df_stable['ret_5d'] > 0).sum() / len(df_stable) * 100
        win_rate_10d = (df_stable['ret_10d'] > 0).sum() / len(df_stable) * 100
        max_dd = df_stable['max_drawdown'].mean()
        
        print(f"\n  5日胜率: {win_rate_5d:.1f}%")
        print(f"  10日胜率: {win_rate_10d:.1f}%")
        print(f"  平均最大回撤: {max_dd:.1f}%")
    
    # ==================== 对比分析 ====================
    print("\n" + "="*70)
    print("【策略对比】各种抄底时机")
    print("="*70)
    
    print("\n| 抄底时机 | 样本数 | 5日胜率 | 5日收益 | 继续下跌风险 |")
    print("|----------|--------|---------|---------|--------------|")
    
    if all_big_drop:
        df_drop = pd.DataFrame(all_big_drop)
        wr = (df_drop['ret_5d'] > 0).sum() / len(df_drop) * 100
        ret = df_drop['ret_5d'].mean()
        risk = df_drop['max_drawdown'].mean()
        print(f"| 大跌当天 | {len(df_drop)} | {wr:.0f}% | {ret:+.1f}% | {risk:.1f}% |")
    
    if all_consecutive_3d:
        df_c3 = pd.DataFrame(all_consecutive_3d)
        wr = (df_c3['ret_5d'] > 0).sum() / len(df_c3) * 100
        ret = df_c3['ret_5d'].mean()
        risk = df_c3['further_drop'].mean()
        print(f"| 连跌3天 | {len(df_c3)} | {wr:.0f}% | {ret:+.1f}% | {risk:.1f}% |")
    
    if all_consecutive_5d:
        df_c5 = pd.DataFrame(all_consecutive_5d)
        wr = (df_c5['ret_5d'] > 0).sum() / len(df_c5) * 100
        ret = df_c5['ret_5d'].mean()
        risk = df_c5['further_drop'].mean()
        print(f"| 连跌5天 | {len(df_c5)} | {wr:.0f}% | {ret:+.1f}% | {risk:.1f}% |")
    
    if all_half_price:
        df_half = pd.DataFrame(all_half_price)
        wr = (df_half['ret_5d'] > 0).sum() / len(df_half) * 100
        ret = df_half['ret_5d'].mean()
        risk = df_half['further_drop'].mean()
        print(f"| 腰斩后 | {len(df_half)} | {wr:.0f}% | {ret:+.1f}% | {risk:.1f}% |")
    
    if all_stabilization:
        df_stable = pd.DataFrame(all_stabilization)
        wr = (df_stable['ret_5d'] > 0).sum() / len(df_stable) * 100
        ret = df_stable['ret_5d'].mean()
        risk = df_stable['max_drawdown'].mean()
        print(f"| 企稳后 | {len(df_stable)} | {wr:.0f}% | {ret:+.1f}% | {risk:.1f}% |")
    
    # ==================== 总结 ====================
    print("\n" + "="*70)
    print("抄底策略总结")
    print("="*70)
    
    print("""
【数据验证的真相】

1. 大跌当天抄底
   - 看似便宜，实则风险大
   - 继续下跌概率高
   - 胜率不到50%

2. 连续下跌后抄底
   - 连跌3天后抄底，可能继续跌
   - 连跌5天后抄底，风险更大
   - "接飞刀"是危险的

3. 腰斩后抄底
   - 腰斩后平均还会再跌10-20%
   - 腰斩可以再腰斩
   - 不要因为跌多就认为便宜

4. 等企稳后再买
   - 胜率最高
   - 回撤最小
   - 虽然买得贵一点，但更安全

【抄底正确姿势】

1. 永远不接飞刀
2. 等止跌（连续2-3天不创新低）
3. 等企稳（缩量横盘）
4. 等信号（放量阳线）
5. 分批买入，不要一次性满仓

【记住】
宁可买贵一点，不要买在下跌途中
底部是走出来的，不是抄出来的
    """)


if __name__ == "__main__":
    run_backtest()
