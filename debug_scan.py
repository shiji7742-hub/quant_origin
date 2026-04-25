"""调试扫描 - 检查数据"""
import requests
import pandas as pd
import json
import os

for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    if key in os.environ:
        del os.environ[key]

session = requests.Session()
session.trust_env = False

# 测试几只股票
test_codes = ['600000', '000001', '300308', '000002', '600519']

print("调试: 检查K线数据和评分")
print("="*60)

for code in test_codes:
    print(f"\n{code}:")
    
    try:
        if code.startswith('6'):
            kcode = f'sh{code}'
        else:
            kcode = f'sz{code}'
        
        url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={kcode},day,,,60,qfq'
        r = session.get(url, timeout=10)
        data = r.json()
        
        if not data.get('data'):
            print("  无data字段")
            continue
            
        stock_data = data['data'].get(kcode) or data['data'].get(kcode.upper())
        if not stock_data:
            print("  无stock_data")
            continue
            
        if 'qfqday' not in stock_data:
            print("  无qfqday")
            continue
        
        days = stock_data['qfqday']
        print(f"  K线天数: {len(days)}")
        print(f"  最新日期: {days[-1][0]}")
        print(f"  最新数据: 开{days[-1][1]} 收{days[-1][2]} 高{days[-1][3]} 低{days[-1][4]} 量{days[-1][5]}")
        
        # 计算指标
        df = pd.DataFrame(days, columns=['日期','开盘','收盘','最高','最低','成交量'])
        for col in ['开盘','收盘','最高','最低','成交量']:
            df[col] = df[col].astype(float)
        
        df['MA5'] = df['收盘'].rolling(5).mean()
        df['MA10'] = df['收盘'].rolling(10).mean()
        df['MA20'] = df['收盘'].rolling(20).mean()
        df['VOL_MA5'] = df['成交量'].rolling(5).mean()
        
        latest = df.iloc[-1]
        
        print(f"  MA5={latest['MA5']:.2f} MA10={latest['MA10']:.2f} MA20={latest['MA20']:.2f}")
        print(f"  收盘={latest['收盘']:.2f} 开盘={latest['开盘']:.2f}")
        
        vol_ratio = latest['成交量'] / latest['VOL_MA5'] if latest['VOL_MA5'] > 0 else 0
        print(f"  量比={vol_ratio:.2f}")
        
        box_high = df.iloc[-16:-1]['最高'].max()
        print(f"  箱体高点={box_high:.2f}")
        
        # 评分
        score = 0
        if latest['MA5'] > latest['MA10'] > latest['MA20']:
            score += 25
            print("  +25 均线多头")
        if vol_ratio > 1.2:
            score += 20
            print("  +20 放量")
        if latest['收盘'] > latest['开盘']:
            score += 15
            print("  +15 收阳")
        if latest['收盘'] > latest['MA20']:
            score += 20
            print("  +20 站上MA20")
        if latest['收盘'] > box_high:
            score += 20
            print("  +20 箱体突破")
        
        print(f"  总评分: {score}")
        
    except Exception as e:
        print(f"  错误: {e}")
