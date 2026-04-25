#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
盘中托价+尾盘回落策略 - 历史回测
回测时间：2025年10月 - 2026年1月
验证策略有效性
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
from typing import List, Dict

def should_filter_stock(name: str, price: float = None) -> tuple:
    """判断是否应该过滤股票"""
    
    # 权重板块
    weight_sectors = ['银行', '保险', '券商', '证券']
    for keyword in weight_sectors:
        if keyword in name:
            return True, f"权重板块-{keyword}"
    
    # 白酒板块
    if '茅台' in name or '五粮液' in name or '泸州老窖' in name or '洋河' in name:
        return True, "白酒板块"
    
    # 热门题材（需要根据时期调整）
    hot_themes = ['航天', '卫星', '火箭', '空间']
    for keyword in hot_themes:
        if keyword in name:
            return True, f"热门题材-{keyword}"
    
    # 价格过滤
    if price:
        if price < 3:  # 低价股
            return True, "低价股"
        if price > 100:  # 超高价股
            return True, "超高价股"
    
    return False, None


def analyze_single_day(symbol: str, name: str, date: str) -> Dict:
    """分析单只股票在某一天的表现"""
    
    try:
        # 获取日K线数据
        df_daily = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
        df_daily['日期'] = pd.to_datetime(df_daily['日期'])
        
        # 找到目标日期
        target_date = pd.to_datetime(date)
        day_data = df_daily[df_daily['日期'] == target_date]
        
        if len(day_data) == 0:
            return None
        
        day_data = day_data.iloc[0]
        
        # 过滤检查
        should_filter, reason = should_filter_stock(name, day_data['收盘'])
        if should_filter:
            return {'filtered': True, 'reason': reason}
        
        # 基本条件过滤
        if day_data['涨跌幅'] > 9:  # 涨停
            return None
        if day_data['涨跌幅'] < -9:  # 跌停
            return None
        if day_data['振幅'] < 2:  # 振幅太小
            return None
        if day_data['振幅'] > 15:  # 振幅太大（可能是妖股）
            return None
        
        # 计算尾盘回落
        intraday_high = day_data['最高']
        close_price = day_data['收盘']
        pullback = (intraday_high - close_price) / intraday_high * 100
        
        # 判断是否符合信号
        is_pullback = pullback > 1  # 尾盘回落>1%
        
        if not is_pullback:
            return None
        
        # 简化版支撑位判断（用最低价作为支撑）
        support_price = day_data['最低'] * 1.01  # 最低价上方1%
        hold_support = close_price >= support_price
        
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
        
        # 获取后续表现
        after_data = df_daily[df_daily['日期'] > target_date].head(5)
        
        if len(after_data) > 0:
            returns = []
            for i in range(min(5, len(after_data))):
                ret = (after_data.iloc[i]['收盘'] - day_data['收盘']) / day_data['收盘'] * 100
                returns.append(ret)
            
            # 填充到5天
            while len(returns) < 5:
                returns.append(None)
            
            t1, t2, t3, t4, t5 = returns
        else:
            t1 = t2 = t3 = t4 = t5 = None
        
        return {
            'symbol': symbol,
            'name': name,
            'date': date,
            'score': score,
            'open': day_data['开盘'],
            'close': day_data['收盘'],
            'high': day_data['最高'],
            'low': day_data['最低'],
            'change_pct': day_data['涨跌幅'],
            'amplitude': day_data['振幅'],
            'pullback': pullback,
            't1': t1,
            't2': t2,
            't3': t3,
            't4': t4,
            't5': t5,
            'filtered': False
        }
        
    except Exception as e:
        return None


def get_trading_days(start_date: str, end_date: str) -> List[str]:
    """获取交易日列表"""
    try:
        # 使用上证指数获取交易日
        df = ak.stock_zh_index_daily(symbol="sh000001")
        df['date'] = pd.to_datetime(df['date'])
        
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        
        trading_days = df[
            (df['date'] >= start) & 
            (df['date'] <= end)
        ]['date'].dt.strftime('%Y-%m-%d').tolist()
        
        return trading_days
    except:
        # 备用方案：手动生成日期列表
        dates = []
        current = datetime.strptime(start_date, '%Y-%m-%d')
        end = datetime.strptime(end_date, '%Y-%m-%d')
        
        while current <= end:
            # 排除周末
            if current.weekday() < 5:
                dates.append(current.strftime('%Y-%m-%d'))
            current += timedelta(days=1)
        
        return dates


def backtest_strategy(start_date: str = '2025-10-01', end_date: str = '2026-01-24'):
    """回测策略"""
    
    print("=" * 70)
    print("盘中托价+尾盘回落策略 - 历史回测")
    print("=" * 70)
    print(f"回测期间: {start_date} 至 {end_date}")
    print("=" * 70)
    
    # 获取交易日
    print("\n获取交易日列表...")
    trading_days = get_trading_days(start_date, end_date)
    print(f"共 {len(trading_days)} 个交易日")
    
    # 获取股票池（使用最近的活跃股票）
    print("\n获取股票池...")
    try:
        df_spot = ak.stock_zh_a_spot_em()
        # 筛选：成交额>1亿，价格5-50元
        stock_pool = df_spot[
            (df_spot['成交额'] > 100000000) &
            (df_spot['最新价'] > 5) &
            (df_spot['最新价'] < 50)
        ]
        stock_pool = stock_pool.sort_values('成交额', ascending=False).head(200)
        print(f"选择成交额前200只股票")
    except:
        print("获取股票池失败，使用备用池")
        # 备用股票池
        stock_list = [
            ('002279', '久其软件'),
            ('000002', '万科A'),
            ('000333', '美的集团'),
            ('600276', '恒瑞医药'),
            ('002230', '科大讯飞'),
            ('300750', '宁德时代'),
            ('000063', '中兴通讯'),
            ('002475', '立讯精密'),
            ('300059', '东方财富'),
            ('002594', '比亚迪'),
        ]
        stock_pool = pd.DataFrame(stock_list, columns=['代码', '名称'])
    
    # 回测
    all_signals = []
    
    print(f"\n开始回测...")
    print(f"预计需要时间: {len(trading_days) * len(stock_pool) * 0.3 / 60:.1f} 分钟")
    
    for day_idx, date in enumerate(trading_days):
        print(f"\n[{day_idx+1}/{len(trading_days)}] {date}")
        
        day_signals = []
        
        for stock_idx, row in stock_pool.iterrows():
            symbol = row['代码']
            name = row['名称']
            
            result = analyze_single_day(symbol, name, date)
            
            if result and not result.get('filtered') and result.get('score', 0) >= 80:
                day_signals.append(result)
                print(f"  [OK] {name}({symbol}) 评分:{result['score']}")
        
        all_signals.extend(day_signals)
        
        print(f"  当日发现 {len(day_signals)} 个信号")
        
        # 避免请求过快
        time.sleep(1)
    
    # 生成报告
    if not all_signals:
        print("\n未发现符合条件的信号")
        return
    
    print(f"\n{'='*70}")
    print(f"回测完成！共发现 {len(all_signals)} 个信号")
    print(f"{'='*70}")
    
    # 生成DataFrame
    df_signals = pd.DataFrame(all_signals)
    
    # 保存Excel
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'回测结果_{start_date}至{end_date}_{timestamp}.xlsx'
    df_signals.to_excel(filename, index=False, engine='openpyxl')
    print(f"\n详细结果已保存: {filename}")
    
    # 统计分析
    print(f"\n{'='*70}")
    print("策略表现统计")
    print(f"{'='*70}")
    
    # 胜率统计
    t1_data = df_signals[df_signals['t1'].notna()]
    if len(t1_data) > 0:
        t1_win_rate = len(t1_data[t1_data['t1'] > 0]) / len(t1_data) * 100
        t1_avg = t1_data['t1'].mean()
        t1_median = t1_data['t1'].median()
        t1_max = t1_data['t1'].max()
        t1_min = t1_data['t1'].min()
        
        print(f"\nT+1表现:")
        print(f"  样本数: {len(t1_data)}")
        print(f"  胜率: {t1_win_rate:.1f}%")
        print(f"  平均收益: {t1_avg:.2f}%")
        print(f"  中位数收益: {t1_median:.2f}%")
        print(f"  最大收益: {t1_max:.2f}%")
        print(f"  最大亏损: {t1_min:.2f}%")
    
    t3_data = df_signals[df_signals['t3'].notna()]
    if len(t3_data) > 0:
        t3_win_rate = len(t3_data[t3_data['t3'] > 0]) / len(t3_data) * 100
        t3_avg = t3_data['t3'].mean()
        t3_median = t3_data['t3'].median()
        
        print(f"\nT+3表现:")
        print(f"  样本数: {len(t3_data)}")
        print(f"  胜率: {t3_win_rate:.1f}%")
        print(f"  平均收益: {t3_avg:.2f}%")
        print(f"  中位数收益: {t3_median:.2f}%")
    
    t5_data = df_signals[df_signals['t5'].notna()]
    if len(t5_data) > 0:
        t5_win_rate = len(t5_data[t5_data['t5'] > 0]) / len(t5_data) * 100
        t5_avg = t5_data['t5'].mean()
        
        print(f"\nT+5表现:")
        print(f"  样本数: {len(t5_data)}")
        print(f"  胜率: {t5_win_rate:.1f}%")
        print(f"  平均收益: {t5_avg:.2f}%")
    
    # 按评分分组统计
    print(f"\n{'='*70}")
    print("按评分分组统计")
    print(f"{'='*70}")
    
    score_groups = [
        (100, 110, "100-110分"),
        (90, 100, "90-100分"),
        (80, 90, "80-90分")
    ]
    
    for min_score, max_score, label in score_groups:
        group_data = df_signals[
            (df_signals['score'] >= min_score) & 
            (df_signals['score'] < max_score) &
            (df_signals['t1'].notna())
        ]
        
        if len(group_data) > 0:
            win_rate = len(group_data[group_data['t1'] > 0]) / len(group_data) * 100
            avg_return = group_data['t1'].mean()
            
            print(f"\n{label}:")
            print(f"  样本数: {len(group_data)}")
            print(f"  胜率: {win_rate:.1f}%")
            print(f"  平均收益: {avg_return:.2f}%")
    
    # TOP10信号
    print(f"\n{'='*70}")
    print("收益TOP10信号")
    print(f"{'='*70}")
    
    top10 = df_signals[df_signals['t1'].notna()].nlargest(10, 't1')
    print(top10[['date', 'name', 'score', 'pullback', 't1', 't3']].to_string(index=False))
    
    print(f"\n{'='*70}")


def main():
    # 回测最近3个月
    backtest_strategy(start_date='2025-10-01', end_date='2026-01-24')


if __name__ == '__main__':
    main()
