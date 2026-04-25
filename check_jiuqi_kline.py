# -*- coding: utf-8 -*-
import requests
import os
for key in list(os.environ.keys()):
    if 'proxy' in key.lower():
        del os.environ[key]
session = requests.Session()
session.trust_env = False
session.headers.update({'User-Agent': 'Mozilla/5.0'})

code = '002279'
kcode = f'sz{code}'
url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={kcode},day,,,30,qfq'
r = session.get(url, timeout=15)
data = r.json()
days_data = data['data'][kcode]['qfqday']

print("="*75)
print("久其软件 002279 近期K线分析")
print("="*75)
print(f"{'日期':<12} {'开盘':>8} {'最高':>8} {'最低':>8} {'收盘':>8} {'振幅%':>8} {'备注':<15}")
print("-"*75)

for d in days_data[-12:]:
    date = d[0]
    open_p = float(d[1])
    close = float(d[2])
    high = float(d[3])
    low = float(d[4])
    
    # 计算振幅
    amplitude = (high - low) / low * 100
    change = (close - open_p) / open_p * 100
    
    # 标记
    mark = ''
    if date >= '2026-01-20':
        mark = '<- 对敲期'
        if amplitude > 4:
            mark += ' 大振幅!'
    
    print(f"{date:<12} {open_p:>8.2f} {high:>8.2f} {low:>8.2f} {close:>8.2f} {amplitude:>8.2f} {mark:<15}")

print("-"*75)

# 分析对敲期
print("\n【对敲期分析 1/20-1/26】")
duiqiao_days = [d for d in days_data if d[0] >= '2026-01-20']
if duiqiao_days:
    highs = [float(d[3]) for d in duiqiao_days]
    lows = [float(d[4]) for d in duiqiao_days]
    closes = [float(d[2]) for d in duiqiao_days]
    
    print(f"  区间最高: {max(highs):.2f}")
    print(f"  区间最低: {min(lows):.2f}")
    print(f"  区间振幅: {(max(highs)-min(lows))/min(lows)*100:.2f}%")
    print(f"  收盘区间: {min(closes):.2f} - {max(closes):.2f}")
    
    # 判断是否在收窄
    first_amp = (float(duiqiao_days[0][3]) - float(duiqiao_days[0][4])) / float(duiqiao_days[0][4]) * 100
    last_amp = (float(duiqiao_days[-1][3]) - float(duiqiao_days[-1][4])) / float(duiqiao_days[-1][4]) * 100
    
    print(f"\n  首日振幅: {first_amp:.2f}%")
    print(f"  今日振幅: {last_amp:.2f}%")
    
    if last_amp > first_amp:
        print("  -> 振幅放大，今天可能是变盘日!")
    else:
        print("  -> 振幅收窄，继续震荡")
