# -*- coding: utf-8 -*-
import requests
import json
import os
from datetime import datetime
try:
    import pandas as pd
    HAS_PANDAS = True
except:
    HAS_PANDAS = False

# 清理代理
for key in list(os.environ.keys()):
    if 'proxy' in key.lower():
        del os.environ[key]

session = requests.Session()
session.trust_env = False
session.headers.update({'User-Agent': 'Mozilla/5.0'})

def log(msg):
    print(msg)

log("="*60)
log("全市场扫描 - 筛选近期放量股票")
log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
log("="*60)

# 参数设置
days = 3
vol_ratio = 2.0
price_change = 1

log(f"\n筛选条件:")
log(f"  最近天数: {days}天")
log(f"  量比阈值: ≥{vol_ratio}倍")
log(f"  价格要求: 上涨")

# 获取股票列表
log("\n[1] 获取全市场股票列表...")
stocks = []
url = 'https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData'
max_pages = 50
for node in ['hs_a', 'sz_a']:
    for page in range(1, max_pages + 1):
        try:
            params_req = {'page': page, 'num': 80, 'sort': 'amount', 'asc': 0, 'node': node}
            r = session.get(url, params=params_req, timeout=10)
            if r.text and r.text not in ['null', '[]']:
                data = json.loads(r.text)
                if not data:
                    break
                for item in data:
                    # 使用 code 字段获取纯股票代码（不带市场前缀）
                    symbol = item.get('symbol', '')  # sh603980 格式
                    code = item.get('code', '')  # 603980 格式
                    if not code and symbol:
                        code = symbol[2:] if symbol.startswith(('sh', 'sz')) else symbol
                    
                    name = item.get('name', '')
                    price = float(item.get('trade', 0) or 0)
                    if 'ST' in name:
                        continue
                    if code.startswith('8') or code.startswith('4') or code.startswith('9'):
                        continue
                    if price < 3 or price > 100:
                        continue
                    stocks.append({'code': code, 'name': name, 'price': price})
            else:
                break
        except Exception as e:
            break
    if page % 10 == 0:
        log(f"  已获取 {len(stocks)} 只股票...")

# 去重
seen = set()
unique_stocks = []
for s in stocks:
    if s['code'] not in seen:
        seen.add(s['code'])
        unique_stocks.append(s)
stocks = unique_stocks
log(f"  去重后共 {len(stocks)} 只股票")

# 扫描放量股票
log(f"\n[2] 全市场扫描放量股票（量比≥{vol_ratio}倍）...")
results = []
for i, stock in enumerate(stocks):
    code = stock['code']
    
    if (i+1) % 50 == 0:
        progress = (i+1) / len(stocks) * 100
        log(f"  进度: {i+1}/{len(stocks)} ({progress:.1f}%) 已找到{len(results)}个")
    
    try:
        if code.startswith('6'):
            kcode = f'sh{code}'
        else:
            kcode = f'sz{code}'
        
        kurl = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={kcode},day,,,60,qfq'
        r = session.get(kurl, timeout=5)
        kdata = r.json()
        
        if not kdata.get('data'):
            continue
        
        stock_data = kdata['data'].get(kcode) or kdata['data'].get(kcode.upper())
        if not stock_data:
            continue
        
        kline = stock_data.get('qfqday') or stock_data.get('day', [])
        if len(kline) < 20:
            continue
        
        volumes = []
        prices = []
        for item in kline:
            if len(item) >= 6:
                volumes.append(float(item[5]))
                prices.append(float(item[2]))
        
        if len(volumes) < 20:
            continue
        
        recent_vol = sum(volumes[-days:]) / days
        base_vol = sum(volumes[-20:-days]) / (20 - days) if len(volumes) >= 20 else sum(volumes[:-days]) / max(1, len(volumes) - days)
        
        if base_vol <= 0:
            continue
        
        current_vol_ratio = recent_vol / base_vol
        
        if len(prices) >= days + 1:
            recent_price_change = (prices[-1] - prices[-days-1]) / prices[-days-1] * 100
        else:
            recent_price_change = 0
        
        if current_vol_ratio >= vol_ratio:
            if price_change == 0 or (price_change > 0 and recent_price_change > 0):
                results.append({
                    'code': code,
                    'name': stock['name'],
                    'price': prices[-1] if prices else stock['price'],
                    'vol_ratio': round(current_vol_ratio, 2),
                    'price_change': round(recent_price_change, 2),
                    'recent_vol': int(recent_vol),
                    'base_vol': int(base_vol)
                })
    except:
        continue

results.sort(key=lambda x: x['vol_ratio'], reverse=True)

log(f"\n[3] 筛选结果: 找到 {len(results)} 只放量股票\n")
log("="*100)
log(f"{'代码':<8} {'名称':<12} {'现价':<8} {'量比':<8} {'涨跌幅':<10} {'近期量':<12} {'基准量':<12}")
log("="*100)

display_count = min(50, len(results))
for r in results[:display_count]:
    vol_tag = "🔥" if r['vol_ratio'] >= 3 else "📈"
    price_color = "+" if r['price_change'] >= 0 else ""
    log(f"{r['code']:<8} {r['name']:<12} {r['price']:<8.2f} {vol_tag}{r['vol_ratio']:<7.2f}x "
        f"{price_color}{r['price_change']:<9.2f}% {r['recent_vol']/10000:<11.0f}万 {r['base_vol']/10000:<11.0f}万")

log("="*100)
log(f"\n共找到 {len(results)} 只符合条件的股票")

# 保存文件
script_dir = os.getcwd()
output_file = os.path.join(script_dir, f'放量股票_{datetime.now().strftime("%Y%m%d")}.txt')
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(f"筛选时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    f.write(f"筛选条件: 最近{days}天，量比≥{vol_ratio}倍，要求上涨\n")
    f.write("="*100 + "\n")
    f.write(f"{'代码':<8} {'名称':<12} {'现价':<8} {'量比':<8} {'涨跌幅':<10} {'近期量':<12} {'基准量':<12}\n")
    f.write("="*100 + "\n")
    for r in results:
        price_color = "+" if r['price_change'] >= 0 else ""
        f.write(f"{r['code']:<8} {r['name']:<12} {r['price']:<8.2f} {r['vol_ratio']:<8.2f}x "
                f"{price_color}{r['price_change']:<9.2f}% {r['recent_vol']/10000:<11.0f}万 {r['base_vol']/10000:<11.0f}万\n")

log(f"\n结果已保存到: {output_file}")

if HAS_PANDAS and len(results) > 0:
    try:
        df = pd.DataFrame(results)
        excel_file = os.path.join(script_dir, f'放量股票_{datetime.now().strftime("%Y%m%d")}.xlsx')
        df.to_excel(excel_file, index=False, engine='openpyxl')
        log(f"Excel文件已保存到: {excel_file}")
    except Exception as e:
        log(f"Excel导出失败: {str(e)}")
