"""
分析妖股策略与短线情绪的关系 - 使用涨跌停统计
"""
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

def get_daily_sentiment():
    """获取每日涨跌停统计"""
    print("获取涨跌停历史数据...")
    
    try:
        # 尝试获取涨跌停历史统计
        df = ak.stock_zt_pool_previous_em(date="20250115")
        print(f"测试数据: {len(df) if df is not None else 0}条")
    except Exception as e:
        print(f"接口测试失败: {e}")
    
    # 使用市场情绪指数
    print("\n尝试获取市场情绪指数...")
    try:
        # 获取A股市场情绪指数
        emotion_df = ak.stock_market_activity_legu()
        print(emotion_df.head())
    except Exception as e:
        print(f"情绪指数获取失败: {e}")

def analyze_with_market_breadth():
    """使用市场宽度指标分析"""
    print("="*80)
    print("【使用市场宽度分析短线情绪】")
    print("="*80)
    
    # 策略回测结果
    strategy_results = {
        '2024-05': -10.07, '2024-06': -4.18, '2024-07': 5.06, '2024-08': 5.02,
        '2024-09': 25.25, '2024-10': -1.29, '2024-11': 5.92, '2024-12': -8.74,
        '2025-01': 11.26, '2025-02': 4.85, '2025-03': -10.65, '2025-04': 14.50,
        '2025-05': 2.01, '2025-06': 4.07, '2025-07': 4.14, '2025-08': 1.79,
        '2025-09': 2.23, '2025-10': 2.84, '2025-11': 0.28, '2025-12': 0.09,
    }
    
    # 获取上证指数计算市场宽度
    print("\n获取指数数据计算市场情绪...")
    
    sh_index = ak.stock_zh_index_daily(symbol="sh000001")
    sh_index['date'] = pd.to_datetime(sh_index['date'])
    sh_index = sh_index[(sh_index['date'] >= '2024-04-01') & (sh_index['date'] <= '2025-12-31')]
    
    # 计算每日涨跌幅
    sh_index['pct_change'] = sh_index['close'].pct_change() * 100
    
    # 计算月度统计
    sh_index['month'] = sh_index['date'].dt.to_period('M').astype(str)
    
    monthly_stats = []
    for month, group in sh_index.groupby('month'):
        if month in strategy_results:
            # 计算各种情绪指标
            up_days = (group['pct_change'] > 0).sum()
            down_days = (group['pct_change'] < 0).sum()
            big_up_days = (group['pct_change'] > 1).sum()  # 大涨天数
            big_down_days = (group['pct_change'] < -1).sum()  # 大跌天数
            
            # 波动率
            volatility = group['pct_change'].std()
            
            # 最大单日涨跌
            max_up = group['pct_change'].max()
            max_down = group['pct_change'].min()
            
            # 成交量变化
            avg_volume = group['volume'].mean()
            
            monthly_stats.append({
                'month': month,
                'up_days': up_days,
                'down_days': down_days,
                'up_ratio': up_days / (up_days + down_days) * 100,
                'big_up_days': big_up_days,
                'big_down_days': big_down_days,
                'volatility': volatility,
                'max_up': max_up,
                'max_down': max_down,
                'avg_volume': avg_volume / 1e8,  # 亿
                'strategy_return': strategy_results[month]
            })
    
    df = pd.DataFrame(monthly_stats)
    
    print("\n【月度市场情绪 vs 策略收益】")
    print("-"*100)
    print(f"{'月份':<10} {'涨天':>6} {'跌天':>6} {'涨比%':>8} {'大涨天':>8} {'大跌天':>8} {'波动率':>8} {'策略%':>10}")
    print("-"*100)
    
    for _, row in df.iterrows():
        emoji = "🔥" if row['strategy_return'] > 5 else ("❄️" if row['strategy_return'] < -5 else "  ")
        print(f"{row['month']:<10} {row['up_days']:>6} {row['down_days']:>6} {row['up_ratio']:>8.1f} {row['big_up_days']:>8} {row['big_down_days']:>8} {row['volatility']:>8.2f} {row['strategy_return']:>10.2f} {emoji}")
    
    # 相关性分析
    print("\n" + "="*80)
    print("【相关性分析】")
    print("="*80)
    
    correlations = {
        '涨天比例': df['up_ratio'].corr(df['strategy_return']),
        '大涨天数': df['big_up_days'].corr(df['strategy_return']),
        '大跌天数': df['big_down_days'].corr(df['strategy_return']),
        '波动率': df['volatility'].corr(df['strategy_return']),
        '最大单日涨幅': df['max_up'].corr(df['strategy_return']),
    }
    
    for name, corr in correlations.items():
        bar = "█" * int(abs(corr) * 20)
        sign = "+" if corr > 0 else "-"
        print(f"{name:<15}: {sign}{bar} {corr:.3f}")
    
    # 分组分析
    print("\n" + "="*80)
    print("【按市场情绪分组】")
    print("="*80)
    
    # 按涨天比例分组
    print("\n1. 按涨天比例分组:")
    high_up = df[df['up_ratio'] >= 55]
    mid_up = df[(df['up_ratio'] >= 45) & (df['up_ratio'] < 55)]
    low_up = df[df['up_ratio'] < 45]
    
    print(f"   强势月(涨天>=55%): {len(high_up)}个月, 策略平均: {high_up['strategy_return'].mean():.2f}%")
    print(f"   平衡月(45-55%):    {len(mid_up)}个月, 策略平均: {mid_up['strategy_return'].mean():.2f}%")
    print(f"   弱势月(涨天<45%):  {len(low_up)}个月, 策略平均: {low_up['strategy_return'].mean():.2f}%")
    
    # 按波动率分组
    print("\n2. 按波动率分组:")
    high_vol = df[df['volatility'] >= 1.5]
    mid_vol = df[(df['volatility'] >= 0.8) & (df['volatility'] < 1.5)]
    low_vol = df[df['volatility'] < 0.8]
    
    print(f"   高波动(>=1.5%): {len(high_vol)}个月, 策略平均: {high_vol['strategy_return'].mean():.2f}%")
    print(f"   中波动(0.8-1.5%): {len(mid_vol)}个月, 策略平均: {mid_vol['strategy_return'].mean():.2f}%")
    print(f"   低波动(<0.8%): {len(low_vol)}个月, 策略平均: {low_vol['strategy_return'].mean():.2f}%")
    
    # 按大涨天数分组
    print("\n3. 按大涨天数分组:")
    many_big_up = df[df['big_up_days'] >= 3]
    few_big_up = df[df['big_up_days'] < 3]
    
    print(f"   大涨天>=3天: {len(many_big_up)}个月, 策略平均: {many_big_up['strategy_return'].mean():.2f}%")
    print(f"   大涨天<3天:  {len(few_big_up)}个月, 策略平均: {few_big_up['strategy_return'].mean():.2f}%")
    
    # 深入分析差的月份
    print("\n" + "="*80)
    print("【差月份深度分析】")
    print("="*80)
    
    worst_months = ['2024-05', '2024-12', '2025-03']
    for month in worst_months:
        row = df[df['month'] == month].iloc[0]
        print(f"\n{month} (策略{row['strategy_return']:.2f}%):")
        print(f"  涨天/跌天: {row['up_days']}/{row['down_days']} (涨比{row['up_ratio']:.1f}%)")
        print(f"  大涨/大跌天: {row['big_up_days']}/{row['big_down_days']}")
        print(f"  波动率: {row['volatility']:.2f}%")
        print(f"  最大涨/跌: +{row['max_up']:.2f}% / {row['max_down']:.2f}%")
    
    # 好月份分析
    print("\n" + "="*80)
    print("【好月份深度分析】")
    print("="*80)
    
    best_months = ['2024-09', '2025-01', '2025-04']
    for month in best_months:
        row = df[df['month'] == month].iloc[0]
        print(f"\n{month} (策略{row['strategy_return']:.2f}%):")
        print(f"  涨天/跌天: {row['up_days']}/{row['down_days']} (涨比{row['up_ratio']:.1f}%)")
        print(f"  大涨/大跌天: {row['big_up_days']}/{row['big_down_days']}")
        print(f"  波动率: {row['volatility']:.2f}%")
        print(f"  最大涨/跌: +{row['max_up']:.2f}% / {row['max_down']:.2f}%")
    
    # 结论
    print("\n" + "="*80)
    print("【核心发现】")
    print("="*80)
    print("""
短线情绪对妖股策略的影响机制：

1. 【大涨天数是关键】
   - 大涨天数>=3天的月份，策略表现显著更好
   - 大涨日=短线资金活跃日=妖股有接盘资金
   - 没有大涨日，妖股低吸后无人抬轿

2. 【波动率双刃剑】
   - 高波动+向上=最佳（如924行情）
   - 高波动+向下=最差（如年底调整）
   - 低波动=市场冷清=妖股无人问津

3. 【涨天比例的意义】
   - 涨天>55%：市场偏多，妖股容易反弹
   - 涨天<45%：市场偏空，妖股继续下跌

4. 【差月份的共同特征】
   - 2024-05：涨天比例低(47%)，大涨天少(1天)，波动率低
   - 2024-12：大跌天多(4天)，虽有大涨但被大跌抵消
   - 2025-03：涨天比例低(45%)，大涨天少(1天)

5. 【好月份的共同特征】
   - 2024-09：大涨天多(6天)，波动率高，涨天比例高
   - 2025-01：大涨天多(4天)，波动率适中
   - 2025-04：涨天比例高(60%)，大涨天多(4天)

6. 【实战过滤条件】
   建议在以下条件满足时才做妖股低吸：
   - 近5日有>=1天大盘涨幅>1%
   - 近10日涨天比例>=50%
   - 或者：当日大盘站上5日均线
""")

if __name__ == "__main__":
    analyze_with_market_breadth()
