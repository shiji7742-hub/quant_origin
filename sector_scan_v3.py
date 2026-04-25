"""
板块异动扫描 V3 - 正确逻辑：
几个月前爆发 → 长时间回调整理 → 近期企稳等待起爆
"""
import requests
import pandas as pd
import json
import os
from datetime import datetime

def log(msg):
    print(msg, flush=True)

# 清除代理
for key in list(os.environ.keys()):
    if 'proxy' in key.lower():
        del os.environ[key]

session = requests.Session()
session.trust_env = False
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://quote.eastmoney.com/'
})


def get_stock_kline(code, days=180):
    """获取个股K线 - 需要更长的历史"""
    code = str(code).zfill(6)
    if code.startswith('6'):
        kcode = f'sh{code}'
    else:
        kcode = f'sz{code}'
    
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
        if len(days_data) < 60:
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


def get_industry_stocks():
    """获取行业龙头股 - 用于估算板块走势"""
    industry_leaders = {
        '人工智能': ['002230', '300474', '002415'],
        '机器人': ['002747', '300024', '300607'],
        '芯片': ['002371', '603501', '688981'],
        '新能源车': ['002594', '300750', '002466'],
        '光伏': ['601012', '002459', '600438'],
        '医药': ['600276', '000538', '300760'],
        '白酒': ['600519', '000858', '000568'],
        '银行': ['601398', '601939', '600036'],
        '军工': ['600893', '000768', '600760'],
        '消费电子': ['002475', '002241', '603160'],
        '半导体设备': ['002371', '688012', '300661'],
        '储能': ['002074', '300014', '300724'],
        '传媒': ['002027', '300413', '002602'],
        '游戏': ['002555', '002624', '002174'],
        '建材': ['600585', '000401', '002271'],
        '有色金属': ['601899', '000630', '002460'],
        '煤炭': ['601088', '601898', '600188'],
        '房地产': ['001979', '600048', '000002'],
        '证券': ['600030', '601211', '600837'],
        '保险': ['601318', '601628', '601601'],
    }
    return industry_leaders


def estimate_sector_trend(stocks):
    """用成分股估算板块走势"""
    all_data = []
    for code in stocks:
        df = get_stock_kline(code, days=180)
        if df is not None and len(df) > 60:
            all_data.append(df[['日期', '涨跌幅']].set_index('日期')['涨跌幅'])
    
    if len(all_data) == 0:
        return None
    
    combined = pd.concat(all_data, axis=1)
    return combined.mean(axis=1)


def detect_sector_signal_v3(daily_returns):
    """
    检测板块异动信号 V3 - 正确逻辑
    
    条件：
    1. 2-4个月前有过爆发（单日>4%或连续3日>8%）
    2. 爆发后经历了较长时间回调（从高点回撤>8%）
    3. 近30日整体弱势（累计<8%）
    4. 近10日开始企稳（不再大跌，累计>-3%）
    5. 近5日有小幅反弹迹象（>-2%）
    """
    if daily_returns is None or len(daily_returns) < 90:
        return False, None, "数据不足(<90天)"
    
    daily_returns = daily_returns.dropna()
    if len(daily_returns) < 90:
        return False, None, "有效数据不足"
    
    # 时间分段
    # 2-4个月前的数据（约40-120天前）
    old_period = daily_returns.iloc[:-40]  # 40天前之前的数据
    
    # 近期数据
    recent_40d = daily_returns.iloc[-40:]   # 最近40天
    recent_30d = daily_returns.iloc[-30:]   # 最近30天
    recent_10d = daily_returns.iloc[-10:]   # 最近10天
    recent_5d = daily_returns.iloc[-5:]     # 最近5天
    
    if len(old_period) < 30:
        return False, None, "历史数据不足"
    
    # ===== 条件1：找2-4个月前的爆发 =====
    # 单日爆发>4%
    surge_days = old_period[old_period > 4.0]
    
    # 或者连续3日累计>8%
    rolling_3d = old_period.rolling(3).sum()
    strong_moves = rolling_3d[rolling_3d > 8.0]
    
    if len(surge_days) == 0 and len(strong_moves) == 0:
        return False, None, "无早期爆发(需>4%或3日>8%)"
    
    # 取最大爆发点
    if len(surge_days) > 0:
        max_surge_value = surge_days.max()
        max_surge_idx = surge_days.idxmax()
    else:
        max_surge_value = strong_moves.max() / 3  # 转换为日均
        max_surge_idx = strong_moves.idxmax()
    
    surge_count = len(surge_days) + len(strong_moves.dropna())
    
    # ===== 条件2：爆发后经历回调 =====
    after_surge = daily_returns[daily_returns.index >= max_surge_idx]
    
    if len(after_surge) < 30:
        return False, None, f"爆发后数据不足({len(after_surge)}天<30天)"
    
    # 计算从爆发到现在的累计涨跌
    cumsum = after_surge.cumsum()
    max_gain = cumsum.max()        # 爆发后的最高点
    current_gain = cumsum.iloc[-1]  # 当前位置
    drawdown = max_gain - current_gain  # 从高点的回撤
    
    # 要求回撤>8%
    if drawdown < 8:
        return False, None, f"回撤不足({drawdown:.1f}%<8%)"
    
    # 回撤太大也不好（超过25%可能是趋势反转）
    if drawdown > 25:
        return False, None, f"回撤过大({drawdown:.1f}%>25%)"
    
    # ===== 条件3：近30日整体弱势 =====
    recent_30d_sum = recent_30d.sum()
    if recent_30d_sum > 8:
        return False, None, f"近30日涨太多({recent_30d_sum:.1f}%>8%)"
    
    # ===== 条件4：近10日开始企稳 =====
    recent_10d_sum = recent_10d.sum()
    if recent_10d_sum < -5:
        return False, None, f"近10日仍在下跌({recent_10d_sum:.1f}%<-5%)"
    
    # ===== 条件5：近5日有企稳迹象 =====
    recent_5d_sum = recent_5d.sum()
    if recent_5d_sum < -3:
        return False, None, f"近5日仍在下跌({recent_5d_sum:.1f}%<-3%)"
    
    # 计算爆发距今多少天
    days_since_surge = (daily_returns.index[-1] - max_surge_idx).days
    
    return True, {
        'surge_date': max_surge_idx.strftime('%Y-%m-%d'),
        'surge_value': round(max_surge_value, 2),
        'surge_count': surge_count,
        'days_since_surge': days_since_surge,
        'drawdown': round(drawdown, 2),
        'recent_30d': round(recent_30d_sum, 2),
        'recent_10d': round(recent_10d_sum, 2),
        'recent_5d': round(recent_5d_sum, 2),
    }, "符合条件"


def run_scan():
    log("="*60)
    log("板块异动扫描 V3")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*60)
    
    log("\n【策略逻辑】")
    log("  几个月前爆发 → 长时间回调 → 近期企稳 → 等待起爆")
    
    log("\n【筛选条件】")
    log("  1. 2-4个月前有过爆发（单日>4%或3日>8%）")
    log("  2. 爆发后从高点回撤 8-25%")
    log("  3. 近30日整体弱势（累计<8%）")
    log("  4. 近10日企稳（>-5%）")
    log("  5. 近5日止跌（>-3%）")
    
    log("\n[1] 获取行业数据...")
    industry_leaders = get_industry_stocks()
    log(f"  共 {len(industry_leaders)} 个行业")
    
    log("\n[2] 分析各行业...")
    
    results = []
    for industry, stocks in industry_leaders.items():
        log(f"\n  {industry}:")
        
        trend = estimate_sector_trend(stocks)
        if trend is None:
            log(f"    -> 无法获取数据")
            continue
        
        log(f"    数据: {len(trend)}天")
        
        is_signal, details, reason = detect_sector_signal_v3(trend)
        
        if is_signal:
            log(f"    -> ✓ 符合条件!")
            log(f"       爆发日: {details['surge_date']} (+{details['surge_value']}%)")
            log(f"       距今: {details['days_since_surge']}天")
            log(f"       回撤: {details['drawdown']}%")
            log(f"       近5日: {details['recent_5d']:+.1f}%")
            results.append({
                '板块': industry,
                '龙头股': stocks,
                **details
            })
        else:
            log(f"    -> ✗ {reason}")
    
    # 结果
    log("\n" + "="*60)
    log("扫描结果")
    log("="*60)
    
    if results:
        # 按回撤排序（回撤越大，洗盘越充分）
        results = sorted(results, key=lambda x: x['drawdown'], reverse=True)
        
        log(f"\n发现 {len(results)} 个潜力板块:")
        log("-" * 50)
        
        for r in results:
            log(f"\n  【{r['板块']}】")
            log(f"    爆发日期: {r['surge_date']} (+{r['surge_value']}%)")
            log(f"    距今天数: {r['days_since_surge']}天 (约{r['days_since_surge']//30}个月)")
            log(f"    回撤幅度: {r['drawdown']}%（洗盘程度）")
            log(f"    近30日: {r['recent_30d']:+.1f}%")
            log(f"    近10日: {r['recent_10d']:+.1f}%（企稳）")
            log(f"    近5日: {r['recent_5d']:+.1f}%")
            log(f"    龙头股: {', '.join(r['龙头股'])}")
        
        log("\n" + "-" * 50)
        log("【操作建议】")
        log("  1. 回撤越大（>15%），洗盘越充分，启动空间越大")
        log("  2. 近5日止跌企稳是关键，可以开始关注")
        log("  3. 等待放量突破确认再介入")
        log("  4. 结合大盘环境判断")
    else:
        log("\n当前无符合条件的板块")
        log("\n可能原因：")
        log("  1. 大多数板块没有经历足够的回调")
        log("  2. 近期市场整体走强，没有企稳信号")
        log("  3. 需要等待更多板块进入回调整理阶段")
    
    log("\n" + "="*60)
    
    return results


if __name__ == "__main__":
    run_scan()
