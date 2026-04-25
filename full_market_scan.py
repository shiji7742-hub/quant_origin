"""全市场扫描 - 使用新浪+腾讯数据源"""
import requests
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
import os
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
warnings.filterwarnings('ignore')

# 清除代理设置
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    if key in os.environ:
        del os.environ[key]

print("="*60)
print("全市场扫描 - 寻找明日买点")
print(f"扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*60)

def get_all_stocks_sina():
    """从新浪获取全部A股列表"""
    try:
        # 获取沪市
        url_sh = 'https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData'
        # 获取深市
        stocks = []
        
        for market, node in [('sh', 'hs_a'), ('sz', 'sz_a')]:
            for page in range(1, 50):  # 最多50页
                params = {
                    'page': page,
                    'num': 100,
                    'sort': 'symbol',
                    'asc': 1,
                    'node': node,
                    'symbol': '',
                    '_s_r_a': 'page'
                }
                
                session = requests.Session()
                session.trust_env = False
                response = session.get(url_sh, params=params, timeout=10)
                
                if response.status_code == 200 and response.text and response.text != 'null':
                    data = json.loads(response.text)
                    if not data:
                        break
                    for item in data:
                        code = item.get('symbol', '')
                        name = item.get('name', '')
                        price = float(item.get('trade', 0) or 0)
                        change = float(item.get('changepercent', 0) or 0)
                        volume = float(item.get('volume', 0) or 0)
                        
                        # 过滤
                        if not code or not name:
                            continue
                        if 'ST' in name or '*' in name:
                            continue
                        if code.startswith('8') or code.startswith('4') or code.startswith('9'):
                            continue
                        if price < 3 or price > 100:
                            continue
                        if volume < 10000000:  # 成交量太小
                            continue
                        
                        stocks.append({
                            'code': code,
                            'name': name,
                            'price': price,
                            'change': change
                        })
                else:
                    break
                    
                time.sleep(0.1)
        
        return stocks
    except Exception as e:
        print(f"获取股票列表失败: {e}")
        return []

def get_stock_kline_tencent(symbol):
    """从腾讯获取K线数据"""
    try:
        if symbol.startswith('6'):
            code = f'sh{symbol}'
        else:
            code = f'sz{symbol}'
        
        url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,60,qfq'
        
        session = requests.Session()
        session.trust_env = False
        response = session.get(url, timeout=8)
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
    
    # 计算各项指标
    ma_bullish = latest['MA5'] > latest['MA10'] > latest['MA20']
    vol_ratio = latest['成交量'] / latest['VOL_MA5'] if latest['VOL_MA5'] > 0 else 0
    is_red = latest['收盘'] > latest['开盘']
    above_ma20 = latest['收盘'] > latest['MA20']
    
    box_high = df.iloc[-16:-1]['最高'].max() if len(df) >= 16 else 0
    box_breakout = latest['收盘'] > box_high
    
    high_20d = df.tail(20)['最高'].max()
    pullback = (latest['收盘'] - high_20d) / high_20d * 100
    
    # 计算评分
    score = 0
    if ma_bullish: score += 25
    if vol_ratio > 1.2: score += 20
    if is_red: score += 15
    if above_ma20: score += 20
    if box_breakout: score += 20
    
    if score < 60:  # 只返回强信号
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

def scan_stock(stock):
    """扫描单只股票"""
    code = stock['code']
    name = stock['name']
    
    df = get_stock_kline_tencent(code)
    if df is None:
        return None
    
    signals = check_signals(df)
    if signals is None:
        return None
    
    return {
        '代码': code,
        '名称': name,
        **signals
    }

# 主扫描逻辑
print("\n[1/3] 获取股票列表...")
all_stocks = get_all_stocks_sina()

if not all_stocks:
    print("无法获取股票列表，尝试使用备用方案...")
    # 备用：从腾讯获取部分热门股票
    # 这里简化处理
    print("请稍后重试或检查网络连接")
else:
    print(f"  获取到 {len(all_stocks)} 只股票")
    
    print("\n[2/3] 扫描全市场...")
    results = []
    scanned = 0
    
    # 使用线程池并发扫描
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(scan_stock, stock): stock for stock in all_stocks}
        
        for future in as_completed(futures):
            scanned += 1
            if scanned % 100 == 0:
                print(f"  进度: {scanned}/{len(all_stocks)} (找到 {len(results)} 个信号)")
            
            try:
                result = future.result()
                if result:
                    results.append(result)
                    print(f"  ★ {result['代码']} {result['名称']} 评分{result['评分']}")
            except:
                pass
    
    print(f"\n  扫描完成: {scanned} 只股票, 找到 {len(results)} 个强信号")
    
    # 输出结果
    print("\n[3/3] 生成报告...")
    if results:
        results_sorted = sorted(results, key=lambda x: x['评分'], reverse=True)
        
        print("\n" + "="*60)
        print("全市场扫描结果 - 强信号股票")
        print("="*60)
        
        for r in results_sorted[:20]:  # 只显示前20个
            print(f"  {r['代码']} {r['名称']:<8} {r['收盘价']:>8.2f} 评分{r['评分']} "
                  f"多头:{r['均线多头']} 量比:{r['量比']} 突破:{r['箱体突破']}")
        
        if len(results_sorted) > 20:
            print(f"  ... 共 {len(results_sorted)} 只股票")
        
        # 保存结果
        df_result = pd.DataFrame(results_sorted)
        filename = f"全市场扫描_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        df_result.to_excel(filename, index=False)
        print(f"\n结果已保存: {filename}")
        
        print("\n" + "-"*60)
        print("操作建议:")
        print("  1. 优先选择评分高、量比大的股票")
        print("  2. 开盘后30分钟观察，确认企稳后买入")
        print("  3. 止损-5%，止盈+10%")
        print("-"*60)
    else:
        print("\n今日无符合条件的强信号股票")
