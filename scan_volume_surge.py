"""
主板放量扫描器
扫描五日和十日成交量放大的主板股票（排除ST、创业板、科创板）
数据源：腾讯财经（行情+K线）
"""
import requests
import pandas as pd
import numpy as np
import os
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

for key in list(os.environ.keys()):
    if 'proxy' in key.lower():
        del os.environ[key]

session = requests.Session()
session.trust_env = False
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
})


def log(msg):
    print(msg, flush=True)


def get_main_board_stocks():
    """通过腾讯批量行情接口获取全部主板非ST股票"""
    log("正在获取主板股票列表...")
    all_stocks = []

    # 生成所有可能的主板代码
    all_codes = []
    for i in range(600000, 610000):
        all_codes.append(f'sh{i}')
    for i in range(0, 5000):
        all_codes.append(f'sz{str(i).zfill(6)}')

    batch_size = 80
    for start in range(0, len(all_codes), batch_size):
        batch = all_codes[start:start + batch_size]
        joined = ','.join(batch)
        url = 'https://qt.gtimg.cn/q=' + joined
        try:
            r = session.get(url, timeout=15)
            lines = r.text.strip().split(';')
            for line in lines:
                line = line.strip()
                if not line or '=""' in line:
                    continue
                parts = line.split('~')
                if len(parts) < 40:
                    continue
                name = parts[1]
                code = parts[2]
                try:
                    price = float(parts[3]) if parts[3] else 0
                    volume = float(parts[6]) if parts[6] else 0
                    changepct = float(parts[32]) if parts[32] else 0
                except:
                    continue

                if price <= 0 or volume <= 0:
                    continue
                if 'ST' in name or 'st' in name:
                    continue

                all_stocks.append({
                    'code': code,
                    'name': name,
                    'price': price,
                    'change': changepct,
                    'volume': volume,
                })
        except Exception as e:
            continue

        if start % 4000 == 0 and start > 0:
            log(f"  已扫描 {start}/{len(all_codes)}, 找到 {len(all_stocks)} 只")
        time.sleep(0.02)

    log(f"主板非ST股票共 {len(all_stocks)} 只")
    return all_stocks


def get_kline(code, days=60):
    """腾讯K线接口"""
    code = str(code).zfill(6)
    kcode = ('sh' + code) if code.startswith('6') else ('sz' + code)
    url = 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=' + kcode + ',day,,,' + str(days) + ',qfq'
    try:
        r = session.get(url, timeout=10)
        data = r.json()
        if not data.get('data'):
            return None
        stock_data = data['data'].get(kcode) or data['data'].get(kcode.upper())
        if not stock_data or 'qfqday' not in stock_data:
            return None
        days_data = stock_data['qfqday']
        df = pd.DataFrame([d[:6] for d in days_data],
                          columns=['date', 'open', 'close', 'high', 'low', 'volume'])
        for col in ['open', 'close', 'high', 'low', 'volume']:
            df[col] = df[col].astype(float)
        return df
    except:
        return None


def check_volume_surge(stock):
    """检查放量情况"""
    code = stock['code']
    name = stock['name']

    df = get_kline(code, 60)
    if df is None or len(df) < 30:
        return None

    vol = df['volume'].values
    vol_5 = vol[-5:].mean()
    vol_10 = vol[-10:].mean()
    vol_base = vol[-30:-10].mean() if len(vol) >= 30 else vol[:-10].mean()

    if vol_base <= 0:
        return None

    ratio_5 = vol_5 / vol_base
    ratio_10 = vol_10 / vol_base

    price = df.iloc[-1]['close']
    price_5ago = df.iloc[-5]['close'] if len(df) >= 5 else price
    price_10ago = df.iloc[-10]['close'] if len(df) >= 10 else price
    change_5d = (price - price_5ago) / price_5ago * 100 if price_5ago > 0 else 0
    change_10d = (price - price_10ago) / price_10ago * 100 if price_10ago > 0 else 0

    score = 0
    if ratio_5 >= 1.5 and change_5d > 0:
        score += 30
    if ratio_10 >= 1.5 and change_10d > 0:
        score += 30
    if ratio_5 >= 2.0:
        score += 20
    if ratio_10 >= 2.0:
        score += 20

    return {
        'code': code, 'name': name, 'price': price,
        'change': stock['change'],
        'change_5d': change_5d, 'change_10d': change_10d,
        'ratio_5': ratio_5, 'ratio_10': ratio_10,
        'score': score,
    }


def scan_volume_surge():
    """扫描主板放量股票"""
    log("=" * 70)
    log("主板五日/十日放量扫描")
    log("时间: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    log("=" * 70)

    stocks = get_main_board_stocks()
    if not stocks:
        log("未获取到股票数据，请检查网络")
        return []

    results = []
    total = len(stocks)
    done = 0
    failed = 0

    log("\n开始扫描 " + str(total) + " 只股票K线...\n")

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(check_volume_surge, s): s for s in stocks}
        for future in as_completed(futures):
            done += 1
            if done % 200 == 0:
                log("  进度: " + str(done) + "/" + str(total) + " (有效" + str(len(results)) + ", 失败" + str(failed) + ")")
            try:
                result = future.result()
                if result:
                    results.append(result)
                else:
                    failed += 1
            except:
                failed += 1

    log("\n扫描完成: 有效 " + str(len(results)) + " 只, 失败 " + str(failed) + " 只\n")

    surge_5d = sorted([r for r in results if r['ratio_5'] >= 1.5], key=lambda x: x['ratio_5'], reverse=True)
    surge_10d = sorted([r for r in results if r['ratio_10'] >= 1.5], key=lambda x: x['ratio_10'], reverse=True)
    surge_both = sorted([r for r in results if r['ratio_5'] >= 1.5 and r['ratio_10'] >= 1.5], key=lambda x: x['score'], reverse=True)
    top_picks = sorted([r for r in surge_both if r['change_5d'] > 0 and r['change_10d'] > 0], key=lambda x: x['score'], reverse=True)

    # 保存结果到文件
    output_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'volume_surge_result.txt')
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("主板五日/十日放量扫描结果\n")
        f.write("时间: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + "\n")
        f.write("扫描: " + str(len(results)) + " 只有效数据\n\n")

        f.write("=" * 80 + "\n")
        f.write("【五日放量】共 " + str(len(surge_5d)) + " 只 (近5日均量 >= 1.5倍基准)\n")
        f.write("=" * 80 + "\n")
        f.write("代码     名称         现价     今涨跌   5日涨跌   5日量比  10日量比\n")
        f.write("-" * 80 + "\n")
        for s in surge_5d[:40]:
            f.write("%-8s %-10s %8.2f %7.2f%% %7.2f%% %8.2f %8.2f\n" % (
                s['code'], s['name'], s['price'], s['change'], s['change_5d'], s['ratio_5'], s['ratio_10']))

        f.write("\n" + "=" * 80 + "\n")
        f.write("【十日放量】共 " + str(len(surge_10d)) + " 只 (近10日均量 >= 1.5倍基准)\n")
        f.write("=" * 80 + "\n")
        f.write("代码     名称         现价     今涨跌  10日涨跌   5日量比  10日量比\n")
        f.write("-" * 80 + "\n")
        for s in surge_10d[:40]:
            f.write("%-8s %-10s %8.2f %7.2f%% %7.2f%% %8.2f %8.2f\n" % (
                s['code'], s['name'], s['price'], s['change'], s['change_10d'], s['ratio_5'], s['ratio_10']))

        f.write("\n" + "=" * 80 + "\n")
        f.write("【重点关注】放量上涨 (五日十日同时放量+价格上涨) 共 " + str(len(top_picks)) + " 只\n")
        f.write("=" * 80 + "\n")
        for s in top_picks[:30]:
            f.write("  %s %s: 现价%.2f, 5日涨%+.2f%% 量比%.2f, 10日涨%+.2f%% 量比%.2f, 评分%d\n" % (
                s['code'], s['name'], s['price'], s['change_5d'], s['ratio_5'],
                s['change_10d'], s['ratio_10'], s['score']))

    log("结果已保存到: " + output_file)
    log("扫描完成: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    return results


if __name__ == "__main__":
    scan_volume_surge()
