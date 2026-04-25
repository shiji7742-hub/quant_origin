"""
三策略结合实时扫描：横盘托单 + 涨停破位洗盘 + 板块异动
找出当前买点
"""
import requests
import pandas as pd
import json
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

def log(msg):
    print(msg, flush=True)

for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    if key in os.environ:
        del os.environ[key]

session = requests.Session()
session.trust_env = False


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
        df['涨跌幅'] = df['收盘'].pct_change() * 100
        return df
    except:
        return None


def check_limit_up_washout(df):
    """涨停破位洗盘策略（检查最新一天）"""
    if len(df) < 35:
        return False, None
    
    idx = len(df) - 1
    today = df.iloc[idx]
    today_change = (today['收盘'] - today['开盘']) / today['开盘'] * 100
    
    # 今日需要是阳线（放宽到1%）
    if today_change < 1:
        return False, None
    
    # 寻找涨停板（30天内）
    limit_up_info = None
    for i in range(idx - 3, max(idx - 30, 0), -1):
        row = df.iloc[i]
        prev_close = df.iloc[i-1]['收盘'] if i > 0 else row['开盘']
        gain = (row['收盘'] - prev_close) / prev_close * 100
        
        is_limit_up = gain >= 9.5
        is_not_yizi = row['开盘'] < row['收盘'] * 0.99
        
        if is_limit_up and is_not_yizi:
            limit_up_info = {
                'idx': i,
                'date': row['日期'],
                'low': row['最低'],
                'close': row['收盘']
            }
            break
    
    if not limit_up_info:
        return False, None
    
    # 检查是否先创新高（排除）
    for i in range(limit_up_info['idx'] + 1, idx):
        if df.iloc[i]['最高'] > limit_up_info['close'] * 1.08:
            return False, None
    
    limit_low = limit_up_info['low']
    
    # 检查是否破位
    broke_low = False
    for i in range(limit_up_info['idx'] + 1, idx):
        if df.iloc[i]['最低'] < limit_low:
            broke_low = True
            break
    
    if not broke_low:
        return False, None
    
    # 今日收盘价站回涨停最低价上方（放宽条件：接近也算）
    distance_to_limit = (today['收盘'] - limit_low) / limit_low * 100
    if distance_to_limit < -3:  # 允许略低于涨停最低价
        return False, None
    
    return True, {
        '涨停日期': limit_up_info['date'].strftime('%Y-%m-%d'),
        '涨停最低': round(limit_low, 2),
        '距离涨停低': f"{distance_to_limit:+.1f}%",
        '今日涨幅': f"{today_change:+.1f}%"
    }


def check_sideways_support(df):
    """横盘托单策略（检查最新一天）"""
    if len(df) < 10:
        return False, None
    
    idx = len(df) - 1
    sideways_days = 3
    
    sideways_period = df.iloc[idx-sideways_days:idx]
    high = sideways_period['最高'].max()
    low = sideways_period['最低'].min()
    avg = sideways_period['收盘'].mean()
    
    sideways_volatility = (high - low) / avg * 100
    
    if sideways_volatility > 5.0:
        return False, None
    
    support = low
    today = df.iloc[idx]
    today_low = today['最低']
    today_close = today['收盘']
    
    distance_to_support = (today_low - support) / support * 100
    
    if not (-3.0 <= distance_to_support <= 0.5):
        return False, None
    
    support_held = today_low >= support * 0.98
    close_above_support = today_close > support * 1.001
    
    if not (support_held and close_above_support):
        return False, None
    
    return True, {
        '支撑位': round(support, 2),
        '横盘波动': f"{sideways_volatility:.1f}%",
        '距支撑': f"{distance_to_support:+.1f}%"
    }


def check_sector_surge(df):
    """板块异动策略（检查最新一天）"""
    if len(df) < 50:
        return False, None
    
    idx = len(df) - 1
    lookback = 45
    surge_threshold = 5.0
    
    # 找大涨日
    surge_found = False
    surge_idx = None
    surge_info = None
    
    for i in range(idx - 15, max(idx - lookback, 0), -1):
        if df.iloc[i]['涨跌幅'] > surge_threshold:
            surge_found = True
            surge_idx = i
            surge_info = {
                'date': df.iloc[i]['日期'],
                'gain': df.iloc[i]['涨跌幅']
            }
            break
        
        if i >= 3:
            gain_3d = ((df.iloc[i]['收盘'] / df.iloc[i-3]['收盘']) - 1) * 100
            if gain_3d > 10:
                surge_found = True
                surge_idx = i
                surge_info = {
                    'date': df.iloc[i]['日期'],
                    'gain': gain_3d
                }
                break
    
    if not surge_found:
        return False, None
    
    # 计算回撤
    after_surge = df.iloc[surge_idx:idx+1]
    high_after = after_surge['最高'].max()
    current_price = df.iloc[idx]['收盘']
    drawdown = (current_price - high_after) / high_after * 100
    
    # 回撤8-20%
    if drawdown > -8 or drawdown < -20:
        return False, None
    
    # 近10日横盘
    recent_10 = df.iloc[idx-9:idx+1]
    high_10 = recent_10['最高'].max()
    low_10 = recent_10['最低'].min()
    range_10 = (high_10 - low_10) / low_10 * 100
    
    if range_10 > 15:
        return False, None
    
    # 当前价格接近下沿
    dist_to_low = (current_price - low_10) / low_10 * 100
    if dist_to_low > 5:
        return False, None
    
    return True, {
        '爆发日期': surge_info['date'].strftime('%Y-%m-%d'),
        '爆发涨幅': f"+{surge_info['gain']:.1f}%",
        '回撤幅度': f"{drawdown:.1f}%",
        '距10日低': f"{dist_to_low:+.1f}%"
    }


def scan_stock(code, name):
    """扫描单只股票"""
    df = get_stock_data(code)
    if df is None:
        return None
    
    limit_up, limit_info = check_limit_up_washout(df)
    sideways, sideways_info = check_sideways_support(df)
    sector, sector_info = check_sector_surge(df)
    
    if not (limit_up or sideways or sector):
        return None
    
    combo_count = sum([limit_up, sideways, sector])
    
    if combo_count == 3:
        strategy = '三重共振'
    elif combo_count == 2:
        if limit_up and sideways:
            strategy = '涨停+托单'
        elif limit_up and sector:
            strategy = '涨停+异动'
        else:
            strategy = '托单+异动'
    else:
        if limit_up:
            strategy = '涨停洗盘'
        elif sideways:
            strategy = '横盘托单'
        else:
            strategy = '板块异动'
    
    today = df.iloc[-1]
    today_change = (today['收盘'] - today['开盘']) / today['开盘'] * 100
    
    result = {
        '代码': code,
        '名称': name,
        '策略': strategy,
        '组合数': combo_count,
        '现价': round(today['收盘'], 2),
        '今日涨幅': f"{today_change:+.2f}%",
        '涨停洗盘': limit_up,
        '横盘托单': sideways,
        '板块异动': sector
    }
    
    # 添加详细信息
    if limit_info:
        result.update({f'涨停_{k}': v for k, v in limit_info.items()})
    if sideways_info:
        result.update({f'托单_{k}': v for k, v in sideways_info.items()})
    if sector_info:
        result.update({f'异动_{k}': v for k, v in sector_info.items()})
    
    return result


def get_stock_list():
    """获取股票列表（成交额排名前300）"""
    try:
        url = 'https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData'
        stocks = []
        
        for node in ['hs_a', 'sz_a']:
            for page in range(1, 25):
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
                        
                        if 'ST' in name:
                            continue
                        if not (code.startswith('6') or code.startswith('00')):
                            continue
                        
                        stocks.append((code, name))
        
        seen = set()
        unique = [(c, n) for c, n in stocks if c not in seen and not seen.add(c)]
        return unique[:300]
    except:
        return []


def run_scan():
    """运行扫描"""
    log("="*70)
    log("三策略结合实时扫描")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*70)
    
    log("\n策略说明:")
    log("  1. 涨停洗盘：涨停后跌破最低价，今日阳线反包")
    log("  2. 横盘托单：横盘3天，今日触及支撑位守住")
    log("  3. 板块异动：大涨后回撤8-20%，近期横盘接近低点")
    
    log("\n[1] 获取股票列表...")
    stock_list = get_stock_list()
    log(f"  共{len(stock_list)}只主板股票")
    
    log("\n[2] 开始扫描...")
    results = []
    lock = threading.Lock()
    counter = {'done': 0}
    
    def process(args):
        code, name = args
        result = scan_stock(code, name)
        with lock:
            counter['done'] += 1
            if counter['done'] % 50 == 0:
                log(f"  进度: {counter['done']}/{len(stock_list)}")
        return result
    
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = [executor.submit(process, s) for s in stock_list]
        for future in as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
    
    log(f"\n[3] 扫描完成，发现{len(results)}个信号")
    
    if not results:
        log("\n未发现符合条件的买点")
        return
    
    df = pd.DataFrame(results)
    df = df.sort_values(['组合数', '策略'], ascending=[False, True])
    
    # ========== 显示结果 ==========
    log("\n" + "="*70)
    log("扫描结果（按策略组合数排序）")
    log("="*70)
    
    # 多策略共振
    multi = df[df['组合数'] >= 2]
    if len(multi) > 0:
        log(f"\n【多策略共振】({len(multi)}只) - 优先关注")
        log("-" * 60)
        for _, row in multi.iterrows():
            log(f"\n  {row['名称']}({row['代码']}) - {row['策略']}")
            log(f"    现价: {row['现价']}  今日: {row['今日涨幅']}")
            
            details = []
            if row['涨停洗盘']:
                details.append(f"涨停日{row.get('涨停_涨停日期', '')}, 距涨停低{row.get('涨停_距离涨停低', '')}")
            if row['横盘托单']:
                details.append(f"支撑{row.get('托单_支撑位', '')}, 距支撑{row.get('托单_距支撑', '')}")
            if row['板块异动']:
                details.append(f"回撤{row.get('异动_回撤幅度', '')}, 距低{row.get('异动_距10日低', '')}")
            
            for d in details:
                log(f"    {d}")
    
    # 涨停洗盘（单一）
    limit_only = df[(df['组合数'] == 1) & (df['涨停洗盘'] == True)]
    if len(limit_only) > 0:
        log(f"\n【涨停洗盘】({len(limit_only)}只) - 收益最高")
        log("-" * 60)
        for _, row in limit_only.head(10).iterrows():
            log(f"  {row['名称']}({row['代码']}) 现价{row['现价']} {row['今日涨幅']}")
            log(f"    涨停日{row.get('涨停_涨停日期', '')} 距涨停低{row.get('涨停_距离涨停低', '')}")
    
    # 横盘托单（单一）
    sideways_only = df[(df['组合数'] == 1) & (df['横盘托单'] == True)]
    if len(sideways_only) > 0:
        log(f"\n【横盘托单】({len(sideways_only)}只) - 信号稳定")
        log("-" * 60)
        for _, row in sideways_only.head(10).iterrows():
            log(f"  {row['名称']}({row['代码']}) 现价{row['现价']} {row['今日涨幅']}")
            log(f"    支撑{row.get('托单_支撑位', '')} 距支撑{row.get('托单_距支撑', '')}")
    
    # 板块异动（单一）
    sector_only = df[(df['组合数'] == 1) & (df['板块异动'] == True)]
    if len(sector_only) > 0:
        log(f"\n【板块异动】({len(sector_only)}只)")
        log("-" * 60)
        for _, row in sector_only.head(10).iterrows():
            log(f"  {row['名称']}({row['代码']}) 现价{row['现价']} {row['今日涨幅']}")
            log(f"    回撤{row.get('异动_回撤幅度', '')} 距低{row.get('异动_距10日低', '')}")
    
    # 保存结果
    fname = f"三策略扫描_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df.to_excel(fname, index=False)
    log(f"\n已保存: {fname}")
    
    # 总结
    log("\n" + "="*70)
    log("买点总结")
    log("="*70)
    
    log(f"""
发现 {len(results)} 个买点:
  - 多策略共振: {len(multi)} 只（优先关注）
  - 涨停洗盘: {len(limit_only)} 只（收益最高）
  - 横盘托单: {len(sideways_only)} 只（信号稳定）
  - 板块异动: {len(sector_only)} 只

操作建议:
  1. 优先选择多策略共振信号
  2. 涨停洗盘信号收益潜力大
  3. 统一止损 -5%
  4. 持仓周期 3-5 天
""")


if __name__ == "__main__":
    run_scan()
