"""扫描涨停后砸破涨停最低价再快速反弹的个股
时间范围: 2025年10月 - 2026年1月
"""
import akshare as ak
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import threading
import time

def get_all_stocks():
    """获取所有A股主板股票"""
    print("获取A股列表...")
    df = ak.stock_zh_a_spot_em()
    df = df[df['代码'].str.match(r'^(60|00)')]
    df = df[~df['名称'].str.contains('ST')]
    df = df[df['最新价'].notna() & (df['最新价'] > 0)]
    df = df[df['成交量'].notna() & (df['成交量'] > 0)]
    print(f"共 {len(df)} 只有效主板股票")
    return df[['代码', '名称']].to_dict('records')

def find_limit_up_rebound_pattern(symbol, name):
    """
    查找涨停后分几天阴跌破位再快速反弹的模式
    要求：涨停后不是一天直接砸穿，而是分多天阴跌慢慢破位
    """
    try:
        # 获取2025年9月到现在的数据
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", 
                                start_date="20250901", end_date="20260112", adjust="qfq")
        if df is None or len(df) < 20:
            return []
        
        df = df.reset_index(drop=True)
        df['日期'] = pd.to_datetime(df['日期'])
        
        results = []
        
        # 遍历查找涨停板
        for i in range(1, len(df) - 5):  # 至少需要后面5天来判断
            row = df.iloc[i]
            prev_close = df.iloc[i-1]['收盘']
            
            # 判断是否涨停（涨幅>=9.5%）
            gain = (row['收盘'] - prev_close) / prev_close * 100
            if gain < 9.5:
                continue
            
            # 排除一字板（开盘价接近收盘价）
            if row['开盘'] >= row['收盘'] * 0.99:
                continue
            
            limit_up_date = row['日期']
            limit_up_low = row['最低']  # 涨停板当天最低价
            limit_up_close = row['收盘']
            
            # 只看2025年10月到2026年1月的涨停
            if limit_up_date < pd.Timestamp('2025-10-01') or limit_up_date > pd.Timestamp('2026-01-31'):
                continue
            
            # 查找后续是否砸破涨停最低价（要求分多天阴跌）
            broke_low = False
            broke_date = None
            broke_low_price = None
            days_to_break = 0  # 从涨停到破位的天数
            down_days = 0  # 阴跌天数
            
            for j in range(i + 1, min(i + 30, len(df))):  # 30天内
                day = df.iloc[j]
                prev_day = df.iloc[j-1]
                
                # 统计阴线天数（收盘<开盘 或 收盘<前一天收盘）
                if day['收盘'] < day['开盘'] or day['收盘'] < prev_day['收盘']:
                    down_days += 1
                
                if day['最低'] < limit_up_low:
                    broke_low = True
                    broke_date = day['日期']
                    broke_low_price = day['最低']
                    days_to_break = j - i
                    break
            
            if not broke_low:
                continue
            
            # 关键条件：要求分多天阴跌，不是一天直接砸穿
            # 条件1：从涨停到破位至少3天
            # 条件2：阴跌天数至少2天
            if days_to_break < 3 or down_days < 2:
                continue
            
            # 查找破位后是否快速反弹（5天内出现大阳线）
            rebound = False
            rebound_date = None
            rebound_gain = 0
            
            broke_idx = df[df['日期'] == broke_date].index[0]
            for k in range(broke_idx, min(broke_idx + 5, len(df))):  # 5天内反弹
                day = df.iloc[k]
                day_open = day['开盘']
                day_close = day['收盘']
                day_gain = (day_close - day_open) / day_open * 100
                
                # 大阳线（涨幅>3%）
                if day_gain > 3:
                    rebound = True
                    rebound_date = day['日期']
                    rebound_gain = day_gain
                    break
            
            if rebound:
                results.append({
                    '代码': symbol,
                    '名称': name,
                    '涨停日期': limit_up_date.strftime('%Y-%m-%d'),
                    '涨停最低价': round(limit_up_low, 2),
                    '涨停收盘价': round(limit_up_close, 2),
                    '阴跌天数': down_days,
                    '破位日期': broke_date.strftime('%Y-%m-%d'),
                    '破位最低价': round(broke_low_price, 2),
                    '反弹日期': rebound_date.strftime('%Y-%m-%d'),
                    '反弹涨幅': round(rebound_gain, 2),
                    '模式说明': f"涨停后阴跌{down_days}天，第{days_to_break}天破位后反弹"
                })
        
        return results
    except Exception as e:
        return []

class ProgressCounter:
    def __init__(self, total):
        self.completed = 0
        self.total = total
        self.lock = threading.Lock()
    
    def increment(self):
        with self.lock:
            self.completed += 1
            return self.completed

def scan_all_stocks(max_workers=15):
    """扫描全市场"""
    stocks = get_all_stocks()
    all_results = []
    total = len(stocks)
    counter = ProgressCounter(total)
    results_lock = threading.Lock()
    
    print(f"\n开始扫描，查找2025年10月-2026年1月涨停破位反弹模式...")
    print("=" * 60)
    
    start_time = time.time()
    
    def worker(stock):
        results = find_limit_up_rebound_pattern(stock['代码'], stock['名称'])
        completed = counter.increment()
        
        if results:
            with results_lock:
                all_results.extend(results)
            for r in results:
                print(f"[{completed}/{total}] ✓ {r['名称']}({r['代码']}) 涨停:{r['涨停日期']} 反弹:{r['反弹日期']}")
        
        if completed % 200 == 0:
            elapsed = time.time() - start_time
            speed = completed / elapsed if elapsed > 0 else 0
            eta = (total - completed) / speed if speed > 0 else 0
            print(f"[{completed}/{total}] 进度 {completed/total*100:.1f}%, 速度 {speed:.1f}只/秒, 预计剩余 {eta:.0f}秒")
        
        return results
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(worker, stock) for stock in stocks]
        for future in as_completed(futures):
            pass
    
    elapsed = time.time() - start_time
    print("=" * 60)
    print(f"扫描完成! 耗时 {elapsed:.1f}秒, 共发现 {len(all_results)} 条记录")
    
    return all_results

def save_to_excel(results):
    """保存结果到Excel"""
    if not results:
        print("没有找到符合条件的股票")
        return None
    
    df = pd.DataFrame(results)
    # 按涨停日期排序
    df = df.sort_values('涨停日期', ascending=False)
    
    filename = f"涨停阴跌反弹_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    # 使用openpyxl设置格式
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='扫描结果')
        
        # 调整列宽
        worksheet = writer.sheets['扫描结果']
        column_widths = {
            'A': 10,  # 代码
            'B': 12,  # 名称
            'C': 12,  # 涨停日期
            'D': 12,  # 涨停最低价
            'E': 12,  # 涨停收盘价
            'F': 10,  # 阴跌天数
            'G': 12,  # 破位日期
            'H': 12,  # 破位最低价
            'I': 12,  # 反弹日期
            'J': 10,  # 反弹涨幅
            'K': 35,  # 模式说明
        }
        for col, width in column_widths.items():
            worksheet.column_dimensions[col].width = width
    
    print(f"\n结果已保存到: {filename}")
    print(f"共 {len(df)} 条记录")
    return filename

if __name__ == "__main__":
    results = scan_all_stocks(max_workers=15)
    save_to_excel(results)
