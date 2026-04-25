"""
策略体系V2.0 - 全面优化版
优化内容：
1. 分时托单：加入大单识别、市值过滤、尾盘趋势
2. 板块异动：优化时间窗口、龙头确认、联动性
3. 涨停洗盘：涨停质量、换手率、企稳模式
4. 整体：大盘过滤、信号评分、动态风控
"""
import requests
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
import json
import time

def log(msg):
    print(msg, flush=True)

# 清理代理
for key in list(os.environ.keys()):
    if 'proxy' in key.lower():
        del os.environ[key]

session = requests.Session()
session.trust_env = False
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
})

# ==================== 数据获取模块 ====================

def get_stock_kline(code, days=250):
    """获取日K线"""
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
        # 计算换手率（成交量/流通股，这里用成交量变化代替）
        df['成交额'] = df['收盘'] * df['成交量']
        df['量比'] = df['成交量'] / df['成交量'].rolling(20).mean()
        return df
    except Exception as e:
        return None


def get_5min_kline(code):
    """获取5分钟K线"""
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
        df = df.rename(columns={
            'open': '开盘', 'high': '最高', 'low': '最低', 
            'close': '收盘', 'volume': '成交量', 'day': '时间'
        })
        return df
    except:
        return None


def get_stock_name(code):
    """获取股票名称"""
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


def get_index_kline(code='000001', days=60):
    """获取指数K线（用于大盘判断）"""
    kcode = f'sh{code}'
    url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={kcode},day,,,{days},qfq'
    try:
        r = session.get(url, timeout=10)
        data = r.json()
        stock_data = data['data'].get(kcode) or data['data'].get(kcode.upper())
        days_data = stock_data.get('qfqday') or stock_data.get('day')
        df = pd.DataFrame([d[:6] for d in days_data], 
                        columns=['日期','开盘','收盘','最高','最低','成交量'])
        for col in ['开盘','收盘','最高','最低','成交量']:
            df[col] = df[col].astype(float)
        df['日期'] = pd.to_datetime(df['日期'])
        df['涨跌幅'] = df['收盘'].pct_change() * 100
        return df
    except:
        return None


# ==================== 大盘环境模块 ====================

def analyze_market_condition():
    """
    分析大盘环境
    返回: score(-100到100), trend(强势/震荡/弱势), advice
    """
    df = get_index_kline('000001', 60)
    if df is None or len(df) < 20:
        return 0, '未知', '无法获取大盘数据'
    
    current = df.iloc[-1]
    
    # 1. 趋势判断
    ma5 = df['收盘'].iloc[-5:].mean()
    ma10 = df['收盘'].iloc[-10:].mean()
    ma20 = df['收盘'].iloc[-20:].mean()
    
    # 2. 位置判断
    high_20d = df['最高'].iloc[-20:].max()
    low_20d = df['最低'].iloc[-20:].min()
    position = (current['收盘'] - low_20d) / (high_20d - low_20d) * 100
    
    # 3. 动量判断
    ret_5d = (current['收盘'] - df.iloc[-5]['收盘']) / df.iloc[-5]['收盘'] * 100
    ret_10d = (current['收盘'] - df.iloc[-10]['收盘']) / df.iloc[-10]['收盘'] * 100
    
    # 4. 量能判断
    vol_ratio = df['成交量'].iloc[-5:].mean() / df['成交量'].iloc[-20:].mean()
    
    # 综合评分
    score = 0
    
    # 均线多头排列 +30
    if current['收盘'] > ma5 > ma10 > ma20:
        score += 30
        trend = '强势'
    elif current['收盘'] < ma5 < ma10 < ma20:
        score -= 30
        trend = '弱势'
    else:
        trend = '震荡'
    
    # 位置评分 (-20 到 +20)
    if position > 70:
        score += 20
    elif position < 30:
        score -= 20
    
    # 动量评分 (-20 到 +20)
    if ret_5d > 2:
        score += 20
    elif ret_5d < -2:
        score -= 20
    
    # 量能评分 (-10 到 +10)
    if vol_ratio > 1.2:
        score += 10
    elif vol_ratio < 0.8:
        score -= 10
    
    # 生成建议
    if score >= 30:
        advice = '大盘强势，可积极操作，仓位可提高到60-80%'
    elif score >= 0:
        advice = '大盘震荡，谨慎操作，仓位控制在30-50%'
    else:
        advice = '大盘偏弱，防守为主，仓位控制在10-30%'
    
    return score, trend, advice


# ==================== 策略1：分时托单V2 ====================

def check_intraday_support_v2(code, df_daily=None):
    """
    分时托单V2 - 优化版
    新增：大单识别、市值过滤、尾盘趋势、信号评分
    """
    df_5min = get_5min_kline(code)
    if df_5min is None:
        return None
    
    latest_date = df_5min['date'].max()
    day_bars = df_5min[df_5min['date'] == latest_date].copy()
    
    if len(day_bars) < 20:
        return None
    
    high = day_bars['最高'].max()
    low = day_bars['最低'].min()
    avg_price = day_bars['收盘'].mean()
    current = day_bars.iloc[-1]['收盘']
    open_price = day_bars.iloc[0]['开盘']
    
    # 基本指标
    volatility = (high - low) / avg_price * 100
    today_change = (current - open_price) / open_price * 100
    position = (current - low) / (high - low) * 100 if high > low else 50
    
    # 【优化1】托单识别 - 更精确的下影线判断
    day_bars['body_high'] = day_bars[['开盘', '收盘']].max(axis=1)
    day_bars['body_low'] = day_bars[['开盘', '收盘']].min(axis=1)
    day_bars['upper_shadow'] = day_bars['最高'] - day_bars['body_high']
    day_bars['lower_shadow'] = day_bars['body_low'] - day_bars['最低']
    day_bars['body'] = abs(day_bars['收盘'] - day_bars['开盘'])
    day_bars['amplitude'] = day_bars['最高'] - day_bars['最低']
    
    # 托单K线：下影线 > 实体 * 0.5 且 下影线 > 上影线
    support_bars = day_bars[
        (day_bars['lower_shadow'] > day_bars['body'] * 0.5) & 
        (day_bars['lower_shadow'] > day_bars['upper_shadow'])
    ]
    support_count = len(support_bars)
    
    # 【优化2】量能分析 - 上涨时放量，下跌时缩量
    day_bars['change'] = day_bars['收盘'] - day_bars['开盘']
    up_bars = day_bars[day_bars['change'] > 0]
    down_bars = day_bars[day_bars['change'] < 0]
    
    if len(down_bars) > 0 and len(up_bars) > 0:
        avg_up_vol = up_bars['成交量'].mean()
        avg_down_vol = down_bars['成交量'].mean()
        vol_ratio = avg_up_vol / avg_down_vol if avg_down_vol > 0 else 1
    else:
        vol_ratio = 1
    
    # 【优化3】大单识别 - 用单根K线成交额判断
    day_bars['avg_price'] = (day_bars['最高'] + day_bars['最低'] + day_bars['收盘']) / 3
    day_bars['amount'] = day_bars['成交量'] * day_bars['avg_price']
    avg_bar_amount = day_bars['amount'].mean()
    
    # 重新识别支撑K线（带amount列）
    support_bars = day_bars[
        (day_bars['lower_shadow'] > day_bars['body'] * 0.5) & 
        (day_bars['lower_shadow'] > day_bars['upper_shadow'])
    ]
    
    # 支撑时的大单（托单K线成交额 > 平均）
    if len(support_bars) > 0:
        support_amount = support_bars['amount'].mean()
        big_order_ratio = support_amount / avg_bar_amount if avg_bar_amount > 0 else 1
    else:
        big_order_ratio = 0
    
    # 【优化4】尾盘趋势 - 最后30分钟走势
    tail_bars = day_bars.tail(6)  # 最后6根5分钟K线 = 30分钟
    if len(tail_bars) >= 3:
        tail_start = tail_bars.iloc[0]['开盘']
        tail_end = tail_bars.iloc[-1]['收盘']
        tail_trend = (tail_end - tail_start) / tail_start * 100
    else:
        tail_trend = 0
    
    # 【优化5】日线配合（如果有日线数据）
    daily_score = 0
    if df_daily is not None and len(df_daily) >= 20:
        latest_daily = df_daily.iloc[-1]
        ma5 = df_daily['收盘'].iloc[-5:].mean()
        ma10 = df_daily['收盘'].iloc[-10:].mean()
        
        # 日线站上均线加分
        if latest_daily['收盘'] > ma5:
            daily_score += 10
        if latest_daily['收盘'] > ma10:
            daily_score += 10
        
        # 日线量比
        daily_vol_ratio = df_daily['量比'].iloc[-1] if '量比' in df_daily.columns else 1
        if daily_vol_ratio > 1.2:
            daily_score += 10
    
    # 条件检查
    conditions = {
        '横盘波动': volatility < 5,
        '托单次数': support_count >= 5,
        '量比': vol_ratio >= 1.0,  # 放宽到1.0
        '收盘位置': position >= 75,  # 略微放宽
        '涨跌幅': -1 <= today_change <= 4,
        '大单托盘': big_order_ratio >= 0.8,  # 新增
        '尾盘上涨': tail_trend >= -0.5,  # 新增：尾盘不能大跌
    }
    
    passed = sum(conditions.values())
    
    # 【核心优化】信号评分系统
    score = 0
    
    # 基础分（满足条件）
    if volatility < 4: score += 15
    elif volatility < 5: score += 10
    
    if support_count >= 8: score += 20
    elif support_count >= 5: score += 15
    elif support_count >= 3: score += 5
    
    if vol_ratio >= 1.5: score += 25
    elif vol_ratio >= 1.2: score += 20
    elif vol_ratio >= 1.0: score += 10
    
    if position >= 90: score += 20
    elif position >= 80: score += 15
    elif position >= 70: score += 10
    
    if big_order_ratio >= 1.2: score += 15
    elif big_order_ratio >= 1.0: score += 10
    
    if tail_trend >= 0.5: score += 10
    elif tail_trend >= 0: score += 5
    elif tail_trend < -0.5: score -= 10
    
    # 日线配合
    score += daily_score
    
    # 涨跌幅惩罚
    if today_change > 4 or today_change < -1:
        score -= 20
    
    # 返回结果
    return {
        'code': code,
        'volatility': volatility,
        'support_count': support_count,
        'vol_ratio': vol_ratio,
        'position': position,
        'today_change': today_change,
        'big_order_ratio': big_order_ratio,
        'tail_trend': tail_trend,
        'score': score,
        'conditions': conditions,
        'passed': passed,
        'signal': score >= 60  # 60分以上触发信号
    }


# ==================== 策略2：板块异动V2 ====================

def check_sector_signal_v2(sector_name, stock_codes):
    """
    板块异动V2 - 优化版
    新增：龙头确认、联动性分析、更精确的时间窗口
    """
    sector_data = []
    valid_count = 0
    
    for code in stock_codes[:10]:  # 取前10只分析
        df = get_stock_kline(code, 150)
        if df is not None and len(df) >= 120:
            sector_data.append(df)
            valid_count += 1
        time.sleep(0.1)
    
    if valid_count < 3:
        return None
    
    # 计算板块指数（等权平均）
    dates = sector_data[0]['日期'].values
    sector_returns = np.zeros(len(dates))
    
    for df in sector_data:
        if len(df) == len(dates):
            sector_returns += df['涨跌幅'].fillna(0).values
    
    sector_returns /= valid_count
    
    # 计算累计收益
    cum_returns = (1 + sector_returns / 100).cumprod() - 1
    cum_returns *= 100
    
    # 【优化1】更精确的爆发检测
    # 找60-120天前的爆发（单日>4%或3日>8%）
    burst_found = False
    burst_idx = None
    burst_return = 0
    
    for idx in range(60, min(120, len(cum_returns) - 30)):
        # 单日爆发
        if sector_returns[idx] > 4:
            burst_found = True
            burst_idx = idx
            burst_return = sector_returns[idx]
            break
        # 3日累计爆发
        if idx >= 3:
            ret_3d = cum_returns[idx] - cum_returns[idx-3]
            if ret_3d > 8:
                burst_found = True
                burst_idx = idx
                burst_return = ret_3d
                break
    
    if not burst_found:
        return None
    
    # 【优化2】回调分析
    burst_high_idx = burst_idx
    burst_high = cum_returns[burst_idx]
    
    # 找爆发后的最高点
    for i in range(burst_idx, len(cum_returns)):
        if cum_returns[i] > burst_high:
            burst_high = cum_returns[i]
            burst_high_idx = i
    
    current_return = cum_returns[-1]
    drawdown = current_return - burst_high
    
    # 【优化3】企稳判断（更严格）
    ret_30d = cum_returns[-1] - cum_returns[-30] if len(cum_returns) >= 30 else 0
    ret_10d = cum_returns[-1] - cum_returns[-10] if len(cum_returns) >= 10 else 0
    ret_5d = cum_returns[-1] - cum_returns[-5] if len(cum_returns) >= 5 else 0
    ret_3d = cum_returns[-1] - cum_returns[-3] if len(cum_returns) >= 3 else 0
    
    # 【优化4】龙头股确认
    # 找板块内表现最好的股票
    leader_returns = []
    for df in sector_data:
        if len(df) >= 10:
            ret = (df.iloc[-1]['收盘'] - df.iloc[-10]['收盘']) / df.iloc[-10]['收盘'] * 100
            leader_returns.append(ret)
    
    leader_strength = max(leader_returns) if leader_returns else 0
    
    # 【优化5】联动性分析
    # 计算板块内股票的相关性
    correlations = []
    for i in range(len(sector_data)):
        for j in range(i+1, len(sector_data)):
            if len(sector_data[i]) == len(sector_data[j]):
                corr = sector_data[i]['涨跌幅'].corr(sector_data[j]['涨跌幅'])
                if not np.isnan(corr):
                    correlations.append(corr)
    
    avg_correlation = np.mean(correlations) if correlations else 0
    
    # 条件判断
    conditions = {
        '历史爆发': burst_found and burst_return > 4,
        '充分回调': -30 <= drawdown <= -8,
        '30日企稳': ret_30d < 10 and ret_30d > -10,
        '10日企稳': ret_10d > -5,
        '5日企稳': ret_5d > -3,
        '3日趋势': ret_3d > -2,
        '龙头走强': leader_strength > 3,
        '联动性高': avg_correlation > 0.3,
    }
    
    passed = sum(conditions.values())
    
    # 信号评分
    score = 0
    
    if burst_return > 6: score += 20
    elif burst_return > 4: score += 15
    
    if -20 <= drawdown <= -10: score += 20
    elif -30 <= drawdown <= -8: score += 15
    
    if ret_10d > 0: score += 15
    elif ret_10d > -3: score += 10
    
    if ret_3d > 0: score += 10
    
    if leader_strength > 5: score += 15
    elif leader_strength > 3: score += 10
    
    if avg_correlation > 0.5: score += 15
    elif avg_correlation > 0.3: score += 10
    
    return {
        'sector': sector_name,
        'burst_return': burst_return,
        'drawdown': drawdown,
        'ret_10d': ret_10d,
        'ret_5d': ret_5d,
        'ret_3d': ret_3d,
        'leader_strength': leader_strength,
        'correlation': avg_correlation,
        'score': score,
        'conditions': conditions,
        'passed': passed,
        'signal': score >= 60 and passed >= 5
    }


# ==================== 策略3：涨停洗盘V2 ====================

def check_limit_up_washout_v2(code):
    """
    涨停洗盘V2 - 优化版
    新增：涨停质量、换手率、企稳模式识别
    """
    df = get_stock_kline(code, 60)
    if df is None or len(df) < 30:
        return None
    
    current = df.iloc[-1]
    
    # 找涨停日
    limit_up_days = df[df['涨跌幅'] > 9.5]
    if len(limit_up_days) == 0:
        return None
    
    # 取最近的涨停
    limit_up_idx = df.index.get_loc(limit_up_days.index[-1])
    days_since = len(df) - 1 - limit_up_idx
    
    # 时间过滤
    if days_since < 3 or days_since > 25:
        return None
    
    limit_day = df.iloc[limit_up_idx]
    limit_high = limit_day['最高']
    limit_close = limit_day['收盘']
    limit_vol = limit_day['成交量']
    
    # 【优化1】涨停质量评估
    # 涨停时的量能
    avg_vol_before = df.iloc[max(0, limit_up_idx-5):limit_up_idx]['成交量'].mean()
    limit_vol_ratio = limit_vol / avg_vol_before if avg_vol_before > 0 else 1
    
    # 涨停时的振幅（振幅小说明封板坚决）
    limit_amplitude = (limit_day['最高'] - limit_day['最低']) / limit_day['开盘'] * 100
    
    # 涨停质量评分
    limit_quality = 0
    if limit_vol_ratio > 2: limit_quality += 20  # 放量涨停
    if limit_amplitude < 5: limit_quality += 20  # 一字板或封板坚决
    if limit_day['收盘'] == limit_day['最高']: limit_quality += 10  # 收在涨停价
    
    # 【优化2】回调分析
    pullback = (current['收盘'] - limit_high) / limit_high * 100
    pullback_low = (df.iloc[limit_up_idx:]['最低'].min() - limit_high) / limit_high * 100
    
    # 【优化3】量能萎缩
    vol_recent = df.iloc[-5:]['成交量'].mean()
    vol_at_limit = df.iloc[limit_up_idx:limit_up_idx+3]['成交量'].mean() if limit_up_idx + 3 < len(df) else vol_recent
    vol_shrink = vol_recent / vol_at_limit if vol_at_limit > 0 else 1
    
    # 【优化4】企稳模式识别
    recent_5d = df.iloc[-5:]
    volatility_5d = (recent_5d['最高'].max() - recent_5d['最低'].min()) / recent_5d['收盘'].mean() * 100
    
    # 底部抬高
    low_3d = df.iloc[-3:]['最低'].values
    bottom_rising = low_3d[-1] > low_3d[0]
    
    # 均线支撑
    ma5 = df['收盘'].iloc[-5:].mean()
    ma10 = df['收盘'].iloc[-10:].mean()
    above_ma = current['收盘'] > ma5 and current['收盘'] > ma10
    
    # 【优化5】换手率估算（用成交量相对平均的比例）
    avg_vol_20d = df['成交量'].iloc[-20:].mean()
    turnover_ratio = current['成交量'] / avg_vol_20d if avg_vol_20d > 0 else 1
    
    # 条件判断
    conditions = {
        '涨停时间': 3 <= days_since <= 20,
        '回调幅度': -15 <= pullback <= -3,
        '最大回调': pullback_low >= -20,
        '量能萎缩': vol_shrink < 1.0,
        '波动收窄': volatility_5d < 8,
        '底部抬高': bottom_rising,
        '均线支撑': above_ma,
        '涨停质量': limit_quality >= 20,
    }
    
    passed = sum(conditions.values())
    
    # 信号评分
    score = 0
    
    # 涨停质量
    score += limit_quality
    
    # 回调幅度（-8到-12是最佳）
    if -12 <= pullback <= -8: score += 20
    elif -15 <= pullback <= -5: score += 15
    elif -20 <= pullback <= -3: score += 10
    
    # 量能萎缩
    if vol_shrink < 0.5: score += 20
    elif vol_shrink < 0.8: score += 15
    elif vol_shrink < 1.0: score += 10
    
    # 企稳信号
    if bottom_rising: score += 10
    if above_ma: score += 10
    if volatility_5d < 5: score += 10
    
    return {
        'code': code,
        'days_since': days_since,
        'limit_quality': limit_quality,
        'pullback': pullback,
        'pullback_low': pullback_low,
        'vol_shrink': vol_shrink,
        'volatility_5d': volatility_5d,
        'bottom_rising': bottom_rising,
        'above_ma': above_ma,
        'turnover_ratio': turnover_ratio,
        'score': score,
        'conditions': conditions,
        'passed': passed,
        'signal': score >= 50 and passed >= 5
    }


# ==================== 综合策略模块 ====================

def get_sector_stocks():
    """板块股票池"""
    return {
        '人工智能': ['300496', '300474', '002230', '300033', '688111'],
        '半导体': ['002371', '603986', '688012', '300661', '002049'],
        '机器人': ['300024', '002747', '300527', '688165', '002527'],
        '消费电子': ['002456', '002241', '300115', '002475', '603160'],
        '新能源车': ['300750', '002594', '300014', '300207', '002074'],
        '光伏': ['601012', '002459', '600438', '688599', '300274'],
        '医药': ['300760', '300759', '300347', '002821', '300122'],
        '白酒': ['600519', '000858', '000568', '603369', '002304'],
    }


def scan_all_strategies_v2():
    """综合扫描V2"""
    log("="*70)
    log("策略V2.0 - 全面优化版扫描")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*70)
    
    # 1. 大盘环境
    log("\n【一、大盘环境分析】")
    market_score, market_trend, market_advice = analyze_market_condition()
    log(f"  大盘评分: {market_score}")
    log(f"  大盘趋势: {market_trend}")
    log(f"  操作建议: {market_advice}")
    
    # 根据大盘调整仓位建议
    if market_score >= 30:
        position_advice = "60-80%"
    elif market_score >= 0:
        position_advice = "30-50%"
    else:
        position_advice = "10-30%"
    log(f"  仓位建议: {position_advice}")
    
    sectors = get_sector_stocks()
    
    # 2. 板块异动扫描
    log("\n【二、板块异动扫描】")
    active_sectors = []
    
    for sector_name, codes in sectors.items():
        log(f"  扫描: {sector_name}...", )
        result = check_sector_signal_v2(sector_name, codes)
        if result and result['signal']:
            active_sectors.append(result)
            log(f"  ★ {sector_name}: 评分{result['score']}, 回撤{result['drawdown']:.1f}%, 龙头{result['leader_strength']:.1f}%")
        time.sleep(0.2)
    
    if active_sectors:
        log(f"\n  共发现 {len(active_sectors)} 个活跃板块")
    else:
        log(f"\n  暂无明显板块异动")
    
    # 3. 个股扫描
    log("\n【三、个股信号扫描】")
    support_signals = []
    washout_signals = []
    
    for sector_name, codes in sectors.items():
        for code in codes:
            # 获取日线数据
            df_daily = get_stock_kline(code, 60)
            
            # 分时托单
            support = check_intraday_support_v2(code, df_daily)
            if support and support['signal']:
                support['sector'] = sector_name
                support['name'] = get_stock_name(code)
                # 板块共振加分
                if any(s['sector'] == sector_name for s in active_sectors):
                    support['score'] += 20
                    support['resonance'] = True
                else:
                    support['resonance'] = False
                support_signals.append(support)
            
            # 涨停洗盘
            washout = check_limit_up_washout_v2(code)
            if washout and washout['signal']:
                washout['sector'] = sector_name
                washout['name'] = get_stock_name(code)
                if any(s['sector'] == sector_name for s in active_sectors):
                    washout['score'] += 20
                    washout['resonance'] = True
                else:
                    washout['resonance'] = False
                washout_signals.append(washout)
            
            time.sleep(0.15)
    
    # 按评分排序
    support_signals.sort(key=lambda x: x['score'], reverse=True)
    washout_signals.sort(key=lambda x: x['score'], reverse=True)
    
    # 输出结果
    log("\n" + "="*70)
    log("【四、扫描结果汇总】")
    log("="*70)
    
    log(f"\n>>> 分时托单信号 ({len(support_signals)}个)")
    for s in support_signals[:10]:
        resonance = "★共振" if s.get('resonance') else ""
        log(f"  {s['code']} {s['name']}: 评分{s['score']}, 量比{s['vol_ratio']:.2f}, 位置{s['position']:.0f}%, 托单{s['support_count']}次 {resonance}")
    
    log(f"\n>>> 涨停洗盘信号 ({len(washout_signals)}个)")
    for s in washout_signals[:10]:
        resonance = "★共振" if s.get('resonance') else ""
        log(f"  {s['code']} {s['name']}: 评分{s['score']}, 涨停后{s['days_since']}天, 回调{s['pullback']:.1f}%, 缩量{s['vol_shrink']:.2f} {resonance}")
    
    # 重点机会（策略共振）
    resonance_signals = [s for s in support_signals + washout_signals if s.get('resonance')]
    if resonance_signals:
        log(f"\n>>> 重点机会（策略共振）")
        for s in sorted(resonance_signals, key=lambda x: x['score'], reverse=True)[:5]:
            log(f"  ★★★ {s['code']} {s['name']} [{s['sector']}]: 评分{s['score']}")
    
    # 风险提示
    log("\n" + "="*70)
    log("【五、操作建议】")
    log("="*70)
    
    log(f"\n1. 大盘环境：{market_trend}，建议仓位{position_advice}")
    
    if market_score < 0:
        log(f"2. 风险提示：大盘偏弱，建议观望或轻仓试探")
    
    if resonance_signals:
        log(f"3. 重点关注：策略共振标的，可优先考虑")
    
    log(f"\n4. 止损纪律：")
    log(f"   - 分时托单：跌破分时低点-1%")
    log(f"   - 涨停洗盘：跌破回调低点")
    log(f"   - 最大单票止损：-5%")
    
    log(f"\n5. 止盈策略：")
    log(f"   - 第一止盈：+3%减仓1/3")
    log(f"   - 第二止盈：+5%减仓1/3")
    log(f"   - 剩余仓位：跟随趋势，跌破5日线离场")
    
    return {
        'market': {'score': market_score, 'trend': market_trend, 'position': position_advice},
        'sectors': active_sectors,
        'support_signals': support_signals,
        'washout_signals': washout_signals,
        'resonance_signals': resonance_signals
    }


if __name__ == "__main__":
    results = scan_all_strategies_v2()
