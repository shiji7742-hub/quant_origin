"""分析港股"""
import akshare as ak
import ta
import pandas as pd

# 获取港股实时数据
df = ak.stock_hk_spot_em()
stock = df[df['代码'] == '02617'].iloc[0]

print('='*50)
print('02617 药捷安康-B (港股)')
print('='*50)
print(f"最新价: {stock['最新价']} 港元")
print(f"涨跌幅: {stock['涨跌幅']}%")
print(f"成交额: {stock['成交额']/1e8:.2f}亿")

# 获取历史数据
try:
    hist = ak.stock_hk_hist(symbol='02617', period='daily', adjust='qfq')
    if hist is not None and len(hist) > 20:
        hist = hist.tail(60)
        close = hist['收盘']
        
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
            print('均线状态: 多头排列')
        elif latest['MA5'] < latest['MA10'] < latest['MA20']:
            print('均线状态: 空头排列')
        else:
            print('均线状态: 震荡')
        
        macd_status = '金叉' if latest['MACD'] > latest['MACD_signal'] else '死叉'
        print(f"MACD: {macd_status}")
        print(f"RSI: {latest['RSI']:.1f}")
        
        vol_ratio = latest['成交量'] / latest['VOL_MA5'] if latest['VOL_MA5'] > 0 else 0
        print(f"量比: {vol_ratio:.2f}")
        
        price_vs_ma20 = (latest['收盘'] - latest['MA20']) / latest['MA20'] * 100
        print(f"距MA20: {price_vs_ma20:.1f}%")
        
        # 近期走势
        gain_5d = (latest['收盘'] - hist.iloc[-6]['收盘']) / hist.iloc[-6]['收盘'] * 100
        gain_20d = (latest['收盘'] - hist.iloc[-21]['收盘']) / hist.iloc[-21]['收盘'] * 100 if len(hist) > 20 else 0
        print(f"\n【近期走势】")
        print(f"5日涨幅: {gain_5d:+.1f}%")
        print(f"20日涨幅: {gain_20d:+.1f}%")
        
        # 综合评价
        print(f"\n【综合评价】")
        if stock['涨跌幅'] < -10:
            print("今日大跌超10%，短期风险较大")
        if latest['RSI'] < 30:
            print("RSI超卖，可能有反弹机会")
        elif latest['RSI'] > 70:
            print("RSI超买，注意回调风险")
            
except Exception as e:
    print(f'获取历史数据失败: {e}')
