"""
扫描潜力板块中有脉冲拉伸特征的个股
脉冲拉伸：在分时图上短时间内快速拉升（5-15分钟内涨幅超过2-3%）
"""
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime
from data_fetcher import get_intraday_data

def get_potential_sectors(top_n=10):
    """获取潜力板块 - 使用预定义的6个潜力板块"""
    # 预定义的潜力板块（早期爆发后回撤企稳的板块）
    potential_sectors = [
        'GDR',           # 9月+21% → 11月-15% → 企稳
        '电子后视镜',     # 9月+12% → 10月-6% → 企稳
        '举牌',          # 稳步上涨，12月回调
        '乳业',          # 11月爆发后回撤，近期企稳
        '3D摄像头',      # 9月爆发后持续洗盘
        '低碳冶金',      # 洗盘充分，总涨幅小
    ]
    return potential_sectors

def get_sector_stocks(sector_name):
    """获取板块成分股"""
    try:
        df = ak.stock_board_concept_cons_em(symbol=sector_name)
        # 只取主板股票
        df = df[df['代码'].str.match(r'^(60|00)')]
        return df[['代码', '名称', '最新价', '涨跌幅', '换手率']].to_dict('records')
    except:
        return []

def detect_pulse(df, min_pulse_pct=2.0, max_bars=3):
    """
    检测脉冲拉伸
    
    Args:
        df: 分时数据（5分钟K线）
        min_pulse_pct: 最小脉冲涨幅（%）
        max_bars: 脉冲发生的最大K线数（3根=15分钟）
    
    Returns:
        list: 检测到的脉冲列表
    """
    if df is None or len(df) < 10:
        return []
    
    pulses = []
    
    # 计算每根K线的涨幅
    df = df.copy()
    df['涨幅'] = (df['收盘'] - df['开盘']) / df['开盘'] * 100
    
    # 滑动窗口检测脉冲
    for i in range(max_bars, len(df)):
        # 计算过去max_bars根K线的累计涨幅
        window = df.iloc[i-max_bars:i+1]
        window_change = (window['收盘'].iloc[-1] - window['开盘'].iloc[0]) / window['开盘'].iloc[0] * 100
        
        # 检测脉冲条件
        if window_change >= min_pulse_pct:
            # 检查是否是快速拉升（不是缓慢上涨）
            max_single_bar = window['涨幅'].max()
            if max_single_bar >= min_pulse_pct * 0.5:  # 至少有一根K线涨幅较大
                pulse_time = window['时间'].iloc[-1] if '时间' in window.columns else str(i)
                pulses.append({
                    '时间': pulse_time,
                    '涨幅': round(window_change, 2),
                    '最大单K涨幅': round(max_single_bar, 2),
                    '起始价': round(window['开盘'].iloc[0], 2),
                    '最高价': round(window['最高'].max(), 2)
                })
    
    # 去重（相邻的脉冲合并）
    if len(pulses) > 1:
        unique_pulses = [pulses[0]]
        for p in pulses[1:]:
            # 如果时间间隔超过30分钟，认为是新脉冲
            if isinstance(p['时间'], str) and isinstance(unique_pulses[-1]['时间'], str):
                try:
                    t1 = pd.to_datetime(unique_pulses[-1]['时间'])
                    t2 = pd.to_datetime(p['时间'])
                    if (t2 - t1).total_seconds() > 1800:  # 30分钟
                        unique_pulses.append(p)
                except:
                    unique_pulses.append(p)
        pulses = unique_pulses
    
    return pulses

def scan_pulse_stocks(sectors=None, days=30):
    """
    扫描潜力板块中有脉冲拉伸的个股
    
    Args:
        sectors: 板块列表，None则自动获取潜力板块
        days: 分时数据天数
    """
    print("=" * 70)
    print("脉冲拉伸扫描 - 寻找30天内有快速拉升特征的个股")
    print("=" * 70)
    print(f"\n扫描条件：")
    print(f"  - 15分钟内涨幅 >= 2%")
    print(f"  - 单根5分钟K线涨幅 >= 1%")
    print(f"  - 回看天数: {days}天")
    
    if sectors is None:
        sectors = get_potential_sectors(top_n=8)
    
    if not sectors:
        print("未获取到板块")
        return []
    
    print(f"\n将扫描 {len(sectors)} 个板块: {', '.join(sectors)}")
    
    all_results = []
    
    for sector in sectors:
        print(f"\n{'='*50}")
        print(f"【{sector}】")
        print("=" * 50)
        
        stocks = get_sector_stocks(sector)
        if not stocks:
            print("  获取成分股失败")
            continue
        
        print(f"  成分股数量: {len(stocks)}")
        
        # 只分析前20只
        stocks = stocks[:20]
        
        for stock in stocks:
            code = stock['代码']
            name = stock['名称']
            print(f"  分析 {code} {name}...", end=" ")
            
            try:
                df = get_intraday_data(code, days=days)
                if df is None or len(df) < 50:
                    print("数据不足")
                    continue
                
                pulses = detect_pulse(df, min_pulse_pct=2.0, max_bars=3)
                
                if pulses:
                    print(f"✓ 发现 {len(pulses)} 次脉冲")
                    all_results.append({
                        '板块': sector,
                        '代码': code,
                        '名称': name,
                        '当日涨幅': stock['涨跌幅'],
                        '换手率': stock['换手率'],
                        '脉冲次数': len(pulses),
                        '脉冲详情': pulses
                    })
                else:
                    print("×")
            except Exception as e:
                print(f"错误: {e}")
    
    # 按脉冲次数排序
    all_results = sorted(all_results, key=lambda x: x['脉冲次数'], reverse=True)
    
    return all_results

def print_results(results):
    """打印结果"""
    if not results:
        print("\n未发现有脉冲拉伸特征的个股")
        return
    
    print("\n" + "=" * 70)
    print(f"发现 {len(results)} 只有脉冲拉伸特征的个股")
    print("=" * 70)
    
    for i, r in enumerate(results, 1):
        print(f"\n【{i}. {r['代码']} {r['名称']}】 - {r['板块']}")
        print(f"  当日涨幅: {r['当日涨幅']}% | 换手率: {r['换手率']}%")
        print(f"  30天内脉冲次数: {r['脉冲次数']}次")
        
        # 显示最近3次脉冲
        recent_pulses = r['脉冲详情'][-3:]
        for p in recent_pulses:
            print(f"    - {p['时间']}: +{p['涨幅']}% (单K最大+{p['最大单K涨幅']}%)")
    
    print("\n" + "=" * 70)
    print("【分析说明】")
    print("=" * 70)
    print("脉冲拉伸说明有资金在试盘或吸筹")
    print("多次脉冲的个股值得重点关注")
    print("建议结合日K线形态和板块热度综合判断")

def export_to_excel(results, filename=None):
    """导出结果到Excel"""
    if not results:
        print("没有数据可导出")
        return
    
    from datetime import datetime
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    
    if filename is None:
        filename = f"脉冲拉伸扫描_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "脉冲拉伸个股"
    
    # 样式
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    center_align = Alignment(horizontal="center", vertical="center")
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    # 表头
    headers = ["排名", "代码", "名称", "板块", "脉冲次数", "最近脉冲时间", "最近脉冲涨幅", "脉冲详情"]
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border
    
    # 去重（同一只股票可能出现在多个板块）
    seen = set()
    unique_results = []
    for r in results:
        key = r['代码']
        if key not in seen:
            seen.add(key)
            unique_results.append(r)
    
    # 数据行
    for row_idx, r in enumerate(unique_results, 2):
        # 最近一次脉冲
        last_pulse = r['脉冲详情'][-1] if r['脉冲详情'] else {}
        pulse_detail = "; ".join([f"{p['时间']}: +{p['涨幅']}%" for p in r['脉冲详情'][-3:]])
        
        row_data = [
            row_idx - 1,
            r['代码'],
            r['名称'],
            r['板块'],
            r['脉冲次数'],
            str(last_pulse.get('时间', '')),
            f"+{last_pulse.get('涨幅', 0)}%",
            pulse_detail
        ]
        
        for col, value in enumerate(row_data, 1):
            cell = ws.cell(row=row_idx, column=col, value=value)
            cell.alignment = center_align if col <= 5 else Alignment(horizontal="left", vertical="center")
            cell.border = thin_border
    
    # 调整列宽
    ws.column_dimensions['A'].width = 6
    ws.column_dimensions['B'].width = 10
    ws.column_dimensions['C'].width = 12
    ws.column_dimensions['D'].width = 14
    ws.column_dimensions['E'].width = 10
    ws.column_dimensions['F'].width = 20
    ws.column_dimensions['G'].width = 12
    ws.column_dimensions['H'].width = 60
    
    # 添加板块汇总sheet
    ws2 = wb.create_sheet(title="板块汇总")
    
    # 统计各板块
    sector_stats = {}
    for r in unique_results:
        sector = r['板块']
        if sector not in sector_stats:
            sector_stats[sector] = {'count': 0, 'total_pulses': 0, 'stocks': []}
        sector_stats[sector]['count'] += 1
        sector_stats[sector]['total_pulses'] += r['脉冲次数']
        sector_stats[sector]['stocks'].append(f"{r['名称']}({r['脉冲次数']}次)")
    
    # 板块汇总表头
    headers2 = ["板块", "个股数量", "总脉冲次数", "平均脉冲", "主要个股"]
    for col, header in enumerate(headers2, 1):
        cell = ws2.cell(row=1, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center_align
        cell.border = thin_border
    
    # 板块数据
    row_idx = 2
    for sector, stats in sorted(sector_stats.items(), key=lambda x: x[1]['total_pulses'], reverse=True):
        avg_pulse = round(stats['total_pulses'] / stats['count'], 1)
        top_stocks = ", ".join(stats['stocks'][:5])
        
        row_data = [sector, stats['count'], stats['total_pulses'], avg_pulse, top_stocks]
        for col, value in enumerate(row_data, 1):
            cell = ws2.cell(row=row_idx, column=col, value=value)
            cell.alignment = center_align if col <= 4 else Alignment(horizontal="left", vertical="center")
            cell.border = thin_border
        row_idx += 1
    
    ws2.column_dimensions['A'].width = 14
    ws2.column_dimensions['B'].width = 10
    ws2.column_dimensions['C'].width = 12
    ws2.column_dimensions['D'].width = 10
    ws2.column_dimensions['E'].width = 50
    
    wb.save(filename)
    print(f"\n✓ 已导出到: {filename}")
    return filename

if __name__ == "__main__":
    results = scan_pulse_stocks(days=30)
    print_results(results)
    export_to_excel(results)
