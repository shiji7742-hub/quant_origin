"""
板块策略月度报告
统计2025年每个月检测到的板块信号
"""
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
import json

def get_market_data(start_date='20250101', end_date='20260115'):
    """获取大盘数据"""
    try:
        df = ak.stock_zh_index_daily(symbol="sh000001")
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        df = df[(df.index >= start_date) & (df.index <= end_date)]
        df['ma20'] = df['close'].rolling(20).mean()
        df['above_ma20'] = df['close'] > df['ma20']
        return df
    except Exception as e:
        print(f"获取大盘数据失败: {e}")
        return None

def is_market_bullish(check_date, market_data):
    """检查大盘是否在20日均线上方"""
    if market_data is None:
        return True
    try:
        idx = market_data.index.get_indexer([check_date], method='ffill')[0]
        if idx >= 0 and idx < len(market_data):
            return market_data.iloc[idx]['above_ma20']
    except:
        pass
    return True

def get_sector_list():
    """获取所有板块列表"""
    try:
        df = ak.stock_board_concept_name_em()
        return df['板块名称'].tolist()
    except:
        return []

def get_sector_history(sector_name, start_date='20240701', end_date='20260115'):
    """获取板块历史数据（通过龙头股估算）"""
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
                if hist is not None and len(hist) > 50:
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

def detect_signal_at_date(daily_returns, check_idx, lookback=30, market_data=None):
    """
    在指定日期检测信号
    
    条件：
    1. 30天前有过爆发（单日>3%）
    2. 爆发后没有走出主升（累计<爆发的3倍）
    3. 近15日表现弱（累计<5%）
    4. 大盘在20日均线上方
    5. 回撤在5-12%之间
    """
    if check_idx < lookback + 15:
        return False, None
    
    data = daily_returns.iloc[check_idx - lookback - 15:check_idx]
    
    if len(data) < lookback:
        return False, None
    
    check_date = daily_returns.index[check_idx]
    
    # 大盘过滤
    if market_data is not None and not is_market_bullish(check_date, market_data):
        return False, None
    
    old_period = data.iloc[:-15]
    recent_period = data.iloc[-15:]
    
    # 找爆发
    surge_days = old_period[old_period > 3.0]
    
    if len(surge_days) == 0:
        return False, None
    
    max_surge_value = surge_days.max()
    max_surge_idx = surge_days.idxmax()
    surge_count = len(surge_days)
    
    # 爆发后数据
    after_surge = data[data.index >= max_surge_idx]
    
    if len(after_surge) < 10:
        return False, None
    
    # 计算指标
    cumulative_after = after_surge.sum()
    recent_sum = recent_period.sum()
    
    cumsum = after_surge.cumsum()
    max_gain = cumsum.max()
    current_gain = cumsum.iloc[-1]
    drawdown = max_gain - current_gain
    
    # 回撤在5-12%之间
    if drawdown < 5 or drawdown > 12:
        return False, None
    
    # 没主升 + 近期弱
    no_main_rise = (cumulative_after < max_surge_value * 3)
    recent_weak = recent_sum < 5
    
    if no_main_rise and recent_weak:
        return True, {
            'surge_date': max_surge_idx.strftime('%Y-%m-%d'),
            'surge_value': round(max_surge_value, 2),
            'surge_count': surge_count,
            'drawdown': round(drawdown, 2),
            'recent_15d': round(recent_sum, 2)
        }
    
    return False, None

def calculate_future_return(daily_returns, start_idx, days=30):
    """计算未来N天收益"""
    end_idx = start_idx + days
    if end_idx <= len(daily_returns):
        return daily_returns.iloc[start_idx:end_idx].sum()
    return None

def scan_sector_monthly(sector_name, market_data, year=2025):
    """扫描单个板块在指定年份每个月的信号"""
    data = get_sector_history(sector_name, f'{year-1}0701', '20260115')
    
    if data is None or len(data) < 100:
        return {}
    
    monthly_signals = {}
    
    # 遍历每个月
    for month in range(1, 13):
        month_str = f'{year}-{month:02d}'
        
        # 找这个月的所有交易日
        month_dates = data[(data.index.year == year) & (data.index.month == month)]
        
        if len(month_dates) == 0:
            continue
        
        # 在每个月的中间检测一次信号（避免重复）
        mid_idx = len(month_dates) // 2
        check_date = month_dates.index[mid_idx]
        
        # 找到在完整数据中的索引
        try:
            full_idx = data.index.get_loc(check_date)
        except:
            continue
        
        is_signal, details = detect_signal_at_date(data, full_idx, lookback=30, market_data=market_data)
        
        if is_signal:
            # 计算未来30天收益
            future_30d = calculate_future_return(data, full_idx, 30)
            
            monthly_signals[month_str] = {
                'signal_date': check_date.strftime('%Y-%m-%d'),
                **details,
                'future_30d': round(future_30d, 2) if future_30d else None
            }
    
    return monthly_signals

def generate_monthly_report(num_sectors=100, year=2025):
    """生成月度报告"""
    print("=" * 70)
    print(f"板块策略月度报告 - {year}年")
    print("=" * 70)
    print("\n策略条件：")
    print("  1. 30天前有过爆发（单日>3%）")
    print("  2. 爆发后没有走出主升浪")
    print("  3. 近15日表现弱（<5%）")
    print("  4. 高点回撤5-12%")
    print("  5. 大盘在20日均线上方")
    
    print("\n获取大盘数据...")
    market_data = get_market_data(f'{year-1}0701', '20260115')
    
    print("获取板块列表...")
    all_sectors = get_sector_list()
    
    if not all_sectors:
        print("获取板块列表失败")
        return None
    
    print(f"共 {len(all_sectors)} 个板块，将扫描 {min(num_sectors, len(all_sectors))} 个")
    
    import random
    random.shuffle(all_sectors)
    sectors_to_scan = all_sectors[:num_sectors]
    
    # 按月份统计
    monthly_results = defaultdict(list)
    all_signals = []
    
    for i, sector_name in enumerate(sectors_to_scan):
        print(f"[{i+1}/{len(sectors_to_scan)}] 扫描 {sector_name}...", end=" ")
        
        signals = scan_sector_monthly(sector_name, market_data, year)
        
        if signals:
            print(f"发现 {len(signals)} 个月有信号")
            for month, details in signals.items():
                monthly_results[month].append({
                    'sector': sector_name,
                    **details
                })
                all_signals.append({
                    'month': month,
                    'sector': sector_name,
                    **details
                })
        else:
            print("无信号")
    
    # 打印结果
    print("\n" + "=" * 70)
    print(f"{year}年月度信号统计")
    print("=" * 70)
    
    for month in range(1, 13):
        month_str = f'{year}-{month:02d}'
        signals = monthly_results.get(month_str, [])
        
        print(f"\n【{year}年{month}月】检测到 {len(signals)} 个板块")
        
        if signals:
            # 按未来收益排序
            signals_sorted = sorted(signals, key=lambda x: x.get('future_30d') or -999, reverse=True)
            
            for s in signals_sorted[:10]:  # 最多显示10个
                future = s.get('future_30d')
                future_str = f"30日后: {future:+.1f}%" if future else "30日后: N/A"
                print(f"  - {s['sector']}: 爆发+{s['surge_value']}%, 回撤{s['drawdown']}%, {future_str}")
            
            if len(signals) > 10:
                print(f"  ... 还有 {len(signals) - 10} 个板块")
    
    # 统计总结
    print("\n" + "=" * 70)
    print("统计总结")
    print("=" * 70)
    
    # 计算每月信号数
    print("\n【每月信号数量】")
    for month in range(1, 13):
        month_str = f'{year}-{month:02d}'
        count = len(monthly_results.get(month_str, []))
        bar = "█" * (count // 2) if count > 0 else ""
        print(f"  {month:2d}月: {count:3d} 个 {bar}")
    
    # 计算胜率
    if all_signals:
        valid_signals = [s for s in all_signals if s.get('future_30d') is not None]
        if valid_signals:
            win_count = sum(1 for s in valid_signals if s['future_30d'] > 0)
            win_rate = win_count / len(valid_signals) * 100
            avg_return = sum(s['future_30d'] for s in valid_signals) / len(valid_signals)
            
            print(f"\n【整体表现】")
            print(f"  有效信号数: {len(valid_signals)}")
            print(f"  30日胜率: {win_rate:.1f}%")
            print(f"  30日平均收益: {avg_return:.2f}%")
    
    # 保存结果
    output = {
        'year': year,
        'scan_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_sectors_scanned': len(sectors_to_scan),
        'monthly_signals': dict(monthly_results),
        'all_signals': all_signals
    }
    
    output_file = f"monthly_report_{year}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n详细结果已保存到: {output_file}")
    
    # 导出Word报告
    word_file = export_monthly_to_word(monthly_results, all_signals, year)
    print(f"Word报告已保存到: {word_file}")
    
    return monthly_results



def export_monthly_to_word(monthly_results, all_signals, year):
    """导出月度报告到Word"""
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    
    doc = Document()
    
    # 标题
    title = doc.add_heading(f'板块策略月度报告 - {year}年', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    doc.add_paragraph(f'报告生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    doc.add_paragraph()
    
    # 策略说明
    doc.add_heading('一、策略说明', level=1)
    doc.add_paragraph('本报告统计了板块异动策略在每个月检测到的信号。')
    doc.add_paragraph()
    
    doc.add_heading('策略条件：', level=2)
    conditions = [
        '30天前有过爆发（单日涨幅>3%）',
        '爆发后没有走出主升浪',
        '近15日表现弱（累计涨幅<5%）',
        '高点回撤在5-12%之间',
        '大盘在20日均线上方'
    ]
    for c in conditions:
        doc.add_paragraph(c, style='List Bullet')
    
    doc.add_paragraph()
    
    # 月度统计
    doc.add_heading('二、月度信号统计', level=1)
    
    for month in range(1, 13):
        month_str = f'{year}-{month:02d}'
        signals = monthly_results.get(month_str, [])
        
        doc.add_heading(f'{year}年{month}月 - 检测到 {len(signals)} 个板块', level=2)
        
        if signals:
            # 创建表格
            table = doc.add_table(rows=1, cols=5)
            table.style = 'Table Grid'
            
            # 表头
            header_cells = table.rows[0].cells
            headers = ['板块名称', '信号日期', '爆发涨幅', '回撤', '30日后收益']
            for i, h in enumerate(headers):
                header_cells[i].text = h
                header_cells[i].paragraphs[0].runs[0].bold = True
            
            # 按未来收益排序
            signals_sorted = sorted(signals, key=lambda x: x.get('future_30d') or -999, reverse=True)
            
            for s in signals_sorted[:15]:  # 最多15个
                row = table.add_row().cells
                row[0].text = s['sector']
                row[1].text = s['signal_date']
                row[2].text = f"+{s['surge_value']}%"
                row[3].text = f"{s['drawdown']}%"
                future = s.get('future_30d')
                row[4].text = f"{future:+.1f}%" if future else "N/A"
            
            if len(signals) > 15:
                doc.add_paragraph(f'... 还有 {len(signals) - 15} 个板块未列出')
        else:
            doc.add_paragraph('本月未检测到符合条件的信号')
        
        doc.add_paragraph()
    
    # 统计总结
    doc.add_heading('三、统计总结', level=1)
    
    # 每月信号数量表
    doc.add_heading('每月信号数量：', level=2)
    table2 = doc.add_table(rows=1, cols=13)
    table2.style = 'Table Grid'
    
    header2 = table2.rows[0].cells
    for i in range(12):
        header2[i].text = f'{i+1}月'
        header2[i].paragraphs[0].runs[0].bold = True
    header2[12].text = '合计'
    header2[12].paragraphs[0].runs[0].bold = True
    
    row2 = table2.add_row().cells
    total = 0
    for i in range(12):
        month_str = f'{year}-{i+1:02d}'
        count = len(monthly_results.get(month_str, []))
        row2[i].text = str(count)
        total += count
    row2[12].text = str(total)
    
    doc.add_paragraph()
    
    # 整体表现
    if all_signals:
        valid_signals = [s for s in all_signals if s.get('future_30d') is not None]
        if valid_signals:
            win_count = sum(1 for s in valid_signals if s['future_30d'] > 0)
            win_rate = win_count / len(valid_signals) * 100
            avg_return = sum(s['future_30d'] for s in valid_signals) / len(valid_signals)
            
            doc.add_heading('整体表现：', level=2)
            doc.add_paragraph(f'有效信号数：{len(valid_signals)}')
            doc.add_paragraph(f'30日胜率：{win_rate:.1f}%')
            doc.add_paragraph(f'30日平均收益：{avg_return:.2f}%')
    
    doc.add_paragraph()
    
    # 最佳信号
    doc.add_heading('四、最佳信号（30日收益最高）', level=1)
    
    valid_signals = [s for s in all_signals if s.get('future_30d') is not None]
    if valid_signals:
        top_signals = sorted(valid_signals, key=lambda x: x['future_30d'], reverse=True)[:10]
        
        table3 = doc.add_table(rows=1, cols=6)
        table3.style = 'Table Grid'
        
        header3 = table3.rows[0].cells
        for i, h in enumerate(['月份', '板块', '信号日期', '爆发涨幅', '回撤', '30日收益']):
            header3[i].text = h
            header3[i].paragraphs[0].runs[0].bold = True
        
        for s in top_signals:
            row = table3.add_row().cells
            row[0].text = s['month']
            row[1].text = s['sector']
            row[2].text = s['signal_date']
            row[3].text = f"+{s['surge_value']}%"
            row[4].text = f"{s['drawdown']}%"
            row[5].text = f"{s['future_30d']:+.1f}%"
    
    doc.add_paragraph()
    
    # 结论
    doc.add_heading('五、结论', level=1)
    
    # 找出信号最多的月份
    max_month = max(range(1, 13), key=lambda m: len(monthly_results.get(f'{year}-{m:02d}', [])))
    max_count = len(monthly_results.get(f'{year}-{max_month:02d}', []))
    
    conclusion = f'''
本报告统计了{year}年板块策略的月度信号情况：

1. 信号分布：{max_month}月信号最多（{max_count}个），说明该月市场处于板块轮动活跃期。

2. 策略特点：该策略主要捕捉"爆发后回撤洗盘"的板块，这类板块往往在洗盘结束后有较好的上涨空间。

3. 使用建议：
   - 关注信号较多的月份，说明市场机会较多
   - 优先选择回撤充分（8-12%）的板块
   - 结合大盘环境综合判断
'''
    doc.add_paragraph(conclusion)
    
    # 保存
    filename = f"月度报告_{year}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    doc.save(filename)
    
    return filename


if __name__ == "__main__":
    # 生成2025年月度报告
    generate_monthly_report(num_sectors=80, year=2025)
