"""
分析板块启动时的大牛股，回溯它们启动前的洗盘特征
目标：找出主力洗盘的共同规律
"""
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import time

print_lock = Lock()

def safe_print(msg):
    with print_lock:
        print(msg)

# 2025年各月热门板块及其启动时间
SECTOR_SURGE_PERIODS = {
    '存储芯片': {'start': '2025-01-02', 'peak': '2025-02-15'},
    'DeepSeek概念': {'start': '2025-01-20', 'peak': '2025-02-28'},
    '机器人执行器': {'start': '2025-02-01', 'peak': '2025-03-15'},
    '低空经济': {'start': '2025-03-01', 'peak': '2025-04-15'},
    '固态电池': {'start': '2025-04-01', 'peak': '2025-05-20'},
    '人工智能': {'start': '2025-05-15', 'peak': '2025-07-30'},
    '芯片': {'start': '2025-06-01', 'peak': '2025-08-15'},
    '消费电子': {'start': '2025-07-15', 'peak': '2025-09-30'},
    '医药': {'start': '2025-08-01', 'peak': '2025-10-15'},
    '光伏': {'start': '2025-10-01', 'peak': '2025-12-15'},
    '储能': {'start': '2025-11-01', 'peak': '2025-12-31'},
}

def get_sector_stocks(sector_name):
    """获取板块成分股"""
    try:
        df = ak.stock_board_concept_cons_em(symbol=sector_name)
        if df is None:
            return []
        df = df[df['代码'].str.match(r'^(60|00)')]
        df = df[~df['名称'].str.contains('ST')]
        return df[['代码', '名称']].head(30).to_dict('records')
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

def analyze_stock_performance(code, name, sector, surge_start, surge_peak):
    """分析个股在板块启动期的表现"""
    try:
        # 获取数据：启动前60天 到 高峰后30天
        data_start = (pd.to_datetime(surge_start) - timedelta(days=90)).strftime('%Y%m%d')
        data_end = (pd.to_datetime(surge_peak) + timedelta(days=30)).strftime('%Y%m%d')
        
        df = get_stock_data(code, data_start, data_end)
        if df is None or len(df) < 60:
            return None
        
        df = df.reset_index(drop=True)
        
        # 找到启动日和高峰日的索引
        surge_start_dt = pd.to_datetime(surge_start)
        surge_peak_dt = pd.to_datetime(surge_peak)
        
        start_idx = df[df['日期'] >= surge_start_dt].index[0] if len(df[df['日期'] >= surge_start_dt]) > 0 else None
        peak_idx = df[df['日期'] <= surge_peak_dt].index[-1] if len(df[df['日期'] <= surge_peak_dt]) > 0 else None
        
        if start_idx is None or peak_idx is None or start_idx >= peak_idx:
            return None
        
        # 计算启动期涨幅
        start_price = df.iloc[start_idx]['收盘']
        peak_price = df.iloc[start_idx:peak_idx+1]['最高'].max()
        surge_gain = (peak_price - start_price) / start_price * 100
        
        # 只分析涨幅超过30%的牛股
        if surge_gain < 30:
            return None
        
        # 分析启动前60天的洗盘特征
        pre_start_idx = max(0, start_idx - 60)
        pre_data = df.iloc[pre_start_idx:start_idx+1].copy()
        
        if len(pre_data) < 20:
            return None
        
        # 计算洗盘特征
        features = analyze_washout_features(pre_data, df, start_idx)
        
        return {
            '板块': sector,
            '代码': code,
            '名称': name,
            '启动日': surge_start,
            '启动价': round(start_price, 2),
            '最高价': round(peak_price, 2),
            '启动期涨幅': round(surge_gain, 1),
            **features
        }
    except Exception as e:
        return None

def analyze_washout_features(pre_data, full_df, start_idx):
    """分析洗盘特征"""
    features = {}
    
    # 1. 启动前是否有涨停板
    has_limit_up = False
    limit_up_date = None
    limit_up_idx = None
    
    for i in range(len(pre_data) - 1):
        row = pre_data.iloc[i]
        next_row = pre_data.iloc[i + 1]
        gain = (row['收盘'] - pre_data.iloc[i-1]['收盘']) / pre_data.iloc[i-1]['收盘'] * 100 if i > 0 else 0
        if gain >= 9.5:
            has_limit_up = True
            limit_up_date = row['日期']
            limit_up_idx = i
    
    features['有涨停'] = '是' if has_limit_up else '否'
    features['涨停日期'] = limit_up_date.strftime('%Y-%m-%d') if limit_up_date else '-'
    
    # 2. 启动前的回撤幅度
    pre_high = pre_data['最高'].max()
    pre_low = pre_data['最低'].min()
    start_price = pre_data.iloc[-1]['收盘']
    
    # 从最高点到启动日的回撤
    high_idx = pre_data['最高'].idxmax()
    if high_idx < len(pre_data) - 1:
        drawdown = (start_price - pre_high) / pre_high * 100
    else:
        drawdown = 0
    
    features['启动前回撤'] = f"{drawdown:.1f}%"
    
    # 3. 启动前的震荡幅度（近20日）
    recent_20 = pre_data.tail(20)
    volatility = (recent_20['最高'].max() - recent_20['最低'].min()) / recent_20['最低'].min() * 100
    features['近20日震荡'] = f"{volatility:.1f}%"
    
    # 4. 启动前的成交量变化
    if len(pre_data) >= 30:
        vol_early = pre_data.iloc[:15]['成交量'].mean()
        vol_late = pre_data.iloc[-15:]['成交量'].mean()
        vol_change = (vol_late - vol_early) / vol_early * 100 if vol_early > 0 else 0
        features['量能变化'] = f"{vol_change:+.1f}%"
    else:
        features['量能变化'] = '-'
    
    # 5. 是否破位（跌破前期涨停最低价）
    if has_limit_up and limit_up_idx is not None:
        limit_up_low = pre_data.iloc[limit_up_idx]['最低']
        broke_low = False
        for i in range(limit_up_idx + 1, len(pre_data)):
            if pre_data.iloc[i]['最低'] < limit_up_low:
                broke_low = True
                break
        features['是否破位'] = '是' if broke_low else '否'
        features['涨停最低价'] = round(limit_up_low, 2)
    else:
        features['是否破位'] = '-'
        features['涨停最低价'] = '-'
    
    # 6. 启动前均线形态
    pre_data = pre_data.copy()
    pre_data['MA5'] = pre_data['收盘'].rolling(5).mean()
    pre_data['MA10'] = pre_data['收盘'].rolling(10).mean()
    pre_data['MA20'] = pre_data['收盘'].rolling(20).mean()
    
    last = pre_data.iloc[-1]
    if pd.notna(last['MA5']) and pd.notna(last['MA10']) and pd.notna(last['MA20']):
        if last['MA5'] > last['MA10'] > last['MA20']:
            ma_pattern = '多头排列'
        elif last['MA5'] < last['MA10'] < last['MA20']:
            ma_pattern = '空头排列'
        else:
            ma_pattern = '交叉整理'
    else:
        ma_pattern = '-'
    
    features['均线形态'] = ma_pattern
    
    # 7. 启动前相对位置（距离60日高点）
    high_60 = pre_data['最高'].max()
    position = (start_price - pre_low) / (high_60 - pre_low) * 100 if high_60 != pre_low else 50
    features['相对位置'] = f"{position:.0f}%"
    
    # 8. 启动前是否缩量
    if len(pre_data) >= 10:
        vol_recent_5 = pre_data.tail(5)['成交量'].mean()
        vol_prev_20 = pre_data.iloc[-25:-5]['成交量'].mean() if len(pre_data) >= 25 else pre_data['成交量'].mean()
        vol_ratio = vol_recent_5 / vol_prev_20 if vol_prev_20 > 0 else 1
        features['启动前缩量'] = '是' if vol_ratio < 0.7 else '否'
        features['量比'] = f"{vol_ratio:.2f}"
    else:
        features['启动前缩量'] = '-'
        features['量比'] = '-'
    
    # 9. 启动当日特征
    start_row = pre_data.iloc[-1]
    start_gain = (start_row['收盘'] - start_row['开盘']) / start_row['开盘'] * 100
    features['启动日涨幅'] = f"{start_gain:+.1f}%"
    
    return features

def process_sector(sector, period):
    """处理单个板块"""
    results = []
    stocks = get_sector_stocks(sector)
    
    if not stocks:
        return results
    
    for stock in stocks:
        result = analyze_stock_performance(
            stock['代码'], stock['名称'], sector,
            period['start'], period['peak']
        )
        if result:
            results.append(result)
            safe_print(f"  ✓ {result['代码']} {result['名称']} 涨幅{result['启动期涨幅']}%")
    
    return results

def analyze_all_winners():
    """分析所有板块的牛股"""
    print("=" * 70)
    print("分析板块启动时的大牛股洗盘特征")
    print("=" * 70)
    print("\n筛选条件：板块启动期涨幅 > 30%")
    
    start_time = time.time()
    all_results = []
    
    for sector, period in SECTOR_SURGE_PERIODS.items():
        print(f"\n【{sector}】启动期: {period['start']} ~ {period['peak']}")
        results = process_sector(sector, period)
        all_results.extend(results)
        print(f"  找到 {len(results)} 只牛股")
    
    elapsed = time.time() - start_time
    print(f"\n分析完成！耗时: {elapsed:.1f}秒")
    print(f"共找到 {len(all_results)} 只牛股")
    
    return all_results

def summarize_features(results):
    """汇总洗盘特征"""
    if not results:
        print("\n没有找到符合条件的牛股")
        return
    
    df = pd.DataFrame(results)
    
    print("\n" + "=" * 70)
    print("洗盘特征统计分析")
    print("=" * 70)
    
    total = len(df)
    
    # 1. 涨停板统计
    has_limit = (df['有涨停'] == '是').sum()
    print(f"\n【涨停板特征】")
    print(f"  有涨停板: {has_limit}/{total} ({has_limit/total*100:.1f}%)")
    
    # 2. 破位统计
    broke = df[df['是否破位'] == '是']
    not_broke = df[df['是否破位'] == '否']
    print(f"\n【破位特征】（有涨停的股票中）")
    print(f"  破位后启动: {len(broke)}/{has_limit} ({len(broke)/has_limit*100:.1f}%)" if has_limit > 0 else "  无数据")
    print(f"  未破位启动: {len(not_broke)}/{has_limit} ({len(not_broke)/has_limit*100:.1f}%)" if has_limit > 0 else "")
    
    # 3. 回撤幅度统计
    print(f"\n【启动前回撤幅度】")
    drawdowns = df['启动前回撤'].str.replace('%', '').astype(float)
    print(f"  平均回撤: {drawdowns.mean():.1f}%")
    print(f"  中位数回撤: {drawdowns.median():.1f}%")
    print(f"  回撤范围: {drawdowns.min():.1f}% ~ {drawdowns.max():.1f}%")
    
    # 按回撤分组
    dd_groups = {
        '轻度回撤(0-10%)': ((drawdowns >= -10) & (drawdowns < 0)).sum(),
        '中度回撤(10-20%)': ((drawdowns >= -20) & (drawdowns < -10)).sum(),
        '深度回撤(20-30%)': ((drawdowns >= -30) & (drawdowns < -20)).sum(),
        '超深回撤(>30%)': (drawdowns < -30).sum(),
    }
    for name, count in dd_groups.items():
        print(f"  {name}: {count}只 ({count/total*100:.1f}%)")
    
    # 4. 震荡幅度统计
    print(f"\n【近20日震荡幅度】")
    volatility = df['近20日震荡'].str.replace('%', '').astype(float)
    print(f"  平均震荡: {volatility.mean():.1f}%")
    print(f"  中位数: {volatility.median():.1f}%")
    
    # 5. 量能变化
    print(f"\n【启动前量能变化】")
    vol_change = df['量能变化'].str.replace('%', '').str.replace('+', '').astype(float)
    shrink = (vol_change < 0).sum()
    expand = (vol_change > 0).sum()
    print(f"  缩量: {shrink}只 ({shrink/total*100:.1f}%)")
    print(f"  放量: {expand}只 ({expand/total*100:.1f}%)")
    
    # 6. 均线形态
    print(f"\n【启动前均线形态】")
    for pattern in df['均线形态'].unique():
        count = (df['均线形态'] == pattern).sum()
        print(f"  {pattern}: {count}只 ({count/total*100:.1f}%)")
    
    # 7. 相对位置
    print(f"\n【启动前相对位置（距60日低点）】")
    position = df['相对位置'].str.replace('%', '').astype(float)
    print(f"  平均位置: {position.mean():.0f}%")
    print(f"  中位数: {position.median():.0f}%")
    
    low_pos = (position < 30).sum()
    mid_pos = ((position >= 30) & (position < 60)).sum()
    high_pos = (position >= 60).sum()
    print(f"  低位(0-30%): {low_pos}只")
    print(f"  中位(30-60%): {mid_pos}只")
    print(f"  高位(60-100%): {high_pos}只")
    
    # 8. 启动前缩量
    print(f"\n【启动前是否缩量】")
    shrink_vol = (df['启动前缩量'] == '是').sum()
    print(f"  缩量: {shrink_vol}只 ({shrink_vol/total*100:.1f}%)")
    
    return df

def print_conclusion(df):
    """打印结论"""
    print("\n" + "=" * 70)
    print("【主力洗盘共同特征总结】")
    print("=" * 70)
    
    # 计算关键指标
    has_limit = (df['有涨停'] == '是').sum() / len(df) * 100
    broke = len(df[df['是否破位'] == '是']) / len(df[df['有涨停'] == '是']) * 100 if (df['有涨停'] == '是').sum() > 0 else 0
    
    drawdowns = df['启动前回撤'].str.replace('%', '').astype(float)
    avg_dd = drawdowns.mean()
    
    volatility = df['近20日震荡'].str.replace('%', '').astype(float)
    avg_vol = volatility.mean()
    
    position = df['相对位置'].str.replace('%', '').astype(float)
    avg_pos = position.mean()
    
    shrink = (df['启动前缩量'] == '是').sum() / len(df) * 100
    
    print(f"""
基于 {len(df)} 只牛股的分析，主力洗盘的共同特征：

1. 【涨停板】{has_limit:.0f}% 的牛股在启动前有过涨停板
   → 涨停板是主力建仓的信号

2. 【破位洗盘】{broke:.0f}% 的涨停股会跌破涨停最低价
   → 破位是主力洗盘的常见手法

3. 【回撤幅度】平均回撤 {avg_dd:.1f}%
   → 回撤10-20%是最常见的洗盘深度

4. 【震荡整理】近20日平均震荡 {avg_vol:.1f}%
   → 洗盘期间会有一定幅度的震荡

5. 【相对位置】启动时平均位于60日区间的 {avg_pos:.0f}% 位置
   → 不是最低点启动，而是在相对低位

6. 【缩量特征】{shrink:.0f}% 的牛股启动前出现缩量
   → 缩量是洗盘结束的信号

操作建议：
  - 关注有涨停板后回撤10-20%的个股
  - 等待缩量企稳后介入
  - 破位后反包是较好的买点
  - 配合板块热度判断启动时机
""")

def export_to_excel(results, df_summary):
    """导出到Excel"""
    import openpyxl
    from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
    
    filename = f"牛股洗盘特征分析_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    wb = openpyxl.Workbook()
    
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
    border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )
    
    # Sheet1: 所有牛股明细
    ws1 = wb.active
    ws1.title = "牛股明细"
    
    headers = ['板块', '代码', '名称', '启动期涨幅', '有涨停', '涨停日期', 
               '是否破位', '启动前回撤', '近20日震荡', '量能变化', 
               '均线形态', '相对位置', '启动前缩量', '启动日涨幅']
    
    for col, h in enumerate(headers, 1):
        cell = ws1.cell(row=1, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.border = border
    
    for row_idx, r in enumerate(results, 2):
        row_data = [
            r['板块'], r['代码'], r['名称'], f"{r['启动期涨幅']}%",
            r['有涨停'], r['涨停日期'], r['是否破位'], r['启动前回撤'],
            r['近20日震荡'], r['量能变化'], r['均线形态'], r['相对位置'],
            r['启动前缩量'], r['启动日涨幅']
        ]
        for col, val in enumerate(row_data, 1):
            cell = ws1.cell(row=row_idx, column=col, value=val)
            cell.border = border
    
    # 调整列宽
    for col in range(1, 15):
        ws1.column_dimensions[openpyxl.utils.get_column_letter(col)].width = 12
    
    wb.save(filename)
    print(f"\n✓ 已导出: {filename}")

if __name__ == "__main__":
    results = analyze_all_winners()
    df = summarize_features(results)
    if df is not None:
        print_conclusion(df)
        export_to_excel(results, df)
