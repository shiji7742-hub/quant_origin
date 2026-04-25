"""寻找市场上的成功案例并分析共同特征"""
import pandas as pd
import akshare as ak
import ta
from datetime import datetime, timedelta
import time

def find_big_winners(days=30, min_gain=30):
    """
    找出近期涨幅超过min_gain%的股票
    这些就是"成功案例"
    """
    print(f"正在寻找近{days}天涨幅超过{min_gain}%的股票...")
    
    # 获取所有A股
    df = ak.stock_zh_a_spot_em()
    # 只看主板
    df = df[df['代码'].str.match(r'^(60|00)')]
    # 排除ST
    df = df[~df['名称'].str.contains('ST')]
    
    winners = []
    total = len(df)
    
    for idx, row in df.iterrows():
        code = row['代码']
        name = row['名称']
        
        try:
            # 获取历史数据
            hist = ak.stock_zh_a_hist(symbol=code, period='daily', adjust='qfq')
            if hist is None or len(hist) < days:
                continue
            
            hist = hist.tail(days + 5)
            
            # 计算区间涨幅
            start_price = hist.iloc[0]['收盘']
            end_price = hist.iloc[-1]['收盘']
            gain = (end_price - start_price) / start_price * 100
            
            if gain >= min_gain:
                # 找到起涨点（最低点）
                min_idx = hist['收盘'].idxmin()
                min_price = hist.loc[min_idx, '收盘']
                min_date = hist.loc[min_idx, '日期']
                
                # 从最低点算真实涨幅
                real_gain = (end_price - min_price) / min_price * 100
                
                winners.append({
                    'code': code,
                    'name': name,
                    'start_date': str(min_date)[:10],
                    'start_price': min_price,
                    'end_price': end_price,
                    'gain': real_gain
                })
                print(f"  找到: {code} {name} 涨幅 {real_gain:.1f}%")
            
            time.sleep(0.1)  # 避免请求过快
            
        except Exception as e:
            continue
    
    return winners

def analyze_winner_at_start(code, start_date):
    """分析牛股在起涨点的技术特征"""
    try:
        df = ak.stock_zh_a_hist(symbol=code, period='daily', adjust='qfq')
        if df is None:
            return None
        
        df['日期'] = pd.to_datetime(df['日期'])
        target = pd.to_datetime(start_date)
        
        # 获取起涨点之前的数据
        df = df[df['日期'] <= target].tail(30)
        
        if len(df) < 20:
            return None
        
        close = df['收盘']
        
        # 计算指标
        df['MA5'] = close.rolling(5).mean()
        df['MA10'] = close.rolling(10).mean()
        df['MA20'] = close.rolling(20).mean()
        
        macd = ta.trend.MACD(close)
        df['MACD'] = macd.macd()
        df['MACD_signal'] = macd.macd_signal()
        df['RSI'] = ta.momentum.RSIIndicator(close).rsi()
        df['VOL_MA5'] = df['成交量'].rolling(5).mean()
        
        latest = df.iloc[-1]
        
        return {
            'ma_bullish': latest['MA5'] > latest['MA10'] > latest['MA20'],
            'ma_bearish': latest['MA5'] < latest['MA10'] < latest['MA20'],
            'price_above_ma20': latest['收盘'] > latest['MA20'],
            'price_below_ma20': latest['收盘'] < latest['MA20'],
            'macd_golden': latest['MACD'] > latest['MACD_signal'],
            'macd_positive': latest['MACD'] > 0,
            'rsi': latest['RSI'],
            'vol_ratio': latest['成交量'] / latest['VOL_MA5'] if latest['VOL_MA5'] > 0 else 0,
            'price_vs_ma20': (latest['收盘'] - latest['MA20']) / latest['MA20'] * 100,
        }
    except:
        return None

def analyze_winners(winners):
    """分析所有牛股的共同特征"""
    print(f"\n分析 {len(winners)} 只牛股在起涨点的特征...")
    
    features_list = []
    for w in winners:
        print(f"  分析 {w['code']} {w['name']}...")
        features = analyze_winner_at_start(w['code'], w['start_date'])
        if features:
            features['code'] = w['code']
            features['name'] = w['name']
            features['gain'] = w['gain']
            features_list.append(features)
        time.sleep(0.2)
    
    if not features_list:
        print("没有足够的数据进行分析")
        return
    
    df = pd.DataFrame(features_list)
    
    print("\n" + "="*60)
    print(f"牛股起涨点共同特征分析（{len(df)}只样本）")
    print("="*60)
    
    # 布尔特征统计
    bool_features = {
        'ma_bullish': '均线多头排列',
        'ma_bearish': '均线空头排列', 
        'price_above_ma20': '价格在MA20上方',
        'price_below_ma20': '价格在MA20下方',
        'macd_golden': 'MACD金叉',
        'macd_positive': 'MACD在零轴上方',
    }
    
    print("\n【形态特征占比】")
    for col, desc in bool_features.items():
        pct = df[col].mean() * 100
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"  {desc}: {bar} {pct:.0f}%")
    
    print("\n【数值指标统计】")
    print(f"  RSI 平均值: {df['rsi'].mean():.1f} (范围: {df['rsi'].min():.0f}-{df['rsi'].max():.0f})")
    print(f"  量比 平均值: {df['vol_ratio'].mean():.2f}")
    print(f"  距MA20 平均值: {df['price_vs_ma20'].mean():.1f}%")
    
    # 找出最强特征
    print("\n【关键发现】")
    for col, desc in bool_features.items():
        pct = df[col].mean() * 100
        if pct >= 70:
            print(f"  ★ {pct:.0f}%的牛股起涨时 {desc}")
        elif pct <= 30:
            opposite = desc.replace('上方', '下方').replace('多头', '空头')
            print(f"  ★ {100-pct:.0f}%的牛股起涨时 不满足{desc}")
    
    # RSI区间分析
    rsi_low = (df['rsi'] < 40).mean() * 100
    rsi_mid = ((df['rsi'] >= 40) & (df['rsi'] <= 60)).mean() * 100
    rsi_high = (df['rsi'] > 60).mean() * 100
    print(f"\n  RSI分布: 低位(<40)={rsi_low:.0f}%, 中位(40-60)={rsi_mid:.0f}%, 高位(>60)={rsi_high:.0f}%")
    
    return df

def main():
    # 找近30天涨幅超30%的股票
    winners = find_big_winners(days=30, min_gain=30)
    
    if winners:
        print(f"\n共找到 {len(winners)} 只牛股")
        analyze_winners(winners)
    else:
        print("没有找到符合条件的股票，尝试降低涨幅要求")

if __name__ == '__main__':
    main()
