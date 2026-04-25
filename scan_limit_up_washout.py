"""全市场扫描 - 涨停破位洗盘战法（多线程+宽松模式）"""
import akshare as ak
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from strategies import strategy_limit_up_washout
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
import time
import threading

# 全局变量控制宽松模式
RELAXED_MODE = True

def get_all_stocks():
    """获取所有A股主板股票（排除退市、停牌）"""
    print("获取A股列表...")
    df = ak.stock_zh_a_spot_em()
    # 只保留主板（60、00开头），排除ST
    df = df[df['代码'].str.match(r'^(60|00)')]
    df = df[~df['名称'].str.contains('ST')]
    # 排除退市股票（最新价为空或0）
    df = df[df['最新价'].notna() & (df['最新价'] > 0)]
    # 排除停牌股票（成交量为0）
    df = df[df['成交量'].notna() & (df['成交量'] > 0)]
    print(f"共 {len(df)} 只有效主板股票")
    return df[['代码', '名称', '最新价', '涨跌幅']].to_dict('records')

def check_single_stock(stock, relaxed=True):
    """检测单只股票，返回完全匹配或类似匹配"""
    symbol = stock['代码']
    name = stock['名称']
    try:
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
        if df is None or len(df) < 30:
            return None, None
        
        df = df.tail(70)  # 取最近70天数据（宽松模式搜索30天需要更多数据）
        
        # 检查数据是否是最近的（最后一条数据应该在最近5个交易日内）
        last_date = pd.to_datetime(df['日期'].iloc[-1])
        if (pd.Timestamp.now() - last_date).days > 7:
            return None, None  # 数据太旧，可能是退市股票
        
        result = strategy_limit_up_washout(df, relaxed=relaxed)
        
        stock_info = {
            '代码': symbol,
            '名称': name,
            '最新价': stock['最新价'],
            '涨跌幅': stock['涨跌幅'],
            '说明': result['说明'],
            '条件': result['条件']
        }
        
        if result['触发']:
            return stock_info, None
        
        # 检查是否是"类似"股票（满足部分条件）
        similar = check_similar_pattern(df, stock, relaxed)
        if similar:
            return None, similar
            
    except Exception as e:
        pass
    return None, None


def check_similar_pattern(df, stock, relaxed=True):
    """检查类似形态：涨停后回调，但还没完全破位或反包"""
    if len(df) < 20:
        return None
    
    df = df.copy().reset_index(drop=True)
    latest = df.iloc[-1]
    latest_idx = len(df) - 1
    
    search_days = 30 if relaxed else 20
    
    # 找涨停板
    limit_up_info = None
    for i in range(latest_idx - 3, max(latest_idx - search_days, 0), -1):
        row = df.iloc[i]
        prev_close = df.iloc[i-1]['收盘'] if i > 0 else row['开盘']
        gain = (row['收盘'] - prev_close) / prev_close * 100
        is_limit_up = gain >= 9.5
        is_not_yizi = row['开盘'] < row['收盘'] * 0.99
        
        if is_limit_up and is_not_yizi:
            limit_up_info = {
                'idx': i,
                'date': row.get('日期', f'第{i}天'),
                'low': row['最低'],
                'close': row['收盘']
            }
            break
    
    if not limit_up_info:
        return None
    
    # 检查两月涨幅
    if len(df) >= 40:
        price_40d_ago = df.iloc[-40]['收盘']
        gain_2month = (latest['收盘'] - price_40d_ago) / price_40d_ago * 100
        if gain_2month > 40:
            return None
    
    limit_low = limit_up_info['low']
    limit_close = limit_up_info['close']
    
    # 检查是否先创新高
    made_new_high = False
    for i in range(limit_up_info['idx'] + 1, latest_idx + 1):
        if df.iloc[i]['最高'] > limit_close * 1.08:
            made_new_high = True
            break
    
    if made_new_high:
        return None
    
    # 计算当前位置相对涨停板的情况
    distance_to_low = (latest['收盘'] - limit_low) / limit_low * 100
    today_gain = (latest['收盘'] - latest['开盘']) / latest['开盘'] * 100
    
    # 类似形态条件：
    # 1. 接近破位（距离涨停最低价在-5%到+10%之间）
    # 2. 今日有一定涨幅（>1%）或者在关键位置
    near_breakout = -5 < distance_to_low < 10
    has_momentum = today_gain > 1
    
    if near_breakout and has_momentum:
        status = "接近破位" if distance_to_low > 0 else "已破位待反包"
        return {
            '代码': stock['代码'],
            '名称': stock['名称'],
            '最新价': stock['最新价'],
            '涨跌幅': stock['涨跌幅'],
            '说明': f"[类似]涨停日:{limit_up_info['date']}, {status}",
            '条件': f"涨停最低价{limit_low:.2f}, 当前距离{distance_to_low:.1f}%, 今日涨{today_gain:.1f}%"
        }
    
    return None

# 进度计数器（线程安全）
class ProgressCounter:
    def __init__(self, total):
        self.completed = 0
        self.total = total
        self.lock = threading.Lock()
    
    def increment(self):
        with self.lock:
            self.completed += 1
            return self.completed

def scan_market(max_workers=20, relaxed=True):
    """多线程扫描全市场
    
    参数:
    - max_workers: 线程数，默认20（提高并发）
    - relaxed: 是否使用宽松条件，默认True
    """
    global RELAXED_MODE
    RELAXED_MODE = relaxed
    
    stocks = get_all_stocks()
    results = []
    similar_results = []  # 类似形态
    total = len(stocks)
    counter = ProgressCounter(total)
    
    mode_str = "宽松模式" if relaxed else "严格模式"
    print(f"\n开始扫描 [{mode_str}]，线程数: {max_workers}")
    if relaxed:
        print("宽松条件: 大阳线>2%, 量比>1.2, 搜索30天, 追高<8%, 两月涨幅<40%")
    print("=" * 50)
    
    start_time = time.time()
    results_lock = threading.Lock()
    
    def worker(stock):
        result, similar = check_single_stock(stock, relaxed=relaxed)
        completed = counter.increment()
        
        if result:
            with results_lock:
                results.append(result)
            print(f"[{completed}/{total}] ✓ 发现: {result['名称']}({result['代码']})")
        elif similar:
            with results_lock:
                similar_results.append(similar)
            print(f"[{completed}/{total}] ~ 类似: {similar['名称']}({similar['代码']})")
        
        if completed % 200 == 0:
            elapsed = time.time() - start_time
            speed = completed / elapsed if elapsed > 0 else 0
            eta = (total - completed) / speed if speed > 0 else 0
            print(f"[{completed}/{total}] 进度 {completed/total*100:.1f}%, 速度 {speed:.1f}只/秒, 预计剩余 {eta:.0f}秒")
        
        return result, similar
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(worker, stock) for stock in stocks]
        # 等待所有任务完成
        for future in as_completed(futures):
            pass
    
    elapsed = time.time() - start_time
    print("=" * 50)
    print(f"扫描完成! 耗时 {elapsed:.1f}秒")
    print(f"完全匹配: {len(results)} 只, 类似形态: {len(similar_results)} 只")
    
    return results, similar_results

def generate_word_report(results, similar_results=None, relaxed=True):
    """生成Word报告"""
    doc = Document()
    
    # 标题
    mode_str = "（宽松模式）" if relaxed else ""
    title = doc.add_heading(f'涨停破位洗盘战法扫描报告{mode_str}', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # 扫描时间
    doc.add_paragraph(f'扫描时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    doc.add_paragraph(f'完全匹配: {len(results)} 只')
    if similar_results:
        doc.add_paragraph(f'类似形态: {len(similar_results)} 只')
    if relaxed:
        doc.add_paragraph('筛选条件: 大阳线>2%, 量比>1.2, 搜索30天, 追高<8%, 两月涨幅<40%')
    doc.add_paragraph()
    
    # 完全匹配
    doc.add_heading('一、完全匹配', level=1)
    if not results:
        doc.add_paragraph('未发现完全符合条件的股票')
    else:
        table = doc.add_table(rows=1, cols=5)
        table.style = 'Table Grid'
        headers = ['代码', '名称', '最新价', '涨跌幅', '触发说明']
        for i, header in enumerate(headers):
            cell = table.rows[0].cells[i]
            cell.text = header
            cell.paragraphs[0].runs[0].bold = True
        for stock in results:
            row = table.add_row().cells
            row[0].text = stock['代码']
            row[1].text = stock['名称']
            row[2].text = f"{stock['最新价']:.2f}" if stock['最新价'] else '-'
            row[3].text = f"{stock['涨跌幅']:.2f}%" if stock['涨跌幅'] else '-'
            row[4].text = stock['说明']
    
    # 类似形态
    if similar_results:
        doc.add_paragraph()
        doc.add_heading('二、类似形态（待观察）', level=1)
        table2 = doc.add_table(rows=1, cols=5)
        table2.style = 'Table Grid'
        headers = ['代码', '名称', '最新价', '涨跌幅', '说明']
        for i, header in enumerate(headers):
            cell = table2.rows[0].cells[i]
            cell.text = header
            cell.paragraphs[0].runs[0].bold = True
        for stock in similar_results[:20]:  # 最多显示20只
            row = table2.add_row().cells
            row[0].text = stock['代码']
            row[1].text = stock['名称']
            row[2].text = f"{stock['最新价']:.2f}" if stock['最新价'] else '-'
            row[3].text = f"{stock['涨跌幅']:.2f}%" if stock['涨跌幅'] else '-'
            row[4].text = stock['说明']
        if len(similar_results) > 20:
            doc.add_paragraph(f'... 还有 {len(similar_results)-20} 只类似形态未显示')
    
    # 详细信息
    if results:
        doc.add_paragraph()
        doc.add_heading('详细条件', level=1)
        for stock in results:
            doc.add_heading(f"{stock['名称']}({stock['代码']})", level=2)
            doc.add_paragraph(f"条件: {stock['条件']}")
    
    # 保存
    filename = f"涨停破位洗盘_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    doc.save(filename)
    print(f"\n报告已保存: {filename}")
    return filename

if __name__ == "__main__":
    import sys
    
    # 默认宽松模式，可通过命令行参数 --strict 切换严格模式
    relaxed = "--strict" not in sys.argv
    workers = 20  # 默认20线程
    
    # 解析线程数参数
    for arg in sys.argv:
        if arg.startswith("--workers="):
            try:
                workers = int(arg.split("=")[1])
            except:
                pass
    
    results, similar_results = scan_market(max_workers=workers, relaxed=relaxed)
    generate_word_report(results, similar_results, relaxed=relaxed)
