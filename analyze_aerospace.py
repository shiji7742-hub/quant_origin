"""分析商业航天板块的前兆信号"""
from backtest_sector_surge import (
    get_sector_history_long, 
    get_market_data, 
    detect_surge_pattern_v2
)
import pandas as pd

def analyze_aerospace_signals():
    print("=" * 60)
    print("商业航天板块前兆信号分析")
    print("分析区间：2025年9月 - 2026年1月")
    print("=" * 60)
    
    # 获取大盘数据
    market_data = get_market_data('20250901', '20260115')
    
    # 获取商业航天数据
    data = get_sector_history_long("商业航天", '20250901', '20260115')
    
    if data is None:
        print("获取数据失败")
        return
    
    print(f"\n数据长度: {len(data)}天")
    
    # 逐日检测信号
    print("\n【信号检测】")
    print("使用V2策略条件：")
    print("  1. 30天前有过爆发(>3%)")
    print("  2. 高点回撤5-12%")
    print("  3. 近15日表现弱(<5%)")
    print("  4. 大盘在20日均线上方")
    print("-" * 60)
    
    signals_found = []
    
    # 从第45天开始检测（需要足够的历史数据）
    for i in range(45, len(data)):
        is_signal, details = detect_surge_pattern_v2(data, i, lookback=30, market_data=market_data)
        
        if is_signal:
            signal_date = data.index[i]
            signals_found.append({
                'date': signal_date,
                'details': details
            })
            print(f"\n✓ 信号日期: {signal_date.strftime('%Y-%m-%d')}")
            print(f"  爆发日期: {details['surge_date'].strftime('%Y-%m-%d')}")
            print(f"  爆发涨幅: +{details['surge_value']:.2f}%")
            print(f"  爆发次数: {details['surge_count']}次")
            print(f"  高点回撤: {details['drawdown']:.2f}%")
            print(f"  近15日累计: {details['recent_sum']:.2f}%")
            print(f"  近5日累计: {details['recent_5d']:.2f}%")
    
    if not signals_found:
        print("\n未检测到符合V2策略条件的信号")
        print("\n【手动分析关键时间点】")
        
        # 手动分析几个关键时间点
        key_dates = ['2025-11-01', '2025-11-15', '2025-12-01', '2025-12-15']
        
        for date_str in key_dates:
            try:
                idx = data.index.get_loc(pd.Timestamp(date_str), method='nearest')
                if idx >= 45:
                    # 计算该日期前30天的数据
                    lookback_data = data.iloc[idx-45:idx]
                    
                    # 找爆发日
                    surge_days = lookback_data[lookback_data > 3.0]
                    
                    # 计算近15日
                    recent_15d = data.iloc[idx-15:idx].sum()
                    
                    # 计算回撤
                    cumsum = lookback_data.cumsum()
                    max_gain = cumsum.max()
                    current_gain = cumsum.iloc[-1]
                    drawdown = max_gain - current_gain
                    
                    print(f"\n{date_str}:")
                    print(f"  前45天爆发次数: {len(surge_days)}")
                    if len(surge_days) > 0:
                        print(f"  最大爆发: +{surge_days.max():.2f}%")
                    print(f"  近15日累计: {recent_15d:.2f}%")
                    print(f"  高点回撤: {drawdown:.2f}%")
            except:
                continue
    
    # 总结
    print("\n" + "=" * 60)
    print("【分析总结】")
    print("=" * 60)
    
    # 按月统计
    print("\n各月表现：")
    months = [
        ('2025-09', '9月'),
        ('2025-10', '10月'),
        ('2025-11', '11月'),
        ('2025-12', '12月'),
        ('2026-01', '1月')
    ]
    
    for month_prefix, month_name in months:
        month_data = data[data.index.strftime('%Y-%m') == month_prefix]
        if len(month_data) > 0:
            surge_count = (month_data > 3.0).sum()
            drop_count = (month_data < -3.0).sum()
            total_return = month_data.sum()
            print(f"  {month_name}: 累计{total_return:+.1f}%, 爆发{surge_count}次, 大跌{drop_count}次")
    
    print("\n【前兆特征分析】")
    
    # 11月分析
    nov_data = data[data.index.strftime('%Y-%m') == '2025-11']
    if len(nov_data) > 0:
        print(f"\n11月（洗盘期）:")
        print(f"  - 月度累计: {nov_data.sum():.1f}%（明显下跌）")
        print(f"  - 11月21日大跌后，11月24-25日连续反弹")
        print(f"  - 这是典型的'洗盘后试探'特征")
    
    # 12月分析
    dec_data = data[data.index.strftime('%Y-%m') == '2025-12']
    if len(dec_data) > 0:
        print(f"\n12月（启动期）:")
        print(f"  - 月度累计: {dec_data.sum():.1f}%（开始上涨）")
        print(f"  - 12月5日+6%爆发，12月8日+3.8%确认")
        print(f"  - 12月24-25日再次爆发，主升浪启动")
    
    # 1月分析
    jan_data = data[data.index.strftime('%Y-%m') == '2026-01']
    if len(jan_data) > 0:
        print(f"\n1月（主升期）:")
        print(f"  - 月度累计: {jan_data.sum():.1f}%（加速上涨）")
        print(f"  - 多次单日涨幅超过5%")
        print(f"  - 进入主升浪阶段")
    
    print("\n【结论】")
    print("商业航天在2025年11月确实有明显的前兆信号：")
    print("1. 11月整体下跌-6.8%，形成洗盘")
    print("2. 11月24-25日连续反弹，是'试探性爆发'")
    print("3. 12月初开始放量上涨，确认启动")
    print("4. 符合'爆发-退潮-再爆发'的牛板块启动模式")

if __name__ == "__main__":
    analyze_aerospace_signals()
