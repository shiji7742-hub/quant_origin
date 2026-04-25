"""
年报扭亏策略回测演示
使用模拟数据展示回测流程
"""
from quick_backtest_turnaround import quick_backtest
import time

# 已知的一些扭亏股票案例（示例数据，需要替换为真实数据）
demo_stocks = [
    # 格式: (代码, 名称, 年报披露日期)
    # 这里列出一些可能的案例，实际需要验证
    
    # 2024年报案例（需要根据实际情况调整）
    ('600000', '浦发银行', '2025-03-28'),  # 示例
    ('000001', '平安银行', '2025-03-25'),  # 示例
    
    # 添加更多真实案例...
]

print("=" * 80)
print("年报扭亏策略回测演示")
print("=" * 80)
print("\n注意: 这是演示脚本，使用的是示例数据")
print("实际使用时需要替换为真实的扭亏股票和披露日期\n")
print("=" * 80)

# 提示用户
print("\n当前测试股票:")
for i, (code, name, date) in enumerate(demo_stocks, 1):
    print(f"{i}. {code} {name} - 披露日期: {date}")

print("\n" + "=" * 80)
choice = input("\n是否继续测试? (y/n): ").strip().lower()

if choice == 'y':
    print("\n开始回测...\n")
    
    for code, name, date in demo_stocks:
        print("\n" + "=" * 80)
        try:
            quick_backtest(code, name, date)
        except Exception as e:
            print(f"回测失败: {e}")
        
        print("\n" + "=" * 80)
        time.sleep(1)
    
    print("\n回测演示完成！")
    print("\n下一步:")
    print("1. 使用 find_turnaround_stocks.py 查找真实的扭亏股票")
    print("2. 更新 demo_stocks 列表中的股票信息")
    print("3. 重新运行此脚本进行真实回测")
else:
    print("\n已取消")
    print("\n提示:")
    print("1. 先运行: python find_turnaround_stocks.py")
    print("2. 找到真实的扭亏股票和披露日期")
    print("3. 更新此脚本中的 demo_stocks 列表")
    print("4. 再次运行此脚本")
