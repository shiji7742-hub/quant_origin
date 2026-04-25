# -*- coding: utf-8 -*-
"""
板块异动 → 个股信号扫描
在板块异动扫描出的重点板块内，找具体个股买入信号
策略：涨停洗盘反包 + 缩量回踩 + 突破平台
"""
import requests
import os
import json
import time
import numpy as np
import pandas as pd
from datetime import datetime

# 清理代理
for key in list(os.environ.keys()):
    if 'proxy' in key.lower():
        del os.environ[key]

session = requests.Session()
session.trust_env = False
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})


def log(msg):
    try:
        print(msg, flush=True)
    except UnicodeEncodeError:
        print(msg.encode('utf-8', errors='replace').decode('utf-8'), flush=True)


# ==================== 数据获取 ====================

def get_stock_kline(code, days=120):
    """腾讯K线接口"""
    code = str(code).zfill(6)
    kcode = f'sh{code}' if code.startswith('6') else f'sz{code}'
    url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={kcode},day,,,{days},qfq'
    try:
        r = session.get(url, timeout=10)
        data = r.json()
        if not data.get('data'):
            return None
        stock_data = data['data'].get(kcode) or data['data'].get(kcode.upper())
        if not stock_data:
            return None
        days_data = stock_data.get('qfqday') or stock_data.get('day')
        if not days_data:
            return None
        df = pd.DataFrame([d[:6] for d in days_data],
                          columns=['日期', '开盘', '收盘', '最高', '最低', '成交量'])
        for col in ['开盘', '收盘', '最高', '最低', '成交量']:
            df[col] = df[col].astype(float)
        df['日期'] = pd.to_datetime(df['日期'])
        df['涨跌幅'] = df['收盘'].pct_change() * 100
        df['成交额'] = df['收盘'] * df['成交量']
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
        r.encoding = 'gbk'
        parts = r.text.split('~')
        if len(parts) > 1:
            return parts[1]
    except:
        pass
    return code


def get_sector_stocks(sector_code):
    """获取行业板块成分股（新浪）"""
    url = f'http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page=1&num=80&sort=changepercent&asc=0&node={sector_code}&symbol=&_s_r_a=page'
    try:
        r = session.get(url, timeout=10)
        r.encoding = 'gbk'
        text = r.text
        if not text or text == 'null':
            return []
        data = json.loads(text)
        stocks = []
        for item in data:
            symbol = item.get('symbol', '')
            code = symbol[2:] if len(symbol) > 2 else ''
            name = item.get('name', '')
            # 只要主板
            if code.startswith(('60', '00')):
                # 排除ST
                if 'ST' not in name and '*' not in name:
                    stocks.append({
                        'code': code,
                        'name': name,
                        'price': float(item.get('trade', 0)),
                        'change': float(item.get('changepercent', 0)),
                        'volume': float(item.get('volume', 0)),
                        'turnover': float(item.get('turnoverratio', 0)),
                        'mktcap': float(item.get('mktcap', 0)),
                    })
        return stocks
    except Exception as e:
        return []


# ==================== 个股策略检测 ====================

def check_limit_up_washout(df, code, name):
    """
    策略1: 涨停破位洗盘反包
    - 近20天内有非一字涨停
    - 后续跌破涨停最低价
    - 今天大阳反包
    """
    if df is None or len(df) < 20:
        return None

    df = df.copy().reset_index(drop=True)
    latest = df.iloc[-1]
    latest_idx = len(df) - 1

    # 今天涨幅
    today_gain = (latest['收盘'] - latest['开盘']) / latest['开盘'] * 100
    if today_gain < 2.0:  # 至少2%阳线
        return None

    # 找涨停板
    for i in range(latest_idx - 3, max(latest_idx - 25, 0), -1):
        row = df.iloc[i]
        prev_close = df.iloc[i - 1]['收盘'] if i > 0 else row['开盘']
        gain = (row['收盘'] - prev_close) / prev_close * 100

        if gain >= 9.5:
            # 非一字板
            if row['开盘'] < row['收盘'] * 0.99:
                limit_low = row['最低']
                limit_close = row['收盘']
                limit_date = row['日期']

                # 检查是否破位
                broke = False
                made_new_high = False
                for j in range(i + 1, latest_idx + 1):
                    if df.iloc[j]['最低'] <= limit_low:
                        broke = True
                    if df.iloc[j]['最高'] > limit_close * 1.05:
                        made_new_high = True

                if broke and not made_new_high:
                    # 反包条件
                    recovered = latest['收盘'] > limit_low
                    # 量能
                    vol_5d = df['成交量'].iloc[-5:].mean()
                    vol_20d = df['成交量'].iloc[-20:].mean()
                    vol_ratio = vol_5d / vol_20d if vol_20d > 0 else 1

                    if recovered and vol_ratio > 1.0:
                        days_since = latest_idx - i
                        score = 0
                        score += min(20, int(today_gain * 5))
                        if -15 <= (latest['收盘'] - limit_close) / limit_close * 100 <= 0:
                            score += 20
                        if vol_ratio > 1.5:
                            score += 15
                        elif vol_ratio > 1.2:
                            score += 10

                        return {
                            'strategy': '涨停洗盘反包',
                            'code': code,
                            'name': name,
                            'score': score,
                            'today_gain': round(today_gain, 2),
                            'limit_date': limit_date.strftime('%m-%d'),
                            'days_since': days_since,
                            'limit_low': round(limit_low, 2),
                            'current': round(latest['收盘'], 2),
                            'vol_ratio': round(vol_ratio, 2),
                            'detail': f"涨停{limit_date.strftime('%m-%d')} 最低{limit_low:.2f} 今日+{today_gain:.1f}% 量比{vol_ratio:.1f}"
                        }
                break
    return None


def check_pullback_support(df, code, name):
    """
    策略2: 缩量回踩均线支撑
    - 均线多头 (MA5>MA10>MA20)
    - 回踩MA20附近 (+-3%)
    - 缩量 (量<5日均量0.7)
    """
    if df is None or len(df) < 25:
        return None

    df = df.copy()
    df['MA5'] = df['收盘'].rolling(5).mean()
    df['MA10'] = df['收盘'].rolling(10).mean()
    df['MA20'] = df['收盘'].rolling(20).mean()

    latest = df.iloc[-1]
    if pd.isna(latest['MA20']):
        return None

    vol_ma5 = df['成交量'].iloc[-6:-1].mean()

    # 均线多头
    ma_bull = latest['MA5'] > latest['MA10'] > latest['MA20']
    if not ma_bull:
        return None

    # 回踩MA20
    dist_ma20 = abs(latest['收盘'] - latest['MA20']) / latest['MA20']
    near_ma20 = dist_ma20 < 0.05  # 5%以内

    # 缩量
    low_vol = latest['成交量'] < vol_ma5 * 0.8 if vol_ma5 > 0 else False

    # 今日收阳
    is_yang = latest['收盘'] > latest['开盘']

    if near_ma20 and (low_vol or is_yang):
        score = 0
        if ma_bull:
            score += 20
        if dist_ma20 < 0.02:
            score += 20
        elif dist_ma20 < 0.05:
            score += 10
        if low_vol:
            score += 15
        if is_yang:
            score += 10
        # 站上MA5加分
        if latest['收盘'] > latest['MA5']:
            score += 10

        return {
            'strategy': '缩量回踩',
            'code': code,
            'name': name,
            'score': score,
            'today_gain': round((latest['收盘'] / latest['开盘'] - 1) * 100, 2),
            'ma20': round(latest['MA20'], 2),
            'dist_pct': round(dist_ma20 * 100, 2),
            'vol_ratio': round(latest['成交量'] / vol_ma5, 2) if vol_ma5 > 0 else 0,
            'current': round(latest['收盘'], 2),
            'detail': f"MA20={latest['MA20']:.2f} 距离{dist_ma20*100:.1f}% 量比{latest['成交量']/vol_ma5:.2f}" if vol_ma5 > 0 else ""
        }
    return None


def check_platform_breakout(df, code, name):
    """
    策略3: 突破平台
    - 10日振幅<10% (横盘)
    - 今日突破10日最高价
    - 放量
    """
    if df is None or len(df) < 15:
        return None

    recent = df.tail(11)
    platform = recent.iloc[:-1]
    latest = recent.iloc[-1]

    high_10 = platform['最高'].max()
    low_10 = platform['最低'].min()
    range_pct = (high_10 - low_10) / low_10 * 100

    is_platform = range_pct < 12
    breakout = latest['收盘'] > high_10

    vol_ma5 = df['成交量'].iloc[-6:-1].mean()
    vol_up = latest['成交量'] > vol_ma5 * 1.2 if vol_ma5 > 0 else False

    if is_platform and breakout:
        score = 0
        if range_pct < 8:
            score += 20
        elif range_pct < 12:
            score += 10
        score += 20  # 突破
        if vol_up:
            score += 15
        today_gain = (latest['收盘'] - latest['开盘']) / latest['开盘'] * 100
        if today_gain > 3:
            score += 15
        elif today_gain > 1:
            score += 10

        return {
            'strategy': '突破平台',
            'code': code,
            'name': name,
            'score': score,
            'today_gain': round(today_gain, 2),
            'range_pct': round(range_pct, 2),
            'breakout_price': round(high_10, 2),
            'current': round(latest['收盘'], 2),
            'vol_ratio': round(latest['成交量'] / vol_ma5, 2) if vol_ma5 > 0 else 0,
            'detail': f"10日振幅{range_pct:.1f}% 突破{high_10:.2f} 今+{today_gain:.1f}%"
        }
    return None


def check_bottom_volume(df, code, name):
    """
    策略4: 底部放量阳线
    - 股价低于MA20
    - 放量>5日均量2倍
    - 收阳线
    """
    if df is None or len(df) < 25:
        return None

    df = df.copy()
    latest = df.iloc[-1]
    ma20 = df['收盘'].tail(20).mean()
    vol_ma5 = df['成交量'].iloc[-6:-1].mean()

    at_bottom = latest['收盘'] < ma20
    high_vol = latest['成交量'] > vol_ma5 * 2 if vol_ma5 > 0 else False
    is_yang = latest['收盘'] > latest['开盘']
    yang_pct = (latest['收盘'] - latest['开盘']) / latest['开盘'] * 100

    if at_bottom and high_vol and is_yang and yang_pct > 1:
        score = 0
        vol_r = latest['成交量'] / vol_ma5 if vol_ma5 > 0 else 0
        if vol_r > 3:
            score += 25
        elif vol_r > 2:
            score += 20
        if yang_pct > 5:
            score += 20
        elif yang_pct > 3:
            score += 15
        elif yang_pct > 1:
            score += 10
        score += 10  # 底部加分

        return {
            'strategy': '底部放量',
            'code': code,
            'name': name,
            'score': score,
            'today_gain': round(yang_pct, 2),
            'ma20': round(ma20, 2),
            'current': round(latest['收盘'], 2),
            'vol_ratio': round(vol_r, 2),
            'detail': f"低于MA20({ma20:.2f}) 量比{vol_r:.1f} 阳线+{yang_pct:.1f}%"
        }
    return None


def check_macd_golden_cross(df, code, name):
    """
    策略5: MACD金叉 + 均线多头
    """
    if df is None or len(df) < 35:
        return None

    df = df.copy()
    closes = df['收盘'].values

    # 计算MACD
    ema12 = pd.Series(closes).ewm(span=12).mean().values
    ema26 = pd.Series(closes).ewm(span=26).mean().values
    dif = ema12 - ema26
    dea = pd.Series(dif).ewm(span=9).mean().values

    # 金叉判断 (DIF上穿DEA)
    if dif[-1] > dea[-1] and dif[-2] <= dea[-2]:
        # 均线
        ma5 = df['收盘'].iloc[-5:].mean()
        ma10 = df['收盘'].iloc[-10:].mean()
        ma20 = df['收盘'].iloc[-20:].mean()

        score = 20  # 金叉基础分
        # 零轴附近金叉更有效
        if abs(dif[-1]) < closes[-1] * 0.02:
            score += 15
        # 均线多头
        if closes[-1] > ma5 > ma10:
            score += 15
        if ma10 > ma20:
            score += 10
        # DIF由负转正更好
        if dif[-2] < 0 and dif[-1] > 0:
            score += 10

        today_gain = (closes[-1] - df['开盘'].iloc[-1]) / df['开盘'].iloc[-1] * 100

        return {
            'strategy': 'MACD金叉',
            'code': code,
            'name': name,
            'score': score,
            'today_gain': round(today_gain, 2),
            'dif': round(dif[-1], 3),
            'dea': round(dea[-1], 3),
            'current': round(closes[-1], 2),
            'vol_ratio': 0,
            'detail': f"DIF={dif[-1]:.3f} DEA={dea[-1]:.3f} 金叉"
        }
    return None


# ==================== 主扫描 ====================

# 重点扫描的板块（来自板块异动扫描结果）
TARGET_SECTORS = [
    # (板块代码, 板块名称, 异动评分, 状态)
    ('new_sybc', '商业百货', 70, '放量拉升'),
    ('new_gsgy', '供水供气', 65, '弱反弹'),
    ('new_jdly', '酒店旅游', 65, '弱反弹'),
    ('new_fzxl', '服装鞋类', 60, '横盘企稳'),
    ('new_glql', '公路桥梁', 60, '横盘企稳'),
    ('new_jrhy', '金融行业', 60, '金融企稳'),
    ('new_zhhy', '综合行业', 60, '放量拉升'),
    ('new_cbzz', '船舶制造', 50, '横盘企稳'),
    ('new_fcq', '房地产', 50, '放量拉升'),
    ('new_kfq', '开发区', 50, '横盘企稳'),
    ('new_ylqx', '医疗器械', 50, '弱反弹'),
    ('new_jjhy', '家具行业', 50, '弱反弹'),
    ('new_nlmy', '农林牧渔', 50, '放量拉升'),
    ('new_njhf', '农药化肥', 45, '弱反弹'),
    ('new_npjy', '酿酒行业', 45, '横盘企稳'),
    ('new_snhy', '水泥行业', 45, '弱反弹'),
    ('new_sphy', '食品行业', 45, '弱反弹'),
    ('new_swzy', '生物制药', 45, '横盘企稳'),
]


def scan_sector_stocks():
    log("=" * 70)
    log("板块异动 -> 个股信号扫描")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 70)
    log(f"\n扫描 {len(TARGET_SECTORS)} 个重点板块内的个股买入信号")
    log("策略: 涨停洗盘反包 / 缩量回踩 / 突破平台 / 底部放量 / MACD金叉\n")

    all_signals = []
    total_stocks = 0

    for sector_code, sector_name, sector_score, sector_status in TARGET_SECTORS:
        log(f"{'─'*60}")
        log(f"[{sector_name}] 板块评分:{sector_score} 状态:{sector_status}")

        stocks = get_sector_stocks(sector_code)
        if not stocks:
            log(f"  无法获取成分股，跳过")
            continue

        log(f"  成分股: {len(stocks)} 只（主板非ST）")
        total_stocks += len(stocks)

        sector_signals = []
        for j, stock in enumerate(stocks):
            code = stock['code']
            name = stock['name']

            df = get_stock_kline(code, 120)
            if df is None or len(df) < 20:
                continue

            signals = []

            # 跑所有策略
            r1 = check_limit_up_washout(df, code, name)
            if r1:
                r1['sector'] = sector_name
                r1['sector_score'] = sector_score
                signals.append(r1)

            r2 = check_pullback_support(df, code, name)
            if r2:
                r2['sector'] = sector_name
                r2['sector_score'] = sector_score
                signals.append(r2)

            r3 = check_platform_breakout(df, code, name)
            if r3:
                r3['sector'] = sector_name
                r3['sector_score'] = sector_score
                signals.append(r3)

            r4 = check_bottom_volume(df, code, name)
            if r4:
                r4['sector'] = sector_name
                r4['sector_score'] = sector_score
                signals.append(r4)

            r5 = check_macd_golden_cross(df, code, name)
            if r5:
                r5['sector'] = sector_name
                r5['sector_score'] = sector_score
                signals.append(r5)

            sector_signals.extend(signals)
            time.sleep(0.1)

        if sector_signals:
            sector_signals.sort(key=lambda x: x['score'], reverse=True)
            log(f"  >>> 发现 {len(sector_signals)} 个信号:")
            for s in sector_signals[:5]:  # 每板块显示前5
                log(f"      {s['code']} {s['name']:6s} [{s['strategy']}] "
                    f"评分:{s['score']} 今日{s['today_gain']:+.1f}% {s['detail']}")
            if len(sector_signals) > 5:
                log(f"      ... 还有 {len(sector_signals)-5} 个")
        else:
            log(f"  无信号")

        all_signals.extend(sector_signals)

    # ==================== 汇总 ====================
    log(f"\n{'='*70}")
    log(f"扫描汇总")
    log(f"{'='*70}")
    log(f"扫描板块: {len(TARGET_SECTORS)} 个")
    log(f"扫描个股: {total_stocks} 只")
    log(f"发现信号: {len(all_signals)} 个\n")

    if not all_signals:
        log("未发现个股买入信号")
        return []

    # 按综合分排序 (板块分*0.3 + 个股策略分*0.7)
    for s in all_signals:
        s['total_score'] = s['sector_score'] * 0.3 + s['score'] * 0.7

    all_signals.sort(key=lambda x: x['total_score'], reverse=True)

    # 按策略分组统计
    strategy_counts = {}
    for s in all_signals:
        st = s['strategy']
        strategy_counts[st] = strategy_counts.get(st, 0) + 1
    log("信号分布:")
    for st, cnt in sorted(strategy_counts.items(), key=lambda x: x[1], reverse=True):
        log(f"  {st}: {cnt} 个")

    # 输出TOP信号
    log(f"\n{'─'*70}")
    log("TOP 30 个股买入信号（综合评分排序）:")
    log(f"{'─'*70}")

    seen = set()
    rank = 0
    for s in all_signals:
        key = f"{s['code']}_{s['strategy']}"
        if key in seen:
            continue
        seen.add(key)
        rank += 1
        if rank > 30:
            break

        log(f"\n  #{rank:2d} {s['code']} {s['name']:6s}  [{s['strategy']}]")
        log(f"      综合分:{s['total_score']:.0f} (板块:{s['sector']}={s['sector_score']}分 + 策略:{s['score']}分)")
        log(f"      今日: {s['today_gain']:+.2f}%  现价: {s['current']}")
        log(f"      {s['detail']}")

    # 保存
    filename = f"个股信号_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"板块异动->个股信号扫描 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"扫描板块: {len(TARGET_SECTORS)}个 | 扫描个股: {total_stocks}只 | 信号: {len(all_signals)}个\n")
        f.write("=" * 70 + "\n\n")

        seen2 = set()
        rank2 = 0
        for s in all_signals:
            key = f"{s['code']}_{s['strategy']}"
            if key in seen2:
                continue
            seen2.add(key)
            rank2 += 1
            if rank2 > 50:
                break
            f.write(f"#{rank2} {s['code']} {s['name']} [{s['strategy']}] 综合分:{s['total_score']:.0f}\n")
            f.write(f"   板块:{s['sector']}({s['sector_score']}分) 策略分:{s['score']}\n")
            f.write(f"   今日:{s['today_gain']:+.2f}% 现价:{s['current']} {s['detail']}\n\n")

    log(f"\n>> 结果已保存: {filename}")
    return all_signals


if __name__ == "__main__":
    scan_sector_stocks()
