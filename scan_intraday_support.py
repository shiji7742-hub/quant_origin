"""
分时托单策略 - 正确版本
核心逻辑：
1. 分时图上横盘整理（波动小）
2. 小单连续往下砸
3. 大单一下子吃进收回（托单护盘）

数据来源：腾讯分时K线
"""
import requests
import pandas as pd
import numpy as np
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


def get_minute_kline(code, period='m5'):
    """
    获取分钟K线
    period: m1, m5, m15, m30, m60
    """
    code = str(code).zfill(6)
    kcode = f'sh{code}' if code.startswith('6') else f'sz{code}'
    
    # 腾讯分钟K线接口
    url = f'https://web.ifzq.gtimg.cn/appstock/app/minute/query?code={kcode}'
    try:
        r = session.get(url, timeout=10)
        data = r.json()
        
        if 'data' not in data or kcode not in data['data']:
            return None
        
        minute_data = data['data'][kcode]['data']['data']
        if not minute_data:
            return None
        
        # 解析分时数据: "0930 10.5 100" -> 时间 价格 成交量
        records = []
        for item in minute_data:
            parts = item.split(' ')
            if len(parts) >= 3:
                time_str = parts[0]
                price = float(parts[1])
                volume = float(parts[2])
                records.append({
                    '时间': time_str,
                    '价格': price,
                    '成交量': volume,
                })
        
        if not records:
            return None
        
        df = pd.DataFrame(records)
        df['成交额'] = df['价格'] * df['成交量']
        
        return df
    except Exception as e:
        return None


def get_5min_kline(code):
    """获取5分钟K线"""
    code = str(code).zfill(6)
    kcode = f'sh{code}' if code.startswith('6') else f'sz{code}'
    
    # 5分钟K线
    url = f'https://web.ifzq.gtimg.cn/appstock/app/kline/mkline?param={kcode},m5,,320'
    try:
        r = session.get(url, timeout=10)
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
    except Exception as e:
        return None


def get_stock_kline(code, days=30):
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
        if len(days_data) < 5:
            return None
        df = pd.DataFrame([d[:6] for d in days_data], 
                        columns=['日期','开盘','收盘','最高','最低','成交量'])
        for col in ['开盘','收盘','最高','最低','成交量']:
            df[col] = df[col].astype(float)
        return df
    except:
        return None


def check_intraday_support(df_5min, df_daily):
    """
    检测分时托单信号
    
    条件：
    1. 今日分时横盘（5分钟K线波动小）
    2. 多次下探后收回（下影线多）
    3. 下跌时量小，反弹时量大（大单托）
    """
    if df_5min is None or len(df_5min) < 20:
        return False, None, "5分钟数据不足"
    
    if df_daily is None or len(df_daily) < 5:
        return False, None, "日K数据不足"
    
    # 取今日的5分钟K线（最后48根，一天约48个5分钟）
    today_bars = df_5min.tail(48)
    if len(today_bars) < 10:
        return False, None, "今日数据不足"
    
    # 计算今日高低点
    high = today_bars['最高'].max()
    low = today_bars['最低'].min()
    avg_price = today_bars['收盘'].mean()
    current = today_bars.iloc[-1]['收盘']
    
    # 条件1：分时横盘（波动幅度小）
    volatility = (high - low) / avg_price * 100
    if volatility > 3.0:  # 波动超过3%不算横盘
        return False, None, f"分时波动过大({volatility:.1f}%>3%)"
    
    # 条件2：多次下探后收回（分析下影线）
    # 下影线 = 收盘 - 最低
    # 上影线 = 最高 - 收盘
    today_bars = today_bars.copy()
    today_bars['下影线'] = today_bars['收盘'] - today_bars['最低']
    today_bars['上影线'] = today_bars['最高'] - today_bars['收盘']
    today_bars['实体'] = abs(today_bars['收盘'] - today_bars['开盘'])
    
    # 统计下影线明显的K线（下影线 > 实体）
    support_bars = today_bars[today_bars['下影线'] > today_bars['实体'] * 0.5]
    support_count = len(support_bars)
    
    if support_count < 3:
        return False, None, f"托单次数不足({support_count}<3次)"
    
    # 条件3：下跌量小，反弹量大
    # 分析每次下探的量能特征
    today_bars['涨跌'] = today_bars['收盘'] - today_bars['开盘']
    
    # 下跌K线的平均成交量
    down_bars = today_bars[today_bars['涨跌'] < 0]
    up_bars = today_bars[today_bars['涨跌'] > 0]
    
    if len(down_bars) < 3 or len(up_bars) < 3:
        return False, None, "涨跌K线数量不足"
    
    avg_down_vol = down_bars['成交量'].mean()
    avg_up_vol = up_bars['成交量'].mean()
    
    # 上涨量应该 >= 下跌量（大单托）
    vol_ratio = avg_up_vol / avg_down_vol if avg_down_vol > 0 else 1
    
    if vol_ratio < 0.8:
        return False, None, f"反弹量不足(量比{vol_ratio:.2f}<0.8)"
    
    # 条件4：收盘价接近分时高点（守住了）
    position = (current - low) / (high - low) * 100 if high > low else 50
    if position < 50:
        return False, None, f"收盘位置偏低({position:.0f}%<50%)"
    
    # 条件5：结合日K，今日不能大跌
    today_daily = df_daily.iloc[-1]
    yesterday_close = df_daily.iloc[-2]['收盘']
    today_change = (today_daily['收盘'] - yesterday_close) / yesterday_close * 100
    
    if today_change < -2:
        return False, None, f"今日跌幅过大({today_change:.1f}%)"
    
    # 额外：检查是否有"大单托"的特征
    # 统计下影线K线的成交量，如果比平均高说明有大单接盘
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
    }, "符合托单特征"


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
    """获取科技板块成分股"""
    return {
        '人工智能': ['002230', '300474', '002415', '300496', '300624', '002049'],
        '机器人': ['002747', '300024', '300607', '002527', '300124', '002270'],
        '半导体': ['002371', '603501', '688981', '300661', '688012', '603160'],
        '消费电子': ['002475', '002241', '603160', '601138', '002036', '002456'],
        '光伏': ['601012', '002459', '600438', '688599', '300274', '002129'],
        '新能源车': ['002594', '300750', '002466', '002074', '300014', '300207'],
    }


def run_scan():
    log("="*70)
    log("分时托单策略扫描")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*70)
    
    log("\n【策略逻辑】")
    log("  1. 分时图横盘整理（5分钟波动<3%）")
    log("  2. 多次下探后收回（下影线多，托单>=3次）")
    log("  3. 下跌量小，反弹量大（大单托住）")
    log("  4. 收盘在分时高点附近（守住了）")
    
    log("\n【核心特征】")
    log("  - 小单连续往下砸")
    log("  - 大单一下子吃进收回")
    log("  - 说明有资金在护盘/吸筹")
    
    sector_stocks = get_sector_stocks()
    all_stocks = []
    for stocks in sector_stocks.values():
        all_stocks.extend(stocks)
    all_stocks = list(set(all_stocks))
    
    log(f"\n扫描 {len(all_stocks)} 只股票...")
    log("-" * 50)
    
    results = []
    
    for code in all_stocks:
        # 获取5分钟K线
        df_5min = get_5min_kline(code)
        df_daily = get_stock_kline(code, days=10)
        
        if df_5min is None:
            continue
        
        is_signal, info, reason = check_intraday_support(df_5min, df_daily)
        
        if is_signal:
            name = get_stock_name(code)
            sector = next((s for s, stocks in sector_stocks.items() if code in stocks), '未知')
            
            log(f"\n  ✓ {name}({code}) [{sector}]")
            log(f"    波动{info['分时波动']}, 托单{info['托单次数']}次, 量比{info['量比']}")
            log(f"    位置{info['收盘位置']}, 今日{info['今日涨幅']}")
            log(f"    分时区间: {info['分时低点']} - {info['分时高点']}")
            
            results.append({
                '代码': code,
                '名称': name,
                '板块': sector,
                **info
            })
    
    log("\n" + "="*70)
    log("扫描结果")
    log("="*70)
    
    if results:
        log(f"\n【分时托单信号】({len(results)}只)")
        
        for r in results:
            log(f"\n  {r['名称']}({r['代码']}) - {r['板块']}")
            log(f"    分时波动: {r['分时波动']}")
            log(f"    托单次数: {r['托单次数']}次")
            log(f"    量比: {r['量比']}（反弹量/下跌量）")
            log(f"    大单托比: {r['大单托比']}")
            log(f"    收盘位置: {r['收盘位置']}")
            log(f"    今日涨幅: {r['今日涨幅']}")
            log(f"    买入参考: {r['分时低点']}附近")
        
        log("\n" + "-" * 50)
        log("【操作建议】")
        log("  1. 在分时低点附近挂单买入")
        log("  2. 止损：跌破分时低点-1%")
        log("  3. 目标：分时高点或更高")
        log("  4. 注意：盘中观察是否继续有大单托")
        
        fname = f"分时托单_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        pd.DataFrame(results).to_excel(fname, index=False)
        log(f"\n已保存: {fname}")
    else:
        log("\n当前无分时托单信号")
        log("\n可能原因：")
        log("  1. 今日波动较大，未形成横盘")
        log("  2. 托单特征不明显")
        log("  3. 建议盘中多时间点扫描")


if __name__ == "__main__":
    run_scan()
