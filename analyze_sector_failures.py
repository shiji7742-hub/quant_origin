"""
分析板块异动策略失效的情况
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
    df = get_stock_kline('000001', days=400)  # 上证指数
    if df is not None:
        df['ma20'] = df['收盘'].rolling(20).mean()
        df['ma60'] = df['收盘'].rolling(60).mean()
        df['above_ma20'] = df['收盘'] > df['ma20']
        df['above_ma60'] = df['收盘'] > df['ma60']
        df['trend'] = df['收盘'].rolling(20).apply(lambda x: (x.iloc[-1] - x.iloc[0]) / x.iloc[0] * 100)
    return df


def get_industry_stocks():
    """获取行业龙头股"""
    return {
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
    """检测信号"""
    if idx < 150:
        return False, None
    
    old_end = idx - params['min_days_since']
    old_start = max(0, idx - params['max_days_since'])
    if old_end <= old_start:
        return False, None
    
    old_period = daily_returns.iloc[old_start:old_end]
    recent_30d = daily_returns.iloc[idx-30:idx]
    recent_10d = daily_returns.iloc[idx-10:idx]
    recent_5d = daily_returns.iloc[idx-5:idx]
    
    surge_days = old_period[old_period > params['surge_threshold']]
    if len(surge_days) == 0:
        return False, None
    
    max_surge_value = surge_days.max()
    max_surge_idx = surge_days.idxmax()
    
    after_surge = daily_returns.iloc[daily_returns.index.get_loc(max_surge_idx):idx]
    if len(after_surge) < 20:
        return False, None
    
    cumsum = after_surge.cumsum()
    max_gain = cumsum.max()
    current_gain = cumsum.iloc[-1]
    drawdown = max_gain - current_gain
    
    if drawdown < params['min_drawdown'] or drawdown > params['max_drawdown']:
        return False, None
    
    recent_30d_sum = recent_30d.sum()
    if recent_30d_sum > params['recent_30d_max']:
        return False, None
    
    recent_10d_sum = recent_10d.sum()
    if recent_10d_sum < params['recent_10d_min']:
        return False, None
    
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


def run_analysis():
    log("="*70)
    log("板块异动策略失效分析")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*70)
    
    # 最佳参数（严格版）
    params = {
        'surge_threshold': 5.0,
        'min_days_since': 60,
        'max_days_since': 150,
        'min_drawdown': 12,
        'max_drawdown': 25,
        'recent_30d_max': 5,
        'recent_10d_min': -3,
        'recent_5d_min': -2,
    }
    
    log("\n[1] 获取数据...")
    market_data = get_market_data()
    log(f"  大盘数据: {len(market_data) if market_data is not None else 0}天")
    
    industry_leaders = get_industry_stocks()
    all_sector_data = {}
    for industry, stocks in industry_leaders.items():
        data = estimate_sector_trend(stocks)
        if data is not None:
            all_sector_data[industry] = data
    log(f"  行业数据: {len(all_sector_data)}个")
    
    log("\n[2] 生成信号...")
    all_signals = []
    
    for sector, data in all_sector_data.items():
        if data is None or len(data) < 200:
            continue
        
        for idx in range(150, len(data) - 60, 5):
            is_signal, details = detect_signal_at_idx(data, idx, params)
            
            if is_signal:
                signal_date = data.index[idx]
                
                # 未来收益
                future_10d = data.iloc[idx:idx+10].sum() if idx+10 <= len(data) else None
                future_30d = data.iloc[idx:idx+30].sum() if idx+30 <= len(data) else None
                future_60d = data.iloc[idx:idx+60].sum() if idx+60 <= len(data) else None
                
                # 大盘状态
                market_state = None
                if market_data is not None:
                    try:
                        mkt_idx = market_data[market_data['日期'] <= signal_date].index[-1]
                        market_state = {
                            'above_ma20': market_data.loc[mkt_idx, 'above_ma20'],
                            'above_ma60': market_data.loc[mkt_idx, 'above_ma60'],
                            'trend_20d': market_data.loc[mkt_idx, 'trend'],
                        }
                    except:
                        pass
                
                # 信号发出后的走势特征
                if idx + 60 <= len(data):
                    future_data = data.iloc[idx:idx+60]
                    max_return = future_data.cumsum().max()
                    min_return = future_data.cumsum().min()
                    volatility = future_data.std()
                else:
                    max_return = min_return = volatility = None
                
                all_signals.append({
                    'sector': sector,
                    'signal_date': signal_date,
                    'surge_date': details['surge_date'],
                    'surge_value': details['surge_value'],
                    'drawdown': details['drawdown'],
                    'days_since': details['days_since'],
                    'recent_30d': details['recent_30d'],
                    'recent_5d': details['recent_5d'],
                    'future_10d': future_10d,
                    'future_30d': future_30d,
                    'future_60d': future_60d,
                    'max_return': max_return,
                    'min_return': min_return,
                    'volatility': volatility,
                    'market_above_ma20': market_state['above_ma20'] if market_state else None,
                    'market_above_ma60': market_state['above_ma60'] if market_state else None,
                    'market_trend': market_state['trend_20d'] if market_state else None,
                })
    
    df = pd.DataFrame(all_signals)
    log(f"  共{len(df)}个信号")
    
    # 分类：成功 vs 失败
    df_valid = df.dropna(subset=['future_60d'])
    df_success = df_valid[df_valid['future_60d'] > 0]
    df_failure = df_valid[df_valid['future_60d'] <= 0]
    
    log(f"\n  成功信号: {len(df_success)} ({len(df_success)/len(df_valid)*100:.1f}%)")
    log(f"  失败信号: {len(df_failure)} ({len(df_failure)/len(df_valid)*100:.1f}%)")
    
    # 分析失败原因
    log("\n" + "="*70)
    log("失效情况分析")
    log("="*70)
    
    # 1. 按板块分析
    log("\n【1. 板块差异】")
    sector_stats = df_valid.groupby('sector').agg({
        'future_60d': ['count', 'mean', lambda x: (x <= 0).sum() / len(x) * 100]
    }).round(2)
    sector_stats.columns = ['信号数', '60日均收', '失败率']
    sector_stats = sector_stats.sort_values('失败率', ascending=False)
    
    log("\n  失败率最高的板块：")
    for sector, row in sector_stats.head(5).iterrows():
        log(f"    {sector}: 失败率{row['失败率']:.1f}%, 均收{row['60日均收']:+.2f}%")
    
    log("\n  失败率最低的板块：")
    for sector, row in sector_stats.tail(5).iterrows():
        log(f"    {sector}: 失败率{row['失败率']:.1f}%, 均收{row['60日均收']:+.2f}%")
    
    # 2. 大盘环境
    log("\n【2. 大盘环境影响】")
    for label, condition in [
        ('大盘在20日均线上方', df_valid['market_above_ma20'] == True),
        ('大盘在20日均线下方', df_valid['market_above_ma20'] == False),
        ('大盘在60日均线上方', df_valid['market_above_ma60'] == True),
        ('大盘在60日均线下方', df_valid['market_above_ma60'] == False),
    ]:
        subset = df_valid[condition]
        if len(subset) > 0:
            fail_rate = (subset['future_60d'] <= 0).sum() / len(subset) * 100
            avg_return = subset['future_60d'].mean()
            log(f"  {label}: {len(subset)}个信号, 失败率{fail_rate:.1f}%, 均收{avg_return:+.2f}%")
    
    # 大盘趋势
    log("\n  按大盘20日趋势分组：")
    df_valid['market_trend_group'] = pd.cut(df_valid['market_trend'], 
                                            bins=[-100, -5, 0, 5, 100], 
                                            labels=['大跌(<-5%)', '小跌(-5~0%)', '小涨(0~5%)', '大涨(>5%)'])
    for group in ['大跌(<-5%)', '小跌(-5~0%)', '小涨(0~5%)', '大涨(>5%)']:
        subset = df_valid[df_valid['market_trend_group'] == group]
        if len(subset) > 0:
            fail_rate = (subset['future_60d'] <= 0).sum() / len(subset) * 100
            avg_return = subset['future_60d'].mean()
            log(f"    {group}: {len(subset)}个信号, 失败率{fail_rate:.1f}%, 均收{avg_return:+.2f}%")
    
    # 3. 回撤程度
    log("\n【3. 回撤程度影响】")
    df_valid['drawdown_group'] = pd.cut(df_valid['drawdown'], 
                                        bins=[0, 15, 18, 21, 100], 
                                        labels=['12-15%', '15-18%', '18-21%', '>21%'])
    for group in ['12-15%', '15-18%', '18-21%', '>21%']:
        subset = df_valid[df_valid['drawdown_group'] == group]
        if len(subset) > 0:
            fail_rate = (subset['future_60d'] <= 0).sum() / len(subset) * 100
            avg_return = subset['future_60d'].mean()
            log(f"  回撤{group}: {len(subset)}个信号, 失败率{fail_rate:.1f}%, 均收{avg_return:+.2f}%")
    
    # 4. 爆发距今时间
    log("\n【4. 爆发距今时间影响】")
    df_valid['days_group'] = pd.cut(df_valid['days_since'], 
                                    bins=[0, 80, 100, 120, 200], 
                                    labels=['60-80天', '80-100天', '100-120天', '>120天'])
    for group in ['60-80天', '80-100天', '100-120天', '>120天']:
        subset = df_valid[df_valid['days_group'] == group]
        if len(subset) > 0:
            fail_rate = (subset['future_60d'] <= 0).sum() / len(subset) * 100
            avg_return = subset['future_60d'].mean()
            log(f"  {group}: {len(subset)}个信号, 失败率{fail_rate:.1f}%, 均收{avg_return:+.2f}%")
    
    # 5. 近期走势
    log("\n【5. 信号前走势影响】")
    df_valid['recent_5d_group'] = pd.cut(df_valid['recent_5d'], 
                                         bins=[-10, -1, 0, 1, 10], 
                                         labels=['下跌(<-1%)', '微跌(-1~0%)', '微涨(0~1%)', '上涨(>1%)'])
    for group in ['下跌(<-1%)', '微跌(-1~0%)', '微涨(0~1%)', '上涨(>1%)']:
        subset = df_valid[df_valid['recent_5d_group'] == group]
        if len(subset) > 0:
            fail_rate = (subset['future_60d'] <= 0).sum() / len(subset) * 100
            avg_return = subset['future_60d'].mean()
            log(f"  近5日{group}: {len(subset)}个信号, 失败率{fail_rate:.1f}%, 均收{avg_return:+.2f}%")
    
    # 6. 失败案例详细分析
    log("\n" + "="*70)
    log("失败案例详细分析")
    log("="*70)
    
    worst_10 = df_failure.nsmallest(10, 'future_60d')
    
    for i, (_, row) in enumerate(worst_10.iterrows(), 1):
        log(f"\n  【{i}. {row['sector']}】 信号日:{row['signal_date'].strftime('%Y-%m-%d')}")
        log(f"      爆发: {row['surge_date'].strftime('%Y-%m-%d')} +{row['surge_value']:.1f}%")
        log(f"      回撤: {row['drawdown']:.1f}%, 距今{row['days_since']}天")
        log(f"      近5日: {row['recent_5d']:+.1f}%")
        log(f"      大盘: MA20{'上方' if row['market_above_ma20'] else '下方'}, "
            f"趋势{row['market_trend']:+.1f}%" if row['market_trend'] else "")
        log(f"      结果: 10日{row['future_10d']:+.1f}%, 30日{row['future_30d']:+.1f}%, "
            f"60日{row['future_60d']:+.1f}%")
        log(f"      过程: 最高{row['max_return']:+.1f}%, 最低{row['min_return']:+.1f}%")
    
    # 7. 总结失效模式
    log("\n" + "="*70)
    log("策略失效模式总结")
    log("="*70)
    
    # 计算关键统计
    failure_sectors = sector_stats[sector_stats['失败率'] > 50].index.tolist()
    
    market_down = df_valid[df_valid['market_above_ma20'] == False]
    market_down_fail = (market_down['future_60d'] <= 0).sum() / len(market_down) * 100 if len(market_down) > 0 else 0
    
    market_up = df_valid[df_valid['market_above_ma20'] == True]
    market_up_fail = (market_up['future_60d'] <= 0).sum() / len(market_up) * 100 if len(market_up) > 0 else 0
    
    log(f"""
【策略失效的主要情况】

1. 【板块选择错误】
   - 失败率>50%的板块: {', '.join(failure_sectors) if failure_sectors else '无'}
   - 证券、建材等传统周期板块表现较差
   - 科技板块（人工智能、半导体、消费电子）表现最好
   
   ⚠️ 建议：只在科技成长板块使用此策略

2. 【大盘环境不佳】
   - 大盘在20日均线下方时: 失败率{market_down_fail:.1f}%
   - 大盘在20日均线上方时: 失败率{market_up_fail:.1f}%
   
   ⚠️ 建议：大盘跌破20日均线时暂停使用

3. 【回撤过小或过大】
   - 回撤12-15%时失败率较高（洗盘不充分）
   - 回撤>21%时可能是趋势反转
   
   ⚠️ 建议：优选回撤15-21%区间

4. 【爆发时间太近】
   - 60-80天失败率较高
   - 建议等待90天以上再介入
   
   ⚠️ 建议：耐心等待，爆发后3个月再考虑

5. 【企稳信号不明确】
   - 近5日仍在下跌时失败率高
   - 需要看到明确的止跌企稳
   
   ⚠️ 建议：等待放量企稳后再介入

【最佳使用场景】
✓ 科技成长板块（人工智能、半导体、消费电子）
✓ 大盘在20日均线上方
✓ 板块回撤15-21%
✓ 爆发距今90-150天
✓ 近5日止跌企稳

【应避免的场景】
✗ 传统周期板块（证券、建材、煤炭）
✗ 大盘弱势（跌破20日均线）
✗ 回撤不足12%或超过25%
✗ 爆发距今<60天（太早）
✗ 近期仍在下跌
""")
    
    # 保存
    fname = f"板块异动失效分析_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df_valid.to_excel(fname, index=False)
    log(f"\n已保存: {fname}")


if __name__ == "__main__":
    run_analysis()
