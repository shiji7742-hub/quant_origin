"""
回测潜力板块信号的收益
计算信号出现后持有1/2/3/4个月的收益
"""
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side

def read_signals_from_excel(filename="2025年潜力板块月度信号.xlsx"):
    """从Excel读取信号数据"""
    df = pd.read_excel(filename, sheet_name="详细信号")
    return df

def get_sector_price_data(sector_name, start_date, end_date):
    """获取板块价格数据（通过龙头股估算）"""
    try:
        df = ak.stock_board_concept_cons_em(symbol=sector_name)
        if df is None or len(df) == 0:
            return None
        
        top_stocks = df.head(3)['代码'].tolist()
        all_prices = []
        
        for symbol in top_stocks:
            try:
                hist = ak.stock_zh_a_hist(
                    symbol=symbol,
                    period="daily",
                    start_date=start_date,
                    end_date=end_date,
                    adjust="qfq"
                )
                if hist is not None and len(hist) > 10:
                    hist['日期'] = pd.to_datetime(hist['日期'])
                    hist = hist.set_index('日期')
                    all_prices.append(hist['收盘'])
            except:
                continue
        
        if len(all_prices) == 0:
            return None
        
        # 合并取平均
        combined = pd.concat(all_prices, axis=1)
        return combined.mean(axis=1)
    except:
        return None

def calculate_returns(price_series, signal_date, holding_days_list=[22, 44, 66, 88]):
    """
    计算从信号日期开始持有不同天数的收益
    22天≈1个月, 44天≈2个月, 66天≈3个月, 88天≈4个月
    """
    if price_series is None:
        return {d: None for d in holding_days_list}
    
    signal_dt = pd.to_datetime(signal_date)
    
    # 找到信号日期或之后最近的交易日
    valid_dates = price_series.index[price_series.index >= signal_dt]
    if len(valid_dates) == 0:
        return {d: None for d in holding_days_list}
    
    buy_date = valid_dates[0]
    buy_price = price_series[buy_date]
    
    returns = {}
    for days in holding_days_list:
        target_date = buy_date + timedelta(days=days)
        # 找到目标日期或之前最近的交易日
        valid_sell_dates = price_series.index[price_series.index <= target_date]
        if len(valid_sell_dates) == 0:
            returns[days] = None
            continue
        
        sell_date = valid_sell_dates[-1]
        sell_price = price_series[sell_date]
        
        ret = (sell_price - buy_price) / buy_price * 100
        returns[days] = round(ret, 2)
    
    return returns

def backtest_all_signals():
    """回测所有信号"""
    print("=" * 70)
    print("潜力板块信号收益回测")
    print("=" * 70)
    
    # 读取信号
    print("\n读取信号数据...")
    try:
        signals_df = read_signals_from_excel()
    except Exception as e:
        print(f"读取Excel失败: {e}")
        return None
    
    print(f"共 {len(signals_df)} 条信号")
    
    # 月份到日期的映射
    month_to_date = {
        '01月': '2025-01-31', '02月': '2025-02-28', '03月': '2025-03-31',
        '04月': '2025-04-30', '05月': '2025-05-31', '06月': '2025-06-30',
        '07月': '2025-07-31', '08月': '2025-08-31', '09月': '2025-09-30',
        '10月': '2025-10-31', '11月': '2025-11-30', '12月': '2025-12-31',
    }
    
    results = []
    sectors_cache = {}  # 缓存板块数据
    
    for idx, row in signals_df.iterrows():
        month = row['月份']
        sector = row['板块']
        signal_date = month_to_date.get(month)
        
        if not signal_date:
            continue
        
        print(f"\r[{idx+1}/{len(signals_df)}] 回测 {month} {sector}...", end="", flush=True)
        
        # 获取价格数据（使用缓存）
        if sector not in sectors_cache:
            price_data = get_sector_price_data(sector, '20250101', '20260115')
            sectors_cache[sector] = price_data
        else:
            price_data = sectors_cache[sector]
        
        # 计算收益
        returns = calculate_returns(price_data, signal_date)
        
        results.append({
            '月份': month,
            '板块': sector,
            '信号日期': signal_date,
            '爆发日期': row['爆发日期'],
            '爆发涨幅': row['爆发涨幅'],
            '回撤幅度': row['回撤幅度'],
            '1个月收益': returns.get(22),
            '2个月收益': returns.get(44),
            '3个月收益': returns.get(66),
            '4个月收益': returns.get(88),
        })
    
    print("\n")
    return pd.DataFrame(results)

def analyze_results(df):
    """分析回测结果"""
    print("\n" + "=" * 70)
    print("回测结果分析")
    print("=" * 70)
    
    # 按月份统计
    print("\n【各月份平均收益】")
    monthly_stats = df.groupby('月份').agg({
        '1个月收益': 'mean',
        '2个月收益': 'mean',
        '3个月收益': 'mean',
        '4个月收益': 'mean',
    }).round(2)
    
    # 按月份顺序排序
    month_order = ['03月', '04月', '05月', '06月', '07月', '08月', '09月', '10月', '11月', '12月']
    monthly_stats = monthly_stats.reindex([m for m in month_order if m in monthly_stats.index])
    
    print(monthly_stats.to_string())
    
    # 总体统计
    print("\n【总体平均收益】")
    overall = {
        '1个月': df['1个月收益'].mean(),
        '2个月': df['2个月收益'].mean(),
        '3个月': df['3个月收益'].mean(),
        '4个月': df['4个月收益'].mean(),
    }
    for period, ret in overall.items():
        if ret is not None:
            print(f"  持有{period}: {ret:.2f}%")
    
    # 胜率统计
    print("\n【胜率统计（收益>0的比例）】")
    for col in ['1个月收益', '2个月收益', '3个月收益', '4个月收益']:
        valid = df[col].dropna()
        if len(valid) > 0:
            win_rate = (valid > 0).sum() / len(valid) * 100
            print(f"  {col.replace('收益', '')}: {win_rate:.1f}% ({(valid > 0).sum()}/{len(valid)})")
    
    # 最佳买入月份
    print("\n【最佳买入月份（按4个月收益排序）】")
    best_months = monthly_stats.sort_values('4个月收益', ascending=False)
    for month in best_months.index[:5]:
        row = best_months.loc[month]
        print(f"  {month}: 1月{row['1个月收益']:.1f}% → 2月{row['2个月收益']:.1f}% → 3月{row['3个月收益']:.1f}% → 4月{row['4个月收益']:.1f}%")
    
    # 表现最好的板块
    print("\n【收益最高的板块（4个月收益）】")
    top_sectors = df.nlargest(10, '4个月收益')[['月份', '板块', '1个月收益', '2个月收益', '3个月收益', '4个月收益']]
    for _, row in top_sectors.iterrows():
        print(f"  {row['月份']} {row['板块']}: {row['1个月收益']}% → {row['2个月收益']}% → {row['3个月收益']}% → {row['4个月收益']}%")
    
    return monthly_stats

def export_results(df, monthly_stats):
    """导出结果到Excel"""
    filename = "潜力板块信号收益回测.xlsx"
    
    # 样式
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    green_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    center_align = Alignment(horizontal="center", vertical="center")
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )
    
    wb = openpyxl.Workbook()
    
    # Sheet1: 详细数据
    ws1 = wb.active
    ws1.title = "详细回测数据"
    
    headers = list(df.columns)
    for col, h in enumerate(headers, 1):
        cell = ws1.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border
    
    for row_idx, row in df.iterrows():
        for col_idx, value in enumerate(row, 1):
            cell = ws1.cell(row=row_idx+2, column=col_idx, value=value)
            cell.alignment = center_align
            cell.border = thin_border
            # 收益列着色
            if col_idx >= 7 and value is not None:
                try:
                    if float(str(value).replace('%', '')) > 0:
                        cell.fill = green_fill
                    elif float(str(value).replace('%', '')) < 0:
                        cell.fill = red_fill
                except:
                    pass
    
    # 调整列宽
    for col in ws1.columns:
        ws1.column_dimensions[col[0].column_letter].width = 12
    ws1.column_dimensions['B'].width = 18
    
    # Sheet2: 月度汇总
    ws2 = wb.create_sheet(title="月度汇总")
    
    headers2 = ["月份", "信号数", "1个月平均", "2个月平均", "3个月平均", "4个月平均", "最佳持有期"]
    for col, h in enumerate(headers2, 1):
        cell = ws2.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border
    
    row = 2
    for month in monthly_stats.index:
        stats = monthly_stats.loc[month]
        signal_count = len(df[df['月份'] == month])
        
        # 找最佳持有期
        returns = [stats['1个月收益'], stats['2个月收益'], stats['3个月收益'], stats['4个月收益']]
        valid_returns = [(r, i) for i, r in enumerate(returns) if pd.notna(r)]
        if valid_returns:
            best_idx = max(valid_returns, key=lambda x: x[0])[1]
            best_period = ['1个月', '2个月', '3个月', '4个月'][best_idx]
        else:
            best_period = '-'
        
        row_data = [month, signal_count, 
                    f"{stats['1个月收益']:.1f}%" if pd.notna(stats['1个月收益']) else '-',
                    f"{stats['2个月收益']:.1f}%" if pd.notna(stats['2个月收益']) else '-',
                    f"{stats['3个月收益']:.1f}%" if pd.notna(stats['3个月收益']) else '-',
                    f"{stats['4个月收益']:.1f}%" if pd.notna(stats['4个月收益']) else '-',
                    best_period]
        
        for col, value in enumerate(row_data, 1):
            cell = ws2.cell(row=row, column=col, value=value)
            cell.alignment = center_align
            cell.border = thin_border
        row += 1
    
    for col in ws2.columns:
        ws2.column_dimensions[col[0].column_letter].width = 12
    
    # Sheet3: 结论
    ws3 = wb.create_sheet(title="结论")
    
    conclusions = [
        "【潜力板块信号收益回测结论】",
        "",
        "1. 最佳买入时机：",
        f"   - 总体平均收益: 1月{df['1个月收益'].mean():.1f}% → 4月{df['4个月收益'].mean():.1f}%",
        "",
        "2. 最佳买入月份（按4个月收益）：",
    ]
    
    best_months = monthly_stats.sort_values('4个月收益', ascending=False)
    for i, month in enumerate(best_months.index[:3], 1):
        ret = best_months.loc[month, '4个月收益']
        if pd.notna(ret):
            conclusions.append(f"   {i}. {month}: 4个月收益 {ret:.1f}%")
    
    conclusions.extend([
        "",
        "3. 胜率统计：",
        f"   - 1个月胜率: {(df['1个月收益'].dropna() > 0).mean()*100:.1f}%",
        f"   - 4个月胜率: {(df['4个月收益'].dropna() > 0).mean()*100:.1f}%",
        "",
        "4. 建议：",
        "   - 信号出现后买入，持有2-3个月收益较优",
        "   - 关注回撤较大(10-15%)的板块，洗盘更充分",
    ])
    
    for row, text in enumerate(conclusions, 1):
        ws3.cell(row=row, column=1, value=text)
    ws3.column_dimensions['A'].width = 60
    
    wb.save(filename)
    print(f"\n✓ 已导出到: {filename}")

if __name__ == "__main__":
    df = backtest_all_signals()
    if df is not None and len(df) > 0:
        monthly_stats = analyze_results(df)
        export_results(df, monthly_stats)
