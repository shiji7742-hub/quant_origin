"""
横盘托单策略回测 - 使用腾讯接口
基于日线数据识别横盘+反弹模式
"""
import requests
import pandas as pd
import json
import os
from datetime import datetime, timedelta

def log(msg):
    print(msg, flush=True)

# 清除代理
for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    if key in os.environ:
        del os.environ[key]

session = requests.Session()
session.trust_env = False


def get_stock_data(code, days=250):
    """从腾讯获取K线数据"""
    try:
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
        
        # 处理列数
        if len(days_data[0]) >= 6:
            df = pd.DataFrame([d[:6] for d in days_data], 
                            columns=['日期','开盘','收盘','最高','最低','成交量'])
        else:
            return None
        
        for col in ['开盘','收盘','最高','最低','成交量']:
            df[col] = df[col].astype(float)
        
        df['日期'] = pd.to_datetime(df['日期'])
        return df
        
    except:
        return None


def check_sideways_pattern(df, idx, sideways_days=3, sideways_range=5.0, support_test_range=3.0):
    """
    检查横盘托单模式
    
    模式：
    1. 前N天横盘（波动小于sideways_range%）
    2. 某天测试支撑位（下探到支撑附近）
    3. 守住支撑并反弹
    """
    if idx < sideways_days + 1 or idx >= len(df) - 3:
        return None
    
    # 1. 检查横盘期
    sideways_period = df.iloc[idx-sideways_days:idx]
    high = sideways_period['最高'].max()
    low = sideways_period['最低'].min()
    avg = sideways_period['收盘'].mean()
    
    sideways_volatility = (high - low) / avg * 100
    
    if sideways_volatility > sideways_range:
        return None
    
    support = low
    
    # 2. 检查当天是否测试支撑
    today = df.iloc[idx]
    today_low = today['最低']
    today_close = today['收盘']
    today_open = today['开盘']
    
    distance_to_support = (today_low - support) / support * 100
    
    if not (-support_test_range <= distance_to_support <= 0.5):
        return None
    
    # 3. 检查是否守住支撑
    support_held = today_low >= support * 0.98
    close_above_support = today_close > support * 1.001
    
    if not (support_held and close_above_support):
        return None
    
    # 4. 检查后续走势
    future_data = df.iloc[idx+1:idx+6]
    if len(future_data) < 1:
        return None
    
    return {
        'signal_date': today['日期'],
        'signal_price': today_close,
        'support': support,
        'distance': distance_to_support,
        'sideways_volatility': sideways_volatility,
        'sideways_high': high,
        'sideways_low': low,
        'today_low': today_low,
        'future_data': future_data
    }


def backtest_stock(code, name):
    """回测单只股票"""
    df = get_stock_data(code, 250)
    if df is None:
        return []
    
    trades = []
    sideways_days = 3
    sideways_range = 5.0  # 日线级别波动5%
    
    for i in range(sideways_days + 1, len(df) - 5):
        signal = check_sideways_pattern(df, i, sideways_days, sideways_range)
        
        if signal:
            buy_price = signal['signal_price']
            buy_date = signal['signal_date']
            future_data = signal['future_data']
            
            # 计算收益
            returns = {}
            for hold_days in [1, 3, 5]:
                if hold_days <= len(future_data):
                    sell_price = future_data.iloc[hold_days-1]['收盘']
                    returns[f'{hold_days}日'] = (sell_price - buy_price) / buy_price * 100
            
            max_price = future_data['最高'].max()
            max_return = (max_price - buy_price) / buy_price * 100
            
            min_price = future_data['最低'].min()
            max_drawdown = (min_price - buy_price) / buy_price * 100
            
            trades.append({
                '代码': code,
                '名称': name,
                '日期': buy_date.strftime('%Y-%m-%d'),
                '买入价': buy_price,
                '支撑位': signal['support'],
                '距支撑': signal['distance'],
                '横盘波动': signal['sideways_volatility'],
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
                        if code.startswith('8') or code.startswith('4') or code.startswith('68'):
                            continue
                        
                        stocks.append((code, name))
        
        seen = set()
        unique = [(c, n) for c, n in stocks if c not in seen and not seen.add(c)]
        return unique[:150]
        
    except Exception as e:
        log(f"获取股票列表失败: {e}")
        return [
            ('600519', '贵州茅台'), ('000858', '五粮液'), ('600036', '招商银行'),
            ('601318', '中国平安'), ('000001', '平安银行'), ('600000', '浦发银行'),
            ('000333', '美的集团'), ('000651', '格力电器'), ('002594', '比亚迪'),
            ('600887', '伊利股份'), ('000568', '泸州老窖'), ('002415', '海康威视'),
            ('600031', '三一重工'), ('000002', '万科A'), ('600030', '中信证券')
        ]


def run_backtest():
    """运行回测"""
    log("="*60)
    log("横盘托单策略回测")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*60)
    
    log("\n策略逻辑:")
    log("  1. 识别3天以上的横盘（波动<5%）")
    log("  2. 价格下探到支撑位附近")
    log("  3. 守住支撑并收盘在支撑上方")
    log("  4. 统计后续1/3/5日收益")
    
    log("\n[1] 获取股票列表...")
    stock_list = get_stock_list()
    log(f"  共{len(stock_list)}只股票")
    
    log("\n[2] 开始回测...")
    all_trades = []
    
    for i, (code, name) in enumerate(stock_list):
        if (i+1) % 10 == 0:
            log(f"  进度: {i+1}/{len(stock_list)}")
        
        trades = backtest_stock(code, name)
        if trades:
            all_trades.extend(trades)
            log(f"  ✓ {name}({code}): {len(trades)}个信号")
    
    log(f"\n[3] 回测完成，共{len(all_trades)}个交易信号")
    
    if not all_trades:
        log("\n未发现符合条件的信号")
        return
    
    df = pd.DataFrame(all_trades)
    
    # 统计结果
    log("\n" + "="*60)
    log("回测结果统计")
    log("="*60)
    
    log(f"\n交易统计:")
    log(f"  总信号数: {len(df)}")
    log(f"  涉及股票: {df['代码'].nunique()}只")
    
    log(f"\n收益统计:")
    for period in ['1日收益', '3日收益', '5日收益']:
        avg_return = df[period].mean()
        win_rate = (df[period] > 0).sum() / len(df) * 100
        max_r = df[period].max()
        min_r = df[period].min()
        
        log(f"\n  {period}:")
        log(f"    平均: {avg_return:+.2f}%  胜率: {win_rate:.1f}%")
        log(f"    最高: {max_r:+.2f}%  最低: {min_r:+.2f}%")
    
    log(f"\n极值统计:")
    log(f"  平均最高收益: {df['最高收益'].mean():+.2f}%")
    log(f"  平均最大回撤: {df['最大回撤'].mean():+.2f}%")
    
    # 保存结果
    fname = f"横盘托单回测_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df.to_excel(fname, index=False)
    log(f"\n已保存: {fname}")
    
    # 显示最佳案例
    log("\n" + "="*60)
    log("最佳案例（按5日收益排序）")
    log("="*60)
    
    top = df.nlargest(min(15, len(df)), '5日收益')
    for idx, (_, row) in enumerate(top.iterrows(), 1):
        log(f"\n{idx}. {row['名称']}({row['代码']}) - {row['日期']}")
        log(f"   买入: {row['买入价']:.2f}  支撑: {row['支撑位']:.2f}  距离: {row['距支撑']:.2f}%")
        log(f"   收益: 1日{row['1日收益']:+.2f}% | 3日{row['3日收益']:+.2f}% | 5日{row['5日收益']:+.2f}%")
        log(f"   最高: {row['最高收益']:+.2f}%  回撤: {row['最大回撤']:+.2f}%")


if __name__ == "__main__":
    run_backtest()
