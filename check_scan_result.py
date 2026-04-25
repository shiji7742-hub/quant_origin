"""检查之前扫描结果的股票现状"""
import akshare as ak
import json

# 读取之前的扫描结果
with open('scan_result_20251219_145947.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print("="*70)
print("检查12月19日扫描结果的股票现状")
print("="*70)

# 获取实时行情
df = ak.stock_zh_a_spot_em()
df = df.set_index('代码')

# 检查触发的股票
print("\n【当时触发信号的股票】")
print(f"{'代码':<8} {'名称':<10} {'当时价':>8} {'现价':>8} {'涨跌':>8}")
print("-"*50)

for item in data['triggered']:
    code = item['symbol']
    old_price = item['close']
    if code in df.index:
        row = df.loc[code]
        change = (row['最新价'] - old_price) / old_price * 100
        print(f"{code:<8} {row['名称']:<10} {old_price:>8.2f} {row['最新价']:>8.2f} {change:>+7.1f}%")

# 检查观察中的股票（距离支撑位近的）
print("\n【观察中的股票（距支撑位<6%）】")
print(f"{'代码':<8} {'名称':<10} {'支撑位':>8} {'现价':>8} {'距支撑':>8}")
print("-"*50)

for item in data['watching']:
    if item['distance'] < 6:
        code = item['symbol']
        support = item['limit_low']
        if code in df.index:
            row = df.loc[code]
            dist = (row['最新价'] - support) / support * 100
            status = "⚠️破位" if dist < 0 else ""
            print(f"{code:<8} {row['名称']:<10} {support:>8.2f} {row['最新价']:>8.2f} {dist:>+7.1f}% {status}")
