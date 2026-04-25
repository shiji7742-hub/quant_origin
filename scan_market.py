"""全市场扫描 - 涨停破位洗盘战法（多线程版本）"""
import akshare as ak
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from config import MAINBOARD_PATTERN
import threading

# 线程安全的计数器
scan_count = 0
scan_lock = threading.Lock()

def get_all_mainboard_stocks():
    """获取所有主板股票"""
    print("正在获取主板股票列表...")
    df = ak.stock_zh_a_spot_em()
    # 只保留主板（60、00开头，排除创业板30、科创板68）
    df = df[df['代码'].str.match(MAINBOARD_PATTERN)]
    # 排除ST股
    df = df[~df['名称'].str.contains('ST')]
    # 排除停牌（成交额为0）
    df = df[df['成交额'] > 0]
    print(f"共 {len(df)} 只主板股票")
    return df['代码'].tolist()

def scan_limit_up_washout(symbol: str) -> dict:
    """扫描单只股票的涨停破位洗盘状态"""
    global scan_count
    try:
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
        if df is None or len(df) < 35:
            return None
        
        df = df.tail(40).reset_index(drop=True)
        latest = df.iloc[-1]
        latest_idx = len(df) - 1
        
        # 找非一字涨停板
        limit_up_info = None
        for i in range(latest_idx - 3, max(latest_idx - 20, 0), -1):
            row = df.iloc[i]
            prev_close = df.iloc[i-1]['收盘'] if i > 0 else row['开盘']
            
            gain = (row['收盘'] - prev_close) / prev_close * 100
            is_limit_up = gain >= 9.5
            is_not_yizi = row['开盘'] < row['收盘'] * 0.99
            
            if is_limit_up and is_not_yizi:
                limit_up_info = {
                    'idx': i,
                    'date': str(row.get('日期', '')),
                    'low': row['最低'],
                    'close': row['收盘']
                }
                break
        
        if not limit_up_info:
            return None
        
        limit_idx = limit_up_info['idx']
        limit_low = limit_up_info['low']
        limit_close = limit_up_info['close']
        
        # 检查是否低位启动（涨停前10日涨幅不超过20%）
        if limit_idx >= 10:
            price_10d_ago = df.iloc[limit_idx - 10]['收盘']
            price_before = df.iloc[limit_idx - 1]['收盘']
            pre_gain = (price_before - price_10d_ago) / price_10d_ago * 100
            if pre_gain > 20:
                return None  # 不是低位启动
        
        # 检查涨停后是否先创新高再破位（排除）
        made_new_high = False
        broke_support = False
        for i in range(limit_idx + 1, latest_idx + 1):
            row = df.iloc[i]
            if row['最高'] > limit_close * 1.05:
                made_new_high = True
            if row['最低'] <= limit_low:
                broke_support = True
        
        if made_new_high:
            return None  # 先涨后跌，不符合
        
        # 今日涨幅
        today_gain = (latest['收盘'] - latest['开盘']) / latest['开盘'] * 100
        is_big_yang = today_gain > 3
        recovered = latest['收盘'] > limit_low
        
        # 检查近5日均量是否相比前20日均量明显放大
        if len(df) >= 25:
            vol_recent_5 = df['成交量'].iloc[-5:].mean()
            vol_prev_20 = df['成交量'].iloc[-25:-5].mean()
            vol_ratio = vol_recent_5 / vol_prev_20 if vol_prev_20 > 0 else 0
            volume_amplify = vol_ratio > 1.5
        else:
            vol_ratio = 0
            volume_amplify = False
        
        # 【新增】当日量比 > 2
        vol_ma5_today = df['成交量'].iloc[-6:-1].mean() if len(df) >= 6 else 0
        today_vol_ratio = latest['成交量'] / vol_ma5_today if vol_ma5_today > 0 else 0
        high_vol_ratio = today_vol_ratio > 2
        
        # 【新增】当日涨幅 < 6%（不追高）
        not_chasing_high = today_gain < 6
        
        # 判断状态
        if broke_support and is_big_yang and recovered and volume_amplify and high_vol_ratio and not_chasing_high:
            return {
                'status': 'TRIGGERED',
                'symbol': symbol,
                'limit_date': limit_up_info['date'],
                'limit_low': limit_low,
                'today_gain': round(today_gain, 2),
                'close': latest['收盘'],
                'vol_ratio': round(vol_ratio, 2),
                'today_vol_ratio': round(today_vol_ratio, 2),
            }
        elif not broke_support:
            distance = (latest['收盘'] - limit_low) / limit_low * 100
            return {
                'status': 'WATCHING',
                'symbol': symbol,
                'limit_date': limit_up_info['date'],
                'limit_low': limit_low,
                'close': latest['收盘'],
                'distance': round(distance, 2),
            }
        elif broke_support and (not recovered or not volume_amplify):
            return {
                'status': 'POTENTIAL',
                'symbol': symbol,
                'limit_date': limit_up_info['date'],
                'limit_low': limit_low,
                'close': latest['收盘'],
                'distance': round(distance, 2),
            }
        elif broke_support and (not recovered or not volume_up):
            return {
                'status': 'POTENTIAL',
                'symbol': symbol,
                'limit_date': limit_up_info['date'],
                'limit_low': limit_low,
                'close': latest['收盘'],
                'today_gain': round(today_gain, 2),
                'vol_ratio': round(vol_ratio, 2),
            }
        
        return None
    except:
        return None

def run_scan(max_workers=10):
    """运行全市场扫描（多线程）"""
    global scan_count
    scan_count = 0
    
    print("=" * 70)
    print(f"涨停破位洗盘战法 - 全市场扫描（多线程版本）")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"线程数: {max_workers}")
    print("=" * 70)
    
    stocks = get_all_mainboard_stocks()
    total = len(stocks)
    
    triggered = []
    potential = []
    watching = []
    
    print(f"开始扫描...")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(scan_limit_up_washout, symbol): symbol for symbol in stocks}
        
        for future in as_completed(futures):
            with scan_lock:
                scan_count += 1
                if scan_count % 200 == 0:
                    print(f"扫描进度: {scan_count}/{total} ({scan_count*100//total}%)")
            
            result = future.result()
            if result:
                if result['status'] == 'TRIGGERED':
                    triggered.append(result)
                    print(f"  ★ 发现触发: {result['symbol']}")
                elif result['status'] == 'POTENTIAL':
                    potential.append(result)
                elif result['status'] == 'WATCHING':
                    watching.append(result)
    
    print(f"\n扫描完成！共扫描 {total} 只股票")
    
    # 输出结果
    print("\n" + "=" * 70)
    print(f"【已触发 - 今日可抄底】共 {len(triggered)} 只")
    print("=" * 70)
    for r in triggered:
        print(f"  {r['symbol']} | 涨停日:{r['limit_date']} | 涨停最低:{r['limit_low']:.2f} | 今日涨幅:{r['today_gain']}% | 量比:{r['vol_ratio']} | 收盘:{r['close']:.2f}")
    
    print("\n" + "=" * 70)
    print(f"【潜在机会 - 已破位等反包】共 {len(potential)} 只")
    print("=" * 70)
    for r in potential[:20]:
        print(f"  {r['symbol']} | 涨停日:{r['limit_date']} | 涨停最低:{r['limit_low']:.2f} | 今日涨幅:{r['today_gain']}% | 量比:{r['vol_ratio']} | 收盘:{r['close']:.2f}")
    if len(potential) > 20:
        print(f"  ... 还有 {len(potential) - 20} 只")
    
    print("\n" + "=" * 70)
    print(f"【观察中 - 有涨停等破位】共 {len(watching)} 只")
    print("=" * 70)
    for r in watching[:20]:
        print(f"  {r['symbol']} | 涨停日:{r['limit_date']} | 涨停最低:{r['limit_low']:.2f} | 距破位:{r['distance']}% | 收盘:{r['close']:.2f}")
    if len(watching) > 20:
        print(f"  ... 还有 {len(watching) - 20} 只")
    
    # 保存结果
    import json
    result_data = {
        'scan_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'triggered': triggered,
        'potential': potential,
        'watching': watching
    }
    filename = f"scan_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(result_data, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存到: {filename}")
    
    # 导出Word
    word_file = export_to_word(result_data)
    print(f"Word报告已保存到: {word_file}")
    
    return result_data

def export_to_word(result_data: dict) -> str:
    """导出扫描结果到Word文档"""
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    
    doc = Document()
    
    title = doc.add_heading('涨停破位洗盘战法 - 扫描报告', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    doc.add_paragraph(f"扫描时间: {result_data['scan_time']}")
    doc.add_paragraph()
    
    # 已触发
    doc.add_heading('一、已触发 - 今日可抄底', level=1)
    triggered = result_data['triggered']
    if triggered:
        table = doc.add_table(rows=1, cols=6)
        table.style = 'Table Grid'
        hdr = table.rows[0].cells
        hdr[0].text = '代码'
        hdr[1].text = '涨停日'
        hdr[2].text = '涨停最低价'
        hdr[3].text = '今日涨幅'
        hdr[4].text = '量比'
        hdr[5].text = '收盘价'
        
        for r in triggered:
            row = table.add_row().cells
            row[0].text = r['symbol']
            row[1].text = r['limit_date']
            row[2].text = f"{r['limit_low']:.2f}"
            row[3].text = f"{r['today_gain']}%"
            row[4].text = str(r.get('vol_ratio', 'N/A'))
            row[5].text = f"{r['close']:.2f}"
    else:
        doc.add_paragraph('暂无符合条件的股票')
    
    doc.add_paragraph()
    
    # 潜在机会
    doc.add_heading('二、潜在机会 - 已破位等反包', level=1)
    potential = result_data['potential']
    if potential:
        table = doc.add_table(rows=1, cols=6)
        table.style = 'Table Grid'
        hdr = table.rows[0].cells
        hdr[0].text = '代码'
        hdr[1].text = '涨停日'
        hdr[2].text = '涨停最低价'
        hdr[3].text = '今日涨幅'
        hdr[4].text = '量比'
        hdr[5].text = '收盘价'
        
        for r in potential[:30]:
            row = table.add_row().cells
            row[0].text = r['symbol']
            row[1].text = r['limit_date']
            row[2].text = f"{r['limit_low']:.2f}"
            row[3].text = f"{r['today_gain']}%"
            row[4].text = str(r.get('vol_ratio', 'N/A'))
            row[5].text = f"{r['close']:.2f}"
        
        if len(potential) > 30:
            doc.add_paragraph(f'... 还有 {len(potential) - 30} 只')
    else:
        doc.add_paragraph('暂无符合条件的股票')
    
    doc.add_paragraph()
    
    # 观察中
    doc.add_heading('三、观察中 - 有涨停等破位', level=1)
    watching = result_data['watching']
    if watching:
        table = doc.add_table(rows=1, cols=5)
        table.style = 'Table Grid'
        hdr = table.rows[0].cells
        hdr[0].text = '代码'
        hdr[1].text = '涨停日'
        hdr[2].text = '涨停最低价'
        hdr[3].text = '距破位'
        hdr[4].text = '收盘价'
        
        for r in watching[:30]:
            row = table.add_row().cells
            row[0].text = r['symbol']
            row[1].text = r['limit_date']
            row[2].text = f"{r['limit_low']:.2f}"
            row[3].text = f"{r['distance']}%"
            row[4].text = f"{r['close']:.2f}"
        
        if len(watching) > 30:
            doc.add_paragraph(f'... 还有 {len(watching) - 30} 只')
    else:
        doc.add_paragraph('暂无符合条件的股票')
    
    doc.add_paragraph()
    doc.add_heading('战法说明', level=1)
    doc.add_paragraph('涨停破位洗盘战法条件：')
    doc.add_paragraph('1. 近20天内有非一字涨停板（有换手的涨停）')
    doc.add_paragraph('2. 后续回调跌破涨停板最低价（破位洗盘）')
    doc.add_paragraph('3. 今日大阳线反包（涨幅>3%，收盘站回涨停最低价之上）')
    doc.add_paragraph('4. 低位启动（涨停前10日涨幅<20%）')
    doc.add_paragraph('5. 涨停后直接回调（不能先创新高再破位）')
    doc.add_paragraph('6. 近5日均量相比前20日均量放大1.5倍以上')
    
    filename = f"扫描报告_{datetime.now().strftime('%Y%m%d')}.docx"
    doc.save(filename)
    return filename

if __name__ == "__main__":
    run_scan(max_workers=10)  # 10个线程并发
