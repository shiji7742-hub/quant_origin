"""
三策略结合扫描V3：
1. 涨停洗盘 - 找个股
2. 横盘托单 - 找个股
3. 板块异动 - 只找板块（不找个股）
"""
import requests
import pandas as pd
import json
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

try:
    import akshare as ak
    HAS_AKSHARE = True
except:
    HAS_AKSHARE = False

def log(msg):
    print(msg, flush=True)

for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    if key in os.environ:
        del os.environ[key]

session = requests.Session()
session.trust_env = False


# ==================== 板块异动策略（只找板块）====================
def get_sector_list():
    """获取板块列表"""
    if not HAS_AKSHARE:
        return []
    try:
        df = ak.stock_board_concept_name_em()
        return df.to_dict('records')
    except:
        return []


def get_sector_history(sector_name):
    """获取板块历史走势"""
    if not HAS_AKSHARE:
        return None
    try:
        df = ak.stock_board_concept_cons_em(symbol=sector_name)
        if df is None or len(df) == 0:
            return None
        
        top_stocks = df.head(3)['代码'].tolist()
        all_data = []
        
        for symbol in top_stocks:
            try:
                hist = ak.stock_zh_a_hist(symbol=symbol, period="daily", 
                                          start_date='20251001', adjust="qfq")
                if hist is not None and len(hist) > 30:
                    hist['涨跌幅'] = hist['收盘'].pct_change() * 100
                    hist['日期'] = pd.to_datetime(hist['日期'])
                    all_data.append(hist[['日期', '涨跌幅']].set_index('日期'))
            except:
                continue
        
        if len(all_data) == 0:
            return None
        
        combined = pd.concat([d['涨跌幅'] for d in all_data], axis=1)
        return combined.mean(axis=1)
    except:
        return None


def detect_potential_sector(daily_returns):
    """检测板块是否有异动特征"""
    if daily_returns is None or len(daily_returns) < 45:
        return False, None
    
    daily_returns = daily_returns.dropna()
    if len(daily_returns) < 45:
        return False, None
    
    old_period = daily_returns.iloc[:-15]
    recent_15d = daily_returns.iloc[-15:]
    recent_5d = daily_returns.iloc[-5:]
    
    surge_days = old_period[old_period > 3.0]
    if len(surge_days) == 0:
        return False, None
    
    max_surge_value = surge_days.max()
    max_surge_idx = surge_days.idxmax()
    surge_count = len(surge_days)
    
    after_surge = daily_returns[daily_returns.index >= max_surge_idx]
    if len(after_surge) < 10:
        return False, None
    
    cumsum = after_surge.cumsum()
    max_gain = cumsum.max()
    current_gain = cumsum.iloc[-1]
    drawdown = max_gain - current_gain
    
    recent_15d_sum = recent_15d.sum()
    recent_5d_sum = recent_5d.sum()
    
    if drawdown < 5 or drawdown > 15:
        return False, None
    
    if recent_15d_sum > 5:
        return False, None
    
    if recent_5d_sum < -5:
        return False, None
    
    return True, {
        'surge_date': max_surge_idx.strftime('%Y-%m-%d'),
        'surge_value': round(max_surge_value, 2),
        'surge_count': surge_count,
        'drawdown': round(drawdown, 2),
        'recent_15d': round(recent_15d_sum, 2),
        'recent_5d': round(recent_5d_sum, 2)
    }


def scan_potential_sectors():
    """扫描潜力板块"""
    log("\n[1] 扫描板块异动...")
    
    sectors = get_sector_list()
    if not sectors:
        log("  无法获取板块数据")
        return []
    
    log(f"  共{len(sectors)}个板块，开始分析...")
    
    results = []
    for i, sector in enumerate(sectors[:80]):
        name = sector['板块名称']
        
        if (i+1) % 20 == 0:
            log(f"  进度: {i+1}/80")
        
        data = get_sector_history(name)
        is_potential, details = detect_potential_sector(data)
        
        if is_potential:
            results.append({
                '板块名称': name,
                '板块代码': sector['板块代码'],
                '当日涨幅': float(sector['涨跌幅']),
                '上涨家数': int(sector['上涨家数']),
                '下跌家数': int(sector['下跌家数']),
                **details
            })
    
    log(f"  发现{len(results)}个潜力板块")
    return results


# ==================== 个股策略 ====================
def get_stock_data(code, days=100):
    """获取K线数据"""
    try:
        code = str(code).zfill(6)
        if code.startswith('6'):
            kcode = f'sh{code}'
        else:
            kcode = f'sz{code}'
        
        url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={kcode},day,,,{days},qfq'
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
        return df
    except:
        return None


def check_limit_up_washout(df):
    """涨停破位洗盘策略"""
    if len(df) < 35:
        return False, None
    
    idx = len(df) - 1
    today = df.iloc[idx]
    today_change = (today['收盘'] - today['开盘']) / today['开盘'] * 100
    
    if today_change < 1:
        return False, None
    
    limit_up_info = None
    for i in range(idx - 3, max(idx - 30, 0), -1):
        row = df.iloc[i]
        prev_close = df.iloc[i-1]['收盘'] if i > 0 else row['开盘']
        gain = (row['收盘'] - prev_close) / prev_close * 100
        
        if gain >= 9.5 and row['开盘'] < row['收盘'] * 0.99:
            limit_up_info = {'idx': i, 'date': row['日期'], 'low': row['最低'], 'close': row['收盘']}
            break
    
    if not limit_up_info:
        return False, None
    
    for i in range(limit_up_info['idx'] + 1, idx):
        if df.iloc[i]['最高'] > limit_up_info['close'] * 1.08:
            return False, None
    
    limit_low = limit_up_info['low']
    broke_low = False
    for i in range(limit_up_info['idx'] + 1, idx):
        if df.iloc[i]['最低'] < limit_low:
            broke_low = True
            break
    
    if not broke_low:
        return False, None
    
    distance = (today['收盘'] - limit_low) / limit_low * 100
    if distance < -3:
        return False, None
    
    return True, {
        '涨停日期': limit_up_info['date'].strftime('%Y-%m-%d'),
        '涨停最低': round(limit_low, 2),
        '距离': f"{distance:+.1f}%"
    }


def check_sideways_support(df):
    """横盘托单策略"""
    if len(df) < 10:
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
    
    return True, {
        '支撑位': round(support, 2),
        '波动': f"{volatility:.1f}%",
        '距支撑': f"{distance:+.1f}%"
    }


def get_stock_list():
    """获取活跃股票列表"""
    try:
        url = 'https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData'
        stocks = []
        
        for node in ['hs_a', 'sz_a']:
            for page in range(1, 20):
                params = {'page': page, 'num': 40, 'sort': 'amount', 'asc': 0, 'node': node}
                r = session.get(url, params=params, timeout=15)
                if r.text and r.text not in ['null', '[]']:
                    data = json.loads(r.text)
                    if not data:
                        break
                    for item in data:
                        symbol = item.get('symbol', '')
                        name = item.get('name', '')
                        if symbol.startswith('sh') or symbol.startswith('sz'):
                            code = symbol[2:]
                        else:
                            code = symbol
                        if 'ST' in name or not (code.startswith('6') or code.startswith('00')):
                            continue
                        stocks.append((code, name))
        
        seen = set()
        unique = [(c, n) for c, n in stocks if c not in seen and not seen.add(c)]
        return unique[:300]
    except:
        return []


# ==================== 主扫描逻辑 ====================
def run_scan():
    log("="*70)
    log("三策略扫描V3")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*70)
    
    log("\n策略说明:")
    log("  1. 涨停洗盘：找个股（涨停→破位→反包）")
    log("  2. 横盘托单：找个股（横盘→触支撑→守住）")
    log("  3. 板块异动：找板块（爆发→回撤→企稳）")
    
    # ===== 板块异动 =====
    potential_sectors = scan_potential_sectors()
    
    # ===== 个股策略 =====
    log("\n[2] 获取股票列表...")
    stock_list = get_stock_list()
    log(f"  共{len(stock_list)}只活跃股")
    
    log("\n[3] 扫描个股...")
    
    limit_up_results = []
    sideways_results = []
    lock = threading.Lock()
    counter = {'done': 0}
    
    def scan_stock(args):
        code, name = args
        df = get_stock_data(code)
        if df is None:
            return None, None
        
        limit_up, limit_info = check_limit_up_washout(df)
        sideways, sideways_info = check_sideways_support(df)
        
        today = df.iloc[-1]
        today_change = (today['收盘'] - today['开盘']) / today['开盘'] * 100
        
        result1 = None
        result2 = None
        
        if limit_up:
            result1 = {
                '代码': code, '名称': name, '现价': round(today['收盘'], 2),
                '今日涨幅': f"{today_change:+.2f}%", **limit_info
            }
        
        if sideways:
            result2 = {
                '代码': code, '名称': name, '现价': round(today['收盘'], 2),
                '今日涨幅': f"{today_change:+.2f}%", **sideways_info
            }
        
        return result1, result2
    
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = [executor.submit(scan_stock, s) for s in stock_list]
        for future in as_completed(futures):
            with lock:
                counter['done'] += 1
                if counter['done'] % 50 == 0:
                    log(f"  进度: {counter['done']}/{len(stock_list)}")
            result1, result2 = future.result()
            if result1:
                limit_up_results.append(result1)
            if result2:
                sideways_results.append(result2)
    
    log(f"\n[4] 扫描完成")
    
    # ===== 显示结果 =====
    log("\n" + "="*70)
    log("扫描结果")
    log("="*70)
    
    # 板块异动
    log(f"\n【板块异动】({len(potential_sectors)}个板块)")
    log("  条件：早期爆发(>3%) → 回撤5-15% → 近期企稳")
    log("-" * 60)
    if potential_sectors:
        for s in potential_sectors:
            log(f"  {s['板块名称']}")
            log(f"    爆发日{s['surge_date']} +{s['surge_value']}% | 回撤{s['drawdown']}% | 近5日{s['recent_5d']:+.1f}%")
    else:
        log("  当前无符合条件的板块")
    
    # 涨停洗盘
    log(f"\n【涨停洗盘】({len(limit_up_results)}只个股)")
    log("  条件：涨停 → 跌破最低 → 今日阳线反包")
    log("-" * 60)
    for r in limit_up_results[:10]:
        log(f"  {r['名称']}({r['代码']}) 现价{r['现价']} {r['今日涨幅']}")
        log(f"    涨停日{r['涨停日期']} 距涨停低{r['距离']}")
    if len(limit_up_results) > 10:
        log(f"  ... 还有{len(limit_up_results)-10}只")
    
    # 横盘托单
    log(f"\n【横盘托单】({len(sideways_results)}只个股)")
    log("  条件：横盘3天 → 触及支撑 → 守住")
    log("-" * 60)
    for r in sideways_results[:10]:
        log(f"  {r['名称']}({r['代码']}) 现价{r['现价']} {r['今日涨幅']}")
        log(f"    支撑{r['支撑位']} {r['距支撑']}")
    if len(sideways_results) > 10:
        log(f"  ... 还有{len(sideways_results)-10}只")
    
    # 总结
    log("\n" + "="*70)
    log("总结")
    log("="*70)
    log(f"""
扫描结果:
  - 板块异动: {len(potential_sectors)} 个板块
  - 涨停洗盘: {len(limit_up_results)} 只个股
  - 横盘托单: {len(sideways_results)} 只个股

使用建议:
  1. 板块异动：关注这些板块，等待启动信号
  2. 涨停洗盘：收益最高，今日涨幅小的优先
  3. 横盘托单：信号稳定，设止损-5%
  4. 如需配合：在异动板块中找涨停洗盘/托单个股
""")
    
    # 保存
    if limit_up_results or sideways_results or potential_sectors:
        fname = f"三策略扫描V3_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        with pd.ExcelWriter(fname, engine='openpyxl') as writer:
            if potential_sectors:
                pd.DataFrame(potential_sectors).to_excel(writer, sheet_name='板块异动', index=False)
            if limit_up_results:
                pd.DataFrame(limit_up_results).to_excel(writer, sheet_name='涨停洗盘', index=False)
            if sideways_results:
                pd.DataFrame(sideways_results).to_excel(writer, sheet_name='横盘托单', index=False)
        log(f"\n已保存: {fname}")


if __name__ == "__main__":
    run_scan()
