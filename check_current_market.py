"""
分析当前大盘位置（2026年1月16日）
"""
import akshare as ak
import pandas as pd

def analyze_current():
    print("获取大盘数据...")
    df = ak.stock_zh_index_daily(symbol="sh000001")
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date')
    
    # 最近数据
    recent = df[df.index >= '2025-09-01']
    
    # 计算指标
    df['ma5'] = df['close'].rolling(5).mean()
    df['ma10'] = df['close'].rolling(10).mean()
    df['ma20'] = df['close'].rolling(20).mean()
    df['ma60'] = df['close'].rolling(60).mean()
    
    # 当前数据
    today = df.iloc[-1]
    today_date = df.index[-1]
    
    print("\n" + "=" * 70)
    print(f"当前大盘分析 ({today_date.strftime('%Y-%m-%d')})")
    print("=" * 70)
    
    print(f"\n【当前点位】")
    print(f"  收盘价: {today['close']:.0f}")
    print(f"  MA5:  {today['ma5']:.0f}")
    print(f"  MA10: {today['ma10']:.0f}")
    print(f"  MA20: {today['ma20']:.0f}")
    print(f"  MA60: {today['ma60']:.0f}")
    
    # 均线位置
    print(f"\n【均线关系】")
    print(f"  站上MA5:  {'是' if today['close'] > today['ma5'] else '否'}")
    print(f"  站上MA10: {'是' if today['close'] > today['ma10'] else '否'}")
    print(f"  站上MA20: {'是' if today['close'] > today['ma20'] else '否'}")
    print(f"  站上MA60: {'是' if today['close'] > today['ma60'] else '否'}")
    
    # 近期走势
    print(f"\n【近期走势】")
    
    # 计算各时间段涨跌
    periods = [
        ('近5日', 5),
        ('近10日', 10),
        ('近20日', 20),
        ('近60日', 60),
    ]
    
    for name, days in periods:
        if len(df) > days:
            start_price = df['close'].iloc[-days-1]
            end_price = today['close']
            change = (end_price / start_price - 1) * 100
            print(f"  {name}: {change:+.2f}%")
    
    # 相对位置
    print(f"\n【相对位置】")
    
    # 2025年高低点
    df_2025 = df[df.index >= '2025-01-01']
    high_2025 = df_2025['close'].max()
    low_2025 = df_2025['close'].min()
    high_date = df_2025['close'].idxmax()
    low_date = df_2025['close'].idxmin()
    
    position_2025 = (today['close'] - low_2025) / (high_2025 - low_2025) * 100
    
    print(f"  2025年最高: {high_2025:.0f} ({high_date.strftime('%Y-%m-%d')})")
    print(f"  2025年最低: {low_2025:.0f} ({low_date.strftime('%Y-%m-%d')})")
    print(f"  当前位置: {position_2025:.0f}% (0%=最低, 100%=最高)")
    print(f"  距离高点: {(today['close']/high_2025-1)*100:.1f}%")
    print(f"  距离低点: {(today['close']/low_2025-1)*100:.1f}%")
    
    # 近3个月走势
    print(f"\n【近3个月走势】")
    for month in ['2025-11', '2025-12', '2026-01']:
        month_df = df[df.index.strftime('%Y-%m') == month]
        if len(month_df) > 0:
            month_return = (month_df['close'].iloc[-1] / month_df['close'].iloc[0] - 1) * 100
            print(f"  {month}: {month_return:+.2f}%")
    
    # 判断阶段
    print("\n" + "=" * 70)
    print("【阶段判断】")
    print("=" * 70)
    
    # 判断逻辑
    if position_2025 > 80:
        stage = "高位震荡"
        risk = "较高"
        suggestion = "不建议追高，等待回调"
    elif position_2025 > 60:
        stage = "中高位"
        risk = "中等"
        suggestion = "可小仓位参与，注意止盈"
    elif position_2025 > 40:
        stage = "中位"
        risk = "中等"
        suggestion = "可逐步建仓"
    elif position_2025 > 20:
        stage = "中低位"
        risk = "较低"
        suggestion = "较好的建仓时机"
    else:
        stage = "低位"
        risk = "低"
        suggestion = "积极建仓"
    
    # 趋势判断
    if today['close'] > today['ma20'] > today['ma60']:
        trend = "上升趋势"
    elif today['close'] < today['ma20'] < today['ma60']:
        trend = "下降趋势"
    else:
        trend = "震荡整理"
    
    print(f"""
  当前阶段: {stage}
  趋势判断: {trend}
  风险等级: {risk}
  操作建议: {suggestion}
  
  当前位置: {position_2025:.0f}% (相对2025年高低点)
""")
    
    # 与2025年5-7月对比
    print("=" * 70)
    print("【与2025年5-7月对比】")
    print("=" * 70)
    
    # 2025年5月数据
    may_2025 = df[df.index.strftime('%Y-%m') == '2025-05']
    if len(may_2025) > 0:
        may_position = (may_2025['close'].iloc[-1] - low_2025) / (high_2025 - low_2025) * 100
        print(f"\n  2025年5月位置: {may_position:.0f}%")
        print(f"  当前位置:      {position_2025:.0f}%")
        print(f"  差距:          {position_2025 - may_position:.0f}个百分点")
    
    if position_2025 > 70:
        comparison = """
  【结论】
  当前位置明显高于2025年5-7月（当时约27-51%）
  
  这意味着：
  1. 现在不是最佳买入时机
  2. 需要等待大盘回调到更低位置
  3. 或者等待新的年度低点形成后再布局
  
  建议：
  - 观望为主，不急于建仓
  - 等待大盘回调到60%以下位置
  - 或者等待2026年的调整低点
"""
    elif position_2025 > 40:
        comparison = """
  【结论】
  当前位置处于中位，与2025年6-7月类似
  
  这意味着：
  1. 可以开始关注潜力信号
  2. 但不是最佳买入点
  3. 可以小仓位试探
  
  建议：
  - 开始筛选潜力板块
  - 等待回调后分批建仓
  - 控制仓位在30%以内
"""
    else:
        comparison = """
  【结论】
  当前位置较低，类似2025年5月
  
  这意味着：
  1. 可能是较好的布局时机
  2. 可以开始建仓潜力板块
  
  建议：
  - 积极筛选潜力信号
  - 分批建仓
  - 持有等待下半年行情
"""
    print(comparison)

if __name__ == "__main__":
    analyze_current()
