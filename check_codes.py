"""检查股票代码格式"""
import requests
import json
import os

for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    if key in os.environ:
        del os.environ[key]

session = requests.Session()
session.trust_env = False

print("检查新浪返回的股票代码格式...")
print("="*50)

url = 'https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData'
params = {'page': 1, 'num': 10, 'sort': 'amount', 'asc': 0, 'node': 'hs_a'}

r = session.get(url, params=params, timeout=15)
data = json.loads(r.text)

print(f"获取到 {len(data)} 条数据")
print("\n前5只股票:")
for item in data[:5]:
    code = item.get('symbol', '')
    name = item.get('name', '')
    print(f"  symbol={code} name={name}")
    print(f"    代码长度: {len(code)}")
    print(f"    前缀: {code[:2] if len(code) >= 2 else 'N/A'}")
    
    # 检查是否能匹配腾讯接口
    if code.startswith('sh') or code.startswith('sz'):
        kcode = code
    elif code.startswith('6'):
        kcode = f'sh{code}'
    else:
        kcode = f'sz{code}'
    
    print(f"    腾讯代码: {kcode}")
