"""测试周末各接口可用性"""
import requests
import json
import os

for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    if key in os.environ:
        del os.environ[key]

print("="*60)
print("周末API可用性测试")
print("="*60)

session = requests.Session()
session.trust_env = False

# 1. 新浪K线接口
print("\n1. 新浪K线接口:")
try:
    url = 'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData'
    params = {'symbol': 'sh600000', 'scale': '240', 'ma': 'no', 'datalen': '5'}
    r = session.get(url, params=params, timeout=10)
    data = json.loads(r.text)
    if data:
        print(f"   OK - 最新日期: {data[-1]['day']}")
    else:
        print("   FAIL - 无数据")
except Exception as e:
    print(f"   FAIL - {e}")

# 2. 腾讯K线接口
print("\n2. 腾讯K线接口:")
try:
    url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh600000,day,,,5,qfq'
    r = session.get(url, timeout=10)
    data = r.json()
    if data.get('data', {}).get('sh600000', {}).get('qfqday'):
        days = data['data']['sh600000']['qfqday']
        print(f"   OK - 最新日期: {days[-1][0]}")
    else:
        print("   FAIL - 无数据")
except Exception as e:
    print(f"   FAIL - {e}")

# 3. 新浪股票列表接口
print("\n3. 新浪股票列表接口:")
try:
    url = 'https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData'
    params = {'page': 1, 'num': 10, 'sort': 'amount', 'asc': 0, 'node': 'hs_a'}
    r = session.get(url, params=params, timeout=10)
    if r.text and r.text not in ['null', '[]', '']:
        data = json.loads(r.text)
        if data:
            print(f"   OK - 获取到 {len(data)} 只股票")
            print(f"   示例: {data[0]['symbol']} {data[0]['name']}")
        else:
            print("   FAIL - 空数据")
    else:
        print("   FAIL - 无响应")
except Exception as e:
    print(f"   FAIL - {e}")

# 4. 东方财富接口
print("\n4. 东方财富接口:")
try:
    url = 'https://push2.eastmoney.com/api/qt/clist/get'
    params = {'pn': 1, 'pz': 10, 'fs': 'm:1+t:2', 'fields': 'f12,f14'}
    r = session.get(url, params=params, timeout=10)
    data = r.json()
    if data.get('data', {}).get('diff'):
        print(f"   OK - 获取到 {len(data['data']['diff'])} 只")
    else:
        print("   FAIL - 无数据")
except Exception as e:
    print(f"   FAIL - {e}")

# 5. 新浪实时行情接口
print("\n5. 新浪实时行情接口:")
try:
    url = 'https://hq.sinajs.cn/list=sh600000,sz000001'
    headers = {'Referer': 'https://finance.sina.com.cn/'}
    r = session.get(url, headers=headers, timeout=10)
    if 'hq_str' in r.text and len(r.text) > 50:
        print("   OK - 可获取实时数据")
    else:
        print("   FAIL - 无数据")
except Exception as e:
    print(f"   FAIL - {e}")

print("\n" + "="*60)
print("结论:")
print("  OK = 周末可用")
print("  FAIL = 周末不可用或被代理阻断")
print("="*60)
