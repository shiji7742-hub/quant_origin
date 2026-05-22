"""
近五日涨停板回调战法扫描
战法逻辑：
1. 近5个交易日内出现过非一字涨停板
2. 涨停后出现回调（最低价跌破涨停日最低价，或回调幅度>3%）
3. 今日收盘站回涨停日最低价之上（或今日为阳线反包）
4. 今日有量能配合（量比>1.2）
"""
import os
import sys
import requests
import json
import time

import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

sys.path.insert(0, os.path.dirname(__file__))
try:
    from config import MAINBOARD_PATTERN
except:
    MAINBOARD_PATTERN = r'^(60|00)\d{4}$'

scan_count = 0
scan_lock = threading.Lock()

_session = requests.Session()
_session.trust_env = False  # 忽略系统代理（绕过本地V2Ray/Clash）
_session.headers.update({'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.sina.com.cn/'})


def get_all_stocks(mainboard_only=False):
    """
    获取股票列表。
    主板范围：沪市 600000-603999、深市 000001-002999
    用腾讯实时行情接口批量验证代码是否有效（过滤退市/ST）。
    """
    print("正在生成主板股票代码列表...")

    # 生成候选代码
    candidates = []
    # 沪市主板
    for i in range(600000, 604000):
        candidates.append(f"{i:06d}")
    # 深市主板
    for i in range(1, 3000):
        candidates.append(f"{i:06d}")

    print(f"候选代码 {len(candidates)} 个，正在批量验证（腾讯实时行情）...")

    # 腾讯实时行情支持批量查询，每次最多100只
    valid = []
    batch_size = 100
    for start in range(0, len(candidates), batch_size):
        batch = candidates[start:start + batch_size]
        codes = ','.join(
            f"sh{c}" if c.startswith('6') else f"sz{c}"
            for c in batch
        )
        try:
            r = _session.get(f'https://hq.sinajs.cn/list={codes}',
                             headers={'Referer': 'https://finance.sina.com.cn/'}, timeout=10)
            lines = r.content.decode('gbk', errors='replace').strip().split('\n')
            for line, code in zip(lines, batch):
                # 格式: var hq_str_sh600000="平安银行,10.83,..."
                if '=""' in line or line.strip() == '':
                    continue  # 无效代码
                parts = line.split('"')
                if len(parts) < 2 or not parts[1]:
                    continue
                fields = parts[1].split(',')
                if len(fields) < 5:
                    continue
                name = fields[0]
                if not name or 'ST' in name or '退' in name or '*' in name:
                    continue
                # 过滤停牌（成交量为0）
                try:
                    vol = float(fields[8]) if len(fields) > 8 else 0
                    if vol == 0:
                        continue
                except:
                    pass
                valid.append([code, name])
        except Exception:
            pass
        if (start // batch_size) % 20 == 0:
            print(f"  已验证 {start}/{len(candidates)}，有效 {len(valid)} 只...")
        time.sleep(0.05)

    print(f"共 {len(valid)} 只主板非ST股票")
    return valid


def get_kline_tencent(symbol, days=35):
    """腾讯财经K线接口（trust_env=False，绕过系统代理）"""
    code = f"sh{symbol}" if symbol.startswith('6') else f"sz{symbol}"
    url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={code},day,,,{days},qfq'
    try:
        r = _session.get(url, timeout=10)
        data = r.json()
        stock_data = data.get('data', {}).get(code) or data.get('data', {}).get(code.upper())
        if not stock_data:
            return None
        rows_raw = stock_data.get('qfqday') or stock_data.get('day')
        if not rows_raw:
            return None
        rows = []
        for d in rows_raw:
            rows.append({'日期': d[0], '开盘': float(d[1]), '收盘': float(d[2]),
                         '最高': float(d[3]), '最低': float(d[4]), '成交量': float(d[5])})
        df = pd.DataFrame(rows)
        df['日期'] = pd.to_datetime(df['日期'])
        df['涨跌幅'] = df['收盘'].pct_change() * 100
        return df
    except:
        return None

def scan_stock(symbol, name):
    global scan_count
    try:
        df = get_kline_tencent(symbol, days=60)
        if df is None or len(df) < 20:
            return None

        df = df.reset_index(drop=True)
        latest = df.iloc[-1]
        latest_idx = len(df) - 1

        # 宽松模式参数（对齐 strategies.py relaxed=True）
        min_yang_gain   = 2.0   # 今日开到收涨幅 >2%
        max_chase_gain  = 8.0   # 今日涨幅（相对昨收）<8%
        search_days     = 10    # 近10个交易日内找涨停
        min_vol_ratio_5 = 1.2   # 近5日均量/前20日均量 >1.2
        min_vol_ratio_10= 1.1   # 近10日均量/前20日均量 >1.1
        min_today_vol   = 1.2   # 当日量比 >1.2
        pre_gain_limit  = 30    # 涨停前10日涨幅 <30%
        new_high_thresh = 1.08  # 涨停后涨超8%算创新高

        # 今日相对昨收涨幅（不追高）
        prev_close = df.iloc[-2]['收盘'] if latest_idx >= 1 else latest['开盘']
        today_gain_pct = (latest['收盘'] - prev_close) / prev_close * 100
        if today_gain_pct >= max_chase_gain:
            return None

        # 近10日内找非一字涨停板（从近到远，跳过今日）
        limit_up_info = None
        for i in range(latest_idx - 1, max(latest_idx - search_days - 1, 0), -1):
            row = df.iloc[i]
            prev_c = df.iloc[i-1]['收盘'] if i > 0 else row['开盘']
            gain = (row['收盘'] - prev_c) / prev_c * 100
            is_limit_up = gain >= 9.5
            is_not_yizi = row['开盘'] < row['收盘'] * 0.99
            if is_limit_up and is_not_yizi:
                limit_up_info = {
                    'idx': i,
                    'date': str(row['日期'])[:10],
                    'low': row['最低'],
                    'close': row['收盘'],
                    'days_ago': latest_idx - i
                }
                break

        if not limit_up_info:
            return None

        limit_idx   = limit_up_info['idx']
        limit_low   = limit_up_info['low']
        limit_close = limit_up_info['close']

        # 低位启动：涨停前10日涨幅 <30%
        if limit_idx >= 10:
            pre_gain = (df.iloc[limit_idx-1]['收盘'] - df.iloc[limit_idx-10]['收盘']) / df.iloc[limit_idx-10]['收盘'] * 100
            if pre_gain > pre_gain_limit:
                return None

        # 近两月涨幅 <40%
        if len(df) >= 40:
            gain_2m = (latest['收盘'] - df.iloc[-40]['收盘']) / df.iloc[-40]['收盘'] * 100
            if gain_2m > 40:
                return None

        # 涨停后走势：不能先创新高再破位
        broke_support  = False
        made_new_high  = False
        for i in range(limit_idx + 1, latest_idx + 1):
            row = df.iloc[i]
            if row['最高'] > limit_close * new_high_thresh:
                made_new_high = True
            if row['最低'] <= limit_low:
                broke_support = True

        if made_new_high or not broke_support:
            return None

        # 今日收盘反包回涨停低点之上
        if latest['收盘'] <= limit_low:
            return None

        # 均量放大：近5日或近10日均量 > 前20日均量的1.2/1.1倍
        if len(df) >= 25:
            vol5  = df['成交量'].iloc[-5:].mean()
            vol10 = df['成交量'].iloc[-10:].mean()
            vol20 = df['成交量'].iloc[-25:-5].mean()
            vol_ratio_5  = vol5  / vol20 if vol20 > 0 else 0
            vol_ratio_10 = vol10 / vol20 if vol20 > 0 else 0
            volume_ok = (vol_ratio_5 > min_vol_ratio_5) or (vol_ratio_10 > min_vol_ratio_10)
        else:
            volume_ok = False

        if not volume_ok:
            return None

        # 当日量比 >1.2
        vol_ma5_today = df['成交量'].iloc[-6:-1].mean() if latest_idx >= 5 else 0
        today_vol_ratio = latest['成交量'] / vol_ma5_today if vol_ma5_today > 0 else 0
        if today_vol_ratio < min_today_vol:
            return None

        # 回调幅度（涨停收盘到涨停后最低）
        post_low = df.iloc[limit_idx+1:latest_idx+1]['最低'].min() if limit_idx + 1 <= latest_idx else latest['最低']
        pullback_pct = (limit_close - post_low) / limit_close * 100

        return {
            'symbol': symbol,
            'name': name,
            'limit_date': limit_up_info['date'],
            'days_ago': limit_up_info['days_ago'],
            'limit_close': round(limit_close, 2),
            'limit_low': round(limit_low, 2),
            'pullback_pct': round(pullback_pct, 2),
            'today_close': round(latest['收盘'], 2),
            'today_gain_pct': round(today_gain_pct, 2),
            'today_vol_ratio': round(today_vol_ratio, 2),
            'vol_ratio_5': round(vol_ratio_5, 2) if len(df) >= 25 else 0,
        }
    except Exception:
        return None
    finally:
        with scan_lock:
            scan_count += 1

def run_scan(mainboard_only=False, max_workers=20):
    global scan_count
    scan_count = 0

    print("=" * 70)
    print(f"近五日涨停板回调战法 - 全市场扫描")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"线程数: {max_workers} | 范围: {'主板' if mainboard_only else '全市场'}")
    print("=" * 70)

    stocks = get_all_stocks(mainboard_only=mainboard_only)
    total = len(stocks)
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(scan_stock, s[0], s[1]): s for s in stocks}
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
            with scan_lock:
                cnt = scan_count
            if cnt % 200 == 0:
                print(f"  已扫描 {cnt}/{total}，命中 {len(results)} 只...")

    print(f"\n扫描完成，共扫描 {total} 只，命中 {len(results)} 只\n")

    if not results:
        print("未找到符合条件的股票")
        return

    df_result = pd.DataFrame(results)
    df_result = df_result.sort_values('pullback_pct', ascending=False)

    print("=" * 70)
    print(f"【近10日涨停破位洗盘反包】共 {len(df_result)} 只")
    print("=" * 70)
    if len(df_result) > 0:
        print(f"{'代码':<8}{'名称':<8}{'涨停日':<12}{'距今':<6}{'涨停价':<8}{'涨停低':<8}{'回调%':<8}{'今收':<8}{'今涨%':<8}{'今量比':<7}{'5日量比'}")
        print("-" * 90)
        for _, r in df_result.iterrows():
            print(f"{r['symbol']:<8}{r['name']:<8}{r['limit_date']:<12}{r['days_ago']}天前  "
                  f"{r['limit_close']:<8}{r['limit_low']:<8}{r['pullback_pct']:<8}{r['today_close']:<8}"
                  f"{r['today_gain_pct']:<8}{r['today_vol_ratio']:<7}{r['vol_ratio_5']}")

    # 保存结果
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    out_file = os.path.join(os.path.dirname(__file__), f'近五日涨停回调_{ts}.xlsx')
    df_result.to_excel(out_file, index=False)
    print(f"\n结果已保存至: {out_file}")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--workers', type=int, default=20)
    args = parser.parse_args()
    run_scan(max_workers=args.workers)
