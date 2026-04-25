"""
快速大单监测 - 监测持仓股票
"""
import akshare as ak
import pandas as pd
from datetime import datetime

def monitor_holdings():
    """监测持仓股票的大单情况"""
    
    # 读取持仓
    try:
        with open('my_holdings.txt', 'r', encoding='utf-8') as f:
            holdings = [line.strip() for line in f if line.strip()]
    except:
        print("未找到 my_holdings.txt，请手动输入股票代码")
        holdings = input("股票代码（逗号分隔）: ").split(',')
    
    print(f"\n{'='*80}")
    print(f"持仓大单监测 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}\n")
    
    # 获取资金流向排名
    try:
        flow_df = ak.stock_individual_fund_flow_rank(symbol="即时")
        
        for stock_code in holdings:
            stock_code = stock_code.strip()
            
            # 查找该股票
            stock_flow = flow_df[flow_df['代码'] == stock_code]
            
            if stock_flow.empty:
                print(f"❌ {stock_code} - 未找到数据")
                continue
            
            name = stock_flow['名称'].values[0]
            price = stock_flow['最新价'].values[0]
            change = stock_flow['涨跌幅'].values[0]
            
            # 资金流向
            main_flow = stock_flow['主力净流入-净额'].values[0] if '主力净流入-净额' in stock_flow.columns else 0
            main_pct = stock_flow['主力净流入-净占比'].values[0] if '主力净流入-净占比' in stock_flow.columns else 0
            
            super_flow = stock_flow['超大单净流入-净额'].values[0] if '超大单净流入-净额' in stock_flow.columns else 0
            super_pct = stock_flow['超大单净流入-净占比'].values[0] if '超大单净流入-净占比' in stock_flow.columns else 0
            
            big_flow = stock_flow['大单净流入-净额'].values[0] if '大单净流入-净额' in stock_flow.columns else 0
            big_pct = stock_flow['大单净流入-净占比'].values[0] if '大单净流入-净占比' in stock_flow.columns else 0
            
            # 判断状态
            if main_flow > 0:
                status = "✅ 流入"
            else:
                status = "❌ 流出"
            
            # 判断强度
            if abs(main_pct) > 10:
                strength = "🔥🔥🔥"
            elif abs(main_pct) > 5:
                strength = "🔥🔥"
            elif abs(main_pct) > 2:
                strength = "🔥"
            else:
                strength = ""
            
            print(f"【{name}】({stock_code}) {strength}")
            print(f"  价格: {price:.2f}  涨跌: {change:+.2f}%")
            print(f"  {status} 主力: {main_flow/10000:.2f}万 ({main_pct:+.2f}%)")
            print(f"         超大单: {super_flow/10000:.2f}万 ({super_pct:+.2f}%)")
            print(f"         大单: {big_flow/10000:.2f}万 ({big_pct:+.2f}%)")
            print()
            
    except Exception as e:
        print(f"获取数据失败: {e}")
        print("提示: 请确保在交易时间运行，且网络连接正常")


def monitor_single_stock(stock_code):
    """监测单只股票的详细大单"""
    print(f"\n{'='*80}")
    print(f"【{stock_code}】详细大单监测")
    print(f"{'='*80}\n")
    
    try:
        # 1. 资金流向
        flow_df = ak.stock_individual_fund_flow_rank(symbol="即时")
        stock_flow = flow_df[flow_df['代码'] == stock_code]
        
        if not stock_flow.empty:
            print("💰 资金流向:")
            print(f"  主力净流入: {stock_flow['主力净流入-净额'].values[0]/10000:.2f}万")
            print(f"  超大单: {stock_flow['超大单净流入-净额'].values[0]/10000:.2f}万")
            print(f"  大单: {stock_flow['大单净流入-净额'].values[0]/10000:.2f}万")
            print(f"  中单: {stock_flow['中单净流入-净额'].values[0]/10000:.2f}万")
            print(f"  小单: {stock_flow['小单净流入-净额'].values[0]/10000:.2f}万")
        
        # 2. 分时数据
        print("\n📈 分时成交:")
        symbol = f"sh{stock_code}" if stock_code.startswith('6') else f"sz{stock_code}"
        tick_df = ak.stock_zh_a_tick_tx_js(symbol=symbol)
        
        if not tick_df.empty:
            tick_df['成交额(万)'] = tick_df['成交价'] * tick_df['成交量'] / 10000
            
            # 显示最近20笔
            print("  最近20笔成交:")
            for idx, row in tick_df.head(20).iterrows():
                order_type = "🔴" if row['性质'] == '买盘' else "🟢" if row['性质'] == '卖盘' else "⚪"
                amount = row['成交额(万)']
                
                # 标记大单
                if amount >= 100:
                    flag = "💎💎💎"
                elif amount >= 50:
                    flag = "💎💎"
                elif amount >= 20:
                    flag = "💎"
                else:
                    flag = "   "
                
                print(f"  {flag} {row['成交时间']} {order_type} {row['成交价']:.2f} × {row['成交量']:>6} = {amount:>8.2f}万")
            
            # 统计大单
            big_orders = tick_df[tick_df['成交额(万)'] >= 50]
            if not big_orders.empty:
                print(f"\n  📊 大单统计(≥50万):")
                print(f"     笔数: {len(big_orders)}")
                print(f"     总额: {big_orders['成交额(万)'].sum():.2f}万")
                
                buy_orders = big_orders[big_orders['性质'] == '买盘']
                sell_orders = big_orders[big_orders['性质'] == '卖盘']
                
                print(f"     买入: {len(buy_orders)}笔 {buy_orders['成交额(万)'].sum():.2f}万")
                print(f"     卖出: {len(sell_orders)}笔 {sell_orders['成交额(万)'].sum():.2f}万")
        
    except Exception as e:
        print(f"获取数据失败: {e}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # 监测指定股票
        stock_code = sys.argv[1]
        monitor_single_stock(stock_code)
    else:
        # 监测持仓
        monitor_holdings()
