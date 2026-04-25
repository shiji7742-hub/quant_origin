"""
测试AI交易系统
快速验证功能是否正常
"""
from virtual_portfolio import VirtualPortfolio
from datetime import datetime

def test_system():
    """测试系统功能"""
    print("="*70)
    print("AI交易系统测试")
    print("="*70)
    
    # 测试1：创建账户
    print("\n【测试1】创建虚拟账户...")
    try:
        portfolio = VirtualPortfolio(initial_capital=100000)
        print(f"✓ 账户创建成功")
        print(f"  初始资金: {portfolio.initial_capital:,.2f}")
        print(f"  当前现金: {portfolio.cash:,.2f}")
    except Exception as e:
        print(f"✗ 失败: {e}")
        return
    
    # 测试2：模拟买入
    print("\n【测试2】模拟买入...")
    try:
        success, msg = portfolio.buy(
            code='600000',
            name='浦发银行',
            price=10.0,
            shares=1000,
            reason='测试买入'
        )
        if success:
            print(f"✓ {msg}")
            print(f"  剩余现金: {portfolio.cash:,.2f}")
        else:
            print(f"✗ {msg}")
    except Exception as e:
        print(f"✗ 失败: {e}")
    
    # 测试3：查看持仓
    print("\n【测试3】查看持仓...")
    try:
        positions = portfolio.get_position_status()
        if positions:
            print(f"✓ 持仓数量: {len(positions)}")
            for pos in positions:
                print(f"  {pos['code']} {pos['name']}: {pos['shares']}股")
        else:
            print("  当前无持仓")
    except Exception as e:
        print(f"✗ 失败: {e}")
    
    # 测试4：模拟卖出
    print("\n【测试4】模拟卖出...")
    try:
        success, msg = portfolio.sell(
            code='600000',
            shares=1000,
            price=10.5,
            reason='测试卖出'
        )
        if success:
            print(f"✓ {msg}")
            print(f"  当前现金: {portfolio.cash:,.2f}")
        else:
            print(f"✗ {msg}")
    except Exception as e:
        print(f"✗ 失败: {e}")
    
    # 测试5：查看交易记录
    print("\n【测试5】查看交易记录...")
    try:
        if portfolio.trades:
            print(f"✓ 交易记录数: {len(portfolio.trades)}")
            for trade in portfolio.trades[-2:]:
                action = "买入" if trade['type'] == 'buy' else "卖出"
                print(f"  {action} {trade['code']} {trade['name']}")
                if trade['type'] == 'sell':
                    print(f"    盈亏: {trade['profit']:+.2f} ({trade['profit_rate']:+.2f}%)")
        else:
            print("  无交易记录")
    except Exception as e:
        print(f"✗ 失败: {e}")
    
    # 测试6：计算总资产
    print("\n【测试6】计算总资产...")
    try:
        total = portfolio.get_total_value()
        profit = total - portfolio.initial_capital
        print(f"✓ 总资产: {total:,.2f}")
        print(f"  盈亏: {profit:+,.2f} ({profit/portfolio.initial_capital*100:+.2f}%)")
    except Exception as e:
        print(f"✗ 失败: {e}")
    
    print("\n" + "="*70)
    print("测试完成！")
    print("="*70)
    print("\n提示：")
    print("• 测试数据已保存到 virtual_trading_data/ 目录")
    print("• 如需重新测试，请删除该目录")
    print("• 运行 python auto_trading_system.py 开始真实模拟交易")

if __name__ == "__main__":
    test_system()
