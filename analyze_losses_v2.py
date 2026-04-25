"""分析横盘托单策略亏损案例 v2"""
import pandas as pd
import requests
import json
import os
from datetime import datetime
import glob

def log(msg):
    print(msg, flush=True)

for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    if key in os.environ:
        del os.environ[key]

session = requests.Session()
session.trust_env = False


def get_stock_data(code):
    """获取K线数据"""
    try:
        # 确保代码格式正确
        code = str(code).zfill(6)
        
        if code.startswith('6'):
            kcode = f'sh{code}'
        else:
            kcode = f'sz{code}'
        
        url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={kcode},day,,,250,qfq'
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
    except Exception as e:
        return None


# 读取回测结果
log("="*60)
log("分析横盘托单策略亏损案例")
log("="*60)

files = glob.glob('横盘托单回测_*.xlsx')
if not files:
    log("未找到回测结果文件")
    exit()

latest_file = max(files, key=os.path.getmtime)
log(f"\n读取: {latest_file}")

df = pd.read_excel(latest_file)
log(f"总交易数: {len(df)}")

# 确保代码列是字符串
df['代码'] = df['代码'].astype(str).str.zfill(6)

# 亏损程度分布
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

# 分析亏损最严重的案例
log("\n" + "="*60)
log("5日亏损最严重的15个案例详情")
log("="*60)

worst = df.nsmallest(15, '5日收益')

loss_reasons = {
    '跳空低开': 0,
    '跌破支撑': 0,
    '持续下跌': 0,
    '正常回调': 0
}

for idx, (_, row) in enumerate(worst.iterrows(), 1):
    code = str(row['代码']).zfill(6)
    name = row['名称']
    signal_date = pd.to_datetime(row['日期'])
    buy_price = row['买入价']
    
    stock_df = get_stock_data(code)
    
    if stock_df is None:
        log(f"\n{idx}. {name}({code}) - {signal_date.strftime('%Y-%m-%d')}")
        log(f"   5日收益: {row['5日收益']:+.2f}%  最大回撤: {row['最大回撤']:+.2f}%")
        log(f"   (无法获取详细数据)")
        continue
    
    # 找到信号日
    signal_idx = stock_df[stock_df['日期'] == signal_date].index
    if len(signal_idx) == 0:
        # 尝试模糊匹配
        signal_idx = stock_df[stock_df['日期'].dt.strftime('%Y-%m-%d') == signal_date.strftime('%Y-%m-%d')].index
        if len(signal_idx) == 0:
            log(f"\n{idx}. {name}({code}) - {signal_date.strftime('%Y-%m-%d')}")
            log(f"   5日收益: {row['5日收益']:+.2f}%")
            log(f"   (找不到信号日)")
            continue
    
    signal_idx = signal_idx[0]
    
    # 分析数据
    signal_day = stock_df.iloc[signal_idx]
    
    # 前5天数据
    pre_start = max(0, signal_idx - 5)
    pre_data = stock_df.iloc[pre_start:signal_idx]
    
    # 后5天数据
    post_end = min(len(stock_df), signal_idx + 6)
    post_data = stock_df.iloc[signal_idx:post_end]
    
    if len(post_data) < 2:
        continue
    
    # 分析
    # 1. 次日跳空
    next_day = post_data.iloc[1] if len(post_data) > 1 else None
    if next_day is not None:
        gap = (next_day['开盘'] - signal_day['收盘']) / signal_day['收盘'] * 100
        day1_change = (next_day['收盘'] - signal_day['收盘']) / signal_day['收盘'] * 100
    else:
        gap = 0
        day1_change = 0
    
    # 2. 支撑位
    support = row['支撑位']
    if len(post_data) >= 2:
        post_low = post_data.iloc[1:]['最低'].min()
        broke_support = post_low < support * 0.98
    else:
        broke_support = False
    
    # 3. 前期趋势
    if len(pre_data) >= 3:
        pre_change = (pre_data.iloc[-1]['收盘'] - pre_data.iloc[0]['收盘']) / pre_data.iloc[0]['收盘'] * 100
    else:
        pre_change = 0
    
    # 判断原因
    if gap < -3:
        reason = '跳空低开'
    elif broke_support:
        reason = '跌破支撑'
    elif pre_change < -5:
        reason = '持续下跌'
    else:
        reason = '正常回调'
    
    loss_reasons[reason] = loss_reasons.get(reason, 0) + 1
    
    log(f"\n{idx}. {name}({code}) - {signal_date.strftime('%Y-%m-%d')}")
    log(f"   买入价: {buy_price:.2f}  支撑位: {support:.2f}")
    log(f"   5日收益: {row['5日收益']:+.2f}%  最大回撤: {row['最大回撤']:+.2f}%")
    log(f"   次日跳空: {gap:+.2f}%  次日涨跌: {day1_change:+.2f}%")
    log(f"   跌破支撑: {'是' if broke_support else '否'}")
    log(f"   ★ 亏损原因: {reason}")
    
    # 显示后续走势
    log(f"   后续走势:")
    for i, (_, day) in enumerate(post_data.iterrows()):
        if i == 0:
            continue
        chg = (day['收盘'] - buy_price) / buy_price * 100
        log(f"     第{i}天: {day['日期'].strftime('%m-%d')} 开{day['开盘']:.2f} 收{day['收盘']:.2f} ({chg:+.1f}%)")

# 统计亏损原因
log("\n" + "="*60)
log("亏损原因统计（严重亏损案例）")
log("="*60)

total = sum(loss_reasons.values())
if total > 0:
    for reason, count in sorted(loss_reasons.items(), key=lambda x: -x[1]):
        pct = count / total * 100
        log(f"  {reason}: {count}个 ({pct:.0f}%)")

# 改进建议
log("\n" + "="*60)
log("策略改进建议")
log("="*60)
log("""
根据亏损案例分析，建议以下改进：

1. 【止损机制】
   - 跌破支撑位2%立即止损
   - 设置最大止损线-5%

2. 【过滤条件】
   - 增加MA20判断，价格需在MA20上方
   - 前5日不能有超过-5%的大跌
   - 排除近期有利空消息的股票

3. 【跳空应对】
   - 次日开盘跳空低开>2%时不追加
   - 考虑分批建仓降低风险

4. 【仓位控制】
   - 单只股票不超过总仓位15%
   - 同板块股票不超过30%

5. 【时机选择】
   - 避开财报披露前后3天
   - 大盘弱势时减少操作
""")
