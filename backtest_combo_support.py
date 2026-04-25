"""
板块异动 + 托单 组合策略回测
结合板块筛选，看看能否提升托单策略效果
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
    """获取科技板块成分股"""
    return {
        '人工智能': ['002230', '300474', '002415', '300496', '300624', '002049'],
        '机器人': ['002747', '300024', '300607', '002527', '300124', '002270'],
        '半导体': ['002371', '603501', '688981', '300661', '688012', '603160'],
        '消费电子': ['002475', '002241', '603160', '601138', '002036', '002456'],
        '光伏': ['601012', '002459', '600438', '688599', '300274', '002129'],
        '新能源车': ['002594', '300750', '002466', '002074', '300014', '300207'],
    }


def check_sector_signal_at_idx(sector_returns, idx):
    """检测板块异动信号"""
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
    
    surge_days = old_period[old_period > 5.0]
    if len(surge_days) == 0:
        return False, None
    
    max_surge_idx = surge_days.idxmax()
    
    after_surge = data[data.index >= max_surge_idx]
    if len(after_surge) < 30:
        return False, None
    
    cumsum = after_surge.cumsum()
    max_gain = cumsum.max()
    current_gain = cumsum.iloc[-1]
    drawdown = max_gain - current_gain
    
    # 放宽条件：回撤10-25%
    if drawdown < 10 or drawdown > 25:
        return False, None
    
    if recent_30d.sum() > 8:
        return False, None
    if recent_10d.sum() < -5:
        return False, None
    if recent_5d.sum() < -3:
        return False, None
    
    return True, {'drawdown': drawdown}


def check_support_signal(df, idx):
    """
    检测托单信号（改进版）
    重点：大放量托单效果最好
    """
    if idx < 10 or idx >= len(df) - 5:
        return False, None
    
    today = df.iloc[idx]
    
    # 近3日数据
    recent_3d = df.iloc[idx-3:idx]
    high_3d = recent_3d['最高'].max()
    low_3d = recent_3d['最低'].min()
    avg_3d = recent_3d['收盘'].mean()
    
    # 条件1：近3日横盘
    volatility_3d = (high_3d - low_3d) / avg_3d * 100
    if volatility_3d > 6.0:  # 放宽到6%
        return False, None
    
    # 条件2：当日下影线明显
    body_low = min(today['开盘'], today['收盘'])
    body_high = max(today['开盘'], today['收盘'])
    lower_shadow = body_low - today['最低']
    amplitude = today['最高'] - today['最低']
    
    if amplitude == 0:
        return False, None
    
    lower_shadow_ratio = lower_shadow / amplitude * 100
    if lower_shadow_ratio < 30:
        return False, None
    
    # 条件3：收盘在当日高位
    position = (today['收盘'] - today['最低']) / amplitude * 100
    if position < 50:
        return False, None
    
    # 条件4：成交量（重点关注放量）
    vol_5d = df.iloc[idx-5:idx]['成交量'].mean()
    vol_ratio = today['成交量'] / vol_5d if vol_5d > 0 else 1
    
    # 条件5：当日涨跌幅适中
    today_change = (today['收盘'] - df.iloc[idx-1]['收盘']) / df.iloc[idx-1]['收盘'] * 100
    if today_change < -3 or today_change > 3:
        return False, None
    
    # 支撑位
    support = low_3d
    distance_to_support = (today['最低'] - support) / support * 100
    if distance_to_support < -3 or distance_to_support > 2:
        return False, None
    
    return True, {
        'volatility_3d': volatility_3d,
        'lower_shadow_ratio': lower_shadow_ratio,
        'position': position,
        'vol_ratio': vol_ratio,
        'today_change': today_change,
    }


def run_backtest():
    log("="*70)
    log("板块异动 + 托单 组合策略回测")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*70)
    
    sector_stocks = get_sector_stocks()
    
    # 获取数据
    log("\n[1] 获取数据...")
    all_stock_data = {}
    sector_trends = {}
    
    for sector, stocks in sector_stocks.items():
        stock_data = {}
        all_returns = []
        for code in stocks:
            df = get_stock_kline(code, days=400)
            if df is not None and len(df) > 100:
                stock_data[code] = df
                all_returns.append(df[['日期', '涨跌幅']].set_index('日期')['涨跌幅'])
        
        all_stock_data[sector] = stock_data
        if all_returns:
            combined = pd.concat(all_returns, axis=1)
            sector_trends[sector] = combined.mean(axis=1)
            log(f"  {sector}: {len(stock_data)}只股票")
    
    # 收集信号
    log("\n[2] 收集信号...")
    
    # 仅托单信号
    support_only_signals = []
    # 板块+托单组合信号
    combo_signals = []
    
    for sector, stock_data in all_stock_data.items():
        sector_trend = sector_trends.get(sector)
        if sector_trend is None:
            continue
        
        for code, df in stock_data.items():
            for idx in range(100, len(df) - 10, 1):
                signal_date = df.iloc[idx]['日期']
                
                # 检测托单信号
                is_support, support_info = check_support_signal(df, idx)
                
                if not is_support:
                    continue
                
                # 计算未来收益
                buy_price = df.iloc[idx]['收盘']
                future_1d = (df.iloc[idx+1]['收盘'] - buy_price) / buy_price * 100
                future_3d = (df.iloc[idx+3]['收盘'] - buy_price) / buy_price * 100
                future_5d = (df.iloc[idx+5]['收盘'] - buy_price) / buy_price * 100
                
                # 仅托单信号
                support_only_signals.append({
                    'sector': sector,
                    'code': code,
                    'date': signal_date,
                    'vol_ratio': support_info['vol_ratio'],
                    'lower_shadow': support_info['lower_shadow_ratio'],
                    'position': support_info['position'],
                    'future_1d': future_1d,
                    'future_3d': future_3d,
                    'future_5d': future_5d,
                })
                
                # 检测板块异动
                try:
                    sector_idx = sector_trend.index.get_indexer([signal_date], method='ffill')[0]
                    if sector_idx >= 0:
                        is_sector, sector_info = check_sector_signal_at_idx(sector_trend, sector_idx)
                        
                        if is_sector:
                            combo_signals.append({
                                'sector': sector,
                                'code': code,
                                'date': signal_date,
                                'sector_drawdown': sector_info['drawdown'],
                                'vol_ratio': support_info['vol_ratio'],
                                'lower_shadow': support_info['lower_shadow_ratio'],
                                'position': support_info['position'],
                                'future_1d': future_1d,
                                'future_3d': future_3d,
                                'future_5d': future_5d,
                            })
                except:
                    pass
    
    df_support = pd.DataFrame(support_only_signals)
    df_combo = pd.DataFrame(combo_signals)
    
    log(f"\n  仅托单信号: {len(df_support)}个")
    log(f"  板块+托单组合: {len(df_combo)}个")
    
    # 对比结果
    log("\n" + "="*70)
    log("策略对比")
    log("="*70)
    
    log(f"\n{'策略':<20} {'信号数':>8} {'1日胜率':>10} {'3日胜率':>10} {'5日胜率':>10}")
    log("-" * 60)
    
    for name, df in [('仅托单', df_support), ('板块+托单', df_combo)]:
        if len(df) == 0:
            continue
        wr_1d = (df['future_1d'] > 0).sum() / len(df) * 100
        wr_3d = (df['future_3d'] > 0).sum() / len(df) * 100
        wr_5d = (df['future_5d'] > 0).sum() / len(df) * 100
        log(f"{name:<20} {len(df):>8} {wr_1d:>9.1f}% {wr_3d:>9.1f}% {wr_5d:>9.1f}%")
    
    log(f"\n{'策略':<20} {'1日均收':>10} {'3日均收':>10} {'5日均收':>10}")
    log("-" * 60)
    
    for name, df in [('仅托单', df_support), ('板块+托单', df_combo)]:
        if len(df) == 0:
            continue
        avg_1d = df['future_1d'].mean()
        avg_3d = df['future_3d'].mean()
        avg_5d = df['future_5d'].mean()
        log(f"{name:<20} {avg_1d:>+9.2f}% {avg_3d:>+9.2f}% {avg_5d:>+9.2f}%")
    
    # 进一步筛选：大放量托单
    log("\n" + "="*70)
    log("放量托单效果（量比>1.5）")
    log("="*70)
    
    for name, df in [('仅托单', df_support), ('板块+托单', df_combo)]:
        if len(df) == 0:
            continue
        big_vol = df[df['vol_ratio'] > 1.5]
        if len(big_vol) > 0:
            wr = (big_vol['future_3d'] > 0).sum() / len(big_vol) * 100
            ar = big_vol['future_3d'].mean()
            log(f"  {name} 放量: {len(big_vol)}个信号, 胜率{wr:.1f}%, 均收{ar:+.2f}%")
    
    # 板块+托单组合详细分析
    if len(df_combo) > 0:
        log("\n" + "="*70)
        log("板块+托单组合详细分析")
        log("="*70)
        
        # 按板块
        log("\n【按板块】")
        sector_stats = df_combo.groupby('sector').agg({
            'future_3d': ['count', 'mean', lambda x: (x > 0).sum() / len(x) * 100]
        }).round(2)
        sector_stats.columns = ['信号数', '均收', '胜率']
        sector_stats = sector_stats.sort_values('胜率', ascending=False)
        
        for sector, row in sector_stats.iterrows():
            log(f"  {sector}: {int(row['信号数'])}个, 胜率{row['胜率']:.1f}%, 均收{row['均收']:+.2f}%")
        
        # 按量比
        log("\n【按量比】")
        df_combo['量比分组'] = pd.cut(df_combo['vol_ratio'], bins=[0, 1.0, 1.5, 10], 
                                     labels=['缩量(<1)', '平量(1-1.5)', '放量(>1.5)'])
        for group in ['缩量(<1)', '平量(1-1.5)', '放量(>1.5)']:
            subset = df_combo[df_combo['量比分组'] == group]
            if len(subset) > 0:
                wr = (subset['future_3d'] > 0).sum() / len(subset) * 100
                ar = subset['future_3d'].mean()
                log(f"  {group}: {len(subset)}个, 胜率{wr:.1f}%, 均收{ar:+.2f}%")
        
        # 最佳组合
        log("\n【最佳条件组合】")
        
        # 放量+高位置
        best = df_combo[(df_combo['vol_ratio'] > 1.2) & (df_combo['position'] > 70)]
        if len(best) > 0:
            wr = (best['future_3d'] > 0).sum() / len(best) * 100
            ar = best['future_3d'].mean()
            log(f"  放量>1.2 + 位置>70%: {len(best)}个, 胜率{wr:.1f}%, 均收{ar:+.2f}%")
        
        # 最佳案例
        log("\n【最佳案例】")
        best_5 = df_combo.nlargest(5, 'future_5d')
        for i, (_, row) in enumerate(best_5.iterrows(), 1):
            log(f"  {i}. {row['code']}({row['sector']}) {row['date'].strftime('%Y-%m-%d')}")
            log(f"     量比{row['vol_ratio']:.2f}, 板块回撤{row['sector_drawdown']:.1f}%")
            log(f"     收益: 3日{row['future_3d']:+.1f}%, 5日{row['future_5d']:+.1f}%")
    
    # 总结
    log("\n" + "="*70)
    log("策略总结")
    log("="*70)
    
    if len(df_combo) > 0 and len(df_support) > 0:
        support_wr = (df_support['future_3d'] > 0).sum() / len(df_support) * 100
        support_ar = df_support['future_3d'].mean()
        combo_wr = (df_combo['future_3d'] > 0).sum() / len(df_combo) * 100
        combo_ar = df_combo['future_3d'].mean()
        
        log(f"""
【对比结果】
  仅托单: {len(df_support)}个信号, 胜率{support_wr:.1f}%, 均收{support_ar:+.2f}%
  板块+托单: {len(df_combo)}个信号, 胜率{combo_wr:.1f}%, 均收{combo_ar:+.2f}%
  
  胜率提升: {combo_wr - support_wr:+.1f}%
  收益提升: {combo_ar - support_ar:+.2f}%

【结论】
{'组合策略有效提升！' if combo_wr > support_wr and combo_ar > support_ar else '组合策略效果不明显。'}

【最佳使用方式】
1. 先用板块异动选出潜力板块
2. 在潜力板块中找放量托单信号（量比>1.2）
3. 优选收盘位置>70%的信号
4. 止损：跌破支撑位-3%
""")
    
    # 保存
    fname = f"组合托单回测_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    with pd.ExcelWriter(fname, engine='openpyxl') as writer:
        df_support.to_excel(writer, sheet_name='仅托单', index=False)
        if len(df_combo) > 0:
            df_combo.to_excel(writer, sheet_name='板块托单组合', index=False)
    log(f"\n已保存: {fname}")


if __name__ == "__main__":
    run_backtest()
