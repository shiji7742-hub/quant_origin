"""
综合策略扫描 - 周一开盘机会分析
结合三大策略：
1. 分时托单（5分钟K线）
2. 板块异动（板块先行筛选）
3. 涨停板破位洗盘
"""
import requests
import pandas as pd
import numpy as np
import os
from datetime import datetime
import json

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


def get_stock_kline(code, days=150):
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
        if len(days_data) < 30:
            return None
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


# ==================== 策略1：分时托单 ====================
def check_intraday_support(df_5min, date_str):
    """分时托单检测"""
    day_bars = df_5min[df_5min['date'] == date_str].copy()
    if len(day_bars) < 20:
        return False, None
    
    high = day_bars['最高'].max()
    low = day_bars['最低'].min()
    avg_price = day_bars['收盘'].mean()
    current = day_bars.iloc[-1]['收盘']
    open_price = day_bars.iloc[0]['开盘']
    
    volatility = (high - low) / avg_price * 100
    if volatility > 5.0:
        return False, None
    
    day_bars['下影线'] = day_bars.apply(
        lambda x: min(x['开盘'], x['收盘']) - x['最低'], axis=1)
    day_bars['实体'] = abs(day_bars['收盘'] - day_bars['开盘'])
    
    support_bars = day_bars[day_bars['下影线'] > day_bars['实体'] * 0.5]
    support_count = len(support_bars)
    
    if support_count < 3:
        return False, None
    
    day_bars['涨跌'] = day_bars['收盘'] - day_bars['开盘']
    down_bars = day_bars[day_bars['涨跌'] < 0]
    up_bars = day_bars[day_bars['涨跌'] > 0]
    
    if len(down_bars) < 2 or len(up_bars) < 2:
        return False, None
    
    avg_down_vol = down_bars['成交量'].mean()
    avg_up_vol = up_bars['成交量'].mean()
    vol_ratio = avg_up_vol / avg_down_vol if avg_down_vol > 0 else 1
    
    position = (current - low) / (high - low) * 100 if high > low else 50
    today_change = (current - open_price) / open_price * 100
    
    # 评分
    score = 0
    if vol_ratio > 1.2:
        score += 40
    elif vol_ratio > 1.0:
        score += 20
    if position > 80:
        score += 30
    elif position > 60:
        score += 15
    if support_count >= 5:
        score += 20
    if -0.5 <= today_change <= 3:
        score += 10
    
    if score < 30:
        return False, None
    
    return True, {
        'vol_ratio': vol_ratio,
        'position': position,
        'support_count': support_count,
        'today_change': today_change,
        'score': score,
        'low': low,
    }


# ==================== 策略2：板块异动 ====================
def check_sector_signal(sector_returns):
    """板块异动检测"""
    if len(sector_returns) < 90:
        return False, None
    
    old_period = sector_returns.iloc[:-60]
    recent_30d = sector_returns.iloc[-30:]
    recent_10d = sector_returns.iloc[-10:]
    recent_5d = sector_returns.iloc[-5:]
    
    if len(old_period) < 30:
        return False, None
    
    surge_days = old_period[old_period > 4.0]
    if len(surge_days) == 0:
        return False, None
    
    max_surge_idx = surge_days.index[0]
    after_surge = sector_returns[sector_returns.index >= max_surge_idx]
    
    if len(after_surge) < 30:
        return False, None
    
    cumsum = after_surge.cumsum()
    max_gain = cumsum.max()
    current_gain = cumsum.iloc[-1]
    drawdown = max_gain - current_gain
    
    if drawdown < 8 or drawdown > 30:
        return False, None
    
    if recent_30d.sum() > 10:
        return False, None
    if recent_10d.sum() < -8:
        return False, None
    if recent_5d.sum() < -5:
        return False, None
    
    return True, {'drawdown': drawdown}


# ==================== 策略3：涨停板破位洗盘 ====================
def check_limit_up_washout(df):
    """涨停板破位洗盘检测"""
    if len(df) < 30:
        return False, None
    
    # 找近30天内的涨停
    recent_30d = df.iloc[-30:]
    limit_up_days = recent_30d[recent_30d['涨跌幅'] > 9.5]
    
    if len(limit_up_days) == 0:
        return False, None
    
    # 取最近的涨停
    limit_up_idx = df.index.get_loc(limit_up_days.index[-1])
    days_since = len(df) - 1 - limit_up_idx
    
    if days_since < 3 or days_since > 20:
        return False, None
    
    # 涨停后的走势
    after_limit = df.iloc[limit_up_idx:]
    limit_high = df.iloc[limit_up_idx]['最高']
    current = df.iloc[-1]['收盘']
    
    # 回调幅度
    pullback = (current - limit_high) / limit_high * 100
    if pullback > -3 or pullback < -15:
        return False, None
    
    # 近3日企稳
    recent_3d = df.iloc[-3:]
    recent_volatility = (recent_3d['最高'].max() - recent_3d['最低'].min()) / recent_3d['收盘'].mean() * 100
    if recent_volatility > 8:
        return False, None
    
    # 量能萎缩
    vol_5d = df.iloc[-5:]['成交量'].mean()
    vol_10d = df.iloc[-10:-5]['成交量'].mean()
    vol_shrink = vol_5d / vol_10d if vol_10d > 0 else 1
    
    if vol_shrink > 1.2:
        return False, None
    
    score = 0
    score += min(30, abs(pullback) * 3)
    score += min(20, (1.2 - vol_shrink) * 50)
    score += min(20, (20 - days_since))
    
    return True, {
        'days_since': days_since,
        'pullback': pullback,
        'vol_shrink': vol_shrink,
        'score': score,
        'limit_high': limit_high,
    }


# ==================== 板块和股票池 ====================
def get_sector_stocks():
    """获取板块成分股"""
    return {
        '人工智能': ['002230', '300474', '002415', '300496', '300624', '002049', 
                   '300229', '002555', '300044', '688787'],
        '半导体': ['002371', '603501', '300661', '688012', '603160', '688981',
                 '688008', '688036', '002185', '300458'],
        '机器人': ['002747', '300024', '300607', '002527', '300124', '002270',
                 '688165', '300367', '603728', '300276'],
        '消费电子': ['002475', '002241', '601138', '002036', '002456', '002241'],
        '光伏': ['601012', '002459', '600438', '300274', '002129', '688599'],
        '新能源车': ['002594', '300750', '002466', '002074', '300014', '300207'],
    }


def run_comprehensive_scan():
    log("="*70)
    log("综合策略扫描 - 周一开盘机会分析")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*70)
    
    log("\n【扫描策略】")
    log("  1. 分时托单（量比>1.2, 位置>80%）")
    log("  2. 板块异动（爆发后回调企稳）")
    log("  3. 涨停板破位洗盘（涨停后回调-5%~-15%）")
    
    sector_stocks = get_sector_stocks()
    
    # 存储结果
    intraday_signals = []  # 分时托单
    sector_signals = []     # 板块异动
    washout_signals = []    # 涨停洗盘
    combo_signals = []      # 组合信号
    
    # 计算板块趋势
    log("\n[1] 分析板块异动...")
    sector_trends = {}
    active_sectors = []
    
    for sector, stocks in sector_stocks.items():
        all_returns = []
        for code in stocks[:5]:
            df = get_stock_kline(code, 150)
            if df is not None and len(df) > 90:
                all_returns.append(df.set_index('日期')['涨跌幅'])
        
        if all_returns:
            combined = pd.concat(all_returns, axis=1)
            sector_trend = combined.mean(axis=1)
            sector_trends[sector] = sector_trend
            
            is_active, info = check_sector_signal(sector_trend)
            if is_active:
                active_sectors.append(sector)
                sector_signals.append({
                    'sector': sector,
                    'drawdown': info['drawdown'],
                })
                log(f"  ★ {sector}: 板块异动（回撤{info['drawdown']:.1f}%后企稳）")
    
    if not active_sectors:
        log("  无明显板块异动信号")
    
    # 扫描个股
    log("\n[2] 扫描个股信号...")
    
    scanned = set()
    for sector, stocks in sector_stocks.items():
        for code in stocks:
            if code in scanned:
                continue
            scanned.add(code)
            
            # 获取数据
            df_daily = get_stock_kline(code, 60)
            df_5min = get_5min_kline(code)
            
            if df_daily is None:
                continue
            
            name = get_stock_name(code)
            signals_found = []
            
            # 策略1：分时托单
            if df_5min is not None:
                latest_date = df_5min['date'].max()
                is_support, support_info = check_intraday_support(df_5min, latest_date)
                if is_support:
                    signals_found.append('分时托单')
                    intraday_signals.append({
                        'code': code,
                        'name': name,
                        'sector': sector,
                        'strategy': '分时托单',
                        'vol_ratio': support_info['vol_ratio'],
                        'position': support_info['position'],
                        'support_count': support_info['support_count'],
                        'score': support_info['score'],
                        'low': support_info['low'],
                    })
            
            # 策略3：涨停洗盘
            is_washout, washout_info = check_limit_up_washout(df_daily)
            if is_washout:
                signals_found.append('涨停洗盘')
                washout_signals.append({
                    'code': code,
                    'name': name,
                    'sector': sector,
                    'strategy': '涨停洗盘',
                    'days_since': washout_info['days_since'],
                    'pullback': washout_info['pullback'],
                    'vol_shrink': washout_info['vol_shrink'],
                    'score': washout_info['score'],
                    'limit_high': washout_info['limit_high'],
                })
            
            # 组合信号：板块异动 + 个股信号
            if sector in active_sectors and signals_found:
                combo_signals.append({
                    'code': code,
                    'name': name,
                    'sector': sector,
                    'signals': '+'.join(signals_found),
                    'in_active_sector': True,
                })
    
    # ==================== 结果汇总 ====================
    log("\n" + "="*70)
    log("扫描结果汇总")
    log("="*70)
    
    # 板块异动
    log("\n【板块异动】")
    if sector_signals:
        for s in sector_signals:
            log(f"  ★ {s['sector']}: 回撤{s['drawdown']:.1f}%后企稳，关注板块内个股")
    else:
        log("  暂无明显板块异动")
    
    # 分时托单
    log("\n【分时托单信号】")
    if intraday_signals:
        df_intraday = pd.DataFrame(intraday_signals)
        df_intraday = df_intraday.sort_values('score', ascending=False)
        
        for i, (_, row) in enumerate(df_intraday.head(5).iterrows(), 1):
            in_active = "★板块共振" if row['sector'] in active_sectors else ""
            log(f"  {i}. {row['code']} {row['name']} ({row['sector']}) {in_active}")
            log(f"     量比{row['vol_ratio']:.2f}, 位置{row['position']:.0f}%, 托单{row['support_count']}次, 评分{row['score']}")
    else:
        log("  暂无分时托单信号")
    
    # 涨停洗盘
    log("\n【涨停板破位洗盘】")
    if washout_signals:
        df_washout = pd.DataFrame(washout_signals)
        df_washout = df_washout.sort_values('score', ascending=False)
        
        for i, (_, row) in enumerate(df_washout.head(5).iterrows(), 1):
            in_active = "★板块共振" if row['sector'] in active_sectors else ""
            log(f"  {i}. {row['code']} {row['name']} ({row['sector']}) {in_active}")
            log(f"     涨停后{row['days_since']}天, 回调{row['pullback']:.1f}%, 缩量{row['vol_shrink']:.2f}")
    else:
        log("  暂无涨停洗盘信号")
    
    # 组合信号（重点）
    log("\n" + "="*70)
    log("★★★ 重点机会（策略共振）★★★")
    log("="*70)
    
    if combo_signals:
        for s in combo_signals:
            log(f"\n  {s['code']} {s['name']} ({s['sector']})")
            log(f"    策略: {s['signals']} + 板块异动")
            log(f"    理由: 个股信号 + 板块共振，胜率更高")
    else:
        # 找最强信号
        log("\n  暂无多策略共振信号，以下为单策略最强信号:")
        
        if intraday_signals:
            best = max(intraday_signals, key=lambda x: x['score'])
            log(f"\n  【分时托单最强】")
            log(f"    {best['code']} {best['name']} ({best['sector']})")
            log(f"    量比{best['vol_ratio']:.2f}, 位置{best['position']:.0f}%, 评分{best['score']}")
        
        if washout_signals:
            best = max(washout_signals, key=lambda x: x['score'])
            log(f"\n  【涨停洗盘最强】")
            log(f"    {best['code']} {best['name']} ({best['sector']})")
            log(f"    涨停后{best['days_since']}天, 回调{best['pullback']:.1f}%")
    
    # 操作建议
    log("\n" + "="*70)
    log("周一操作建议")
    log("="*70)
    
    log("""
【开盘前】
  - 关注大盘走势，若大盘低开>1%，暂缓操作
  - 竞价阶段观察信号股的集合竞价情况

【分时托单操作】
  - 开盘后观察5分钟，确认没有大幅低开
  - 若低开<-1%且快速拉回，可考虑买入
  - 止损：跌破周五分时最低点-1%

【涨停洗盘操作】
  - 等待放量突破信号，不要抢跑
  - 突破涨停高点时可追入
  - 止损：跌破回调低点

【板块共振优先】
  - 若个股信号+板块异动，优先考虑
  - 板块龙头股优先

【仓位控制】
  - 单票不超过20%仓位
  - 同板块不超过30%仓位
""")
    
    # 保存结果
    fname = f"综合扫描_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    with pd.ExcelWriter(fname, engine='openpyxl') as writer:
        if intraday_signals:
            pd.DataFrame(intraday_signals).to_excel(writer, sheet_name='分时托单', index=False)
        if washout_signals:
            pd.DataFrame(washout_signals).to_excel(writer, sheet_name='涨停洗盘', index=False)
        if sector_signals:
            pd.DataFrame(sector_signals).to_excel(writer, sheet_name='板块异动', index=False)
    log(f"\n已保存: {fname}")


if __name__ == "__main__":
    run_comprehensive_scan()
