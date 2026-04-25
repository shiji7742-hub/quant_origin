#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
扫描2026年1月20日的所有信号股票
找出和久其软件同时发出"盘中托价+尾盘回落"信号的股票
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime
import time

def should_filter_stock(name: str, market_cap: float = None) -> tuple:
    """
    判断是否应该过滤掉这只股票
    
    过滤规则：
    1. 大市值股票（市值>1000亿）
    2. 银行板块
    3. 白酒板块
    4. 保险板块
    5. 券商板块
    6. 热门题材（商业航天等）
    
    Returns:
        (should_filter, reason)
    """
    
    # 权重板块关键词
    weight_sectors = ['银行', '保险', '券商', '证券']
    for keyword in weight_sectors:
        if keyword in name:
            return True, f"权重板块-{keyword}"
    
    # 白酒板块
    if '茅台' in name or '五粮液' in name or '泸州老窖' in name or '洋河' in name:
        return True, "白酒板块"
    
    # 热门题材
    hot_themes = ['航天', '卫星', '火箭', '空间']
    for keyword in hot_themes:
        if keyword in name:
            return True, f"热门题材-{keyword}"
    
    # 大市值（如果有市值数据）
    if market_cap and market_cap > 100000000000:  # 1000亿
        return True, "大市值"
    
    return False, None


def analyze_stock_20260120(symbol: str, name: str) -> dict:
    """分析单只股票在1月20日的表现"""
    
    # 先过滤
    should_filter, reason = should_filter_stock(name)
    if should_filter:
        return {'filtered': True, 'reason': reason}
    
    try:
        # 获取日K线数据
        df_daily = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
        df_daily['日期'] = pd.to_datetime(df_daily['日期'])
        
        # 找到1月20日的数据
        target_date = pd.to_datetime('2026-01-20')
        day_data = df_daily[df_daily['日期'] == target_date]
        
        if len(day_data) == 0:
            return None
        
        day_data = day_data.iloc[0]
        
        # 获取分时数据
        df_min = ak.stock_zh_a_hist_min_em(
            symbol=symbol, 
            period='1', 
            adjust='', 
            start_date='2026-01-20 09:30:00', 
            end_date='2026-01-20 15:00:00'
        )
        
        if df_min is None or len(df_min) == 0:
            return None
        
        df_min['时间'] = pd.to_datetime(df_min['时间'])
        df_min = df_min.sort_values('时间')
        
        # 分析价格
        prices = df_min['收盘'].values
        price_min = prices.min()
        price_max = prices.max()
        
        # 找支撑位（价格集中区）
        bins = np.linspace(price_min, price_max, 20)
        hist, bin_edges = np.histogram(prices, bins=bins)
        max_count_idx = np.argmax(hist)
        support_price = (bin_edges[max_count_idx] + bin_edges[max_count_idx + 1]) / 2
        
        # 分析尾盘
        closing_df = df_min[df_min['时间'].dt.time >= pd.Timestamp('14:30').time()]
        
        if len(closing_df) == 0:
            return None
        
        closing_prices = closing_df['收盘'].values
        closing_final = closing_prices[-1]
        
        # 尾盘回落幅度
        intraday_high = day_data['最高']
        pullback = (intraday_high - closing_final) / intraday_high * 100
        
        # 相对支撑位的位置
        position_vs_support = (closing_final - support_price) / support_price * 100
        
        # 判断是否符合信号
        is_pullback = pullback > 1  # 尾盘回落>1%
        hold_support = closing_final >= support_price * 0.98  # 守住支撑
        
        is_signal = is_pullback and hold_support
        
        # 评分
        score = 0
        if is_pullback:
            score += 30
        if hold_support:
            score += 30
        if 3 < day_data['振幅'] < 8:
            score += 20
        if -2 < position_vs_support < 2:
            score += 20
        
        # 获取后续表现
        after_data = df_daily[df_daily['日期'] > target_date].head(3)
        
        if len(after_data) > 0:
            next_day = after_data.iloc[0]
            t1_return = (next_day['收盘'] - day_data['收盘']) / day_data['收盘'] * 100
            
            if len(after_data) >= 2:
                t2_return = (after_data.iloc[1]['收盘'] - day_data['收盘']) / day_data['收盘'] * 100
            else:
                t2_return = None
                
            if len(after_data) >= 3:
                t3_return = (after_data.iloc[2]['收盘'] - day_data['收盘']) / day_data['收盘'] * 100
            else:
                t3_return = None
        else:
            t1_return = None
            t2_return = None
            t3_return = None
        
        return {
            'symbol': symbol,
            'name': name,
            'is_signal': is_signal,
            'score': score,
            'open': day_data['开盘'],
            'close': day_data['收盘'],
            'high': day_data['最高'],
            'low': day_data['最低'],
            'change_pct': day_data['涨跌幅'],
            'amplitude': day_data['振幅'],
            'support_price': support_price,
            'pullback': pullback,
            'position_vs_support': position_vs_support,
            't1_return': t1_return,
            't2_return': t2_return,
            't3_return': t3_return
        }
        
    except Exception as e:
        print(f"  分析{name}({symbol})失败: {e}")
        return None


def scan_market_20260120():
    """扫描1月20日的市场"""
    
    print("=" * 70)
    print("扫描2026年1月20日 - 盘中托价+尾盘回落信号")
    print("=" * 70)
    
    # 获取1月20日的股票池
    print("\n获取股票池...")
    try:
        # 方法1：从涨幅榜获取
        print("尝试从涨幅榜获取...")
        df_spot = ak.stock_zh_a_spot_em()
        
        # 筛选条件
        stock_pool = df_spot[
            (df_spot['涨跌幅'] > -5) & 
            (df_spot['涨跌幅'] < 5) &
            (df_spot['最新价'] > 5) &
            (df_spot['最新价'] < 50)
        ]
        
        print(f"筛选出 {len(stock_pool)} 只股票")
        
        # 取前50只（减少数量，提高成功率）
        stock_pool = stock_pool.sort_values('成交额', ascending=False).head(50)
        print(f"选择成交额前50只进行分析")
        
    except Exception as e:
        print(f"方法1失败: {e}")
        print("\n使用备用股票池...")
        
        # 备用：手动指定一些活跃股票（包含各种类型用于测试过滤）
        stock_list = [
            ('002279', '久其软件'),      # 应该通过
            ('000001', '平安银行'),      # 应该被过滤-银行
            ('600000', '浦发银行'),      # 应该被过滤-银行
            ('000002', '万科A'),         # 应该通过
            ('600036', '招商银行'),      # 应该被过滤-银行
            ('601318', '中国平安'),      # 应该被过滤-保险
            ('000858', '五粮液'),        # 应该被过滤-白酒
            ('600519', '贵州茅台'),      # 应该被过滤-白酒
            ('000333', '美的集团'),      # 应该通过
            ('600276', '恒瑞医药'),      # 应该通过
            ('300059', '东方财富'),      # 应该被过滤-券商
            ('002230', '科大讯飞'),      # 应该通过
            ('300750', '宁德时代'),      # 应该通过
            ('688009', '中国卫星'),      # 应该被过滤-航天
            ('000063', '中兴通讯'),      # 应该通过
        ]
        
        stock_pool = pd.DataFrame(stock_list, columns=['代码', '名称'])
        print(f"使用备用股票池，共{len(stock_pool)}只")
    
    # 扫描
    results = []
    
    for i, row in stock_pool.iterrows():
        symbol = row['代码']
        name = row['名称']
        
        print(f"\n[{len(results)+1}/{len(stock_pool)}] 分析 {name}({symbol})...", end='')
        
        result = analyze_stock_20260120(symbol, name)
        
        if result is None:
            print(f" -")
        elif result.get('filtered'):
            print(f" [过滤] {result['reason']}")
        elif result.get('is_signal'):
            results.append(result)
            print(f" [OK] 发现信号! 评分:{result['score']}")
        else:
            print(f" -")
        
        time.sleep(0.3)  # 避免请求过快
    
    # 生成报告
    if not results:
        print("\n未发现符合条件的股票")
        return
    
    print(f"\n{'='*70}")
    print(f"共发现 {len(results)} 只股票符合信号")
    print(f"{'='*70}")
    
    # 按评分排序
    results.sort(key=lambda x: x['score'], reverse=True)
    
    # 生成DataFrame
    report_data = []
    for r in results:
        report_data.append({
            '代码': r['symbol'],
            '名称': r['name'],
            '评分': r['score'],
            '开盘': f"{r['open']:.2f}",
            '收盘': f"{r['close']:.2f}",
            '最高': f"{r['high']:.2f}",
            '最低': f"{r['low']:.2f}",
            '涨跌幅': f"{r['change_pct']:.2f}%",
            '振幅': f"{r['amplitude']:.2f}%",
            '支撑位': f"{r['support_price']:.2f}",
            '回落幅度': f"{r['pullback']:.2f}%",
            '相对支撑': f"{r['position_vs_support']:+.2f}%",
            'T+1收益': f"{r['t1_return']:.2f}%" if r['t1_return'] else '-',
            'T+2收益': f"{r['t2_return']:.2f}%" if r['t2_return'] else '-',
            'T+3收益': f"{r['t3_return']:.2f}%" if r['t3_return'] else '-'
        })
    
    df_report = pd.DataFrame(report_data)
    
    # 保存Excel
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'20260120信号股票_{timestamp}.xlsx'
    df_report.to_excel(filename, index=False, engine='openpyxl')
    
    print(f"\n报告已保存: {filename}")
    
    # 打印TOP20
    print(f"\n【信号强度TOP20】")
    print(df_report.head(20).to_string(index=False))
    
    # 统计后续表现
    print(f"\n【后续表现统计】")
    
    t1_returns = [r['t1_return'] for r in results if r['t1_return'] is not None]
    if t1_returns:
        print(f"T+1平均收益: {np.mean(t1_returns):.2f}%")
        print(f"T+1上涨概率: {len([x for x in t1_returns if x > 0]) / len(t1_returns) * 100:.1f}%")
    
    t2_returns = [r['t2_return'] for r in results if r['t2_return'] is not None]
    if t2_returns:
        print(f"T+2平均收益: {np.mean(t2_returns):.2f}%")
        print(f"T+2上涨概率: {len([x for x in t2_returns if x > 0]) / len(t2_returns) * 100:.1f}%")
    
    t3_returns = [r['t3_return'] for r in results if r['t3_return'] is not None]
    if t3_returns:
        print(f"T+3平均收益: {np.mean(t3_returns):.2f}%")
        print(f"T+3上涨概率: {len([x for x in t3_returns if x > 0]) / len(t3_returns) * 100:.1f}%")
    
    print(f"\n{'='*70}")


def main():
    scan_market_20260120()


if __name__ == '__main__':
    main()
