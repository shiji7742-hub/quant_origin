"""
查看虚拟账户状态
"""
from virtual_portfolio import VirtualPortfolio
from datetime import datetime
import pandas as pd

def view_portfolio():
    """查看账户详情"""
    portfolio = VirtualPortfolio()
    
    # 显示账户状态
    portfolio.print_status()
    
    # 显示最近交易
    if portfolio.trades:
        print("\n" + "="*70)
        print("最近10笔交易")
        print("="*70)
        recent_trades = portfolio.trades[-10:]
        for i, trade in enumerate(reversed(recent_trades), 1):
            action = "买入" if trade['type'] == 'buy' else "卖出"
            print(f"\n{i}. [{trade['date']}] {action} {trade['code']} {trade['name']}")
            print(f"   价格: {trade['price']:.2f}  数量: {trade['shares']}股  金额: {trade['amount']:,.2f}")
            if trade['type'] == 'sell':
                print(f"   盈亏: {trade['profit']:+,.2f} ({trade['profit_rate']:+.2f}%)")
            print(f"   原因: {trade['reason']}")
    
    # 显示收益曲线
    if portfolio.daily_records:
        print("\n" + "="*70)
        print("收益曲线（最近10天）")
        print("="*70)
        recent_records = portfolio.daily_records[-10:]
        for record in recent_records:
            bar_length = int(abs(record['total_return']) / 2)
            bar = "█" * bar_length
            print(f"{record['date']}: {record['total_return']:+6.2f}% {bar}")

if __name__ == "__main__":
    view_portfolio()
