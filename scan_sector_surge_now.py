# -*- coding: utf-8 -*-
"""
板块异动扫描 - 使用东方财富可用接口
策略逻辑：
1. 获取所有概念板块的120天K线
2. 检测：早期爆发(单日>3%或3日>8%) → 回调洗盘(-8%~-30%) → 近期企稳
3. 评分排序输出
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
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://quote.eastmoney.com/'
})

def log(msg):
    print(msg, flush=True)


# ==================== 数据获取 ====================

def get_all_concept_sectors():
    """获取所有概念板块列表（用腾讯财经接口）"""
    # 东方财富push2的SSL有问题，用push2his获取板块K线数据是OK的
    # 先用一个硬编码的热门概念板块列表扫描
    # 板块代码格式: 90.BKxxxx

    # 方法: 通过东方财富网页版获取板块列表
    url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get'

    # 先试着获取一些已知板块验证接口
    test_sectors = {
        'BK0493': '新能源',  # 测试用
    }

    params = {
        'secid': '90.BK0493',
        'fields1': 'f1,f2,f3,f4,f5,f6',
        'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
        'klt': '101', 'fqt': '1',
        'end': '20261231', 'lmt': '5',
        'ut': 'fa5fd1943c7b386f172d6893dbbd1d0c'
    }
    try:
        r = session.get(url, params=params, timeout=10)
        data = r.json()
        if data.get('data'):
            log("✓ 东方财富K线接口可用")
            return True
    except:
        log("✗ K线接口不可用")
        return False


def get_sector_kline(bk_code, days=120):
    """获取板块K线数据"""
    url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get'
    params = {
        'secid': f'90.{bk_code}',
        'fields1': 'f1,f2,f3,f4,f5,f6',
        'fields2': 'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61',
        'klt': '101',  # 日K
        'fqt': '1',
        'end': '20261231',
        'lmt': str(days),
        'ut': 'fa5fd1943c7b386f172d6893dbbd1d0c'
    }
    try:
        r = session.get(url, params=params, timeout=10)
        data = r.json()
        if not data.get('data') or not data['data'].get('klines'):
            return None, None

        name = data['data'].get('name', bk_code)
        klines = data['data']['klines']

        rows = []
        for kl in klines:
            parts = kl.split(',')
            # 日期,开盘,收盘,最高,最低,成交量,成交额,振幅,涨跌幅,涨跌额,换手率
            rows.append({
                '日期': parts[0],
                '开盘': float(parts[1]),
                '收盘': float(parts[2]),
                '最高': float(parts[3]),
                '最低': float(parts[4]),
                '成交量': float(parts[5]),
                '成交额': float(parts[6]),
                '振幅': float(parts[7]),
                '涨跌幅': float(parts[8]),
                '换手率': float(parts[10]) if len(parts) > 10 else 0,
            })

        df = pd.DataFrame(rows)
        df['日期'] = pd.to_datetime(df['日期'])
        return name, df
    except Exception as e:
        return None, None


def get_concept_sector_list():
    """
    获取概念板块列表
    用遍历BK代码的方式（BK0400-BK1300 覆盖大部分概念板块）
    """
    log("正在探测可用的概念板块...")
    sectors = {}

    # 东方财富概念板块编号范围大致在 BK0400 - BK1300
    # 分批快速探测
    test_ranges = [
        (400, 500), (500, 600), (600, 700), (700, 800),
        (800, 900), (900, 1000), (1000, 1100), (1100, 1200),
        (1200, 1350)
    ]

    total_found = 0
    for start, end in test_ranges:
        for i in range(start, end):
            bk_code = f'BK{i:04d}'
            name, df = get_sector_kline(bk_code, days=5)
            if name and df is not None and len(df) > 0:
                sectors[bk_code] = name
                total_found += 1
            time.sleep(0.05)  # 避免请求太快

        log(f"  探测 BK{start:04d}-BK{end:04d}: 累计发现 {total_found} 个板块")

    return sectors


def get_concept_sector_list_fast():
    """
    快速获取概念板块列表 - 使用已知的热门板块
    避免遍历太慢
    """
    # 常见概念板块编号（东方财富）
    known_sectors = {}

    # 批量快速检测 BK0400-BK1300
    log("快速探测板块（每批并发）...")

    found = 0
    batch_size = 50
    for batch_start in range(400, 1350, batch_size):
        batch_end = min(batch_start + batch_size, 1350)
        for i in range(batch_start, batch_end):
            bk_code = f'BK{i:04d}'
            try:
                url = 'https://push2his.eastmoney.com/api/qt/stock/kline/get'
                params = {
                    'secid': f'90.{bk_code}',
                    'fields1': 'f1,f2,f3,f4,f5,f6',
                    'fields2': 'f51,f52,f53,f54,f55,f56',
                    'klt': '101', 'fqt': '1',
                    'end': '20261231', 'lmt': '3',
                    'ut': 'fa5fd1943c7b386f172d6893dbbd1d0c'
                }
                r = session.get(url, params=params, timeout=5)
                data = r.json()
                if data.get('data') and data['data'].get('name'):
                    name = data['data']['name']
                    known_sectors[bk_code] = name
                    found += 1
            except:
                pass
            time.sleep(0.02)

        log(f"  BK{batch_start:04d}-BK{batch_end:04d}: 累计 {found} 个")

    return known_sectors


# ==================== 板块异动检测 ====================

def detect_sector_anomaly(df, name):
    """
    检测板块异动信号

    条件：
    1. 60-120天内有过爆发（单日>3% 或 3日>8%）
    2. 爆发后有明显回调（-8% ~ -30%）
    3. 近期企稳（10日>-5%, 5日>-3%, 3日>-2%）
    4. 评分系统
    """
    if df is None or len(df) < 60:
        return None

    returns = df['涨跌幅'].values
    closes = df['收盘'].values
    dates = df['日期'].values
    n = len(df)

    # 计算累计收益
    cum_returns = np.cumprod(1 + returns / 100) - 1
    cum_returns *= 100

    # === 1. 寻找爆发点 ===
    burst_found = False
    burst_idx = None
    burst_return = 0
    burst_type = ''

    # 搜索范围: 30天前 ~ 100天前
    search_start = max(10, n - 100)
    search_end = max(search_start + 1, n - 20)

    for idx in range(search_start, search_end):
        # 单日爆发 > 3%
        if returns[idx] > 3.0:
            burst_found = True
            burst_idx = idx
            burst_return = returns[idx]
            burst_type = '单日爆发'
            break

        # 3日累计爆发 > 8%
        if idx >= 3:
            ret_3d = cum_returns[idx] - cum_returns[idx - 3]
            if ret_3d > 8.0:
                burst_found = True
                burst_idx = idx
                burst_return = ret_3d
                burst_type = '3日爆发'
                break

    if not burst_found:
        return None

    # === 2. 计算爆发后的回调 ===
    # 找爆发后最高点
    post_burst = cum_returns[burst_idx:]
    peak_offset = np.argmax(post_burst)
    peak_idx = burst_idx + peak_offset
    peak_value = cum_returns[peak_idx]
    current_value = cum_returns[-1]

    drawdown = current_value - peak_value

    # === 3. 企稳判断 ===
    ret_30d = cum_returns[-1] - cum_returns[-min(30, n)] if n >= 30 else 0
    ret_10d = cum_returns[-1] - cum_returns[-min(10, n)] if n >= 10 else 0
    ret_5d = cum_returns[-1] - cum_returns[-min(5, n)] if n >= 5 else 0
    ret_3d = cum_returns[-1] - cum_returns[-min(3, n)] if n >= 3 else 0

    # === 4. 量能分析 ===
    vol_5d = df['成交额'].iloc[-5:].mean()
    vol_20d = df['成交额'].iloc[-20:].mean() if n >= 20 else vol_5d
    vol_ratio = vol_5d / vol_20d if vol_20d > 0 else 1

    # === 5. 条件判断 ===
    conditions = {
        '历史爆发': burst_found and burst_return > 3,
        '充分回调': -30 <= drawdown <= -5,
        '30日企稳': -15 < ret_30d < 10,
        '10日企稳': ret_10d > -5,
        '5日企稳': ret_5d > -3,
        '3日趋势': ret_3d > -2,
    }

    passed = sum(conditions.values())

    # === 6. 评分 ===
    score = 0

    # 爆发强度
    if burst_return > 6: score += 20
    elif burst_return > 4: score += 15
    elif burst_return > 3: score += 10

    # 回调幅度（-10~-20最佳）
    if -20 <= drawdown <= -10:
        score += 25
    elif -25 <= drawdown <= -8:
        score += 20
    elif -30 <= drawdown <= -5:
        score += 10

    # 企稳程度
    if ret_10d > 2: score += 20
    elif ret_10d > 0: score += 15
    elif ret_10d > -3: score += 10

    if ret_3d > 1: score += 15
    elif ret_3d > 0: score += 10
    elif ret_3d > -1: score += 5

    # 量能回暖
    if vol_ratio > 1.3: score += 10
    elif vol_ratio > 1.1: score += 5

    # 信号判断
    signal = score >= 50 and passed >= 4

    burst_date = pd.Timestamp(dates[burst_idx]).strftime('%Y-%m-%d') if hasattr(dates[burst_idx], 'strftime') or isinstance(dates[burst_idx], np.datetime64) else str(dates[burst_idx])[:10]
    days_since = n - 1 - burst_idx

    # 当前状态
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
        'vol_ratio': round(vol_ratio, 2),
        'status': status,
        'conditions': conditions,
        'latest_close': round(closes[-1], 2),
        'latest_date': pd.Timestamp(dates[-1]).strftime('%Y-%m-%d') if hasattr(dates[-1], 'strftime') or isinstance(dates[-1], np.datetime64) else str(dates[-1])[:10],
    }


# ==================== 主扫描流程 ====================

def scan_sector_anomaly(max_sectors=0):
    """
    完整扫描流程
    max_sectors: 最多扫描板块数，0=全部
    """
    log("=" * 70)
    log("板块异动扫描 - 寻找爆发后回调企稳的潜力板块")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 70)
    log("\n策略逻辑:")
    log("  1. 历史爆发: 20-100天前有单日>3%或3日>8%的爆发")
    log("  2. 充分回调: 从高点回撤-5%~-30%")
    log("  3. 近期企稳: 10日>-5%, 5日>-3%, 3日>-2%")
    log("  4. 评分≥50 + 满足≥4个条件 → 触发信号\n")

    # 第一步: 获取板块列表
    log("[1] 获取概念板块列表...")
    sectors = get_concept_sector_list_fast()
    log(f"    发现 {len(sectors)} 个概念板块\n")

    if not sectors:
        log("未获取到板块数据，退出")
        return []

    # 第二步: 逐个分析
    log("[2] 逐个分析板块K线（120天）...")
    results = []
    sector_list = list(sectors.items())
    if max_sectors > 0:
        sector_list = sector_list[:max_sectors]

    total = len(sector_list)
    for i, (bk_code, name) in enumerate(sector_list):
        if (i + 1) % 50 == 0:
            log(f"    进度: {i+1}/{total} ({len(results)} 个信号)")

        _, df = get_sector_kline(bk_code, days=120)
        if df is None or len(df) < 60:
            continue

        result = detect_sector_anomaly(df, name)
        if result and result['signal']:
            result['bk_code'] = bk_code
            results.append(result)

        time.sleep(0.05)

    log(f"    完成! 扫描了 {total} 个板块\n")

    # 第三步: 排序输出
    results.sort(key=lambda x: x['score'], reverse=True)

    log("[3] 扫描结果")
    log("=" * 70)

    if not results:
        log("未发现符合条件的板块异动信号")
        return []

    log(f"发现 {len(results)} 个板块异动信号:\n")

    for i, r in enumerate(results, 1):
        # 状态emoji
        status_map = {
            '下杀中': '📉', '缓跌': '↘️',
            '横盘企稳': '➡️', '弱反弹': '↗️',
            '放量拉升': '🚀'
        }
        emoji = status_map.get(r['status'], '❓')

        log(f"{'─'*60}")
        log(f"  #{i} {emoji} 【{r['name']}】 评分:{r['score']}分  {r['status']}")
        log(f"     爆发: {r['burst_date']} {r['burst_type']} +{r['burst_return']}% ({r['days_since']}天前)")
        log(f"     回撤: {r['drawdown']}% | 量比: {r['vol_ratio']}")
        log(f"     近期: 30日{r['ret_30d']:+.1f}% | 10日{r['ret_10d']:+.1f}% | 5日{r['ret_5d']:+.1f}% | 3日{r['ret_3d']:+.1f}%")

        # 条件达标情况
        cond_str = ' '.join([f"{'✓' if v else '✗'}{k}" for k, v in r['conditions'].items()])
        log(f"     条件: {cond_str}")

    log(f"\n{'='*70}")

    # 保存结果
    save_results(results)

    return results


def save_results(results):
    """保存扫描结果"""
    if not results:
        return

    filename = f"板块异动_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(f"板块异动扫描结果 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"共发现 {len(results)} 个信号\n\n")

        for i, r in enumerate(results, 1):
            f.write(f"#{i} 【{r['name']}】 评分:{r['score']}分 状态:{r['status']}\n")
            f.write(f"   爆发: {r['burst_date']} {r['burst_type']} +{r['burst_return']}%\n")
            f.write(f"   回撤: {r['drawdown']}%  距爆发: {r['days_since']}天\n")
            f.write(f"   近期: 30日{r['ret_30d']:+.1f}% 10日{r['ret_10d']:+.1f}% 5日{r['ret_5d']:+.1f}% 3日{r['ret_3d']:+.1f}%\n")
            f.write(f"   量比: {r['vol_ratio']}  板块代码: {r['bk_code']}\n")
            f.write("\n")

    log(f"✓ 结果已保存: {filename}")


if __name__ == "__main__":
    results = scan_sector_anomaly()
