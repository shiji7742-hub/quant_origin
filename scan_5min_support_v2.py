"""
分时托单策略扫描（优化版）
根据回测高胜率条件筛选

【高胜率条件】
1. 量比 > 1.2（上涨量/下跌量）← 最关键
2. 人工智能/半导体板块优先
3. 收盘位置 > 80%
4. 今日涨跌幅 0-2%（小涨）
5. 托单次数 >= 5次
"""
import requests
import pandas as pd
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


def check_intraday_support_v2(df_5min, date_str):
    """
    检测分时托单信号（高胜率版）
    
    核心条件：
    1. 量比 > 1.2（上涨量/下跌量）← 最关键
    2. 收盘位置 > 80%
    3. 托单次数 >= 5次
    4. 今日涨跌幅 0-2%
    5. 分时波动 < 5%
    """
    day_bars = df_5min[df_5min['date'] == date_str].copy()
    if len(day_bars) < 20:
        return False, None, "K线不足"
    
    high = day_bars['最高'].max()
    low = day_bars['最低'].min()
    avg_price = day_bars['收盘'].mean()
    current = day_bars.iloc[-1]['收盘']
    open_price = day_bars.iloc[0]['开盘']
    
    # 条件1：分时波动 < 5%（横盘）
    volatility = (high - low) / avg_price * 100
    if volatility > 5.0:
        return False, None, f"波动太大({volatility:.1f}%)"
    
    # 分析下影线（托单特征）
    day_bars['下影线'] = day_bars.apply(
        lambda x: min(x['开盘'], x['收盘']) - x['最低'], axis=1)
    day_bars['实体'] = abs(day_bars['收盘'] - day_bars['开盘'])
    
    # 托单K线：下影线 > 实体的50%
    support_bars = day_bars[day_bars['下影线'] > day_bars['实体'] * 0.5]
    support_count = len(support_bars)
    
    # 条件2：托单次数 >= 5次
    if support_count < 5:
        return False, None, f"托单次数不足({support_count}次)"
    
    # 量能分析
    day_bars['涨跌'] = day_bars['收盘'] - day_bars['开盘']
    down_bars = day_bars[day_bars['涨跌'] < 0]
    up_bars = day_bars[day_bars['涨跌'] > 0]
    
    if len(down_bars) < 3 or len(up_bars) < 3:
        return False, None, "涨跌K线分布异常"
    
    avg_down_vol = down_bars['成交量'].mean()
    avg_up_vol = up_bars['成交量'].mean()
    vol_ratio = avg_up_vol / avg_down_vol if avg_down_vol > 0 else 1
    
    # 条件3：量比 > 1.2（最关键！）
    if vol_ratio < 1.2:
        return False, None, f"量比不足({vol_ratio:.2f})"
    
    # 条件4：收盘位置 > 80%（守住高位）
    position = (current - low) / (high - low) * 100 if high > low else 50
    if position < 80:
        return False, None, f"收盘位置低({position:.0f}%)"
    
    # 条件5：今日涨跌幅 0-2%（小涨，不追高）
    today_change = (current - open_price) / open_price * 100
    if today_change < -0.5 or today_change > 3:
        return False, None, f"涨跌幅不合适({today_change:+.1f}%)"
    
    # 尾盘走势（最后4根5分钟K线）
    last_4 = day_bars.iloc[-4:]
    tail_trend = (last_4.iloc[-1]['收盘'] - last_4.iloc[0]['开盘']) / last_4.iloc[0]['开盘'] * 100
    
    # 计算信号质量分数
    score = 0
    score += min(30, (vol_ratio - 1.0) * 50)  # 量比加分
    score += min(20, (position - 50) / 2)      # 位置加分
    score += min(20, support_count)            # 托单次数加分
    if tail_trend > 0:
        score += 10                            # 尾盘上涨加分
    if 0 <= today_change <= 2:
        score += 20                            # 今日小涨加分
    
    return True, {
        'volatility': volatility,
        'support_count': support_count,
        'vol_ratio': vol_ratio,
        'position': position,
        'today_change': today_change,
        'tail_trend': tail_trend,
        'score': score,
        'close': current,
        'low': low,
        'high': high,
    }, None


def get_sector_stocks():
    """获取板块成分股（按胜率排序）"""
    return {
        # 高胜率板块（优先扫描）
        '人工智能': ['002230', '300474', '002415', '300496', '300624', '002049', 
                   '300229', '002555', '300044', '688787'],
        '半导体': ['002371', '603501', '300661', '688012', '603160', '688981',
                 '688008', '688036', '002185', '300458'],
        '机器人': ['002747', '300024', '300607', '002527', '300124', '002270',
                 '688165', '300367', '603728', '300276'],
        
        # 中等胜率板块
        '消费电子': ['002475', '002241', '601138', '002036', '002456'],
        
        # 低胜率板块（可选择不扫描）
        # '光伏': ['601012', '002459', '600438', '300274', '002129'],
        # '新能源车': ['002594', '300750', '002466', '002074', '300014'],
    }


def run_scan():
    log("="*70)
    log("分时托单扫描（高胜率优化版）")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*70)
    
    log("\n【高胜率筛选条件】")
    log("  1. 量比 > 1.2（上涨量/下跌量）← 最关键")
    log("  2. 收盘位置 > 80%")
    log("  3. 托单次数 >= 5次")
    log("  4. 今日涨跌幅 -0.5%~+3%")
    log("  5. 分时波动 < 5%")
    log("  6. 优先扫描：人工智能/半导体/机器人")
    
    sector_stocks = get_sector_stocks()
    
    signals = []
    filtered_reasons = {}
    
    for sector, stocks in sector_stocks.items():
        log(f"\n[{sector}] 扫描 {len(stocks)} 只...")
        
        for code in stocks:
            df_5min = get_5min_kline(code)
            if df_5min is None:
                continue
            
            # 获取最近的交易日
            latest_date = df_5min['date'].max()
            
            is_signal, info, reason = check_intraday_support_v2(df_5min, latest_date)
            
            if is_signal:
                name = get_stock_name(code)
                signals.append({
                    'code': code,
                    'name': name,
                    'sector': sector,
                    'date': latest_date,
                    **info
                })
                log(f"  ★ {code} {name}")
                log(f"    量比{info['vol_ratio']:.2f}, 位置{info['position']:.0f}%, 托单{info['support_count']}次, 评分{info['score']:.0f}")
            else:
                if reason not in filtered_reasons:
                    filtered_reasons[reason] = 0
                filtered_reasons[reason] += 1
    
    # 结果汇总
    log("\n" + "="*70)
    log("扫描结果")
    log("="*70)
    
    if not signals:
        log("\n今日无符合条件的信号")
        
        log("\n【过滤原因统计】")
        for reason, count in sorted(filtered_reasons.items(), key=lambda x: -x[1]):
            log(f"  {reason}: {count}只")
    else:
        df = pd.DataFrame(signals)
        df = df.sort_values('score', ascending=False)
        
        log(f"\n发现 {len(df)} 个高胜率信号:")
        log("-" * 70)
        
        for i, (_, row) in enumerate(df.iterrows(), 1):
            sector_tag = ""
            if row['sector'] in ['人工智能', '半导体']:
                sector_tag = "★★★"
            elif row['sector'] == '机器人':
                sector_tag = "★★"
            else:
                sector_tag = "★"
            
            log(f"\n{i}. {row['code']} {row['name']} ({row['sector']}) {sector_tag}")
            log(f"   量比: {row['vol_ratio']:.2f} (上涨量/下跌量)")
            log(f"   位置: {row['position']:.0f}% (收盘在分时高位)")
            log(f"   托单: {row['support_count']}次 (下探收回)")
            log(f"   今涨: {row['today_change']:+.1f}%")
            log(f"   尾盘: {row['tail_trend']:+.2f}%")
            log(f"   评分: {row['score']:.0f}分")
        
        # 操作建议
        log("\n" + "="*70)
        log("操作建议")
        log("="*70)
        
        best = df.iloc[0]
        log(f"""
【今日最佳】
  {best['code']} {best['name']} ({best['sector']})
  评分: {best['score']:.0f}分
  
【买入策略】
  - 次日开盘竞价买入
  - 或开盘后观察5分钟，确认没有大幅低开再买

【止损设置】
  - 跌破分时最低点 {best['low']:.2f} 再-1%止损
  - 即止损价约 {best['low'] * 0.99:.2f}

【止盈设置】
  - 第一目标：+3%
  - 第二目标：+5%
  - 持有期：1-3天

【注意事项】
  - 大盘大跌时暂不操作
  - 开盘低开>2%放弃
""")
        
        # 保存
        fname = f"分时托单信号_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        df.to_excel(fname, index=False)
        log(f"\n已保存: {fname}")


if __name__ == "__main__":
    run_scan()
