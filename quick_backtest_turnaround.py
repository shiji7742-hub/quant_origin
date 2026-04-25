"""
快速回测年报扭亏策略
直接输入股票代码和披露日期进行回测
"""
from backtest_annual_turnaround import (
    check_annual_turnaround,
    check_signal_before_report,
    calculate_returns_after_report
)
from data_fetcher import get_stock_history
from datetime import datetime
import pandas as pd

def quick_backtest(symbol, name, report_date_str):
    """
    快速回测单只股票
    
    Args:
        symbol: 股票代码
        name: 股票名称
        report_date_str: 年报披露日期，格式：'2025-03-28'
    """
    print("=" * 80)
    print(f"回测: {symbol} {name}")
    print(f"年报披露日期: {report_date_str}")
    print("=" * 80)
    
    report_date = datetime.strptime(report_date_str, '%Y-%m-%d')
    
    # 1. 检查年报扭亏
    print("\n[1/4] 检查年报扭亏...")
    turnaround_info = check_annual_turnaround(symbol)
    print(f"结果: {turnaround_info}")
    
    if not turnaround_info['is_turnaround']:
        print("✗ 该股票未扭亏，无法回测")
        return
    
    print(f"✓ 确认扭亏: 2024年盈利 {turnaround_info['profit_2024']/10000:.2f}万")
    
    # 2. 获取K线数据
    print("\n[2/4] 获取K线数据...")
    df = get_stock_history(symbol, days=90)
    
    if df is None or len(df) < 20:
        print("✗ K线数据不足")
        return
    
    print(f"✓ 获取到 {len(df)} 天K线数据")
    
    # 3. 检查年报前信号
    print("\n[3/4] 检查年报前一天的信号...")
    signal_info = check_signal_before_report(df, report_date, days_before=1)
    
    print(f"\n信号详情:")
    print(f"  信号日期: {signal_info.get('signal_date', 'N/A')}")
    print(f"  信号价格: {signal_info.get('signal_price', 0):.2f}")
    print(f"  波动率: {signal_info.get('volatility', 0):.2f}%")
    print(f"  平均振幅: {signal_info.get('avg_amplitude', 0):.2f}%")
    print(f"  平均换手率: {signal_info.get('avg_turnover', 0):.2f}%")
    print(f"  横盘整理: {'✓' if signal_info.get('is_sideways') else '✗'}")
    print(f"  低振幅: {'✓' if signal_info.get('low_amplitude') else '✗'}")
    print(f"  低换手: {'✓' if signal_info.get('low_turnover') else '✗'}")
    
    # 计算信号评分
    signal_score = 0
    if signal_info.get('is_sideways'):
        signal_score += 40
    if signal_info.get('low_amplitude'):
        signal_score += 30
    if signal_info.get('low_turnover'):
        signal_score += 30
    
    print(f"\n信号评分: {signal_score}/100")
    
    if signal_score >= 70:
        print("评级: ⭐⭐⭐ 强信号")
    elif signal_score >= 40:
        print("评级: ⭐⭐ 中等信号")
    elif signal_score > 0:
        print("评级: ⭐ 弱信号")
    else:
        print("评级: 无信号")
    
    # 4. 计算年报后收益
    print("\n[4/4] 计算年报后收益...")
    returns_info = calculate_returns_after_report(df, report_date, [1, 3, 5, 10, 20])
    
    print(f"\n收益详情:")
    print(f"  买入日期: {returns_info.get('买入日期', 'N/A')}")
    print(f"  买入价格: {returns_info.get('买入价', 0):.2f}")
    
    for days in [1, 3, 5, 10, 20]:
        ret = returns_info.get(f'{days}日收益')
        if ret is not None:
            emoji = "📈" if ret > 0 else "📉"
            print(f"  {days}日收益: {ret:+.2f}% {emoji}")
        else:
            print(f"  {days}日收益: 数据不足")
    
    # 5. 综合评估
    print("\n" + "=" * 80)
    print("综合评估")
    print("=" * 80)
    
    print(f"\n✓ 年报扭亏: 2023年亏损{turnaround_info['profit_2023']/10000:.0f}万 → 2024年盈利{turnaround_info['profit_2024']/10000:.0f}万")
    print(f"{'✓' if signal_score > 0 else '✗'} 年报前信号: {signal_score}分")
    
    ret_1d = returns_info.get('1日收益')
    ret_5d = returns_info.get('5日收益')
    ret_10d = returns_info.get('10日收益')
    
    if ret_1d is not None:
        print(f"{'✓' if ret_1d > 0 else '✗'} 次日收益: {ret_1d:+.2f}%")
    if ret_5d is not None:
        print(f"{'✓' if ret_5d > 0 else '✗'} 5日收益: {ret_5d:+.2f}%")
    if ret_10d is not None:
        print(f"{'✓' if ret_10d > 0 else '✗'} 10日收益: {ret_10d:+.2f}%")
    
    # 策略有效性判断
    print("\n策略有效性:")
    if signal_score >= 70 and ret_5d and ret_5d > 3:
        print("⭐⭐⭐ 强验证 - 强信号+高收益")
    elif signal_score >= 40 and ret_5d and ret_5d > 0:
        print("⭐⭐ 中等验证 - 中等信号+正收益")
    elif signal_score > 0 or (ret_5d and ret_5d > 0):
        print("⭐ 弱验证 - 部分条件满足")
    else:
        print("✗ 未验证 - 信号或收益不佳")
    
    print("=" * 80)


def batch_backtest(stock_list):
    """
    批量回测
    
    Args:
        stock_list: [(代码, 名称, 披露日期), ...]
    """
    print("=" * 80)
    print(f"批量回测 {len(stock_list)} 只股票")
    print("=" * 80)
    
    results = []
    
    for symbol, name, report_date in stock_list:
        print(f"\n{'='*80}")
        quick_backtest(symbol, name, report_date)
        print()
        
        # 简单记录（可扩展）
        results.append({
            '代码': symbol,
            '名称': name,
            '披露日期': report_date
        })
    
    print("\n" + "=" * 80)
    print("批量回测完成")
    print("=" * 80)


if __name__ == '__main__':
    print("年报扭亏策略快速回测")
    print("=" * 80)
    
    # 示例1: 单只股票回测
    # quick_backtest('600000', '浦发银行', '2025-03-28')
    
    # 示例2: 批量回测
    # 请替换为实际的扭亏股票和披露日期
    test_stocks = [
        # ('600000', '浦发银行', '2025-03-28'),
        # ('000001', '平安银行', '2025-03-25'),
        # 添加更多...
    ]
    
    if test_stocks:
        batch_backtest(test_stocks)
    else:
        print("请在 test_stocks 中添加要回测的股票")
        print("格式: ('股票代码', '股票名称', '披露日期')")
        print("\n或者直接调用:")
        print("quick_backtest('600000', '浦发银行', '2025-03-28')")
