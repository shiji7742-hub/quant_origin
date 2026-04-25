"""读取最新扫描结果"""
import pandas as pd
import os

os.chdir(r'D:\量化\quant_ai')

# 读取策略组合扫描结果
filename = '策略组合扫描_20260122_145228.xlsx'
print(f"读取: {filename}")
print("="*70)

df = pd.read_excel(filename)
print(f"共 {len(df)} 条记录\n")

# 按策略组合分组显示
if '策略组合' in df.columns:
    for combo in df['策略组合'].unique():
        subset = df[df['策略组合'] == combo]
        print(f"\n【{combo}】 ({len(subset)} 只)")
        print("-"*60)
        for _, row in subset.head(10).iterrows():
            print(f"  {row['代码']} {row['名称']:<8} 现价:{row['现价']:>7.2f} 涨跌:{row['涨跌幅']}")
else:
    print(df.head(30).to_string(index=False))
