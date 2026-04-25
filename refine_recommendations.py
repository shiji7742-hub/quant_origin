"""
精确筛选推荐股票
基于策略组合扫描结果，进一步筛选最优标的
"""
import pandas as pd
import akshare as ak
from datetime import datetime

print("="*70)
print("精确推荐筛选")
print("="*70)

# 读取扫描结果
df = pd.read_excel('策略组合扫描_20260119_220003.xlsx')
print(f"\n总信号数: {len(df)}")

# 筛选三重信号
df_triple = df[df['策略组合']=='深度回调+箱体突破+均线粘合'].copy()
print(f"三重信号股票: {len(df_triple)}只")

# 获取实时详细数据
print("\n正在获取详细数据...")
results = []

for _, row in df_triple.iterrows():
    code = str(row['代码']).zfill(6)
    name = row['名称']
    
    try:
        # 获取实时行情
        df_spot = ak.stock_zh_a_spot_em()
        stock_info = df_spot[df_spot['代码']==code].iloc[0]
        
        # 获取历史数据
        df_hist = ak.stock_zh_a_hist(symbol=code, period='daily', adjust='qfq')
        df_hist = df_hist.tail(60)
        
        # 计算指标
        close = df_hist['收盘'].values
        volume = df_hist['成交量'].values
        
        # 均线
        ma5 = pd.Series(close).rolling(5).mean().iloc[-1]
        ma10 = pd.Series(close).rolling(10).mean().iloc[-1]
        ma20 = pd.Series(close).rolling(20).mean().iloc[-1]
        
        # 量比
        vol_today = volume[-1]
        vol_avg = volume[-20:-1].mean()
        vol_ratio = vol_today / vol_avg if vol_avg > 0 else 0
        
        # 近期高点
        high_20 = df_hist['最高'].tail(20).max()
        current_price = close[-1]
        distance_to_high = (high_20 - current_price) / current_price * 100
        
        # 评分
        score = 0
        reasons = []
        
        # 1. 今日涨幅适中 (2分)
        change = stock_info['涨跌幅']
        if 2 < change < 6:
            score += 2
            reasons.append(f'涨幅适中{change:.1f}%')
        elif change <= 2:
            score += 1
            reasons.append(f'涨幅较小{change:.1f}%')
        
        # 2. 成交额充足 (2分)
        amount = stock_info['成交额']
        if amount > 5e8:
            score += 2
            reasons.append(f'成交额{amount/1e8:.1f}亿')
        elif amount > 2e8:
            score += 1
            reasons.append(f'成交额{amount/1e8:.1f}亿')
        
        # 3. 换手率适中 (1分)
        turnover = stock_info['换手率']
        if 2 < turnover < 10:
            score += 1
            reasons.append(f'换手{turnover:.1f}%')
        
        # 4. 均线多头 (2分)
        if ma5 > ma10 > ma20:
            score += 2
            reasons.append('均线多头')
        elif ma5 > ma10:
            score += 1
            reasons.append('短期向上')
        
        # 5. 量比放大 (1分)
        if vol_ratio > 1.2:
            score += 1
            reasons.append(f'量比{vol_ratio:.1f}')
        
        # 6. 上涨空间 (2分)
        if distance_to_high > 10:
            score += 2
            reasons.append(f'空间{distance_to_high:.1f}%')
        elif distance_to_high > 5:
            score += 1
            reasons.append(f'空间{distance_to_high:.1f}%')
        
        results.append({
            '代码': code,
            '名称': name,
            '现价': current_price,
            '今日涨幅': change,
            '成交额': amount / 1e8,
            '换手率': turnover,
            '量比': vol_ratio,
            '距高点': distance_to_high,
            '评分': score,
            '优势': ' | '.join(reasons)
        })
        
        print(f"  ✓ {code} {name} 评分:{score}/10")
        
    except Exception as e:
        print(f"  ✗ {code} {name} 失败")
        continue

# 排序
results.sort(key=lambda x: x['评分'], reverse=True)

# 输出结果
print("\n" + "="*70)
print("精确推荐结果（按评分排序）")
print("="*70)

for i, r in enumerate(results, 1):
    print(f"\n{i}. {r['代码']} {r['名称']}")
    print(f"   现价: {r['现价']:.2f}  今日涨幅: {r['今日涨幅']:+.2f}%")
    print(f"   成交额: {r['成交额']:.1f}亿  换手率: {r['换手率']:.1f}%  量比: {r['量比']:.2f}")
    print(f"   距高点: {r['距高点']:.1f}%  评分: {r['评分']}/10")
    print(f"   优势: {r['优势']}")

# 导出
df_result = pd.DataFrame(results)
filename = f"精确推荐_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
df_result.to_excel(filename, index=False)
print(f"\n已导出: {filename}")

# 给出明确建议
print("\n" + "="*70)
print("明日操作建议")
print("="*70)

top3 = results[:3]
print("\n【首选3只】（评分最高）")
for i, r in enumerate(top3, 1):
    print(f"\n{i}. {r['代码']} {r['名称']}")
    print(f"   建议买入价: {r['现价']:.2f}附近")
    print(f"   止损价: {r['现价']*0.95:.2f} (-5%)")
    print(f"   目标价: {r['现价']*1.10:.2f} (+10%)")
    print(f"   建议仓位: 5-8%")

print("\n⚠️ 风险提示:")
print("1. 当前市场情绪较弱，建议总仓位≤20%")
print("2. 严格止损-5%，不要心存侥幸")
print("3. 持有周期10-20天，不要短炒")
print("4. 分批建仓，不要一次性满仓")
print("="*70)
