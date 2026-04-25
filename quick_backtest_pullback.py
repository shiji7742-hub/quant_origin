#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速回测 - 选择几个关键日期验证策略
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime
import time

# 从scan_date_20260120.py复制过来的函数
def should_filter_stock(name: str, price: float = None) -> tuple:
    """判断是否应该过滤股票"""
    weight_sectors = ['银行', '保险', '券商', '证券']
    for keyword in weight_sectors:
        if keyword in name:
            return True, f"权重板块-{keyword}"
    
    if '茅台' in name or '五粮液' in name or '泸州老窖' in name or '洋河' in name:
        return True, "白酒板块"
    
    hot_themes = ['航天', '卫星', '火箭', '空间']
    for keyword in hot_themes:
        if keyword in name:
            return True, f"热门题材-{keyword}"
    
    if price and price < 3:
        return True, "低价股"
    if price and price > 100:
        return True, "超高价股"
    
    return False, None


def analyze_stock_on_date(symbol: str, name: str, date: str) -> dict:
    """分析单只股票在某一天的表现"""
    
    try:
        df_daily = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
        df_daily['日期'] = pd.to_datetime(df_daily['日期'])
        
        target_date = pd.to_datetime(date)
        day_data = df_daily[df_daily['日期'] == target_date]
        
        if len(day_data) == 0:
            return None
        
        day_data = day_data.iloc[0]
        
        # 过滤
        should_filter, reason = should_filter_stock(name, day_data['收盘'])
        if should_filter:
            return {'filtered': True, 'reason': reason}
        
        # 基本过滤
        if abs(day_data['涨跌幅']) > 9:
            return None
        if day_data['振幅'] < 2 or day_data['振幅'] > 15:
            return None
        
        # 尾盘回落
        pullback = (day_data['最高'] - day_data['收盘']) / day_data['最高'] * 100
        
        if pullback < 1:
            return None
        
        # 支撑位
        support_price = day_data['最低'] * 1.01
        hold_support = day_data['收盘'] >= support_price
        
        if not hold_support:
            return None
        
        # 评分
        score = 0
        if pullback > 1:
            score += 30
        if pullback > 3:
            score += 10
        if hold_support:
            score += 30
        if 3 < day_data['振幅'] < 8:
            score += 20
        if -2 < day_data['涨跌幅'] < 3:
            score += 10
        
        if score < 80:
            return None
        
        # 后续表现
        after_data = df_daily[df_daily['日期'] > target_date].head(5)
        
        returns = []
        for i in range(min(5, len(after_data))):
            ret = (after_data.iloc[i]['收盘'] - day_data['收盘']) / day_data['收盘'] * 100
            returns.append(ret)
        
        while len(returns) < 5:
            returns.append(None)
        
        return {
            'symbol': symbol,
            'name': name,
            'date': date,
            'score': score,
            'close': day_data['收盘'],
            'change_pct': day_data['涨跌幅'],
            'amplitude': day_data['振幅'],
            'pullback': pullback,
            't1': returns[0],
            't2': returns[1],
            't3': returns[2],
            't4': returns[3],
            't5': returns[4]
        }
        
    except Exception as e:
        return None


def quick_backtest():
    """快速回测"""
    
    print("=" * 70)
    print("快速回测 - 盘中托价+尾盘回落策略")
    print("=" * 70)
    
    # 选择几个关键日期
    test_dates = [
        '2026-01-20',  # 久其软件的日期
        '2026-01-17',
        '2026-01-16',
        '2026-01-15',
        '2026-01-14',
        '2026-01-13',
        '2026-01-10',
        '2026-01-09',
        '2026-01-08',
        '2026-01-07',
    ]
    
    # 股票池（活跃的中小市值股票）
    stock_list = [
        ('002279', '久其软件'),
        ('000002', '万科A'),
        ('000333', '美的集团'),
        ('600276', '恒瑞医药'),
        ('002230', '科大讯飞'),
        ('000063', '中兴通讯'),
        ('002475', '立讯精密'),
        ('002594', '比亚迪'),
        ('300059', '东方财富'),
        ('600519', '贵州茅台'),  # 测试过滤
        ('000001', '平安银行'),  # 测试过滤
        ('002371', '北方华创'),
        ('688981', '中芯国际'),
        ('300750', '宁德时代'),
        ('002415', '海康威视'),
    ]
    
    all_signals = []
    
    for date in test_dates:
        print(f"\n{'='*70}")
        print(f"日期: {date}")
        print(f"{'='*70}")
        
        day_signals = []
        
        for symbol, name in stock_list:
            result = analyze_stock_on_date(symbol, name, date)
            
            if result:
                if result.get('filtered'):
                    print(f"  [过滤] {name}({symbol}) - {result['reason']}")
                else:
                    day_signals.append(result)
                    print(f"  [OK] {name}({symbol}) 评分:{result['score']} T+1:{result['t1']:.2f}%" if result['t1'] else f"  [OK] {name}({symbol}) 评分:{result['score']}")
        
        all_signals.extend(day_signals)
        print(f"\n当日发现 {len(day_signals)} 个信号")
        
        time.sleep(0.5)
    
    # 统计
    if not all_signals:
        print("\n未发现信号")
        return
    
    df = pd.DataFrame(all_signals)
    
    print(f"\n{'='*70}")
    print(f"回测结果汇总")
    print(f"{'='*70}")
    print(f"总信号数: {len(df)}")
    
    # T+1统计
    t1_data = df[df['t1'].notna()]
    if len(t1_data) > 0:
        win_rate = len(t1_data[t1_data['t1'] > 0]) / len(t1_data) * 100
        avg_return = t1_data['t1'].mean()
        median_return = t1_data['t1'].median()
        
        print(f"\nT+1表现:")
        print(f"  样本数: {len(t1_data)}")
        print(f"  胜率: {win_rate:.1f}%")
        print(f"  平均收益: {avg_return:.2f}%")
        print(f"  中位数收益: {median_return:.2f}%")
        print(f"  最大收益: {t1_data['t1'].max():.2f}%")
        print(f"  最大亏损: {t1_data['t1'].min():.2f}%")
    
    # T+3统计
    t3_data = df[df['t3'].notna()]
    if len(t3_data) > 0:
        win_rate = len(t3_data[t3_data['t3'] > 0]) / len(t3_data) * 100
        avg_return = t3_data['t3'].mean()
        
        print(f"\nT+3表现:")
        print(f"  样本数: {len(t3_data)}")
        print(f"  胜率: {win_rate:.1f}%")
        print(f"  平均收益: {avg_return:.2f}%")
    
    # 详细列表
    print(f"\n{'='*70}")
    print("所有信号详情")
    print(f"{'='*70}")
    print(df[['date', 'nam