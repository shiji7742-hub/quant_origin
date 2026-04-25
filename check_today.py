# -*- coding: utf-8 -*-
"""检查昨日推荐股票今日表现"""
import requests
import os

for key in list(os.environ.keys()):
    if 'proxy' in key.lower():
        del os.environ[key]

session = requests.Session()
session.trust_env = False
session.headers.update({'User-Agent': 'Mozilla/5.0'})

# 昨日报告推荐的股票
stocks = [
    ('000685', '中山公用'),
    ('000823', '超声电子'),
    ('002456', '欧菲光'),
    ('300750', '宁德时代'),
    ('300207', '欣旺达'),
]

print('昨日报告推荐的股票 - 今日表现')
print('='*60)

results = []

for code, name in stocks:
    kcode = f'sh{code}' if code.startswith('6') else f'sz{code}'
    try:
        url = f'https://qt.gtimg.cn/q={kcode}'
        r = session.get(url, timeout=5)
        parts = r.text.split('~')
        if len(parts) > 34:
            stock_name = parts[1]
            price = float(parts[3])
            prev_close = float(parts[4])
            open_price = float(parts[5])
            high = float(parts[33])
            low = float(parts[34])
            
            open_change = (open_price - prev_close) / prev_close * 100
            current_change = (price - prev_close) / prev_close * 100
            intraday_range = (high - low) / prev_close * 100
            
            print(f'{code} {stock_name}')
            print(f'  昨收: {prev_close:.2f}  今开: {open_price:.2f}  现价: {price:.2f}')
            print(f'  开盘涨幅: {open_change:+.2f}%')
            print(f'  当前涨幅: {current_change:+.2f}%')
            print(f'  今日振幅: {intraday_range:.2f}%')
            
            # 判断走势
            if open_change < 0.3 and open_change > -0.3:
                open_type = '平开'
            elif open_change >= 0.3:
                open_type = '高开'
            else:
                open_type = '低开'
            
            if current_change < open_change - 0.5:
                trend = '下杀'
            elif current_change > open_change + 0.5:
                trend = '上攻'
            else:
                trend = '震荡'
            
            print(f'  走势: {open_type} -> {trend}')
            
            results.append({
                'code': code,
                'name': stock_name,
                'open_change': open_change,
                'current_change': current_change,
                'open_type': open_type,
                'trend': trend,
            })
            print()
    except Exception as e:
        print(f'{code}: 获取失败 {e}')

# 总结
print('='*60)
print('问题分析')
print('='*60)

down_count = sum(1 for r in results if r['current_change'] < 0)
flat_open_down = sum(1 for r in results if r['open_type'] == '平开' and r['trend'] == '下杀')

print(f'\n推荐股票数: {len(results)}')
print(f'今日下跌数: {down_count}')
print(f'平开下杀数: {flat_open_down}')

if flat_open_down >= len(results) * 0.6:
    print('\n【问题诊断】')
    print('多数股票出现"平开下杀"，可能原因：')
    print('1. 周五收盘时市场情绪较好，但周末有利空消息')
    print('2. 推荐的股票处于高位，获利盘周一出逃')
    print('3. 分时托单信号只看了上周五的形态，没考虑开盘风险')
    print('4. 没有结合大盘开盘情况进行判断')
