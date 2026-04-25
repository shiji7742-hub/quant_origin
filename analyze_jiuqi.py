# -*- coding: utf-8 -*-
"""
分析久其软件 002279 的分时盘口
观察主力尾盘对敲形态
"""
import requests
import os
from datetime import datetime

# 清理代理
for key in list(os.environ.keys()):
    if 'proxy' in key.lower():
        del os.environ[key]

session = requests.Session()
session.trust_env = False
session.headers.update({'User-Agent': 'Mozilla/5.0'})

code = '002279'  # 久其软件
kcode = f'sz{code}'

print("="*60)
print("久其软件 002279 分时盘口分析")
print("="*60)

# 1. 获取实时行情
url = f'http://qt.gtimg.cn/q={kcode}'
r = session.get(url, timeout=10)
parts = r.text.split('~')

print(f"\n【实时行情】")
print(f"现价: {parts[3]}元  涨跌: {parts[32]}%")
print(f"今开: {parts[5]}  最高: {parts[33]}  最低: {parts[34]}")
print(f"成交: {float(parts[6])/100:.0f}手  金额: {float(parts[37])/10000:.0f}万  换手: {parts[38]}%")
print(f"时间: {parts[30]}")

# 2. 5档盘口
print(f"\n【5档盘口】")
print("-"*40)
try:
    print(f"卖5: {parts[27]:>8} x {float(parts[17])/100:>6.0f}手")
    print(f"卖4: {parts[26]:>8} x {float(parts[16])/100:>6.0f}手")
    print(f"卖3: {parts[25]:>8} x {float(parts[15])/100:>6.0f}手")
    print(f"卖2: {parts[24]:>8} x {float(parts[14])/100:>6.0f}手")
    print(f"卖1: {parts[23]:>8} x {float(parts[13])/100:>6.0f}手")
    print("-"*40)
    print(f"买1: {parts[9]:>8} x {float(parts[10])/100:>6.0f}手")
    print(f"买2: {parts[11]:>8} x {float(parts[12])/100:>6.0f}手")
    print(f"买3: {parts[19]:>8} x {float(parts[20])/100:>6.0f}手")
    print(f"买4: {parts[21]:>8} x {float(parts[22])/100:>6.0f}手")
    print(f"买5: {parts[29]:>8} x {float(parts[28])/100:>6.0f}手")
except Exception as e:
    print(f"盘口解析错误: {e}")

# 3. 获取分时成交明细
print(f"\n【最近成交明细 - 大单】")
print("-"*60)

url2 = f'http://stock.gtimg.cn/data/index.php?appn=detail&action=data&c={kcode}&p=0'
try:
    r2 = session.get(url2, timeout=10)
    text = r2.text
    
    # 尝试多种解析方式
    trades = []
    if 'detail' in text:
        start = text.find('"') + 1
        end = text.rfind('"')
        data_str = text[start:end]
        raw_trades = data_str.split('|')
        
        for t in raw_trades:
            if '/' in t:
                parts_t = t.split('/')
                if len(parts_t) >= 4:
                    try:
                        # 尝试解析，跳过无效数据
                        time_str = parts_t[0]
                        price = float(parts_t[1])
                        volume = int(parts_t[2])
                        direction = parts_t[3]
                        trades.append({
                            'time': time_str,
                            'price': price,
                            'volume': volume,
                            'dir': direction
                        })
                    except:
                        continue
        
        print(f"{'时间':^10} {'价格':^8} {'手数':^8} {'方向':^6} {'金额万':^10}")
        print("-"*60)
        
        big_buy = 0
        big_sell = 0
        big_trades = []
        
        for t in trades:
            amount = t['price'] * t['volume'] / 10000
            
            # 统计大单 (200手以上)
            if t['volume'] >= 200:
                dir_text = '买入' if t['dir'] == 'B' else '卖出'
                big_trades.append({
                    'time': t['time'],
                    'price': t['price'],
                    'volume': t['volume'],
                    'dir': t['dir'],
                    'dir_text': dir_text,
                    'amount': amount
                })
                if t['dir'] == 'B':
                    big_buy += amount
                else:
                    big_sell += amount
        
        # 只显示最近20笔大单
        for t in big_trades[-20:]:
            print(f"{t['time']:^10} {t['price']:^8.2f} {t['volume']:^8} {t['dir_text']:^6} {t['amount']:^10.1f}")
        
        print("-"*60)
        print(f"\n【大单统计】")
        print(f"  大单买入: {big_buy:.1f}万")
        print(f"  大单卖出: {big_sell:.1f}万")
        print(f"  净流入:   {big_buy-big_sell:.1f}万")
        
        # 对敲特征分析
        print(f"\n【对敲特征分析】")
        print("-"*60)
        
        # 检查买卖是否接近（对敲特征）
        if abs(big_buy - big_sell) < max(big_buy, big_sell) * 0.2:
            print("  ! 买卖大单接近平衡 - 可能存在对敲")
        
        # 检查尾盘大单密集度
        late_trades = [t for t in big_trades if t['time'] >= '14:30']
        if len(late_trades) > 5:
            late_buy = sum(t['amount'] for t in late_trades if t['dir'] == 'B')
            late_sell = sum(t['amount'] for t in late_trades if t['dir'] == 'S')
            print(f"  尾盘(14:30后)大单: 买{late_buy:.1f}万 / 卖{late_sell:.1f}万")
            if len(late_trades) > len(big_trades) * 0.3:
                print("  ! 尾盘大单密集 - 主力活跃")
        
        # 检查价格波动与成交配合
        prices = [t['price'] for t in big_trades[-10:]]
        if prices:
            price_range = max(prices) - min(prices)
            avg_price = sum(prices) / len(prices)
            print(f"  近10笔大单价格区间: {min(prices):.2f} - {max(prices):.2f} (波动{price_range/avg_price*100:.2f}%)")
            if price_range / avg_price < 0.01:
                print("  ! 价格波动小但成交大 - 典型对敲特征")

except Exception as e:
    print(f"获取成交明细失败: {e}")

print("\n" + "="*60)
print("【对敲形态学习要点】")
print("="*60)
print("""
1. 买卖大单金额接近 - 自买自卖制造成交量
2. 尾盘大单密集 - 影响收盘价/次日竞价
3. 价格波动小但成交量大 - 主力控盘
4. 盘口买卖单突然放大 - 制造活跃假象
5. 成交明细买卖交替出现 - 左手倒右手
""")
