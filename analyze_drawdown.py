"""分析不同回撤区间的收益"""
import pandas as pd

# 读取回测数据
df = pd.read_excel('潜力板块信号收益回测.xlsx', sheet_name='详细回测数据')

# 提取回撤数值
df['回撤数值'] = df['回撤幅度'].str.replace('%', '').astype(float)

# 按回撤区间分组
def get_drawdown_group(x):
    if x < 8:
        return '5-8%'
    elif x < 12:
        return '8-12%'
    elif x < 16:
        return '12-16%'
    else:
        return '16-20%'

df['回撤区间'] = df['回撤数值'].apply(get_drawdown_group)

# 按回撤区间统计
print('=' * 70)
print('按回撤幅度分组的收益统计')
print('=' * 70)

for group in ['5-8%', '8-12%', '12-16%', '16-20%']:
    subset = df[df['回撤区间'] == group]
    if len(subset) > 0:
        print(f'\n【回撤 {group}】 样本数: {len(subset)}')
        r1 = subset['1个月收益'].mean()
        r2 = subset['2个月收益'].mean()
        r3 = subset['3个月收益'].mean()
        r4 = subset['4个月收益'].mean()
        print(f'  1个月: {r1:.2f}%')
        print(f'  2个月: {r2:.2f}%')
        print(f'  3个月: {r3:.2f}%')
        print(f'  4个月: {r4:.2f}%')
        win_rate = (subset['4个月收益'] > 0).mean() * 100
        print(f'  4个月胜率: {win_rate:.1f}%')

# 汇总表
print('\n' + '=' * 70)
print('回撤区间收益汇总')
print('=' * 70)

summary = df.groupby('回撤区间').agg({
    '1个月收益': 'mean',
    '2个月收益': 'mean', 
    '3个月收益': 'mean',
    '4个月收益': 'mean',
    '板块': 'count'
}).round(2)
summary.columns = ['1个月', '2个月', '3个月', '4个月', '样本数']
summary = summary.reindex(['5-8%', '8-12%', '12-16%', '16-20%'])
print(summary)

# 找最佳区间
print('\n' + '=' * 70)
print('结论')
print('=' * 70)
best_1m = summary['1个月'].idxmax()
best_4m = summary['4个月'].idxmax()
print(f'1个月收益最高: {best_1m} ({summary.loc[best_1m, "1个月"]:.2f}%)')
print(f'4个月收益最高: {best_4m} ({summary.loc[best_4m, "4个月"]:.2f}%)')

# 按回撤+月份交叉分析
print('\n' + '=' * 70)
print('回撤区间 × 信号月份 交叉分析（4个月收益）')
print('=' * 70)

cross = df.pivot_table(
    values='4个月收益',
    index='回撤区间',
    columns='月份',
    aggfunc='mean'
).round(1)
cross = cross.reindex(['5-8%', '8-12%', '12-16%', '16-20%'])
print(cross)
