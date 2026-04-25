"""快速全市场扫描 - 扫描活跃股票"""
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
print("快速全市场扫描 - 寻找明日买点")
print(f"扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*60)

def get_active_stocks():
    """获取活跃股票列表（腾讯接口）"""
    stocks = []
    
    try:
        # 获取沪深两市活跃股票
        for market in ['sh', 'sz']:
            for page in range(0, 10):  # 获取前1000只
                url = f'https://push2.eastmoney.com/api/qt/clist/get'
                params = {
                    'pn': page + 1,
                    'pz': 100,
                    'po': 1,
                    'np': 1,
                    'fltt': 2,
                    'invt': 2,
                    'fid': 'f3',
                    'fs': f'm:{"1" if market == "sh" else "0"}+t:6,80' if market == 'sh' else f'm:0+t:6,80',
                    'fields': 'f12,f14,f2,f3,f5'
                }
                
                session = requests.Session()
                session.trust_env = False
                response = session.get(url, params=params, timeout=10)
                data = response.json()
                
                if data.get('data') and data['data'].get('diff'):
                    for item in data['data']['diff']:
                        code = item.get('f12', '')
                        name = item.get('f14', '')
                        price = item.get('f2', 0)
                        change = item.get('f3', 0)
                        volume = item.get('f5', 0)
                        
                        if not code or not name:
                            continue
                        if 'ST' in name or '*' in name:
                            continue
                        if code.startswith('8') or code.startswith('4') or code.startswith('9'):
                            continue
                        if not isinstance(price, (int, float)) or price < 3 or price > 100:
                            continue
                        
                        stocks.append({
                            'code': code,
                            'name': name,
                            'price': price,
                            'change': change,
                            'volume': volume
                        })
                else:
                    break
                    
                time.sleep(0.05)
                
    except Exception as e:
        print(f"东方财富接口失败: {e}")
        print("尝试备用接口...")
        
        # 备用：使用腾讯接口获取
        try:
            for market in ['sh', 'sz']:
                url = f'https://qt.gtimg.cn/q={market}rank'
                session = requests.Session()
                session.trust_env = False
                response = session.get(url, timeout=10)
                # 解析腾讯排行数据
                text = response.text
                if text:
                    parts = text.split('~')
                    for i in range(1, len(parts), 2):
                        if i < len(parts):
                            code = parts[i-1].split('=')[-1] if '=' in parts[i-1] else ''
                            name = parts[i] if i < len(parts) else ''
                            if code and name and not 'ST' in name:
                                stocks.append({'code': code, 'name': name, 'price': 0, 'change': 0})
        except:
            pass
    
    return stocks

def get_stock_kline(symbol):
    """获取K线数据"""
    try:
        if symbol.startswith('6'):
            code = f'sh{symbol}'
        else:
            code = f'sz{symbol}'
        
        url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,60,qfq'
        
        session = requests.Session()
        session.trust_env = False
        response = session.get(url, timeout=5)
        data = response.json()
        
        if data and 'data' in data:
            stock_data = data['data'].get(code) or data['data'].get(code.upper())
            if stock_data and 'qfqday' in stock_data:
                days = stock_data['qfqday']
                if days and len(days) >= 30:
                    rows = []
                    for day in days:
                        rows.append({
                            '日期': day[0],
                            '开盘': float(day[1]),
                            '收盘': float(day[2]),
                            '最高': float(day[3]),
                            '最低': float(day[4]),
                            '成交量': float(day[5])
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
print("\n[1/3] 获取活跃股票列表...")
stocks = get_active_stocks()

if not stocks:
    print("获取股票列表失败")
else:
    print(f"  获取到 {len(stocks)} 只活跃股票")
    
    # 去重
    seen = set()
    unique_stocks = []
    for s in stocks:
        if s['code'] not in seen:
            seen.add(s['code'])
            unique_stocks.append(s)
    stocks = unique_stocks
    print(f"  去重后 {len(stocks)} 只")
    
    print("\n[2/3] 扫描股票...")
    results = []
    
    for i, stock in enumerate(stocks):
        code = stock['code']
        name = stock['name']
        
        if (i + 1) % 50 == 0:
            print(f"  进度: {i+1}/{len(stocks)} (找到 {len(results)} 个)")
        
        df = get_stock_kline(code)
        signals = check_signals(df)
        
        if signals:
            result = {'代码': code, '名称': name, **signals}
            results.append(result)
            print(f"  ★ {code} {name} 评分{signals['评分']}")
        
        time.sleep(0.1)
    
    print(f"\n  扫描完成，找到 {len(results)} 个强信号")
    
    # 结果
    print("\n[3/3] 生成报告...")
    if results:
        results_sorted = sorted(results, key=lambda x: x['评分'], reverse=True)
        
        print("\n" + "="*60)
        print("【明日买点 - 全市场扫描结果】")
        print("="*60)
        
        for r in results_sorted[:30]:
            print(f"  {r['代码']} {r['名称']:<8} {r['收盘价']:>7.2f} 评分{r['评分']} "
                  f"多头:{r['均线多头']} 量比:{r['量比']} 突破:{r['箱体突破']}")
        
        if len(results_sorted) > 30:
            print(f"  ... 共 {len(results_sorted)} 只")
        
        df_result = pd.DataFrame(results_sorted)
        filename = f"全市场扫描_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        df_result.to_excel(filename, index=False)
        print(f"\n已保存: {filename}")
    else:
        print("\n今日无强信号股票")
