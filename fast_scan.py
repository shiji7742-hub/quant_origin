"""快速扫描 - 带输出刷新"""
import requests
import pandas as pd
import json
import os
import sys
from datetime import datetime

# 强制刷新输出
def log(msg):
    print(msg, flush=True)

for key in ['HTTP_PROXY', 'HTTPS_PROXY', 'http_proxy', 'https_proxy']:
    if key in os.environ:
        del os.environ[key]

log("="*60)
log("快速全市场扫描")
log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
log("="*60)

session = requests.Session()
session.trust_env = False

# 获取股票列表
log("\n[1] 获取股票列表...")
stocks = []
try:
    url = 'https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData'
    for node in ['hs_a', 'sz_a']:
        for page in range(1, 15):  # 减少页数，加快速度
            params = {'page': page, 'num': 80, 'sort': 'amount', 'asc': 0, 'node': node}
            r = session.get(url, params=params, timeout=15)
            if r.text and r.text not in ['null', '[]']:
                data = json.loads(r.text)
                if not data:
                    break
                for item in data:
                    code = item.get('symbol', '')
                    name = item.get('name', '')
                    price = float(item.get('trade', 0) or 0)
                    if 'ST' in name or price < 3 or price > 80:
                        continue
                    if code.startswith('8') or code.startswith('4'):
                        continue
                    stocks.append({'code': code, 'name': name})
            else:
                break
        log(f"  {node}: 已获取 {len(stocks)} 只")
except Exception as e:
    log(f"  错误: {e}")

# 去重
seen = set()
unique = [s for s in stocks if s['code'] not in seen and not seen.add(s['code'])]
stocks = unique[:500]  # 只取前500只，加快速度
log(f"  筛选后: {len(stocks)} 只")

# 扫描
log("\n[2] 扫描信号...")
results = []

for i, stock in enumerate(stocks):
    code, name = stock['code'], stock['name']
    
    if (i+1) % 50 == 0:
        log(f"  进度: {i+1}/{len(stocks)} 找到{len(results)}个")
    
    try:
        # 获取K线
        if code.startswith('6'):
            kcode = f'sh{code}'
        else:
            kcode = f'sz{code}'
        
        url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={kcode},day,,,60,qfq'
        r = session.get(url, timeout=5)
        data = r.json()
        
        if not data.get('data'):
            continue
        stock_data = data['data'].get(kcode) or data['data'].get(kcode.upper())
        if not stock_data or 'qfqday' not in stock_data:
            continue
        
        days = stock_data['qfqday']
        if len(days) < 30:
            continue
        
        # 转DataFrame
        df = pd.DataFrame(days, columns=['日期','开盘','收盘','最高','最低','成交量'])
        for col in ['开盘','收盘','最高','最低','成交量']:
            df[col] = df[col].astype(float)
        
        df['MA5'] = df['收盘'].rolling(5).mean()
        df['MA10'] = df['收盘'].rolling(10).mean()
        df['MA20'] = df['收盘'].rolling(20).mean()
        df['VOL_MA5'] = df['成交量'].rolling(5).mean()
        
        latest = df.iloc[-1]
        if pd.isna(latest['MA20']):
            continue
        
        # 评分
        score = 0
        if latest['MA5'] > latest['MA10'] > latest['MA20']:
            score += 25
        if latest['成交量'] / latest['VOL_MA5'] > 1.2:
            score += 20
        if latest['收盘'] > latest['开盘']:
            score += 15
        if latest['收盘'] > latest['MA20']:
            score += 20
        
        box_high = df.iloc[-16:-1]['最高'].max()
        if latest['收盘'] > box_high:
            score += 20
        
        if score >= 60:
            vol_ratio = latest['成交量'] / latest['VOL_MA5']
            results.append({
                '代码': code,
                '名称': name,
                '收盘': latest['收盘'],
                '评分': score,
                '量比': f"{vol_ratio:.2f}",
                '日期': days[-1][0]
            })
            log(f"  ★ {code} {name} 评分{score}")
    
    except:
        pass

# 结果
log(f"\n[3] 扫描完成，找到 {len(results)} 个强信号")

if results:
    results.sort(key=lambda x: x['评分'], reverse=True)
    
    log("\n" + "="*60)
    log("【明日买点】")
    log("="*60)
    
    for r in results[:20]:
        log(f"  {r['代码']} {r['名称']:<8} {r['收盘']:>7.2f} 评分{r['评分']} 量比{r['量比']}")
    
    if len(results) > 20:
        log(f"  ... 共{len(results)}只")
    
    # 保存
    df = pd.DataFrame(results)
    fname = f"快速扫描_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df.to_excel(fname, index=False)
    log(f"\n已保存: {fname}")
