"""
解释板块异动策略的选股逻辑
"""
import requests
import pandas as pd
import os

for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    if key in os.environ:
        del os.environ[key]

session = requests.Session()
session.trust_env = False


def get_stock_data(code, days=100):
    """获取K线数据"""
    code = str(code).zfill(6)
    if code.startswith('6'):
        kcode = f'sh{code}'
    else:
        kcode = f'sz{code}'
    
    url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={kcode},day,,,{days},qfq'
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


def analyze_sector_surge(code, name):
    """分析板块异动策略逻辑"""
    df = get_stock_data(code)
    
    print(f"\n{'='*60}")
    print(f"【{name}】({code}) 板块异动策略分析")
    print("="*60)
    
    idx = len(df) - 1
    today = df.iloc[idx]
    
    print(f"\n当前状态:")
    print(f"  日期: {today['日期'].strftime('%Y-%m-%d')}")
    print(f"  收盘价: {today['收盘']:.2f}")
    
    # 1. 找大涨日（45天内，单日>5%或3日>10%）
    print(f"\n【条件1】寻找大涨日（45天内）")
    
    surge_found = False
    surge_idx = None
    surge_info = None
    
    for i in range(idx - 15, max(idx - 45, 0), -1):
        daily_gain = df.iloc[i]['涨跌幅']
        if daily_gain > 5:
            surge_found = True
            surge_idx = i
            surge_info = {'date': df.iloc[i]['日期'], 'gain': daily_gain, 'type': '单日大涨'}
            print(f"  ✓ 发现: {df.iloc[i]['日期'].strftime('%Y-%m-%d')} 单日涨幅 +{daily_gain:.1f}%")
            break
        
        if i >= 3:
            gain_3d = ((df.iloc[i]['收盘'] / df.iloc[i-3]['收盘']) - 1) * 100
            if gain_3d > 10:
                surge_found = True
                surge_idx = i
                surge_info = {'date': df.iloc[i]['日期'], 'gain': gain_3d, 'type': '3日累计'}
                print(f"  ✓ 发现: {df.iloc[i]['日期'].strftime('%Y-%m-%d')} 3日累计 +{gain_3d:.1f}%")
                break
    
    if not surge_found:
        print("  ✗ 未发现大涨日")
        return
    
    # 2. 计算回撤（从大涨后最高点到当前的回撤）
    print(f"\n【条件2】计算回撤幅度（要求8-20%）")
    
    after_surge = df.iloc[surge_idx:idx+1]
    high_after = after_surge['最高'].max()
    high_date = after_surge.loc[after_surge['最高'].idxmax(), '日期']
    current_price = today['收盘']
    drawdown = (current_price - high_after) / high_after * 100
    
    print(f"  大涨后最高价: {high_after:.2f} ({high_date.strftime('%Y-%m-%d')})")
    print(f"  当前价格: {current_price:.2f}")
    print(f"  回撤幅度: {drawdown:.1f}%")
    
    if -20 <= drawdown <= -8:
        print(f"  ✓ 回撤在8-20%区间内")
    else:
        print(f"  ✗ 回撤不在8-20%区间")
    
    # 3. 近10日横盘（振幅<15%）
    print(f"\n【条件3】近10日横盘（振幅<15%）")
    
    recent_10 = df.iloc[idx-9:idx+1]
    high_10 = recent_10['最高'].max()
    low_10 = recent_10['最低'].min()
    range_10 = (high_10 - low_10) / low_10 * 100
    
    print(f"  近10日最高: {high_10:.2f}")
    print(f"  近10日最低: {low_10:.2f}")
    print(f"  振幅: {range_10:.1f}%")
    
    if range_10 <= 15:
        print(f"  ✓ 振幅<15%，处于横盘状态")
    else:
        print(f"  ✗ 振幅>15%，波动较大")
    
    # 4. 当前价格接近下沿（距低点<5%）
    print(f"\n【条件4】接近低点（距离<5%）")
    
    dist_to_low = (current_price - low_10) / low_10 * 100
    
    print(f"  当前价格: {current_price:.2f}")
    print(f"  近10日低点: {low_10:.2f}")
    print(f"  距离低点: {dist_to_low:+.1f}%")
    
    if dist_to_low <= 5:
        print(f"  ✓ 接近低点，可能企稳")
    else:
        print(f"  ✗ 距离低点较远")
    
    # 总结
    print(f"\n【策略逻辑总结】")
    print(f"""
  1. {surge_info['date'].strftime('%m-%d')} 有过{surge_info['type']} +{surge_info['gain']:.1f}%
     → 说明该股有资金关注，有爆发力
  
  2. 之后从高点{high_after:.2f}回撤到{current_price:.2f}，跌了{drawdown:.1f}%
     → 主力洗盘/获利盘消化
  
  3. 近10日振幅仅{range_10:.1f}%，处于横盘整理
     → 卖压减轻，筹码趋于稳定
  
  4. 当前价格距近期低点{low_10:.2f}仅{dist_to_low:.1f}%
     → 接近支撑，风险收益比合适

  买入逻辑：大涨→回撤→横盘→接近支撑 = 潜在二次启动点
""")
    
    # 显示近期K线
    print(f"\n【近15日K线】")
    print(f"{'日期':^12} {'开盘':>8} {'收盘':>8} {'最高':>8} {'最低':>8} {'涨跌幅':>8}")
    print("-" * 60)
    for _, row in df.tail(15).iterrows():
        change = row['涨跌幅'] if pd.notna(row['涨跌幅']) else 0
        print(f"{row['日期'].strftime('%Y-%m-%d'):^12} {row['开盘']:>8.2f} {row['收盘']:>8.2f} {row['最高']:>8.2f} {row['最低']:>8.2f} {change:>+7.2f}%")


# 分析几只被选中的股票
stocks = [
    ('601318', '中国平安'),
    ('002050', '三花智控'),
    ('002384', '东山精密'),
]

for code, name in stocks:
    analyze_sector_surge(code, name)
