"""快速扫描 - 寻找明日买点"""
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

print("="*60)
print("明日买点快速扫描")
print(f"扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*60)

def get_stock_data(symbol, days=60):
    """获取股票历史数据"""
    try:
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", 
                                start_date="20241101", adjust="qfq")
        if df is not None and len(df) > 0:
            df['日期'] = pd.to_datetime(df['日期'])
        return df
    except:
        return None

def check_signals(df):
    """检查技术信号"""
    if df is None or len(df) < 30:
        return {}
    
    df = df.copy().reset_index(drop=True)
    df['MA5'] = df['收盘'].rolling(5).mean()
    df['MA10'] = df['收盘'].rolling(10).mean()
    df['MA20'] = df['收盘'].rolling(20).mean()
    df['VOL_MA5'] = df['成交量'].rolling(5).mean()
    
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    
    signals = {}
    
    # 1. 均线多头排列
    if pd.notna(latest['MA5']) and pd.notna(latest['MA10']) and pd.notna(latest['MA20']):
        ma_bullish = latest['MA5'] > latest['MA10'] > latest['MA20']
        signals['均线多头'] = ma_bullish
    
    # 2. 量能放大
    vol_ratio = latest['成交量'] / latest['VOL_MA5'] if latest['VOL_MA5'] > 0 else 0
    signals['量能放大'] = vol_ratio > 1.2
    signals['量比'] = f"{vol_ratio:.2f}"
    
    # 3. 今日收阳
    is_red = latest['收盘'] > latest['开盘']
    signals['收阳'] = is_red
    
    # 4. 站上MA20
    above_ma20 = latest['收盘'] > latest['MA20'] if pd.notna(latest['MA20']) else False
    signals['站上MA20'] = above_ma20
    
    # 5. 箱体突破
    box_high = df.iloc[-16:-1]['最高'].max() if len(df) >= 16 else 0
    box_breakout = latest['收盘'] > box_high
    signals['箱体突破'] = box_breakout
    
    # 6. 回调幅度
    high_20d = df.tail(20)['最高'].max()
    pullback = (latest['收盘'] - high_20d) / high_20d * 100
    signals['回调幅度'] = f"{pullback:.1f}%"
    
    # 计算评分
    score = 0
    if signals.get('均线多头'): score += 25
    if signals.get('量能放大'): score += 20
    if signals.get('收阳'): score += 15
    if signals.get('站上MA20'): score += 20
    if signals.get('箱体突破'): score += 20
    signals['评分'] = score
    
    return signals

# 测试用股票列表 - 从之前扫描结果中筛选的潜力股
test_stocks = [
    ('000685', '中山公用'),
    ('000823', '超声电子'),
    ('001211', '双枪科技'),
    ('002893', '京能热力'),
    ('605033', '美邦股份'),
    ('000663', '永安林业'),
    ('001386', '马可波罗'),
    ('002133', '广宇集团'),
    ('002307', '北新路桥'),
    ('002279', '久其软件'),
    ('000002', '万科A'),
    ('600887', '伊利股份'),
]

print(f"\n检查 {len(test_stocks)} 只潜力股的最新信号...")
print("-"*60)

results = []
for code, name in test_stocks:
    try:
        df = get_stock_data(code)
        if df is None:
            print(f"  {code} {name}: 获取数据失败")
            continue
        
        signals = check_signals(df)
        latest = df.iloc[-1]
        
        result = {
            '代码': code,
            '名称': name,
            '收盘价': latest['收盘'],
            '涨跌幅': f"{(latest['收盘']-latest['开盘'])/latest['开盘']*100:.2f}%",
            '评分': signals.get('评分', 0),
            '均线多头': 'Yes' if signals.get('均线多头') else 'No',
            '量比': signals.get('量比', ''),
            '箱体突破': 'Yes' if signals.get('箱体突破') else 'No',
            '回调幅度': signals.get('回调幅度', ''),
        }
        results.append(result)
        
        status = 'STRONG' if result['评分'] >= 60 else 'WEAK'
        print(f"  {code} {name}: {result['收盘价']:.2f} ({result['涨跌幅']}) Score={result['评分']} [{status}]")
        
    except Exception as e:
        print(f"  {code} {name}: Error - {str(e)[:50]}")

# 排序输出
if results:
    print("\n" + "="*60)
    print("明日买点推荐 (按评分排序)")
    print("="*60)
    
    results_sorted = sorted(results, key=lambda x: x['评分'], reverse=True)
    
    strong_signals = [r for r in results_sorted if r['评分'] >= 60]
    medium_signals = [r for r in results_sorted if 40 <= r['评分'] < 60]
    
    if strong_signals:
        print("\n【强信号 - 可考虑买入】")
        for r in strong_signals:
            print(f"  {r['代码']} {r['名称']}: {r['收盘价']:.2f} 评分{r['评分']} "
                  f"多头:{r['均线多头']} 量比:{r['量比']} 突破:{r['箱体突破']}")
    
    if medium_signals:
        print("\n【中等信号 - 观察】")
        for r in medium_signals:
            print(f"  {r['代码']} {r['名称']}: {r['收盘价']:.2f} 评分{r['评分']} 回调:{r['回调幅度']}")
    
    print("\n" + "-"*60)
    print("操作建议:")
    print("  1. 强信号股票可在开盘后30分钟观察，确认企稳后买入")
    print("  2. 建议单只仓位不超过5%，总仓位控制在15%以内")
    print("  3. 止损设置为-5%，止盈目标+10%")
    print("-"*60)
