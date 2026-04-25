"""
回测V2：潜力板块 + 涨停破位洗盘 + 大盘位置过滤
优化版本：
1. 扩大板块范围（不限于6个潜力板块）
2. 加入大盘位置过滤（低位买入效果更好）
3. 分析不同市场环境下的表现
"""
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from strategies import strategy_limit_up_washout

def get_index_data(start_date, end_date):
    """获取上证指数数据"""
    try:
        df = ak.stock_zh_index_daily(symbol="sh000001")
        df['date'] = pd.to_datetime(df['date'])
        df = df[(df['date'] >= start_date) & (df['date'] <= end_date)]
        return df
    except:
        return None

def get_market_position(index_df, date):
    """计算某日大盘在年内的位置（0-100%）"""
    if index_df is None:
        return 50
    
    # 取该日期前一年的数据
    year_start = date - timedelta(days=365)
    year_data = index_df[(index_df['date'] >= year_start) & (index_df['date'] <= date)]
    
    if len(year_data) < 20:
        return 50
    
    current = year_data.iloc[-1]['close']
    year_low = year_data['low'].min()
    year_high = year_data['high'].max()
    
    if year_high == year_low:
        return 50
    
    position = (current - year_low) / (year_high - year_low) * 100
    return position

def get_all_concept_sectors():
    """获取所有概念板块"""
    try:
        df = ak.stock_board_concept_name_em()
        return df['板块名称'].tolist()[:100]  # 取前100个热门板块
    except:
        return []

def get_sector_stocks(sector_name):
    """获取板块成分股"""
    try:
        df = ak.stock_board_concept_cons_em(symbol=sector_name)
        if df is None:
            return []
        df = df[df['代码'].str.match(r'^(60|00)')]
        df = df[~df['名称'].str.contains('ST')]
        return df[['代码', '名称']].head(20).to_dict('records')  # 每板块最多20只
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
    
    for i in range(30, len(df)):
        df_slice = df.iloc[:i+1].copy()
        result = strategy_limit_up_washout(df_slice, relaxed=relaxed)
        
        if result['触发']:
            signal_date = df.iloc[i]['日期']
            signal_price = df.iloc[i]['收盘']
            signals.append({
                'date': signal_date,
                'price': signal_price,
                'idx': i
            })
    
    return signals

def calculate_returns(df, signal_idx, holding_days=[5, 10, 20]):
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
    
    # 最大收益和回撤
    if signal_idx + 1 < len(df):
        future_data = df.iloc[signal_idx+1:min(signal_idx+21, len(df))]
        if len(future_data) > 0:
            max_price = future_data['最高'].max()
            min_price = future_data['最低'].min()
            returns['最大收益'] = (max_price - signal_price) / signal_price * 100
            returns['最大回撤'] = (min_price - signal_price) / signal_price * 100
    
    return returns

def backtest_with_market_filter():
    """带大盘位置过滤的回测"""
    print("=" * 70)
    print("回测V2：涨停破位洗盘 + 大盘位置过滤")
    print("=" * 70)
    
    start_date = "20250101"
    end_date = "20260115"
    
    # 获取大盘数据
    print("\n获取大盘数据...")
    index_df = get_index_data(start_date, end_date)
    
    # 选择测试板块（热门+潜力）
    test_sectors = [
        # 原潜力板块
        'GDR', '电子后视镜', '举牌', '乳业', '3D摄像头', '低碳冶金',
        # 扩展板块
        '人工智能', '芯片', '新能源汽车', '光伏', '储能', '机器人',
        '消费电子', '医药', '白酒', '银行'
    ]
    
    print(f"\n回测区间: {start_date} - {end_date}")
    print(f"测试板块: {len(test_sectors)}个")
    
    all_signals = []
    scanned_stocks = set()  # 避免重复扫描
    
    for sector in test_sectors:
        print(f"\n扫描【{sector}】...", end=" ")
        
        stocks = get_sector_stocks(sector)
        if not stocks:
            print("获取失败")
            continue
        
        sector_signals = 0
        for stock in stocks:
            code = stock['代码']
            name = stock['名称']
            
            if code in scanned_stocks:
                continue
            scanned_stocks.add(code)
            
            df = get_stock_data(code, start_date, end_date)
            if df is None or len(df) < 50:
                continue
            
            signals = find_signals_in_history(df, relaxed=True)
            
            for sig in signals:
                # 计算大盘位置
                market_pos = get_market_position(index_df, sig['date'])
                returns = calculate_returns(df, sig['idx'])
                
                signal_info = {
                    '板块': sector,
                    '代码': code,
                    '名称': name,
                    '信号日期': sig['date'].strftime('%Y-%m-%d'),
                    '买入价': sig['price'],
                    '大盘位置': market_pos,
                    **returns
                }
                all_signals.append(signal_info)
                sector_signals += 1
        
        print(f"找到{sector_signals}个信号")
    
    return all_signals

def analyze_by_market_position(signals):
    """按大盘位置分析"""
    if not signals:
        print("\n没有找到任何信号")
        return
    
    df = pd.DataFrame(signals)
    
    print("\n" + "=" * 70)
    print("按大盘位置分析")
    print("=" * 70)
    
    # 分组：低位(0-30%), 中位(30-60%), 高位(60-100%)
    df['市场阶段'] = pd.cut(df['大盘位置'], 
                          bins=[0, 30, 60, 100], 
                          labels=['低位(0-30%)', '中位(30-60%)', '高位(60-100%)'])
    
    print("\n【不同大盘位置下的策略表现】")
    print("-" * 60)
    
    position_stats = []
    for stage in ['低位(0-30%)', '中位(30-60%)', '高位(60-100%)']:
        stage_df = df[df['市场阶段'] == stage]
        if len(stage_df) == 0:
            continue
        
        valid_10 = stage_df[stage_df['10日'].notna()]['10日']
        if len(valid_10) > 0:
            win_rate = (valid_10 > 0).sum() / len(valid_10) * 100
            avg_ret = valid_10.mean()
            
            print(f"\n{stage}:")
            print(f"  信号数: {len(stage_df)}")
            print(f"  10日胜率: {win_rate:.1f}%")
            print(f"  10日平均收益: {avg_ret:.2f}%")
            
            position_stats.append({
                '市场阶段': stage,
                '信号数': len(stage_df),
                '10日胜率': f"{win_rate:.1f}%",
                '10日平均收益': f"{avg_ret:.2f}%"
            })
    
    return df, position_stats

def analyze_overall(df):
    """整体分析"""
    print("\n" + "=" * 70)
    print("整体回测结果")
    print("=" * 70)
    
    print(f"\n总信号数: {len(df)}")
    
    periods = ['5日', '10日', '20日']
    stats = []
    
    for period in periods:
        if period in df.columns:
            valid = df[df[period].notna()][period]
            if len(valid) > 0:
                win_rate = (valid > 0).sum() / len(valid) * 100
                avg_ret = valid.mean()
                
                print(f"\n{period}: 样本{len(valid)}, 胜率{win_rate:.1f}%, 平均{avg_ret:.2f}%")
                
                stats.append({
                    '持有期': period,
                    '样本数': len(valid),
                    '胜率': f"{win_rate:.1f}%",
                    '平均收益': f"{avg_ret:.2f}%"
                })
    
    # 盈亏比
    if '最大收益' in df.columns and '最大回撤' in df.columns:
        valid_max = df[df['最大收益'].notna()]['最大收益']
        valid_dd = df[df['最大回撤'].notna()]['最大回撤']
        if len(valid_max) > 0 and valid_dd.mean() != 0:
            print(f"\n20日内平均最大收益: {valid_max.mean():.2f}%")
            print(f"20日内平均最大回撤: {valid_dd.mean():.2f}%")
            print(f"盈亏比: {abs(valid_max.mean() / valid_dd.mean()):.2f}")
    
    return stats

def export_results(signals, overall_stats, position_stats):
    """导出结果"""
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    
    filename = f"组合策略回测V2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    wb = openpyxl.Workbook()
    
    # 样式
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    green_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    red_fill = PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid")
    border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )
    
    # Sheet1: 信号明细
    ws1 = wb.active
    ws1.title = "信号明细"
    
    df = pd.DataFrame(signals)
    headers = ['板块', '代码', '名称', '信号日期', '大盘位置', '买入价', '5日', '10日', '20日', '最大收益', '最大回撤']
    
    for col, h in enumerate(headers, 1):
        cell = ws1.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = border
    
    for row_idx, sig in enumerate(signals, 2):
        for col, h in enumerate(headers, 1):
            val = sig.get(h, '')
            if h == '大盘位置' and isinstance(val, (int, float)):
                val = f"{val:.1f}%"
            elif isinstance(val, float):
                val = f"{val:.2f}%"
            cell = ws1.cell(row=row_idx, column=col, value=val)
            cell.border = border
            
            if h in ['5日', '10日', '20日', '最大收益']:
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
    
    row = 1
    ws2.cell(row=row, column=1, value="【整体统计】").font = Font(bold=True, size=12)
    row += 2
    
    for col, h in enumerate(['持有期', '样本数', '胜率', '平均收益'], 1):
        cell = ws2.cell(row=row, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = border
    
    for stat in overall_stats:
        row += 1
        for col, h in enumerate(['持有期', '样本数', '胜率', '平均收益'], 1):
            cell = ws2.cell(row=row, column=col, value=stat.get(h, ''))
            cell.border = border
    
    row += 3
    ws2.cell(row=row, column=1, value="【按大盘位置统计】").font = Font(bold=True, size=12)
    row += 2
    
    for col, h in enumerate(['市场阶段', '信号数', '10日胜率', '10日平均收益'], 1):
        cell = ws2.cell(row=row, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = border
    
    for stat in position_stats:
        row += 1
        for col, h in enumerate(['市场阶段', '信号数', '10日胜率', '10日平均收益'], 1):
            cell = ws2.cell(row=row, column=col, value=stat.get(h, ''))
            cell.border = border
    
    # 调整列宽
    for ws in [ws1, ws2]:
        for col in range(1, 12):
            ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 14
    
    wb.save(filename)
    print(f"\n✓ 已导出: {filename}")

def print_conclusion(overall_stats, position_stats):
    """打印结论"""
    print("\n" + "=" * 70)
    print("【策略有效性结论】")
    print("=" * 70)
    
    print("""
核心发现：
""")
    
    # 分析大盘位置影响
    if position_stats:
        for stat in position_stats:
            stage = stat['市场阶段']
            win_rate = stat['10日胜率']
            avg_ret = stat['10日平均收益']
            print(f"  {stage}: 胜率{win_rate}, 平均收益{avg_ret}")
    
    print("""
策略优化建议：
  1. 大盘低位(0-30%)时使用该策略效果最佳
  2. 大盘高位(60%+)时谨慎使用，可能胜率下降
  3. 配合板块强度筛选，优先选择近期有资金关注的板块
  4. 设置止损位：跌破涨停最低价5%止损
""")

if __name__ == "__main__":
    signals = backtest_with_market_filter()
    df, position_stats = analyze_by_market_position(signals)
    overall_stats = analyze_overall(df)
    export_results(signals, overall_stats, position_stats)
    print_conclusion(overall_stats, position_stats)
