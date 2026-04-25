"""
分析2025年5-7月最佳信号的共同特征
总结历史经验
"""
import pandas as pd

# 读取数据
df = pd.read_excel('潜力板块信号收益回测.xlsx', sheet_name='详细回测数据')
df['回撤数值'] = df['回撤幅度'].str.replace('%', '').astype(float)
df['爆发数值'] = df['爆发涨幅'].str.replace('+', '').str.replace('%', '').astype(float)

# 筛选5-7月信号
may_july = df[df['月份'].isin(['05月', '06月', '07月'])]

print("=" * 70)
print("2025年5-7月信号深度分析")
print("=" * 70)

print(f"\n5-7月总信号数: {len(may_july)}")
print(f"平均4个月收益: {may_july['4个月收益'].mean():.1f}%")

# 按收益分组
top_performers = may_july[may_july['4个月收益'] > 50]  # 收益>50%
good_performers = may_july[(may_july['4个月收益'] > 20) & (may_july['4个月收益'] <= 50)]
avg_performers = may_july[(may_july['4个月收益'] > 0) & (may_july['4个月收益'] <= 20)]
losers = may_july[may_july['4个月收益'] <= 0]

print("\n【收益分布】")
print(f"  大牛(>50%): {len(top_performers)}个, 占比{len(top_performers)/len(may_july)*100:.1f}%")
print(f"  优秀(20-50%): {len(good_performers)}个, 占比{len(good_performers)/len(may_july)*100:.1f}%")
print(f"  一般(0-20%): {len(avg_performers)}个, 占比{len(avg_performers)/len(may_july)*100:.1f}%")
print(f"  亏损(<0%): {len(losers)}个, 占比{len(losers)/len(may_july)*100:.1f}%")

# 分析大牛板块特征
print("\n" + "=" * 70)
print("【大牛板块(4个月收益>50%)详细分析】")
print("=" * 70)

if len(top_performers) > 0:
    print(f"\n共{len(top_performers)}个大牛板块:")
    for _, r in top_performers.sort_values('4个月收益', ascending=False).iterrows():
        print(f"\n  {r['月份']} {r['板块']}")
        print(f"    爆发涨幅: {r['爆发涨幅']}")
        print(f"    回撤幅度: {r['回撤幅度']}")
        print(f"    收益曲线: 1月{r['1个月收益']:.1f}% → 2月{r['2个月收益']:.1f}% → 3月{r['3个月收益']:.1f}% → 4月{r['4个月收益']:.1f}%")
    
    print("\n【大牛板块共同特征】")
    print(f"  平均爆发涨幅: {top_performers['爆发数值'].mean():.1f}%")
    print(f"  平均回撤幅度: {top_performers['回撤数值'].mean():.1f}%")
    print(f"  回撤区间分布:")
    for dd_range in ['5-10%', '10-15%', '15-20%']:
        if dd_range == '5-10%':
            count = len(top_performers[(top_performers['回撤数值'] >= 5) & (top_performers['回撤数值'] < 10)])
        elif dd_range == '10-15%':
            count = len(top_performers[(top_performers['回撤数值'] >= 10) & (top_performers['回撤数值'] < 15)])
        else:
            count = len(top_performers[(top_performers['回撤数值'] >= 15) & (top_performers['回撤数值'] <= 20)])
        print(f"    {dd_range}: {count}个 ({count/len(top_performers)*100:.0f}%)")

# 分析亏损板块特征
print("\n" + "=" * 70)
print("【亏损板块分析】")
print("=" * 70)

if len(losers) > 0:
    print(f"\n共{len(losers)}个亏损板块:")
    for _, r in losers.iterrows():
        print(f"  {r['月份']} {r['板块']}: 4个月{r['4个月收益']:.1f}%")
    
    print("\n【亏损板块特征】")
    print(f"  平均爆发涨幅: {losers['爆发数值'].mean():.1f}%")
    print(f"  平均回撤幅度: {losers['回撤数值'].mean():.1f}%")

# 板块类型分析
print("\n" + "=" * 70)
print("【板块类型分析】")
print("=" * 70)

# 手动分类
tech_keywords = ['AI', 'ChatGPT', '数据', '芯片', '半导体', '5G', 'F5G', '鸿蒙', '手机', 'VPN', '数字']
new_energy_keywords = ['新能源', '锂电', '光伏', '储能', '氢能', '电力']
consume_keywords = ['消费', '食品', '医药', '医疗', '白酒']

def classify_sector(name):
    for kw in tech_keywords:
        if kw in name:
            return '科技'
    for kw in new_energy_keywords:
        if kw in name:
            return '新能源'
    for kw in consume_keywords:
        if kw in name:
            return '消费'
    return '其他'

may_july['板块类型'] = may_july['板块'].apply(classify_sector)

type_stats = may_july.groupby('板块类型').agg({
    '4个月收益': ['mean', 'count'],
}).round(1)
type_stats.columns = ['平均收益', '数量']
type_stats = type_stats.sort_values('平均收益', ascending=False)

print("\n各类型板块表现:")
for t in type_stats.index:
    r = type_stats.loc[t]
    print(f"  {t}: 平均收益{r['平均收益']:.1f}%, 数量{int(r['数量'])}个")

# 总结经验
print("\n" + "=" * 70)
print("【历史经验总结】")
print("=" * 70)

print("""
1. 【大牛板块特征】
   - 多为科技类板块（AI、数据、芯片相关）
   - 爆发涨幅较大（通常>8%）
   - 回撤幅度适中（10-18%最佳）
   - 1个月收益可能为负或小正，但后续爆发

2. 【避坑经验】
   - 回撤过小(<8%)的板块，洗盘不充分，后续涨幅有限
   - 回撤过大(>18%)的板块，可能是趋势反转而非洗盘
   - 非热门赛道的板块，即使符合条件，涨幅也有限

3. 【选股逻辑】
   - 优先选择当年热门赛道（2025年是AI、数据中心）
   - 在热门赛道中找回撤12-16%的板块
   - 信号出现后不急于买入，可等1-2周确认企稳

4. 【时机把握】
   - 5月信号：最佳，正好赶上下半年行情
   - 6月信号：次佳，持有到10月收益最大化
   - 7月信号：可以，但需要更精选

5. 【仓位管理】
   - 单板块仓位不超过20%
   - 同时持有3-5个板块分散风险
   - 信号密集时（如5月）可适当加仓
""")

# 2026年预判
print("\n" + "=" * 70)
print("【2026年操作建议】")
print("=" * 70)

print("""
基于2025年经验，2026年操作建议：

1. 【关注时间】
   - 4月开始观察，等待信号出现
   - 5-7月是最佳买入窗口

2. 【选板块标准】
   - 当年热门赛道（需要判断2026年主线）
   - Q1有过爆发（单日>5%）
   - 回撤12-16%后企稳
   - 近期有脉冲拉伸迹象

3. 【买入策略】
   - 信号出现后观察1-2周
   - 确认企稳后分批建仓
   - 首次建仓50%，回调加仓50%

4. 【持有策略】
   - 目标持有4个月
   - 中途不轻易止损（除非跌破前低）
   - 涨幅超过30%可考虑减仓1/3

5. 【止盈策略】
   - 4个月后开始分批止盈
   - 涨幅超过50%可止盈一半
   - 涨幅超过80%全部止盈
""")
