"""
每日策略V2 - 改进版
改进点：
1. 排除大盘股（银行、券商等波动小）
2. 加入日线趋势判断
3. 排除已涨多的股票
4. 加入资金流入判断
5. 选择中小盘活跃股
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
        if not data or len(data) < 10:
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


def analyze_daily_trend(df):
    """
    分析日线趋势
    返回: trend_score, trend_info
    """
    if df is None or len(df) < 20:
        return 0, None
    
    current = df.iloc[-1]
    
    # 均线
    ma5 = df['收盘'].iloc[-5:].mean()
    ma10 = df['收盘'].iloc[-10:].mean()
    ma20 = df['收盘'].iloc[-20:].mean()
    
    # 近期涨跌
    ret_3d = (current['收盘'] - df.iloc[-4]['收盘']) / df.iloc[-4]['收盘'] * 100
    ret_5d = (current['收盘'] - df.iloc[-6]['收盘']) / df.iloc[-6]['收盘'] * 100
    ret_10d = (current['收盘'] - df.iloc[-11]['收盘']) / df.iloc[-11]['收盘'] * 100
    
    # 20日位置
    high_20d = df['最高'].iloc[-20:].max()
    low_20d = df['最低'].iloc[-20:].min()
    pos_20d = (current['收盘'] - low_20d) / (high_20d - low_20d) * 100 if high_20d > low_20d else 50
    
    # 量能
    vol_5d = df['成交量'].iloc[-5:].mean()
    vol_20d = df['成交量'].iloc[-20:].mean()
    vol_ratio = vol_5d / vol_20d if vol_20d > 0 else 1
    
    # 评分
    score = 0
    
    # 1. 均线多头排列 (+30)
    if current['收盘'] > ma5 > ma10 > ma20:
        score += 30
    elif current['收盘'] > ma5 > ma10:
        score += 20
    elif current['收盘'] > ma5:
        score += 10
    elif current['收盘'] < ma5 < ma10:
        score -= 20  # 空头排列扣分
    
    # 2. 位置判断 - 不要追高 (+20)
    if 30 <= pos_20d <= 70:
        score += 20  # 中间位置最佳
    elif pos_20d < 30:
        score += 15  # 低位也可以
    elif pos_20d > 90:
        score -= 20  # 高位扣分
    
    # 3. 近期涨幅 - 不要追涨 (+15)
    if -3 <= ret_5d <= 5:
        score += 15  # 没涨太多
    elif ret_5d > 10:
        score -= 15  # 涨太多扣分
    elif ret_5d < -5:
        score -= 10  # 跌太多也扣分
    
    # 4. 量能配合 (+15)
    if 1.0 <= vol_ratio <= 1.5:
        score += 15  # 温和放量最佳
    elif vol_ratio > 2:
        score -= 5  # 量太大可能是出货
    
    # 5. 趋势判断
    if ret_3d > 0 and ret_5d > 0:
        score += 10  # 短期上涨趋势
    
    info = {
        'ma5': ma5,
        'ma10': ma10,
        'ma20': ma20,
        'ret_3d': ret_3d,
        'ret_5d': ret_5d,
        'ret_10d': ret_10d,
        'pos_20d': pos_20d,
        'vol_ratio': vol_ratio,
    }
    
    return score, info


def analyze_intraday(code):
    """分析分时走势"""
    df_5min = get_5min_kline(code)
    if df_5min is None:
        return 0, None
    
    latest_date = df_5min['date'].max()
    day_bars = df_5min[df_5min['date'] == latest_date].copy()
    
    if len(day_bars) < 5:
        return 0, None
    
    high = day_bars['high'].max()
    low = day_bars['low'].min()
    current = day_bars.iloc[-1]['close']
    open_price = day_bars.iloc[0]['open']
    
    if high <= low:
        return 0, None
    
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
    
    if volatility < 4:
        score += 15
    elif volatility > 6:
        score -= 10  # 波动太大扣分
    
    if support_count >= 5:
        score += 20
    elif support_count >= 3:
        score += 10
    
    if vol_ratio >= 1.3:
        score += 20
    elif vol_ratio >= 1.1:
        score += 10
    
    if position >= 75:
        score += 20
    elif position >= 60:
        score += 10
    elif position < 40:
        score -= 15  # 收盘位置太低扣分
    
    if 0 <= today_change <= 3:
        score += 10
    elif today_change > 5:
        score -= 10  # 涨太多扣分
    elif today_change < -1:
        score -= 10  # 下跌扣分
    
    info = {
        'volatility': volatility,
        'support_count': support_count,
        'vol_ratio': vol_ratio,
        'position': position,
        'today_change': today_change,
    }
    
    return score, info


def comprehensive_score(daily_score, intraday_score, daily_info, intraday_info):
    """综合评分"""
    total = daily_score + intraday_score
    
    # 额外加减分
    
    # 日线+分时共振
    if daily_score >= 40 and intraday_score >= 40:
        total += 20
    
    # 日线弱势但分时强
    if daily_score < 20 and intraday_score >= 50:
        total -= 20  # 可能是诱多
    
    # 日线强但分时弱
    if daily_score >= 50 and intraday_score < 20:
        total -= 10  # 今天走势不佳
    
    return total


def scan_improved():
    """改进版扫描"""
    log("="*70)
    log("每日策略V2 - 改进版")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*70)
    
    # 股票池 - 中小盘活跃股（排除银行券商等大盘股）
    stocks = {
        '人工智能': ['002230', '603019', '002410', '002236', '000977'],  # 科大讯飞、中科曙光、广联达、大华股份、浪潮信息
        '半导体': ['002371', '603986', '002049', '603501', '002185'],  # 北方华创、兆易创新、紫光国微、韦尔股份、华天科技
        '机器人': ['002747', '002527', '002472', '002892', '002008'],  # 埃斯顿、新时达、双环传动、科力尔、大族激光
        '新能源车': ['002594', '002074', '000625', '002466', '002129'],  # 比亚迪、国轩高科、长安汽车、天齐锂业、中环股份
        '光伏': ['601012', '002459', '600438', '601865', '002506'],  # 隆基绿能、晶澳科技、通威股份、福莱特、协鑫集成
        '消费电子': ['002456', '002241', '002475', '002938', '002036'],  # 欧菲光、歌尔股份、立讯精密、鹏鼎控股、联创电子
        '医药': ['000538', '002821', '600276', '000963', '002007'],  # 云南白药、凯莱英、恒瑞医药、华东医药、华兰生物
        '军工': ['600893', '000768', '002013', '600760', '002179'],  # 航发动力、中航飞机、中航机电、中航沈飞、中航光电
        '新材料': ['002080', '603799', '002340', '600516', '002428'],  # 中材科技、华友钴业、格林美、方大炭素、云南锗业
    }
    
    all_signals = []
    
    for sector, codes in stocks.items():
        log(f"\n扫描: {sector}")
        
        for code in codes:
            name = get_stock_name(code)
            
            # 过滤ST
            if 'ST' in name or 'st' in name:
                continue
            
            # 日线分析
            df = get_stock_kline(code, 60)
            daily_score, daily_info = analyze_daily_trend(df)
            
            # 分时分析
            intraday_score, intraday_info = analyze_intraday(code)
            
            if daily_info is None or intraday_info is None:
                continue
            
            # 综合评分
            total_score = comprehensive_score(daily_score, intraday_score, daily_info, intraday_info)
            
            # 只保留评分>60的
            if total_score >= 60:
                all_signals.append({
                    'code': code,
                    'name': name,
                    'sector': sector,
                    'total_score': total_score,
                    'daily_score': daily_score,
                    'intraday_score': intraday_score,
                    'pos_20d': daily_info['pos_20d'],
                    'ret_5d': daily_info['ret_5d'],
                    'vol_ratio': daily_info['vol_ratio'],
                    'today_change': intraday_info['today_change'],
                    'position': intraday_info['position'],
                    'support_count': intraday_info['support_count'],
                })
            
            time.sleep(0.1)
    
    # 排序
    all_signals.sort(key=lambda x: x['total_score'], reverse=True)
    
    # 输出结果
    log("\n" + "="*70)
    log("扫描结果（按综合评分排序）")
    log("="*70)
    
    if all_signals:
        log(f"\n共 {len(all_signals)} 个符合条件的信号\n")
        
        for i, s in enumerate(all_signals[:15], 1):
            # 评级
            if s['total_score'] >= 100:
                rating = "★★★"
            elif s['total_score'] >= 80:
                rating = "★★"
            else:
                rating = "★"
            
            log(f"{i:2}. {s['code']} {s['name']} [{s['sector']}] {rating}")
            log(f"    综合{s['total_score']} = 日线{s['daily_score']} + 分时{s['intraday_score']}")
            log(f"    20日位置{s['pos_20d']:.0f}%, 5日涨{s['ret_5d']:+.1f}%, 今日{s['today_change']:+.1f}%")
            log("")
    else:
        log("\n暂无符合条件的信号")
    
    # 推荐
    log("="*70)
    log("今日推荐")
    log("="*70)
    
    if len(all_signals) >= 1:
        top3 = all_signals[:3]
        
        for i, s in enumerate(top3, 1):
            log(f"\n【推荐{i}】{s['code']} {s['name']}")
            log(f"  板块: {s['sector']}")
            log(f"  综合评分: {s['total_score']} (日线{s['daily_score']} + 分时{s['intraday_score']})")
            log(f"  20日位置: {s['pos_20d']:.0f}%")
            log(f"  5日涨幅: {s['ret_5d']:+.1f}%")
            log(f"  今日涨幅: {s['today_change']:+.1f}%")
            
            # 操作建议
            if s['today_change'] > 3:
                log(f"  建议: 已涨较多，等回调再买")
            elif s['today_change'] < 0:
                log(f"  建议: 可以考虑现价介入")
            else:
                log(f"  建议: 可以轻仓介入")
            
            log(f"  止损: -3%")
            log(f"  止盈: +5%")
    
    # 风险提示
    log("\n" + "="*70)
    log("风险提示")
    log("="*70)
    log("""
  1. 以上推荐仅供参考，不构成投资建议
  2. 严格执行止损纪律，单票止损-3%
  3. 不要追涨，等回调再买
  4. 控制仓位，单票不超过15%
  5. 大盘不好时减少操作
    """)


if __name__ == "__main__":
    scan_improved()
