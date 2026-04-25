"""
快速横盘托单扫描 - 针对持仓或指定股票
"""
import akshare as ak
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

def analyze_stock(stock_code):
    """分析单只股票"""
    try:
        # 1. 获取分时数据
        df = ak.stock_zh_a_hist_min_em(symbol=stock_code, period='1', adjust='')
        if df.empty:
            return None
        
        df['时间'] = pd.to_datetime(df['时间'])
        today = datetime.now().date()
        df = df[df['时间'].dt.date == today]
        
        if len(df) < 10:
            return None
        
        # 2. 判断横盘
        recent = df.tail(10)
        high = recent['最高'].max()
        low = recent['最低'].min()
        avg = recent['收盘'].mean()
        current = df['收盘'].iloc[-1]
        
        volatility = (high - low) / avg * 100
        
        # 不是横盘就跳过
        if volatility >= 0.5:
            return None
        
        # 3. 距离支撑
        distance = (current - low) / low * 100
        
        # 不在关键位置就跳过
        if not (-0.3 <= distance <= 0.1):
            return None
        
        # 4. 获取逐笔数据
        symbol = f"sh{stock_code}" if stock_code.startswith('6') else f"sz{stock_code}"
        tick_df = ak.stock_zh_a_tick_tx_js(symbol=symbol)
        
        if tick_df.empty:
            return None
        
        tick_df['成交额(万)'] = tick_df['成交价'] * tick_df['成交量'] / 10000
        
        # 5. 分析大单
        recent_ticks = tick_df.head(20)
        big_orders = recent_ticks[recent_ticks['成交额(万)'] >= 50]
        
        if big_orders.empty:
            return None
        
        buy_big = big_orders[big_orders['性质'] == '买盘']
        sell_big = big_orders[big_orders['性质'] == '卖盘']
        
        buy_amount = buy_big['成交额(万)'].sum() if not buy_big.empty else 0
        sell_amount = sell_big['成交额(万)'].sum() if not sell_big.empty else 0
        
        # 6. 判断信号
        signal_type = None
        if buy_amount > sell_amount * 1.5 and buy_amount > 100:
            signal_type = '托单护盘'
        elif sell_amount > buy_amount * 1.5 and sell_amount > 100:
            signal_type = '即将跌破'
        
        if signal_type is None:
            return None
        
        # 7. 获取股票名称
        spot_df = ak.stock_zh_a_spot_em()
        stock_info = spot_df[spot_df['代码'] == stock_code]
        
        if stock_info.empty:
            name = stock_code
            price = current
            change = 0
        else:
            name = stock_info['名称'].values[0]
            price = stock_info['最新价'].values[0]
            change = stock_info['涨跌幅'].values[0]
        
        return {
            'code': stock_code,
            'name': name,
            'price': price,
            'change': change,
            'signal_type': signal_type,
            'support': low,
            'distance': distance,
            'volatility': volatility,
            'buy_amount': buy_amount,
            'sell_amount': sell_amount,
            'buy_count': len(buy_big),
            'sell_count': len(sell_big),
            'recent_ticks': recent_ticks.head(5)
        }
        
    except Exception as e:
        return None


def scan_stocks(stock_codes):
    """多线程扫描股票"""
    print(f"\n{'='*80}")
    print(f"快速横盘托单扫描 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}\n")
    print(f"扫描 {len(stock_codes)} 只股票...\n")
    
    results = []
    analyzed = 0
    lock = threading.Lock()
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_stock = {
            executor.submit(analyze_stock, code): code 
            for code in stock_codes
        }
        
        for future in as_completed(future_to_stock):
            with lock:
                analyzed += 1
                print(f"进度: {analyzed}/{len(stock_codes)}", end='\r')
            
            try:
                result = future.result(timeout=15)
                if result:
                    with lock:
                        results.append(result)
                        print(f"\n✅ {result['name']}({result['code']}) - {result['signal_type']}")
            except Exception as e:
                pass
    
    print(f"\n\n{'='*80}")
    print(f"扫描完成，发现 {len(results)} 个信号")
    print(f"{'='*80}\n")
    
    if results:
        # 按买入大单金额排序
        results.sort(key=lambda x: x['buy_amount'], reverse=True)
        
        for i, r in enumerate(results, 1):
            print(f"\n{i}. 【{r['signal_type']}】{r['name']} ({r['code']})")
            print(f"   价格: {r['price']:.2f}  涨跌: {r['change']:+.2f}%")
            print(f"   支撑: {r['support']:.2f}  距离: {r['distance']:+.2f}%  波动: {r['volatility']:.2f}%")
            print(f"   买单: {r['buy_count']}笔 {r['buy_amount']:.0f}万  卖单: {r['sell_count']}笔 {r['sell_amount']:.0f}万")
            
            print(f"   最近成交:")
            for idx, row in r['recent_ticks'].iterrows():
                order_type = "🔴" if row['性质'] == '买盘' else "🟢" if row['性质'] == '卖盘' else "⚪"
                amount = row['成交额(万)']
                flag = "💎" if amount >= 50 else "  "
                print(f"     {flag} {row['成交时间']} {order_type} {row['成交价']:.2f} × {row['成交量']:>6} = {amount:>7.2f}万")
        
        # 保存到Excel
        save_to_excel(results)
    else:
        print("暂无符合条件的股票")


def save_to_excel(results):
    """保存到Excel"""
    try:
        data = []
        for r in results:
            data.append({
                '股票代码': r['code'],
                '股票名称': r['name'],
                '最新价': r['price'],
                '涨跌幅': r['change'],
                '信号类型': r['signal_type'],
                '支撑位': r['support'],
                '距支撑': f"{r['distance']:.2f}%",
                '波动幅度': f"{r['volatility']:.2f}%",
                '买入大单': f"{r['buy_amount']:.0f}万",
                '卖出大单': f"{r['sell_amount']:.0f}万",
                '买单笔数': r['buy_count'],
                '卖单笔数': r['sell_count']
            })
        
        df = pd.DataFrame(data)
        filename = f"横盘托单_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        df.to_excel(filename, index=False)
        print(f"\n✅ 结果已保存到: {filename}")
        
    except Exception as e:
        print(f"保存Excel失败: {e}")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # 命令行指定股票
        stock_codes = sys.argv[1].split(',')
    else:
        # 读取持仓
        try:
            with open('my_holdings.txt', 'r', encoding='utf-8') as f:
                stock_codes = [line.strip() for line in f if line.strip()]
            print(f"已加载持仓: {', '.join(stock_codes)}")
        except:
            stock_input = input("请输入股票代码（逗号分隔）: ").strip()
            stock_codes = [code.strip() for code in stock_input.split(',')]
    
    scan_stocks(stock_codes)
