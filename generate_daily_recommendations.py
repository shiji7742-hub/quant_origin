#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
管理员工具：生成每日推荐股票
每天开盘前运行，生成 daily_recommendations.json
"""

import json
from datetime import datetime
import akshare as ak
from strategies import strategy_limit_up_washout, check_all_strategies
from new_washout_strategies import check_all_new_strategies

def scan_short_term():
    """扫描短线股票"""
    print("\n扫描短线股票...")
    results = []
    
    # 获取活跃股票
    try:
        df = ak.stock_zh_a_spot_em()
        # 筛选：涨幅-3%到+5%，成交额>1亿
        candidates = df[
            (df['涨跌幅'] > -3) & 
            (df['涨跌幅'] < 5) &
            (df['成交额'] > 100000000) &
            (~df['名称'].str.contains('ST'))
        ].head(50)
        
        for _, row in candidates.iterrows():
            code = row['代码']
            name = row['名称']
            
            try:
                # 获取历史数据
                hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
                if hist is None or len(hist) < 30:
                    continue
                
                hist = hist.tail(70)
                
                # 检测涨停破位洗盘
                result = strategy_limit_up_washout(hist, relaxed=True)
                if result['触发']:
                    results.append({
                        'code': code,
                        'name': name,
                        'price': float(row['最新价']),
                        'change': float(row['涨跌幅']),
                        'strategy': '涨停破位洗盘',
                        'reason': result['说明']
                    })
                    print(f"  ✓ {code} {name} - 涨停破位洗盘")
                    
                    if len(results) >= 10:
                        break
            except:
                continue
        
    except Exception as e:
        print(f"扫描失败: {e}")
    
    return results[:10]

def scan_medium_term():
    """扫描波段股票"""
    print("\n扫描波段股票...")
    results = []
    
    try:
        df = ak.stock_zh_a_spot_em()
        candidates = df[
            (df['涨跌幅'] > -5) & 
            (df['涨跌幅'] < 3) &
            (df['成交额'] > 50000000) &
            (~df['名称'].str.contains('ST'))
        ].head(50)
        
        for _, row in candidates.iterrows():
            code = row['代码']
            name = row['名称']
            
            try:
                hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
                if hist is None or len(hist) < 30:
                    continue
                
                hist = hist.tail(70)
                
                # 检测新策略
                new_strategies = check_all_new_strategies(hist)
                
                for strategy_name, result in new_strategies.items():
                    if result['触发'] and strategy_name in ['深度回调支撑', '缩量横盘整理']:
                        results.append({
                            'code': code,
                            'name': name,
                            'price': float(row['最新价']),
                            'change': float(row['涨跌幅']),
                            'strategy': strategy_name,
                            'reason': result['说明']
                        })
                        print(f"  ✓ {code} {name} - {strategy_name}")
                        break
                
                if len(results) >= 10:
                    break
            except:
                continue
        
    except Exception as e:
        print(f"扫描失败: {e}")
    
    return results[:10]

def scan_long_term():
    """扫描中长线股票"""
    print("\n扫描中长线股票...")
    results = []
    
    try:
        df = ak.stock_zh_a_spot_em()
        candidates = df[
            (df['涨跌幅'] > -8) & 
            (df['涨跌幅'] < 2) &
            (df['成交额'] > 30000000) &
            (~df['名称'].str.contains('ST'))
        ].head(50)
        
        for _, row in candidates.iterrows():
            code = row['代码']
            name = row['名称']
            
            try:
                hist = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
                if hist is None or len(hist) < 30:
                    continue
                
                hist = hist.tail(70)
                
                # 检测基础策略
                strategies = check_all_strategies(hist)
                
                for strategy_name, result in strategies.items():
                    if result['触发'] and strategy_name in ['底部放量', '突破平台']:
                        results.append({
                            'code': code,
                            'name': name,
                            'price': float(row['最新价']),
                            'change': float(row['涨跌幅']),
                            'strategy': strategy_name,
                            'reason': result['说明']
                        })
                        print(f"  ✓ {code} {name} - {strategy_name}")
                        break
                
                if len(results) >= 10:
                    break
            except:
                continue
        
    except Exception as e:
        print(f"扫描失败: {e}")
    
    return results[:10]

def generate_recommendations():
    """生成每日推荐"""
    print("=" * 70)
    print("生成每日推荐股票")
    print("=" * 70)
    
    # 扫描三种风格
    short_stocks = scan_short_term()
    medium_stocks = scan_medium_term()
    long_stocks = scan_long_term()
    
    # 生成JSON数据
    data = {
        'date': datetime.now().strftime('%Y-%m-%d'),
        'short': short_stocks,
        'medium': medium_stocks,
        'long': long_stocks,
        'update_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'note': '数据由管理员每日开盘前更新'
    }
    
    # 保存到文件
    with open('daily_recommendations.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print("\n" + "=" * 70)
    print("生成完成！")
    print("=" * 70)
    print(f"短线推荐: {len(short_stocks)} 只")
    print(f"波段推荐: {len(medium_stocks)} 只")
    print(f"中长线推荐: {len(long_stocks)} 只")
    print(f"\n数据已保存到: daily_recommendations.json")
    print(f"更新时间: {data['update_time']}")

if __name__ == '__main__':
    generate_recommendations()
