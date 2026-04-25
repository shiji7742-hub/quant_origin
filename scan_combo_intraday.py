"""
板块异动 + 分时托单 组合策略

核心逻辑：
1. 先选出潜力板块（板块异动策略）
2. 在潜力板块中找分时托单信号

分时托单特征：
- 分时图横盘整理
- 小单连续往下砸
- 大单一下子吃进收回（托单护盘）
"""
import requests
import pandas as pd
import numpy as np
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

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


def get_5min_kline(code):
    """获取5分钟K线"""
    code = str(code).zfill(6)
    kcode = f'sh{code}' if code.startswith('6') else f'sz{code}'
    url = f'https://web.ifzq.gtimg.cn/appstock/app/kline/mkline?param={kcode},m5,,320'
    try:
        r = session.get(url, timeout=8)
        data = r.json()
        if 'data' not in data:
            return None
        stock_data = data['data'].get(kcode) or data['data'].get(kcode.upper())
        if not stock_data or 'm5' not in stock_data:
            return None
        klines = stock_data['m5']
        if len(klines) < 20:
            return None
        df = pd.DataFrame(klines, columns=['时间', '开盘', '收盘', '最高', '最低', '成交量'])
        for col in ['开盘', '收盘', '最高', '最低', '成交量']:
            df[col] = df[col].astype(float)
        return df
    except:
        return None


def get_stock_kline(code, days=180):
    """获取日K线"""
    code = str(code).zfill(6)
    kcode = f'sh{code}' if code.startswith('6') else f'sz{code}'
    url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={kcode},day,,,{days},qfq'
    try:
        r = session.get(url, timeout=8)
        data = r.json()
        if not data.get('data'):
            return None
        stock_data = data['data'].get(kcode) or data['data'].get(kcode.upper())
        if not stock_data or 'qfqday' not in stock_data:
            return None
        days_data = stock_data['qfqday']
        if len(days_data) < 10:
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


def get_stock_name(code):
    """获取股票名称"""
    try:
        url = f'https://qt.gtimg.cn/q=s_{("sh" if code.startswith("6") else "sz")}{code}'
        r = session.get(url, timeout=5)
        text = r.text
        if '~' in text:
            parts = text.split('~')
            if len(parts) > 1:
                return parts[1]
    except:
        pass
    return code


def get_sector_stocks():
    """获取各板块成分股"""
    return {
        '人工智能': {
            '龙头': ['002230', '300474', '002415'],
            '成分': ['002230', '300474', '002415', '300496', '300624', '002049', 
                    '300044', '002362', '300212', '688777']
        },
        '机器人': {
            '龙头': ['002747', '300024', '300607'],
            '成分': ['002747', '300024', '300607', '002527', '300124', '002270',
                    '300367', '688165', '002472', '300730']
        },
        '半导体': {
            '龙头': ['002371', '603501', '688981'],
            '成分': ['002371', '603501', '688981', '002049', '300661', '688012',
                    '603160', '002185', '300782', '688396']
        },
        '消费电子': {
            '龙头': ['002475', '002241', '603160'],
            '成分': ['002475', '002241', '603160', '601138', '002036', '002456',
                    '002600', '300115', '002236', '300671']
        },
        '光伏': {
            '龙头': ['601012', '002459', '600438'],
            '成分': ['601012', '002459', '600438', '688599', '300274', '002129',
                    '603806', '300763', '601865', '300724']
        },
        '新能源车': {
            '龙头': ['002594', '300750', '002466'],
            '成分': ['002594', '300750', '002466', '002074', '300014', '300207',
                    '002340', '300450', '600884', '300457']
        },
    }


def estimate_sector_trend(stocks, days=180):
    """用龙头股估算板块走势"""
    all_data = []
    for code in stocks:
        df = get_stock_kline(code, days)
        if df is not None and len(df) > 60:
            all_data.append(df[['日期', '涨跌幅']].set_index('日期')['涨跌幅'])
    if len(all_data) == 0:
        return None
    combined = pd.concat(all_data, axis=1)
    return combined.mean(axis=1)


def check_sector_signal(daily_returns, min_drawdown=15):
    """检测板块异动信号"""
    if daily_returns is None or len(daily_returns) < 90:
        return False, None, "数据不足"
    
    daily_returns = daily_returns.dropna()
    if len(daily_returns) < 90:
        return False, None, "有效数据不足"
    
    old_period = daily_returns.iloc[:-60]
    recent_30d = daily_returns.iloc[-30:]
    recent_10d = daily_returns.iloc[-10:]
    recent_5d = daily_returns.iloc[-5:]
    
    if len(old_period) < 30:
        return False, None, "历史数据不足"
    
    surge_days = old_period[old_period > 5.0]
    if len(surge_days) == 0:
        return False, None, "无早期爆发"
    
    max_surge_value = surge_days.max()
    max_surge_idx = surge_days.idxmax()
    
    after_surge = daily_returns[daily_returns.index >= max_surge_idx]
    if len(after_surge) < 30:
        return False, None, "爆发后数据不足"
    
    cumsum = after_surge.cumsum()
    max_gain = cumsum.max()
    current_gain = cumsum.iloc[-1]
    drawdown = max_gain - current_gain
    
    if drawdown < min_drawdown:
        return False, None, f"回撤不足({drawdown:.1f}%)"
    if drawdown > 25:
        return False, None, f"回撤过大({drawdown:.1f}%)"
    
    if recent_30d.sum() > 5:
        return False, None, "近30日涨太多"
    if recent_10d.sum() < -3:
        return False, None, "近10日仍在下跌"
    if recent_5d.sum() < -2:
        return False, None, "近5日仍在下跌"
    
    days_since = (daily_returns.index[-1] - max_surge_idx).days
    
    return True, {
        'surge_date': max_surge_idx.strftime('%Y-%m-%d'),
        'surge_value': round(max_surge_value, 2),
        'drawdown': round(drawdown, 2),
        'days_since': days_since,
        'recent_5d': round(recent_5d.sum(), 2),
    }, "符合条件"


def check_intraday_support(df_5min, df_daily):
    """
    检测分时托单信号
    
    核心特征：
    1. 分时横盘（波动小）
    2. 多次下探收回（下影线多）
    3. 下跌量小、反弹量大
    4. 收盘守住
    """
    if df_5min is None or len(df_5min) < 20:
        return False, None, "5分钟数据不足"
    
    if df_daily is None or len(df_daily) < 5:
        return False, None, "日K数据不足"
    
    # 取最近一天的5分钟K线（约48根）
    today_bars = df_5min.tail(48)
    if len(today_bars) < 10:
        return False, None, "今日数据不足"
    
    high = today_bars['最高'].max()
    low = today_bars['最低'].min()
    avg_price = today_bars['收盘'].mean()
    current = today_bars.iloc[-1]['收盘']
    
    # 条件1：分时横盘
    volatility = (high - low) / avg_price * 100
    if volatility > 4.0:
        return False, None, f"波动过大({volatility:.1f}%)"
    
    # 条件2：多次下探收回
    today_bars = today_bars.copy()
    today_bars['下影线'] = today_bars['收盘'] - today_bars['最低']
    today_bars['上影线'] = today_bars['最高'] - today_bars['收盘']
    today_bars['实体'] = abs(today_bars['收盘'] - today_bars['开盘'])
    
    # 下影线明显的K线（托单特征）
    support_bars = today_bars[today_bars['下影线'] > today_bars['实体'] * 0.3]
    support_count = len(support_bars)
    
    if support_count < 2:
        return False, None, f"托单次数不足({support_count})"
    
    # 条件3：量能分析
    today_bars['涨跌'] = today_bars['收盘'] - today_bars['开盘']
    down_bars = today_bars[today_bars['涨跌'] < 0]
    up_bars = today_bars[today_bars['涨跌'] > 0]
    
    if len(down_bars) < 2 or len(up_bars) < 2:
        return False, None, "K线数量不足"
    
    avg_down_vol = down_bars['成交量'].mean()
    avg_up_vol = up_bars['成交量'].mean()
    vol_ratio = avg_up_vol / avg_down_vol if avg_down_vol > 0 else 1
    
    # 条件4：收盘位置
    position = (current - low) / (high - low) * 100 if high > low else 50
    if position < 40:
        return False, None, f"收盘位置偏低({position:.0f}%)"
    
    # 条件5：日K涨跌幅
    today_daily = df_daily.iloc[-1]
    yesterday_close = df_daily.iloc[-2]['收盘']
    today_change = (today_daily['收盘'] - yesterday_close) / yesterday_close * 100
    
    if today_change < -3:
        return False, None, f"今日跌幅过大({today_change:.1f}%)"
    
    # 大单托比
    if len(support_bars) > 0:
        support_vol = support_bars['成交量'].mean()
        avg_vol = today_bars['成交量'].mean()
        big_order_ratio = support_vol / avg_vol if avg_vol > 0 else 1
    else:
        big_order_ratio = 1
    
    return True, {
        '分时波动': f"{volatility:.2f}%",
        '托单次数': support_count,
        '量比': f"{vol_ratio:.2f}",
        '收盘位置': f"{position:.0f}%",
        '今日涨幅': f"{today_change:+.2f}%",
        '大单托比': f"{big_order_ratio:.2f}",
        '现价': round(current, 2),
        '分时低点': round(low, 2),
        '分时高点': round(high, 2),
    }, "符合托单"


def run_combo_scan():
    log("="*70)
    log("板块异动 + 分时托单 组合策略")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*70)
    
    log("\n【策略逻辑】")
    log("  Step 1: 板块异动选板块（60-150天前爆发→回撤15-25%→企稳）")
    log("  Step 2: 分时托单选个股（横盘+小单砸+大单托）")
    
    log("\n【分时托单特征】")
    log("  - 分时图横盘整理（波动<4%）")
    log("  - 多次下探收回（下影线多）")
    log("  - 小单往下砸，大单吃进收回")
    log("  - 收盘守住分时高位")
    
    # Step 1: 扫描潜力板块
    log("\n" + "="*70)
    log("[1] 扫描潜力板块")
    log("="*70)
    
    sector_stocks = get_sector_stocks()
    potential_sectors = []
    
    for sector, data in sector_stocks.items():
        log(f"\n  分析: {sector}")
        trend = estimate_sector_trend(data['龙头'])
        if trend is None:
            log(f"    -> 无数据")
            continue
        
        is_signal, details, reason = check_sector_signal(trend, min_drawdown=12)
        
        if is_signal:
            log(f"    -> ✓ 符合条件")
            log(f"       回撤{details['drawdown']}%, 近5日{details['recent_5d']:+.1f}%")
            potential_sectors.append({
                '板块': sector,
                '成分股': data['成分'],
                **details
            })
        else:
            log(f"    -> ✗ {reason}")
    
    if not potential_sectors:
        log("\n当前无符合条件的潜力板块")
        return
    
    log(f"\n发现 {len(potential_sectors)} 个潜力板块")
    
    # Step 2: 在潜力板块中扫描分时托单
    log("\n" + "="*70)
    log("[2] 扫描分时托单信号")
    log("="*70)
    
    all_results = []
    
    for sector_info in potential_sectors:
        sector = sector_info['板块']
        stocks = sector_info['成分股']
        
        log(f"\n  扫描 {sector} ({len(stocks)}只)...")
        
        for code in stocks:
            df_5min = get_5min_kline(code)
            df_daily = get_stock_kline(code, days=30)
            
            if df_5min is None:
                continue
            
            is_signal, info, reason = check_intraday_support(df_5min, df_daily)
            
            if is_signal:
                name = get_stock_name(code)
                log(f"    ✓ {name}({code})")
                log(f"      波动{info['分时波动']}, 托单{info['托单次数']}次")
                
                all_results.append({
                    '代码': code,
                    '名称': name,
                    '板块': sector,
                    '板块回撤': f"{sector_info['drawdown']}%",
                    **info
                })
    
    # 结果
    log("\n" + "="*70)
    log("扫描结果")
    log("="*70)
    
    if all_results:
        log(f"\n【双重共振信号】({len(all_results)}只)")
        
        for r in all_results:
            log(f"\n  {r['名称']}({r['代码']}) - {r['板块']}")
            log(f"    板块回撤: {r['板块回撤']}")
            log(f"    分时波动: {r['分时波动']}, 托单{r['托单次数']}次")
            log(f"    量比: {r['量比']}, 大单托比: {r['大单托比']}")
            log(f"    收盘位置: {r['收盘位置']}, 今日{r['今日涨幅']}")
            log(f"    买点参考: {r['分时低点']} 附近")
        
        log("\n" + "-" * 50)
        log("【操作建议】")
        log("  1. 分时低点附近分批买入")
        log("  2. 止损: 跌破分时低点-2%")
        log("  3. 目标: 分时高点或更高")
        log("  4. 盘中继续观察是否有大单托")
        
        fname = f"板块分时组合_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        pd.DataFrame(all_results).to_excel(fname, index=False)
        log(f"\n已保存: {fname}")
    else:
        log("\n当前无双重共振信号")
        log("\n潜力板块列表：")
        for s in potential_sectors:
            log(f"  {s['板块']}: 回撤{s['drawdown']}%")
        log("\n建议：")
        log("  1. 盘中多时间点扫描")
        log("  2. 等待成分股形成分时托单形态")


if __name__ == "__main__":
    run_combo_scan()
