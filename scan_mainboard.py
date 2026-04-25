"""仅扫描主板股票（排除创业板和科创板）"""
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

log("="*60)
log("主板股票扫描（排除创业板/科创板）")
log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
log("="*60)

session = requests.Session()
session.trust_env = False

# 获取股票列表
log("\n[1] 获取股票列表...")
stocks = []
url = 'https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData'
for node in ['hs_a', 'sz_a']:
    for page in range(1, 30):
        params = {'page': page, 'num': 80, 'sort': 'amount', 'asc': 0, 'node': node}
        try:
            r = session.get(url, params=params, timeout=15)
            if r.text and r.text not in ['null', '[]']:
                data = json.loads(r.text)
                if not data:
                    break
                for item in data:
                    symbol = item.get('symbol', '')
                    name = item.get('name', '')
                    price = float(item.get('trade', 0) or 0)
                    
                    if symbol.startswith('sh') or symbol.startswith('sz'):
                        code = symbol[2:]
                        kcode = symbol
                    else:
                        code = symbol
                        if symbol.startswith('6'):
                            kcode = f'sh{symbol}'
                        else:
                            kcode = f'sz{symbol}'
                    
                    # 主板筛选：排除创业板(30)、科创板(68)、北交所(8/4)
                    if code.startswith('3') or code.startswith('68'):
                        continue  # 排除创业板和科创板
                    if code.startswith('8') or code.startswith('4'):
                        continue  # 排除北交所
                    
                    if 'ST' in name or price < 3 or price > 200:
                        continue
                    
                    stocks.append({'code': code, 'name': name, 'kcode': kcode})
            else:
                break
        except:
            break

seen = set()
unique = [s for s in stocks if s['code'] not in seen and not seen.add(s['code'])]
stocks = unique[:1500]
log(f"  筛选后: {len(stocks)} 只主板股票")

# 扫描
log("\n[2] 扫描信号...")
results = []

for i, stock in enumerate(stocks):
    code, name, kcode = stock['code'], stock['name'], stock['kcode']
    
    if (i+1) % 100 == 0:
        log(f"  进度: {i+1}/{len(stocks)} 找到{len(results)}个")
    
    try:
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
        
        if len(days[0]) == 6:
            df = pd.DataFrame(days, columns=['日期','开盘','收盘','最高','最低','成交量'])
        else:
            df = pd.DataFrame([d[:6] for d in days], columns=['日期','开盘','收盘','最高','最低','成交量'])
        
        for col in ['开盘','收盘','最高','最低','成交量']:
            df[col] = df[col].astype(float)
        
        df['MA5'] = df['收盘'].rolling(5).mean()
        df['MA10'] = df['收盘'].rolling(10).mean()
        df['MA20'] = df['收盘'].rolling(20).mean()
        df['VOL_MA5'] = df['成交量'].rolling(5).mean()
        
        latest = df.iloc[-1]
        if pd.isna(latest['MA20']):
            continue
        
        score = 0
        signals = []
        
        if latest['MA5'] > latest['MA10'] > latest['MA20']:
            score += 25
            signals.append('多头')
        
        vol_ratio = latest['成交量'] / latest['VOL_MA5'] if latest['VOL_MA5'] > 0 else 0
        if vol_ratio > 1.2:
            score += 20
            signals.append('放量')
        
        if latest['收盘'] > latest['开盘']:
            score += 15
            signals.append('收阳')
        
        if latest['收盘'] > latest['MA20']:
            score += 15
            signals.append('>MA20')
        
        box_high = df.iloc[-16:-1]['最高'].max()
        if latest['收盘'] > box_high:
            score += 20
            signals.append('突破')
        
        if score >= 40:
            # 标记板块
            if code.startswith('6'):
                board = '沪主板'
            elif code.startswith('00') or code.startswith('001'):
                board = '深主板'
            elif code.startswith('002'):
                board = '中小板'
            else:
                board = '其他'
            
            results.append({
                '代码': code,
                '名称': name,
                '板块': board,
                '收盘': latest['收盘'],
                '评分': score,
                '量比': f"{vol_ratio:.2f}",
                '信号': '+'.join(signals),
                '日期': days[-1][0]
            })
    
    except:
        pass

log(f"\n[3] 扫描完成，找到 {len(results)} 个信号(≥40分)")

if results:
    results.sort(key=lambda x: x['评分'], reverse=True)
    
    log("\n" + "="*60)
    log("【主板明日买点】")
    log("="*60)
    
    strong = [r for r in results if r['评分'] >= 60]
    medium = [r for r in results if 50 <= r['评分'] < 60]
    weak = [r for r in results if 40 <= r['评分'] < 50]
    
    if strong:
        log(f"\n★★★ 强信号(≥60分): {len(strong)}只")
        for r in strong[:25]:
            log(f"  {r['代码']} {r['名称']:<8} [{r['板块']}] {r['收盘']:>7.2f} 评分{r['评分']} {r['信号']}")
    
    if medium:
        log(f"\n★★ 中等信号(50-59分): {len(medium)}只")
        for r in medium[:20]:
            log(f"  {r['代码']} {r['名称']:<8} [{r['板块']}] {r['收盘']:>7.2f} 评分{r['评分']} {r['信号']}")
    
    if weak:
        log(f"\n★ 观望信号(40-49分): {len(weak)}只")
        for r in weak[:15]:
            log(f"  {r['代码']} {r['名称']:<8} [{r['板块']}] {r['收盘']:>7.2f} 评分{r['评分']} {r['信号']}")
    
    df = pd.DataFrame(results)
    fname = f"主板扫描_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df.to_excel(fname, index=False)
    log(f"\n已保存: {fname}")
else:
    log("\n市场整体偏弱，无符合条件的主板股票")
