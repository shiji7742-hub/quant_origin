"""检查持仓股票技术面"""
import pandas as pd
import akshare as ak
import ta

def calculate_indicators(df):
    if df is None or len(df) < 20:
        return df
    df = df.copy()
    close = df['收盘']
    df['MA5'] = close.rolling(5).mean()
    df['MA10'] = close.rolling(10).mean()
    df['MA20'] = close.rolling(20).mean()
    macd = ta.trend.MACD(close)
    df['MACD'] = macd.macd()
    df['MACD_signal'] = macd.macd_signal()
    df['RSI'] = ta.momentum.RSIIndicator(close).rsi()
    df['VOL_MA5'] = df['成交量'].rolling(5).mean()
    return df

def analyze_stock(code):
    df = ak.stock_zh_a_hist(symbol=code, period='daily', adjust='qfq')
    if df is None or len(df) < 20:
        return None
    df = df.tail(60)
    df = calculate_indicators(df)
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    # 均线状态
    ma_bullish = latest['MA5'] > latest['MA10'] > latest['MA20']
    ma_bearish = latest['MA5'] < latest['MA10'] < latest['MA20']
    
    # MACD状态
    macd_golden = latest['MACD'] > latest['MACD_signal']
    
    # 量比
    vol_ratio = latest['成交量'] / latest['VOL_MA5'] if latest['VOL_MA5'] > 0 else 0
    
    # RSI
    rsi = latest['RSI']
    rsi_status = '超买' if rsi > 70 else ('超卖' if rsi < 30 else '正常')
    
    # 价格位置
    price_vs_ma20 = (latest['收盘'] - latest['MA20']) / latest['MA20'] * 100
    
    # 问题诊断
    problems = []
    if ma_bearish:
        problems.append('均线空头排列')
    if not macd_golden:
        problems.append('MACD死叉')
    if rsi > 70:
        problems.append('RSI超买')
    if price_vs_ma20 < -5:
        problems.append(f'跌破MA20({price_vs_ma20:.1f}%)')
    if vol_ratio < 0.5:
        problems.append('缩量明显')
    
    return {
        'MA状态': '多头' if ma_bullish else ('空头' if ma_bearish else '震荡'),
        'MACD': '金叉' if macd_golden else '死叉',
        'RSI': f'{rsi:.1f}({rsi_status})',
        '量比': f'{vol_ratio:.2f}',
        '距MA20': f'{price_vs_ma20:.1f}%',
        '问题': problems
    }

# 持仓股票
stocks = [
    ('600280', '中央商场'),
    ('600990', '四创电子'),
    ('002187', '广百股份'),
    ('600650', '锦江在线'),
    ('003033', '征和工业'),
    ('002251', '步步高'),
    ('600737', '中粮糖业'),
    ('603601', '再升科技'),
    ('002309', '中利集团'),
]

print('='*70)
print('持仓股票技术面诊断')
print('='*70)

should_sell = []
should_hold = []

for code, name in stocks:
    result = analyze_stock(code)
    if result:
        print(f'\n{code} {name}:')
        print(f"  MA状态: {result['MA状态']} | MACD: {result['MACD']} | RSI: {result['RSI']}")
        print(f"  量比: {result['量比']} | 距MA20: {result['距MA20']}")
        if result['问题']:
            print(f"  ⚠️ 问题: {', '.join(result['问题'])}")
            should_sell.append((code, name, result['问题']))
        else:
            should_hold.append((code, name))

print('\n' + '='*70)
print('建议筛掉的股票（有技术问题）:')
print('='*70)
for code, name, problems in should_sell:
    print(f"  ❌ {code} {name}: {', '.join(problems)}")

print('\n建议继续持有:')
for code, name in should_hold:
    print(f'  ✓ {code} {name}')
