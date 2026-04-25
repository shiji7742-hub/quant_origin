"""测试单个板块"""
from backtest_sector_surge import backtest_sector, get_market_data, get_sector_history_long, detect_surge_pattern_v2
import pandas as pd

def test_single_sector(sector_name):
    print(f"测试板块: {sector_name}")
    print("=" * 50)
    
    # 获取大盘数据
    market_data = get_market_data('20240901', '20260115')
    
    # 回测
    signals = backtest_sector(sector_name, '20240901', '20251215', market_data)
    
    if signals:
        print(f"\n发现 {len(signals)} 个信号：")
        for s in signals:
            print(f"\n  信号日期: {s['signal_date']}")
            print(f"  爆发日期: {s['surge_date']} | 爆发涨幅: +{s['surge_value']}%")
            print(f"  回撤: {s['drawdown']}%")
            print(f"  未来收益: 30d={s['future_30d']}%, 60d={s['future_60d']}%, 90d={s['future_90d']}%")
    else:
        print("\n未检测到符合条件的信号")
        
        # 看看原始数据
        print("\n查看原始数据...")
        data = get_sector_history_long(sector_name, '20240901', '20251215')
        if data is not None:
            print(f"数据长度: {len(data)}天")
            
            # 找爆发日
            surge_days = data[data > 3.0]
            if len(surge_days) > 0:
                print(f"\n爆发日（涨幅>3%）：")
                for date, val in surge_days.items():
                    print(f"  {date.strftime('%Y-%m-%d')}: +{val:.2f}%")
            else:
                print("没有找到爆发日（涨幅>3%）")

if __name__ == "__main__":
    # 详细分析商业航天 2025年11月-2026年1月 期间
    from backtest_sector_surge import get_sector_history_long, get_market_data
    import pandas as pd
    
    print("商业航天 2025年11月-2026年1月 详细分析")
    print("=" * 60)
    
    # 获取最新数据
    data = get_sector_history_long("商业航天", '20250901', '20260115')
    
    if data is not None:
        # 筛选9月到1月的数据
        data_period = data[(data.index >= '2025-09-01') & (data.index <= '2026-01-31')]
        
        print(f"\n【每日涨跌幅】")
        print(data_period.to_string())
        
        print(f"\n【爆发日（涨幅>3%）】")
        surge_days = data_period[data_period > 3.0]
        if len(surge_days) > 0:
            for date, val in surge_days.items():
                print(f"  {date.strftime('%Y-%m-%d')}: +{val:.2f}%")
        else:
            print("  无")
        
        print(f"\n【大跌日（跌幅>3%）】")
        drop_days = data_period[data_period < -3.0]
        if len(drop_days) > 0:
            for date, val in drop_days.items():
                print(f"  {date.strftime('%Y-%m-%d')}: {val:.2f}%")
        else:
            print("  无")
        
        # 计算累计涨幅
        print(f"\n【阶段累计涨幅】")
        sep_data = data[(data.index >= '2025-09-01') & (data.index < '2025-10-01')]
        oct_data = data[(data.index >= '2025-10-01') & (data.index < '2025-11-01')]
        nov_data = data[(data.index >= '2025-11-01') & (data.index < '2025-12-01')]
        dec_data = data[(data.index >= '2025-12-01') & (data.index < '2026-01-01')]
        jan_data = data[(data.index >= '2026-01-01') & (data.index < '2026-02-01')]
        
        if len(sep_data) > 0:
            print(f"  2025年9月: {sep_data.sum():.2f}%")
        if len(oct_data) > 0:
            print(f"  2025年10月: {oct_data.sum():.2f}%")
        if len(nov_data) > 0:
            print(f"  2025年11月: {nov_data.sum():.2f}%")
        if len(dec_data) > 0:
            print(f"  2025年12月: {dec_data.sum():.2f}%")
        if len(jan_data) > 0:
            print(f"  2026年1月: {jan_data.sum():.2f}%")
        
        print(f"\n【结论】")
        if len(surge_days) > 0:
            print("商业航天在这个期间有试探性爆发，符合启动前的特征。")
        else:
            print("商业航天在这个期间没有明显的爆发迹象。")
