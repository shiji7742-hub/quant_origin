"""分析横盘托单策略亏损案例"""
import pandas as pd
import requests
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
        df = pd.DataFrame([d[:6] for d in days_data], 
                        columns=['日期','开盘','收盘','最高','最低','成交量'])
        for col in ['开盘','收盘','最高','最低','成交量']:
            df[col] = df[col].astype(float)
        df['日期'] = pd.to_datetime(df['日期'])
        return df
    except:
        return None


def analyze_loss_case(code, name, signal_date, buy_price):
    """分析单个亏损案例"""
    df = get_stock_data(code)
    if df is None:
        return None
    
    # 找到信号日
    signal_date = pd.to_datetime(signal_date)
    idx = df[df['日期'] == signal_date].index
    if len(idx) == 0:
        return None
    idx = idx[0]
    
    # 前10天走势（看趋势）
    pre_data = df.iloc[max(0, idx-10):idx]
    
    # 后10天走势
    post_data = df.iloc[idx:min(len(df), idx+11)]
    
    # 分析前期趋势
    if len(pre_data) >= 5:
        pre_change = (pre_data.iloc[-1]['收盘'] - pre_data.iloc[0]['收盘']) / pre_data.iloc[0]['收盘'] * 100
        pre_trend = '上涨' if pre_change > 3 else ('下跌' if pre_change < -3 else '横盘')
    else:
        pre_change = 0
        pre_trend = '未知'
    
    # 分析后期走势
    if len(post_data) >= 6:
        day1_change = (post_data.iloc[1]['收盘'] - post_data.iloc[0]['收盘']) / post_data.iloc[0]['收盘'] * 100
        day5_low = post_data.iloc[1:6]['最低'].min()
        day5_change = (post_data.iloc[5]['收盘'] - post_data.iloc[0]['收盘']) / post_data.iloc[0]['收盘'] * 100
        max_drawdown = (day5_low - post_data.iloc[0]['收盘']) / post_data.iloc[0]['收盘'] * 100
    else:
        return None
    
    # 分析跳空情况
    gap_down = (post_data.iloc[1]['开盘'] - post_data.iloc[0]['收盘']) / post_data.iloc[0]['收盘'] * 100
    has_gap = gap_down < -2
    
    # 分析是否跌破支撑
    support = pre_data['最低'].min()
    broke_support = day5_low < support * 0.97
    
    return {
        '代码': code,
        '名称': name,
        '信号日': signal_date.strftime('%Y-%m-%d'),
        '买入价': buy_price,
        '前期趋势': pre_trend,
        '前期涨跌': f"{pre_change:+.1f}%",
        '次日跳空': f"{gap_down:+.1f}%" if has_gap else '无',
        '5日收益': f"{day5_change:+.1f}%",
        '最大回撤': f"{max_drawdown:+.1f}%",
        '跌破支撑': '是' if broke_support else '否',
        'post_data': post_data
    }


# 读取回测结果
log("="*60)
log("分析横盘托单策略亏损案例")
log("="*60)

# 获取最新的回测文件
import glob
files = glob.glob('横盘托单回测_*.xlsx')
if not files:
    log("未找到回测结果文件")
    exit()

latest_file = max(files, key=os.path.getmtime)
log(f"\n读取: {latest_file}")

df = pd.read_excel(latest_file)
log(f"总交易数: {len(df)}")

# 找出亏损最严重的案例
log("\n" + "="*60)
log("5日亏损最严重的20个案例")
log("="*60)

worst = df.nsmallest(20, '5日收益')

loss_reasons = {
    '跳空低开': 0,
    '跌破支撑': 0,
    '下跌趋势': 0,
    '正常波动': 0
}

for idx, (_, row) in enumerate(worst.iterrows(), 1):
    result = analyze_loss_case(row['代码'], row['名称'], row['日期'], row['买入价'])
    
    if result:
        log(f"\n{idx}. {result['名称']}({result['代码']}) - {result['信号日']}")
        log(f"   买入价: {result['买入价']:.2f}")
        log(f"   前期: {result['前期趋势']} ({result['前期涨跌']})")
        log(f"   次日跳空: {result['次日跳空']}")
        log(f"   5日收益: {result['5日收益']}")
        log(f"   最大回撤: {result['最大回撤']}")
        log(f"   跌破支撑: {result['跌破支撑']}")
        
        # 分析原因
        if '跳空' in result['次日跳空'] and float(result['次日跳空'].replace('%','').replace('+','')) < -3:
            reason = '跳空低开'
        elif result['跌破支撑'] == '是':
            reason = '跌破支撑'
        elif result['前期趋势'] == '下跌':
            reason = '下跌趋势'
        else:
            reason = '正常波动'
        
        log(f"   ★ 主要原因: {reason}")
        loss_reasons[reason] = loss_reasons.get(reason, 0) + 1
    else:
        log(f"\n{idx}. {row['名称']}({row['代码']}) - 无法获取数据")

# 统计亏损原因
log("\n" + "="*60)
log("亏损原因统计")
log("="*60)

for reason, count in sorted(loss_reasons.items(), key=lambda x: -x[1]):
    pct = count / sum(loss_reasons.values()) * 100 if sum(loss_reasons.values()) > 0 else 0
    log(f"  {reason}: {count}个 ({pct:.0f}%)")

# 按亏损程度分组统计
log("\n" + "="*60)
log("亏损程度分布")
log("="*60)

loss_df = df[df['5日收益'] < 0]
log(f"\n亏损交易总数: {len(loss_df)} ({len(loss_df)/len(df)*100:.1f}%)")

brackets = [
    (-5, 0, '轻微亏损(0~-5%)'),
    (-10, -5, '中等亏损(-5%~-10%)'),
    (-20, -10, '较大亏损(-10%~-20%)'),
    (-100, -20, '严重亏损(>-20%)')
]

for low, high, label in brackets:
    count = len(df[(df['5日收益'] > low) & (df['5日收益'] <= high)])
    pct = count / len(df) * 100
    log(f"  {label}: {count}个 ({pct:.1f}%)")

# 改进建议
log("\n" + "="*60)
log("策略改进建议")
log("="*60)
log("""
1. 【过滤下跌趋势】增加MA20判断，只在价格站上MA20时买入
2. 【设置止损】跌破支撑位2%立即止损
3. 【避开跳空】开盘跌幅>2%时不买入或减仓
4. 【仓位控制】单只股票不超过总仓位20%
5. 【时机选择】避开财报季、重大消息日
""")
