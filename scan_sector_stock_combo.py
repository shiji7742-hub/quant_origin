"""
板块异动 + 横盘托单 组合策略
1. 先用板块异动策略选出潜力板块
2. 再在这些板块中用横盘托单策略选个股
"""
import requests
import pandas as pd
import json
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

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


# ==================== 数据获取 ====================
def get_stock_kline(code, days=180):
    """获取个股K线"""
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


def get_sector_stocks():
    """获取各板块的成分股"""
    # 科技成长板块（回测表现最好的）
    sector_stocks = {
        '人工智能': {
            '龙头': ['002230', '300474', '002415'],  # 科大讯飞、景嘉微、海康威视
            '成分': ['002230', '300474', '002415', '300496', '300624', '002049', 
                    '300044', '002362', '300212', '688777', '300418', '300253']
        },
        '机器人': {
            '龙头': ['002747', '300024', '300607'],  # 埃斯顿、机器人、拓斯达
            '成分': ['002747', '300024', '300607', '002527', '300124', '002270',
                    '300367', '688165', '002472', '300730', '603633', '002689']
        },
        '半导体': {
            '龙头': ['002371', '603501', '688981'],  # 北方华创、韦尔股份、中芯国际
            '成分': ['002371', '603501', '688981', '002049', '300661', '688012',
                    '603160', '002185', '300782', '688396', '603986', '002156']
        },
        '消费电子': {
            '龙头': ['002475', '002241', '603160'],  # 立讯精密、歌尔股份、汇顶科技
            '成分': ['002475', '002241', '603160', '601138', '002036', '002456',
                    '002600', '300115', '002236', '300671', '603501', '002384']
        },
        '光伏': {
            '龙头': ['601012', '002459', '600438'],  # 隆基绿能、晶澳科技、通威股份
            '成分': ['601012', '002459', '600438', '688599', '300274', '002129',
                    '603806', '300763', '601865', '300724', '002506', '603185']
        },
        '新能源车': {
            '龙头': ['002594', '300750', '002466'],  # 比亚迪、宁德时代、天齐锂业
            '成分': ['002594', '300750', '002466', '002074', '300014', '300207',
                    '002340', '300450', '600884', '300457', '002709', '300073']
        },
    }
    return sector_stocks


# ==================== 板块异动策略 ====================
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


def check_sector_signal(daily_returns):
    """
    检测板块异动信号（优化版参数）
    条件：
    1. 60-150天前有过爆发（单日>5%）
    2. 爆发后回撤12-25%
    3. 近30日整体弱势（<5%）
    4. 近10日企稳（>-3%）
    5. 近5日止跌（>-2%）
    """
    if daily_returns is None or len(daily_returns) < 90:
        return False, None, "数据不足"
    
    daily_returns = daily_returns.dropna()
    if len(daily_returns) < 90:
        return False, None, "有效数据不足"
    
    # 时间分段：60-150天前的数据
    old_period = daily_returns.iloc[:-60]
    recent_30d = daily_returns.iloc[-30:]
    recent_10d = daily_returns.iloc[-10:]
    recent_5d = daily_returns.iloc[-5:]
    
    if len(old_period) < 30:
        return False, None, "历史数据不足"
    
    # 条件1：找爆发
    surge_days = old_period[old_period > 5.0]
    if len(surge_days) == 0:
        return False, None, "无早期爆发(>5%)"
    
    max_surge_value = surge_days.max()
    max_surge_idx = surge_days.idxmax()
    
    # 条件2：计算回撤
    after_surge = daily_returns[daily_returns.index >= max_surge_idx]
    if len(after_surge) < 30:
        return False, None, "爆发后数据不足"
    
    cumsum = after_surge.cumsum()
    max_gain = cumsum.max()
    current_gain = cumsum.iloc[-1]
    drawdown = max_gain - current_gain
    
    if drawdown < 12:
        return False, None, f"回撤不足({drawdown:.1f}%<12%)"
    if drawdown > 25:
        return False, None, f"回撤过大({drawdown:.1f}%>25%)"
    
    # 条件3-5：近期走势
    recent_30d_sum = recent_30d.sum()
    if recent_30d_sum > 5:
        return False, None, f"近30日涨太多({recent_30d_sum:.1f}%)"
    
    recent_10d_sum = recent_10d.sum()
    if recent_10d_sum < -3:
        return False, None, f"近10日仍在下跌({recent_10d_sum:.1f}%)"
    
    recent_5d_sum = recent_5d.sum()
    if recent_5d_sum < -2:
        return False, None, f"近5日仍在下跌({recent_5d_sum:.1f}%)"
    
    days_since = (daily_returns.index[-1] - max_surge_idx).days
    
    return True, {
        'surge_date': max_surge_idx.strftime('%Y-%m-%d'),
        'surge_value': round(max_surge_value, 2),
        'drawdown': round(drawdown, 2),
        'days_since': days_since,
        'recent_30d': round(recent_30d_sum, 2),
        'recent_10d': round(recent_10d_sum, 2),
        'recent_5d': round(recent_5d_sum, 2),
    }, "符合条件"


# ==================== 横盘托单策略 ====================
def check_sideways_support(df):
    """
    横盘托单策略
    条件：
    1. 近3天横盘（波动<5%）
    2. 今日最低接近支撑位（-3%~+0.5%）
    3. 收盘守住支撑位
    """
    if df is None or len(df) < 10:
        return False, None
    
    idx = len(df) - 1
    sideways_period = df.iloc[idx-3:idx]
    
    high = sideways_period['最高'].max()
    low = sideways_period['最低'].min()
    avg = sideways_period['收盘'].mean()
    
    volatility = (high - low) / avg * 100
    if volatility > 5.0:
        return False, None
    
    support = low
    today = df.iloc[idx]
    distance = (today['最低'] - support) / support * 100
    
    if not (-3.0 <= distance <= 0.5):
        return False, None
    
    if today['最低'] < support * 0.98:
        return False, None
    if today['收盘'] <= support * 1.001:
        return False, None
    
    today_change = (today['收盘'] - today['开盘']) / today['开盘'] * 100
    
    return True, {
        '支撑位': round(support, 2),
        '波动': f"{volatility:.1f}%",
        '距支撑': f"{distance:+.1f}%",
        '今日涨幅': f"{today_change:+.2f}%",
        '现价': round(today['收盘'], 2),
    }


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


# ==================== 组合扫描 ====================
def run_combo_scan():
    log("="*70)
    log("板块异动 + 横盘托单 组合策略")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*70)
    
    log("\n【策略逻辑】")
    log("  1. 先用板块异动策略选出潜力板块")
    log("  2. 再在这些板块中用横盘托单策略选个股")
    log("  3. 双重共振，提高胜率")
    
    log("\n【板块异动条件】")
    log("  - 60-150天前有爆发(>5%)")
    log("  - 回撤12-25%")
    log("  - 近期企稳")
    
    log("\n【横盘托单条件】")
    log("  - 近3天横盘（波动<5%）")
    log("  - 触及支撑位")
    log("  - 收盘守住支撑")
    
    # 获取板块数据
    log("\n" + "="*70)
    log("[1] 扫描潜力板块")
    log("="*70)
    
    sector_stocks = get_sector_stocks()
    potential_sectors = []
    
    for sector, data in sector_stocks.items():
        log(f"\n  分析: {sector}")
        
        trend = estimate_sector_trend(data['龙头'])
        if trend is None:
            log(f"    -> 无法获取数据")
            continue
        
        log(f"    数据: {len(trend)}天")
        
        is_signal, details, reason = check_sector_signal(trend)
        
        if is_signal:
            log(f"    -> ✓ 符合条件!")
            log(f"       爆发: {details['surge_date']} +{details['surge_value']}%")
            log(f"       回撤: {details['drawdown']}%, 距今{details['days_since']}天")
            log(f"       近5日: {details['recent_5d']:+.1f}%")
            potential_sectors.append({
                '板块': sector,
                '成分股': data['成分'],
                **details
            })
        else:
            log(f"    -> ✗ {reason}")
    
    if not potential_sectors:
        log("\n当前无符合条件的潜力板块")
        log("建议等待板块回调企稳后再扫描")
        return
    
    log(f"\n发现 {len(potential_sectors)} 个潜力板块: {[s['板块'] for s in potential_sectors]}")
    
    # 在潜力板块中扫描个股
    log("\n" + "="*70)
    log("[2] 在潜力板块中扫描横盘托单个股")
    log("="*70)
    
    all_results = []
    
    for sector_info in potential_sectors:
        sector = sector_info['板块']
        stocks = sector_info['成分股']
        
        log(f"\n  扫描 {sector} ({len(stocks)}只股票)...")
        
        sector_results = []
        
        for code in stocks:
            df = get_stock_kline(code, days=30)
            if df is None:
                continue
            
            is_signal, stock_info = check_sideways_support(df)
            
            if is_signal:
                name = get_stock_name(code)
                sector_results.append({
                    '代码': code,
                    '名称': name,
                    '所属板块': sector,
                    '板块爆发日': sector_info['surge_date'],
                    '板块回撤': f"{sector_info['drawdown']}%",
                    '板块近5日': f"{sector_info['recent_5d']:+.1f}%",
                    **stock_info
                })
        
        if sector_results:
            log(f"    发现 {len(sector_results)} 只横盘托单信号")
            for r in sector_results:
                log(f"      {r['名称']}({r['代码']}) {r['今日涨幅']} 支撑{r['支撑位']}")
            all_results.extend(sector_results)
        else:
            log(f"    暂无横盘托单信号")
    
    # 显示最终结果
    log("\n" + "="*70)
    log("扫描结果")
    log("="*70)
    
    if all_results:
        log(f"\n【双重共振信号】({len(all_results)}只)")
        log("-" * 60)
        
        for r in all_results:
            log(f"\n  {r['名称']}({r['代码']})")
            log(f"    板块: {r['所属板块']}")
            log(f"    板块爆发: {r['板块爆发日']}, 回撤{r['板块回撤']}")
            log(f"    个股: 现价{r['现价']}, 支撑{r['支撑位']}, {r['距支撑']}")
            log(f"    今日: {r['今日涨幅']}, 波动{r['波动']}")
        
        log("\n" + "-" * 60)
        log("【操作建议】")
        log("  1. 优先选择今日涨幅小的（空间大）")
        log("  2. 买入价参考支撑位")
        log("  3. 止损：跌破支撑位-3%")
        log("  4. 持有周期：30-60天（板块策略特点）")
        
        # 保存结果
        fname = f"板块托单组合_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        df_results = pd.DataFrame(all_results)
        
        # 同时保存板块信息
        df_sectors = pd.DataFrame(potential_sectors)
        df_sectors = df_sectors.drop('成分股', axis=1)
        
        with pd.ExcelWriter(fname, engine='openpyxl') as writer:
            df_sectors.to_excel(writer, sheet_name='潜力板块', index=False)
            df_results.to_excel(writer, sheet_name='双重共振个股', index=False)
        
        log(f"\n已保存: {fname}")
    else:
        log("\n当前无双重共振信号")
        log("\n可能原因：")
        log("  1. 潜力板块的成分股尚未形成横盘托单形态")
        log("  2. 需要等待更多个股回调到支撑位")
        
        # 仍然保存板块信息
        fname = f"潜力板块_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        df_sectors = pd.DataFrame(potential_sectors)
        df_sectors = df_sectors.drop('成分股', axis=1)
        df_sectors.to_excel(fname, index=False)
        log(f"\n已保存潜力板块: {fname}")
    
    log("\n" + "="*70)


if __name__ == "__main__":
    run_combo_scan()
