#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
扫描2026年1月23日的信号股票
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime
import time
from functools import wraps


def retry_on_error(max_retries=5, delay=2):
    """重试装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt < max_retries - 1:
                        wait_time = delay * (2 ** attempt)
                        time.sleep(wait_time)
                    else:
                        return None
            return None
        return wrapper
    return decorator


def should_filter_stock(name: str, price: float = None) -> tuple:
    """过滤不适合的股票"""
    
    # ST股票
    if 'ST' in name or 'st' in name or '*' in name:
        return True, "ST股票"
    
    # 权重板块
    weight_sectors = ['银行', '保险', '券商', '证券', '信托']
    for keyword in weight_sectors:
        if keyword in name:
            return True, f"权重-{keyword}"
    
    # 白酒
    if any(x in name for x in ['茅台', '五粮液', '泸州', '洋河', '汾酒', '古井']):
        return True, "白酒"
    
    # 热门题材
    hot_themes = ['航天', '卫星', '火箭', '空间', '低空']
    for keyword in hot_themes:
        if keyword in name:
            return True, f"热门-{keyword}"
    
    # 价格过滤
    if price:
        if price < 3:
            return True, "低价股"
        if price > 100:
            return True, "超高价"
    
    return False, None


@retry_on_error(max_retries=5, delay=2)
def get_stock_data(symbol: str):
    """获取股票数据（带重试）"""
    return ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")


def analyze_stock_20260123(symbol: str, name: str) -> dict:
    """分析单只股票在1月23日的表现"""
    
    try:
        # 获取日K线数据
        df = get_stock_data(symbol)
        
        if df is None:
            return None
        
        df['日期'] = pd.to_datetime(df['日期'])
        
        # 找到1月23日的数据
        target_date = pd.to_datetime('2026-01-23')
        day_data = df[df['日期'] == target_date]
        
        if len(day_data) == 0:
            return None
        
        day_data = day_data.iloc[0]
        
        # 过滤
        should_filter, reason = should_filter_stock(name, day_data['收盘'])
        if should_filter:
            return None
        
        # 基本过滤
        if abs(day_data['涨跌幅']) > 9.5:
            return None
        if day_data['振幅'] < 1.5 or day_data['振幅'] > 20:
            return None
        if day_data['成交量'] < 50:
            return None
        
        # 核心信号：尾盘回落
        pullback = (day_data['最高'] - day_data['收盘']) / day_data['最高'] * 100
        
        if pullback < 0.5:
            return None
        
        # 支撑位判断
        support_price = day_data['最低'] * 1.01
        hold_support = day_data['收盘'] >= support_price
        
        if not hold_support:
            return None
        
        # 评分
        score = 0
        if pullback >= 1:
            score += 30
        if pullback >= 2:
            score += 10
        if pullback >= 4:
            score += 10
        if hold_support:
            score += 30
        if 2 <= day_data['振幅'] <= 10:
            score += 20
        if -3 <= day_data['涨跌幅'] <= 5:
            score += 10
        
        if score < 70:
            return None
        
        # 获取后续表现（如果有的话）
        after_data = df[df['日期'] > target_date].head(3)
        
        if len(after_data) > 0:
            t1_return = (after_data.iloc[0]['收盘'] - day_data['收盘']) / day_data['收盘'] * 100
            
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
            'score': score,
            'open': day_data['开盘'],
            'close': day_data['收盘'],
            'high': day_data['最高'],
            'low': day_data['最低'],
            'change_pct': day_data['涨跌幅'],
            'amplitude': day_data['振幅'],
            'support_price': support_price,
            'pullback': pullback,
            't1_return': t1_return,
            't2_return': t2_return,
            't3_return': t3_return
        }
        
    except Exception as e:
        return None


def get_stock_pool():
    """获取股票池（无限重试）"""
    
    retry_count = 0
    
    while True:
        try:
            print(f"获取股票池... (尝试 {retry_count + 1})")
            df = ak.stock_zh_a_spot_em()
            
            print(f"  ✓ 成功获取数据!")
            print(f"  原始股票数: {len(df)}")
            
            # 过滤ST股票
            df = df[~df['名称'].str.contains('ST|st|\\*', regex=True, na=False)]
            print(f"  过滤ST后: {len(df)}")
            
            # 筛选条件
            df = df[
                (df['成交额'] > 50000000) &  # 成交额>5000万
                (df['最新价'] >= 5) &  # 价格>=5元
                (df['最新价'] <= 50) &  # 价格<=50元
                (df['涨跌幅'].abs() < 9.5)  # 非涨跌停
            ]
            print(f"  基本筛选后: {len(df)}")
            
            # 按成交额排序
            df = df.sort_values('成交额', ascending=False)
            
            stock_list = [(row['代码'], row['名称']) for _, row in df.iterrows()]
            print(f"  最终股票池: {len(stock_list)} 只")
            
            return stock_list
            
        except Exception as e:
            retry_count += 1
            print(f"  ✗ 获取失败: {e}")
            
            wait_time = min(3 * (2 ** min(retry_count - 1, 3)), 30)
            print(f"  等待 {wait_time} 秒后重试... (已尝试{retry_count}次)")
            time.sleep(wait_time)


def scan_market_20260123():
    """扫描1月23日的市场"""
    
    print("=" * 70)
    print("扫描2026年1月23日 - 盘中托价+尾盘回落信号")
    print("=" * 70)
    
    # 获取股票池
    stock_pool = get_stock_pool()
    
    # 扫描
    results = []
    total_checked = 0
    network_errors = 0
    
    print(f"\n开始扫描...")
    print(f"预计检查: {len(stock_pool)} 只股票")
    
    for i, (symbol, name) in enumerate(stock_pool):
        total_checked += 1
        
        # 显示进度
        if (i + 1) % 50 == 0:
            print(f"  进度: {i+1}/{len(stock_pool)} (发现{len(results)}个信号, 网络错误{network_errors}次)")
        
        result = analyze_stock_20260123(symbol, name)
        
        if result is None:
            network_errors += 1
        else:
            results.append(result)
            t1_str = f"T+1:{result['t1_return']:+.2f}%" if result['t1_return'] else "T+1:未知"
            print(f"  [信号] {name}({symbol}) 评分:{result['score']} 回落:{result['pullback']:.2f}% {t1_str}")
        
        time.sleep(1.5)  # 延迟
    
    # 生成报告
    print(f"\n{'='*70}")
    print(f"扫描完成！")
    print(f"{'='*70}")
    print(f"总检查: {total_checked}")
    print(f"网络错误: {network_errors} ({network_errors/total_checked*100:.1f}%)")
    print(f"发现信号: {len(results)}")
    
    if not results:
        print("\n未发现符合条件的股票")
        return
    
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
            'T+1收益': f"{r['t1_return']:.2f}%" if r['t1_return'] else '-',
            'T+2收益': f"{r['t2_return']:.2f}%" if r['t2_return'] else '-',
            'T+3收益': f"{r['t3_return']:.2f}%" if r['t3_return'] else '-'
        })
    
    df_report = pd.DataFrame(report_data)
    
    # 保存Excel
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'20260123信号股票_{timestamp}.xlsx'
    df_report.to_excel(filename, index=False, engine='openpyxl')
    
    print(f"\n报告已保存: {filename}")
    
    # 打印结果
    print(f"\n【信号强度排序】")
    print(df_report.to_string(index=False))
    
    # 统计后续表现
    if any(r['t1_return'] is not None for r in results):
        print(f"\n【后续表现统计】")
        
        t1_returns = [r['t1_return'] for r in results if r['t1_return'] is not None]
        if t1_returns:
            print(f"T+1平均收益: {np.mean(t1_returns):.2f}%")
            print(f"T+1上涨概率: {len([x for x in t1_returns if x > 0]) / len(t1_returns) * 100:.1f}%")
    
    print(f"\n{'='*70}")


def main():
    scan_market_20260123()


if __name__ == '__main__':
    main()
