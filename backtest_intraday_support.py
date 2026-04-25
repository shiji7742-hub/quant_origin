"""
分时托单策略回测
用历史5分钟K线数据回测分时托单策略效果
"""
import requests
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta

def log(msg):
    print(msg, flush=True)

for key in list(os.environ.keys()):
    if 'proxy' in key.lower():
        del os.environ[key]

session = requests.Session()
session.trust_env = False


def get_5min_kline(code, count=800):
    """获取5分钟K线（约1个月数据）"""
    code = str(code).zfill(6)
    kcode = f'sh{code}' if code.startswith('6') else f'sz{code}'
    url = f'https://web.ifzq.gtimg.cn/appstock/app/kline/mkline?param={kcode},m5,,{count}'
    try:
        r = session.get(url, timeout=10)
        data = r.json()
        if 'data' not in data:
            return None
        stock_data = data['data'].get(kcode) or data['data'].get(kcode.upper())
        if not stock_data or 'm5' not in stock_data:
            return None
        klines = stock_data['m5']
        if len(klines) < 100:
            return None
        df = pd.DataFrame(klines, columns=['时间', '开盘', '收盘', '最高', '最低', '成交量'])
        for col in ['开盘', '收盘', '最高', '最低', '成交量']:
            df[col] = df[col].astype(float)
        # 解析日期
        df['日期'] = df['时间'].str[:8]
        df['时分'] = df['时间'].str[8:]
        return df
    except Exception as e:
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
        return df
    except:
        return None


def check_intraday_support_at_day(df_5min, date_str):
    """
    检测某一天的分时托单信号
    
    条件：
    1. 当日分时横盘（波动<4%）
    2. 多次下探收回（下影线多）
    3. 下跌量小、反弹量大
    4. 收盘守住分时高位
    """
    # 获取当天的5分钟K线
    day_bars = df_5min[df_5min['日期'] == date_str].copy()
    if len(day_bars) < 20:
        return False, None
    
    high = day_bars['最高'].max()
    low = day_bars['最低'].min()
    avg_price = day_bars['收盘'].mean()
    current = day_bars.iloc[-1]['收盘']
    open_price = day_bars.iloc[0]['开盘']
    
    # 条件1：分时横盘（波动<4%）
    volatility = (high - low) / avg_price * 100
    if volatility > 4.0:
        return False, None
    
    # 条件2：多次下探收回（下影线分析）
    day_bars['下影线'] = day_bars['收盘'] - day_bars['最低']
    day_bars['上影线'] = day_bars['最高'] - day_bars['收盘']
    day_bars['实体'] = abs(day_bars['收盘'] - day_bars['开盘'])
    
    # 下影线明显的K线（托单特征）
    support_bars = day_bars[day_bars['下影线'] > day_bars['实体'] * 0.3]
    support_count = len(support_bars)
    
    if support_count < 3:
        return False, None
    
    # 条件3：量能分析
    day_bars['涨跌'] = day_bars['收盘'] - day_bars['开盘']
    down_bars = day_bars[day_bars['涨跌'] < 0]
    up_bars = day_bars[day_bars['涨跌'] > 0]
    
    if len(down_bars) < 3 or len(up_bars) < 3:
        return False, None
    
    avg_down_vol = down_bars['成交量'].mean()
    avg_up_vol = up_bars['成交量'].mean()
    vol_ratio = avg_up_vol / avg_down_vol if avg_down_vol > 0 else 1
    
    # 上涨量应该 >= 下跌量的80%
    if vol_ratio < 0.8:
        return False, None
    
    # 条件4：收盘位置在分时高位
    position = (current - low) / (high - low) * 100 if high > low else 50
    if position < 50:
        return False, None
    
    # 条件5：今日涨跌幅不能太大
    today_change = (current - open_price) / open_price * 100
    if today_change < -3 or today_change > 5:
        return False, None
    
    # 大单托比
    if len(support_bars) > 0:
        support_vol = support_bars['成交量'].mean()
        avg_vol = day_bars['成交量'].mean()
        big_order_ratio = support_vol / avg_vol if avg_vol > 0 else 1
    else:
        big_order_ratio = 1
    
    return True, {
        'volatility': volatility,
        'support_count': support_count,
        'vol_ratio': vol_ratio,
        'position': position,
        'today_change': today_change,
        'big_order_ratio': big_order_ratio,
        'close': current,
        'low': low,
        'high': high,
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
    log("分时托单策略回测")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*70)
    
    log("\n【策略条件】")
    log("  1. 分时横盘（波动<4%）")
    log("  2. 多次下探收回（托单>=3次）")
    log("  3. 上涨量/下跌量 >= 0.8")
    log("  4. 收盘在分时高位（>50%）")
    log("  5. 今日涨跌幅 -3%~+5%")
    
    sector_stocks = get_sector_stocks()
    all_stocks = []
    for sector, stocks in sector_stocks.items():
        for code in stocks:
            all_stocks.append((code, sector))
    
    log(f"\n回测股票: {len(all_stocks)}只")
    log("-" * 50)
    
    all_signals = []
    
    for code, sector in all_stocks:
        log(f"\n  处理 {code} ({sector})...")
        
        # 获取5分钟K线
        df_5min = get_5min_kline(code, count=1000)
        if df_5min is None:
            log(f"    -> 无5分钟数据")
            continue
        
        # 获取日K线
        df_daily = get_stock_kline(code, days=60)
        if df_daily is None:
            log(f"    -> 无日K数据")
            continue
        
        # 获取所有交易日
        dates = df_5min['日期'].unique()
        log(f"    数据: {len(dates)}个交易日")
        
        signal_count = 0
        
        # 遍历每个交易日检测信号
        for i, date_str in enumerate(dates[:-5]):  # 留5天计算未来收益
            is_signal, info = check_intraday_support_at_day(df_5min, date_str)
            
            if not is_signal:
                continue
            
            signal_count += 1
            
            # 计算未来收益（用日K线）
            try:
                # 找到信号日在日K中的位置
                daily_dates = df_daily['日期'].tolist()
                # 匹配日期格式
                signal_date_fmt = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                
                signal_idx = None
                for idx, d in enumerate(daily_dates):
                    if signal_date_fmt in str(d):
                        signal_idx = idx
                        break
                
                if signal_idx is None or signal_idx + 5 >= len(df_daily):
                    continue
                
                buy_price = df_daily.iloc[signal_idx]['收盘']
                
                # 计算1、2、3、5日收益
                future_1d = (df_daily.iloc[signal_idx+1]['收盘'] - buy_price) / buy_price * 100
                future_2d = (df_daily.iloc[signal_idx+2]['收盘'] - buy_price) / buy_price * 100
                future_3d = (df_daily.iloc[signal_idx+3]['收盘'] - buy_price) / buy_price * 100
                future_5d = (df_daily.iloc[signal_idx+5]['收盘'] - buy_price) / buy_price * 100
                
                # 最大收益和最大回撤
                future_prices = df_daily.iloc[signal_idx:signal_idx+6]['收盘']
                max_return = (future_prices.max() - buy_price) / buy_price * 100
                max_drawdown = (future_prices.min() - buy_price) / buy_price * 100
                
                all_signals.append({
                    'code': code,
                    'sector': sector,
                    'date': date_str,
                    'volatility': info['volatility'],
                    'support_count': info['support_count'],
                    'vol_ratio': info['vol_ratio'],
                    'position': info['position'],
                    'today_change': info['today_change'],
                    'future_1d': future_1d,
                    'future_2d': future_2d,
                    'future_3d': future_3d,
                    'future_5d': future_5d,
                    'max_return': max_return,
                    'max_drawdown': max_drawdown,
                })
            except Exception as e:
                continue
        
        if signal_count > 0:
            log(f"    -> 发现 {signal_count} 个信号")
    
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
    
    # 按托单次数统计
    log("\n" + "="*70)
    log("按托单次数统计")
    log("="*70)
    
    df['托单分组'] = pd.cut(df['support_count'], bins=[0, 3, 5, 8, 100], 
                           labels=['3次', '4-5次', '6-8次', '>8次'])
    
    for group in ['3次', '4-5次', '6-8次', '>8次']:
        subset = df[df['托单分组'] == group]
        if len(subset) > 0:
            win_rate = (subset['future_3d'] > 0).sum() / len(subset) * 100
            avg_return = subset['future_3d'].mean()
            log(f"  托单{group}: {len(subset)}个信号, 胜率{win_rate:.1f}%, 均收{avg_return:+.2f}%")
    
    # 按量比统计
    log("\n" + "="*70)
    log("按量比统计（上涨量/下跌量）")
    log("="*70)
    
    df['量比分组'] = pd.cut(df['vol_ratio'], bins=[0, 1.0, 1.2, 1.5, 10], 
                           labels=['0.8-1.0', '1.0-1.2', '1.2-1.5', '>1.5'])
    
    for group in ['0.8-1.0', '1.0-1.2', '1.2-1.5', '>1.5']:
        subset = df[df['量比分组'] == group]
        if len(subset) > 0:
            win_rate = (subset['future_3d'] > 0).sum() / len(subset) * 100
            avg_return = subset['future_3d'].mean()
            log(f"  量比{group}: {len(subset)}个信号, 胜率{win_rate:.1f}%, 均收{avg_return:+.2f}%")
    
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
    
    # 最佳案例
    log("\n" + "="*70)
    log("最佳案例（5日收益TOP10）")
    log("="*70)
    
    best_10 = df.nlargest(10, 'future_5d')
    for i, (_, row) in enumerate(best_10.iterrows(), 1):
        log(f"\n  {i}. {row['code']} ({row['sector']}) {row['date']}")
        log(f"     托单{row['support_count']}次, 量比{row['vol_ratio']:.2f}, 位置{row['position']:.0f}%")
        log(f"     收益: 1日{row['future_1d']:+.1f}%, 3日{row['future_3d']:+.1f}%, 5日{row['future_5d']:+.1f}%")
    
    # 总结
    log("\n" + "="*70)
    log("策略总结")
    log("="*70)
    
    overall_3d_wr = (df['future_3d'] > 0).sum() / len(df) * 100
    overall_3d_avg = df['future_3d'].mean()
    
    log(f"""
【整体表现】
  - 信号数: {len(df)}个
  - 3日胜率: {overall_3d_wr:.1f}%
  - 3日均收: {overall_3d_avg:+.2f}%

【最佳条件组合】
  - 托单次数: >=5次（信号更可靠）
  - 量比: >1.0（上涨量大于下跌量）
  - 收盘位置: >70%（守住高位）

【操作建议】
  1. 发现分时托单信号后，在分时低点买入
  2. 止损: 跌破分时低点-2%
  3. 持有: 2-3天
  4. 优选托单次数多、量比大的信号
""")
    
    # 保存
    fname = f"分时托单回测_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df.to_excel(fname, index=False)
    log(f"\n已保存: {fname}")


if __name__ == "__main__":
    run_backtest()
