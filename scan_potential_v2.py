"""
扫描潜力板块 V2 - 放宽条件，扩大扫描范围
"""
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime
from backtest_sector_surge import get_market_data, is_market_bullish

def get_all_sectors():
    """获取所有概念板块"""
    try:
        df = ak.stock_board_concept_name_em()
        return df
    except Exception as e:
        print(f"获取板块列表失败: {e}")
        return pd.DataFrame()

def get_sector_history(sector_name, start_date='20250901', end_date='20260115'):
    """获取板块历史数据"""
    try:
        df = ak.stock_board_concept_cons_em(symbol=sector_name)
        if df is None or len(df) == 0:
            return None
        
        top_stocks = df.head(3)['代码'].tolist()
        
        all_data = []
        for symbol in top_stocks:
            try:
                hist = ak.stock_zh_a_hist(
                    symbol=symbol, 
                    period="daily", 
                    start_date=start_date,
                    end_date=end_date,
                    adjust="qfq"
                )
                if hist is not None and len(hist) > 30:
                    hist['涨跌幅'] = hist['收盘'].pct_change() * 100
                    hist['日期'] = pd.to_datetime(hist['日期'])
                    all_data.append(hist[['日期', '涨跌幅']].set_index('日期'))
            except:
                continue
        
        if len(all_data) == 0:
            return None
        
        combined = pd.concat([d['涨跌幅'] for d in all_data], axis=1)
        return combined.mean(axis=1)
    except:
        return None

def detect_potential_signal_v2(daily_returns, market_data=None):
    """
    V2版本 - 放宽条件
    
    条件：
    1. 过去60天内有过爆发（单日>2.5%）- 放宽
    2. 爆发后有回撤（3-18%）- 放宽
    3. 近期表现弱（近15日累计<8%）- 放宽
    4. 近5日不能大跌（>-8%）- 放宽
    """
    if daily_returns is None or len(daily_returns) < 50:
        return False, None
    
    daily_returns = daily_returns.dropna()
    
    if len(daily_returns) < 50:
        return False, None
    
    # 分段
    old_period = daily_returns.iloc[:-15]
    recent_15d = daily_returns.iloc[-15:]
    recent_5d = daily_returns.iloc[-5:]
    
    # 条件1：找爆发（单日>2.5%）
    surge_days = old_period[old_period > 2.5]
    
    if len(surge_days) == 0:
        return False, None
    
    max_surge_value = surge_days.max()
    max_surge_idx = surge_days.idxmax()
    surge_count = len(surge_days)
    
    # 爆发后数据
    after_surge = daily_returns[daily_returns.index >= max_surge_idx]
    
    if len(after_surge) < 8:
        return False, None
    
    # 计算指标
    cumulative_after = after_surge.sum()
    recent_15d_sum = recent_15d.sum()
    recent_5d_sum = recent_5d.sum()
    
    # 计算回撤
    cumsum = after_surge.cumsum()
    max_gain = cumsum.max()
    current_gain = cumsum.iloc[-1]
    drawdown = max_gain - current_gain
    
    # 条件2：回撤在3-18%之间
    if drawdown < 3 or drawdown > 18:
        return False, None
    
    # 条件3：近期弱
    recent_weak = recent_15d_sum < 8
    
    # 条件4：近5日不大跌
    not_crashing = recent_5d_sum > -8
    
    # 条件5：没有走出主升
    no_main_rise = cumulative_after < max_surge_value * 4
    
    if no_main_rise and recent_weak and not_crashing:
        # 计算各月涨幅
        monthly_returns = {}
        for month in ['2025-09', '2025-10', '2025-11', '2025-12', '2026-01']:
            month_data = daily_returns[daily_returns.index.strftime('%Y-%m') == month]
            if len(month_data) > 0:
                monthly_returns[month] = round(month_data.sum(), 1)
        
        # 计算评分
        score = 0
        # 回撤越大越好（洗盘充分）
        if drawdown >= 8:
            score += 3
        elif drawdown >= 5:
            score += 2
        else:
            score += 1
        
        # 爆发次数越多越好（资金关注度高）
        if surge_count >= 5:
            score += 3
        elif surge_count >= 3:
            score += 2
        else:
            score += 1
        
        # 近期企稳加分
        if -3 < recent_5d_sum < 3:
            score += 2
        
        # 爆发强度
        if max_surge_value >= 5:
            score += 2
        elif max_surge_value >= 3:
            score += 1
        
        return True, {
            'surge_date': max_surge_idx.strftime('%Y-%m-%d'),
            'surge_value': round(max_surge_value, 2),
            'surge_count': surge_count,
            'drawdown': round(drawdown, 2),
            'recent_15d': round(recent_15d_sum, 2),
            'recent_5d': round(recent_5d_sum, 2),
            'cumulative_after': round(cumulative_after, 2),
            'monthly_returns': monthly_returns,
            'score': score
        }
    
    return False, None

def scan_all_sectors():
    """扫描所有板块"""
    print("=" * 70)
    print("潜力板块扫描 V2 - 全市场扫描")
    print("=" * 70)
    print(f"\n扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\n扫描条件（放宽版）：")
    print("  1. 过去60天内有过爆发（单日>2.5%）")
    print("  2. 爆发后回撤3-18%")
    print("  3. 近15日表现弱(<8%)")
    print("  4. 近5日不大跌(>-8%)")
    
    print("\n获取大盘数据...")
    market_data = get_market_data('20250901', '20260115')
    
    print("获取板块列表...")
    df = get_all_sectors()
    
    if df.empty:
        print("获取板块列表失败")
        return []
    
    total = len(df)
    print(f"共 {total} 个板块")
    
    results = []
    
    for i, (_, sector) in enumerate(df.iterrows()):
        name = sector['板块名称']
        today_change = float(sector['涨跌幅'])
        
        print(f"[{i+1}/{total}] {name}...", end=" ")
        
        data = get_sector_history(name, '20250901', '20260115')
        
        if data is None:
            print("×")
            continue
        
        is_potential, details = detect_potential_signal_v2(data, market_data)
        
        if is_potential:
            print(f"✓ 评分:{details['score']}")
            results.append({
                '板块名称': name,
                '板块代码': sector['板块代码'],
                '当日涨幅': today_change,
                '上涨家数': int(sector['上涨家数']),
                '下跌家数': int(sector['下跌家数']),
                **details
            })
        else:
            print("×")
    
    # 按评分排序
    results = sorted(results, key=lambda x: x['score'], reverse=True)
    
    return results

def print_results(results):
    """打印结果"""
    if not results:
        print("\n未发现符合条件的板块")
        return
    
    print("\n" + "=" * 70)
    print(f"发现 {len(results)} 个潜力板块（按评分排序）")
    print("=" * 70)
    
    # 分级显示
    high_score = [r for r in results if r['score'] >= 7]
    mid_score = [r for r in results if 5 <= r['score'] < 7]
    low_score = [r for r in results if r['score'] < 5]
    
    if high_score:
        print("\n" + "★" * 20)
        print("【高潜力板块】评分≥7")
        print("★" * 20)
        for i, r in enumerate(high_score, 1):
            print(f"\n{i}. 【{r['板块名称']}】 评分:{r['score']}")
            print(f"   爆发: {r['surge_date']} +{r['surge_value']}% ({r['surge_count']}次)")
            print(f"   回撤: {r['drawdown']}% | 近15日: {r['recent_15d']}% | 近5日: {r['recent_5d']}%")
            print(f"   今日: {r['当日涨幅']:.2f}%")
            if 'monthly_returns' in r:
                monthly = r['monthly_returns']
                print(f"   月度: ", end="")
                for month, ret in monthly.items():
                    m = month.split('-')[1]
                    print(f"{m}月:{ret:+.0f}% ", end="")
                print()
    
    if mid_score:
        print("\n" + "-" * 40)
        print("【中等潜力板块】评分5-6")
        print("-" * 40)
        for i, r in enumerate(mid_score, 1):
            print(f"\n{i}. 【{r['板块名称']}】 评分:{r['score']}")
            print(f"   爆发: {r['surge_date']} +{r['surge_value']}% ({r['surge_count']}次)")
            print(f"   回撤: {r['drawdown']}% | 近15日: {r['recent_15d']}% | 近5日: {r['recent_5d']}%")
    
    if low_score and len(low_score) <= 10:
        print("\n" + "-" * 40)
        print("【一般潜力板块】评分<5")
        print("-" * 40)
        for r in low_score[:10]:
            print(f"  {r['板块名称']}: 评分{r['score']}, 回撤{r['drawdown']}%")
    elif low_score:
        print(f"\n另有 {len(low_score)} 个一般潜力板块（评分<5）")
    
    # 总结
    print("\n" + "=" * 70)
    print("【投资建议】")
    print("=" * 70)
    print("\n高潜力板块特征：")
    print("  - 早期有多次爆发（资金关注度高）")
    print("  - 回撤充分（8%以上，洗盘到位）")
    print("  - 近期企稳（不再大跌）")
    print("\n风险提示：")
    print("  - 本分析基于技术面，需结合基本面判断")
    print("  - 建议关注板块龙头股")
    print("  - 设置止损，控制仓位")

if __name__ == "__main__":
    results = scan_all_sectors()
    print_results(results)
