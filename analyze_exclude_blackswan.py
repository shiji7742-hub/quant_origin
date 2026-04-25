"""排除黑天鹅事件后的策略表现分析"""
import pandas as pd
import os
import glob
from datetime import datetime

def log(msg):
    print(msg, flush=True)

# 读取回测结果
log("="*60)
log("排除黑天鹅事件后的策略表现")
log("="*60)

files = glob.glob('横盘托单回测_*.xlsx')
if not files:
    log("未找到回测结果文件")
    exit()

latest_file = max(files, key=os.path.getmtime)
log(f"\n读取: {latest_file}")

df = pd.read_excel(latest_file)
df['日期'] = pd.to_datetime(df['日期'])

log(f"总交易数: {len(df)}")

# 定义黑天鹅时期（2025年4月关税战）
blackswan_start = pd.to_datetime('2025-03-28')
blackswan_end = pd.to_datetime('2025-04-15')

log(f"\n黑天鹅时期: {blackswan_start.strftime('%Y-%m-%d')} ~ {blackswan_end.strftime('%Y-%m-%d')}")
log("(美国对中国加征关税)")

# 分割数据
blackswan_df = df[(df['日期'] >= blackswan_start) & (df['日期'] <= blackswan_end)]
normal_df = df[(df['日期'] < blackswan_start) | (df['日期'] > blackswan_end)]

log(f"\n黑天鹅期间交易: {len(blackswan_df)}个")
log(f"正常时期交易: {len(normal_df)}个")

# 对比分析
log("\n" + "="*60)
log("黑天鹅期间 vs 正常时期 对比")
log("="*60)

def analyze_period(data, name):
    if len(data) == 0:
        return
    
    log(f"\n【{name}】({len(data)}个交易)")
    
    for period in ['1日收益', '3日收益', '5日收益']:
        avg = data[period].mean()
        win_rate = (data[period] > 0).sum() / len(data) * 100
        max_r = data[period].max()
        min_r = data[period].min()
        
        log(f"  {period}: 平均{avg:+.2f}%  胜率{win_rate:.1f}%  最高{max_r:+.1f}%  最低{min_r:+.1f}%")
    
    # 亏损分布
    loss_5 = len(data[data['5日收益'] < -5])
    loss_10 = len(data[data['5日收益'] < -10])
    loss_20 = len(data[data['5日收益'] < -20])
    
    log(f"  亏损>5%: {loss_5}个({loss_5/len(data)*100:.1f}%)")
    log(f"  亏损>10%: {loss_10}个({loss_10/len(data)*100:.1f}%)")
    log(f"  亏损>20%: {loss_20}个({loss_20/len(data)*100:.1f}%)")

analyze_period(blackswan_df, "黑天鹅期间 (2025.3.28~4.15)")
analyze_period(normal_df, "正常时期")

# 详细对比表格
log("\n" + "="*60)
log("详细对比")
log("="*60)

metrics = ['1日收益', '3日收益', '5日收益']

log(f"\n{'指标':<12} {'黑天鹅期间':>15} {'正常时期':>15} {'差异':>10}")
log("-" * 55)

for m in metrics:
    bs_avg = blackswan_df[m].mean() if len(blackswan_df) > 0 else 0
    nm_avg = normal_df[m].mean() if len(normal_df) > 0 else 0
    diff = nm_avg - bs_avg
    log(f"{m}平均  {bs_avg:>+14.2f}% {nm_avg:>+14.2f}% {diff:>+9.2f}%")

for m in metrics:
    bs_wr = (blackswan_df[m] > 0).sum() / len(blackswan_df) * 100 if len(blackswan_df) > 0 else 0
    nm_wr = (normal_df[m] > 0).sum() / len(normal_df) * 100 if len(normal_df) > 0 else 0
    diff = nm_wr - bs_wr
    log(f"{m}胜率  {bs_wr:>14.1f}% {nm_wr:>14.1f}% {diff:>+9.1f}%")

# 正常时期按月份分析
log("\n" + "="*60)
log("正常时期按月份分析")
log("="*60)

normal_df['月份'] = normal_df['日期'].dt.to_period('M')
monthly = normal_df.groupby('月份').agg({
    '5日收益': ['count', 'mean', lambda x: (x > 0).sum() / len(x) * 100]
}).round(2)
monthly.columns = ['交易数', '平均收益', '胜率']

log(f"\n{'月份':<10} {'交易数':>8} {'平均收益':>10} {'胜率':>8}")
log("-" * 40)
for idx, row in monthly.iterrows():
    log(f"{str(idx):<10} {int(row['交易数']):>8} {row['平均收益']:>+9.2f}% {row['胜率']:>7.1f}%")

# 结论
log("\n" + "="*60)
log("结论")
log("="*60)

nm_5d_wr = (normal_df['5日收益'] > 0).sum() / len(normal_df) * 100 if len(normal_df) > 0 else 0
nm_5d_avg = normal_df['5日收益'].mean() if len(normal_df) > 0 else 0
bs_5d_wr = (blackswan_df['5日收益'] > 0).sum() / len(blackswan_df) * 100 if len(blackswan_df) > 0 else 0

log(f"""
排除黑天鹅事件后：

✓ 5日胜率: {nm_5d_wr:.1f}% (vs 黑天鹅期间 {bs_5d_wr:.1f}%)
✓ 5日平均收益: {nm_5d_avg:+.2f}%
✓ 亏损>10%占比: {len(normal_df[normal_df['5日收益'] < -10]) / len(normal_df) * 100:.1f}%
✓ 亏损>20%占比: {len(normal_df[normal_df['5日收益'] < -20]) / len(normal_df) * 100:.2f}%

策略在正常市场环境下表现更稳定，黑天鹅事件造成的极端亏损
是系统性风险，可通过以下方式规避：
1. 关注宏观政策风险（贸易战、加息等）
2. 设置严格止损（-5%）
3. 控制仓位（单只<15%）
4. 分散持仓（≥5只）
""")

# 如果排除黑天鹅，模拟加入止损后的效果
log("\n" + "="*60)
log("止损优化模拟（正常时期）")
log("="*60)

for stop_loss in [-3, -5, -7]:
    # 模拟止损
    simulated = normal_df.copy()
    simulated['止损后收益'] = simulated['5日收益'].apply(
        lambda x: max(x, stop_loss) if x < 0 else x
    )
    
    avg = simulated['止损后收益'].mean()
    wr = (simulated['止损后收益'] > 0).sum() / len(simulated) * 100
    
    log(f"  止损{stop_loss}%: 平均收益{avg:+.2f}%  胜率{wr:.1f}%")
