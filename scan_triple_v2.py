"""
三策略结合扫描V2：横盘托单 + 涨停破位洗盘 + 板块异动（正确版）

板块异动正确逻辑：
1. 先找出"早期爆发后回撤企稳"的板块
2. 在这些板块中找符合其他策略的个股
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


# ==================== 板块异动策略（正确版）====================
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
    """获取板块历史走势（通过龙头股估算）"""
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
    """
    检测板块是否有异动特征
    
    条件：
    1. 过去60天内有过爆发（单日>3%）
    2. 爆发后回撤5-15%
    3. 近期表现弱但企稳
    """
    if daily_returns is None or len(daily_returns) < 45:
        return False, None
    
    daily_returns = daily_returns.dropna()
    if len(daily_returns) < 45:
        return False, None
    
    old_period = daily_returns.iloc[:-15]
    recent_15d = daily_returns.iloc[-15:]
    recent_5d = daily_returns.iloc[-5:]
    
    # 找爆发（单日>3%）
    surge_days = old_period[old_period > 3.0]
    if len(surge_days) == 0:
        return False, None
    
    max_surge_value = surge_days.max()
    max_surge_idx = surge_days.idxmax()
    surge_count = len(surge_days)
    
    after_surge = daily_returns[daily_returns.index >= max_surge_idx]
    if len(after_surge) < 10:
        return False, None
    
    # 计算回撤
    cumsum = after_surge.cumsum()
    max_gain = cumsum.max()
    current_gain = cumsum.iloc[-1]
    drawdown = max_gain - current_gain
    
    # 条件判断
    recent_15d_sum = recent_15d.sum()
    recent_5d_sum = recent_5d.sum()
    
    if drawdown < 5 or drawdown > 15:
        return False, None
    
    if recent_15d_sum > 5:  # 近期不能太强
        return False, None
    
    if recent_5d_sum < -5:  # 近期不能大跌
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
    for i, sector in enumerate(sectors[:60]):  # 分析前60个
        name = sector['板块名称']
        
        if (i+1) % 10 == 0:
            log(f"  进度: {i+1}/60")
        
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


def get_sector_stocks(sector_name):
    """获取板块成分股"""
    if not HAS_AKSHARE:
        return []
    try:
        df = ak.stock_board_concept_cons_em(symbol=sector_name)
        if df is None:
            return []
        # 只取主板
        df = df[df['代码'].str.match(r'^(60|00)')]
        df = df[~df['名称'].str.contains('ST')]
        return df[['代码', '名称']].to_dict('records')
    except:
        return []


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


# ==================== 主扫描逻辑 ====================
def run_scan():
    log("="*70)
    log("三策略结合扫描V2（板块异动正确版）")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*70)
    
    log("\n策略说明:")
    log("  1. 涨停洗盘：涨停后跌破最低价，今日阳线反包")
    log("  2. 横盘托单：横盘3天，今日触及支撑位守住")
    log("  3. 板块异动：先找潜力板块，再在板块中找个股")
    
    # ===== 第一步：扫描潜力板块 =====
    potential_sectors = scan_potential_sectors()
    
    if potential_sectors:
        log("\n【潜力板块】（早期爆发→回撤→企稳）")
        log("-" * 60)
        for s in potential_sectors[:10]:
            log(f"  {s['板块名称']}: 爆发+{s['surge_value']}% 回撤{s['drawdown']}% 近5日{s['recent_5d']:+.1f}%")
    
    # ===== 第二步：在潜力板块中找个股 =====
    log("\n[2] 在潜力板块中扫描个股...")
    
    sector_stocks = []
    for sector in potential_sectors[:5]:  # 取前5个板块
        stocks = get_sector_stocks(sector['板块名称'])
        for s in stocks:
            s['所属板块'] = sector['板块名称']
        sector_stocks.extend(stocks)
    
    log(f"  潜力板块共{len(sector_stocks)}只成分股")
    
    # ===== 第三步：获取全市场活跃股 =====
    log("\n[3] 获取全市场活跃股...")
    
    try:
        url = 'https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData'
        all_stocks = []
        
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
                        all_stocks.append({'代码': code, '名称': name, '所属板块': ''})
        
        seen = set()
        unique = [s for s in all_stocks if s['代码'] not in seen and not seen.add(s['代码'])]
        all_stocks = unique[:250]
        log(f"  共{len(all_stocks)}只活跃股")
    except:
        all_stocks = []
    
    # 合并：潜力板块股 + 活跃股
    all_to_scan = sector_stocks + all_stocks
    seen = set()
    all_to_scan = [s for s in all_to_scan if s['代码'] not in seen and not seen.add(s['代码'])]
    
    log(f"\n[4] 开始扫描{len(all_to_scan)}只股票...")
    
    results = []
    lock = threading.Lock()
    counter = {'done': 0}
    
    def scan_stock(stock):
        code = stock['代码']
        name = stock['名称']
        sector = stock.get('所属板块', '')
        
        df = get_stock_data(code)
        if df is None:
            return None
        
        limit_up, limit_info = check_limit_up_washout(df)
        sideways, sideways_info = check_sideways_support(df)
        
        in_potential_sector = bool(sector)
        
        if not (limit_up or sideways or in_potential_sector):
            return None
        
        today = df.iloc[-1]
        today_change = (today['收盘'] - today['开盘']) / today['开盘'] * 100
        
        # 策略组合
        strategies = []
        if limit_up:
            strategies.append('涨停洗盘')
        if sideways:
            strategies.append('横盘托单')
        if in_potential_sector:
            strategies.append('板块异动')
        
        return {
            '代码': code,
            '名称': name,
            '策略': '+'.join(strategies),
            '组合数': len(strategies),
            '所属板块': sector,
            '现价': round(today['收盘'], 2),
            '今日涨幅': f"{today_change:+.2f}%",
            '涨停洗盘': limit_up,
            '横盘托单': sideways,
            '板块异动': in_potential_sector,
            '涨停信息': limit_info,
            '托单信息': sideways_info
        }
    
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = [executor.submit(scan_stock, s) for s in all_to_scan]
        for future in as_completed(futures):
            with lock:
                counter['done'] += 1
                if counter['done'] % 50 == 0:
                    log(f"  进度: {counter['done']}/{len(all_to_scan)}")
            result = future.result()
            if result:
                results.append(result)
    
    log(f"\n[5] 扫描完成，发现{len(results)}个信号")
    
    if not results:
        log("\n未发现符合条件的买点")
        return
    
    df = pd.DataFrame(results)
    df = df.sort_values(['组合数', '策略'], ascending=[False, True])
    
    # ===== 显示结果 =====
    log("\n" + "="*70)
    log("扫描结果")
    log("="*70)
    
    # 多策略共振
    multi = df[df['组合数'] >= 2]
    if len(multi) > 0:
        log(f"\n【多策略共振】({len(multi)}只) - 优先关注")
        log("-" * 60)
        for _, row in multi.iterrows():
            log(f"\n  {row['名称']}({row['代码']}) - {row['策略']}")
            log(f"    现价: {row['现价']}  今日: {row['今日涨幅']}")
            if row['所属板块']:
                log(f"    潜力板块: {row['所属板块']}")
            if row['涨停信息']:
                log(f"    涨停日{row['涨停信息']['涨停日期']} 距{row['涨停信息']['距离']}")
            if row['托单信息']:
                log(f"    支撑{row['托单信息']['支撑位']} {row['托单信息']['距支撑']}")
    
    # 涨停洗盘
    limit_only = df[(df['组合数'] == 1) & (df['涨停洗盘'] == True)]
    if len(limit_only) > 0:
        log(f"\n【涨停洗盘】({len(limit_only)}只)")
        log("-" * 60)
        for _, row in limit_only.head(8).iterrows():
            info = row['涨停信息']
            log(f"  {row['名称']}({row['代码']}) 现价{row['现价']} {row['今日涨幅']}")
            log(f"    涨停日{info['涨停日期']} 距{info['距离']}")
    
    # 横盘托单
    sideways_only = df[(df['组合数'] == 1) & (df['横盘托单'] == True)]
    if len(sideways_only) > 0:
        log(f"\n【横盘托单】({len(sideways_only)}只)")
        log("-" * 60)
        for _, row in sideways_only.head(8).iterrows():
            info = row['托单信息']
            log(f"  {row['名称']}({row['代码']}) 现价{row['现价']} {row['今日涨幅']}")
            log(f"    支撑{info['支撑位']} {info['距支撑']}")
    
    # 板块异动（纯板块）
    sector_only = df[(df['组合数'] == 1) & (df['板块异动'] == True)]
    if len(sector_only) > 0:
        log(f"\n【板块异动成分股】({len(sector_only)}只) - 潜力板块内的股票")
        log("-" * 60)
        for _, row in sector_only.head(8).iterrows():
            log(f"  {row['名称']}({row['代码']}) 现价{row['现价']} {row['今日涨幅']}")
            log(f"    所属: {row['所属板块']}")
    
    # 保存
    fname = f"三策略扫描V2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df.to_excel(fname, index=False)
    log(f"\n已保存: {fname}")
    
    # 总结
    log("\n" + "="*70)
    log("买点总结")
    log("="*70)
    log(f"""
发现 {len(results)} 个买点:
  - 多策略共振: {len(multi)} 只（最优先）
  - 涨停洗盘: {len(limit_only)} 只（收益最高）
  - 横盘托单: {len(sideways_only)} 只（信号稳定）
  - 板块异动: {len(sector_only)} 只（潜力板块成分股）

操作建议:
  1. 多策略共振信号最优
  2. 涨停洗盘收益潜力大
  3. 板块异动成分股需配合板块启动
  4. 统一止损 -5%
""")


if __name__ == "__main__":
    run_scan()
