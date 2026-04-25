"""检查新浪接口返回的最新数据日期"""
import requests
import json

print("检查新浪财经接口最新数据...")
print("="*50)

test_stocks = [
    ('sz000663', '永安林业'),
    ('sz002279', '久其软件'),
    ('sh600887', '伊利股份'),
]

for symbol, name in test_stocks:
    try:
        url = 'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData'
        params = {
            'symbol': symbol,
            'scale': '240',
            'ma': 'no',
            'datalen': '10'
        }
        
        session = requests.Session()
        session.trust_env = False
        
        response = session.get(url, params=params, timeout=15)
        data = json.loads(response.text)
        
        if data:
            print(f"\n{name} ({symbol}) 最近5天:")
            for item in data[-5:]:
                print(f"  {item['day']}: 开={item['open']} 收={item['close']} 量={item['volume']}")
        else:
            print(f"\n{name}: 无数据")
            
    except Exception as e:
        print(f"\n{name}: 错误 - {e}")

print("\n" + "="*50)
print("说明: 周末股市不交易，最新数据应该是最近一个交易日")
