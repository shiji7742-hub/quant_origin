"""
快速检查持仓股票的托单情况
"""
import akshare as ak
import pandas as pd
from datetime import datetime

def quick_check(stock_code):
    """快速检查单只股票"""
    print(f"\n{'='*70}")
    print(f"检查 {stock_code} 的托单情况")
    print(f"{'='*70}\n")
    
    try:
        # 1. 获取分时数据
        df = ak.stock_zh_a_hist_min_em(symbol=stock_code, period='1', adjust='')
        df['时间'] = pd.to_datetime(df['时间'])
        today = datetime.now().date()
        df = df[df['时间'].dt.date == today]
        
        if df.empty:
            print("❌ 无分时数据")
            return
        
        # 2. 分析横盘
        recent = df.tail(10)
        high = recent['最高'].max()
        low = recent['最低'].min()
        avg = recent['收盘'].mean()
        current = df['收盘'].iloc[-1]
        
        volatility = (high - low) / avg * 100
        
        print(f"📊 分时状态:")
        print(f"   当前价: {current:.2f}")
        print(f"   10分钟区间: {low:.2f} - {high:.2f}")
        print(f"   波动幅度: {volatility:.2f}%")
        
        if volatility < 1.5:
            print(f"   ✅ 横盘中")
        else:
            print(f"   ❌ 非横盘")
        
        # 3. 距离支撑
        distance = (current - low) / low * 100
        print(f"   支撑位: {low:.2f}")
        print(f"   距支撑: {distance:+.2f}%")
        
        if -0.3 <= distance <= 0.1:
            print(f"   ⚠️  接近支撑位！")
        
        # 4. 获取逐笔数据
        symbol = f"sh{stock_code}" if stock_code.startswith('6') else f"sz{stock_code}"
        tick_df = ak.stock_zh_a_tick_tx_js(symbol=symbol)
        
        if not tick_df.empty:
            tick_df['成交额(万)'] = tick_df['成交价'] * tick_df['成交量'] / 10000
            
            print(f"\n💰 大单情况 (最近20笔):")
            
            recent_ticks = tick_df.head(20)
            big_orders = recent_ticks[recent_ticks['成交额(万)'] >= 50]
            
            if not big_orders.empty:
                buy_big = big_orders[big_orders['性质'] == '买盘']
                sell_big = big_orders[big_orders['性质'] == '卖盘']
                
                buy_amount = buy_big['成交额(万)'].sum() if not buy_big.empty else 0
                sell_amount = sell_big['成交额(万)'].sum() if not sell_big.empty else 0
                
                print(f"   买入大单: {len(buy_big)}笔  {buy_amount:.0f}万")
                print(f"   卖出大单: {len(sell_big)}笔  {sell_amount:.0f}万")
                
                if buy_amount > sell_amount * 1.5:
                    print(f"   🛡️  有托单护盘迹象！")
                elif sell_amount > buy_amount * 1.5:
                    print(f"   ⚠️  卖压较大，注意风险！")
                else:
                    print(f"   ⚖️  买卖相对均衡")
            else:
                print(f"   暂无大单")
            
            # 5. 显示最近成交
            print(f"\n🔍 最近10笔成交:")
            for idx, row in recent_ticks.head(10).iterrows():
                order_type = "🔴" if row['性质'] == '买盘' else "🟢" if row['性质'] == '卖盘' else "⚪"
                amount = row['成交额(万)']
                
                flag = "💎" if amount >= 50 else "  "
                
                print(f"   {flag} {row['成交时间']} {order_type} {row['成交价']:.2f} × {row['成交量']:>6} = {amount:>7.2f}万")
        
    except Exception as e:
        print(f"❌ 检查失败: {e}")


def check_all_holdings():
    """检查所有持仓"""
    try:
        with open('my_holdings.txt', 'r', encoding='utf-8') as f:
            holdings = [line.strip() for line in f if line.strip()]
        
        print(f"\n{'#'*70}")
        print(f"持仓托单检查 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'#'*70}")
        
        for stock_code in holdings:
            quick_check(stock_code)
        
    except FileNotFoundError:
        print("未找到 my_holdings.txt")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # 检查指定股票
        quick_check(sys.argv[1])
    else:
        # 检查所有持仓
        check_all_holdings()
