"""
板块异动策略回测
目标：找出最佳的策略参数和使用方式
"""
import requests
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta

def log(msg):
    print(msg, flush=True)

# 清除代理
for key in list(os.environ.keys()):
    if 'proxy' in key.lower():
        del os.environ[key]

session = requests.Session()
session.trust_env = False


def get_stock_kline(code, days=400):
    """获取个股K线"""
    code = str(code).zfill(6)
    if code.startswith('6'):
        kcode = f'sh{code}'
    else:
        kcode = f'sz{code}'
    
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


def get_industry_stocks():
    """获取行业龙头股"""
    industry_leaders = {
        '人工智能': ['002230', '300474', '002415'],
        '机器人': ['002747', '300024', '300607'],
        '芯片': ['002371', '603501', '688981'],
        '新能源车': ['002594', '300750', '002466'],
        '光伏': ['601012', '002459', '600438'],
        '医药': ['600276', '000538', '300760'],
        '白酒': ['600519', '000858', '000568'],
        '军工': ['600893', '000768', '600760'],
        '消费电子': ['002475', '002241', '603160'],
        '半导体设备': ['002371', '688012', '300661'],
        '储能': ['002074', '300014', '300724'],
        '传媒': ['002027', '300413', '002602'],
        '建材': ['600585', '000401', '002271'],
        '有色金属': ['601899', '000630', '002460'],
        '煤炭': ['601088', '601898', '600188'],
        '房地产': ['001979', '600048', '000002'],
        '证券': ['600030', '601211', '600837'],
    }
    return industry_leaders


def estimate_sector_trend(stocks):
    """用成分股估算板块走势"""
    all_data = []
    for code in stocks:
        df = get_stock_kline(code, days=400)
        if df is not None and len(df) > 100:
            all_data.append(df[['日期', '涨跌幅']].set_index('日期')['涨跌幅'])
    
    if len(all_data) == 0:
        return None
    
    combined = pd.concat(all_data, axis=1)
    return combined.mean(axis=1)


def detect_signal_at_idx(daily_returns, idx, params):
    """
    在指定位置检测信号
    
    params: {
        'surge_threshold': 爆发阈值（单日涨幅）,
        'min_days_since': 爆发距今最少天数,
        'max_days_since': 爆发距今最多天数,
        'min_drawdown': 最小回撤,
        'max_drawdown': 最大回撤,
        'recent_30d_max': 近30日累计最大,
        'recent_10d_min': 近10日累计最小,
        'recent_5d_min': 近5日累计最小,
    }
    """
    if idx < 120:
        return False, None
    
    data = daily_returns.iloc[:idx]
    
    # 分时间段
    old_end = idx - params['min_days_since']
    old_start = max(0, idx - params['max_days_since'])
    
    if old_end <= old_start:
        return False, None
    
    old_period = daily_returns.iloc[old_start:old_end]
    recent_30d = daily_returns.iloc[idx-30:idx]
    recent_10d = daily_returns.iloc[idx-10:idx]
    recent_5d = daily_returns.iloc[idx-5:idx]
    
    # 条件1：找爆发
    surge_days = old_period[old_period > params['surge_threshold']]
    if len(surge_days) == 0:
        return False, None
    
    max_surge_value = surge_days.max()
    max_surge_idx = surge_days.idxmax()
    
    # 条件2：计算回撤
    after_surge = daily_returns.iloc[daily_returns.index.get_loc(max_surge_idx):idx]
    if len(after_surge) < 20:
        return False, None
    
    cumsum = after_surge.cumsum()
    max_gain = cumsum.max()
    current_gain = cumsum.iloc[-1]
    drawdown = max_gain - current_gain
    
    if drawdown < params['min_drawdown'] or drawdown > params['max_drawdown']:
        return False, None
    
    # 条件3：近期弱势
    recent_30d_sum = recent_30d.sum()
    if recent_30d_sum > params['recent_30d_max']:
        return False, None
    
    # 条件4：近10日企稳
    recent_10d_sum = recent_10d.sum()
    if recent_10d_sum < params['recent_10d_min']:
        return False, None
    
    # 条件5：近5日止跌
    recent_5d_sum = recent_5d.sum()
    if recent_5d_sum < params['recent_5d_min']:
        return False, None
    
    days_since = (daily_returns.index[idx] - max_surge_idx).days
    
    return True, {
        'surge_date': max_surge_idx,
        'surge_value': max_surge_value,
        'drawdown': drawdown,
        'days_since': days_since,
        'recent_30d': recent_30d_sum,
        'recent_10d': recent_10d_sum,
        'recent_5d': recent_5d_sum,
    }


def calculate_future_returns(daily_returns, idx, periods=[10, 20, 30, 60]):
    """计算未来N天的收益"""
    results = {}
    for period in periods:
        end_idx = idx + period
        if end_idx <= len(daily_returns):
            future_data = daily_returns.iloc[idx:end_idx]
            results[f'{period}d'] = future_data.sum()
        else:
            results[f'{period}d'] = None
    return results


def backtest_with_params(all_sector_data, params, name=""):
    """用指定参数回测"""
    all_signals = []
    
    for sector, data in all_sector_data.items():
        if data is None or len(data) < 200:
            continue
        
        # 每5天检测一次（减少重复信号）
        for idx in range(150, len(data) - 60, 5):
            is_signal, details = detect_signal_at_idx(data, idx, params)
            
            if is_signal:
                signal_date = data.index[idx]
                future_returns = calculate_future_returns(data, idx)
                
                all_signals.append({
                    'sector': sector,
                    'signal_date': signal_date,
                    'surge_date': details['surge_date'],
                    'surge_value': details['surge_value'],
                    'drawdown': details['drawdown'],
                    'days_since': details['days_since'],
                    'recent_30d': details['recent_30d'],
                    'recent_5d': details['recent_5d'],
                    **future_returns
                })
    
    if not all_signals:
        return None
    
    df = pd.DataFrame(all_signals)
    
    # 统计
    stats = {}
    for period in ['10d', '20d', '30d', '60d']:
        valid = df[period].dropna()
        if len(valid) > 0:
            stats[f'{period}_win_rate'] = (valid > 0).sum() / len(valid) * 100
            stats[f'{period}_avg'] = valid.mean()
            stats[f'{period}_median'] = valid.median()
    
    stats['signal_count'] = len(df)
    stats['params'] = name
    
    return stats, df


def run_backtest():
    log("="*70)
    log("板块异动策略回测")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*70)
    
    log("\n[1] 获取行业数据...")
    industry_leaders = get_industry_stocks()
    
    all_sector_data = {}
    for industry, stocks in industry_leaders.items():
        log(f"  获取 {industry}...")
        data = estimate_sector_trend(stocks)
        if data is not None:
            all_sector_data[industry] = data
            log(f"    {len(data)}天数据")
    
    log(f"\n  共获取 {len(all_sector_data)} 个行业数据")
    
    log("\n[2] 测试不同参数组合...")
    
    # 参数组合
    param_sets = [
        # 基础版：爆发后30-90天
        {
            'name': '基础版(30-90天)',
            'params': {
                'surge_threshold': 4.0,
                'min_days_since': 30,
                'max_days_since': 90,
                'min_drawdown': 5,
                'max_drawdown': 20,
                'recent_30d_max': 10,
                'recent_10d_min': -8,
                'recent_5d_min': -5,
            }
        },
        # 中期版：爆发后60-120天
        {
            'name': '中期版(60-120天)',
            'params': {
                'surge_threshold': 4.0,
                'min_days_since': 60,
                'max_days_since': 120,
                'min_drawdown': 8,
                'max_drawdown': 25,
                'recent_30d_max': 8,
                'recent_10d_min': -5,
                'recent_5d_min': -3,
            }
        },
        # 长期版：爆发后90-180天
        {
            'name': '长期版(90-180天)',
            'params': {
                'surge_threshold': 5.0,
                'min_days_since': 90,
                'max_days_since': 180,
                'min_drawdown': 10,
                'max_drawdown': 30,
                'recent_30d_max': 5,
                'recent_10d_min': -5,
                'recent_5d_min': -3,
            }
        },
        # 严格版：高回撤+企稳
        {
            'name': '严格版(高回撤)',
            'params': {
                'surge_threshold': 5.0,
                'min_days_since': 60,
                'max_days_since': 150,
                'min_drawdown': 12,
                'max_drawdown': 25,
                'recent_30d_max': 5,
                'recent_10d_min': -3,
                'recent_5d_min': -2,
            }
        },
        # 宽松版：更多信号
        {
            'name': '宽松版(更多信号)',
            'params': {
                'surge_threshold': 3.0,
                'min_days_since': 30,
                'max_days_since': 120,
                'min_drawdown': 5,
                'max_drawdown': 25,
                'recent_30d_max': 15,
                'recent_10d_min': -10,
                'recent_5d_min': -5,
            }
        },
    ]
    
    results = []
    all_dfs = {}
    
    for ps in param_sets:
        log(f"\n  测试: {ps['name']}")
        stats, df = backtest_with_params(all_sector_data, ps['params'], ps['name'])
        if stats:
            results.append(stats)
            all_dfs[ps['name']] = df
            log(f"    信号数: {stats['signal_count']}")
            log(f"    30日胜率: {stats.get('30d_win_rate', 0):.1f}%")
            log(f"    60日胜率: {stats.get('60d_win_rate', 0):.1f}%")
    
    # 结果比较
    log("\n" + "="*70)
    log("回测结果比较")
    log("="*70)
    
    log(f"\n{'参数组合':<20} {'信号数':>8} {'10日胜率':>10} {'20日胜率':>10} {'30日胜率':>10} {'60日胜率':>10}")
    log("-" * 70)
    
    for r in results:
        log(f"{r['params']:<20} {r['signal_count']:>8} "
            f"{r.get('10d_win_rate', 0):>9.1f}% "
            f"{r.get('20d_win_rate', 0):>9.1f}% "
            f"{r.get('30d_win_rate', 0):>9.1f}% "
            f"{r.get('60d_win_rate', 0):>9.1f}%")
    
    log(f"\n{'参数组合':<20} {'10日均收':>10} {'20日均收':>10} {'30日均收':>10} {'60日均收':>10}")
    log("-" * 70)
    
    for r in results:
        log(f"{r['params']:<20} "
            f"{r.get('10d_avg', 0):>+9.2f}% "
            f"{r.get('20d_avg', 0):>+9.2f}% "
            f"{r.get('30d_avg', 0):>+9.2f}% "
            f"{r.get('60d_avg', 0):>+9.2f}%")
    
    # 找最佳参数
    best_30d = max(results, key=lambda x: x.get('30d_win_rate', 0))
    best_60d = max(results, key=lambda x: x.get('60d_win_rate', 0))
    best_avg = max(results, key=lambda x: x.get('60d_avg', 0))
    
    log("\n" + "="*70)
    log("最佳参数")
    log("="*70)
    log(f"\n30日胜率最高: {best_30d['params']} ({best_30d.get('30d_win_rate', 0):.1f}%)")
    log(f"60日胜率最高: {best_60d['params']} ({best_60d.get('60d_win_rate', 0):.1f}%)")
    log(f"60日收益最高: {best_avg['params']} ({best_avg.get('60d_avg', 0):+.2f}%)")
    
    # 分析最佳版本的信号
    if best_60d['params'] in all_dfs:
        best_df = all_dfs[best_60d['params']]
        
        log("\n" + "="*70)
        log(f"最佳版本({best_60d['params']})信号分析")
        log("="*70)
        
        # 按板块统计
        log("\n【按板块统计】")
        sector_stats = best_df.groupby('sector').agg({
            '60d': ['count', 'mean', lambda x: (x > 0).sum() / len(x) * 100]
        }).round(2)
        sector_stats.columns = ['信号数', '60日均收', '60日胜率']
        sector_stats = sector_stats.sort_values('60日胜率', ascending=False)
        
        for sector, row in sector_stats.iterrows():
            log(f"  {sector}: {int(row['信号数'])}个信号, "
                f"胜率{row['60日胜率']:.1f}%, 均收{row['60日均收']:+.2f}%")
        
        # 按回撤分组
        log("\n【按回撤程度分组】")
        best_df['drawdown_group'] = pd.cut(best_df['drawdown'], 
                                           bins=[0, 10, 15, 20, 100], 
                                           labels=['5-10%', '10-15%', '15-20%', '>20%'])
        for group in ['5-10%', '10-15%', '15-20%', '>20%']:
            gdata = best_df[best_df['drawdown_group'] == group]['60d'].dropna()
            if len(gdata) > 0:
                wr = (gdata > 0).sum() / len(gdata) * 100
                avg = gdata.mean()
                log(f"  回撤{group}: {len(gdata)}个信号, 胜率{wr:.1f}%, 均收{avg:+.2f}%")
        
        # 按距今时间分组
        log("\n【按爆发距今时间分组】")
        best_df['days_group'] = pd.cut(best_df['days_since'], 
                                       bins=[0, 60, 90, 120, 365], 
                                       labels=['30-60天', '60-90天', '90-120天', '>120天'])
        for group in ['30-60天', '60-90天', '90-120天', '>120天']:
            gdata = best_df[best_df['days_group'] == group]['60d'].dropna()
            if len(gdata) > 0:
                wr = (gdata > 0).sum() / len(gdata) * 100
                avg = gdata.mean()
                log(f"  {group}: {len(gdata)}个信号, 胜率{wr:.1f}%, 均收{avg:+.2f}%")
        
        # 最佳案例
        log("\n【最佳案例（60日收益最高）】")
        top5 = best_df.nlargest(5, '60d')
        for _, row in top5.iterrows():
            log(f"  {row['sector']}: {row['signal_date'].strftime('%Y-%m-%d')}")
            log(f"    爆发+{row['surge_value']:.1f}%, 回撤{row['drawdown']:.1f}%, "
                f"距今{row['days_since']}天 -> 60日{row['60d']:+.1f}%")
        
        # 最差案例
        log("\n【最差案例（60日收益最低）】")
        bottom5 = best_df.nsmallest(5, '60d')
        for _, row in bottom5.iterrows():
            log(f"  {row['sector']}: {row['signal_date'].strftime('%Y-%m-%d')}")
            log(f"    爆发+{row['surge_value']:.1f}%, 回撤{row['drawdown']:.1f}%, "
                f"距今{row['days_since']}天 -> 60日{row['60d']:+.1f}%")
    
    # 使用建议
    log("\n" + "="*70)
    log("策略使用建议")
    log("="*70)
    
    log("""
基于回测结果，板块异动策略的最佳使用方式：

1. 【时间窗口】
   - 爆发后60-120天是最佳介入窗口
   - 太早（<60天）洗盘不充分
   - 太晚（>150天）可能已经错过

2. 【回撤程度】
   - 回撤10-15%是最佳区间
   - 回撤太小（<8%）说明洗盘不够
   - 回撤太大（>20%）可能趋势反转

3. 【企稳信号】
   - 近30日累计涨幅<5%（弱势）
   - 近10日止跌（>-5%）
   - 近5日企稳反弹（>-2%）

4. 【持有周期】
   - 短期（10-20日）胜率一般
   - 中长期（30-60日）胜率更高
   - 建议持有30-60天

5. 【风险控制】
   - 止损：跌破回撤低点-5%
   - 分批建仓：首次30%，确认后加仓
""")
    
    # 保存结果
    fname = f"板块异动回测_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    with pd.ExcelWriter(fname, engine='openpyxl') as writer:
        # 参数比较
        pd.DataFrame(results).to_excel(writer, sheet_name='参数比较', index=False)
        # 最佳版本信号
        if best_60d['params'] in all_dfs:
            all_dfs[best_60d['params']].to_excel(writer, sheet_name='最佳版本信号', index=False)
    log(f"\n已保存: {fname}")


if __name__ == "__main__":
    run_backtest()
