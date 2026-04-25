#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
扫描2026年1月23日的信号股票 - 直接访问东方财富API
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime
import time
import json


def get_stock_list():
    """直接从东方财富获取股票列表（带重试）"""
    
    retry_count = 0
    
    while True:
        print(f"获取股票列表... (尝试 {retry_count + 1})")
        
        url = "http://80.push2.eastmoney.com/api/qt/clist/get"
        
        params = {
            'pn': '1',
            'pz': '5000',  # 获取5000只
            'po': '1',
            'np': '1',
            'fltt': '2',
            'invt': '2',
            'fid': 'f3',
            'fs': 'm:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23',  # A股
            'fields': 'f12,f14,f2,f3,f4,f5,f6,f7,f15,f16,f17,f18'
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            
            if response.status_code != 200:
                raise Exception(f"HTTP错误: {response.status_code}")
            
            data = response.json()
            
            if 'data' not in data or 'diff' not in data['data']:
                raise Exception("数据格式错误")
            
            stocks = data['data']['diff']
            
            print(f"  ✓ 成功获取 {len(stocks)} 只股票")
            
            # 转换为DataFrame
            stock_list = []
            for stock in stocks:
                stock_list.append({
                    '代码': stock['f12'],
                    '名称': stock['f14'],
                    '最新价': stock['f2'],
                    '涨跌幅': stock['f3'],
                    '涨跌额': stock['f4'],
                    '成交量': stock['f5'],
                    '成交额': stock['f6'],
                    '振幅': stock['f7'],
                    '最高': stock['f15'],
                    '最低': stock['f16'],
                    '今开': stock['f17'],
                    '昨收': stock['f18']
                })
            
            df = pd.DataFrame(stock_list)
            return df
            
        except Exception as e:
            retry_count += 1
            print(f"  ✗ 获取失败: {e}")
            
            wait_time = min(3 * (2 ** min(retry_count - 1, 3)), 30)
            print(f"  等待 {wait_time} 秒后重试... (已尝试{retry_count}次)")
            time.sleep(wait_time)


def get_stock_kline(stock_code: str):
    """获取股票K线数据"""
    
    # 判断市场代码
    if stock_code.startswith('6'):
        secid = f'1.{stock_code}'  # 上海
    else:
        secid = f'0.{stock_code}'  # 深圳
    
    url = "http://push2his.eastmoney.com/api/qt/stock/kline/get"
    
    params = {
        'secid': secid,
        'fields1': 'f1,f2,f3,f4,f5,f6',
        'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
        'klt': '101',  # 日K
        'fqt': '1',  # 前复权
        'beg': '20260101',
        'end': '20260131'
    }
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        if response.status_code != 200:
            return None
        
        data = response.json()
        
        if 'data' not in data or data['data'] is None:
            return None
        
        if 'klines' not in data['data']:
            return None
        
        klines = data['data']['klines']
        
        # 解析K线数据
        df_list = []
        for kline in klines:
            parts = kline.split(',')
            df_list.append({
                '日期': parts[0],
                '开盘': float(parts[1]),
                '收盘': float(parts[2]),
                '最高': float(parts[3]),
                '最低': float(parts[4]),
                '成交量': float(parts[5]),
                '成交额': float(parts[6]),
                '振幅': float(parts[7]),
                '涨跌幅': float(parts[8]),
                '涨跌额': float(parts[9]),
                '换手率': float(parts[10])
            })
        
        df = pd.DataFrame(df_list)
        df['日期'] = pd.to_datetime(df['日期'])
        
        return df
        
    except Exception as e:
        return None


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


def analyze_stock_20260123(stock_code: str, stock_name: str) -> dict:
    """分析单只股票在1月23日的表现"""
    
    try:
        # 获取K线数据
        df = get_stock_kline(stock_code)
        
        if df is None or len(df) == 0:
            return None
        
        # 找到1月23日的数据
        target_date = pd.to_datetime('2026-01-23')
        day_data = df[df['日期'] == target_date]
        
        if len(day_data) == 0:
            return None
        
        day_data = day_data.iloc[0]
        
        # 过滤
        should_filter, reason = should_filter_stock(stock_name, day_data['收盘'])
        if should_filter:
            return None
        
        # 基本过滤
        if abs(day_data['涨跌幅']) > 9.5:
            return None
        if day_data['振幅'] < 1.5 or day_data['振幅'] > 20:
            return None
        if day_data['成交量'] < 5000:
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
        
        # 获取后续表现
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
            'symbol': stock_code,
            'name': stock_name,
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


def scan_market_20260123():
    """扫描1月23日的市场"""
    
    print("=" * 70)
    print("扫描2026年1月23日 - 盘中托价+尾盘回落信号 (直接API)")
    print("=" * 70)
    
    # 获取股票列表
    stock_list = get_stock_list()
    
    if stock_list is None:
        print("获取股票列表失败")
        return
    
    # 过滤ST股票
    stock_list = stock_list[~stock_list['名称'].str.contains('ST|st|\\*', regex=True, na=False)]
    print(f"  过滤ST后: {len(stock_list)} 只")
    
    # 筛选条件
    stock_list = stock_list[
        (stock_list['成交额'] > 50000000) &  # 成交额>5000万
        (stock_list['最新价'] >= 5) &  # 价格>=5元
        (stock_list['最新价'] <= 50) &  # 价格<=50元
        (stock_list['涨跌幅'].abs() < 9.5)  # 非涨跌停
    ]
    print(f"  基本筛选后: {len(stock_list)} 只")
    
    # 按成交额排序
    stock_list = stock_list.sort_values('成交额', ascending=False)
    
    print(f"  最终股票池: {len(stock_list)} 只")
    
    # 扫描
    results = []
    total_checked = 0
    errors = 0
    
    print(f"\n开始扫描...")
    
    for idx, row in stock_list.iterrows():
        stock_code = row['代码']
        stock_name = row['名称']
        total_checked += 1
        
        # 显示进度
        if total_checked % 50 == 0:
            print(f"  进度: {total_checked}/{len(stock_list)} (发现{len(results)}个信号, 错误{errors}次)")
        
        result = analyze_stock_20260123(stock_code, stock_name)
        
        if result is None:
            errors += 1
        else:
            results.append(result)
            t1_str = f"T+1:{result['t1_return']:+.2f}%" if result['t1_return'] else "T+1:未知"
            print(f"  [信号] {stock_name}({stock_code}) 评分:{result['score']} 回落:{result['pullback']:.2f}% {t1_str}")
        
        time.sleep(0.3)  # 延迟
    
    # 生成报告
    print(f"\n{'='*70}")
    print(f"扫描完成！")
    print(f"{'='*70}")
    print(f"总检查: {total_checked}")
    print(f"错误: {errors} ({errors/total_checked*100:.1f}%)")
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
    filename = f'20260123信号股票_直接API_{timestamp}.xlsx'
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
