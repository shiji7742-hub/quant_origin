"""
回测：潜力板块 + 涨停破位洗盘 组合策略
验证策略有效性
"""
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from strategies import strategy_limit_up_washout

def get_sector_stocks(sector_name):
    """获取板块成分股"""
    try:
        df = ak.stock_board_concept_cons_em(symbol=sector_name)
        if df is None:
            return []
        df = df[df['代码'].str.match(r'^(60|00)')]
        df = df[~df['名称'].str.contains('ST')]
        return df[['代码', '名称']].to_dict('records')
    except:
        return []

def get_stock_data(symbol, start_date, end_date):
    """获取股票历史数据"""
    try:
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", 
                                start_date=start_date, end_date=end_date, adjust="qfq")
        if df is not None and len(df) > 0:
            df['日期'] = pd.to_datetime(df['日期'])
        return df
    except:
        return None

def find_signals_in_history(df, relaxed=True):
    """在历史数据中找出所有触发信号的日期"""
    if df is None or len(df) < 30:
        return []
    
    signals = []
    df = df.reset_index(drop=True)
    
    # 从第30天开始扫描，确保有足够历史数据
    for i in range(30, len(df)):
        # 取到当天为止的数据
        df_slice = df.iloc[:i+1].copy()
        result = strategy_limit_up_washout(df_slice, relaxed=relaxed)
        
        if result['触发']:
            signal_date = df.iloc[i]['日期']
            signal_price = df.iloc[i]['收盘']
            signals.append({
                'date': signal_date,
                'price': signal_price,
                'idx': i,
                'detail': result['说明']
            })
    
    return signals

def calculate_returns(df, signal_idx, holding_days=[5, 10, 20, 40]):
    """计算信号后的收益"""
    signal_price = df.iloc[signal_idx]['收盘']
    returns = {}
    
    for days in holding_days:
        target_idx = signal_idx + days
        if target_idx < len(df):
            future_price = df.iloc[target_idx]['收盘']
            ret = (future_price - signal_price) / signal_price * 100
            returns[f'{days}日'] = ret
        else:
            returns[f'{days}日'] = None
    
    # 计算最大回撤和最大收益
    if signal_idx + 1 < len(df):
        future_data = df.iloc[signal_idx+1:min(signal_idx+41, len(df))]
        if len(future_data) > 0:
            max_price = future_data['最高'].max()
            min_price = future_data['最低'].min()
            returns['最大收益'] = (max_price - signal_price) / signal_price * 100
            returns['最大回撤'] = (min_price - signal_price) / signal_price * 100
    
    return returns

def backtest_combined_strategy():
    """回测组合策略"""
    print("=" * 70)
    print("回测：潜力板块 + 涨停破位洗盘 组合策略")
    print("=" * 70)
    
    # 潜力板块
    sectors = ['GDR', '电子后视镜', '举牌', '乳业', '3D摄像头', '低碳冶金']
    
    # 回测时间范围：2025年全年
    start_date = "20250101"
    end_date = "20260115"
    
    print(f"\n回测区间: {start_date} - {end_date}")
    print(f"潜力板块: {', '.join(sectors)}")
    
    all_signals = []
    
    for sector in sectors:
        print(f"\n{'='*50}")
        print(f"【{sector}】")
        print("=" * 50)
        
        stocks = get_sector_stocks(sector)
        if not stocks:
            print("  获取成分股失败")
            continue
        
        print(f"  成分股数量: {len(stocks)}")
        
        for stock in stocks:
            code = stock['代码']
            name = stock['名称']
            
            df = get_stock_data(code, start_date, end_date)
            if df is None or len(df) < 50:
                continue
            
            signals = find_signals_in_history(df, relaxed=True)
            
            for sig in signals:
                returns = calculate_returns(df, sig['idx'])
                
                signal_info = {
                    '板块': sector,
                    '代码': code,
                    '名称': name,
                    '信号日期': sig['date'].strftime('%Y-%m-%d'),
                    '买入价': sig['price'],
                    **returns
                }
                all_signals.append(signal_info)
                print(f"  ✓ {code} {name} {sig['date'].strftime('%Y-%m-%d')} "
                      f"5日:{returns.get('5日', 'N/A'):.1f}%" if returns.get('5日') else "")
    
    return all_signals

def analyze_results(signals):
    """分析回测结果"""
    if not signals:
        print("\n没有找到任何信号")
        return None
    
    df = pd.DataFrame(signals)
    
    print("\n" + "=" * 70)
    print("回测结果分析")
    print("=" * 70)
    
    print(f"\n总信号数: {len(df)}")
    
    # 按持有期统计
    periods = ['5日', '10日', '20日', '40日']
    print("\n【不同持有期收益统计】")
    print("-" * 60)
    
    stats = []
    for period in periods:
        if period in df.columns:
            valid = df[df[period].notna()][period]
            if len(valid) > 0:
                win_rate = (valid > 0).sum() / len(valid) * 100
                avg_ret = valid.mean()
                median_ret = valid.median()
                max_ret = valid.max()
                min_ret = valid.min()
                
                print(f"\n{period}:")
                print(f"  样本数: {len(valid)}")
                print(f"  胜率: {win_rate:.1f}%")
                print(f"  平均收益: {avg_ret:.2f}%")
                print(f"  中位数收益: {median_ret:.2f}%")
                print(f"  最大收益: {max_ret:.2f}%")
                print(f"  最大亏损: {min_ret:.2f}%")
                
                stats.append({
                    '持有期': period,
                    '样本数': len(valid),
                    '胜率': f"{win_rate:.1f}%",
                    '平均收益': f"{avg_ret:.2f}%",
                    '中位数': f"{median_ret:.2f}%",
                    '最大收益': f"{max_ret:.2f}%",
                    '最大亏损': f"{min_ret:.2f}%"
                })
    
    # 最大收益和回撤
    if '最大收益' in df.columns and '最大回撤' in df.columns:
        valid_max = df[df['最大收益'].notna()]['最大收益']
        valid_dd = df[df['最大回撤'].notna()]['最大回撤']
        
        print(f"\n【40日内最大收益/回撤】")
        print(f"  平均最大收益: {valid_max.mean():.2f}%")
        print(f"  平均最大回撤: {valid_dd.mean():.2f}%")
        print(f"  盈亏比: {abs(valid_max.mean() / valid_dd.mean()):.2f}")
    
    # 按板块统计
    print("\n【按板块统计】")
    print("-" * 60)
    
    sector_stats = []
    for sector in df['板块'].unique():
        sector_df = df[df['板块'] == sector]
        if '10日' in sector_df.columns:
            valid = sector_df[sector_df['10日'].notna()]['10日']
            if len(valid) > 0:
                win_rate = (valid > 0).sum() / len(valid) * 100
                avg_ret = valid.mean()
                print(f"\n{sector}:")
                print(f"  信号数: {len(sector_df)}, 10日胜率: {win_rate:.1f}%, 平均收益: {avg_ret:.2f}%")
                
                sector_stats.append({
                    '板块': sector,
                    '信号数': len(sector_df),
                    '10日胜率': f"{win_rate:.1f}%",
                    '10日平均收益': f"{avg_ret:.2f}%"
                })
    
    # 按月份统计
    print("\n【按月份统计】")
    print("-" * 60)
    
    df['月份'] = pd.to_datetime(df['信号日期']).dt.to_period('M')
    month_stats = []
    
    for month in sorted(df['月份'].unique()):
        month_df = df[df['月份'] == month]
        if '10日' in month_df.columns:
            valid = month_df[month_df['10日'].notna()]['10日']
            if len(valid) > 0:
                win_rate = (valid > 0).sum() / len(valid) * 100
                avg_ret = valid.mean()
                print(f"  {month}: 信号{len(month_df)}个, 胜率{win_rate:.1f}%, 平均{avg_ret:.2f}%")
                
                month_stats.append({
                    '月份': str(month),
                    '信号数': len(month_df),
                    '10日胜率': f"{win_rate:.1f}%",
                    '10日平均收益': f"{avg_ret:.2f}%"
                })
    
    return {
        'signals': df,
        'period_stats': stats,
        'sector_stats': sector_stats,
        'month_stats': month_stats
    }

def export_backtest_results(signals, results):
    """导出回测结果到Excel"""
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    
    filename = f"组合策略回测_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    wb = openpyxl.Workbook()
    
    # 样式
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    green_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    center = Alignment(horizontal="center", vertical="center")
    border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )
    
    # Sheet1: 所有信号明细
    ws1 = wb.active
    ws1.title = "信号明细"
    
    df = pd.DataFrame(signals)
    headers = ['板块', '代码', '名称', '信号日期', '买入价', '5日', '10日', '20日', '40日', '最大收益', '最大回撤']
    
    for col, h in enumerate(headers, 1):
        cell = ws1.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = center
        cell.border = border
    
    for row_idx, sig in enumerate(signals, 2):
        for col, h in enumerate(headers, 1):
            val = sig.get(h, '')
            if isinstance(val, float):
                val = f"{val:.2f}%"
            cell = ws1.cell(row=row_idx, column=col, value=val)
            cell.alignment = center
            cell.border = border
            
            # 收益着色
            if h in ['5日', '10日', '20日', '40日', '最大收益']:
                try:
                    num_val = sig.get(h, 0)
                    if num_val and num_val > 0:
                        cell.fill = green_fill
                    elif num_val and num_val < 0:
                        cell.fill = red_fill
                except:
                    pass
    
    # Sheet2: 统计汇总
    ws2 = wb.create_sheet(title="统计汇总")
    
    # 持有期统计
    ws2.cell(row=1, column=1, value="【不同持有期收益统计】").font = Font(bold=True)
    if results and 'period_stats' in results:
        row = 3
        for col, h in enumerate(['持有期', '样本数', '胜率', '平均收益', '中位数', '最大收益', '最大亏损'], 1):
            cell = ws2.cell(row=row, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border
        
        for stat in results['period_stats']:
            row += 1
            for col, h in enumerate(['持有期', '样本数', '胜率', '平均收益', '中位数', '最大收益', '最大亏损'], 1):
                cell = ws2.cell(row=row, column=col, value=stat.get(h, ''))
                cell.border = border
    
    # 板块统计
    if results and 'sector_stats' in results:
        row += 3
        ws2.cell(row=row, column=1, value="【按板块统计】").font = Font(bold=True)
        row += 2
        for col, h in enumerate(['板块', '信号数', '10日胜率', '10日平均收益'], 1):
            cell = ws2.cell(row=row, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border
        
        for stat in results['sector_stats']:
            row += 1
            for col, h in enumerate(['板块', '信号数', '10日胜率', '10日平均收益'], 1):
                cell = ws2.cell(row=row, column=col, value=stat.get(h, ''))
                cell.border = border
    
    # 月份统计
    if results and 'month_stats' in results:
        row += 3
        ws2.cell(row=row, column=1, value="【按月份统计】").font = Font(bold=True)
        row += 2
        for col, h in enumerate(['月份', '信号数', '10日胜率', '10日平均收益'], 1):
            cell = ws2.cell(row=row, column=col, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border
        
        for stat in results['month_stats']:
            row += 1
            for col, h in enumerate(['月份', '信号数', '10日胜率', '10日平均收益'], 1):
                cell = ws2.cell(row=row, column=col, value=stat.get(h, ''))
                cell.border = border
    
    # 调整列宽
    for ws in [ws1, ws2]:
        for col in range(1, 12):
            ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 12
    
    wb.save(filename)
    print(f"\n✓ 回测结果已导出: {filename}")

def print_conclusion(results):
    """打印结论"""
    print("\n" + "=" * 70)
    print("【策略有效性结论】")
    print("=" * 70)
    
    if not results or 'period_stats' not in results:
        print("数据不足，无法得出结论")
        return
    
    # 提取关键指标
    stats = {s['持有期']: s for s in results['period_stats']}
    
    print("""
根据回测数据分析：

1. 短期表现（5-10日）：
""")
    if '5日' in stats:
        print(f"   - 5日胜率: {stats['5日']['胜率']}, 平均收益: {stats['5日']['平均收益']}")
    if '10日' in stats:
        print(f"   - 10日胜率: {stats['10日']['胜率']}, 平均收益: {stats['10日']['平均收益']}")
    
    print("""
2. 中期表现（20-40日）：
""")
    if '20日' in stats:
        print(f"   - 20日胜率: {stats['20日']['胜率']}, 平均收益: {stats['20日']['平均收益']}")
    if '40日' in stats:
        print(f"   - 40日胜率: {stats['40日']['胜率']}, 平均收益: {stats['40日']['平均收益']}")
    
    # 判断策略有效性
    try:
        win_rate_10 = float(stats.get('10日', {}).get('胜率', '0%').replace('%', ''))
        avg_ret_10 = float(stats.get('10日', {}).get('平均收益', '0%').replace('%', ''))
        
        print("\n3. 策略评价：")
        if win_rate_10 >= 60 and avg_ret_10 >= 3:
            print("   ✓ 策略有效！胜率和收益都达到较好水平")
            print("   建议：可以作为选股参考，配合仓位管理使用")
        elif win_rate_10 >= 50 and avg_ret_10 >= 0:
            print("   ~ 策略一般，有一定参考价值")
            print("   建议：需要配合其他指标筛选，控制仓位")
        else:
            print("   ✗ 策略效果不佳")
            print("   建议：需要优化策略参数或增加筛选条件")
    except:
        pass

if __name__ == "__main__":
    signals = backtest_combined_strategy()
    results = analyze_results(signals)
    export_backtest_results(signals, results)
    print_conclusion(results)
