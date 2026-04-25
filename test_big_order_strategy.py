#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试大单吃货策略
演示策略的核心逻辑和识别方法
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def create_mock_tick_data():
    """创建模拟的分笔数据（模拟主力托价行为）"""
    
    # 模拟一天的分笔数据
    base_time = datetime.now().replace(hour=9, minute=30, second=0)
    data = []
    
    # 场景1：早盘主力托价（9:30-10:00）
    print("\n【场景1：早盘主力托价】")
    print("时间：9:30-10:00")
    print("特征：大单向上吃，托住价格在8.60-8.65区间")
    print("-" * 60)
    
    base_price = 8.60
    for i in range(30):
        time = base_time + timedelta(minutes=i)
        
        # 每隔5分钟出现一次大单托价
        if i % 5 == 0:
            # 大单买入（主力托价）
            data.append({
                '时间': time.strftime('%H:%M:%S'),
                '成交价': base_price + np.random.uniform(0, 0.05),
                '成交量': np.random.randint(8000, 15000),  # 大单
                '成交金额': 0,  # 后面计算
                '性质': '买盘',
                '类型': '逐笔大单'
            })
            print(f"  {time.strftime('%H:%M:%S')} - 💎 大单托价: {base_price:.2f}元, 成交{data[-1]['成交量']}手")
        else:
            # 散户小单卖出（抛压）
            data.append({
                '时间': time.strftime('%H:%M:%S'),
                '成交价': base_price + np.random.uniform(-0.02, 0.03),
                '成交量': np.random.randint(100, 1000),  # 小单
                '成交金额': 0,
                '性质': '卖盘',
                '类型': '小单'
            })
    
    # 场景2：横盘整理（10:00-11:00）
    print("\n【场景2：横盘整理】")
    print("时间：10:00-11:00")
    print("特征：价格被控制在8.60-8.65，波动<1%")
    print("-" * 60)
    
    base_time = base_time.replace(hour=10, minute=0)
    for i in range(60):
        time = base_time + timedelta(minutes=i)
        
        # 横盘，价格稳定
        data.append({
            '时间': time.strftime('%H:%M:%S'),
            '成交价': 8.63 + np.random.uniform(-0.03, 0.03),
            '成交量': np.random.randint(200, 800),
            '成交金额': 0,
            '性质': np.random.choice(['买盘', '卖盘']),
            '类型': '小单'
        })
    
    print(f"  横盘区间: 8.60-8.66元")
    print(f"  波动幅度: <1%")
    
    # 场景3：午后再次托价（13:30-14:00）
    print("\n【场景3：午后再次托价】")
    print("时间：13:30-14:00")
    print("特征：主力再次托价，确认还在控盘")
    print("-" * 60)
    
    base_time = base_time.replace(hour=13, minute=30)
    for i in range(30):
        time = base_time + timedelta(minutes=i)
        
        if i % 8 == 0:
            # 再次大单托价
            data.append({
                '时间': time.strftime('%H:%M:%S'),
                '成交价': 8.65 + np.random.uniform(0, 0.05),
                '成交量': np.random.randint(10000, 18000),
                '成交金额': 0,
                '性质': '买盘',
                '类型': '逐笔大单'
            })
            print(f"  {time.strftime('%H:%M:%S')} - 💎 再次托价: {8.65:.2f}元, 成交{data[-1]['成交量']}手")
        else:
            data.append({
                '时间': time.strftime('%H:%M:%S'),
                '成交价': 8.65 + np.random.uniform(-0.02, 0.02),
                '成交量': np.random.randint(100, 800),
                '成交金额': 0,
                '性质': np.random.choice(['买盘', '卖盘']),
                '类型': '小单'
            })
    
    # 场景4：尾盘回落（14:30-15:00）
    print("\n【场景4：尾盘回落】")
    print("时间：14:30-15:00")
    print("特征：价格回落但守住支撑位8.63")
    print("-" * 60)
    
    base_time = base_time.replace(hour=14, minute=30)
    for i in range(30):
        time = base_time + timedelta(minutes=i)
        
        # 尾盘回落
        price = 8.70 - (i / 30) * 0.04  # 从8.70逐步回落到8.66
        data.append({
            '时间': time.strftime('%H:%M:%S'),
            '成交价': price + np.random.uniform(-0.01, 0.01),
            '成交量': np.random.randint(100, 500),  # 成交量萎缩
            '成交金额': 0,
            '性质': '卖盘' if i < 20 else '买盘',
            '类型': '小单'
        })
    
    print(f"  盘中最高: 8.70元")
    print(f"  收盘价: 8.66元")
    print(f"  回落幅度: 0.58%")
    print(f"  支撑位: 8.63元 ✓ 守住")
    
    # 计算成交金额
    df = pd.DataFrame(data)
    df['成交金额'] = df['成交价'] * df['成交量'] * 100  # 转换为元
    
    return df

def analyze_big_order_pattern(df):
    """分析大单吃货模式"""
    
    print("\n" + "=" * 70)
    print("【大单吃货策略分析】")
    print("=" * 70)
    
    # 1. 统计大单
    big_orders = df[df['类型'] == '逐笔大单']
    big_buy = big_orders[big_orders['性质'] == '买盘']
    
    print(f"\n1️⃣ 大单统计")
    print(f"   逐笔大单买入: {len(big_buy)}次")
    print(f"   总金额: {big_buy['成交金额'].sum()/10000:.2f}万元")
    print(f"   平均托价位: {big_buy['成交价'].mean():.2f}元")
    
    # 2. 托价次数和节奏
    print(f"\n2️⃣ 托价节奏")
    print(f"   托价次数: {len(big_buy)}次")
    print(f"   时间分布: 早盘{len(big_buy[big_buy['时间'] < '10:00:00'])}次, "
          f"午后{len(big_buy[big_buy['时间'] > '13:00:00'])}次")
    print(f"   节奏特征: 有规律的托价动作 ✓")
    
    # 3. 横盘控制
    price_range = df['成交价'].max() - df['成交价'].min()
    price_volatility = (price_range / df['成交价'].mean()) * 100
    
    print(f"\n3️⃣ 横盘控制")
    print(f"   价格区间: {df['成交价'].min():.2f} - {df['成交价'].max():.2f}元")
    print(f"   波动幅度: {price_volatility:.2f}%")
    print(f"   控盘判断: {'✓ 价格被控制' if price_volatility < 2 else '✗ 波动较大'}")
    
    # 4. 抛压释放
    small_sell = df[(df['类型'] == '小单') & (df['性质'] == '卖盘')]
    small_sell_amount = small_sell['成交金额'].sum()
    big_buy_amount = big_buy['成交金额'].sum()
    
    absorption_ratio = (small_sell_amount / big_buy_amount * 100) if big_buy_amount > 0 else 0
    
    print(f"\n4️⃣ 抛压释放")
    print(f"   散户卖单: {small_sell_amount/10000:.2f}万元")
    print(f"   主力买单: {big_buy_amount/10000:.2f}万元")
    print(f"   吸收比例: {absorption_ratio:.1f}%")
    print(f"   释放判断: {'✓ 抛压被吸收' if absorption_ratio < 150 else '✗ 抛压过大'}")
    
    # 5. 尾盘回落
    closing_data = df[df['时间'] > '14:30:00']
    intraday_high = df['成交价'].max()
    closing_price = df.iloc[-1]['成交价']
    support_price = big_buy['成交价'].mean()
    
    pullback = (intraday_high - closing_price) / intraday_high * 100
    hold_support = closing_price >= support_price * 0.98
    
    print(f"\n5️⃣ 尾盘回落")
    print(f"   盘中最高: {intraday_high:.2f}元")
    print(f"   收盘价: {closing_price:.2f}元")
    print(f"   回落幅度: {pullback:.2f}%")
    print(f"   支撑位: {support_price:.2f}元")
    print(f"   守住支撑: {'✓ 是' if hold_support else '✗ 否'}")
    
    # 6. 综合评分
    score = 0
    if len(big_buy) >= 3:
        score += 30  # 持续托价
    if price_volatility < 2:
        score += 25  # 横盘控制
    if absorption_ratio < 150:
        score += 25  # 抛压释放
    if pullback > 0.5 and hold_support:
        score += 20  # 尾盘回落
    
    print(f"\n" + "=" * 70)
    print(f"【综合评分】")
    print("=" * 70)
    print(f"   总分: {score}/100")
    
    if score >= 80:
        print(f"   评级: 🌟🌟🌟 强烈买入信号")
        print(f"   建议: 第二天低开到支撑位{support_price:.2f}元附近买入")
    elif score >= 60:
        print(f"   评级: 🌟🌟 买入信号")
        print(f"   建议: 观察第二天是否再次托价")
    else:
        print(f"   评级: 🌟 观察信号")
        print(f"   建议: 信号不够强，继续观察")
    
    # 7. 操作建议
    print(f"\n" + "=" * 70)
    print(f"【操作建议】")
    print("=" * 70)
    print(f"   买入价位: {support_price:.2f} ± 0.05元")
    print(f"   止损位: {support_price * 0.98:.2f}元 (-2%)")
    print(f"   止盈位: {support_price * 1.10:.2f}元 (+10%)")
    print(f"   持仓周期: 3-5天")
    
    return score

def main():
    """主函数"""
    print("=" * 70)
    print("大单吃货策略测试")
    print("=" * 70)
    print("\n策略核心：")
    print("  1. 大单托价 - 主力主动买入，托住价格")
    print("  2. 释放抛压 - 让散户卖单在托价位成交")
    print("  3. 横盘吸筹 - 价格被控制，持续建仓")
    print("  4. 再次托价 - 确认主力还在控盘")
    print("  5. 尾盘回落 - 洗盘+隐蔽+降成本")
    
    # 创建模拟数据
    df = create_mock_tick_data()
    
    # 分析模式
    score = analyze_big_order_pattern(df)
    
    print("\n" + "=" * 70)
    print("测试完成！")
    print("=" * 70)
    print("\n💡 关键理解：")
    print("   尾盘回落不是坏事，反而是强烈买入信号！")
    print("   主力的三个目的：")
    print("   1. 洗盘 - 吓出短线客")
    print("   2. 隐蔽 - 不想上龙虎榜")
    print("   3. 降成本 - 第二天继续吸")
    print("\n📅 实战使用：")
    print("   - 交易日收盘后运行: python analyze_closing_pullback.py")
    print("   - 找出有'托价+回落'信号的股票")
    print("   - 第二天低开时买入")

if __name__ == '__main__':
    main()
