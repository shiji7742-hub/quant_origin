"""
板块异动 + 横盘托单 组合策略回测
验证：在潜力板块中选横盘托单个股，胜率是否提升
"""
import requests
import pandas as pd
import numpy as np
import os
from datetime import datetime

def log(msg):
    print(msg, flush=True)

for key in list(os.environ.keys()):
    if 'proxy' in key.lower():
        del os.environ[key]

session = requests.Session()
session.trust_env = False


def get_stock_kline(code, days=400):
    """获取个股K线"""
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
        if len(days_data) < 100:
            return None
        df = pd.DataFrame([d[:6] for d in days_data], 
                        columns=['日期','开盘','收盘','最高','最低','成交量'])
        for col in ['开盘','收盘','最高','最低','成交量']:
            df[col] = df[col].astype(float)
        df['日期'] = pd.to_datetime(df['日期'])
        df['涨跌幅'] = df['收盘'].pct_change() * 100
        return df
    except:
        return None


def get_sector_stocks():
    """获取各板块的成分股"""
    return {
        '人工智能': ['002230', '300474', '002415', '300496', '300624', '002049'],
        '机器人': ['002747', '300024', '300607', '002527', '300124', '002270'],
        '半导体': ['002371', '603501', '688981', '300661', '688012', '603160'],
        '消费电子': ['002475', '002241', '603160', '601138', '002036', '002456'],
        '光伏': ['601012', '002459', '600438', '688599', '300274', '002129'],
        '新能源车': ['002594', '300750', '002466', '002074', '300014', '300207'],
    }


def check_sector_signal_at_idx(sector_returns, idx):
    """在指定位置检测板块异动信号"""
    if idx < 100:
        return False, None
    
    data = sector_returns.iloc[:idx]
    if len(data) < 90:
        return False, None
    
    old_period = data.iloc[:-60]
    recent_30d = data.iloc[-30:]
    recent_10d = data.iloc[-10:]
    recent_5d = data.iloc[-5:]
    
    if len(old_period) < 30:
        return False, None
    
    # 找爆发
    surge_days = old_period[old_period > 5.0]
    if len(surge_days) == 0:
        return False, None
    
    max_surge_value = surge_days.max()
    max_surge_idx = surge_days.idxmax()
    
    # 计算回撤
    after_surge = data[data.index >= max_surge_idx]
    if len(after_surge) < 30:
        return False, None
    
    cumsum = after_surge.cumsum()
    max_gain = cumsum.max()
    current_gain = cumsum.iloc[-1]
    drawdown = max_gain - current_gain
    
    if drawdown < 12 or drawdown > 25:
        return False, None
    
    recent_30d_sum = recent_30d.sum()
    recent_10d_sum = recent_10d.sum()
    recent_5d_sum = recent_5d.sum()
    
    if recent_30d_sum > 5:
        return False, None
    if recent_10d_sum < -3:
        return False, None
    if recent_5d_sum < -2:
        return False, None
    
    days_since = (data.index[-1] - max_surge_idx).days
    
    return True, {
        'drawdown': drawdown,
        'days_since': days_since,
        'recent_5d': recent_5d_sum,
    }


def check_sideways_at_idx(df, idx):
    """在指定位置检测横盘托单信号"""
    if idx < 5:
        return False, None
    
    sideways_period = df.iloc[idx-3:idx]
    high = sideways_period['最高'].max()
    low = sideways_period['最低'].min()
    avg = sideways_period['收盘'].mean()
    
    volatility = (high - low) / avg * 100
    if volatility > 5.0:
        return False, None
    
    support = low
    today = df.iloc[idx]
    distance = (today['最低'] - support) / support * 100
    
    if not (-3.0 <= distance <= 0.5):
        return False, None
    
    if today['最低'] < support * 0.98:
        return False, None
    if today['收盘'] <= support * 1.001:
        return False, None
    
    return True, {
        'support': support,
        'volatility': volatility,
    }


def run_backtest():
    log("="*70)
    log("板块异动 + 横盘托单 组合策略回测")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*70)
    
    sector_stocks = get_sector_stocks()
    
    # 获取所有数据
    log("\n[1] 获取数据...")
    
    all_stock_data = {}
    sector_trends = {}
    
    for sector, stocks in sector_stocks.items():
        log(f"  {sector}...")
        
        # 获取个股数据
        stock_data = {}
        all_returns = []
        for code in stocks:
            df = get_stock_kline(code, days=400)
            if df is not None and len(df) > 100:
                stock_data[code] = df
                all_returns.append(df[['日期', '涨跌幅']].set_index('日期')['涨跌幅'])
        
        all_stock_data[sector] = stock_data
        
        # 计算板块走势
        if all_returns:
            combined = pd.concat(all_returns, axis=1)
            sector_trends[sector] = combined.mean(axis=1)
            log(f"    {len(stock_data)}只股票, {len(sector_trends[sector])}天数据")
    
    log(f"\n  共{len(sector_trends)}个板块数据")
    
    # 回测
    log("\n[2] 开始回测...")
    
    # 策略1：仅横盘托单（不考虑板块）
    all_sideways_signals = []
    
    # 策略2：板块异动 + 横盘托单
    combo_signals = []
    
    for sector, stock_data in all_stock_data.items():
        sector_trend = sector_trends.get(sector)
        if sector_trend is None:
            continue
        
        for code, df in stock_data.items():
            # 遍历每个交易日
            for idx in range(100, len(df) - 30, 3):
                signal_date = df.iloc[idx]['日期']
                
                # 检测横盘托单
                is_sideways, sideways_info = check_sideways_at_idx(df, idx)
                
                if not is_sideways:
                    continue
                
                # 计算未来收益
                buy_price = df.iloc[idx]['收盘']
                future_5d = (df.iloc[idx+5]['收盘'] - buy_price) / buy_price * 100 if idx+5 < len(df) else None
                future_10d = (df.iloc[idx+10]['收盘'] - buy_price) / buy_price * 100 if idx+10 < len(df) else None
                future_20d = (df.iloc[idx+20]['收盘'] - buy_price) / buy_price * 100 if idx+20 < len(df) else None
                
                if future_10d is None:
                    continue
                
                # 仅横盘托单信号
                all_sideways_signals.append({
                    'sector': sector,
                    'code': code,
                    'date': signal_date,
                    'future_5d': future_5d,
                    'future_10d': future_10d,
                    'future_20d': future_20d,
                })
                
                # 检测板块异动
                try:
                    sector_idx = sector_trend.index.get_indexer([signal_date], method='ffill')[0]
                    if sector_idx >= 0:
                        is_sector_signal, sector_info = check_sector_signal_at_idx(sector_trend, sector_idx)
                        
                        if is_sector_signal:
                            combo_signals.append({
                                'sector': sector,
                                'code': code,
                                'date': signal_date,
                                'sector_drawdown': sector_info['drawdown'],
                                'future_5d': future_5d,
                                'future_10d': future_10d,
                                'future_20d': future_20d,
                            })
                except:
                    pass
    
    log(f"\n  仅横盘托单信号: {len(all_sideways_signals)}个")
    log(f"  板块+托单组合信号: {len(combo_signals)}个")
    
    # 统计结果
    log("\n" + "="*70)
    log("回测结果对比")
    log("="*70)
    
    df_sideways = pd.DataFrame(all_sideways_signals)
    df_combo = pd.DataFrame(combo_signals)
    
    log(f"\n{'策略':<20} {'信号数':>8} {'5日胜率':>10} {'10日胜率':>10} {'20日胜率':>10}")
    log("-" * 60)
    
    for name, df in [('仅横盘托单', df_sideways), ('板块+托单组合', df_combo)]:
        if len(df) == 0:
            continue
        
        wr_5d = (df['future_5d'] > 0).sum() / len(df) * 100
        wr_10d = (df['future_10d'] > 0).sum() / len(df) * 100
        wr_20d = (df['future_20d'].dropna() > 0).sum() / len(df['future_20d'].dropna()) * 100
        
        log(f"{name:<20} {len(df):>8} {wr_5d:>9.1f}% {wr_10d:>9.1f}% {wr_20d:>9.1f}%")
    
    log(f"\n{'策略':<20} {'5日均收':>10} {'10日均收':>10} {'20日均收':>10}")
    log("-" * 60)
    
    for name, df in [('仅横盘托单', df_sideways), ('板块+托单组合', df_combo)]:
        if len(df) == 0:
            continue
        
        avg_5d = df['future_5d'].mean()
        avg_10d = df['future_10d'].mean()
        avg_20d = df['future_20d'].dropna().mean()
        
        log(f"{name:<20} {avg_5d:>+9.2f}% {avg_10d:>+9.2f}% {avg_20d:>+9.2f}%")
    
    # 按板块统计组合策略
    if len(df_combo) > 0:
        log("\n" + "="*70)
        log("组合策略按板块统计")
        log("="*70)
        
        sector_stats = df_combo.groupby('sector').agg({
            'future_10d': ['count', 'mean', lambda x: (x > 0).sum() / len(x) * 100]
        }).round(2)
        sector_stats.columns = ['信号数', '10日均收', '10日胜率']
        sector_stats = sector_stats.sort_values('10日胜率', ascending=False)
        
        for sector, row in sector_stats.iterrows():
            log(f"  {sector}: {int(row['信号数'])}个信号, 胜率{row['10日胜率']:.1f}%, 均收{row['10日均收']:+.2f}%")
    
    # 提升效果
    log("\n" + "="*70)
    log("组合策略效果")
    log("="*70)
    
    if len(df_sideways) > 0 and len(df_combo) > 0:
        sideways_10d_wr = (df_sideways['future_10d'] > 0).sum() / len(df_sideways) * 100
        combo_10d_wr = (df_combo['future_10d'] > 0).sum() / len(df_combo) * 100
        
        sideways_10d_avg = df_sideways['future_10d'].mean()
        combo_10d_avg = df_combo['future_10d'].mean()
        
        log(f"""
【对比分析】

1. 胜率对比（10日）:
   - 仅横盘托单: {sideways_10d_wr:.1f}%
   - 板块+托单组合: {combo_10d_wr:.1f}%
   - 提升: {combo_10d_wr - sideways_10d_wr:+.1f}%

2. 收益对比（10日）:
   - 仅横盘托单: {sideways_10d_avg:+.2f}%
   - 板块+托单组合: {combo_10d_avg:+.2f}%
   - 提升: {combo_10d_avg - sideways_10d_avg:+.2f}%

【结论】
{'组合策略有效！胜率和收益都有提升。' if combo_10d_wr > sideways_10d_wr else '组合策略效果不明显，可能需要调整参数。'}

【使用建议】
1. 优先选择板块异动+横盘托单的双重信号
2. 如果没有双重信号，可以考虑仅横盘托单
3. 科技成长板块（人工智能、半导体、消费电子）效果最好
4. 避免在证券、建材等传统板块使用
""")
    
    # 保存结果
    fname = f"组合策略回测_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    with pd.ExcelWriter(fname, engine='openpyxl') as writer:
        df_sideways.to_excel(writer, sheet_name='仅横盘托单', index=False)
        if len(df_combo) > 0:
            df_combo.to_excel(writer, sheet_name='板块托单组合', index=False)
    log(f"\n已保存: {fname}")


if __name__ == "__main__":
    run_backtest()
