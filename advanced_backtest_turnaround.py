"""
年报扭亏策略 - 进阶回测分析
包含多种市场环境和详细的策略分析
"""
import pandas as pd
import numpy as np
from datetime import datetime
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
import matplotlib.pyplot as plt

def generate_advanced_backtest():
    """生成进阶回测数据"""
    
    print("=" * 80)
    print("年报扭亏策略 - 进阶回测分析")
    print("=" * 80)
    print("\n模拟50只扭亏股票在不同市场环境下的表现\n")
    
    np.random.seed(42)
    
    stocks = []
    
    # 模拟50只股票，分为不同类型
    for i in range(50):
        code = f"{600000 + i:06d}"
        name = f"股票{i+1}"
        
        # 市场环境（牛市/震荡/熊市）
        if i < 20:
            market = "牛市"
            market_factor = 1.5  # 牛市收益放大
        elif i < 35:
            market = "震荡"
            market_factor = 1.0  # 震荡市正常
        else:
            market = "熊市"
            market_factor = 0.5  # 熊市收益缩水
        
        # 信号强度
        if i % 3 == 0:  # 33%强信号
            signal_type = "强信号"
            signal_score = np.random.randint(70, 101)
            base_return = 6.0
        elif i % 3 == 1:  # 33%中等信号
            signal_type = "中等信号"
            signal_score = np.random.randint(40, 70)
            base_return = 3.0
        else:  # 33%弱信号
            signal_type = "弱信号"
            signal_score = np.random.randint(0, 40)
            base_return = 0.5
        
        # 扭亏幅度影响
        loss_2023 = -np.random.randint(5000, 100000)
        profit_2024 = np.random.randint(1000, 50000)
        turnaround_ratio = (profit_2024 - loss_2023) / abs(loss_2023)
        
        # 扭亏幅度大的表现更好
        if turnaround_ratio > 0.5:
            turnaround_factor = 1.3
        elif turnaround_ratio > 0.3:
            turnaround_factor = 1.1
        else:
            turnaround_factor = 1.0
        
        # 计算收益（考虑市场环境、信号强度、扭亏幅度）
        final_factor = market_factor * turnaround_factor
        
        ret_1d = np.random.normal(base_return * 0.5 * final_factor, 2.0)
        ret_3d = np.random.normal(base_return * 0.8 * final_factor, 2.5)
        ret_5d = np.random.normal(base_return * final_factor, 3.0)
        ret_10d = np.random.normal(base_return * 1.3 * final_factor, 4.0)
        ret_20d = np.random.normal(base_return * 1.5 * final_factor, 5.0)
        
        # 最大回撤
        max_drawdown = -np.random.uniform(2, 10) if ret_5d > 0 else -np.random.uniform(5, 15)
        
        stocks.append({
            '股票代码': code,
            '股票名称': name,
            '披露日期': f'2025-{np.random.randint(1,5):02d}-{np.random.randint(1,29):02d}',
            '市场环境': market,
            '信号类型': signal_type,
            '信号评分': signal_score,
            '2023利润(万)': loss_2023,
            '2024利润(万)': profit_2024,
            '扭亏幅度': f"{turnaround_ratio*100:.1f}%",
            '波动率%': round(np.random.uniform(2, 10), 2),
            '振幅%': round(np.random.uniform(2, 8), 2),
            '换手率%': round(np.random.uniform(1, 6), 2),
            '买入价': round(np.random.uniform(5, 50), 2),
            '1日收益%': round(ret_1d, 2),
            '3日收益%': round(ret_3d, 2),
            '5日收益%': round(ret_5d, 2),
            '10日收益%': round(ret_10d, 2),
            '20日收益%': round(ret_20d, 2),
            '最大回撤%': round(max_drawdown, 2),
        })
    
    df = pd.DataFrame(stocks)
    
    # 1. 整体统计
    print("=" * 80)
    print("一、整体回测统计")
    print("=" * 80)
    
    print(f"\n样本总数: {len(df)}")
    print(f"时间跨度: 2025年1-4月")
    
    for days in [1, 3, 5, 10, 20]:
        col = f'{days}日收益%'
        avg_return = df[col].mean()
        median_return = df[col].median()
        win_rate = (df[col] > 0).sum() / len(df) * 100
        max_return = df[col].max()
        min_return = df[col].min()
        std = df[col].std()
        
        print(f"\n{days}日持有:")
        print(f"  平均收益: {avg_return:.2f}%")
        print(f"  中位数收益: {median_return:.2f}%")
        print(f"  胜率: {win_rate:.1f}%")
        print(f"  最大收益: {max_return:.2f}%")
        print(f"  最大亏损: {min_return:.2f}%")
        print(f"  收益标准差: {std:.2f}%")
        if std > 0:
            sharpe = avg_return / std
            print(f"  夏普比率: {sharpe:.2f}")
    
    # 2. 按信号强度分析
    print("\n" + "=" * 80)
    print("二、按信号强度分析")
    print("=" * 80)
    
    for signal_type in ['强信号', '中等信号', '弱信号']:
        df_signal = df[df['信号类型'] == signal_type]
        print(f"\n【{signal_type}】样本数: {len(df_signal)}")
        
        for days in [5, 10]:
            col = f'{days}日收益%'
            avg = df_signal[col].mean()
            win = (df_signal[col] > 0).sum() / len(df_signal) * 100
            print(f"  {days}日: 平均{avg:.2f}%, 胜率{win:.1f}%")
    
    # 3. 按市场环境分析
    print("\n" + "=" * 80)
    print("三、按市场环境分析")
    print("=" * 80)
    
    for market in ['牛市', '震荡', '熊市']:
        df_market = df[df['市场环境'] == market]
        print(f"\n【{market}】样本数: {len(df_market)}")
        
        for days in [5, 10]:
            col = f'{days}日收益%'
            avg = df_market[col].mean()
            win = (df_market[col] > 0).sum() / len(df_market) * 100
            print(f"  {days}日: 平均{avg:.2f}%, 胜率{win:.1f}%")
    
    # 4. 信号在不同市场环境的表现
    print("\n" + "=" * 80)
    print("四、信号在不同市场环境的表现（5日收益）")
    print("=" * 80)
    
    for market in ['牛市', '震荡', '熊市']:
        print(f"\n【{market}】")
        for signal_type in ['强信号', '中等信号', '弱信号']:
            df_combo = df[(df['市场环境'] == market) & (df['信号类型'] == signal_type)]
            if len(df_combo) > 0:
                avg = df_combo['5日收益%'].mean()
                win = (df_combo['5日收益%'] > 0).sum() / len(df_combo) * 100
                print(f"  {signal_type}: {avg:.2f}% (胜率{win:.1f}%, 样本{len(df_combo)})")
    
    # 5. 扭亏幅度影响
    print("\n" + "=" * 80)
    print("五、扭亏幅度对收益的影响")
    print("=" * 80)
    
    df['扭亏幅度值'] = df.apply(lambda x: (x['2024利润(万)'] - x['2023利润(万)']) / abs(x['2023利润(万)']), axis=1)
    
    df_high_turnaround = df[df['扭亏幅度值'] > 0.5]
    df_medium_turnaround = df[(df['扭亏幅度值'] > 0.3) & (df['扭亏幅度值'] <= 0.5)]
    df_low_turnaround = df[df['扭亏幅度值'] <= 0.3]
    
    print(f"\n大幅扭亏(>50%): {len(df_high_turnaround)}只")
    print(f"  5日平均收益: {df_high_turnaround['5日收益%'].mean():.2f}%")
    print(f"  胜率: {(df_high_turnaround['5日收益%']>0).sum()/len(df_high_turnaround)*100:.1f}%")
    
    print(f"\n中等扭亏(30-50%): {len(df_medium_turnaround)}只")
    print(f"  5日平均收益: {df_medium_turnaround['5日收益%'].mean():.2f}%")
    print(f"  胜率: {(df_medium_turnaround['5日收益%']>0).sum()/len(df_medium_turnaround)*100:.1f}%")
    
    print(f"\n小幅扭亏(<30%): {len(df_low_turnaround)}只")
    print(f"  5日平均收益: {df_low_turnaround['5日收益%'].mean():.2f}%")
    print(f"  胜率: {(df_low_turnaround['5日收益%']>0).sum()/len(df_low_turnaround)*100:.1f}%")
    
    # 6. 最佳组合策略
    print("\n" + "=" * 80)
    print("六、最佳组合策略")
    print("=" * 80)
    
    # 策略1: 强信号 + 牛市/震荡
    df_best1 = df[(df['信号类型'] == '强信号') & (df['市场环境'].isin(['牛市', '震荡']))]
    print(f"\n策略1: 强信号 + 牛市/震荡市")
    print(f"  样本数: {len(df_best1)}")
    print(f"  5日平均收益: {df_best1['5日收益%'].mean():.2f}%")
    print(f"  胜率: {(df_best1['5日收益%']>0).sum()/len(df_best1)*100:.1f}%")
    print(f"  最大回撤: {df_best1['最大回撤%'].mean():.2f}%")
    
    # 策略2: 强信号 + 大幅扭亏
    df_best2 = df[(df['信号类型'] == '强信号') & (df['扭亏幅度值'] > 0.5)]
    print(f"\n策略2: 强信号 + 大幅扭亏(>50%)")
    print(f"  样本数: {len(df_best2)}")
    print(f"  5日平均收益: {df_best2['5日收益%'].mean():.2f}%")
    print(f"  胜率: {(df_best2['5日收益%']>0).sum()/len(df_best2)*100:.1f}%")
    print(f"  最大回撤: {df_best2['最大回撤%'].mean():.2f}%")
    
    # 策略3: 强信号 + 牛市 + 大幅扭亏
    df_best3 = df[(df['信号类型'] == '强信号') & (df['市场环境'] == '牛市') & (df['扭亏幅度值'] > 0.5)]
    if len(df_best3) > 0:
        print(f"\n策略3: 强信号 + 牛市 + 大幅扭亏（最优组合）")
        print(f"  样本数: {len(df_best3)}")
        print(f"  5日平均收益: {df_best3['5日收益%'].mean():.2f}%")
        print(f"  胜率: {(df_best3['5日收益%']>0).sum()/len(df_best3)*100:.1f}%")
        print(f"  最大回撤: {df_best3['最大回撤%'].mean():.2f}%")
    
    # 7. 风险收益分析
    print("\n" + "=" * 80)
    print("七、风险收益分析")
    print("=" * 80)
    
    print("\n按信号类型:")
    for signal_type in ['强信号', '中等信号', '弱信号']:
        df_signal = df[df['信号类型'] == signal_type]
        avg_return = df_signal['5日收益%'].mean()
        avg_drawdown = df_signal['最大回撤%'].mean()
        risk_reward = abs(avg_return / avg_drawdown) if avg_drawdown != 0 else 0
        
        print(f"\n{signal_type}:")
        print(f"  平均收益: {avg_return:.2f}%")
        print(f"  平均回撤: {avg_drawdown:.2f}%")
        print(f"  收益回撤比: {risk_reward:.2f}")
    
    # 8. 策略评估和建议
    print("\n" + "=" * 80)
    print("八、策略评估和建议")
    print("=" * 80)
    
    # 计算关键指标
    strong_signal = df[df['信号类型'] == '强信号']
    strong_avg = strong_signal['5日收益%'].mean()
    strong_win = (strong_signal['5日收益%'] > 0).sum() / len(strong_signal) * 100
    
    all_avg = df['5日收益%'].mean()
    
    print(f"\n关键指标:")
    print(f"  强信号平均收益: {strong_avg:.2f}%")
    print(f"  强信号胜率: {strong_win:.1f}%")
    print(f"  整体平均收益: {all_avg:.2f}%")
    
    print(f"\n策略评估:")
    if strong_avg > 5 and strong_win > 70:
        print("  ⭐⭐⭐ 策略效果优秀")
        print("  建议: 可以积极应用，重点关注强信号+牛市+大幅扭亏的组合")
    elif strong_avg > 3 and strong_win > 60:
        print("  ⭐⭐ 策略效果良好")
        print("  建议: 可以应用，但要控制仓位，避免熊市操作")
    elif strong_avg > 1.5 and strong_win > 50:
        print("  ⭐ 策略有一定效果")
        print("  建议: 小仓位试探，继续优化参数")
    else:
        print("  ✗ 策略效果不明显")
        print("  建议: 需要重新审视信号体系")
    
    print(f"\n操作建议:")
    print(f"  1. 优先选择: 强信号(≥70分) + 大幅扭亏(>50%)")
    print(f"  2. 市场环境: 牛市>震荡>熊市，熊市谨慎")
    print(f"  3. 持有周期: 5-10天为佳")
    print(f"  4. 仓位管理: 单只10-15%，总仓位50-70%")
    print(f"  5. 止损设置: 跌破横盘区间或-5%")
    
    # 保存结果
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'年报扭亏进阶回测_{timestamp}.xlsx'
    
    # 创建多个工作表
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='完整数据', index=False)
        
        # 按信号分组
        for signal_type in ['强信号', '中等信号', '弱信号']:
            df[df['信号类型'] == signal_type].to_excel(
                writer, sheet_name=signal_type, index=False
            )
        
        # 按市场环境分组
        for market in ['牛市', '震荡', '熊市']:
            df[df['市场环境'] == market].to_excel(
                writer, sheet_name=market, index=False
            )
        
        # 最佳组合
        if len(df_best1) > 0:
            df_best1.to_excel(writer, sheet_name='策略1_强信号+好市场', index=False)
        if len(df_best2) > 0:
            df_best2.to_excel(writer, sheet_name='策略2_强信号+大幅扭亏', index=False)
        if len(df_best3) > 0:
            df_best3.to_excel(writer, sheet_name='策略3_最优组合', index=False)
    
    print("\n" + "=" * 80)
    print(f"回测结果已保存到: {filename}")
    print("=" * 80)
    
    print("\n重要提示:")
    print("  这是基于策略逻辑的模拟回测，展示了:")
    print("  1. 不同信号强度的表现差异")
    print("  2. 市场环境对策略的影响")
    print("  3. 扭亏幅度与收益的关系")
    print("  4. 最佳组合策略的筛选")
    print("\n  实际应用时需要:")
    print("  1. 用真实历史数据验证")
    print("  2. 根据当前市场环境调整")
    print("  3. 严格执行风险控制")
    
    return df


if __name__ == '__main__':
    print("\n年报扭亏策略 - 进阶回测分析")
    print("=" * 80)
    print("模拟50只股票在不同市场环境下的表现")
    print("包含信号强度、市场环境、扭亏幅度等多维度分析")
    print("=" * 80)
    
    choice = input("\n是否继续? (y/n): ").strip().lower()
    
    if choice == 'y':
        df = generate_advanced_backtest()
        
        print("\n\n进阶回测完成！")
        print("\n查看Excel文件了解详细数据")
        print("包含多个工作表，按不同维度分组")
    else:
        print("已取消")
