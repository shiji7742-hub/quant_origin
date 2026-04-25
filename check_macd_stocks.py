"""
检查MACD金叉股票的最新状态
"""
import pandas as pd
import akshare as ak
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

print("="*70)
print("MACD金叉股票最新状态检查")
print("="*70)

# 读取1月17日的扫描结果
try:
    df_scan = pd.read_excel('MACD金叉扫描_宽松_20260117_094524.xlsx', 
                            sheet_name='0轴上方金叉')
    print(f"\n读取到 {len(df_scan)} 只MACD金叉股票（1月17日数据）")
except Exception as e:
    print(f"读取文件失败: {e}")
    exit(1)

# 重点关注的股票（MACD值较高且当时涨幅不大）
focus_codes = []
for _, row in df_scan.iterrows():
    code = str(row['代码']).zfill(6)
    macd = row['MACD']
    change_17 = float(str(row['今日涨幅']).replace('%', ''))
    
    # 筛选条件：MACD>0.5 且 17日涨幅<8%
    if macd > 0.5 and change_17 < 8:
        focus_codes.append({
            'code': code,
            'name': row['名称'],
            'macd': macd,
            'price_17': row['现价'],
            'change_17': change_17
        })

print(f"\n筛选出 {len(focus_codes)} 只重点股票（MACD>0.5且17日涨幅<8%）")

# 获取最新行情
print("\n正在获取最新行情...")
results = []

for stock in focus_codes[:20]:  # 只检查前20只
    code = stock['code']
    name = stock['name']
    
    try:
        # 获取最近5天数据
        df = ak.stock_zh_a_hist(symbol=code, period='daily', adjust='qfq')
        if df is None or len(df) < 5:
            continue
        
        df = df.tail(5)
        latest = df.iloc[-1]
        price_17_actual = df.iloc[-3]['收盘'] if len(df) >= 3 else stock['price_17']
        
        current_price = latest['收盘']
        current_change = latest['涨跌幅']
        
        # 计算从17日到现在的累计涨幅
        total_change = (current_price - price_17_actual) / price_17_actual * 100
        
        # 判断是否还有机会
        opportunity = "✓" if total_change < 5 and current_change < 3 else "✗"
        
        results.append({
            '代码': code,
            '名称': name,
            'MACD': stock['macd'],
            '17日价': price_17_actual,
            '现价': current_price,
            '今日涨幅': current_change,
            '累计涨幅': total_change,
            '机会': opportunity
        })
        
    except Exception as e:
        continue

# 输出结果
print("\n" + "="*70)
print("分析结果")
print("="*70)

if not results:
    print("\n无法获取最新数据")
else:
    df_result = pd.DataFrame(results)
    
    # 有机会的股票
    df_good = df_result[df_result['机会'] == '✓'].sort_values('MACD', ascending=False)
    
    print("\n【可以考虑】（累计涨幅<5%且今日涨幅<3%）")
    if len(df_good) > 0:
        for i, row in df_good.iterrows():
            print(f"\n{row['代码']} {row['名称']}")
            print(f"  MACD: {row['MACD']:.2f}")
            print(f"  17日价: {row['17日价']:.2f} → 现价: {row['现价']:.2f}")
            print(f"  今日涨幅: {row['今日涨幅']:+.2f}%  累计涨幅: {row['累计涨幅']:+.2f}%")
    else:
        print("  暂无（大部分已经涨太多）")
    
    # 已经涨太多的
    df_high = df_result[df_result['机会'] == '✗'].sort_values('累计涨幅', ascending=False)
    
    print("\n【已涨太多】（累计涨幅≥5%或今日涨幅≥3%）")
    if len(df_high) > 0:
        for i, row in df_high.head(5).iterrows():
            print(f"  {row['代码']} {row['名称']}: 累计+{row['累计涨幅']:.2f}%")
    
    # 导出
    filename = f"MACD股票最新状态_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df_result.to_excel(filename, index=False)
    print(f"\n已导出: {filename}")

print("\n" + "="*70)
print("⚠️ 风险提示：")
print("1. 当前市场情绪评分仅1/7，不是最佳入场时机")
print("2. 建议等待市场情绪改善（评分≥4/7）")
print("3. 如果一定要操作，仓位控制在10%以内")
print("4. 严格止损-5%")
print("="*70)
