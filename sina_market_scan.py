"""新浪全市场扫描"""
import requests
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
import os
import time
import json
warnings.filterwarnings('ignore')

for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    if key in os.environ:
        del os.environ[key]

print("="*60)
print("新浪全市场扫描 - 寻找明日买点")
print(f"扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*60)

def get_stock_list_sina():
    """从新浪获取股票列表"""
    stocks = []
    
    try:
        session = requests.Session()
        session.trust_env = False
        
        # 获取沪深股票
        for node in ['hs_a', 'sz_a']:
            page = 1
            while page <= 30:  # 最多30页
                url = 'https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData'
                params = {
                    'page': page,
                    'num': 80,
                    'sort': 'amount',
                    'asc': 0,
                    'node': node
                }
                
                response = session.get(url, params=params, timeout=15)
                
                if response.status_code == 200 and response.text and response.text not in ['null', '[]', '']:
                    try:
                        data = json.loads(response.text)
                        if not data:
                            break
                        
                        for item in data:
                            code = item.get('symbol', '')
                            name = item.get('name', '')
                            price = float(item.get('trade', 0) or 0)
                            change = float(item.get('changepercent', 0) or 0)
                            amount = float(item.get('amount', 0) or 0)
                            
                            if not code or not name:
                                continue
                            if 'ST' in name or '*' in name:
                                continue
                            if code.startswith('8') or code.startswith('4') or code.startswith('9'):
                                continue
                            if price < 3 or price > 80:
                                continue
                            if amount < 50000000:  # 成交额5000万以上
                                continue
                            
                            stocks.append({
                                'code': code,
                                'name': name,
                                'price': price,
                                'change': change,
                                'amount': amount
                            })
                        
                        page += 1
                        time.sleep(0.2)
                        
                    except json.JSONDecodeError:
                        break
                else:
                    break
                    
    except Exception as e:
        print(f"新浪接口错误: {e}")
    
    return stocks

def get_kline_sina(symbol):
    """从新浪获取K线"""
    try:
        if symbol.startswith('6'):
            market = 'sh'
        else:
            market = 'sz'
        
        code = f"{market}{symbol}"
        url = 'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData'
        params = {
            'symbol': code,
            'scale': '240',
            'ma': 'no',
            'datalen': '60'
        }
        
        session = requests.Session()
        session.trust_env = False
        response = session.get(url, params=params, timeout=10)
        
        if response.status_code == 200 and response.text and response.text != 'null':
            data = json.loads(response.text)
            if data and len(data) >= 30:
                rows = []
                for item in data:
                    rows.append({
                        '日期': item['day'],
                        '开盘': float(item['open']),
                        '最高': float(item['high']),
                        '最低': float(item['low']),
                        '收盘': float(item['close']),
                        '成交量': float(item['volume'])
                    })
                df = pd.DataFrame(rows)
                df['日期'] = pd.to_datetime(df['日期'])
                df['涨跌幅'] = df['收盘'].pct_change() * 100
                return df
        return None
    except:
        return None

def check_signals(df):
    """检查技术信号"""
    if df is None or len(df) < 30:
        return None
    
    df = df.copy().reset_index(drop=True)
    df['MA5'] = df['收盘'].rolling(5).mean()
    df['MA10'] = df['收盘'].rolling(10).mean()
    df['MA20'] = df['收盘'].rolling(20).mean()
    df['VOL_MA5'] = df['成交量'].rolling(5).mean()
    
    latest = df.iloc[-1]
    
    if pd.isna(latest['MA20']):
        return None
    
    ma_bullish = latest['MA5'] > latest['MA10'] > latest['MA20']
    vol_ratio = latest['成交量'] / latest['VOL_MA5'] if latest['VOL_MA5'] > 0 else 0
    is_red = latest['收盘'] > latest['开盘']
    above_ma20 = latest['收盘'] > latest['MA20']
    
    box_high = df.iloc[-16:-1]['最高'].max() if len(df) >= 16 else 0
    box_breakout = latest['收盘'] > box_high
    
    high_20d = df.tail(20)['最高'].max()
    pullback = (latest['收盘'] - high_20d) / high_20d * 100
    
    score = 0
    if ma_bullish: score += 25
    if vol_ratio > 1.2: score += 20
    if is_red: score += 15
    if above_ma20: score += 20
    if box_breakout: score += 20
    
    if score < 60:
        return None
    
    return {
        '评分': score,
        '均线多头': 'Y' if ma_bullish else 'N',
        '量比': f"{vol_ratio:.2f}",
        '箱体突破': 'Y' if box_breakout else 'N',
        '回调幅度': f"{pullback:.1f}%",
        '收盘价': latest['收盘'],
        '涨跌幅': latest['涨跌幅'] if pd.notna(latest['涨跌幅']) else 0,
        '数据日期': latest['日期'].strftime('%Y-%m-%d')
    }

# 主逻辑
print("\n[1/3] 获取股票列表 (新浪接口)...")
stocks = get_stock_list_sina()

if not stocks:
    print("获取失败，请检查网络")
else:
    # 去重
    seen = set()
    unique = []
    for s in stocks:
        if s['code'] not in seen:
            seen.add(s['code'])
            unique.append(s)
    stocks = unique
    
    print(f"  获取到 {len(stocks)} 只活跃股票")
    
    print("\n[2/3] 扫描信号...")
    results = []
    
    for i, stock in enumerate(stocks):
        code = stock['code']
        name = stock['name']
        
        if (i + 1) % 50 == 0:
            print(f"  进度: {i+1}/{len(stocks)} (找到 {len(results)} 个)")
        
        df = get_kline_sina(code)
        signals = check_signals(df)
        
        if signals:
            result = {'代码': code, '名称': name, **signals}
            results.append(result)
            print(f"  ★ {code} {name} 评分{signals['评分']}")
        
        time.sleep(0.15)
    
    print(f"\n  扫描完成，找到 {len(results)} 个强信号")
    
    # 结果
    if results:
        results_sorted = sorted(results, key=lambda x: x['评分'], reverse=True)
        
        print("\n" + "="*60)
        print("【明日买点 - 新扫描结果】")
        print("="*60)
        
        for r in results_sorted[:30]:
            print(f"  {r['代码']} {r['名称']:<8} {r['收盘价']:>7.2f} 评分{r['评分']} "
                  f"多头:{r['均线多头']} 量比:{r['量比']} 突破:{r['箱体突破']}")
        
        if len(results_sorted) > 30:
            print(f"  ... 共 {len(results_sorted)} 只")
        
        df_result = pd.DataFrame(results_sorted)
        filename = f"新浪全市场扫描_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        df_result.to_excel(filename, index=False)
        print(f"\n已保存: {filename}")
    else:
        print("\n今日无强信号")
