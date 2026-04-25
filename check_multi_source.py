"""多数据源检查最新交易日"""
import requests
import json
from datetime import datetime

print("="*60)
print("多数据源检查最新交易数据")
print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*60)

def check_sina(symbol):
    """新浪财经"""
    try:
        if symbol.startswith('6'):
            code = f'sh{symbol}'
        else:
            code = f'sz{symbol}'
        
        url = 'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData'
        params = {'symbol': code, 'scale': '240', 'ma': 'no', 'datalen': '5'}
        
        session = requests.Session()
        session.trust_env = False
        response = session.get(url, params=params, timeout=10)
        data = json.loads(response.text)
        
        if data:
            latest = data[-1]
            return f"新浪: {latest['day']} 收盘={latest['close']}"
    except Exception as e:
        return f"新浪: 错误 - {str(e)[:30]}"
    return "新浪: 无数据"

def check_tencent(symbol):
    """腾讯财经"""
    try:
        if symbol.startswith('6'):
            code = f'sh{symbol}'
        else:
            code = f'sz{symbol}'
        
        url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,5,qfq'
        
        session = requests.Session()
        session.trust_env = False
        response = session.get(url, timeout=10)
        data = response.json()
        
        if data and 'data' in data:
            stock_data = data['data'].get(code) or data['data'].get(code.upper())
            if stock_data and 'qfqday' in stock_data:
                days = stock_data['qfqday']
                if days:
                    latest = days[-1]
                    return f"腾讯: {latest[0]} 收盘={latest[2]}"
    except Exception as e:
        return f"腾讯: 错误 - {str(e)[:30]}"
    return "腾讯: 无数据"

def check_163(symbol):
    """网易财经"""
    try:
        url = f'https://quotes.money.163.com/service/chddata.html?code={"0" if symbol.startswith("6") else "1"}{symbol}&start=20260120&end=20260131&fields=TCLOSE'
        
        session = requests.Session()
        session.trust_env = False
        response = session.get(url, timeout=10)
        
        if response.status_code == 200:
            lines = response.text.strip().split('\n')
            if len(lines) > 1:
                latest = lines[1].split(',')
                return f"网易: {latest[0]} 收盘={latest[3]}"
    except Exception as e:
        return f"网易: 错误 - {str(e)[:30]}"
    return "网易: 无数据"

# 测试几只股票
test_stocks = [
    ('000663', '永安林业'),
    ('002279', '久其软件'),
    ('600887', '伊利股份'),
]

for symbol, name in test_stocks:
    print(f"\n{name} ({symbol}):")
    print(f"  {check_sina(symbol)}")
    print(f"  {check_tencent(symbol)}")
    print(f"  {check_163(symbol)}")

print("\n" + "="*60)
print("结论:")
print("  如果所有接口都显示1月23日，说明1月24日休市")
print("  如果有接口显示1月24日，说明是新浪接口延迟")
print("="*60)
