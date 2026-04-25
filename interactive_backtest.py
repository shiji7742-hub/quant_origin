"""
交互式回测工具
手动输入股票进行回测
"""
from quick_backtest_turnaround import quick_backtest
import sys

def interactive_backtest():
    """交互式回测"""
    print("=" * 80)
    print("年报扭亏策略 - 交互式回测")
    print("=" * 80)
    print("\n请输入要回测的股票信息")
    print("提示: 需要是已经披露年报且确认扭亏的股票\n")
    
    stocks = []
    
    while True:
        print("-" * 80)
        code = input("股票代码 (6位数字，输入q退出): ").strip()
        
        if code.lower() == 'q':
            break
        
        if len(code) != 6 or not code.isdigit():
            print("✗ 代码格式错误，请输入6位数字")
            continue
        
        name = input("股票名称: ").strip()
        if not name:
            print("✗ 名称不能为空")
            continue
        
        date = input("年报披露日期 (格式: 2025-03-28): ").strip()
        
        # 简单验证日期格式
        try:
            from datetime import datetime
            datetime.strptime(date, '%Y-%m-%d')
        except:
            print("✗ 日期格式错误，请使用 YYYY-MM-DD 格式")
            continue
        
        stocks.append((code, name, date))
        print(f"✓ 已添加: {code} {name} {date}")
        
        more = input("\n继续添加? (y/n): ").strip().lower()
        if more != 'y':
            break
    
    if not stocks:
        print("\n未添加任何股票，退出")
        return
    
    # 开始回测
    print("\n" + "=" * 80)
    print(f"开始回测 {len(stocks)} 只股票")
    print("=" * 80)
    
    for i, (code, name, date) in enumerate(stocks, 1):
        print(f"\n[{i}/{len(stocks)}] 回测 {code} {name}")
        print("=" * 80)
        
        try:
            quick_backtest(code, name, date)
        except Exception as e:
            print(f"✗ 回测失败: {e}")
            import traceback
            traceback.print_exc()
        
        if i < len(stocks):
            input("\n按回车继续下一只...")
    
    print("\n" + "=" * 80)
    print("回测完成！")
    print("=" * 80)


def quick_test():
    """快速测试模式 - 使用预设股票"""
    print("=" * 80)
    print("快速测试模式")
    print("=" * 80)
    
    # 预设一些测试股票（需要根据实际情况调整）
    test_stocks = [
        ('600000', '浦发银行', '2025-03-28'),
        # 添加更多已知的扭亏股票...
    ]
    
    print(f"\n将测试 {len(test_stocks)} 只预设股票:")
    for code, name, date in test_stocks:
        print(f"  - {code} {name} ({date})")
    
    choice = input("\n继续? (y/n): ").strip().lower()
    
    if choice == 'y':
        for code, name, date in test_stocks:
            print("\n" + "=" * 80)
            try:
                quick_backtest(code, name, date)
            except Exception as e:
                print(f"✗ 回测失败: {e}")
            print("=" * 80)
            input("\n按回车继续...")
    else:
        print("已取消")


if __name__ == '__main__':
    print("\n年报扭亏策略回测工具")
    print("=" * 80)
    print("1. 交互式回测 (手动输入股票)")
    print("2. 快速测试 (使用预设股票)")
    print("=" * 80)
    
    choice = input("\n请选择 (1/2): ").strip()
    
    if choice == '1':
        interactive_backtest()
    elif choice == '2':
        quick_test()
    else:
        print("无效选择")
