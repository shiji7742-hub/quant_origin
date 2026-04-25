"""
分析组合策略（板块异动+横盘托单）失效情况
找出失败的原因并改进
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


def get_market_data():
    """获取大盘数据"""
    df = get_stock_kline('000001', days=400)
    if df is not None:
        df['ma5'] = df['收盘'].rolling(5).mean()
        df['ma10'] = df['收盘'].rolling(10).mean()
        df['ma20'] = df['收盘'].rolling(20).mean()
        df['ma60'] = df['收盘'].rolling(60).mean()
        df['above_ma20'] = df['收盘'] > df['ma20']
        df['trend_5d'] = df['收盘'].pct_change(5) * 100
        df['trend_20d'] = df['收盘'].pct_change(20) * 100
    return df


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
    
    max_surge_value = surge_days.max()
    max_surge_idx = surge_days.idxmax()
    
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
        'recent_30d': recent_30d_sum,
        'recent_10d': recent_10d_sum,
        'recent_5d': recent_5d_sum,
    }


def check_sideways_at_idx(df, idx):
    """检测横盘托单信号（返回更多特征）"""
    if idx < 10:
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
    
    # 更多特征
    today_change = (today['收盘'] - today['开盘']) / today['开盘'] * 100
    today_amplitude = (today['最高'] - today['最低']) / today['开盘'] * 100
    
    # 成交量特征
    vol_5d = df.iloc[idx-5:idx]['成交量'].mean()
    vol_today = today['成交量']
    vol_ratio = vol_today / vol_5d if vol_5d > 0 else 1
    
    # 前期涨幅
    if idx >= 10:
        price_10d_ago = df.iloc[idx-10]['收盘']
        gain_10d = (today['收盘'] - price_10d_ago) / price_10d_ago * 100
    else:
        gain_10d = 0
    
    # 相对位置（距离20日高点）
    if idx >= 20:
        high_20d = df.iloc[idx-20:idx]['最高'].max()
        from_high = (today['收盘'] - high_20d) / high_20d * 100
    else:
        from_high = 0
    
    return True, {
        'support': support,
        'volatility': volatility,
        'distance': distance,
        'today_change': today_change,
        'today_amplitude': today_amplitude,
        'vol_ratio': vol_ratio,
        'gain_10d': gain_10d,
        'from_high_20d': from_high,
    }


def run_analysis():
    log("="*70)
    log("组合策略失效分析")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*70)
    
    # 获取数据
    log("\n[1] 获取数据...")
    market_data = get_market_data()
    log(f"  大盘数据: {len(market_data) if market_data is not None else 0}天")
    
    sector_stocks = get_sector_stocks()
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
    
    log(f"  板块数据: {len(sector_trends)}个")
    
    # 收集所有信号
    log("\n[2] 收集信号...")
    all_signals = []
    
    for sector, stock_data in all_stock_data.items():
        sector_trend = sector_trends.get(sector)
        if sector_trend is None:
            continue
        
        for code, df in stock_data.items():
            for idx in range(100, len(df) - 20, 2):
                signal_date = df.iloc[idx]['日期']
                
                # 检测横盘托单
                is_sideways, sideways_info = check_sideways_at_idx(df, idx)
                if not is_sideways:
                    continue
                
                # 检测板块异动
                try:
                    sector_idx = sector_trend.index.get_indexer([signal_date], method='ffill')[0]
                    if sector_idx < 0:
                        continue
                    is_sector_signal, sector_info = check_sector_signal_at_idx(sector_trend, sector_idx)
                    if not is_sector_signal:
                        continue
                except:
                    continue
                
                # 计算未来收益
                buy_price = df.iloc[idx]['收盘']
                future_5d = (df.iloc[idx+5]['收盘'] - buy_price) / buy_price * 100 if idx+5 < len(df) else None
                future_10d = (df.iloc[idx+10]['收盘'] - buy_price) / buy_price * 100 if idx+10 < len(df) else None
                future_20d = (df.iloc[idx+20]['收盘'] - buy_price) / buy_price * 100 if idx+20 < len(df) else None
                
                # 最大收益和最大回撤
                if idx + 20 <= len(df):
                    future_prices = df.iloc[idx:idx+20]['收盘']
                    max_price = future_prices.max()
                    min_price = future_prices.min()
                    max_return = (max_price - buy_price) / buy_price * 100
                    max_drawdown = (min_price - buy_price) / buy_price * 100
                else:
                    max_return = max_drawdown = None
                
                if future_10d is None:
                    continue
                
                # 大盘状态
                market_state = {}
                if market_data is not None:
                    try:
                        mkt_idx = market_data[market_data['日期'] <= signal_date].index[-1]
                        market_state = {
                            'market_above_ma20': market_data.loc[mkt_idx, 'above_ma20'],
                            'market_trend_5d': market_data.loc[mkt_idx, 'trend_5d'],
                            'market_trend_20d': market_data.loc[mkt_idx, 'trend_20d'],
                        }
                    except:
                        pass
                
                all_signals.append({
                    'sector': sector,
                    'code': code,
                    'date': signal_date,
                    # 板块特征
                    'sector_drawdown': sector_info['drawdown'],
                    'sector_days_since': sector_info['days_since'],
                    'sector_recent_5d': sector_info['recent_5d'],
                    # 个股特征
                    'stock_volatility': sideways_info['volatility'],
                    'stock_distance': sideways_info['distance'],
                    'stock_today_change': sideways_info['today_change'],
                    'stock_vol_ratio': sideways_info['vol_ratio'],
                    'stock_gain_10d': sideways_info['gain_10d'],
                    'stock_from_high': sideways_info['from_high_20d'],
                    # 大盘
                    **market_state,
                    # 结果
                    'future_5d': future_5d,
                    'future_10d': future_10d,
                    'future_20d': future_20d,
                    'max_return': max_return,
                    'max_drawdown': max_drawdown,
                })
    
    df = pd.DataFrame(all_signals)
    log(f"  共{len(df)}个组合信号")
    
    # 分类
    df_success = df[df['future_10d'] > 0]
    df_failure = df[df['future_10d'] <= 0]
    
    success_rate = len(df_success) / len(df) * 100
    log(f"  成功: {len(df_success)} ({success_rate:.1f}%)")
    log(f"  失败: {len(df_failure)} ({100-success_rate:.1f}%)")
    
    # 分析失败原因
    log("\n" + "="*70)
    log("失效原因分析")
    log("="*70)
    
    # 1. 个股当日涨幅
    log("\n【1. 买入当日涨幅影响】")
    df['today_change_group'] = pd.cut(df['stock_today_change'], 
                                       bins=[-10, -1, 0, 1, 2, 10], 
                                       labels=['下跌(<-1%)', '微跌(-1~0)', '微涨(0~1%)', '小涨(1~2%)', '大涨(>2%)'])
    for group in ['下跌(<-1%)', '微跌(-1~0)', '微涨(0~1%)', '小涨(1~2%)', '大涨(>2%)']:
        subset = df[df['today_change_group'] == group]
        if len(subset) > 0:
            fail_rate = (subset['future_10d'] <= 0).sum() / len(subset) * 100
            avg_return = subset['future_10d'].mean()
            log(f"  {group}: {len(subset)}个, 失败率{fail_rate:.1f}%, 均收{avg_return:+.2f}%")
    
    # 2. 成交量比
    log("\n【2. 成交量影响】")
    df['vol_group'] = pd.cut(df['stock_vol_ratio'], 
                             bins=[0, 0.5, 0.8, 1.0, 1.5, 10], 
                             labels=['极缩量(<0.5)', '缩量(0.5-0.8)', '平量(0.8-1)', '放量(1-1.5)', '大放量(>1.5)'])
    for group in ['极缩量(<0.5)', '缩量(0.5-0.8)', '平量(0.8-1)', '放量(1-1.5)', '大放量(>1.5)']:
        subset = df[df['vol_group'] == group]
        if len(subset) > 0:
            fail_rate = (subset['future_10d'] <= 0).sum() / len(subset) * 100
            avg_return = subset['future_10d'].mean()
            log(f"  {group}: {len(subset)}个, 失败率{fail_rate:.1f}%, 均收{avg_return:+.2f}%")
    
    # 3. 前10日涨幅
    log("\n【3. 前10日涨幅影响】")
    df['gain_10d_group'] = pd.cut(df['stock_gain_10d'], 
                                   bins=[-50, -5, 0, 5, 10, 50], 
                                   labels=['大跌(<-5%)', '小跌(-5~0)', '小涨(0~5%)', '涨5-10%', '大涨(>10%)'])
    for group in ['大跌(<-5%)', '小跌(-5~0)', '小涨(0~5%)', '涨5-10%', '大涨(>10%)']:
        subset = df[df['gain_10d_group'] == group]
        if len(subset) > 0:
            fail_rate = (subset['future_10d'] <= 0).sum() / len(subset) * 100
            avg_return = subset['future_10d'].mean()
            log(f"  {group}: {len(subset)}个, 失败率{fail_rate:.1f}%, 均收{avg_return:+.2f}%")
    
    # 4. 距20日高点
    log("\n【4. 距20日高点影响】")
    df['from_high_group'] = pd.cut(df['stock_from_high'], 
                                    bins=[-50, -15, -10, -5, 0, 10], 
                                    labels=['深跌(<-15%)', '跌10-15%', '跌5-10%', '跌<5%', '新高附近'])
    for group in ['深跌(<-15%)', '跌10-15%', '跌5-10%', '跌<5%', '新高附近']:
        subset = df[df['from_high_group'] == group]
        if len(subset) > 0:
            fail_rate = (subset['future_10d'] <= 0).sum() / len(subset) * 100
            avg_return = subset['future_10d'].mean()
            log(f"  {group}: {len(subset)}个, 失败率{fail_rate:.1f}%, 均收{avg_return:+.2f}%")
    
    # 5. 大盘环境
    log("\n【5. 大盘环境影响】")
    for label, condition in [
        ('大盘在20日线上方', df['market_above_ma20'] == True),
        ('大盘在20日线下方', df['market_above_ma20'] == False),
    ]:
        subset = df[condition]
        if len(subset) > 0:
            fail_rate = (subset['future_10d'] <= 0).sum() / len(subset) * 100
            avg_return = subset['future_10d'].mean()
            log(f"  {label}: {len(subset)}个, 失败率{fail_rate:.1f}%, 均收{avg_return:+.2f}%")
    
    df['market_5d_group'] = pd.cut(df['market_trend_5d'], 
                                    bins=[-20, -2, 0, 2, 20], 
                                    labels=['大盘5日大跌', '大盘5日小跌', '大盘5日小涨', '大盘5日大涨'])
    for group in ['大盘5日大跌', '大盘5日小跌', '大盘5日小涨', '大盘5日大涨']:
        subset = df[df['market_5d_group'] == group]
        if len(subset) > 0:
            fail_rate = (subset['future_10d'] <= 0).sum() / len(subset) * 100
            avg_return = subset['future_10d'].mean()
            log(f"  {group}: {len(subset)}个, 失败率{fail_rate:.1f}%, 均收{avg_return:+.2f}%")
    
    # 6. 板块回撤程度
    log("\n【6. 板块回撤程度影响】")
    df['sector_dd_group'] = pd.cut(df['sector_drawdown'], 
                                    bins=[0, 15, 18, 21, 30], 
                                    labels=['12-15%', '15-18%', '18-21%', '>21%'])
    for group in ['12-15%', '15-18%', '18-21%', '>21%']:
        subset = df[df['sector_dd_group'] == group]
        if len(subset) > 0:
            fail_rate = (subset['future_10d'] <= 0).sum() / len(subset) * 100
            avg_return = subset['future_10d'].mean()
            log(f"  板块回撤{group}: {len(subset)}个, 失败率{fail_rate:.1f}%, 均收{avg_return:+.2f}%")
    
    # 找出最差的组合
    log("\n" + "="*70)
    log("最差案例分析")
    log("="*70)
    
    worst_10 = df_failure.nsmallest(10, 'future_10d')
    for i, (_, row) in enumerate(worst_10.iterrows(), 1):
        log(f"\n  【{i}. {row['sector']} {row['code']}】 日期:{row['date'].strftime('%Y-%m-%d')}")
        log(f"      当日涨幅: {row['stock_today_change']:+.2f}%, 量比: {row['stock_vol_ratio']:.2f}")
        log(f"      前10日: {row['stock_gain_10d']:+.1f}%, 距高点: {row['stock_from_high']:+.1f}%")
        log(f"      板块回撤: {row['sector_drawdown']:.1f}%")
        log(f"      结果: 10日{row['future_10d']:+.1f}%, 最大跌{row['max_drawdown']:+.1f}%")
    
    # 改进建议
    log("\n" + "="*70)
    log("改进方案")
    log("="*70)
    
    # 找最佳条件组合
    log("\n寻找最佳过滤条件...")
    
    conditions = [
        ('当日涨幅<2%', df['stock_today_change'] < 2),
        ('当日涨幅>-1%', df['stock_today_change'] > -1),
        ('量比>0.8', df['stock_vol_ratio'] > 0.8),
        ('量比<1.5', df['stock_vol_ratio'] < 1.5),
        ('前10日涨幅<10%', df['stock_gain_10d'] < 10),
        ('距高点>-10%', df['stock_from_high'] > -10),
        ('大盘在20日线上', df['market_above_ma20'] == True),
        ('板块回撤>15%', df['sector_drawdown'] > 15),
    ]
    
    best_combo = None
    best_score = 0
    
    from itertools import combinations
    for r in range(3, 6):
        for combo in combinations(conditions, r):
            mask = pd.Series([True] * len(df))
            for name, cond in combo:
                mask &= cond
            
            subset = df[mask]
            if len(subset) < 10:
                continue
            
            win_rate = (subset['future_10d'] > 0).sum() / len(subset) * 100
            avg_return = subset['future_10d'].mean()
            score = win_rate * 0.6 + avg_return * 4
            
            if score > best_score:
                best_score = score
                best_combo = (combo, len(subset), win_rate, avg_return)
    
    if best_combo:
        combo, n, wr, ar = best_combo
        log(f"\n【最佳过滤条件】")
        for name, _ in combo:
            log(f"  ✓ {name}")
        log(f"\n  信号数: {n}个")
        log(f"  胜率: {wr:.1f}%")
        log(f"  均收: {ar:+.2f}%")
        
        # 应用改进后对比
        original_wr = (df['future_10d'] > 0).sum() / len(df) * 100
        original_ar = df['future_10d'].mean()
        
        log(f"\n【改进效果】")
        log(f"  原策略: {len(df)}个信号, 胜率{original_wr:.1f}%, 均收{original_ar:+.2f}%")
        log(f"  改进后: {n}个信号, 胜率{wr:.1f}%, 均收{ar:+.2f}%")
        log(f"  胜率提升: {wr - original_wr:+.1f}%")
        log(f"  收益提升: {ar - original_ar:+.2f}%")
    
    log(f"""
======================================================================
改进后的策略条件
======================================================================

【板块筛选】(不变)
1. 60-150天前有爆发(>5%)
2. 回撤12-25%（优选>15%）
3. 近期企稳

【个股筛选】(改进)
1. 近3天横盘(波动<5%)
2. 触及支撑位(-3%~+0.5%)
3. 收盘守住支撑
4. ★ 当日涨幅 -1% ~ +2%（排除追高）
5. ★ 量比 0.8~1.5（平稳换手）
6. ★ 前10日涨幅 <10%（避免高位）

【大盘过滤】
★ 大盘在20日均线上方时操作

【风控】
- 止损: 跌破支撑位-3%
- 止盈: 涨10-15%或持有10-20天
""")
    
    # 保存
    fname = f"组合策略失效分析_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df.to_excel(fname, index=False)
    log(f"\n已保存: {fname}")


if __name__ == "__main__":
    run_analysis()
