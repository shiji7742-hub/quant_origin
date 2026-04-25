"""分析样本数据，寻找成功模式的共同特征"""
import pandas as pd
import akshare as ak
import ta
from datetime import datetime, timedelta

def load_samples():
    """加载样本数据"""
    samples = []
    with open('samples.txt', 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = line.split(',')
            if len(parts) >= 4:
                samples.append({
                    'code': parts[0].strip(),
                    'buy_date': parts[1].strip(),
                    'sell_date': parts[2].strip(),
                    'result': parts[3].strip(),
                    'note': parts[4].strip() if len(parts) > 4 else ''
                })
    return samples

def get_stock_data_at_date(code, target_date, days_before=30):
    """获取某日期前的股票数据"""
    df = ak.stock_zh_a_hist(symbol=code, period='daily', adjust='qfq')
    if df is None or len(df) == 0:
        return None
    
    df['日期'] = pd.to_datetime(df['日期'])
    target = pd.to_datetime(target_date)
    
    # 获取目标日期之前的数据
    df = df[df['日期'] <= target].tail(days_before + 5)
    return df

def calculate_features(df, buy_date):
    """计算买入时的技术特征"""
    if df is None or len(df) < 20:
        return None
    
    df = df.copy()
    close = df['收盘']
    
    # 均线
    df['MA5'] = close.rolling(5).mean()
    df['MA10'] = close.rolling(10).mean()
    df['MA20'] = close.rolling(20).mean()
    
    # MACD
    macd = ta.trend.MACD(close)
    df['MACD'] = macd.macd()
    df['MACD_signal'] = macd.macd_signal()
    
    # RSI
    df['RSI'] = ta.momentum.RSIIndicator(close).rsi()
    
    # 成交量
    df['VOL_MA5'] = df['成交量'].rolling(5).mean()
    
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    
    features = {
        # 均线状态
        'ma_bullish': latest['MA5'] > latest['MA10'] > latest['MA20'],
        'price_above_ma5': latest['收盘'] > latest['MA5'],
        'price_above_ma20': latest['收盘'] > latest['MA20'],
        'ma5_above_ma10': latest['MA5'] > latest['MA10'],
        
        # MACD状态
        'macd_positive': latest['MACD'] > 0,
        'macd_golden': latest['MACD'] > latest['MACD_signal'],
        
        # RSI
        'rsi': latest['RSI'],
        'rsi_oversold': latest['RSI'] < 30,
        'rsi_overbought': latest['RSI'] > 70,
        
        # 量能
        'vol_ratio': latest['成交量'] / latest['VOL_MA5'] if latest['VOL_MA5'] > 0 else 0,
        'high_volume': latest['成交量'] > latest['VOL_MA5'] * 1.5,
        
        # 涨跌
        'daily_change': (latest['收盘'] - prev['收盘']) / prev['收盘'] * 100 if prev['收盘'] > 0 else 0,
        'is_red': latest['收盘'] > latest['开盘'],
        
        # 位置
        'price_vs_ma20': (latest['收盘'] - latest['MA20']) / latest['MA20'] * 100 if latest['MA20'] > 0 else 0,
        
        # 近期走势
        'gain_5d': (latest['收盘'] - df.iloc[-6]['收盘']) / df.iloc[-6]['收盘'] * 100 if len(df) > 5 else 0,
    }
    
    return features

def analyze_all_samples():
    """分析所有样本，找出成功模式的共同特征"""
    samples = load_samples()
    
    if not samples:
        print("没有样本数据！请在 samples.txt 中添加样本")
        print("格式：代码,买入日期,卖出日期,结果,备注")
        return
    
    print(f"共加载 {len(samples)} 个样本\n")
    
    win_features = []
    loss_features = []
    
    for sample in samples:
        print(f"分析 {sample['code']} ({sample['buy_date']})...")
        df = get_stock_data_at_date(sample['code'], sample['buy_date'])
        features = calculate_features(df, sample['buy_date'])
        
        if features:
            features['code'] = sample['code']
            features['date'] = sample['buy_date']
            features['note'] = sample['note']
            
            if sample['result'] == 'win':
                win_features.append(features)
            else:
                loss_features.append(features)
    
    print("\n" + "="*60)
    print("分析结果")
    print("="*60)
    
    print(f"\n盈利样本: {len(win_features)} 个")
    print(f"亏损样本: {len(loss_features)} 个")
    
    if win_features:
        print("\n【盈利样本的共同特征】")
        win_df = pd.DataFrame(win_features)
        
        # 统计布尔特征
        bool_cols = ['ma_bullish', 'price_above_ma5', 'price_above_ma20', 'ma5_above_ma10',
                     'macd_positive', 'macd_golden', 'rsi_oversold', 'rsi_overbought', 
                     'high_volume', 'is_red']
        
        for col in bool_cols:
            if col in win_df.columns:
                pct = win_df[col].mean() * 100
                if pct > 60:
                    print(f"  ✓ {col}: {pct:.0f}% 的盈利样本满足")
        
        # 统计数值特征
        print(f"\n  RSI 平均值: {win_df['rsi'].mean():.1f}")
        print(f"  量比 平均值: {win_df['vol_ratio'].mean():.2f}")
        print(f"  距MA20 平均值: {win_df['price_vs_ma20'].mean():.1f}%")
        print(f"  5日涨幅 平均值: {win_df['gain_5d'].mean():.1f}%")
    
    if loss_features:
        print("\n【亏损样本的共同特征】")
        loss_df = pd.DataFrame(loss_features)
        
        for col in bool_cols:
            if col in loss_df.columns:
                pct = loss_df[col].mean() * 100
                if pct > 60:
                    print(f"  ✗ {col}: {pct:.0f}% 的亏损样本满足")
        
        print(f"\n  RSI 平均值: {loss_df['rsi'].mean():.1f}")
        print(f"  量比 平均值: {loss_df['vol_ratio'].mean():.2f}")
        print(f"  距MA20 平均值: {loss_df['price_vs_ma20'].mean():.1f}%")
        print(f"  5日涨幅 平均值: {loss_df['gain_5d'].mean():.1f}%")
    
    # 对比分析
    if win_features and loss_features:
        print("\n【关键差异指标】")
        win_df = pd.DataFrame(win_features)
        loss_df = pd.DataFrame(loss_features)
        
        for col in ['rsi', 'vol_ratio', 'price_vs_ma20', 'gain_5d']:
            win_avg = win_df[col].mean()
            loss_avg = loss_df[col].mean()
            diff = win_avg - loss_avg
            if abs(diff) > 5 or (col == 'vol_ratio' and abs(diff) > 0.3):
                print(f"  {col}: 盈利={win_avg:.1f}, 亏损={loss_avg:.1f}, 差异={diff:+.1f}")

if __name__ == '__main__':
    analyze_all_samples()
