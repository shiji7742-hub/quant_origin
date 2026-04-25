"""
基于牛股分析总结的新洗盘策略
除了"涨停破位洗盘"之外的其他模式
"""
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime

def strategy_shrink_consolidation(df: pd.DataFrame) -> dict:
    """
    策略1：缩量横盘整理（宽松版）
    
    核心：上涨后缩量整理
    满足以下条件中的3个即触发
    """
    if len(df) < 35:
        return {"触发": False, "说明": "缩量横盘整理", "条件": "数据不足"}
    
    df = df.copy().reset_index(drop=True)
    df['MA20'] = df['收盘'].rolling(20).mean()
    latest = df.iloc[-1]
    
    conditions = []
    
    # 条件1：前期有上涨（>8%）
    price_30d_ago = df.iloc[-30]['收盘']
    price_10d_ago = df.iloc[-10]['收盘']
    prior_gain = (price_10d_ago - price_30d_ago) / price_30d_ago * 100
    c1 = prior_gain > 8
    conditions.append(('前期涨幅>8%', c1, f'{prior_gain:.1f}%'))
    
    # 条件2：近10日横盘（振幅<15%）
    recent_10 = df.tail(10)
    high_10 = recent_10['最高'].max()
    low_10 = recent_10['最低'].min()
    range_10 = (high_10 - low_10) / low_10 * 100
    c2 = range_10 < 15
    conditions.append(('振幅<15%', c2, f'{range_10:.1f}%'))
    
    # 条件3：缩量
    vol_recent_5 = df['成交量'].tail(5).mean()
    vol_prev_20 = df['成交量'].iloc[-25:-5].mean() if len(df) >= 25 else df['成交量'].mean()
    vol_ratio = vol_recent_5 / vol_prev_20 if vol_prev_20 > 0 else 1
    c3 = vol_ratio < 0.9
    conditions.append(('量比<0.9', c3, f'{vol_ratio:.2f}'))
    
    # 条件4：股价在MA20上方
    c4 = latest['收盘'] > latest['MA20'] if pd.notna(latest['MA20']) else False
    conditions.append(('MA20上方', c4, '是' if c4 else '否'))
    
    # 满足3个条件即触发
    passed = sum([c[1] for c in conditions])
    triggered = passed >= 3
    
    cond_str = ', '.join([f"{c[0]}:{c[2]}{'✓' if c[1] else '✗'}" for c in conditions])
    
    return {
        "触发": triggered,
        "说明": f"缩量横盘整理（{passed}/4条件）",
        "条件": cond_str
    }


def strategy_deep_pullback_support(df: pd.DataFrame) -> dict:
    """
    策略2：深度回调支撑（宽松版）
    
    核心：回调到均线支撑位
    """
    if len(df) < 35:
        return {"触发": False, "说明": "深度回调支撑", "条件": "数据不足"}
    
    df = df.copy().reset_index(drop=True)
    df['MA20'] = df['收盘'].rolling(20).mean()
    latest = df.iloc[-1]
    
    conditions = []
    
    # 条件1：有回调（距30日高点回撤>8%）
    high_30d = df.tail(30)['最高'].max()
    current_price = latest['收盘']
    pullback = (current_price - high_30d) / high_30d * 100
    c1 = pullback < -8
    conditions.append(('回撤>8%', c1, f'{pullback:.1f}%'))
    
    # 条件2：在MA20附近（±8%）
    ma20 = latest['MA20']
    near_ma20 = abs(current_price - ma20) / ma20 < 0.08 if pd.notna(ma20) else False
    c2 = near_ma20
    conditions.append(('MA20附近', c2, f'{(current_price-ma20)/ma20*100:.1f}%' if pd.notna(ma20) else '-'))
    
    # 条件3：今日收阳或有下影线
    is_red = latest['收盘'] > latest['开盘']
    body = abs(latest['收盘'] - latest['开盘'])
    lower_shadow = min(latest['开盘'], latest['收盘']) - latest['最低']
    c3 = is_red or (lower_shadow > body * 0.3)
    conditions.append(('止跌信号', c3, '阳线' if is_red else '下影线'))
    
    # 满足全部条件
    passed = sum([c[1] for c in conditions])
    triggered = passed >= 3
    
    cond_str = ', '.join([f"{c[0]}:{c[2]}{'✓' if c[1] else '✗'}" for c in conditions])
    
    return {
        "触发": triggered,
        "说明": f"深度回调支撑（{passed}/3条件）",
        "条件": cond_str
    }


def strategy_box_breakout(df: pd.DataFrame) -> dict:
    """
    策略3：箱体突破（宽松版）
    
    核心：震荡后放量突破
    """
    if len(df) < 20:
        return {"触发": False, "说明": "箱体突破", "条件": "数据不足"}
    
    df = df.copy().reset_index(drop=True)
    latest = df.iloc[-1]
    
    # 近15日箱体（不含今日）
    box_data = df.iloc[-16:-1]
    box_high = box_data['最高'].max()
    box_low = box_data['最低'].min()
    box_range = (box_high - box_low) / box_low * 100
    
    conditions = []
    
    # 条件1：有箱体（振幅5-30%）
    c1 = 5 < box_range < 30
    conditions.append(('箱体5-30%', c1, f'{box_range:.1f}%'))
    
    # 条件2：今日突破箱体上沿
    c2 = latest['收盘'] > box_high
    conditions.append(('突破上沿', c2, '是' if c2 else '否'))
    
    # 条件3：放量（量比>1.0）
    vol_ma5 = df['成交量'].iloc[-6:-1].mean()
    vol_ratio = latest['成交量'] / vol_ma5 if vol_ma5 > 0 else 0
    c3 = vol_ratio > 1.0
    conditions.append(('放量>1.0', c3, f'{vol_ratio:.2f}'))
    
    passed = sum([c[1] for c in conditions])
    triggered = passed >= 3
    
    cond_str = ', '.join([f"{c[0]}:{c[2]}{'✓' if c[1] else '✗'}" for c in conditions])
    
    return {
        "触发": triggered,
        "说明": f"箱体突破（{passed}/3条件）",
        "条件": cond_str
    }


def strategy_ma_convergence_divergence(df: pd.DataFrame) -> dict:
    """
    策略4：均线粘合发散（宽松版）
    
    核心：均线粘合后放量突破
    """
    if len(df) < 25:
        return {"触发": False, "说明": "均线粘合发散", "条件": "数据不足"}
    
    df = df.copy().reset_index(drop=True)
    
    df['MA5'] = df['收盘'].rolling(5).mean()
    df['MA10'] = df['收盘'].rolling(10).mean()
    df['MA20'] = df['收盘'].rolling(20).mean()
    
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    if pd.isna(prev['MA5']) or pd.isna(prev['MA10']) or pd.isna(prev['MA20']):
        return {"触发": False, "说明": "均线粘合发散", "条件": "均线数据不足"}
    
    conditions = []
    
    # 条件1：均线粘合（间距<8%）
    ma_values = [prev['MA5'], prev['MA10'], prev['MA20']]
    ma_max = max(ma_values)
    ma_min = min(ma_values)
    ma_spread = (ma_max - ma_min) / ma_min * 100
    c1 = ma_spread < 8
    conditions.append(('均线粘合<8%', c1, f'{ma_spread:.1f}%'))
    
    # 条件2：今日放量（量比>1.0）
    vol_ma5 = df['成交量'].iloc[-6:-1].mean()
    vol_ratio = latest['成交量'] / vol_ma5 if vol_ma5 > 0 else 0
    c2 = vol_ratio > 1.0
    conditions.append(('放量>1.0', c2, f'{vol_ratio:.2f}'))
    
    # 条件3：收阳线
    today_gain = (latest['收盘'] - latest['开盘']) / latest['开盘'] * 100
    c3 = today_gain > 0.5
    conditions.append(('收阳>0.5%', c3, f'{today_gain:.1f}%'))
    
    passed = sum([c[1] for c in conditions])
    triggered = passed >= 3
    
    cond_str = ', '.join([f"{c[0]}:{c[2]}{'✓' if c[1] else '✗'}" for c in conditions])
    
    return {
        "触发": triggered,
        "说明": f"均线粘合发散（{passed}/3条件）",
        "条件": cond_str
    }


def strategy_volume_bottom(df: pd.DataFrame) -> dict:
    """
    策略5：地量见底（宽松版）
    
    核心：低位缩量后放量反弹
    """
    if len(df) < 25:
        return {"触发": False, "说明": "地量见底", "条件": "数据不足"}
    
    df = df.copy().reset_index(drop=True)
    latest = df.iloc[-1]
    
    conditions = []
    
    # 条件1：近期量能较低（近5日均量<前20日均量的80%）
    vol_recent_5 = df['成交量'].tail(6).iloc[:-1].mean()
    vol_prev_20 = df['成交量'].iloc[-25:-5].mean() if len(df) >= 25 else df['成交量'].mean()
    vol_ratio_5d = vol_recent_5 / vol_prev_20 if vol_prev_20 > 0 else 1
    c1 = vol_ratio_5d < 0.8
    conditions.append(('近期缩量<0.8', c1, f'{vol_ratio_5d:.2f}'))
    
    # 条件2：股价在相对低位（距20日高点回撤>5%）
    high_20d = df['最高'].tail(20).max()
    current_price = latest['收盘']
    pullback = (current_price - high_20d) / high_20d * 100
    c2 = pullback < -5
    conditions.append(('回撤>5%', c2, f'{pullback:.1f}%'))
    
    # 条件3：今日放量阳线（量比>1.2，收阳）
    vol_ma5 = df['成交量'].iloc[-6:-1].mean()
    vol_ratio = latest['成交量'] / vol_ma5 if vol_ma5 > 0 else 0
    today_gain = (latest['收盘'] - latest['开盘']) / latest['开盘'] * 100
    c3 = vol_ratio > 1.2 and today_gain > 0
    conditions.append(('放量阳线', c3, f'量比{vol_ratio:.2f},涨{today_gain:.1f}%'))
    
    passed = sum([c[1] for c in conditions])
    triggered = passed >= 3
    
    cond_str = ', '.join([f"{c[0]}:{c[2]}{'✓' if c[1] else '✗'}" for c in conditions])
    
    return {
        "触发": triggered,
        "说明": f"地量见底（{passed}/3条件）",
        "条件": cond_str
    }


def check_all_new_strategies(df: pd.DataFrame) -> dict:
    """检测所有新策略"""
    results = {}
    
    results['缩量横盘整理'] = strategy_shrink_consolidation(df)
    results['深度回调支撑'] = strategy_deep_pullback_support(df)
    results['箱体突破'] = strategy_box_breakout(df)
    results['均线粘合发散'] = strategy_ma_convergence_divergence(df)
    results['地量见底'] = strategy_volume_bottom(df)
    
    return results


def print_strategies_summary():
    """打印策略汇总"""
    print("=" * 70)
    print("基于牛股分析总结的5种新洗盘策略")
    print("=" * 70)
    
    strategies = [
        {
            "名称": "1. 缩量横盘整理",
            "特征": "前期上涨>15% → 横盘振幅<8% → 量能萎缩<60% → 均线多头",
            "逻辑": "主力拉升后横盘洗盘，缩量说明浮筹洗干净",
            "买点": "横盘末期放量突破时"
        },
        {
            "名称": "2. 深度回调支撑",
            "特征": "大涨>7% → 回调15-25% → 到达MA20/MA30 → 止跌信号",
            "逻辑": "深度回调洗掉获利盘，在均线支撑位企稳",
            "买点": "均线支撑位出现止跌K线时"
        },
        {
            "名称": "3. 箱体突破",
            "特征": "20日箱体震荡(10-20%) → 放量突破上沿 → 收盘站稳",
            "逻辑": "箱体震荡是洗盘，突破是启动信号",
            "买点": "放量突破箱体上沿当日"
        },
        {
            "名称": "4. 均线粘合发散",
            "特征": "MA5/10/20粘合(<3%) → 放量向上发散 → 收阳>2%",
            "逻辑": "均线粘合说明多空平衡，向上发散是启动",
            "买点": "均线发散当日"
        },
        {
            "名称": "5. 地量见底",
            "特征": "成交量创20日新低 → 股价回撤>10% → 放量阳线",
            "逻辑": "地量说明抛压枯竭，放量阳线是资金进场",
            "买点": "地量后首根放量阳线"
        }
    ]
    
    for s in strategies:
        print(f"\n【{s['名称']}】")
        print(f"  特征: {s['特征']}")
        print(f"  逻辑: {s['逻辑']}")
        print(f"  买点: {s['买点']}")
    
    print("\n" + "=" * 70)
    print("与原有策略对比")
    print("=" * 70)
    print("""
原策略：涨停破位洗盘
  - 涨停 → 跌破涨停最低价 → 大阳反包
  - 适用：有涨停板的强势股

新策略补充：
  1. 缩量横盘 - 适用：稳健上涨后的整理
  2. 深度回调 - 适用：急涨后的深度洗盘
  3. 箱体突破 - 适用：长期震荡后的启动
  4. 均线粘合 - 适用：趋势不明朗时的方向选择
  5. 地量见底 - 适用：下跌末期的抄底

建议：
  - 涨停破位洗盘：适合追强势股
  - 新策略：适合稳健型选股，可以更早介入
""")


if __name__ == "__main__":
    print_strategies_summary()
