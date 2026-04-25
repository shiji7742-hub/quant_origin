"""分析单只股票"""
import akshare as ak
import ta
import pandas as pd
import sys

def analyze(name_or_code):
    # 获取所有股票
    df = ak.stock_zh_a_spot_em()
    
    # 查找股票
    if name_or_code.isdigit():
        stock = df[df['代码'] == name_or_code.zfill(6)]
    else:
        stock = df[df['名称'].str.contains(name_or_code)]
    
    if len(stock) == 0:
        print(f"未找到股票: {name_or_code}")
        return
    
    row = stock.iloc[0]
    code = row['代码']
    name = row['名称']
    
    print(f"{'='*50}")
    print(f"{code} {name}")
    print(f"{'='*50}")
    print(f"最新价: {row['最新价']}  涨跌幅: {row['涨跌幅']}%")
    print(f"成交额: {row['成交额']/1e8:.2f}亿  换手率: {row['换手率']}%")
    
    # 获取历史数据
    hist = ak.stock_zh_a_hist(symbol=code, period='daily', adjust='qfq')
    if hist is None or len(hist) < 25:
        print("历史数据不足")
        return
    
    hist = hist.tail(60)
    close = hist['收盘']
    
    # 计算指标
    hist['MA5'] = close.rolling(5).mean()
    hist['MA10'] = close.rolling(10).mean()
    hist['MA20'] = close.rolling(20).mean()
    
    macd = ta.trend.MACD(close)
    hist['MACD'] = macd.macd()
    hist['MACD_signal'] = macd.macd_signal()
    hist['RSI'] = ta.momentum.RSIIndicator(close).rsi()
    hist['VOL_MA5'] = hist['成交量'].rolling(5).mean()
    
    latest = hist.iloc[-1]
    
    print(f"\n【技术指标】")
    print(f"MA5/MA10/MA20: {latest['MA5']:.2f} / {latest['MA10']:.2f} / {latest['MA20']:.2f}")
    
    if latest['MA5'] > latest['MA10'] > latest['MA20']:
        print("均线状态: 多头排列 ✓")
    elif latest['MA5'] < latest['MA10'] < latest['MA20']:
        print("均线状态: 空头排列 ✗")
    else:
        print("均线状态: 震荡整理")
    
    if latest['MACD'] > latest['MACD_signal']:
        print(f"MACD: 金叉 ✓ ({latest['MACD']:.3f})")
    else:
        print(f"MACD: 死叉 ({latest['MACD']:.3f})")
    
    rsi = latest['RSI']
    rsi_status = "超买⚠️" if rsi > 70 else ("超卖" if rsi < 30 else "正常")
    print(f"RSI: {rsi:.1f} ({rsi_status})")
    
    vol_ratio = latest['成交量'] / latest['VOL_MA5'] if latest['VOL_MA5'] > 0 else 0
    print(f"量比: {vol_ratio:.2f}")
    
    price_vs_ma20 = (latest['收盘'] - latest['MA20']) / latest['MA20'] * 100
    print(f"距MA20: {price_vs_ma20:.1f}%")
    
    # 近期走势
    print(f"\n【近期走势】")
    gain_5d = (latest['收盘'] - hist.iloc[-6]['收盘']) / hist.iloc[-6]['收盘'] * 100
    gain_20d = (latest['收盘'] - hist.iloc[-21]['收盘']) / hist.iloc[-21]['收盘'] * 100
    print(f"5日涨幅: {gain_5d:+.1f}%")
    print(f"20日涨幅: {gain_20d:+.1f}%")
    
    # 综合评价
    print(f"\n【综合评价】")
    score = 0
    reasons = []
    
    if latest['MA5'] > latest['MA10'] > latest['MA20']:
        score += 2
        reasons.append("均线多头")
    if latest['MACD'] > latest['MACD_signal']:
        score += 2
        reasons.append("MACD金叉")
    if 30 < rsi < 70:
        score += 1
        reasons.append("RSI适中")
    if vol_ratio > 1:
        score += 1
        reasons.append("量能充足")
    if rsi > 80:
        score -= 2
        reasons.append("RSI过高风险")
    if price_vs_ma20 > 30:
        score -= 1
        reasons.append("偏离MA20过大")
    
    if score >= 4:
        print(f"评分: {score}/6 - 技术面较好 👍")
    elif score >= 2:
        print(f"评分: {score}/6 - 技术面一般")
    else:
        print(f"评分: {score}/6 - 技术面较弱 ⚠️")
    
    print(f"理由: {', '.join(reasons)}")

if __name__ == '__main__':
    if len(sys.argv) > 1:
        analyze(sys.argv[1])
    else:
        analyze('药捷安康')
