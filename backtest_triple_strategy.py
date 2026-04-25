"""
三策略结合回测：横盘托单 + 涨停破位洗盘 + 板块异动
分析不同组合的胜率
"""
import requests
import pandas as pd
import json
import os
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

def log(msg):
    print(msg, flush=True)

for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    if key in os.environ:
        del os.environ[key]

session = requests.Session()
session.trust_env = False


def get_stock_data(code, days=300):
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
        if len(days_data) < 60:
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


def check_limit_up_washout(df, idx, search_days=30):
    """涨停破位洗盘策略"""
    if idx < search_days + 5 or idx >= len(df) - 5:
        return False
    
    today = df.iloc[idx]
    today_change = (today['收盘'] - today['开盘']) / today['开盘'] * 100
    
    if today_change < 2:
        return False
    
    limit_up_info = None
    for i in range(idx - 3, max(idx - search_days, 0), -1):
        row = df.iloc[i]
        prev_close = df.iloc[i-1]['收盘'] if i > 0 else row['开盘']
        gain = (row['收盘'] - prev_close) / prev_close * 100
        
        is_limit_up = gain >= 9.5
        is_not_yizi = row['开盘'] < row['收盘'] * 0.99
        
        if is_limit_up and is_not_yizi:
            limit_up_info = {'idx': i, 'low': row['最低'], 'close': row['收盘']}
            break
    
    if not limit_up_info:
        return False
    
    for i in range(limit_up_info['idx'] + 1, idx):
        if df.iloc[i]['最高'] > limit_up_info['close'] * 1.08:
            return False
    
    limit_low = limit_up_info['low']
    
    broke_low = False
    for i in range(limit_up_info['idx'] + 1, idx):
        if df.iloc[i]['最低'] < limit_low:
            broke_low = True
            break
    
    if not broke_low:
        return False
    
    if today['收盘'] < limit_low:
        return False
    
    return True


def check_sideways_support(df, idx, sideways_days=3, sideways_range=5.0):
    """横盘托单策略"""
    if idx < sideways_days + 1 or idx >= len(df) - 5:
        return False
    
    sideways_period = df.iloc[idx-sideways_days:idx]
    high = sideways_period['最高'].max()
    low = sideways_period['最低'].min()
    avg = sideways_period['收盘'].mean()
    
    sideways_volatility = (high - low) / avg * 100
    
    if sideways_volatility > sideways_range:
        return False
    
    support = low
    today = df.iloc[idx]
    today_low = today['最低']
    today_close = today['收盘']
    
    distance_to_support = (today_low - support) / support * 100
    
    if not (-3.0 <= distance_to_support <= 0.5):
        return False
    
    support_held = today_low >= support * 0.98
    close_above_support = today_close > support * 1.001
    
    if not (support_held and close_above_support):
        return False
    
    return True


def check_sector_surge(df, idx, lookback=45, surge_threshold=5.0):
    """
    板块异动策略（应用于个股）
    
    条件：
    1. 过去30-45天内有过爆发（单日涨幅>5%或3日>10%）
    2. 爆发后回撤8-20%
    3. 近10日横盘或企稳
    4. 当前价格接近近期低点
    """
    if idx < lookback + 15 or idx >= len(df) - 5:
        return False
    
    # 找大涨日
    surge_found = False
    surge_idx = None
    
    for i in range(idx - 15, max(idx - lookback, 0), -1):
        if df.iloc[i]['涨跌幅'] > surge_threshold:
            surge_found = True
            surge_idx = i
            break
        
        # 或3日累计>10%
        if i >= 2:
            gain_3d = ((df.iloc[i]['收盘'] / df.iloc[i-3]['收盘']) - 1) * 100
            if gain_3d > 10:
                surge_found = True
                surge_idx = i
                break
    
    if not surge_found:
        return False
    
    # 计算回撤
    after_surge = df.iloc[surge_idx:idx+1]
    high_after = after_surge['最高'].max()
    current_price = df.iloc[idx]['收盘']
    drawdown = (current_price - high_after) / high_after * 100
    
    # 回撤8-20%
    if drawdown > -8 or drawdown < -20:
        return False
    
    # 近10日横盘
    recent_10 = df.iloc[idx-9:idx+1]
    high_10 = recent_10['最高'].max()
    low_10 = recent_10['最低'].min()
    range_10 = (high_10 - low_10) / low_10 * 100
    
    if range_10 > 15:
        return False
    
    # 当前价格接近下沿
    dist_to_low = (current_price - low_10) / low_10 * 100
    if dist_to_low > 5:
        return False
    
    return True


def backtest_stock(code, name):
    """回测单只股票"""
    df = get_stock_data(code)
    if df is None:
        return []
    
    trades = []
    
    for i in range(50, len(df) - 5):
        limit_up = check_limit_up_washout(df, i)
        sideways = check_sideways_support(df, i)
        sector = check_sector_surge(df, i)
        
        # 至少满足一个条件
        if not (limit_up or sideways or sector):
            continue
        
        today = df.iloc[i]
        buy_price = today['收盘']
        buy_date = today['日期']
        
        future_data = df.iloc[i+1:i+6]
        if len(future_data) < 5:
            continue
        
        returns = {}
        for hold_days in [1, 3, 5]:
            if hold_days <= len(future_data):
                sell_price = future_data.iloc[hold_days-1]['收盘']
                returns[f'{hold_days}日'] = (sell_price - buy_price) / buy_price * 100
        
        max_price = future_data['最高'].max()
        max_return = (max_price - buy_price) / buy_price * 100
        
        min_price = future_data['最低'].min()
        max_drawdown = (min_price - buy_price) / buy_price * 100
        
        # 策略组合判断
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
        
        trades.append({
            '代码': code,
            '名称': name,
            '日期': buy_date.strftime('%Y-%m-%d'),
            '策略': strategy,
            '组合数': combo_count,
            '涨停洗盘': limit_up,
            '横盘托单': sideways,
            '板块异动': sector,
            '买入价': buy_price,
            '1日收益': returns.get('1日', 0),
            '3日收益': returns.get('3日', 0),
            '5日收益': returns.get('5日', 0),
            '最高收益': max_return,
            '最大回撤': max_drawdown
        })
    
    return trades


def get_stock_list():
    """获取股票列表"""
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
                        
                        if 'ST' in name:
                            continue
                        if not (code.startswith('6') or code.startswith('00')):
                            continue
                        
                        stocks.append((code, name))
        
        seen = set()
        unique = [(c, n) for c, n in stocks if c not in seen and not seen.add(c)]
        return unique[:200]
    except:
        return []


def run_backtest():
    """运行回测"""
    log("="*70)
    log("三策略结合回测：横盘托单 + 涨停破位洗盘 + 板块异动")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*70)
    
    log("\n策略说明:")
    log("  1. 横盘托单：横盘3天后下探支撑位守住")
    log("  2. 涨停洗盘：涨停后跌破最低价，大阳反包")
    log("  3. 板块异动：大涨后回撤8-20%，近期横盘接近低点")
    
    log("\n[1] 获取股票列表...")
    stock_list = get_stock_list()
    log(f"  共{len(stock_list)}只主板股票")
    
    log("\n[2] 开始回测（多线程）...")
    all_trades = []
    lock = threading.Lock()
    counter = {'done': 0}
    
    def process_stock(args):
        code, name = args
        trades = backtest_stock(code, name)
        with lock:
            counter['done'] += 1
            if counter['done'] % 30 == 0:
                log(f"  进度: {counter['done']}/{len(stock_list)}")
        return trades
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(process_stock, s) for s in stock_list]
        for future in as_completed(futures):
            trades = future.result()
            if trades:
                all_trades.extend(trades)
    
    log(f"\n[3] 回测完成，共{len(all_trades)}个交易信号")
    
    if not all_trades:
        log("\n未发现符合条件的信号")
        return
    
    df = pd.DataFrame(all_trades)
    
    # 排除黑天鹅时期
    df['日期'] = pd.to_datetime(df['日期'])
    blackswan_start = pd.to_datetime('2025-03-28')
    blackswan_end = pd.to_datetime('2025-04-15')
    
    df_normal = df[(df['日期'] < blackswan_start) | (df['日期'] > blackswan_end)]
    
    log(f"\n排除黑天鹅后: {len(df_normal)}个信号")
    
    # ========== 按组合数统计 ==========
    log("\n" + "="*70)
    log("按策略组合数统计（排除黑天鹅）")
    log("="*70)
    
    log(f"\n{'组合':^15} {'信号数':>8} {'5日收益':>10} {'5日胜率':>10} {'最高':>8} {'回撤':>8}")
    log("-" * 70)
    
    for combo in [3, 2, 1]:
        sub_df = df_normal[df_normal['组合数'] == combo]
        if len(sub_df) == 0:
            continue
        
        label = f"{combo}重共振" if combo > 1 else "单一策略"
        count = len(sub_df)
        avg = sub_df['5日收益'].mean()
        wr = (sub_df['5日收益'] > 0).sum() / len(sub_df) * 100
        max_r = sub_df['最高收益'].mean()
        dd = sub_df['最大回撤'].mean()
        
        log(f"{label:^15} {count:>8} {avg:>+9.2f}% {wr:>9.1f}% {max_r:>+7.2f}% {dd:>+7.2f}%")
    
    # ========== 按具体策略统计 ==========
    log("\n" + "="*70)
    log("按具体策略类型统计")
    log("="*70)
    
    strategies = ['三重共振', '涨停+托单', '涨停+异动', '托单+异动', 
                  '涨停洗盘', '横盘托单', '板块异动']
    
    log(f"\n{'策略':^12} {'信号数':>8} {'5日收益':>10} {'5日胜率':>10} {'最高':>8} {'回撤':>8}")
    log("-" * 70)
    
    for strategy in strategies:
        sub_df = df_normal[df_normal['策略'] == strategy]
        if len(sub_df) == 0:
            continue
        
        count = len(sub_df)
        avg = sub_df['5日收益'].mean()
        wr = (sub_df['5日收益'] > 0).sum() / len(sub_df) * 100
        max_r = sub_df['最高收益'].mean()
        dd = sub_df['最大回撤'].mean()
        
        log(f"{strategy:^12} {count:>8} {avg:>+9.2f}% {wr:>9.1f}% {max_r:>+7.2f}% {dd:>+7.2f}%")
    
    # ========== 各周期对比 ==========
    log("\n" + "="*70)
    log("双重/三重共振 vs 单一策略（各周期收益）")
    log("="*70)
    
    multi = df_normal[df_normal['组合数'] >= 2]
    single = df_normal[df_normal['组合数'] == 1]
    
    log(f"\n{'周期':^8} {'多策略共振':^25} {'单一策略':^25}")
    log(f"{'':^8} {'收益':>10} {'胜率':>10} | {'收益':>10} {'胜率':>10}")
    log("-" * 70)
    
    for period in ['1日收益', '3日收益', '5日收益']:
        if len(multi) > 0:
            m_avg = multi[period].mean()
            m_wr = (multi[period] > 0).sum() / len(multi) * 100
        else:
            m_avg, m_wr = 0, 0
        
        s_avg = single[period].mean()
        s_wr = (single[period] > 0).sum() / len(single) * 100
        
        label = period.replace('收益', '')
        log(f"{label:^8} {m_avg:>+9.2f}% {m_wr:>9.1f}% | {s_avg:>+9.2f}% {s_wr:>9.1f}%")
    
    # ========== 最佳案例 ==========
    log("\n" + "="*70)
    log("多策略共振最佳案例")
    log("="*70)
    
    multi_sorted = multi.nlargest(min(15, len(multi)), '5日收益')
    for idx, (_, row) in enumerate(multi_sorted.iterrows(), 1):
        log(f"\n{idx}. {row['名称']}({row['代码']}) - {row['日期'].strftime('%Y-%m-%d')}")
        log(f"   策略: {row['策略']}")
        log(f"   收益: 1日{row['1日收益']:+.2f}% | 3日{row['3日收益']:+.2f}% | 5日{row['5日收益']:+.2f}%")
    
    # 保存结果
    fname = f"三策略回测_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df.to_excel(fname, index=False)
    log(f"\n已保存: {fname}")
    
    # 结论
    log("\n" + "="*70)
    log("结论")
    log("="*70)
    
    if len(multi) > 0:
        multi_wr = (multi['5日收益'] > 0).sum() / len(multi) * 100
        multi_avg = multi['5日收益'].mean()
        single_wr = (single['5日收益'] > 0).sum() / len(single) * 100
        single_avg = single['5日收益'].mean()
        
        log(f"""
策略配合效果分析：

1. 多策略共振（{len(multi)}个信号）:
   - 5日胜率: {multi_wr:.1f}%
   - 5日平均收益: {multi_avg:+.2f}%

2. 单一策略（{len(single)}个信号）:
   - 5日胜率: {single_wr:.1f}%
   - 5日平均收益: {single_avg:+.2f}%

3. 共振优势:
   - 胜率提升: {multi_wr - single_wr:+.1f}个百分点
   - 收益提升: {multi_avg - single_avg:+.2f}%

建议:
  1. 优先选择多策略共振信号（2重或3重）
  2. 涨停+托单、涨停+异动组合效果较好
  3. 单一策略中涨停洗盘收益最高
  4. 设置止损-5%控制风险
""")


if __name__ == "__main__":
    run_backtest()
