"""
检查近几日横盘托单信号的胜率
回溯过去5-10天发出的信号，看后续表现
"""
import requests
import pandas as pd
import json
import os
from datetime import datetime, timedelta

def log(msg):
    print(msg, flush=True)

for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    if key in os.environ:
        del os.environ[key]

session = requests.Session()
session.trust_env = False


def get_stock_data(code, days=60):
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
        if len(days_data) < 20:
            return None
        
        df = pd.DataFrame([d[:6] for d in days_data], 
                        columns=['日期','开盘','收盘','最高','最低','成交量'])
        for col in ['开盘','收盘','最高','最低','成交量']:
            df[col] = df[col].astype(float)
        df['日期'] = pd.to_datetime(df['日期'])
        return df
    except:
        return None


def check_sideways_at_idx(df, idx):
    """检查指定日期是否有横盘托单信号"""
    if idx < 4 or idx >= len(df):
        return False
    
    sideways_period = df.iloc[idx-3:idx]
    high = sideways_period['最高'].max()
    low = sideways_period['最低'].min()
    avg = sideways_period['收盘'].mean()
    
    volatility = (high - low) / avg * 100
    if volatility > 5.0:
        return False
    
    support = low
    today = df.iloc[idx]
    distance = (today['最低'] - support) / support * 100
    
    if not (-3.0 <= distance <= 0.5):
        return False
    
    if today['最低'] < support * 0.98:
        return False
    if today['收盘'] <= support * 1.001:
        return False
    
    return True


def get_stock_list():
    """获取活跃股票列表"""
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
                        if 'ST' in name or not (code.startswith('6') or code.startswith('00')):
                            continue
                        stocks.append((code, name))
        
        seen = set()
        unique = [(c, n) for c, n in stocks if c not in seen and not seen.add(c)]
        return unique[:200]
    except:
        return []


def analyze_recent_signals():
    """分析近期信号的表现"""
    log("="*70)
    log("近期横盘托单信号胜率分析")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*70)
    
    log("\n[1] 获取股票列表...")
    stock_list = get_stock_list()
    log(f"  共{len(stock_list)}只股票")
    
    log("\n[2] 扫描近10个交易日的信号...")
    
    all_signals = []
    
    for i, (code, name) in enumerate(stock_list):
        if (i+1) % 50 == 0:
            log(f"  进度: {i+1}/{len(stock_list)}")
        
        df = get_stock_data(code)
        if df is None or len(df) < 15:
            continue
        
        # 检查最近10个交易日（不包括今天）
        for days_ago in range(1, 11):
            idx = len(df) - 1 - days_ago
            if idx < 5:
                continue
            
            if check_sideways_at_idx(df, idx):
                signal_date = df.iloc[idx]['日期']
                buy_price = df.iloc[idx]['收盘']
                
                # 计算后续收益
                future_days = min(days_ago, 5)  # 实际已过的天数
                if idx + future_days < len(df):
                    future_data = df.iloc[idx+1:idx+1+future_days]
                    
                    returns = {}
                    for hold in [1, 2, 3]:
                        if hold <= len(future_data):
                            sell_price = future_data.iloc[hold-1]['收盘']
                            returns[f'{hold}日'] = (sell_price - buy_price) / buy_price * 100
                    
                    if len(future_data) > 0:
                        max_price = future_data['最高'].max()
                        min_price = future_data['最低'].min()
                        max_return = (max_price - buy_price) / buy_price * 100
                        max_dd = (min_price - buy_price) / buy_price * 100
                    else:
                        max_return = 0
                        max_dd = 0
                    
                    all_signals.append({
                        '代码': code,
                        '名称': name,
                        '信号日期': signal_date.strftime('%Y-%m-%d'),
                        '买入价': round(buy_price, 2),
                        '1日收益': returns.get('1日', None),
                        '2日收益': returns.get('2日', None),
                        '3日收益': returns.get('3日', None),
                        '最高收益': round(max_return, 2),
                        '最大回撤': round(max_dd, 2),
                        '已过天数': days_ago
                    })
    
    log(f"\n[3] 分析完成，共{len(all_signals)}个信号")
    
    if not all_signals:
        log("\n未发现信号")
        return
    
    df = pd.DataFrame(all_signals)
    
    # 按日期分组统计
    log("\n" + "="*70)
    log("按信号日期统计")
    log("="*70)
    
    log(f"\n{'日期':^12} {'信号数':>6} {'1日胜率':>10} {'1日收益':>10} {'最高':>8} {'回撤':>8}")
    log("-" * 60)
    
    for date in sorted(df['信号日期'].unique(), reverse=True):
        day_df = df[df['信号日期'] == date]
        count = len(day_df)
        
        valid_1d = day_df['1日收益'].dropna()
        if len(valid_1d) > 0:
            wr_1d = (valid_1d > 0).sum() / len(valid_1d) * 100
            avg_1d = valid_1d.mean()
        else:
            wr_1d = 0
            avg_1d = 0
        
        avg_max = day_df['最高收益'].mean()
        avg_dd = day_df['最大回撤'].mean()
        
        log(f"{date:^12} {count:>6} {wr_1d:>9.1f}% {avg_1d:>+9.2f}% {avg_max:>+7.2f}% {avg_dd:>+7.2f}%")
    
    # 总体统计
    log("\n" + "="*70)
    log("总体统计")
    log("="*70)
    
    for period in ['1日收益', '2日收益', '3日收益']:
        valid = df[period].dropna()
        if len(valid) > 0:
            wr = (valid > 0).sum() / len(valid) * 100
            avg = valid.mean()
            median = valid.median()
            log(f"\n{period}: {len(valid)}个信号")
            log(f"  胜率: {wr:.1f}%")
            log(f"  平均收益: {avg:+.2f}%")
            log(f"  中位数: {median:+.2f}%")
    
    log(f"\n平均最高收益: {df['最高收益'].mean():+.2f}%")
    log(f"平均最大回撤: {df['最大回撤'].mean():+.2f}%")
    
    # 最佳案例
    log("\n" + "="*70)
    log("最佳案例（1日收益最高）")
    log("="*70)
    
    valid_df = df[df['1日收益'].notna()].nlargest(10, '1日收益')
    for _, row in valid_df.iterrows():
        log(f"  {row['名称']}({row['代码']}) {row['信号日期']} 1日{row['1日收益']:+.2f}%")
    
    # 最差案例
    log("\n【最差案例】")
    worst = df[df['1日收益'].notna()].nsmallest(5, '1日收益')
    for _, row in worst.iterrows():
        log(f"  {row['名称']}({row['代码']}) {row['信号日期']} 1日{row['1日收益']:+.2f}%")
    
    # 保存
    fname = f"横盘托单近期分析_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df.to_excel(fname, index=False)
    log(f"\n已保存: {fname}")


if __name__ == "__main__":
    analyze_recent_signals()
