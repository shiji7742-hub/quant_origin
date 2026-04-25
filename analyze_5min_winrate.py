"""
分析分时托单策略的高胜率条件
"""
import requests
import pandas as pd
import numpy as np
import os
from datetime import datetime
import json

def log(msg):
    print(msg, flush=True)

for key in list(os.environ.keys()):
    if 'proxy' in key.lower():
        del os.environ[key]

session = requests.Session()
session.trust_env = False
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
})


def get_5min_kline_sina(code):
    """从新浪获取5分钟K线"""
    code = str(code).zfill(6)
    symbol = f'sh{code}' if code.startswith('6') else f'sz{code}'
    url = f'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={symbol}&scale=5&ma=no&datalen=500'
    try:
        r = session.get(url, timeout=15)
        text = r.text
        if not text or text == 'null':
            return None
        data = json.loads(text)
        if not data or len(data) < 50:
            return None
        df = pd.DataFrame(data)
        df['day'] = pd.to_datetime(df['day'])
        df['date'] = df['day'].dt.strftime('%Y%m%d')
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        df = df.rename(columns={
            'open': '开盘', 'high': '最高', 'low': '最低', 
            'close': '收盘', 'volume': '成交量', 'day': '时间'
        })
        return df
    except:
        return None


def get_stock_kline(code, days=60):
    """获取日K线"""
    code = str(code).zfill(6)
    kcode = f'sh{code}' if code.startswith('6') else f'sz{code}'
    url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={kcode},day,,,{days},qfq'
    try:
        r = session.get(url, timeout=10)
        data = r.json()
        if not data.get('data'):
            return None
        stock_data = data['data'].get(kcode) or data['data'].get(kcode.upper())
        if not stock_data or 'qfqday' not in stock_data:
            return None
        days_data = stock_data['qfqday']
        df = pd.DataFrame([d[:6] for d in days_data], 
                        columns=['日期','开盘','收盘','最高','最低','成交量'])
        for col in ['开盘','收盘','最高','最低','成交量']:
            df[col] = df[col].astype(float)
        df['日期'] = pd.to_datetime(df['日期'])
        df['涨跌幅'] = df['收盘'].pct_change() * 100
        return df
    except:
        return None


def check_intraday_support(df_5min, date_str):
    """检测分时托单信号"""
    day_bars = df_5min[df_5min['date'] == date_str].copy()
    if len(day_bars) < 20:
        return False, None
    
    high = day_bars['最高'].max()
    low = day_bars['最低'].min()
    avg_price = day_bars['收盘'].mean()
    current = day_bars.iloc[-1]['收盘']
    open_price = day_bars.iloc[0]['开盘']
    
    volatility = (high - low) / avg_price * 100
    if volatility > 5.0:  # 放宽一点收集更多数据
        return False, None
    
    day_bars['下影线'] = day_bars.apply(
        lambda x: min(x['开盘'], x['收盘']) - x['最低'], axis=1)
    day_bars['实体'] = abs(day_bars['收盘'] - day_bars['开盘'])
    
    support_bars = day_bars[day_bars['下影线'] > day_bars['实体'] * 0.5]
    support_count = len(support_bars)
    
    if support_count < 2:
        return False, None
    
    day_bars['涨跌'] = day_bars['收盘'] - day_bars['开盘']
    down_bars = day_bars[day_bars['涨跌'] < 0]
    up_bars = day_bars[day_bars['涨跌'] > 0]
    
    if len(down_bars) < 2 or len(up_bars) < 2:
        return False, None
    
    avg_down_vol = down_bars['成交量'].mean()
    avg_up_vol = up_bars['成交量'].mean()
    vol_ratio = avg_up_vol / avg_down_vol if avg_down_vol > 0 else 1
    
    position = (current - low) / (high - low) * 100 if high > low else 50
    
    today_change = (current - open_price) / open_price * 100
    
    if len(support_bars) > 0:
        support_vol = support_bars['成交量'].mean()
        avg_vol = day_bars['成交量'].mean()
        big_order_ratio = support_vol / avg_vol if avg_vol > 0 else 1
    else:
        big_order_ratio = 1
    
    # 尾盘情况（最后4根5分钟K线）
    last_4 = day_bars.iloc[-4:]
    tail_trend = (last_4.iloc[-1]['收盘'] - last_4.iloc[0]['开盘']) / last_4.iloc[0]['开盘'] * 100
    
    return True, {
        'volatility': volatility,
        'support_count': support_count,
        'vol_ratio': vol_ratio,
        'position': position,
        'today_change': today_change,
        'big_order_ratio': big_order_ratio,
        'tail_trend': tail_trend,
        'close': current,
        'low': low,
        'high': high,
    }


def get_sector_stocks():
    """获取科技板块成分股"""
    return {
        '人工智能': ['002230', '300474', '002415', '300496', '300624', '002049'],
        '机器人': ['002747', '300024', '300607', '002527', '300124', '002270'],
        '半导体': ['002371', '603501', '300661', '688012', '603160', '688981'],
        '消费电子': ['002475', '002241', '601138', '002036', '002456', '603160'],
        '光伏': ['601012', '002459', '600438', '300274', '002129', '688599'],
        '新能源车': ['002594', '300750', '002466', '002074', '300014', '300207'],
    }


def run_analysis():
    log("="*70)
    log("分时托单策略高胜率条件分析")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*70)
    
    sector_stocks = get_sector_stocks()
    all_stocks = []
    for sector, stocks in sector_stocks.items():
        for code in stocks:
            all_stocks.append((code, sector))
    
    log(f"\n收集数据: {len(all_stocks)}只股票")
    
    all_signals = []
    
    for code, sector in all_stocks:
        df_5min = get_5min_kline_sina(code)
        if df_5min is None or len(df_5min) < 100:
            continue
        
        df_daily = get_stock_kline(code, days=60)
        if df_daily is None:
            continue
        
        dates = df_5min['date'].unique()
        
        for date_str in dates[:-5]:
            is_signal, info = check_intraday_support(df_5min, date_str)
            
            if not is_signal:
                continue
            
            try:
                signal_date_fmt = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                daily_dates = df_daily['日期'].astype(str).tolist()
                
                signal_idx = None
                for idx, d in enumerate(daily_dates):
                    if signal_date_fmt in d:
                        signal_idx = idx
                        break
                
                if signal_idx is None or signal_idx + 5 >= len(df_daily):
                    continue
                
                # 前几天的走势
                if signal_idx >= 5:
                    prev_5d_return = (df_daily.iloc[signal_idx]['收盘'] - df_daily.iloc[signal_idx-5]['收盘']) / df_daily.iloc[signal_idx-5]['收盘'] * 100
                    prev_10d_high = df_daily.iloc[signal_idx-10:signal_idx]['最高'].max() if signal_idx >= 10 else df_daily.iloc[:signal_idx]['最高'].max()
                    dist_from_high = (df_daily.iloc[signal_idx]['收盘'] - prev_10d_high) / prev_10d_high * 100
                else:
                    prev_5d_return = 0
                    dist_from_high = 0
                
                buy_price = df_daily.iloc[signal_idx]['收盘']
                
                future_1d = (df_daily.iloc[signal_idx+1]['收盘'] - buy_price) / buy_price * 100
                future_3d = (df_daily.iloc[signal_idx+3]['收盘'] - buy_price) / buy_price * 100
                future_5d = (df_daily.iloc[signal_idx+5]['收盘'] - buy_price) / buy_price * 100
                
                all_signals.append({
                    'code': code,
                    'sector': sector,
                    'date': date_str,
                    'volatility': info['volatility'],
                    'support_count': info['support_count'],
                    'vol_ratio': info['vol_ratio'],
                    'position': info['position'],
                    'today_change': info['today_change'],
                    'big_order_ratio': info['big_order_ratio'],
                    'tail_trend': info['tail_trend'],
                    'prev_5d_return': prev_5d_return,
                    'dist_from_high': dist_from_high,
                    'future_1d': future_1d,
                    'future_3d': future_3d,
                    'future_5d': future_5d,
                })
            except:
                continue
    
    df = pd.DataFrame(all_signals)
    log(f"\n总信号数: {len(df)}个")
    
    if len(df) == 0:
        log("无数据")
        return
    
    df['win_3d'] = df['future_3d'] > 0
    
    # =============================================
    log("\n" + "="*70)
    log("各维度胜率分析")
    log("="*70)
    
    # 1. 量比（上涨量/下跌量）
    log("\n【1. 量比（上涨量/下跌量）】← 最关键！")
    log("-" * 50)
    bins = [0, 0.9, 1.0, 1.1, 1.2, 1.5, 10]
    labels = ['<0.9', '0.9-1.0', '1.0-1.1', '1.1-1.2', '1.2-1.5', '>1.5']
    df['量比分组'] = pd.cut(df['vol_ratio'], bins=bins, labels=labels)
    
    for group in labels:
        subset = df[df['量比分组'] == group]
        if len(subset) >= 2:
            wr = subset['win_3d'].sum() / len(subset) * 100
            ar = subset['future_3d'].mean()
            log(f"  {group:>10}: {len(subset):>3}个, 胜率{wr:>5.1f}%, 均收{ar:>+6.2f}%")
    
    # 2. 托单次数
    log("\n【2. 托单次数（下探收回次数）】")
    log("-" * 50)
    bins = [0, 5, 8, 12, 20, 100]
    labels = ['2-5次', '6-8次', '9-12次', '13-20次', '>20次']
    df['托单分组'] = pd.cut(df['support_count'], bins=bins, labels=labels)
    
    for group in labels:
        subset = df[df['托单分组'] == group]
        if len(subset) >= 2:
            wr = subset['win_3d'].sum() / len(subset) * 100
            ar = subset['future_3d'].mean()
            log(f"  {group:>10}: {len(subset):>3}个, 胜率{wr:>5.1f}%, 均收{ar:>+6.2f}%")
    
    # 3. 收盘位置
    log("\n【3. 收盘位置（分时高低位）】")
    log("-" * 50)
    bins = [0, 50, 60, 70, 80, 90, 100]
    labels = ['<50%', '50-60%', '60-70%', '70-80%', '80-90%', '>90%']
    df['位置分组'] = pd.cut(df['position'], bins=bins, labels=labels)
    
    for group in labels:
        subset = df[df['位置分组'] == group]
        if len(subset) >= 2:
            wr = subset['win_3d'].sum() / len(subset) * 100
            ar = subset['future_3d'].mean()
            log(f"  {group:>10}: {len(subset):>3}个, 胜率{wr:>5.1f}%, 均收{ar:>+6.2f}%")
    
    # 4. 今日涨跌幅
    log("\n【4. 今日涨跌幅】")
    log("-" * 50)
    bins = [-10, -2, 0, 1, 2, 3, 10]
    labels = ['<-2%', '-2~0%', '0~+1%', '+1~+2%', '+2~+3%', '>+3%']
    df['涨跌分组'] = pd.cut(df['today_change'], bins=bins, labels=labels)
    
    for group in labels:
        subset = df[df['涨跌分组'] == group]
        if len(subset) >= 2:
            wr = subset['win_3d'].sum() / len(subset) * 100
            ar = subset['future_3d'].mean()
            log(f"  {group:>10}: {len(subset):>3}个, 胜率{wr:>5.1f}%, 均收{ar:>+6.2f}%")
    
    # 5. 波动率
    log("\n【5. 分时波动率】")
    log("-" * 50)
    bins = [0, 2, 3, 4, 5]
    labels = ['<2%', '2-3%', '3-4%', '4-5%']
    df['波动分组'] = pd.cut(df['volatility'], bins=bins, labels=labels)
    
    for group in labels:
        subset = df[df['波动分组'] == group]
        if len(subset) >= 2:
            wr = subset['win_3d'].sum() / len(subset) * 100
            ar = subset['future_3d'].mean()
            log(f"  {group:>10}: {len(subset):>3}个, 胜率{wr:>5.1f}%, 均收{ar:>+6.2f}%")
    
    # 6. 尾盘走势
    log("\n【6. 尾盘走势（最后20分钟）】")
    log("-" * 50)
    bins = [-10, -0.5, 0, 0.5, 1, 10]
    labels = ['下跌>0.5%', '微跌', '微涨', '上涨0.5-1%', '上涨>1%']
    df['尾盘分组'] = pd.cut(df['tail_trend'], bins=bins, labels=labels)
    
    for group in labels:
        subset = df[df['尾盘分组'] == group]
        if len(subset) >= 2:
            wr = subset['win_3d'].sum() / len(subset) * 100
            ar = subset['future_3d'].mean()
            log(f"  {group:>12}: {len(subset):>3}个, 胜率{wr:>5.1f}%, 均收{ar:>+6.2f}%")
    
    # 7. 前5日涨幅
    log("\n【7. 前5日涨幅（是否超涨/超跌）】")
    log("-" * 50)
    bins = [-30, -5, 0, 5, 10, 50]
    labels = ['跌>5%', '跌0-5%', '涨0-5%', '涨5-10%', '涨>10%']
    df['前5日分组'] = pd.cut(df['prev_5d_return'], bins=bins, labels=labels)
    
    for group in labels:
        subset = df[df['前5日分组'] == group]
        if len(subset) >= 2:
            wr = subset['win_3d'].sum() / len(subset) * 100
            ar = subset['future_3d'].mean()
            log(f"  {group:>10}: {len(subset):>3}个, 胜率{wr:>5.1f}%, 均收{ar:>+6.2f}%")
    
    # 8. 板块
    log("\n【8. 板块】")
    log("-" * 50)
    sector_stats = df.groupby('sector').agg({
        'future_3d': ['count', 'mean'],
        'win_3d': 'mean'
    }).round(3)
    sector_stats.columns = ['信号数', '均收', '胜率']
    sector_stats['胜率'] = sector_stats['胜率'] * 100
    sector_stats = sector_stats.sort_values('胜率', ascending=False)
    
    for sector, row in sector_stats.iterrows():
        log(f"  {sector:>10}: {int(row['信号数']):>3}个, 胜率{row['胜率']:>5.1f}%, 均收{row['均收']:>+6.2f}%")
    
    # =============================================
    log("\n" + "="*70)
    log("高胜率条件组合")
    log("="*70)
    
    combos = [
        # 量比相关
        ('量比>1.2', df['vol_ratio'] > 1.2),
        ('量比>1.5', df['vol_ratio'] > 1.5),
        
        # 位置相关
        ('位置>80%', df['position'] > 80),
        ('位置>90%', df['position'] > 90),
        
        # 涨跌相关
        ('今日小涨(0-2%)', (df['today_change'] >= 0) & (df['today_change'] <= 2)),
        
        # 尾盘
        ('尾盘上涨', df['tail_trend'] > 0.5),
        
        # 组合
        ('量比>1.2 + 位置>80%', (df['vol_ratio'] > 1.2) & (df['position'] > 80)),
        ('量比>1.2 + 今日小涨', (df['vol_ratio'] > 1.2) & (df['today_change'] >= 0) & (df['today_change'] <= 2)),
        ('量比>1.2 + 尾盘上涨', (df['vol_ratio'] > 1.2) & (df['tail_trend'] > 0.5)),
        ('位置>80% + 尾盘上涨', (df['position'] > 80) & (df['tail_trend'] > 0.5)),
        ('量比>1.2 + 位置>80% + 尾盘上涨', (df['vol_ratio'] > 1.2) & (df['position'] > 80) & (df['tail_trend'] > 0.5)),
        
        # 热门板块
        ('人工智能板块', df['sector'] == '人工智能'),
        ('半导体板块', df['sector'] == '半导体'),
        ('人工智能 + 量比>1.0', (df['sector'] == '人工智能') & (df['vol_ratio'] > 1.0)),
    ]
    
    results = []
    for name, condition in combos:
        subset = df[condition]
        if len(subset) >= 2:
            wr = subset['win_3d'].sum() / len(subset) * 100
            ar = subset['future_3d'].mean()
            results.append({
                'condition': name,
                'count': len(subset),
                'win_rate': wr,
                'avg_return': ar,
            })
    
    results_df = pd.DataFrame(results)
    results_df = results_df.sort_values('win_rate', ascending=False)
    
    log(f"\n{'条件':<35} {'信号数':>8} {'胜率':>10} {'均收':>10}")
    log("-" * 70)
    
    for _, row in results_df.iterrows():
        log(f"{row['condition']:<35} {row['count']:>8} {row['win_rate']:>9.1f}% {row['avg_return']:>+9.2f}%")
    
    # =============================================
    log("\n" + "="*70)
    log("策略总结：什么时候胜率高？")
    log("="*70)
    
    log("""
【最关键因素：量比（上涨量/下跌量）】
  - 量比 > 1.2：大单在托，胜率高
  - 量比 > 1.5：强势托单，胜率更高
  - 量比 < 1.0：下跌量大，不是真托单

【高胜率情况】
  1. 量比 > 1.2（上涨K线量 > 下跌K线量 20%以上）
  2. 收盘位置 > 80%（收在分时高位）
  3. 尾盘拉升（最后20分钟上涨）
  4. 今日微涨（0-2%，不追高）
  5. 人工智能/半导体等热门板块

【最佳组合】
  量比 > 1.2 + 位置 > 80% + 尾盘上涨

【避免的情况】
  1. 量比 < 1.0（下跌量大于上涨量）
  2. 收盘位置 < 60%（没守住）
  3. 今日大跌（<-2%）
  4. 尾盘下跌（主力出货）
""")
    
    # 保存
    fname = f"分时托单胜率分析_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df.to_excel(fname, index=False)
    log(f"\n已保存: {fname}")


if __name__ == "__main__":
    run_analysis()
