"""
分析妖股震荡低吸策略的月度表现与市场环境的关系
"""
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime

def get_market_data():
    """获取上证指数数据"""
    print("获取上证指数数据...")
    df = ak.stock_zh_index_daily(symbol="sh000001")
    df['date'] = pd.to_datetime(df['date'])
    df = df[(df['date'] >= '2024-01-01') & (df['date'] <= '2025-12-31')]
    df = df.sort_values('date')
    return df

def analyze_monthly_market(market_df):
    """分析每月市场表现"""
    market_df['month'] = market_df['date'].dt.to_period('M')
    
    monthly_stats = []
    for month, group in market_df.groupby('month'):
        month_return = (group['close'].iloc[-1] / group['close'].iloc[0] - 1) * 100
        month_high = group['high'].max()
        month_low = group['low'].min()
        volatility = (month_high / month_low - 1) * 100
        avg_volume = group['volume'].mean()
        
        # 计算月内涨跌天数
        group = group.copy()
        group['daily_return'] = group['close'].pct_change()
        up_days = (group['daily_return'] > 0).sum()
        down_days = (group['daily_return'] < 0).sum()
        
        monthly_stats.append({
            'month': str(month),
            'open': group['close'].iloc[0],
            'close': group['close'].iloc[-1],
            'market_return': round(month_return, 2),
            'volatility': round(volatility, 2),
            'up_days': up_days,
            'down_days': down_days,
            'sentiment': '牛市' if month_return > 5 else ('熊市' if month_return < -5 else '震荡')
        })
    
    return pd.DataFrame(monthly_stats)

def main():
    # 策略回测结果（从回测输出复制）
    strategy_results = {
        '2024-05': -10.07,
        '2024-06': -4.18,
        '2024-07': 5.06,
        '2024-08': 5.02,
        '2024-09': 25.25,
        '2024-10': -1.29,
        '2024-11': 5.92,
        '2024-12': -8.74,
        '2025-01': 11.26,
        '2025-02': 4.85,
        '2025-03': -10.65,
        '2025-04': 14.50,
        '2025-05': 2.01,
        '2025-06': 4.07,
        '2025-07': 4.14,
        '2025-08': 1.79,
        '2025-09': 2.23,
        '2025-10': 2.84,
        '2025-11': 0.28,
        '2025-12': 0.09,
    }
    
    # 获取市场数据
    market_df = get_market_data()
    monthly_market = analyze_monthly_market(market_df)
    
    # 合并策略收益
    monthly_market['strategy_return'] = monthly_market['month'].map(strategy_results)
    
    print("\n" + "="*80)
    print("【妖股震荡低吸策略 vs 市场环境分析】")
    print("="*80)
    
    print("\n【月度对比表】")
    print("-"*80)
    print(f"{'月份':<10} {'大盘涨跌%':>10} {'策略收益%':>10} {'市场情绪':>10} {'波动率%':>10} {'涨/跌天数':>12}")
    print("-"*80)
    
    for _, row in monthly_market.iterrows():
        if pd.notna(row['strategy_return']):
            print(f"{row['month']:<10} {row['market_return']:>10.2f} {row['strategy_return']:>10.2f} {row['sentiment']:>10} {row['volatility']:>10.2f} {row['up_days']:>5}/{row['down_days']:<5}")
    
    # 分析相关性
    valid_data = monthly_market.dropna(subset=['strategy_return'])
    correlation = valid_data['market_return'].corr(valid_data['strategy_return'])
    
    print("\n" + "="*80)
    print("【关键发现】")
    print("="*80)
    print(f"\n1. 策略收益与大盘涨跌相关系数: {correlation:.3f}")
    
    # 分组分析
    bull_months = valid_data[valid_data['market_return'] > 5]
    bear_months = valid_data[valid_data['market_return'] < -5]
    range_months = valid_data[(valid_data['market_return'] >= -5) & (valid_data['market_return'] <= 5)]
    
    print(f"\n2. 不同市场环境下的策略表现:")
    print(f"   - 牛市月份(大盘>5%): {len(bull_months)}个月, 策略平均收益: {bull_months['strategy_return'].mean():.2f}%")
    print(f"   - 熊市月份(大盘<-5%): {len(bear_months)}个月, 策略平均收益: {bear_months['strategy_return'].mean():.2f}%")
    print(f"   - 震荡月份(-5%~5%): {len(range_months)}个月, 策略平均收益: {range_months['strategy_return'].mean():.2f}%")
    
    # 分析差的月份
    print("\n3. 策略表现最差的月份分析:")
    worst_months = valid_data.nsmallest(3, 'strategy_return')
    for _, row in worst_months.iterrows():
        print(f"   - {row['month']}: 策略{row['strategy_return']:.2f}%, 大盘{row['market_return']:.2f}%, {row['sentiment']}")
    
    # 分析好的月份
    print("\n4. 策略表现最好的月份分析:")
    best_months = valid_data.nlargest(3, 'strategy_return')
    for _, row in best_months.iterrows():
        print(f"   - {row['month']}: 策略{row['strategy_return']:.2f}%, 大盘{row['market_return']:.2f}%, {row['sentiment']}")
    
    # 结论
    print("\n" + "="*80)
    print("【结论】")
    print("="*80)
    
    if correlation > 0.5:
        print("策略收益与大盘高度正相关，说明这是一个顺势策略，大盘涨策略才赚钱。")
    elif correlation > 0.2:
        print("策略收益与大盘中度正相关，大盘走势对策略有一定影响。")
    elif correlation > -0.2:
        print("策略收益与大盘相关性较弱，策略有一定的独立性。")
    else:
        print("策略收益与大盘负相关，可能是逆势策略。")
    
    # 具体月份解读
    print("\n【具体月份解读】")
    print("-"*80)
    
    # 2024年5月
    may_2024 = valid_data[valid_data['month'] == '2024-05'].iloc[0]
    print(f"2024年5月 (策略-10.07%):")
    print(f"  大盘涨跌: {may_2024['market_return']:.2f}%, 波动率: {may_2024['volatility']:.2f}%")
    print(f"  解读: 可能是市场整体弱势，妖股回调后继续下跌而非反弹")
    
    # 2024年12月
    dec_2024 = valid_data[valid_data['month'] == '2024-12'].iloc[0]
    print(f"\n2024年12月 (策略-8.74%):")
    print(f"  大盘涨跌: {dec_2024['market_return']:.2f}%, 波动率: {dec_2024['volatility']:.2f}%")
    print(f"  解读: 年底资金面紧张，机构调仓，妖股容易被抛售")
    
    # 2025年3月
    mar_2025 = valid_data[valid_data['month'] == '2025-03'].iloc[0]
    print(f"\n2025年3月 (策略-10.65%):")
    print(f"  大盘涨跌: {mar_2025['market_return']:.2f}%, 波动率: {mar_2025['volatility']:.2f}%")
    print(f"  解读: 两会后政策预期落地，资金获利了结")
    
    # 2024年9月
    sep_2024 = valid_data[valid_data['month'] == '2024-09'].iloc[0]
    print(f"\n2024年9月 (策略+25.25%):")
    print(f"  大盘涨跌: {sep_2024['market_return']:.2f}%, 波动率: {sep_2024['volatility']:.2f}%")
    print(f"  解读: 924行情启动，市场情绪极度亢奋，妖股反弹力度大")

if __name__ == "__main__":
    main()
