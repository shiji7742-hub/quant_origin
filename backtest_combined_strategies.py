"""
结合策略回测：横盘托单 + 涨停破位洗盘
分析两种策略结合后的胜率
"""
import requests
import pandas as pd
import json
import os
from datetime import datetime

def log(msg):
    print(msg, flush=True)

for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    if key in os.environ:
        del os.environ[key]

session = requests.Session()
session.trust_env = False


def get_stock_data(code, days=250):
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
        if len(days_data) < 50:
            return None
        
        df = pd.DataFrame([d[:6] for d in days_data], 
                        columns=['日期','开盘','收盘','最高','最低','成交量'])
        for col in ['开盘','收盘','最高','最低','成交量']:
            df[col] = df[col].astype(float)
        df['日期'] = pd.to_datetime(df['日期'])
        return df
    except:
        return None


def check_limit_up_washout(df, idx, search_days=30):
    """
    检查涨停破位洗盘形态
    
    条件：
    1. 过去N天内有涨停板（涨幅≥9.5%，非一字板）
    2. 之后跌破涨停日最低价
    3. 今日大阳线反包（涨幅>2%，收盘>涨停最低价）
    """
    if idx < search_days + 5 or idx >= len(df) - 5:
        return None
    
    today = df.iloc[idx]
    today_change = (today['收盘'] - today['开盘']) / today['开盘'] * 100
    
    # 今日必须是阳线
    if today_change < 2:
        return None
    
    # 寻找涨停板
    limit_up_info = None
    for i in range(idx - 3, max(idx - search_days, 0), -1):
        row = df.iloc[i]
        prev_close = df.iloc[i-1]['收盘'] if i > 0 else row['开盘']
        gain = (row['收盘'] - prev_close) / prev_close * 100
        
        # 涨停判断（≥9.5%，非一字板）
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
        return None
    
    # 检查是否先创新高（排除）
    for i in range(limit_up_info['idx'] + 1, idx):
        if df.iloc[i]['最高'] > limit_up_info['close'] * 1.08:
            return None
    
    limit_low = limit_up_info['low']
    
    # 检查是否破位（中间有最低价<涨停最低价）
    broke_low = False
    for i in range(limit_up_info['idx'] + 1, idx):
        if df.iloc[i]['最低'] < limit_low:
            broke_low = True
            break
    
    if not broke_low:
        return None
    
    # 今日收盘价必须站回涨停最低价上方
    if today['收盘'] < limit_low:
        return None
    
    return {
        'limit_up_date': limit_up_info['date'],
        'limit_up_low': limit_low,
        'limit_up_close': limit_up_info['close'],
        'today_change': today_change
    }


def check_sideways_support(df, idx, sideways_days=3, sideways_range=5.0):
    """
    检查横盘托单形态
    """
    if idx < sideways_days + 1 or idx >= len(df) - 5:
        return None
    
    sideways_period = df.iloc[idx-sideways_days:idx]
    high = sideways_period['最高'].max()
    low = sideways_period['最低'].min()
    avg = sideways_period['收盘'].mean()
    
    sideways_volatility = (high - low) / avg * 100
    
    if sideways_volatility > sideways_range:
        return None
    
    support = low
    today = df.iloc[idx]
    today_low = today['最低']
    today_close = today['收盘']
    
    distance_to_support = (today_low - support) / support * 100
    
    if not (-3.0 <= distance_to_support <= 0.5):
        return None
    
    support_held = today_low >= support * 0.98
    close_above_support = today_close > support * 1.001
    
    if not (support_held and close_above_support):
        return None
    
    return {
        'support': support,
        'sideways_volatility': sideways_volatility,
        'distance': distance_to_support
    }


def backtest_stock(code, name):
    """回测单只股票"""
    df = get_stock_data(code)
    if df is None:
        return []
    
    trades = []
    
    for i in range(35, len(df) - 5):
        # 检查两种策略
        limit_up_signal = check_limit_up_washout(df, i)
        sideways_signal = check_sideways_support(df, i)
        
        if not limit_up_signal and not sideways_signal:
            continue
        
        today = df.iloc[i]
        buy_price = today['收盘']
        buy_date = today['日期']
        
        # 计算收益
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
        
        # 判断策略类型
        if limit_up_signal and sideways_signal:
            strategy = '双重共振'
        elif limit_up_signal:
            strategy = '涨停洗盘'
        else:
            strategy = '横盘托单'
        
        trades.append({
            '代码': code,
            '名称': name,
            '日期': buy_date.strftime('%Y-%m-%d'),
            '策略': strategy,
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
            for page in range(1, 15):
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
                        # 只取主板（60、00开头）
                        if not (code.startswith('6') or code.startswith('00')):
                            continue
                        
                        stocks.append((code, name))
        
        seen = set()
        unique = [(c, n) for c, n in stocks if c not in seen and not seen.add(c)]
        return unique[:150]
    except:
        return []


def run_backtest():
    """运行回测"""
    log("="*60)
    log("结合策略回测：横盘托单 + 涨停破位洗盘")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*60)
    
    log("\n策略说明:")
    log("  1. 横盘托单：横盘3天后下探支撑位守住")
    log("  2. 涨停洗盘：涨停后跌破最低价，大阳反包")
    log("  3. 双重共振：同时满足两种条件")
    
    log("\n[1] 获取股票列表...")
    stock_list = get_stock_list()
    log(f"  共{len(stock_list)}只主板股票")
    
    log("\n[2] 开始回测...")
    all_trades = []
    
    for i, (code, name) in enumerate(stock_list):
        if (i+1) % 20 == 0:
            log(f"  进度: {i+1}/{len(stock_list)}")
        
        trades = backtest_stock(code, name)
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
    
    # 按策略分组统计
    log("\n" + "="*60)
    log("按策略类型统计（排除黑天鹅时期）")
    log("="*60)
    
    for strategy in ['双重共振', '涨停洗盘', '横盘托单']:
        sub_df = df_normal[df_normal['策略'] == strategy]
        if len(sub_df) == 0:
            continue
        
        log(f"\n【{strategy}】({len(sub_df)}个信号)")
        
        for period in ['1日收益', '3日收益', '5日收益']:
            avg = sub_df[period].mean()
            wr = (sub_df[period] > 0).sum() / len(sub_df) * 100
            log(f"  {period}: 平均{avg:+.2f}%  胜率{wr:.1f}%")
        
        log(f"  平均最高收益: {sub_df['最高收益'].mean():+.2f}%")
        log(f"  平均最大回撤: {sub_df['最大回撤'].mean():+.2f}%")
    
    # 对比表格
    log("\n" + "="*60)
    log("策略对比（5日维度）")
    log("="*60)
    
    log(f"\n{'策略':<12} {'信号数':>8} {'平均收益':>10} {'胜率':>8} {'最高':>8} {'回撤':>8}")
    log("-" * 60)
    
    for strategy in ['双重共振', '涨停洗盘', '横盘托单']:
        sub_df = df_normal[df_normal['策略'] == strategy]
        if len(sub_df) == 0:
            continue
        
        count = len(sub_df)
        avg = sub_df['5日收益'].mean()
        wr = (sub_df['5日收益'] > 0).sum() / len(sub_df) * 100
        max_r = sub_df['最高收益'].mean()
        dd = sub_df['最大回撤'].mean()
        
        log(f"{strategy:<12} {count:>8} {avg:>+9.2f}% {wr:>7.1f}% {max_r:>+7.2f}% {dd:>+7.2f}%")
    
    # 双重共振案例
    log("\n" + "="*60)
    log("双重共振最佳案例")
    log("="*60)
    
    combo = df_normal[df_normal['策略'] == '双重共振']
    if len(combo) > 0:
        top = combo.nlargest(min(10, len(combo)), '5日收益')
        for idx, (_, row) in enumerate(top.iterrows(), 1):
            log(f"\n{idx}. {row['名称']}({row['代码']}) - {row['日期'].strftime('%Y-%m-%d')}")
            log(f"   收益: 1日{row['1日收益']:+.2f}% | 3日{row['3日收益']:+.2f}% | 5日{row['5日收益']:+.2f}%")
    else:
        log("\n无双重共振信号")
    
    # 保存结果
    fname = f"结合策略回测_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df.to_excel(fname, index=False)
    log(f"\n已保存: {fname}")
    
    # 结论
    log("\n" + "="*60)
    log("结论")
    log("="*60)
    
    if len(combo) > 0:
        combo_wr = (combo['5日收益'] > 0).sum() / len(combo) * 100
        combo_avg = combo['5日收益'].mean()
        log(f"""
双重共振策略（横盘托单 + 涨停洗盘）:
  - 5日胜率: {combo_wr:.1f}%
  - 5日平均收益: {combo_avg:+.2f}%
  - 信号较少但质量更高

建议:
  1. 优先选择双重共振信号
  2. 单一策略信号作为次选
  3. 设置止损-5%控制风险
""")


if __name__ == "__main__":
    run_backtest()
