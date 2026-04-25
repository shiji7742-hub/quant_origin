"""测试批量请求"""
import requests
import json
import os
import time

for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    if key in os.environ:
        del os.environ[key]

session = requests.Session()
session.trust_env = False

codes = ['600000', '000001', '000002', '600519', '000858']

print("测试批量K线请求...")
print("="*50)

for i, code in enumerate(codes):
    if code.startswith('6'):
        kcode = f'sh{code}'
    else:
        kcode = f'sz{code}'
    
    try:
        url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={kcode},day,,,10,qfq'
        r = session.get(url, timeout=5)
        data = r.json()
        
        if data.get('data'):
            stock_data = data['data'].get(kcode) or data['data'].get(kcode.upper())
            if stock_data and 'qfqday' in stock_data:
                days = stock_data['qfqday']
                print(f"{i+1}. {code}: OK - {len(days)}条 最新{days[-1][0]}")
            else:
                print(f"{i+1}. {code}: 无qfqday")
        else:
            print(f"{i+1}. {code}: 无data - {r.text[:100]}")
    except Exception as e:
        print(f"{i+1}. {code}: 错误 - {e}")
    
    time.sleep(0.1)

print("\n" + "="*50)
print("如果全部OK，说明接口正常，不是限流问题")
