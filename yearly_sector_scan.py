"""
回测2025年每个月能检测到潜力信号的板块
信号条件：早期爆发(>3%) → 回撤洗盘(5-15%) → 近期企稳
"""
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random

def get_all_sectors():
    """获取所有概念板块"""
    try:
        df = ak.stock_board_concept_name_em()
        return df['板块名称'].tolist()
    except:
        return []

def get_sector_history(sector_name, start_date, end_date):
    """获取板块历史数据"""
    try:
        df = ak.stock_board_concept_cons_em(symbol=sector_name)
        if df is None or len(df) == 0:
            return None
        
        top_stocks = df.head(3)['代码'].tolist()
        all_data = []
        
        for symbol in top_stocks:
            try:
                hist = ak.stock_zh_a_hist(
                    symbol=symbol, 
                    period="daily", 
                    start_date=start_date,
                    end_date=end_date,
                    adjust="qfq"
                )
                if hist is not None and len(hist) > 20:
                    hist['涨跌幅'] = hist['收盘'].pct_change() * 100
                    hist['日期'] = pd.to_datetime(hist['日期'])
                    all_data.append(hist[['日期', '涨跌幅']].set_index('日期'))
            except:
                continue
        
        if len(all_data) == 0:
            return None
        
        combined = pd.concat([d['涨跌幅'] for d in all_data], axis=1)
        return combined.mean(axis=1)
    except:
        return None

def detect_potential_signal(daily_returns, check_date):
    """
    检测潜力信号
    条件：
    1. 过去60天内有过爆发（单日>3%）
    2. 爆发后有明显回撤（5-15%）
    3. 近期表现弱但企稳（近15日累计<5%，近5日不大跌）
    """
    if daily_returns is None or len(daily_returns) < 40:
        return False, None
    
    # 截取到检测日期的数据
    daily_returns = daily_returns[daily_returns.index <= check_date].dropna()
    
    if len(daily_returns) < 40:
        return False, None
    
    # 分段
    old_period = daily_returns.iloc[:-15]
    recent_15d = daily_returns.iloc[-15:]
    recent_5d = daily_returns.iloc[-5:]
    
    # 找爆发
    surge_days = old_period[old_period > 3.0]
    if len(surge_days) == 0:
        return False, None
    
    max_surge_value = surge_days.max()
    max_surge_idx = surge_days.idxmax()
    
    # 爆发后数据
    after_surge = daily_returns[daily_returns.index >= max_surge_idx]
    if len(after_surge) < 10:
        return False, None
    
    # 计算回撤
    cumsum = after_surge.cumsum()
    max_gain = cumsum.max()
    current_gain = cumsum.iloc[-1]
    drawdown = max_gain - current_gain
    
    # 条件判断
    if drawdown < 5 or drawdown > 20:
        return False, None
    
    recent_15d_sum = recent_15d.sum()
    recent_5d_sum = recent_5d.sum()
    
    recent_weak = recent_15d_sum < 5
    not_crashing = recent_5d_sum > -5
    cumulative_after = after_surge.sum()
    no_main_rise = cumulative_after < max_surge_value * 3
    
    if no_main_rise and recent_weak and not_crashing:
        return True, {
            'surge_date': max_surge_idx.strftime('%Y-%m-%d'),
            'surge_value': round(max_surge_value, 2),
            'drawdown': round(drawdown, 2),
            'recent_15d': round(recent_15d_sum, 2)
        }
    
    return False, None

def scan_monthly_signals(year=2025, num_sectors=100):
    """扫描每个月的潜力板块信号"""
    print("=" * 70)
    print(f"{year}年每月潜力板块信号回测")
    print("=" * 70)
    
    # 获取板块列表
    print("\n获取板块列表...")
    all_sectors = get_all_sectors()
    if not all_sectors:
        print("获取板块失败")
        return {}
    
    # 随机选取板块
    random.shuffle(all_sectors)
    sectors_to_scan = all_sectors[:num_sectors]
    print(f"将扫描 {len(sectors_to_scan)} 个板块")
    
    # 定义每个月的检测日期（月末）
    months = [
        ('01月', '20250101', '20250131', '2025-01-31'),
        ('02月', '20250101', '20250228', '2025-02-28'),
        ('03月', '20250101', '20250331', '2025-03-31'),
        ('04月', '20250101', '20250430', '2025-04-30'),
        ('05月', '20250101', '20250531', '2025-05-31'),
        ('06月', '20250101', '20250630', '2025-06-30'),
        ('07月', '20250101', '20250731', '2025-07-31'),
        ('08月', '20250101', '20250831', '2025-08-31'),
        ('09月', '20250101', '20250930', '2025-09-30'),
        ('10月', '20250101', '20251031', '2025-10-31'),
        ('11月', '20250101', '20251130', '2025-11-30'),
        ('12月', '20250101', '20251231', '2025-12-31'),
    ]
    
    monthly_results = {m[0]: [] for m in months}
    
    # 扫描每个板块
    for i, sector in enumerate(sectors_to_scan):
        print(f"\r[{i+1}/{len(sectors_to_scan)}] 分析 {sector}...", end="", flush=True)
        
        # 获取全年数据
        data = get_sector_history(sector, '20250101', '20251231')
        if data is None:
            continue
        
        # 检测每个月
        for month_name, start, end, check_date in months:
            check_dt = pd.to_datetime(check_date)
            is_signal, details = detect_potential_signal(data, check_dt)
            
            if is_signal:
                monthly_results[month_name].append({
                    '板块': sector,
                    **details
                })
    
    print("\n")
    return monthly_results

def print_monthly_results(results):
    """打印月度结果"""
    print("\n" + "=" * 70)
    print("2025年每月检测到的潜力板块")
    print("=" * 70)
    
    for month, sectors in results.items():
        print(f"\n【{month}】检测到 {len(sectors)} 个板块")
        if sectors:
            # 按回撤排序
            sectors = sorted(sectors, key=lambda x: x['drawdown'], reverse=True)
            for s in sectors[:10]:  # 只显示前10个
                print(f"  - {s['板块']}: 爆发{s['surge_date']} +{s['surge_value']}%, 回撤{s['drawdown']}%")

def export_to_excel(results):
    """导出到Excel"""
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    
    filename = f"2025年潜力板块月度信号.xlsx"
    wb = openpyxl.Workbook()
    
    # 样式
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    center_align = Alignment(horizontal="center", vertical="center")
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )
    
    # 汇总sheet
    ws = wb.active
    ws.title = "月度汇总"
    
    headers = ["月份", "信号数量", "主要板块"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border
    
    row = 2
    for month, sectors in results.items():
        top_sectors = ", ".join([s['板块'] for s in sectors[:5]])
        ws.cell(row=row, column=1, value=month).border = thin_border
        ws.cell(row=row, column=2, value=len(sectors)).border = thin_border
        ws.cell(row=row, column=3, value=top_sectors).border = thin_border
        row += 1
    
    ws.column_dimensions['A'].width = 8
    ws.column_dimensions['B'].width = 10
    ws.column_dimensions['C'].width = 60
    
    # 详细sheet
    ws2 = wb.create_sheet(title="详细信号")
    headers2 = ["月份", "板块", "爆发日期", "爆发涨幅", "回撤幅度", "近15日涨幅"]
    for col, h in enumerate(headers2, 1):
        cell = ws2.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border
    
    row = 2
    for month, sectors in results.items():
        for s in sectors:
            ws2.cell(row=row, column=1, value=month).border = thin_border
            ws2.cell(row=row, column=2, value=s['板块']).border = thin_border
            ws2.cell(row=row, column=3, value=s['surge_date']).border = thin_border
            ws2.cell(row=row, column=4, value=f"+{s['surge_value']}%").border = thin_border
            ws2.cell(row=row, column=5, value=f"{s['drawdown']}%").border = thin_border
            ws2.cell(row=row, column=6, value=f"{s['recent_15d']}%").border = thin_border
            row += 1
    
    for col in ['A', 'B', 'C', 'D', 'E', 'F']:
        ws2.column_dimensions[col].width = 12
    ws2.column_dimensions['B'].width = 20
    
    wb.save(filename)
    print(f"\n✓ 已导出到: {filename}")

if __name__ == "__main__":
    results = scan_monthly_signals(year=2025, num_sectors=80)
    print_monthly_results(results)
    export_to_excel(results)
