"""
年报扭亏策略 - 模拟回测结果
展示如果策略有效，回测结果应该是什么样的
"""
import pandas as pd
import numpy as np
from datetime import datetime

def generate_demo_backtest():
    """生成模拟回测数据"""
    
    print("=" * 80)
    print("年报扭亏策略 - 模拟回测结果")
    print("=" * 80)
    print("\n注意: 这是基于策略逻辑的模拟数据")
    print("实际效果需要用真实历史数据验证\n")
    
    # 模拟20只扭亏股票的回测数据
    np.random.seed(42)
    
    stocks = []
    for i in range(20):
        code = f"{600000 + i:06d}"
        name = f"股票{i+1}"
        
        # 模拟信号评分（有信号的股票表现更好）
        has_strong_signal = i < 8  # 40%有强信号
        has_medium_signal = 8 <= i < 14  # 30%有中等信号
        
        if has_strong_signal:
            signal_score = np.random.randint(70, 101)
            # 强信号的收益更好
            ret_1d = np.random.normal(3.5, 2.0)
            ret_5d = np.random.normal(6.0, 3.0)
            ret_10d = np.random.normal(8.0, 4.0)
        elif has_medium_signal:
            signal_score = np.random.randint(40, 70)
            # 中等信号收益一般
            ret_1d = np.random.normal(1.5, 2.5)
            ret_5d = np.random.normal(3.0, 3.5)
            ret_10d = np.random.normal(4.0, 4.5)
        else:
            signal_score = np.random.randint(0, 40)
            # 无信号收益较差
            ret_1d = np.random.normal(0.0, 3.0)
            ret_5d = np.random.normal(0.5, 4.0)
            ret_10d = np.random.normal(1.0, 5.0)
        
        stocks.append({
            '股票代码': code,
            '股票名称': name,
            '披露日期': f'2025-{np.random.randint(1,5):02d}-{np.random.randint(1,29):02d}',
            '年报扭亏': '✓',
            '2024利润(万)': np.random.randint(1000, 50000),
            '2023利润(万)': -np.random.randint(5000, 100000),
            '年报前信号': '✓' if signal_score >= 40 else '✗',
            '信号评分': signal_score,
            '波动率%': np.random.uniform(2, 10),
            '振幅%': np.random.uniform(2, 8),
            '换手率%': np.random.uniform(1, 6),
            '横盘': '✓' if signal_score >= 40 else '✗',
            '低振幅': '✓' if signal_score >= 70 else '✗',
            '低换手': '✓' if signal_score >= 70 else '✗',
            '买入价': round(np.random.uniform(5, 50), 2),
            '1日收益%': round(ret_1d, 2),
            '5日收益%': round(ret_5d, 2),
            '10日收益%': round(ret_10d, 2),
        })
    
    df = pd.DataFrame(stocks)
    
    # 显示结果
    print("=" * 80)
    print("回测样本")
    print("=" * 80)
    print(f"\n总样本数: {len(df)}")
    print(df[['股票代码', '股票名称', '信号评分', '1日收益%', '5日收益%', '10日收益%']].to_string(index=False))
    
    # 整体统计
    print("\n" + "=" * 80)
    print("整体统计")
    print("=" * 80)
    
    for days in [1, 5, 10]:
        col = f'{days}日收益%'
        avg_return = df[col].mean()
        win_rate = (df[col] > 0).sum() / len(df) * 100
        max_return = df[col].max()
        min_return = df[col].min()
        
        print(f"\n{days}日持有:")
        print(f"  平均收益: {avg_return:.2f}%")
        print(f"  胜率: {win_rate:.1f}%")
        print(f"  最大收益: {max_return:.2f}%")
        print(f"  最大亏损: {min_return:.2f}%")
    
    # 信号有效性分析
    print("\n" + "=" * 80)
    print("信号有效性分析")
    print("=" * 80)
    
    df_with_signal = df[df['年报前信号'] == '✓']
    df_without_signal = df[df['年报前信号'] == '✗']
    
    print(f"\n有信号样本: {len(df_with_signal)} 只 ({len(df_with_signal)/len(df)*100:.1f}%)")
    print(f"无信号样本: {len(df_without_signal)} 只 ({len(df_without_signal)/len(df)*100:.1f}%)")
    
    for days in [1, 5, 10]:
        col = f'{days}日收益%'
        
        avg_with = df_with_signal[col].mean()
        avg_without = df_without_signal[col].mean()
        
        win_with = (df_with_signal[col] > 0).sum() / len(df_with_signal) * 100
        win_without = (df_without_signal[col] > 0).sum() / len(df_without_signal) * 100
        
        print(f"\n{days}日持有:")
        print(f"  有信号平均收益: {avg_with:.2f}%")
        print(f"  无信号平均收益: {avg_without:.2f}%")
        print(f"  信号优势: {avg_with - avg_without:+.2f}%")
        print(f"  有信号胜率: {win_with:.1f}%")
        print(f"  无信号胜率: {win_without:.1f}%")
    
    # 按信号强度分组
    print("\n" + "=" * 80)
    print("按信号强度分组")
    print("=" * 80)
    
    df_strong = df[df['信号评分'] >= 70]
    df_medium = df[(df['信号评分'] >= 40) & (df['信号评分'] < 70)]
    df_weak = df[df['信号评分'] < 40]
    
    print(f"\n强信号 (≥70分): {len(df_strong)} 只")
    print(f"中等信号 (40-69分): {len(df_medium)} 只")
    print(f"弱信号 (<40分): {len(df_weak)} 只")
    
    print("\n5日收益对比:")
    if len(df_strong) > 0:
        print(f"  强信号: {df_strong['5日收益%'].mean():.2f}% (胜率{(df_strong['5日收益%']>0).sum()/len(df_strong)*100:.1f}%)")
    if len(df_medium) > 0:
        print(f"  中等信号: {df_medium['5日收益%'].mean():.2f}% (胜率{(df_medium['5日收益%']>0).sum()/len(df_medium)*100:.1f}%)")
    if len(df_weak) > 0:
        print(f"  弱信号: {df_weak['5日收益%'].mean():.2f}% (胜率{(df_weak['5日收益%']>0).sum()/len(df_weak)*100:.1f}%)")
    
    # 策略评估
    print("\n" + "=" * 80)
    print("策略评估")
    print("=" * 80)
    
    # 计算夏普比率（简化版）
    returns_5d = df_with_signal['5日收益%'].values
    sharpe = returns_5d.mean() / returns_5d.std() if returns_5d.std() > 0 else 0
    
    print(f"\n基于有信号样本的5日持有:")
    print(f"  平均收益: {returns_5d.mean():.2f}%")
    print(f"  收益标准差: {returns_5d.std():.2f}%")
    print(f"  夏普比率: {sharpe:.2f}")
    print(f"  胜率: {(returns_5d > 0).sum() / len(returns_5d) * 100:.1f}%")
    
    # 策略结论
    print("\n" + "=" * 80)
    print("策略结论（基于模拟数据）")
    print("=" * 80)
    
    avg_return_with_signal = df_with_signal['5日收益%'].mean()
    win_rate_with_signal = (df_with_signal['5日收益%'] > 0).sum() / len(df_with_signal) * 100
    signal_advantage = avg_return_with_signal - df_without_signal['5日收益%'].mean()
    
    print(f"\n如果策略有效，应该看到:")
    print(f"  ✓ 有信号的平均收益 > 3%: {avg_return_with_signal:.2f}%")
    print(f"  ✓ 有信号的胜率 > 60%: {win_rate_with_signal:.1f}%")
    print(f"  ✓ 信号优势 > 2%: {signal_advantage:+.2f}%")
    print(f"  ✓ 强信号收益 > 中等信号 > 弱信号")
    
    if avg_return_with_signal > 3 and win_rate_with_signal > 60 and signal_advantage > 2:
        print("\n评估: ⭐⭐⭐ 策略有效")
        print("建议: 可以实盘应用，重点关注强信号股票")
    elif avg_return_with_signal > 1.5 and win_rate_with_signal > 50:
        print("\n评估: ⭐⭐ 策略有一定效果")
        print("建议: 可以小仓位试探，继续优化参数")
    else:
        print("\n评估: ⭐ 策略效果不明显")
        print("建议: 需要调整信号权重或增加筛选条件")
    
    # 保存结果
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'年报扭亏回测_模拟_{timestamp}.xlsx'
    df.to_excel(filename, index=False, engine='openpyxl')
    
    print("\n" + "=" * 80)
    print(f"回测结果已保存到: {filename}")
    print("=" * 80)
    
    print("\n重要提示:")
    print("  这是基于策略逻辑的模拟数据，假设:")
    print("  1. 强信号股票平均收益更高")
    print("  2. 信号评分与收益正相关")
    print("  3. 有信号比无信号表现更好")
    print("\n  实际效果需要用真实历史数据验证！")
    print("  建议:")
    print("  1. 收集10-20只真实的扭亏案例")
    print("  2. 使用 interactive_backtest.py 进行真实回测")
    print("  3. 对比实际结果与模拟结果")
    
    return df


if __name__ == '__main__':
    print("\n年报扭亏策略 - 模拟回测")
    print("=" * 80)
    print("这是基于策略逻辑的模拟回测")
    print("展示如果策略有效，结果应该是什么样的")
    print("=" * 80)
    
    choice = input("\n是否继续? (y/n): ").strip().lower()
    
    if choice == 'y':
        df = generate_demo_backtest()
        
        print("\n\n模拟回测完成！")
        print("\n下一步:")
        print("  1. 收集真实的扭亏股票案例")
        print("  2. 使用 interactive_backtest.py 进行真实回测")
        print("  3. 对比实际结果验证策略有效性")
    else:
        print("已取消")
