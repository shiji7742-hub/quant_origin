"""
托单策略回测（日K线版本）
用日K线下影线特征来识别托单信号

日K托单特征（分时托单在日K上的体现）：
1. 当日有明显下影线（盘中被打下去又收回）
2. 收盘在当日高位（守住了）
3. 成交量平稳或放大
4. 近期横盘整理（波动小）
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


def check_support_signal(df, idx):
    """
    检测日K托单信号
    
    日K上托单的体现：
    1. 近3日横盘（波动<5%）
    2. 当日有明显下影线（被打下去又收回）
    3. 收盘在当日高位（>50%）
    4. 成交量平稳（量比0.7-1.5）
    5. 当日涨跌幅适中（-2%~+2%）
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
    if volatility_3d > 5.0:
        return False, None
    
    # 条件2：当日下影线明显
    # 下影线 = min(开盘,收盘) - 最低
    body_low = min(today['开盘'], today['收盘'])
    body_high = max(today['开盘'], today['收盘'])
    lower_shadow = body_low - today['最低']
    upper_shadow = today['最高'] - body_high
    body = body_high - body_low
    
    # 下影线需要 > 实体的一半，或者 > 总振幅的30%
    amplitude = today['最高'] - today['最低']
    if amplitude == 0:
        return False, None
    
    lower_shadow_ratio = lower_shadow / amplitude * 100
    if lower_shadow_ratio < 30:  # 下影线占比至少30%
        return False, None
    
    # 条件3：收盘在当日高位
    position = (today['收盘'] - today['最低']) / amplitude * 100
    if position < 50:
        return False, None
    
    # 条件4：成交量平稳
    vol_5d = df.iloc[idx-5:idx]['成交量'].mean()
    vol_ratio = today['成交量'] / vol_5d if vol_5d > 0 else 1
    if vol_ratio < 0.7 or vol_ratio > 2.0:
        return False, None
    
    # 条件5：当日涨跌幅适中
    today_change = (today['收盘'] - df.iloc[idx-1]['收盘']) / df.iloc[idx-1]['收盘'] * 100
    if today_change < -2 or today_change > 2:
        return False, None
    
    # 额外：支撑位附近
    support = low_3d
    distance_to_support = (today['最低'] - support) / support * 100
    if distance_to_support < -3 or distance_to_support > 1:
        return False, None
    
    return True, {
        'volatility_3d': volatility_3d,
        'lower_shadow_ratio': lower_shadow_ratio,
        'position': position,
        'vol_ratio': vol_ratio,
        'today_change': today_change,
        'support': support,
        'distance_to_support': distance_to_support,
    }


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


def run_backtest():
    log("="*70)
    log("托单策略回测（日K线版本）")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*70)
    
    log("\n【日K托单特征】")
    log("  分时托单在日K上的体现：")
    log("  1. 近3日横盘（波动<5%）")
    log("  2. 当日下影线明显（>30%）")
    log("  3. 收盘在当日高位（>50%）")
    log("  4. 成交量平稳（0.7-2.0）")
    log("  5. 触及支撑位附近")
    
    sector_stocks = get_sector_stocks()
    all_stocks = []
    for sector, stocks in sector_stocks.items():
        for code in stocks:
            all_stocks.append((code, sector))
    
    log(f"\n回测股票: {len(all_stocks)}只")
    log("-" * 50)
    
    all_signals = []
    
    for code, sector in all_stocks:
        df = get_stock_kline(code, days=400)
        if df is None:
            continue
        
        signal_count = 0
        
        for idx in range(20, len(df) - 10, 1):
            is_signal, info = check_support_signal(df, idx)
            
            if not is_signal:
                continue
            
            signal_count += 1
            
            # 计算未来收益
            buy_price = df.iloc[idx]['收盘']
            
            future_1d = (df.iloc[idx+1]['收盘'] - buy_price) / buy_price * 100
            future_2d = (df.iloc[idx+2]['收盘'] - buy_price) / buy_price * 100
            future_3d = (df.iloc[idx+3]['收盘'] - buy_price) / buy_price * 100
            future_5d = (df.iloc[idx+5]['收盘'] - buy_price) / buy_price * 100
            
            # 最大收益和回撤
            future_prices = df.iloc[idx:idx+6]['收盘']
            max_return = (future_prices.max() - buy_price) / buy_price * 100
            max_drawdown = (future_prices.min() - buy_price) / buy_price * 100
            
            all_signals.append({
                'code': code,
                'sector': sector,
                'date': df.iloc[idx]['日期'].strftime('%Y-%m-%d'),
                'volatility_3d': info['volatility_3d'],
                'lower_shadow_ratio': info['lower_shadow_ratio'],
                'position': info['position'],
                'vol_ratio': info['vol_ratio'],
                'today_change': info['today_change'],
                'future_1d': future_1d,
                'future_2d': future_2d,
                'future_3d': future_3d,
                'future_5d': future_5d,
                'max_return': max_return,
                'max_drawdown': max_drawdown,
            })
        
        if signal_count > 0:
            log(f"  {code}({sector}): {signal_count}个信号")
    
    # 统计结果
    log("\n" + "="*70)
    log("回测结果")
    log("="*70)
    
    df = pd.DataFrame(all_signals)
    
    if len(df) == 0:
        log("\n无有效信号")
        return
    
    log(f"\n总信号数: {len(df)}个")
    
    # 胜率统计
    log(f"\n{'持有期':<10} {'胜率':>10} {'平均收益':>12} {'最大收益':>12} {'最大亏损':>12}")
    log("-" * 60)
    
    for period, col in [('1日', 'future_1d'), ('2日', 'future_2d'), 
                        ('3日', 'future_3d'), ('5日', 'future_5d')]:
        win_rate = (df[col] > 0).sum() / len(df) * 100
        avg_return = df[col].mean()
        max_gain = df[col].max()
        max_loss = df[col].min()
        log(f"{period:<10} {win_rate:>9.1f}% {avg_return:>+11.2f}% {max_gain:>+11.2f}% {max_loss:>+11.2f}%")
    
    # 按板块统计
    log("\n" + "="*70)
    log("按板块统计（3日收益）")
    log("="*70)
    
    sector_stats = df.groupby('sector').agg({
        'future_3d': ['count', 'mean', lambda x: (x > 0).sum() / len(x) * 100]
    }).round(2)
    sector_stats.columns = ['信号数', '均收', '胜率']
    sector_stats = sector_stats.sort_values('胜率', ascending=False)
    
    for sector, row in sector_stats.iterrows():
        log(f"  {sector}: {int(row['信号数'])}个信号, 胜率{row['胜率']:.1f}%, 均收{row['均收']:+.2f}%")
    
    # 按下影线比例统计
    log("\n" + "="*70)
    log("按下影线比例统计")
    log("="*70)
    
    df['下影线分组'] = pd.cut(df['lower_shadow_ratio'], bins=[0, 40, 50, 60, 100], 
                              labels=['30-40%', '40-50%', '50-60%', '>60%'])
    
    for group in ['30-40%', '40-50%', '50-60%', '>60%']:
        subset = df[df['下影线分组'] == group]
        if len(subset) > 0:
            win_rate = (subset['future_3d'] > 0).sum() / len(subset) * 100
            avg_return = subset['future_3d'].mean()
            log(f"  下影线{group}: {len(subset)}个信号, 胜率{win_rate:.1f}%, 均收{avg_return:+.2f}%")
    
    # 按收盘位置统计
    log("\n" + "="*70)
    log("按收盘位置统计")
    log("="*70)
    
    df['位置分组'] = pd.cut(df['position'], bins=[0, 60, 70, 80, 100], 
                           labels=['50-60%', '60-70%', '70-80%', '>80%'])
    
    for group in ['50-60%', '60-70%', '70-80%', '>80%']:
        subset = df[df['位置分组'] == group]
        if len(subset) > 0:
            win_rate = (subset['future_3d'] > 0).sum() / len(subset) * 100
            avg_return = subset['future_3d'].mean()
            log(f"  位置{group}: {len(subset)}个信号, 胜率{win_rate:.1f}%, 均收{avg_return:+.2f}%")
    
    # 按量比统计
    log("\n" + "="*70)
    log("按量比统计")
    log("="*70)
    
    df['量比分组'] = pd.cut(df['vol_ratio'], bins=[0, 0.9, 1.1, 1.5, 10], 
                           labels=['缩量(<0.9)', '平量(0.9-1.1)', '放量(1.1-1.5)', '大放量(>1.5)'])
    
    for group in ['缩量(<0.9)', '平量(0.9-1.1)', '放量(1.1-1.5)', '大放量(>1.5)']:
        subset = df[df['量比分组'] == group]
        if len(subset) > 0:
            win_rate = (subset['future_3d'] > 0).sum() / len(subset) * 100
            avg_return = subset['future_3d'].mean()
            log(f"  {group}: {len(subset)}个信号, 胜率{win_rate:.1f}%, 均收{avg_return:+.2f}%")
    
    # 最佳组合分析
    log("\n" + "="*70)
    log("最佳条件组合")
    log("="*70)
    
    # 下影线>50% 且 位置>70%
    best = df[(df['lower_shadow_ratio'] > 50) & (df['position'] > 70)]
    if len(best) > 0:
        wr = (best['future_3d'] > 0).sum() / len(best) * 100
        ar = best['future_3d'].mean()
        log(f"\n  下影线>50% + 位置>70%:")
        log(f"    信号数: {len(best)}个, 胜率{wr:.1f}%, 均收{ar:+.2f}%")
    
    # 下影线>50% 且 放量
    best2 = df[(df['lower_shadow_ratio'] > 50) & (df['vol_ratio'] > 1.1)]
    if len(best2) > 0:
        wr2 = (best2['future_3d'] > 0).sum() / len(best2) * 100
        ar2 = best2['future_3d'].mean()
        log(f"\n  下影线>50% + 放量>1.1:")
        log(f"    信号数: {len(best2)}个, 胜率{wr2:.1f}%, 均收{ar2:+.2f}%")
    
    # 最佳案例
    log("\n" + "="*70)
    log("最佳案例（5日收益TOP10）")
    log("="*70)
    
    best_10 = df.nlargest(10, 'future_5d')
    for i, (_, row) in enumerate(best_10.iterrows(), 1):
        log(f"\n  {i}. {row['code']} ({row['sector']}) {row['date']}")
        log(f"     下影线{row['lower_shadow_ratio']:.0f}%, 位置{row['position']:.0f}%, 量比{row['vol_ratio']:.2f}")
        log(f"     收益: 1日{row['future_1d']:+.1f}%, 3日{row['future_3d']:+.1f}%, 5日{row['future_5d']:+.1f}%")
    
    # 总结
    overall_3d_wr = (df['future_3d'] > 0).sum() / len(df) * 100
    overall_3d_avg = df['future_3d'].mean()
    
    log(f"""
======================================================================
策略总结
======================================================================

【整体表现】
  - 信号数: {len(df)}个
  - 3日胜率: {overall_3d_wr:.1f}%
  - 3日均收: {overall_3d_avg:+.2f}%

【日K托单特征】
  分时托单在日K上体现为：
  - 横盘整理中出现下影线K线
  - 下影线说明盘中被打下去又收回（有资金托）
  - 收盘守住高位说明托单有效

【最佳条件】
  - 下影线占比 > 50%（托单明显）
  - 收盘位置 > 70%（守住高位）
  - 量比 > 1.1（放量托）

【操作建议】
  1. 发现信号后次日买入
  2. 买入价参考支撑位（近3日低点）
  3. 止损: 跌破支撑位-3%
  4. 持有: 2-3天
""")
    
    # 保存
    fname = f"托单策略回测_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df.to_excel(fname, index=False)
    log(f"\n已保存: {fname}")


if __name__ == "__main__":
    run_backtest()
