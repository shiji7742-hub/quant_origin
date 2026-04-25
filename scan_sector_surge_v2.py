# -*- coding: utf-8 -*-
"""
板块异动扫描 V2 - 使用新浪行业板块 + 腾讯K线
策略逻辑：
1. 从新浪获取行业板块列表及龙头股
2. 用腾讯K线接口获取各板块龙头股120天数据
3. 计算板块等权平均走势
4. 检测: 早期爆发 → 回调洗盘 → 近期企稳
"""
import requests
import os
import re
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

def get_sina_sectors():
    """从新浪获取行业板块列表"""
    url = 'https://vip.stock.finance.sina.com.cn/q/view/newSinaHy.php'
    try:
        r = session.get(url, timeout=10)
        r.encoding = 'gbk'
        text = r.text

        match = re.search(r'\{(.+)\}', text)
        if not match:
            return []

        content = match.group(1)
        # 解析每个板块
        sectors = []
        for item in re.findall(r'"([^"]+)":"([^"]+)"', content):
            key, value = item
            parts = value.split(',')
            if len(parts) >= 10:
                sector = {
                    'code': parts[0],       # 板块代码
                    'name': parts[1],        # 板块名称
                    'count': int(parts[2]) if parts[2].isdigit() else 0,  # 成分股数
                    'avg_price': float(parts[3]) if parts[3] else 0,
                    'change': float(parts[4]) if parts[4] else 0,  # 板块涨跌幅
                    'change_pct': float(parts[5]) if parts[5] else 0,
                    'volume': float(parts[6]) if parts[6] else 0,
                    'amount': float(parts[7]) if parts[7] else 0,
                    'leader_code': parts[8],  # 龙头股代码
                    'leader_change': float(parts[9]) if parts[9] else 0,
                    'leader_price': float(parts[10]) if len(parts) > 10 and parts[10] else 0,
                    'leader_change_pct': float(parts[11]) if len(parts) > 11 and parts[11] else 0,
                    'leader_name': parts[12] if len(parts) > 12 else '',
                }
                sectors.append(sector)

        return sectors
    except Exception as e:
        log(f"获取新浪板块失败: {e}")
        return []


def get_sina_sector_stocks(sector_code):
    """获取新浪行业板块的成分股"""
    url = f'https://vip.stock.finance.sina.com.cn/q/view/newSinaHy.php?param={sector_code}'
    # 备用: 用板块内股票列表
    # 这里简化：每个板块用龙头股+几只代表股
    pass


def get_stock_kline(code, days=120):
    """用腾讯接口获取个股K线"""
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


def get_sector_kline_via_stocks(stock_codes, days=120):
    """通过多只个股K线合成板块走势"""
    all_returns = []

    for code in stock_codes[:5]:  # 最多取5只
        df = get_stock_kline(code, days)
        if df is not None and len(df) >= 60:
            all_returns.append(df[['日期', '涨跌幅']].set_index('日期')['涨跌幅'])
        time.sleep(0.15)

    if len(all_returns) == 0:
        return None

    # 等权平均
    combined = pd.concat(all_returns, axis=1)
    avg_returns = combined.mean(axis=1).dropna()

    return avg_returns


def get_sina_sector_stock_list(sector_code):
    """获取新浪板块成分股列表"""
    # 新浪行业板块成分股接口
    url = f'http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData?page=1&num=10&sort=changepercent&asc=0&node={sector_code}&symbol=&_s_r_a=page'
    try:
        r = session.get(url, timeout=10)
        r.encoding = 'gbk'
        text = r.text
        if not text or text == 'null':
            return []

        data = json.loads(text)
        codes = []
        for item in data:
            symbol = item.get('symbol', '')
            if symbol.startswith(('sh6', 'sz0', 'sh0', 'sz3')):
                code = symbol[2:]
                # 只要主板
                if code.startswith(('60', '00')):
                    codes.append(code)
        return codes
    except:
        return []


# ==================== 板块异动检测 ====================

def detect_anomaly(returns_series, name):
    """
    检测板块异动信号

    条件:
    1. 20-100天前有爆发(单日>3% 或 3日>8%)
    2. 从高点回撤 -5% ~ -30%
    3. 近期企稳(10日>-5%, 5日>-3%)
    """
    if returns_series is None or len(returns_series) < 60:
        return None

    returns = returns_series.values
    n = len(returns)

    # 累计收益
    cum = np.cumprod(1 + returns / 100) - 1
    cum *= 100

    # === 1. 寻找爆发点 ===
    burst_found = False
    burst_idx = None
    burst_return = 0
    burst_type = ''

    search_start = max(10, n - 100)
    search_end = max(search_start + 1, n - 15)

    for idx in range(search_start, search_end):
        if returns[idx] > 3.0:
            burst_found = True
            burst_idx = idx
            burst_return = returns[idx]
            burst_type = '单日爆发'
            break
        if idx >= 3:
            ret_3d = cum[idx] - cum[idx - 3]
            if ret_3d > 8.0:
                burst_found = True
                burst_idx = idx
                burst_return = ret_3d
                burst_type = '3日爆发'
                break

    if not burst_found:
        return None

    # === 2. 回调分析 ===
    post_burst = cum[burst_idx:]
    peak_offset = np.argmax(post_burst)
    peak_idx = burst_idx + peak_offset
    peak_value = cum[peak_idx]
    current_value = cum[-1]
    drawdown = current_value - peak_value

    # === 3. 企稳判断 ===
    ret_30d = cum[-1] - cum[-min(30, n)] if n >= 30 else 0
    ret_10d = cum[-1] - cum[-min(10, n)] if n >= 10 else 0
    ret_5d = cum[-1] - cum[-min(5, n)] if n >= 5 else 0
    ret_3d = cum[-1] - cum[-min(3, n)] if n >= 3 else 0

    # === 4. 条件检查 ===
    conditions = {
        '历史爆发': burst_found and burst_return > 3,
        '充分回调': -30 <= drawdown <= -5,
        '30日企稳': -15 < ret_30d < 10,
        '10日企稳': ret_10d > -5,
        '5日企稳': ret_5d > -3,
        '3日趋势': ret_3d > -2,
    }
    passed = sum(conditions.values())

    # === 5. 评分 ===
    score = 0

    if burst_return > 6:
        score += 20
    elif burst_return > 4:
        score += 15
    elif burst_return > 3:
        score += 10

    if -20 <= drawdown <= -10:
        score += 25
    elif -25 <= drawdown <= -8:
        score += 20
    elif -30 <= drawdown <= -5:
        score += 10

    if ret_10d > 2:
        score += 20
    elif ret_10d > 0:
        score += 15
    elif ret_10d > -3:
        score += 10

    if ret_3d > 1:
        score += 15
    elif ret_3d > 0:
        score += 10
    elif ret_3d > -1:
        score += 5

    signal = score >= 45 and passed >= 4

    days_since = n - 1 - burst_idx
    dates = returns_series.index

    burst_date = dates[burst_idx].strftime('%Y-%m-%d') if hasattr(dates[burst_idx], 'strftime') else str(dates[burst_idx])[:10]

    if ret_5d < -3:
        status = '下杀中'
    elif ret_5d > 3:
        status = '放量拉升'
    elif abs(ret_5d) <= 1.5:
        status = '横盘企稳'
    elif ret_5d > 0:
        status = '弱反弹'
    else:
        status = '缓跌'

    return {
        'name': name,
        'score': score,
        'signal': signal,
        'passed': passed,
        'burst_date': burst_date,
        'burst_return': round(burst_return, 2),
        'burst_type': burst_type,
        'days_since': days_since,
        'drawdown': round(drawdown, 2),
        'ret_30d': round(ret_30d, 2),
        'ret_10d': round(ret_10d, 2),
        'ret_5d': round(ret_5d, 2),
        'ret_3d': round(ret_3d, 2),
        'status': status,
        'conditions': conditions,
    }


# ==================== 主扫描 ====================

def scan():
    log("=" * 70)
    log("板块异动扫描 V2")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 70)
    log("\n策略: 爆发(>3%) → 回调(-5%~-30%) → 企稳 → 信号\n")

    # 1. 获取板块列表
    log("[1] 获取行业板块列表（新浪）...")
    sectors = get_sina_sectors()
    log(f"    获取到 {len(sectors)} 个行业板块\n")

    if not sectors:
        log("无法获取板块数据")
        return []

    # 显示今日板块涨幅概览
    log("    今日板块涨幅TOP10:")
    sorted_sectors = sorted(sectors, key=lambda x: x['change_pct'], reverse=True)
    for s in sorted_sectors[:10]:
        log(f"      {s['name']:8s} {s['change_pct']:+.2f}%  龙头:{s['leader_name']}({s['leader_change_pct']:+.2f}%)")
    log("")

    # 2. 逐板块分析
    log("[2] 获取板块成分股K线数据（腾讯）并分析...")
    results = []
    total = len(sectors)

    for i, sector in enumerate(sectors):
        name = sector['name']
        code = sector['code']

        log(f"    [{i+1}/{total}] {name}...", )

        # 获取成分股
        stocks = get_sina_sector_stock_list(code)
        if not stocks:
            # 至少用龙头股
            leader = sector.get('leader_code', '')
            if leader:
                leader_code = leader.replace('sh', '').replace('sz', '')
                stocks = [leader_code]
            else:
                log(f"      无成分股数据，跳过")
                continue

        # 获取板块等权K线
        avg_returns = get_sector_kline_via_stocks(stocks, days=120)
        if avg_returns is None or len(avg_returns) < 60:
            log(f"      K线数据不足，跳过")
            continue

        # 检测异动
        result = detect_anomaly(avg_returns, name)
        if result and result['signal']:
            result['sector_code'] = code
            result['sector_change'] = sector['change_pct']
            result['leader_name'] = sector['leader_name']
            result['leader_change'] = sector['leader_change_pct']
            result['stock_count'] = len(stocks)
            results.append(result)
            log(f"      [V] 信号! 评分:{result['score']} 状态:{result['status']}")
        else:
            if result:
                log(f"      - 评分:{result['score']} 条件:{result['passed']}/6 (未触发)")
            else:
                log(f"      - 无异动特征")

    # 3. 输出结果
    log(f"\n{'='*70}")
    log("[3] 扫描结果")
    log("=" * 70)

    results.sort(key=lambda x: x['score'], reverse=True)

    if not results:
        log("\n未发现符合条件的板块异动信号")
        log("当前市场可能处于以下状态:")
        log("  - 各板块普涨，没有明显的回调企稳形态")
        log("  - 或各板块持续下跌，尚未企稳")
        log("  - 建议过几天再扫描\n")
        return []

    log(f"\n发现 {len(results)} 个板块异动信号:\n")

    status_emoji = {
        '下杀中': '📉', '缓跌': '↘️',
        '横盘企稳': '➡️', '弱反弹': '↗️',
        '放量拉升': '🚀'
    }

    for i, r in enumerate(results, 1):
        emoji = status_emoji.get(r['status'], '❓')
        log(f"{'─'*60}")
        log(f"  #{i} {emoji}【{r['name']}】 评分:{r['score']}分  {r['status']}")
        log(f"     今日: {r.get('sector_change', 0):+.2f}%  龙头: {r.get('leader_name', '')}({r.get('leader_change', 0):+.2f}%)")
        log(f"     爆发: {r['burst_date']} {r['burst_type']} +{r['burst_return']}% ({r['days_since']}天前)")
        log(f"     回撤: {r['drawdown']}%")
        log(f"     近期: 30日{r['ret_30d']:+.1f}% | 10日{r['ret_10d']:+.1f}% | 5日{r['ret_5d']:+.1f}% | 3日{r['ret_3d']:+.1f}%")
        cond_str = ' '.join([f"{'✓' if v else '✗'}{k}" for k, v in r['conditions'].items()])
        log(f"     条件: {cond_str}")

    log(f"\n{'─'*60}")

    # 保存
    filename = f"板块异动_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"板块异动扫描结果 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 60 + "\n\n")
        for i, r in enumerate(results, 1):
            f.write(f"#{i} 【{r['name']}】 评分:{r['score']}分 状态:{r['status']}\n")
            f.write(f"   爆发: {r['burst_date']} {r['burst_type']} +{r['burst_return']}%\n")
            f.write(f"   回撤: {r['drawdown']}%  距今: {r['days_since']}天\n")
            f.write(f"   近期: 30日{r['ret_30d']:+.1f}% 10日{r['ret_10d']:+.1f}% 5日{r['ret_5d']:+.1f}% 3日{r['ret_3d']:+.1f}%\n\n")
    log(f"✓ 已保存: {filename}")

    return results


if __name__ == "__main__":
    scan()
