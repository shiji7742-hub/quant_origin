"""
主板非ST股票扫描
只扫描：
- 上海主板：600、601、603
- 深圳主板：000、001、002
排除：ST、创业板(300)、科创板(688)
"""
import requests
import pandas as pd
import numpy as np
import os
from datetime import datetime
import json
import time

def log(msg):
    print(msg, flush=True)

for key in list(os.environ.keys()):
    if 'proxy' in key.lower():
        del os.environ[key]

session = requests.Session()
session.trust_env = False
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
})


def get_stock_kline(code, days=60):
    code = str(code).zfill(6)
    kcode = f'sh{code}' if code.startswith('6') else f'sz{code}'
    url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={kcode},day,,,{days},qfq'
    try:
        r = session.get(url, timeout=10)
        data = r.json()
        if not data.get('data'):
            return None
        stock_data = data['data'].get(kcode) or data['data'].get(kcode.upper())
        if not stock_data or 'qfqday' not in stock_data:
            return None
        days_data = stock_data['qfqday']
        df = pd.DataFrame([d[:6] for d in days_data], 
                        columns=['日期','开盘','收盘','最高','最低','成交量'])
        for col in ['开盘','收盘','最高','最低','成交量']:
            df[col] = df[col].astype(float)
        df['日期'] = pd.to_datetime(df['日期'])
        df['涨跌幅'] = df['收盘'].pct_change() * 100
        df['量比'] = df['成交量'] / df['成交量'].rolling(20).mean()
        return df
    except:
        return None


def get_5min_kline(code):
    code = str(code).zfill(6)
    symbol = f'sh{code}' if code.startswith('6') else f'sz{code}'
    url = f'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={symbol}&scale=5&ma=no&datalen=100'
    try:
        r = session.get(url, timeout=15)
        text = r.text
        if not text or text == 'null':
            return None
        data = json.loads(text)
        if not data or len(data) < 20:
            return None
        df = pd.DataFrame(data)
        df['day'] = pd.to_datetime(df['day'])
        df['date'] = df['day'].dt.strftime('%Y%m%d')
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        return df
    except:
        return None


def get_stock_name(code):
    code = str(code).zfill(6)
    kcode = f'sh{code}' if code.startswith('6') else f'sz{code}'
    try:
        url = f'https://qt.gtimg.cn/q={kcode}'
        r = session.get(url, timeout=5)
        parts = r.text.split('~')
        if len(parts) > 1:
            return parts[1]
    except:
        pass
    return code


def check_intraday_support(code):
    """检查分时托单信号"""
    df_5min = get_5min_kline(code)
    if df_5min is None:
        return None
    
    latest_date = df_5min['date'].max()
    day_bars = df_5min[df_5min['date'] == latest_date].copy()
    
    if len(day_bars) < 10:
        return None
    
    high = day_bars['high'].max()
    low = day_bars['low'].min()
    current = day_bars.iloc[-1]['close']
    open_price = day_bars.iloc[0]['open']
    
    if high <= low:
        return None
    
    volatility = (high - low) / ((high + low) / 2) * 100
    position = (current - low) / (high - low) * 100
    today_change = (current - open_price) / open_price * 100
    
    # 托单计算
    day_bars['body_low'] = day_bars[['open', 'close']].min(axis=1)
    day_bars['lower_shadow'] = day_bars['body_low'] - day_bars['low']
    day_bars['body'] = abs(day_bars['close'] - day_bars['open'])
    support_bars = day_bars[day_bars['lower_shadow'] > day_bars['body'] * 0.5]
    support_count = len(support_bars)
    
    # 量比
    day_bars['change'] = day_bars['close'] - day_bars['open']
    up_bars = day_bars[day_bars['change'] > 0]
    down_bars = day_bars[day_bars['change'] < 0]
    if len(down_bars) > 0 and len(up_bars) > 0:
        vol_ratio = up_bars['volume'].mean() / down_bars['volume'].mean()
    else:
        vol_ratio = 1
    
    # 评分
    score = 0
    if volatility < 5: score += 15
    if support_count >= 5: score += 20
    elif support_count >= 3: score += 10
    if vol_ratio >= 1.5: score += 25
    elif vol_ratio >= 1.2: score += 20
    elif vol_ratio >= 1.0: score += 10
    if position >= 80: score += 25
    elif position >= 60: score += 15
    if -1 <= today_change <= 4: score += 10
    
    return {
        'volatility': volatility,
        'support_count': support_count,
        'vol_ratio': vol_ratio,
        'position': position,
        'today_change': today_change,
        'score': score,
    }


def check_limit_washout(df):
    """检查涨停洗盘"""
    if df is None or len(df) < 30:
        return None
    
    current = df.iloc[-1]
    
    # 找涨停
    for back in range(3, 20):
        if len(df) <= back:
            break
        prev = df.iloc[-back-1]
        if prev['涨跌幅'] > 9.5:
            limit_high = prev['最高']
            pullback = (current['收盘'] - limit_high) / limit_high * 100
            
            vol_recent = df.iloc[-5:]['成交量'].mean()
            vol_limit = df.iloc[-back-1:-back+2]['成交量'].mean()
            vol_shrink = vol_recent / vol_limit if vol_limit > 0 else 1
            
            if -15 <= pullback <= -3 and vol_shrink < 1.0:
                score = 0
                if -12 <= pullback <= -5: score += 25
                else: score += 15
                if vol_shrink < 0.5: score += 25
                elif vol_shrink < 0.8: score += 15
                
                ma5 = df['收盘'].iloc[-5:].mean()
                if current['收盘'] > ma5: score += 15
                
                return {
                    'days_since': back,
                    'pullback': pullback,
                    'vol_shrink': vol_shrink,
                    'score': score,
                }
    return None


def scan_main_board():
    """扫描主板股票"""
    log("="*70)
    log("主板非ST股票扫描")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*70)
    
    # 主板股票池（排除ST、创业板、科创板）
    stocks = {
        '人工智能': ['002230', '603019', '002410', '600100', '002236'],  # 科大讯飞、中科曙光、广联达、同方股份、大华股份
        '半导体': ['002371', '603986', '600584', '002049', '603501'],  # 北方华创、兆易创新、长电科技、紫光国微、韦尔股份
        '机器人': ['002747', '002527', '601689', '000410', '002472'],  # 埃斯顿、新时达、拓普集团、沈阳机床、双环传动
        '新能源车': ['002594', '600745', '002074', '600884', '000625'],  # 比亚迪、闻泰科技、国轩高科、杉杉股份、长安汽车
        '光伏': ['601012', '002459', '600438', '601865', '600732'],  # 隆基绿能、晶澳科技、通威股份、福莱特、ST爱旭->换掉
        '消费电子': ['002456', '002241', '002475', '603160', '002938'],  # 欧菲光、歌尔股份、立讯精密、汇顶科技、鹏鼎控股
        '医药': ['000538', '002821', '600276', '000963', '002007'],  # 云南白药、凯莱英、恒瑞医药、华东医药、华兰生物
        '白酒': ['600519', '000858', '000568', '603369', '002304'],  # 贵州茅台、五粮液、泸州老窖、今世缘、洋河股份
        '银行': ['601398', '601939', '600036', '000001', '601166'],  # 工商银行、建设银行、招商银行、平安银行、兴业银行
        '券商': ['600030', '601211', '000776', '601688', '600999'],  # 中信证券、国泰君安、广发证券、华泰证券、招商证券
    }
    
    support_signals = []
    washout_signals = []
    
    for sector, codes in stocks.items():
        log(f"\n扫描: {sector}")
        
        for code in codes:
            name = get_stock_name(code)
            
            # 过滤ST
            if 'ST' in name or 'st' in name:
                continue
            
            # 分时托单
            support = check_intraday_support(code)
            if support and support['score'] >= 50:
                support['code'] = code
                support['name'] = name
                support['sector'] = sector
                support_signals.append(support)
            
            # 涨停洗盘
            df = get_stock_kline(code, 60)
            washout = check_limit_washout(df)
            if washout and washout['score'] >= 40:
                washout['code'] = code
                washout['name'] = name
                washout['sector'] = sector
                washout_signals.append(washout)
            
            time.sleep(0.1)
    
    # 排序
    support_signals.sort(key=lambda x: x['score'], reverse=True)
    washout_signals.sort(key=lambda x: x['score'], reverse=True)
    
    # 输出结果
    log("\n" + "="*70)
    log("扫描结果")
    log("="*70)
    
    log(f"\n【分时托单信号】({len(support_signals)}个)")
    if support_signals:
        for s in support_signals[:10]:
            log(f"  {s['code']} {s['name']} [{s['sector']}]: 评分{s['score']}, 量比{s['vol_ratio']:.2f}, 位置{s['position']:.0f}%, 托单{s['support_count']}次")
    else:
        log("  暂无符合条件的信号")
    
    log(f"\n【涨停洗盘信号】({len(washout_signals)}个)")
    if washout_signals:
        for s in washout_signals[:10]:
            log(f"  {s['code']} {s['name']} [{s['sector']}]: 评分{s['score']}, 涨停后{s['days_since']}天, 回调{s['pullback']:.1f}%, 缩量{s['vol_shrink']:.2f}")
    else:
        log("  暂无符合条件的信号")
    
    # 综合推荐
    log("\n" + "="*70)
    log("综合推荐（主板非ST）")
    log("="*70)
    
    if support_signals:
        top = support_signals[0]
        log(f"\n【重点关注】{top['code']} {top['name']}")
        log(f"  板块: {top['sector']}")
        log(f"  评分: {top['score']}")
        log(f"  量比: {top['vol_ratio']:.2f}")
        log(f"  位置: {top['position']:.0f}%")
        log(f"  今日涨跌: {top['today_change']:+.2f}%")
        log(f"\n  操作建议:")
        log(f"  - 买入: 现价或回调时介入")
        log(f"  - 仓位: 10-15%")
        log(f"  - 止损: -3%")
        log(f"  - 止盈: +5%")


if __name__ == "__main__":
    scan_main_board()
