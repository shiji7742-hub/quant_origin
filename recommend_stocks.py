"""
快速推荐明日可入股票
基于多个验证策略的综合评分
"""
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

print("="*70)
print(f"股票推荐系统 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print("="*70)

# 获取市场数据（增加重试机制）
print("\n正在获取市场数据...")
df_market = None
for attempt in range(3):
    try:
        print(f"  尝试 {attempt + 1}/3...")
        df_market = ak.stock_zh_a_spot_em()
        print(f"  ✓ 获取到 {len(df_market)} 只股票")
        break
    except Exception as e:
        print(f"  ✗ 失败: {str(e)[:100]}")
        if attempt < 2:
            import time
            time.sleep(5)
        else:
            print("\n网络连接失败，无法获取实时数据")
            print("建议：")
            print("1. 检查网络连接")
            print("2. 稍后再试")
            print("3. 或使用历史扫描结果：python check_macd_stocks.py")
            exit(1)

# 基础筛选
print("\n执行基础筛选...")
df = df_market.copy()
df = df[df['代码'].str.match(r'^(60|00)')]  # 主板
df = df[~df['名称'].str.contains('ST|退')]   # 排除ST和退市
df = df[df['成交额'] > 5e7]                  # 成交额>5000万
df = df[df['涨跌幅'] > -5]                   # 跌幅不超过5%
df = df[df['涨跌幅'] < 9.5]                  # 排除涨停

print(f"初筛后: {len(df)} 只股票")

# 选择候选股票（按成交额和涨幅综合排序）
df['综合得分'] = df['成交额'] / 1e8 + df['涨跌幅'] * 10
candidates = df.nlargest(50, '综合得分')

print(f"\n分析 {len(candidates)} 只候选股票...")

results = []
processed = 0

for _, row in candidates.iterrows():
    code = row['代码']
    name = row['名称']
    processed += 1
    
    if processed % 10 == 0:
        print(f"  进度: {processed}/{len(candidates)}")
    
    try:
        # 获取历史数据（增加重试）
        hist = None
        for retry in range(2):
            try:
                hist = ak.stock_zh_a_hist(symbol=code, period='daily', 
                                          start_date='20241001', adjust='qfq')
                break
            except:
                if retry == 0:
                    import time
                    time.sleep(1)
        
        if hist is None or len(hist) < 30:
            continue
        
        hist = hist.tail(60)
        close = hist['收盘'].values
        volume = hist['成交量'].values
        high = hist['最高'].values
        low = hist['最低'].values
        
        # 计算均线
        ma5 = pd.Series(close).rolling(5).mean().values
        ma10 = pd.Series(close).rolling(10).mean().values
        ma20 = pd.Series(close).rolling(20).mean().values
        
        # 当前数据
        current_price = close[-1]
        prev_price = close[-2]
        current_vol = volume[-1]
        
        # 评分系统
        score = 0
        signals = []
        
        # 1. 均线多头排列 (2分)
        if ma5[-1] > ma10[-1] > ma20[-1]:
            score += 2
            signals.append('均线多头')
        elif ma5[-1] > ma10[-1]:
            score += 1
            signals.append('短期向上')
        
        # 2. 价格在均线之上 (1分)
        if current_price > ma20[-1]:
            score += 1
            signals.append('站上MA20')
        
        # 3. 量能放大 (2分)
        vol_ma5 = pd.Series(volume).rolling(5).mean().values[-2]
        if current_vol > vol_ma5 * 1.5:
            score += 2
            signals.append('放量')
        elif current_vol > vol_ma5:
            score += 1
            signals.append('温和放量')
        
        # 4. 近期回调后企稳 (2分)
        high_20 = max(high[-20:])
        pullback = (current_price - high_20) / high_20 * 100
        if -15 < pullback < -5:
            score += 2
            signals.append(f'回调{abs(pullback):.1f}%')
        elif -5 <= pullback < 0:
            score += 1
            signals.append('小幅回调')
        
        # 5. 今日表现 (1分)
        today_change = (current_price - prev_price) / prev_price * 100
        if today_change > 0:
            score += 1
            if today_change > 3:
                signals.append(f'今涨{today_change:.1f}%')
        
        # 6. 箱体突破 (2分)
        if len(close) >= 20:
            box_high = max(high[-16:-1])
            box_low = min(low[-16:-1])
            if current_price > box_high * 1.02:
                score += 2
                signals.append('突破箱体')
        
        # 7. 换手率适中 (1分)
        turnover = row.get('换手率', 0)
        if 2 < turnover < 15:
            score += 1
            signals.append(f'换手{turnover:.1f}%')
        
        # 只保留评分>=5的股票
        if score >= 5:
            results.append({
                '代码': code,
                '名称': name,
                '现价': current_price,
                '涨跌幅': row['涨跌幅'],
                '换手率': turnover,
                '成交额': row['成交额'] / 1e8,
                '评分': score,
                '信号': ' | '.join(signals)
            })
    
    except Exception as e:
        continue

# 按评分排序
results.sort(key=lambda x: x['评分'], reverse=True)

# 输出结果
print("\n" + "="*70)
print(f"推荐结果 (评分>=5分，共{len(results)}只)")
print("="*70)

if not results:
    print("\n今日暂无符合条件的推荐股票")
else:
    print("\n【高分推荐】(评分>=7分)")
    high_score = [r for r in results if r['评分'] >= 7]
    if high_score:
        for i, r in enumerate(high_score[:10], 1):
            print(f"\n{i}. {r['代码']} {r['名称']}")
            print(f"   现价: {r['现价']:.2f}  涨幅: {r['涨跌幅']:+.2f}%  换手: {r['换手率']:.1f}%")
            print(f"   成交额: {r['成交额']:.1f}亿  评分: {r['评分']}/11")
            print(f"   信号: {r['信号']}")
    else:
        print("   无")
    
    print("\n【次优推荐】(评分5-6分)")
    mid_score = [r for r in results if 5 <= r['评分'] < 7]
    if mid_score:
        for i, r in enumerate(mid_score[:10], 1):
            print(f"\n{i}. {r['代码']} {r['名称']}")
            print(f"   现价: {r['现价']:.2f}  涨幅: {r['涨跌幅']:+.2f}%  换手: {r['换手率']:.1f}%")
            print(f"   评分: {r['评分']}/11  信号: {r['信号']}")
    else:
        print("   无")

# 导出Excel
if results:
    print("\n正在导出Excel...")
    df_result = pd.DataFrame(results)
    filename = f"推荐股票_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df_result.to_excel(filename, index=False, engine='openpyxl')
    print(f"已导出: {filename}")

print("\n" + "="*70)
print("扫描完成！")
print("="*70)
