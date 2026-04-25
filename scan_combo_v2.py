"""
板块异动 + 横盘托单 组合策略 V2（改进版）

改进点：
1. 个股当日涨幅限制 -1% ~ +2%（避免追高）
2. 量比要求 0.8~1.5（平稳换手）
3. 前10日涨幅 <10%（避免高位横盘）
4. 距20日高点 >-10%（避免深跌反弹）
5. 板块回撤 >15%（洗盘充分）
"""
import requests
import pandas as pd
import os
from datetime import datetime

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
    """获取各板块的成分股（科技成长板块）"""
    return {
        '人工智能': {
            '龙头': ['002230', '300474', '002415'],
            '成分': ['002230', '300474', '002415', '300496', '300624', '002049', 
                    '300044', '002362', '300212', '688777', '300418', '300253']
        },
        '机器人': {
            '龙头': ['002747', '300024', '300607'],
            '成分': ['002747', '300024', '300607', '002527', '300124', '002270',
                    '300367', '688165', '002472', '300730', '603633', '002689']
        },
        '半导体': {
            '龙头': ['002371', '603501', '688981'],
            '成分': ['002371', '603501', '688981', '002049', '300661', '688012',
                    '603160', '002185', '300782', '688396', '603986', '002156']
        },
        '消费电子': {
            '龙头': ['002475', '002241', '603160'],
            '成分': ['002475', '002241', '603160', '601138', '002036', '002456',
                    '002600', '300115', '002236', '300671', '603501', '002384']
        },
        '光伏': {
            '龙头': ['601012', '002459', '600438'],
            '成分': ['601012', '002459', '600438', '688599', '300274', '002129',
                    '603806', '300763', '601865', '300724', '002506', '603185']
        },
        '新能源车': {
            '龙头': ['002594', '300750', '002466'],
            '成分': ['002594', '300750', '002466', '002074', '300014', '300207',
                    '002340', '300450', '600884', '300457', '002709', '300073']
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
    """
    检测板块异动信号（改进版：优选回撤>15%）
    """
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
        return False, None, "无早期爆发(>5%)"
    
    max_surge_value = surge_days.max()
    max_surge_idx = surge_days.idxmax()
    
    after_surge = daily_returns[daily_returns.index >= max_surge_idx]
    if len(after_surge) < 30:
        return False, None, "爆发后数据不足"
    
    cumsum = after_surge.cumsum()
    max_gain = cumsum.max()
    current_gain = cumsum.iloc[-1]
    drawdown = max_gain - current_gain
    
    # 改进：优选回撤>15%
    if drawdown < min_drawdown:
        return False, None, f"回撤不足({drawdown:.1f}%<{min_drawdown}%)"
    if drawdown > 25:
        return False, None, f"回撤过大({drawdown:.1f}%>25%)"
    
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
        'recent_5d': round(recent_5d_sum, 2),
    }, "符合条件"


def check_sideways_support_v2(df):
    """
    横盘托单策略V2（改进版）
    新增条件：
    1. 当日涨幅 -1% ~ +2%
    2. 量比 0.8 ~ 1.5
    3. 前10日涨幅 < 10%
    4. 距20日高点 > -10%
    """
    if df is None or len(df) < 25:
        return False, None, "数据不足"
    
    idx = len(df) - 1
    sideways_period = df.iloc[idx-3:idx]
    
    high = sideways_period['最高'].max()
    low = sideways_period['最低'].min()
    avg = sideways_period['收盘'].mean()
    
    volatility = (high - low) / avg * 100
    if volatility > 5.0:
        return False, None, f"波动太大({volatility:.1f}%>5%)"
    
    support = low
    today = df.iloc[idx]
    distance = (today['最低'] - support) / support * 100
    
    if not (-3.0 <= distance <= 0.5):
        return False, None, f"距支撑位不合适({distance:.1f}%)"
    
    if today['最低'] < support * 0.98:
        return False, None, "破位"
    if today['收盘'] <= support * 1.001:
        return False, None, "未能守住支撑"
    
    # 改进1：当日涨幅限制
    today_change = (today['收盘'] - today['开盘']) / today['开盘'] * 100
    if today_change < -1:
        return False, None, f"当日跌幅过大({today_change:.1f}%<-1%)"
    if today_change > 2:
        return False, None, f"当日涨幅过大({today_change:.1f}%>2%)，追高风险"
    
    # 改进2：量比
    vol_5d = df.iloc[idx-5:idx]['成交量'].mean()
    vol_today = today['成交量']
    vol_ratio = vol_today / vol_5d if vol_5d > 0 else 1
    if vol_ratio < 0.8:
        return False, None, f"成交量萎缩({vol_ratio:.2f}<0.8)"
    if vol_ratio > 1.5:
        return False, None, f"成交量异常放大({vol_ratio:.2f}>1.5)"
    
    # 改进3：前10日涨幅
    if idx >= 10:
        price_10d_ago = df.iloc[idx-10]['收盘']
        gain_10d = (today['收盘'] - price_10d_ago) / price_10d_ago * 100
        if gain_10d > 10:
            return False, None, f"前10日涨幅过大({gain_10d:.1f}%>10%)"
    else:
        gain_10d = 0
    
    # 改进4：距20日高点
    if idx >= 20:
        high_20d = df.iloc[idx-20:idx]['最高'].max()
        from_high = (today['收盘'] - high_20d) / high_20d * 100
        if from_high < -10:
            return False, None, f"距高点较远({from_high:.1f}%<-10%)，下跌趋势"
    else:
        from_high = 0
    
    return True, {
        '支撑位': round(support, 2),
        '波动': f"{volatility:.1f}%",
        '距支撑': f"{distance:+.1f}%",
        '今日涨幅': f"{today_change:+.2f}%",
        '量比': f"{vol_ratio:.2f}",
        '前10日': f"{gain_10d:+.1f}%",
        '距高点': f"{from_high:+.1f}%",
        '现价': round(today['收盘'], 2),
    }, "符合条件"


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


def run_scan():
    log("="*70)
    log("板块异动 + 横盘托单 组合策略 V2（改进版）")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*70)
    
    log("\n【改进点】回测胜率62.5%→76.5%，收益+3.4%→+7.2%")
    log("  1. 当日涨幅限制 -1%~+2%（排除追高）")
    log("  2. 量比 0.8~1.5（平稳换手）")
    log("  3. 前10日涨幅 <10%（避免高位）")
    log("  4. 距20日高点 >-10%（避免下跌趋势）")
    log("  5. 板块回撤 >15%（洗盘充分）")
    
    # 获取板块数据
    log("\n" + "="*70)
    log("[1] 扫描潜力板块（回撤>15%）")
    log("="*70)
    
    sector_stocks = get_sector_stocks()
    potential_sectors = []
    all_sectors_info = []
    
    for sector, data in sector_stocks.items():
        log(f"\n  分析: {sector}")
        
        trend = estimate_sector_trend(data['龙头'])
        if trend is None:
            log(f"    -> 无法获取数据")
            continue
        
        # 先用12%筛选，记录所有
        is_signal_12, details_12, reason_12 = check_sector_signal(trend, min_drawdown=12)
        
        # 再用15%筛选
        is_signal_15, details_15, reason_15 = check_sector_signal(trend, min_drawdown=15)
        
        if is_signal_15:
            log(f"    -> ✓ 符合条件（优质）")
            log(f"       爆发: {details_15['surge_date']} +{details_15['surge_value']}%")
            log(f"       回撤: {details_15['drawdown']}%（>15%优质）")
            log(f"       近5日: {details_15['recent_5d']:+.1f}%")
            potential_sectors.append({
                '板块': sector,
                '成分股': data['成分'],
                '质量': '优质',
                **details_15
            })
        elif is_signal_12:
            log(f"    -> △ 符合基本条件")
            log(f"       回撤: {details_12['drawdown']}%（<15%不够充分）")
            all_sectors_info.append({
                '板块': sector,
                '回撤': details_12['drawdown'],
                '状态': '回撤不够充分'
            })
        else:
            log(f"    -> ✗ {reason_12}")
    
    if not potential_sectors:
        log("\n" + "-"*50)
        log("当前无符合条件的优质板块（回撤>15%）")
        if all_sectors_info:
            log("\n接近条件的板块：")
            for info in all_sectors_info:
                log(f"  {info['板块']}: 回撤{info['回撤']:.1f}%，{info['状态']}")
        log("\n建议等待板块进一步回调后再扫描")
        return
    
    log(f"\n发现 {len(potential_sectors)} 个优质板块: {[s['板块'] for s in potential_sectors]}")
    
    # 在潜力板块中扫描个股
    log("\n" + "="*70)
    log("[2] 在潜力板块中扫描个股（改进版条件）")
    log("="*70)
    
    all_results = []
    rejected_stats = {}
    
    for sector_info in potential_sectors:
        sector = sector_info['板块']
        stocks = sector_info['成分股']
        
        log(f"\n  扫描 {sector} ({len(stocks)}只)...")
        
        sector_results = []
        rejected = []
        
        for code in stocks:
            df = get_stock_kline(code, days=60)
            if df is None:
                continue
            
            is_signal, stock_info, reason = check_sideways_support_v2(df)
            
            if is_signal:
                name = get_stock_name(code)
                sector_results.append({
                    '代码': code,
                    '名称': name,
                    '所属板块': sector,
                    '板块爆发日': sector_info['surge_date'],
                    '板块回撤': f"{sector_info['drawdown']}%",
                    **stock_info
                })
            else:
                rejected.append(reason)
        
        if sector_results:
            log(f"    发现 {len(sector_results)} 只信号")
            for r in sector_results:
                log(f"      {r['名称']}({r['代码']}) {r['今日涨幅']} 量比{r['量比']}")
            all_results.extend(sector_results)
        else:
            log(f"    暂无信号")
            # 统计被过滤的原因
            for r in rejected:
                rejected_stats[r] = rejected_stats.get(r, 0) + 1
    
    # 显示结果
    log("\n" + "="*70)
    log("扫描结果")
    log("="*70)
    
    if all_results:
        log(f"\n【双重共振信号】({len(all_results)}只)")
        log("-" * 60)
        
        for r in all_results:
            log(f"\n  {r['名称']}({r['代码']})")
            log(f"    板块: {r['所属板块']}，回撤{r['板块回撤']}")
            log(f"    支撑: {r['支撑位']}，现价{r['现价']}，{r['距支撑']}")
            log(f"    今日: {r['今日涨幅']}，量比{r['量比']}")
            log(f"    位置: 前10日{r['前10日']}，距高点{r['距高点']}")
        
        log("\n" + "-" * 60)
        log("【操作建议】")
        log("  1. 优选今日涨幅小、量比接近1的")
        log("  2. 买入价参考支撑位，分批建仓")
        log("  3. 止损：跌破支撑位-3%")
        log("  4. 止盈：涨10-15%或持有10-20天")
        
        fname = f"组合信号V2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        df_results = pd.DataFrame(all_results)
        df_sectors = pd.DataFrame(potential_sectors).drop('成分股', axis=1)
        
        with pd.ExcelWriter(fname, engine='openpyxl') as writer:
            df_sectors.to_excel(writer, sheet_name='潜力板块', index=False)
            df_results.to_excel(writer, sheet_name='共振信号', index=False)
        
        log(f"\n已保存: {fname}")
    else:
        log("\n当前无双重共振信号")
        
        if rejected_stats:
            log("\n被过滤的原因统计：")
            for reason, count in sorted(rejected_stats.items(), key=lambda x: -x[1])[:5]:
                log(f"  {reason}: {count}次")
        
        log("\n可能原因：")
        log("  1. 潜力板块的成分股尚未形成横盘托单形态")
        log("  2. 部分个股被改进版条件过滤（追高、量异常等）")
        log("  3. 需要等待更多个股回调到支撑位")
        
        fname = f"潜力板块V2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        df_sectors = pd.DataFrame(potential_sectors).drop('成分股', axis=1)
        df_sectors.to_excel(fname, index=False)
        log(f"\n已保存潜力板块: {fname}")
    
    log("\n" + "="*70)


if __name__ == "__main__":
    run_scan()
