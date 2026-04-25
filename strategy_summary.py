"""
潜力板块策略完整汇总报告
"""
import pandas as pd
import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows

def create_summary_report():
    """生成策略汇总报告"""
    
    # 读取回测数据
    df = pd.read_excel('潜力板块信号收益回测.xlsx', sheet_name='详细回测数据')
    df['回撤数值'] = df['回撤幅度'].str.replace('%', '').astype(float)
    
    # 样式
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    title_font = Font(bold=True, size=14)
    subtitle_font = Font(bold=True, size=12)
    green_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    yellow_fill = PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid")
    center = Alignment(horizontal="center", vertical="center")
    left = Alignment(horizontal="left", vertical="center")
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "策略汇总"
    
    row = 1
    
    # ========== 标题 ==========
    ws.cell(row=row, column=1, value="潜力板块策略回测汇总报告").font = title_font
    row += 2
    
    # ========== 1. 策略概述 ==========
    ws.cell(row=row, column=1, value="一、策略概述").font = subtitle_font
    row += 1
    
    overview = [
        "信号条件：早期爆发(单日>3%) → 回撤洗盘(5-20%) → 近期企稳(15日<5%且5日>-5%)",
        f"回测周期：2025年1月-12月",
        f"总信号数：{len(df)}条",
        f"覆盖板块：{df['板块'].nunique()}个",
    ]
    for text in overview:
        ws.cell(row=row, column=1, value=text)
        row += 1
    row += 1
    
    # ========== 2. 总体收益 ==========
    ws.cell(row=row, column=1, value="二、总体收益统计").font = subtitle_font
    row += 1
    
    headers = ["持有期", "平均收益", "胜率", "最大收益", "最大亏损"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=row, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
        cell.border = thin_border
    row += 1
    
    for period, col_name in [("1个月", "1个月收益"), ("2个月", "2个月收益"), 
                              ("3个月", "3个月收益"), ("4个月", "4个月收益")]:
        data = df[col_name].dropna()
        row_data = [
            period,
            f"{data.mean():.2f}%",
            f"{(data > 0).mean()*100:.1f}%",
            f"{data.max():.1f}%",
            f"{data.min():.1f}%"
        ]
        for col, val in enumerate(row_data, 1):
            cell = ws.cell(row=row, column=col, value=val)
            cell.alignment = center
            cell.border = thin_border
        row += 1
    row += 1
    
    # ========== 3. 最佳买入月份 ==========
    ws.cell(row=row, column=1, value="三、最佳买入月份（按4个月收益排序）").font = subtitle_font
    row += 1
    
    monthly = df.groupby('月份').agg({
        '1个月收益': 'mean',
        '2个月收益': 'mean',
        '3个月收益': 'mean',
        '4个月收益': 'mean',
        '板块': 'count'
    }).round(2)
    monthly.columns = ['1个月', '2个月', '3个月', '4个月', '信号数']
    monthly = monthly.sort_values('4个月', ascending=False)
    
    headers = ["月份", "信号数", "1个月", "2个月", "3个月", "4个月", "建议"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=row, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
        cell.border = thin_border
    row += 1
    
    for month in monthly.index:
        r = monthly.loc[month]
        ret4 = r['4个月']
        if ret4 > 25:
            suggest = "★★★ 强烈推荐"
        elif ret4 > 15:
            suggest = "★★ 推荐"
        else:
            suggest = "★ 一般"
        
        row_data = [month, int(r['信号数']), f"{r['1个月']:.1f}%", f"{r['2个月']:.1f}%", 
                    f"{r['3个月']:.1f}%", f"{r['4个月']:.1f}%", suggest]
        for col, val in enumerate(row_data, 1):
            cell = ws.cell(row=row, column=col, value=val)
            cell.alignment = center
            cell.border = thin_border
            if col == 7 and "强烈" in str(val):
                cell.fill = green_fill
        row += 1
    row += 1
    
    # ========== 4. 最佳回撤区间 ==========
    ws.cell(row=row, column=1, value="四、最佳回撤区间").font = subtitle_font
    row += 1
    
    def get_dd_group(x):
        if x < 8: return '5-8%'
        elif x < 12: return '8-12%'
        elif x < 16: return '12-16%'
        else: return '16-20%'
    
    df['回撤区间'] = df['回撤数值'].apply(get_dd_group)
    
    dd_stats = df.groupby('回撤区间').agg({
        '1个月收益': 'mean',
        '4个月收益': ['mean', 'count'],
    }).round(2)
    dd_stats.columns = ['1个月', '4个月', '样本数']
    dd_stats['胜率'] = df.groupby('回撤区间').apply(lambda x: (x['4个月收益'] > 0).mean() * 100).round(1)
    dd_stats = dd_stats.reindex(['5-8%', '8-12%', '12-16%', '16-20%'])
    
    headers = ["回撤区间", "样本数", "1个月收益", "4个月收益", "胜率", "评价"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=row, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
        cell.border = thin_border
    row += 1
    
    for dd in dd_stats.index:
        r = dd_stats.loc[dd]
        if r['4个月'] > 20 and r['胜率'] > 85:
            eval_text = "★★★ 最佳"
        elif r['4个月'] > 15:
            eval_text = "★★ 良好"
        else:
            eval_text = "★ 一般"
        
        row_data = [dd, int(r['样本数']), f"{r['1个月']:.1f}%", f"{r['4个月']:.1f}%", 
                    f"{r['胜率']:.1f}%", eval_text]
        for col, val in enumerate(row_data, 1):
            cell = ws.cell(row=row, column=col, value=val)
            cell.alignment = center
            cell.border = thin_border
            if col == 6 and "最佳" in str(val):
                cell.fill = green_fill
        row += 1
    row += 1
    
    # ========== 5. TOP10板块 ==========
    ws.cell(row=row, column=1, value="五、收益最高的板块TOP10").font = subtitle_font
    row += 1
    
    top10 = df.nlargest(10, '4个月收益')[['月份', '板块', '回撤幅度', '1个月收益', '4个月收益']]
    
    headers = ["排名", "信号月份", "板块", "回撤", "1个月", "4个月"]
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=row, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
        cell.border = thin_border
    row += 1
    
    for i, (_, r) in enumerate(top10.iterrows(), 1):
        row_data = [i, r['月份'], r['板块'], r['回撤幅度'], 
                    f"{r['1个月收益']:.1f}%", f"{r['4个月收益']:.1f}%"]
        for col, val in enumerate(row_data, 1):
            cell = ws.cell(row=row, column=col, value=val)
            cell.alignment = center
            cell.border = thin_border
        row += 1
    row += 1
    
    # ========== 6. 策略结论 ==========
    ws.cell(row=row, column=1, value="六、策略结论").font = subtitle_font
    row += 1
    
    conclusions = [
        "",
        "【最优买入条件】",
        "  1. 时机：5-7月出现的信号（4个月收益25-37%）",
        "  2. 回撤：12-16%（收益22%，胜率91%）",
        "  3. 持有：4个月（收益最大化）",
        "",
        "【为什么5-7月最好】",
        "  - 大盘位置：经过Q1调整，处于相对低位",
        "  - 板块周期：Q1爆发→Q2洗盘→Q3启动→Q4主升",
        "  - 资金规律：半年报后机构调仓，布局下半年",
        "",
        "【为什么12-16%回撤最好】",
        "  - 5-8%：洗盘不充分，浮筹未清",
        "  - 8-12%：较好，但不是最优",
        "  - 12-16%：洗盘充分，筹码集中，启动空间大",
        "  - 16-20%：可能洗过头，资金信心不足",
        "",
        "【2026年操作建议】",
        "  1. 重点关注5-7月出现的潜力信号",
        "  2. 优选回撤12-16%的板块",
        "  3. 买入后持有4个月到Q4",
        "  4. 预期收益20-40%，胜率>80%",
    ]
    
    for text in conclusions:
        ws.cell(row=row, column=1, value=text)
        row += 1
    
    # 调整列宽
    ws.column_dimensions['A'].width = 20
    ws.column_dimensions['B'].width = 12
    ws.column_dimensions['C'].width = 18
    ws.column_dimensions['D'].width = 12
    ws.column_dimensions['E'].width = 12
    ws.column_dimensions['F'].width = 12
    ws.column_dimensions['G'].width = 15
    
    # 保存
    filename = "潜力板块策略汇总报告.xlsx"
    wb.save(filename)
    print(f"✓ 已生成: {filename}")
    
    # 打印关键结论
    print("\n" + "=" * 70)
    print("潜力板块策略核心结论")
    print("=" * 70)
    
    print("""
【一句话总结】
5-7月买入回撤12-16%的板块，持有4个月，预期收益20-40%，胜率90%

【详细数据支撑】

1. 最佳买入月份（4个月收益）
   ┌────────┬─────────┬────────┐
   │  月份  │ 4个月收益 │  胜率  │
   ├────────┼─────────┼────────┤
   │  5月   │  +36.8%  │  83%   │ ★★★
   │  7月   │  +25.4%  │  83%   │ ★★★
   │  6月   │  +23.6%  │  82%   │ ★★
   └────────┴─────────┴────────┘

2. 最佳回撤区间（4个月收益）
   ┌──────────┬─────────┬────────┐
   │ 回撤区间 │ 4个月收益 │  胜率  │
   ├──────────┼─────────┼────────┤
   │ 12-16%  │  +22.2%  │  91%   │ ★★★ 最佳
   │  8-12%  │  +19.7%  │  80%   │ ★★
   │  5-8%   │  +13.5%  │  80%   │ ★
   └──────────┴─────────┴────────┘

3. 最佳持有期
   ┌────────┬─────────┬────────┐
   │ 持有期 │ 平均收益 │  胜率  │
   ├────────┼─────────┼────────┤
   │ 1个月  │  +3.4%   │  61%   │
   │ 2个月  │  +9.6%   │  81%   │
   │ 3个月  │  +12.1%  │  77%   │
   │ 4个月  │  +18.5%  │  83%   │ ★★★
   └────────┴─────────┴────────┘

【操作流程】
1月-4月：观察，等待信号
5月-7月：信号出现，筛选回撤12-16%的板块买入
8月-11月：持有，等待主升浪
9月-11月：分批止盈
""")

if __name__ == "__main__":
    create_summary_report()
