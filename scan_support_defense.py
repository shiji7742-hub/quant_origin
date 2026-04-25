"""
全市场扫描横盘托单机会
自动发现分时横盘且有大单护盘的股票
"""
import akshare as ak
import pandas as pd
from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

def analyze_single_stock(row):
    """分析单只股票（用于多线程）"""
    stock_code = row['代码']
    stock_name = row['名称']
    
    try:
        # 获取分时数据
        minute_df = get_minute_data(stock_code)
        if minute_df is None or len(minute_df) < 10:
            return None
        
        # 判断横盘
        is_side, side_info = check_sideways(minute_df)
        if not is_side:
            return None
        
        # 获取逐笔数据
        tick_df = get_tick_data(stock_code)
        if tick_df is None:
            return None
        
        # 检测托单
        signal = check_defense(minute_df, tick_df, side_info)
        
        if signal:
            return {
                'code': stock_code,
                'name': stock_name,
                'price': row['最新价'],
                'change': row['涨跌幅'],
                'signal': signal,
                'side_info': side_info
            }
        
        return None
        
    except Exception as e:
        return None


def scan_sideways_stocks():
    """扫描横盘股票"""
    print(f"\n{'='*80}")
    print(f"扫描横盘托单机会 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*80}\n")
    
    results = []
    
    try:
        # 1. 获取今日涨幅在 -3% 到 +3% 的股票（横盘特征）
        print("📊 获取候选股票...")
        
        # 添加重试机制
        for retry in range(3):
            try:
                spot_df = ak.stock_zh_a_spot_em()
                break
            except Exception as e:
                if retry < 2:
                    print(f"   重试 {retry + 1}/3...")
                    time.sleep(2)
                else:
                    raise e
        
        # 筛选条件
        candidates = spot_df[
            (spot_df['涨跌幅'] > -3) & 
            (spot_df['涨跌幅'] < 3) &
            (spot_df['成交额'] > 50000000) &  # 成交额 > 5000万
            (~spot_df['代码'].str.startswith('688')) &  # 排除科创板
            (~spot_df['代码'].str.startswith('8')) &    # 排除北交所
            (~spot_df['名称'].str.contains('ST'))       # 排除ST
        ].copy()
        
        print(f"找到 {len(candidates)} 只候选股票")
        
        # 2. 多线程分析
        print(f"\n🔍 多线程分析中（使用 10 个线程）...\n")
        
        results = []
        analyzed = 0
        lock = threading.Lock()
        
        # 只分析前30只，避免太慢
        candidates_to_analyze = candidates.head(30)
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            # 提交所有任务
            future_to_stock = {
                executor.submit(analyze_single_stock, row): row['代码'] 
                for idx, row in candidates_to_analyze.iterrows()
            }
            
            # 处理完成的任务
            for future in as_completed(future_to_stock, timeout=60):
                with lock:
                    analyzed += 1
                    if analyzed % 5 == 0:
                        print(f"   进度: {analyzed}/{len(candidates_to_analyze)}")
                
                try:
                    result = future.result(timeout=10)
                    if result:
                        with lock:
                            results.append(result)
                            print(f"✅ {result['name']}({result['code']}) - {result['signal']['type']}")
                except Exception as e:
                    pass
        
        # 3. 输出结果
        print(f"\n{'='*80}")
        print(f"扫描完成，发现 {len(results)} 个信号")
        print(f"{'='*80}\n")
        
        if results:
            # 按信号强度排序
            results.sort(key=lambda x: x['signal']['buy_big_amount'], reverse=True)
            
            for i, r in enumerate(results, 1):
                print(f"\n{i}. 【{r['signal']['type']}】{r['name']} ({r['code']})")
                print(f"   价格: {r['price']:.2f}  涨跌: {r['change']:+.2f}%")
                print(f"   横盘: {r['side_info']['low']:.2f} - {r['side_info']['high']:.2f}")
                print(f"   支撑: {r['signal']['support']:.2f}  距离: {r['signal']['distance']:+.2f}%")
                print(f"   买单: {r['signal']['buy_big_amount']:.0f}万  卖单: {r['signal']['sell_big_amount']:.0f}万")
            
            # 保存到Excel
            save_to_excel(results)
        else:
            print("暂无符合条件的股票")
        
    except Exception as e:
        print(f"扫描出错: {e}")


def get_minute_data(stock_code):
    """获取分时数据"""
    try:
        df = ak.stock_zh_a_hist_min_em(symbol=stock_code, period='1', adjust='')
        if df.empty:
            return None
        
        df['时间'] = pd.to_datetime(df['时间'])
        today = datetime.now().date()
        df = df[df['时间'].dt.date == today]
        
        return df
    except:
        return None


def get_tick_data(stock_code, timeout=5):
    """获取逐笔数据（带超时）"""
    try:
        symbol = f"sh{stock_code}" if stock_code.startswith('6') else f"sz{stock_code}"
        df = ak.stock_zh_a_tick_tx_js(symbol=symbol)
        
        if df.empty:
            return None
        
        df['成交额(万)'] = df['成交价'] * df['成交量'] / 10000
        return df
    except:
        return None


def check_sideways(df, window=10, threshold=1.5):
    """判断是否横盘"""
    if len(df) < window:
        return False, None
    
    recent = df.tail(window)
    high = recent['最高'].max()
    low = recent['最低'].min()
    avg = recent['收盘'].mean()
    
    volatility = (high - low) / avg * 100
    
    is_sideways = volatility < threshold
    
    return is_sideways, {
        'high': high,
        'low': low,
        'avg': avg,
        'volatility': volatility,
        'support': low
    }


def check_defense(minute_df, tick_df, side_info):
    """检测托单"""
    current_price = minute_df['收盘'].iloc[-1]
    support = side_info['support']
    
    # 距离支撑位
    distance = (current_price - support) / support * 100
    
    # 只关注接近支撑的
    if not (-0.3 <= distance <= 0.1):
        return None
    
    # 分析大单
    recent_ticks = tick_df.head(20)
    big_orders = recent_ticks[recent_ticks['成交额(万)'] >= 50]
    
    if big_orders.empty:
        return None
    
    buy_big = big_orders[big_orders['性质'] == '买盘']
    sell_big = big_orders[big_orders['性质'] == '卖盘']
    
    buy_amount = buy_big['成交额(万)'].sum() if not buy_big.empty else 0
    sell_amount = sell_big['成交额(万)'].sum() if not sell_big.empty else 0
    
    # 托单护盘
    if buy_amount > sell_amount * 1.5 and buy_amount > 100:
        return {
            'type': '托单护盘',
            'support': support,
            'distance': distance,
            'buy_big_amount': buy_amount,
            'sell_big_amount': sell_amount,
            'buy_big_count': len(buy_big),
            'sell_big_count': len(sell_big)
        }
    
    # 即将跌破
    elif sell_amount > buy_amount * 1.5 and sell_amount > 100:
        return {
            'type': '即将跌破',
            'support': support,
            'distance': distance,
            'buy_big_amount': buy_amount,
            'sell_big_amount': sell_amount,
            'buy_big_count': len(buy_big),
            'sell_big_count': len(sell_big)
        }
    
    return None


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
                '信号类型': r['signal']['type'],
                '支撑位': r['signal']['support'],
                '距支撑': f"{r['signal']['distance']:.2f}%",
                '横盘区间': f"{r['side_info']['low']:.2f}-{r['side_info']['high']:.2f}",
                '波动幅度': f"{r['side_info']['volatility']:.2f}%",
                '买入大单': f"{r['signal']['buy_big_amount']:.0f}万",
                '卖出大单': f"{r['signal']['sell_big_amount']:.0f}万",
                '买单笔数': r['signal']['buy_big_count'],
                '卖单笔数': r['signal']['sell_big_count']
            })
        
        df = pd.DataFrame(data)
        filename = f"横盘托单扫描_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        df.to_excel(filename, index=False)
        print(f"\n✅ 结果已保存到: {filename}")
        
    except Exception as e:
        print(f"保存Excel失败: {e}")


if __name__ == "__main__":
    scan_sideways_stocks()
