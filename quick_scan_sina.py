"""快速扫描 - 使用新浪+腾讯双数据源（周末可用）"""
import requests
import pandas as pd
import numpy as np
from datetime import datetime
import warnings
import os
import time
import json
warnings.filterwarnings('ignore')

# 清除代理设置
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    if key in os.environ:
        del os.environ[key]

print("="*60)
print("明日买点快速扫描 (新浪+腾讯双数据源)")
print(f"扫描时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*60)

def get_stock_data_tencent(symbol):
    """从腾讯获取股票K线数据（备用）"""
    try:
        if symbol.startswith('6'):
            code = f'sh{symbol}'
        else:
            code = f'sz{symbol}'
        
        url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,60,qfq'
        
        session = requests.Session()
        session.trust_env = False
        response = session.get(url, timeout=10)
        data = response.json()
        
        if data and 'data' in data:
            stock_data = data['data'].get(code) or data['data'].get(code.upper())
            if stock_data and 'qfqday' in stock_data:
                days = stock_data['qfqday']
                if days:
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

def get_stock_data_sina(symbol):
    """从新浪获取股票K线数据"""
    try:
        # 确定市场代码
        if symbol.startswith('6'):
            market = 'sh'
        else:
            market = 'sz'
        
        stock_code = f"{market}{symbol}"
        
        # 使用新浪的历史数据接口
        url = f'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData'
        params = {
            'symbol': stock_code,
            'scale': '240',  # 日K线
            'ma': 'no',
            'datalen': '60'
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://finance.sina.com.cn/'
        }
        
        session = requests.Session()
        session.trust_env = False
        
        response = session.get(url, params=params, headers=headers, timeout=15)
        
        if response.status_code == 200:
            text = response.text
            # 解析数据
            if text and text != 'null':
                import json
                data = json.loads(text)
                if data:
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
                    # 计算涨跌幅
                    df['涨跌幅'] = df['收盘'].pct_change() * 100
                    return df
        return None
    except Exception as e:
        print(f"    新浪error: {e}")
        return None

def get_realtime_sina(symbol):
    """从新浪获取实时行情"""
    try:
        if symbol.startswith('6'):
            market = 'sh'
        else:
            market = 'sz'
        
        stock_code = f"{market}{symbol}"
        url = f'https://hq.sinajs.cn/list={stock_code}'
        
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://finance.sina.com.cn/'
        }
        
        session = requests.Session()
        session.trust_env = False
        
        response = session.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            text = response.text
            # 解析新浪格式: var hq_str_sh600000="股票名称,今开,昨收,现价,..."
            if 'hq_str' in text and '="' in text:
                data_str = text.split('="')[1].rstrip('";')
                if data_str:
                    parts = data_str.split(',')
                    if len(parts) >= 10:
                        return {
                            'name': parts[0],
                            'open': float(parts[1]) if parts[1] else 0,
                            'prev_close': float(parts[2]) if parts[2] else 0,
                            'price': float(parts[3]) if parts[3] else 0,
                            'high': float(parts[4]) if parts[4] else 0,
                            'low': float(parts[5]) if parts[5] else 0,
                            'volume': float(parts[8]) if parts[8] else 0,
                            'amount': float(parts[9]) if parts[9] else 0
                        }
        return None
    except Exception as e:
        return None

def check_signals(df):
    """检查技术信号"""
    if df is None or len(df) < 30:
        return {}
    
    df = df.copy().reset_index(drop=True)
    df['MA5'] = df['收盘'].rolling(5).mean()
    df['MA10'] = df['收盘'].rolling(10).mean()
    df['MA20'] = df['收盘'].rolling(20).mean()
    df['VOL_MA5'] = df['成交量'].rolling(5).mean()
    
    latest = df.iloc[-1]
    
    signals = {}
    
    # 1. 均线多头排列
    if pd.notna(latest['MA5']) and pd.notna(latest['MA10']) and pd.notna(latest['MA20']):
        ma_bullish = latest['MA5'] > latest['MA10'] > latest['MA20']
        signals['均线多头'] = ma_bullish
    
    # 2. 量能放大
    vol_ratio = latest['成交量'] / latest['VOL_MA5'] if latest['VOL_MA5'] > 0 else 0
    signals['量能放大'] = vol_ratio > 1.2
    signals['量比'] = f"{vol_ratio:.2f}"
    
    # 3. 今日收阳
    is_red = latest['收盘'] > latest['开盘']
    signals['收阳'] = is_red
    
    # 4. 站上MA20
    above_ma20 = latest['收盘'] > latest['MA20'] if pd.notna(latest['MA20']) else False
    signals['站上MA20'] = above_ma20
    
    # 5. 箱体突破
    box_high = df.iloc[-16:-1]['最高'].max() if len(df) >= 16 else 0
    box_breakout = latest['收盘'] > box_high
    signals['箱体突破'] = box_breakout
    
    # 6. 回调幅度
    high_20d = df.tail(20)['最高'].max()
    pullback = (latest['收盘'] - high_20d) / high_20d * 100
    signals['回调幅度'] = f"{pullback:.1f}%"
    
    # 7. 最新数据日期
    signals['最新日期'] = latest['日期'].strftime('%Y-%m-%d') if pd.notna(latest['日期']) else 'N/A'
    
    # 计算评分
    score = 0
    if signals.get('均线多头'): score += 25
    if signals.get('量能放大'): score += 20
    if signals.get('收阳'): score += 15
    if signals.get('站上MA20'): score += 20
    if signals.get('箱体突破'): score += 20
    signals['评分'] = score
    
    return signals

# 潜力股列表
test_stocks = [
    ('000685', '中山公用'),
    ('000823', '超声电子'),
    ('001211', '双枪科技'),
    ('002893', '京能热力'),
    ('605033', '美邦股份'),
    ('000663', '永安林业'),
    ('001386', '马可波罗'),
    ('002133', '广宇集团'),
    ('002307', '北新路桥'),
    ('002279', '久其软件'),
    ('000002', '万科A'),
    ('600887', '伊利股份'),
]

print(f"\n检查 {len(test_stocks)} 只潜力股的最新信号 (新浪接口)...")
print("-"*60)

results = []
for code, name in test_stocks:
    try:
        # 尝试新浪接口
        df = get_stock_data_sina(code)
        source = "新浪"
        
        # 如果新浪失败，尝试腾讯接口
        if df is None or len(df) == 0:
            df = get_stock_data_tencent(code)
            source = "腾讯"
        
        if df is None or len(df) == 0:
            print(f"  {code} {name}: 获取数据失败")
            continue
        
        signals = check_signals(df)
        latest = df.iloc[-1]
        
        result = {
            '代码': code,
            '名称': name,
            '收盘价': latest['收盘'],
            '涨跌幅': f"{latest['涨跌幅']:.2f}%" if pd.notna(latest['涨跌幅']) else 'N/A',
            '评分': signals.get('评分', 0),
            '均线多头': 'Y' if signals.get('均线多头') else 'N',
            '量比': signals.get('量比', ''),
            '箱体突破': 'Y' if signals.get('箱体突破') else 'N',
            '回调幅度': signals.get('回调幅度', ''),
            '数据日期': signals.get('最新日期', ''),
        }
        results.append(result)
        
        status = 'STRONG' if result['评分'] >= 60 else ('MEDIUM' if result['评分'] >= 40 else 'WEAK')
        print(f"  {code} {name}: {latest['收盘']:.2f} Score={result['评分']} [{status}] 日期:{result['数据日期']}")
        
        time.sleep(0.3)  # 延迟避免被限制
        
    except Exception as e:
        print(f"  {code} {name}: Error - {str(e)[:60]}")

# 排序输出
if results:
    print("\n" + "="*60)
    print("明日买点推荐 (按评分排序)")
    print("="*60)
    
    results_sorted = sorted(results, key=lambda x: x['评分'], reverse=True)
    
    strong_signals = [r for r in results_sorted if r['评分'] >= 60]
    medium_signals = [r for r in results_sorted if 40 <= r['评分'] < 60]
    weak_signals = [r for r in results_sorted if r['评分'] < 40]
    
    if strong_signals:
        print("\n【强信号 - 可考虑买入】")
        for r in strong_signals:
            print(f"  {r['代码']} {r['名称']}: {r['收盘价']:.2f} 评分{r['评分']} "
                  f"多头:{r['均线多头']} 量比:{r['量比']} 突破:{r['箱体突破']}")
    
    if medium_signals:
        print("\n【中等信号 - 观察】")
        for r in medium_signals:
            print(f"  {r['代码']} {r['名称']}: {r['收盘价']:.2f} 评分{r['评分']} 回调:{r['回调幅度']}")
    
    if weak_signals:
        print("\n【弱信号 - 暂不操作】")
        for r in weak_signals:
            print(f"  {r['代码']} {r['名称']}: {r['收盘价']:.2f} 评分{r['评分']}")
    
    print("\n" + "-"*60)
    print("操作建议:")
    print("  1. 强信号股票可在开盘后30分钟观察，确认企稳后买入")
    print("  2. 建议单只仓位不超过5%，总仓位控制在15%以内")
    print("  3. 止损设置为-5%，止盈目标+10%")
    print("-"*60)
    
    # 保存结果
    df_result = pd.DataFrame(results_sorted)
    filename = f"快速扫描结果_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df_result.to_excel(filename, index=False)
    print(f"\n结果已保存: {filename}")
else:
    print("\n" + "="*60)
    print("网络连接问题")
    print("="*60)
    print("\n无法连接到股票数据接口。请尝试以下解决方案:")
    print("\n1. 关闭VPN或代理软件")
    print("2. 检查防火墙设置")
    print("3. 明天开盘前使用通达信/同花顺等软件获取数据")
    print("\n或者参考之前的扫描结果:")
    print("  - 优化版可买清单_20260121.xlsx")
    print("  - 策略组合扫描_20260122_145228.xlsx")
