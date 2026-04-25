# -*- coding: utf-8 -*-
"""
量化交易系统 - Web服务器
实时展示持仓和市场数据 + 自动交易 + K线形态筛选
"""
from flask import Flask, jsonify, render_template_string, request
import requests
import json
import os
from datetime import datetime
import threading
import time
import subprocess

app = Flask(__name__)

# 自动交易状态
auto_trade_status = {
    'running': False,
    'last_scan': None,
    'last_result': '',
    'scan_count': 0,
}

# 清理代理
for key in list(os.environ.keys()):
    if 'proxy' in key.lower():
        del os.environ[key]

session = requests.Session()
session.trust_env = False
session.headers.update({'User-Agent': 'Mozilla/5.0'})

DATA_FILE = 'd:/量化/quant_ai/portfolio.json'
INITIAL_CAPITAL = 100000

# 股票池
STOCK_POOL = [
    ('002456', '欧菲光'), ('000727', '冠捷科技'), ('000100', 'TCL科技'),
    ('000725', '京东方A'), ('002217', '合力泰'), ('000625', '长安汽车'),
    ('002013', '中航机电'), ('002414', '高德红外'), ('600998', '九州通'),
    ('002027', '分众传媒'), ('601108', '财通证券'),
]


def get_realtime_quote(code):
    """获取实时行情"""
    code = str(code).zfill(6)
    kcode = f'sh{code}' if code.startswith('6') else f'sz{code}'
    url = f'http://qt.gtimg.cn/q={kcode}'
    try:
        r = session.get(url, timeout=5)
        text = r.text
        if '~' not in text:
            return None
        parts = text.split('~')
        return {
            'code': code,
            'name': parts[1],
            'price': float(parts[3]),
            'yesterday_close': float(parts[4]),
            'change': float(parts[32]) if len(parts) > 32 and parts[32] else 0,
            'high': float(parts[33]) if len(parts) > 33 and parts[33] else 0,
            'low': float(parts[34]) if len(parts) > 34 and parts[34] else 0,
            'volume': float(parts[6]) if parts[6] else 0,
            'time': parts[30] if len(parts) > 30 else '',
        }
    except:
        return None


def load_portfolio():
    """加载投资组合"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'cash': INITIAL_CAPITAL, 'positions': {}, 'history': [], 'daily_value': []}


def is_trading_time():
    """判断是否在交易时间"""
    now = datetime.now()
    # 周末不交易
    if now.weekday() >= 5:
        return False
    # 交易时间: 9:30-11:30, 13:00-15:00
    t = now.hour * 100 + now.minute
    if (930 <= t <= 1130) or (1300 <= t <= 1500):
        return True
    return False


def auto_trade_loop():
    """自动交易后台循环"""
    global auto_trade_status
    auto_trade_status['running'] = True
    
    while auto_trade_status['running']:
        try:
            if is_trading_time():
                # 执行扫描交易
                auto_trade_status['scan_count'] += 1
                auto_trade_status['last_scan'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                result = subprocess.run(
                    ['python', 'd:/量化/quant_ai/quant_simulator.py'],
                    capture_output=True, text=True, timeout=120,
                    encoding='utf-8', errors='ignore'
                )
                auto_trade_status['last_result'] = result.stdout[-1500:] if result.stdout else ''
                
                # 交易时间内每60秒扫描一次
                time.sleep(60)
            else:
                # 非交易时间，每5分钟检查一次
                auto_trade_status['last_result'] = '非交易时间，等待中...'
                time.sleep(300)
        except Exception as e:
            auto_trade_status['last_result'] = f'错误: {str(e)}'
            time.sleep(60)


@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)


@app.route('/kline')
def kline_page():
    """K线形态相似度匹配页面"""
    return render_template_string(KLINE_TEMPLATE)


@app.route('/api/kline/<code>')
def api_kline(code):
    """获取股票K线数据"""
    code = str(code).zfill(6)
    days = request.args.get('days', 120, type=int)
    
    try:
        if code.startswith('6'):
            kcode = f'sh{code}'
        else:
            kcode = f'sz{code}'
        
        url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={kcode},day,,,{days},qfq'
        r = session.get(url, timeout=10)
        data = r.json()
        
        if not data.get('data'):
            return jsonify({'success': False, 'error': '无法获取数据'})
        
        stock_data = data['data'].get(kcode) or data['data'].get(kcode.upper())
        if not stock_data:
            return jsonify({'success': False, 'error': '股票代码无效'})
        
        kline_data = stock_data.get('qfqday') or stock_data.get('day', [])
        if not kline_data:
            return jsonify({'success': False, 'error': '无K线数据'})
        
        # 获取股票名称
        name = stock_data.get('qt', {}).get(kcode, ['', ''])[1] if 'qt' in stock_data else ''
        if not name:
            quote = get_realtime_quote(code)
            name = quote['name'] if quote else code
        
        # 格式化数据: [日期, 开盘, 收盘, 最低, 最高, 成交量]
        result = []
        for item in kline_data:
            if len(item) >= 6:
                result.append({
                    'date': item[0],
                    'open': float(item[1]),
                    'close': float(item[2]),
                    'high': float(item[3]),
                    'low': float(item[4]),
                    'volume': float(item[5])
                })
        
        return jsonify({
            'success': True,
            'code': code,
            'name': name,
            'data': result
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/find_similar', methods=['POST'])
def api_find_similar():
    """查找相似K线形态"""
    try:
        params = request.json
        source_code = params.get('code')
        start_idx = params.get('start_idx', 0)
        end_idx = params.get('end_idx', 10)
        
        # 获取源股票数据
        source_data = params.get('pattern_data', [])
        if not source_data or len(source_data) < 3:
            return jsonify({'success': False, 'error': '请选择至少3根K线'})
        
        # 标准化源数据 (价格变化率 + 量比)
        def normalize_pattern(data):
            if len(data) < 2:
                return [], []
            
            prices = []
            volumes = []
            base_price = data[0]['close']
            base_vol = sum(d['volume'] for d in data) / len(data)
            
            for d in data:
                # 价格变化率
                price_change = (d['close'] - d['open']) / d['open'] * 100
                prices.append(price_change)
                # 相对量能
                vol_ratio = d['volume'] / base_vol if base_vol > 0 else 1
                volumes.append(vol_ratio)
            
            return prices, volumes
        
        src_prices, src_vols = normalize_pattern(source_data)
        pattern_len = len(source_data)
        
        # 计算相似度
        def calc_similarity(target_data):
            if len(target_data) < pattern_len:
                return 0, -1
            
            best_score = 0
            best_idx = -1
            
            # 滑动窗口匹配
            for i in range(len(target_data) - pattern_len + 1):
                window = target_data[i:i + pattern_len]
                tgt_prices, tgt_vols = normalize_pattern(window)
                
                if not tgt_prices:
                    continue
                
                # 价格形态相似度 (余弦相似度)
                price_sim = cosine_similarity(src_prices, tgt_prices)
                # 量能形态相似度
                vol_sim = cosine_similarity(src_vols, tgt_vols)
                
                # 综合得分 (价格权重0.6, 量能权重0.4)
                score = price_sim * 0.6 + vol_sim * 0.4
                
                if score > best_score:
                    best_score = score
                    best_idx = i
            
            return best_score, best_idx
        
        def cosine_similarity(a, b):
            if len(a) != len(b) or len(a) == 0:
                return 0
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = sum(x * x for x in a) ** 0.5
            norm_b = sum(x * x for x in b) ** 0.5
            if norm_a == 0 or norm_b == 0:
                return 0
            return max(0, dot / (norm_a * norm_b))
        
        # 获取股票列表进行扫描
        stocks = []
        url = 'https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData'
        for node in ['hs_a', 'sz_a']:
            for page in range(1, 8):
                try:
                    params_req = {'page': page, 'num': 80, 'sort': 'amount', 'asc': 0, 'node': node}
                    r = session.get(url, params=params_req, timeout=10)
                    if r.text and r.text not in ['null', '[]']:
                        data = json.loads(r.text)
                        if not data:
                            break
                        for item in data:
                            code = item.get('symbol', '')
                            name = item.get('name', '')
                            if 'ST' in name or code == source_code:
                                continue
                            if code.startswith('8') or code.startswith('4') or code.startswith('9'):
                                continue
                            stocks.append({'code': code, 'name': name})
                except:
                    break
        
        # 去重
        seen = set()
        unique_stocks = []
        for s in stocks:
            if s['code'] not in seen:
                seen.add(s['code'])
                unique_stocks.append(s)
        stocks = unique_stocks[:300]  # 限制扫描数量
        
        # 扫描相似形态
        results = []
        for stock in stocks:
            code = stock['code']
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
                if len(kline) < pattern_len:
                    continue
                
                # 转换格式
                target_data = []
                for item in kline:
                    if len(item) >= 6:
                        target_data.append({
                            'open': float(item[1]),
                            'close': float(item[2]),
                            'high': float(item[3]),
                            'low': float(item[4]),
                            'volume': float(item[5])
                        })
                
                score, match_idx = calc_similarity(target_data)
                
                if score >= 0.7:  # 相似度阈值
                    results.append({
                        'code': code,
                        'name': stock['name'],
                        'score': round(score * 100, 1),
                        'match_idx': match_idx,
                        'match_len': pattern_len
                    })
            except:
                continue
        
        # 按相似度排序
        results.sort(key=lambda x: x['score'], reverse=True)
        
        return jsonify({
            'success': True,
            'count': len(results),
            'results': results[:20]  # 返回前20个
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/scan_volume', methods=['POST'])
def api_scan_volume():
    """筛选放量股票"""
    try:
        params = request.json or {}
        days = params.get('days', 3)  # 最近N天
        vol_ratio = params.get('vol_ratio', 2.0)  # 量比阈值
        price_change = params.get('price_change', 0)  # 价格涨跌要求
        
        # 获取股票列表 - 全市场扫描
        stocks = []
        url = 'https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodeData'
        max_pages = params.get('max_pages', 50)  # 支持自定义页面数，默认50页
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
                except:
                    break
        
        # 去重
        seen = set()
        unique_stocks = []
        for s in stocks:
            if s['code'] not in seen:
                seen.add(s['code'])
                unique_stocks.append(s)
        stocks = unique_stocks  # 移除数量限制，全市场扫描
        
        # 扫描放量股票
        results = []
        for i, stock in enumerate(stocks):
            code = stock['code']
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
                
                # 解析K线数据
                volumes = []
                prices = []
                for item in kline:
                    if len(item) >= 6:
                        volumes.append(float(item[5]))
                        prices.append(float(item[2]))  # 收盘价
                
                if len(volumes) < 20:
                    continue
                
                # 计算指标
                # 最近N天的平均成交量
                recent_vol = sum(volumes[-days:]) / days
                # 之前20天的平均成交量（排除最近N天）
                base_vol = sum(volumes[-20:-days]) / (20 - days) if len(volumes) >= 20 else sum(volumes[:-days]) / max(1, len(volumes) - days)
                
                if base_vol <= 0:
                    continue
                
                # 量比
                current_vol_ratio = recent_vol / base_vol
                
                # 价格变化（最近N天涨跌幅）
                if len(prices) >= days + 1:
                    recent_price_change = (prices[-1] - prices[-days-1]) / prices[-days-1] * 100
                else:
                    recent_price_change = 0
                
                # 筛选条件
                if current_vol_ratio >= vol_ratio:
                    if price_change == 0 or (price_change > 0 and recent_price_change > 0) or (price_change < 0 and recent_price_change < 0):
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
        
        # 按量比排序
        results.sort(key=lambda x: x['vol_ratio'], reverse=True)
        
        # 命令行模式返回所有结果，Web模式返回前30个
        limit = request.json.get('limit', 30) if hasattr(request, 'json') and request.json else len(results)
        
        return jsonify({
            'success': True,
            'count': len(results),
            'results': results[:limit] if limit < len(results) else results
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/status')
def api_status():
    """获取账户状态"""
    portfolio = load_portfolio()
    positions = []
    total_position_value = 0
    
    for code, pos in portfolio.get('positions', {}).items():
        quote = get_realtime_quote(code)
        if quote:
            current_value = pos['shares'] * quote['price']
            pnl = current_value - pos['shares'] * pos['cost']
            pnl_pct = (quote['price'] - pos['cost']) / pos['cost'] * 100
            total_position_value += current_value
            positions.append({
                'code': code,
                'name': pos['name'],
                'shares': pos['shares'],
                'cost': pos['cost'],
                'price': quote['price'],
                'change': quote['change'],
                'value': current_value,
                'pnl': pnl,
                'pnl_pct': pnl_pct,
                'buy_date': pos['buy_date'],
            })
    
    total_value = portfolio['cash'] + total_position_value
    total_return = total_value - INITIAL_CAPITAL
    total_return_pct = (total_value / INITIAL_CAPITAL - 1) * 100
    
    return jsonify({
        'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'cash': portfolio['cash'],
        'position_value': total_position_value,
        'total_value': total_value,
        'total_return': total_return,
        'total_return_pct': total_return_pct,
        'positions': positions,
        'history': portfolio.get('history', [])[-10:],  # 最近10条
        'daily_value': portfolio.get('daily_value', [])[-20:],  # 最近20条
    })


@app.route('/api/market')
def api_market():
    """获取市场行情"""
    stocks = []
    for code, name in STOCK_POOL:
        quote = get_realtime_quote(code)
        if quote:
            stocks.append({
                'code': code,
                'name': quote['name'],
                'price': quote['price'],
                'change': quote['change'],
            })
    stocks.sort(key=lambda x: x['change'], reverse=True)
    return jsonify({'time': datetime.now().strftime('%H:%M:%S'), 'stocks': stocks})


@app.route('/api/scan')
def api_scan():
    """手动触发扫描交易"""
    try:
        result = subprocess.run(
            ['python', 'd:/量化/quant_ai/quant_simulator.py'],
            capture_output=True, text=True, timeout=120, encoding='utf-8', errors='ignore'
        )
        auto_trade_status['last_scan'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        auto_trade_status['last_result'] = result.stdout[-1500:] if result.stdout else ''
        auto_trade_status['scan_count'] += 1
        return jsonify({
            'success': True,
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'output': result.stdout[-2000:] if result.stdout else '',
            'message': '扫描完成'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/auto_status')
def api_auto_status():
    """获取自动交易状态"""
    return jsonify({
        'running': auto_trade_status['running'],
        'is_trading_time': is_trading_time(),
        'last_scan': auto_trade_status['last_scan'],
        'scan_count': auto_trade_status['scan_count'],
        'last_result': auto_trade_status['last_result'],
    })


@app.route('/api/buy/<code>/<int:amount>')
def api_buy(code, amount):
    """手动买入"""
    portfolio = load_portfolio()
    quote = get_realtime_quote(code)
    if not quote:
        return jsonify({'success': False, 'error': '无法获取行情'})
    
    price = quote['price']
    shares = int(amount / price / 100) * 100
    if shares < 100:
        return jsonify({'success': False, 'error': '资金不足一手'})
    
    cost = shares * price
    commission = max(cost * 0.0003, 5)
    total_cost = cost + commission
    
    if total_cost > portfolio['cash']:
        return jsonify({'success': False, 'error': f'资金不足: 需要{total_cost:.2f}'})
    
    # 执行买入
    if code in portfolio['positions']:
        old = portfolio['positions'][code]
        new_shares = old['shares'] + shares
        new_cost = (old['shares'] * old['cost'] + cost) / new_shares
        portfolio['positions'][code] = {'shares': new_shares, 'cost': new_cost, 
                                        'buy_date': datetime.now().strftime('%Y-%m-%d'), 'name': quote['name']}
    else:
        portfolio['positions'][code] = {'shares': shares, 'cost': price,
                                        'buy_date': datetime.now().strftime('%Y-%m-%d'), 'name': quote['name']}
    
    portfolio['cash'] -= total_cost
    portfolio['history'].append({
        'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 'type': 'buy',
        'code': code, 'name': quote['name'], 'price': price, 'shares': shares,
        'amount': cost, 'commission': commission
    })
    
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(portfolio, f, ensure_ascii=False, indent=2)
    
    return jsonify({'success': True, 'message': f"买入 {quote['name']} {shares}股 @ {price:.2f}"})


KLINE_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>K线形态相似匹配</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #fff; min-height: 100vh; padding: 20px;
        }
        .container { max-width: 1600px; margin: 0 auto; }
        .header {
            display: flex; justify-content: space-between; align-items: center;
            padding: 20px; background: rgba(255,255,255,0.05); border-radius: 16px;
            margin-bottom: 20px;
        }
        .header h1 { font-size: 24px; display: flex; align-items: center; gap: 10px; }
        .controls {
            display: flex; gap: 15px; align-items: center; flex-wrap: wrap;
        }
        .input-group {
            display: flex; align-items: center; gap: 8px;
        }
        .input-group label { color: #888; font-size: 14px; }
        .input-group input, .input-group select {
            padding: 10px 15px; border: 1px solid #3d4f7c; border-radius: 8px;
            background: #1e2a4a; color: #fff; font-size: 14px; outline: none;
        }
        .input-group input:focus { border-color: #00d4aa; }
        .btn {
            padding: 10px 20px; border: none; border-radius: 8px;
            font-weight: 600; cursor: pointer; transition: 0.3s; font-size: 14px;
        }
        .btn-primary { background: #00d4aa; color: #1a1a2e; }
        .btn-primary:hover { background: #00b894; }
        .btn-warning { background: #ff9f43; color: #1a1a2e; }
        .btn-warning:hover { background: #e67e22; }
        .btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .main-content { display: grid; grid-template-columns: 1fr 400px; gap: 20px; }
        .chart-panel {
            background: rgba(255,255,255,0.05); border-radius: 16px; padding: 20px;
        }
        .chart-header {
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 15px; padding-bottom: 15px; border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .stock-info { display: flex; align-items: baseline; gap: 10px; }
        .stock-name { font-size: 20px; font-weight: 600; }
        .stock-code { color: #00d4aa; font-size: 14px; }
        .selection-info {
            background: rgba(255,159,67,0.2); padding: 8px 15px; border-radius: 8px;
            font-size: 13px; color: #ff9f43;
        }
        #chart { width: 100%; height: 550px; }
        .tips {
            margin-top: 15px; padding: 12px; background: rgba(0,212,170,0.1);
            border-radius: 8px; font-size: 13px; color: #00d4aa;
        }
        .results-panel {
            background: rgba(255,255,255,0.05); border-radius: 16px; padding: 20px;
            max-height: calc(100vh - 160px); overflow-y: auto;
        }
        .results-header {
            font-size: 18px; font-weight: 600; margin-bottom: 15px;
            display: flex; align-items: center; gap: 8px;
        }
        .results-header::before {
            content: ""; width: 4px; height: 20px; background: #ff9f43; border-radius: 2px;
        }
        .result-count { color: #888; font-size: 14px; margin-bottom: 15px; }
        .result-item {
            background: rgba(255,255,255,0.05); border-radius: 12px; padding: 15px;
            margin-bottom: 12px; cursor: pointer; transition: 0.3s;
            border: 1px solid transparent;
        }
        .result-item:hover { border-color: #00d4aa; transform: translateX(5px); }
        .result-item-header {
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 8px;
        }
        .result-name { font-weight: 600; font-size: 15px; }
        .result-code { color: #00d4aa; font-size: 13px; }
        .result-score {
            background: linear-gradient(90deg, #ff9f43, #e67e22);
            padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600;
        }
        .result-score.high { background: linear-gradient(90deg, #00d4aa, #00b894); }
        .loading {
            text-align: center; padding: 40px; color: #888;
        }
        .loading-spinner {
            width: 40px; height: 40px; border: 3px solid #3d4f7c;
            border-top-color: #00d4aa; border-radius: 50%;
            animation: spin 1s linear infinite; margin: 0 auto 15px;
        }
        @keyframes spin { to { transform: rotate(360deg); } }
        .empty-state {
            text-align: center; padding: 60px 20px; color: #666;
        }
        .empty-state-icon { font-size: 48px; margin-bottom: 15px; opacity: 0.5; }
        .back-link {
            color: #00d4aa; text-decoration: none; font-size: 14px;
        }
        .back-link:hover { text-decoration: underline; }
        .btn-danger { background: #ef4444; color: #fff; }
        .btn-danger:hover { background: #dc2626; }
        .filter-panel {
            background: rgba(255,255,255,0.08); border-radius: 12px; padding: 15px;
            margin-bottom: 15px;
        }
        .filter-title { font-size: 14px; font-weight: 600; margin-bottom: 12px; color: #ff9f43; }
        .filter-row { display: flex; gap: 15px; align-items: center; flex-wrap: wrap; }
        .filter-row .input-group { margin: 0; }
        .vol-tag {
            display: inline-block; padding: 3px 8px; border-radius: 4px;
            font-size: 12px; font-weight: 600; margin-left: 8px;
        }
        .vol-tag.high { background: #ef4444; color: #fff; }
        .vol-tag.medium { background: #ff9f43; color: #1a1a2e; }
        @media (max-width: 1200px) {
            .main-content { grid-template-columns: 1fr; }
            .results-panel { max-height: none; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 K线形态筛选</h1>
            <div class="controls">
                <a href="/" class="back-link">← 返回主页</a>
                <div class="input-group">
                    <label>股票代码:</label>
                    <input type="text" id="stockCode" value="000001" placeholder="输入代码" style="width:100px;">
                </div>
                <button class="btn btn-primary" onclick="loadStock()">加载K线</button>
            </div>
        </div>

        <div class="main-content">
            <div class="chart-panel">
                <div class="chart-header">
                    <div class="stock-info">
                        <span class="stock-name" id="stockName">请输入股票代码</span>
                        <span class="stock-code" id="displayCode"></span>
                    </div>
                    <div class="selection-info" id="selectionInfo" style="display:none;">
                        已选择: <span id="selectionRange"></span>
                    </div>
                </div>
                <div id="chart"></div>
                <div class="tips">
                    💡 <b>使用方法:</b> 
                    输入股票代码查看K线 | 使用右侧筛选功能搜索放量股票
                </div>
            </div>

            <div class="results-panel">
                <div class="filter-panel">
                    <div class="filter-title">📈 放量筛选</div>
                    <div class="filter-row">
                        <div class="input-group">
                            <label>天数:</label>
                            <select id="volDays" style="width:80px;">
                                <option value="1">1天</option>
                                <option value="2">2天</option>
                                <option value="3" selected>3天</option>
                                <option value="5">5天</option>
                            </select>
                        </div>
                        <div class="input-group">
                            <label>量比≥:</label>
                            <select id="volRatio" style="width:80px;">
                                <option value="1.5">1.5倍</option>
                                <option value="2" selected>2倍</option>
                                <option value="3">3倍</option>
                                <option value="5">5倍</option>
                            </select>
                        </div>
                        <div class="input-group">
                            <label>涨跌:</label>
                            <select id="priceDir" style="width:80px;">
                                <option value="0">不限</option>
                                <option value="1" selected>上涨</option>
                                <option value="-1">下跌</option>
                            </select>
                        </div>
                    </div>
                    <div style="margin-top:12px;">
                        <button class="btn btn-danger" id="scanVolBtn" onclick="scanVolume()" style="width:100%;">
                            🔥 扫描放量股票
                        </button>
                    </div>
                </div>
                
                <div class="results-header">🎯 今日精选（点击查看K线）</div>
                <div id="hotStocksContainer">
                    <div class="result-item" onclick="viewStock('002867')">
                        <div class="result-item-header">
                            <div><span class="result-name">周大生</span><span class="result-code">002867</span></div>
                            <span class="vol-tag high">4.66x</span>
                        </div>
                        <div style="font-size:12px;color:#888;">01-28涨+8.2% | 现价13.48</div>
                    </div>
                    <div class="result-item" onclick="viewStock('300017')">
                        <div class="result-item-header">
                            <div><span class="result-name">网宿科技</span><span class="result-code">300017</span></div>
                            <span class="vol-tag high">3.79x</span>
                        </div>
                        <div style="font-size:12px;color:#888;">01-26涨+20% | 现价16.80</div>
                    </div>
                    <div class="result-item" onclick="viewStock('002506')">
                        <div class="result-item-header">
                            <div><span class="result-name">协鑫集成</span><span class="result-code">002506</span></div>
                            <span class="vol-tag high">2.82x</span>
                        </div>
                        <div style="font-size:12px;color:#888;">01-23涨+10.2% | 现价3.56</div>
                    </div>
                    <div class="result-item" onclick="viewStock('002266')">
                        <div class="result-item-header">
                            <div><span class="result-name">浙富控股</span><span class="result-code">002266</span></div>
                            <span class="vol-tag medium">2.54x</span>
                        </div>
                        <div style="font-size:12px;color:#888;">01-22涨+9.9% | 现价5.16</div>
                    </div>
                    <div class="result-item" onclick="viewStock('600339')">
                        <div class="result-item-header">
                            <div><span class="result-name">中油工程</span><span class="result-code">600339</span></div>
                            <span class="vol-tag medium">2.12x</span>
                        </div>
                        <div style="font-size:12px;color:#888;">01-29涨停+10% | 现价4.30</div>
                    </div>
                    <div class="result-item" onclick="viewStock('002948')">
                        <div class="result-item-header">
                            <div><span class="result-name">青岛银行</span><span class="result-code">002948</span></div>
                            <span class="vol-tag medium">2.07x</span>
                        </div>
                        <div style="font-size:12px;color:#888;">01-29涨停+9.9% | 现价5.09</div>
                    </div>
                    <div class="result-item" onclick="viewStock('300142')">
                        <div class="result-item-header">
                            <div><span class="result-name">沃森生物</span><span class="result-code">300142</span></div>
                            <span class="vol-tag medium">2.08x</span>
                        </div>
                        <div style="font-size:12px;color:#888;">01-26涨+11.5% | 现价12.89</div>
                    </div>
                    <div class="result-item" onclick="viewStock('002185')">
                        <div class="result-item-header">
                            <div><span class="result-name">华天科技</span><span class="result-code">002185</span></div>
                            <span class="vol-tag medium">2.09x</span>
                        </div>
                        <div style="font-size:12px;color:#888;">01-21涨停+10% | 现价14.80</div>
                    </div>
                    <div class="result-item" onclick="viewStock('600352')">
                        <div class="result-item-header">
                            <div><span class="result-name">浙江龙盛</span><span class="result-code">600352</span></div>
                            <span class="vol-tag medium">1.86x</span>
                        </div>
                        <div style="font-size:12px;color:#888;">01-28涨停+10% | 现价15.47</div>
                    </div>
                    <div class="result-item" onclick="viewStock('002129')">
                        <div class="result-item-header">
                            <div><span class="result-name">TCL中环</span><span class="result-code">002129</span></div>
                            <span class="vol-tag medium">1.73x</span>
                        </div>
                        <div style="font-size:12px;color:#888;">01-23涨+7.9% | 现价9.81</div>
                    </div>
                    <div class="result-item" onclick="viewStock('600325')">
                        <div class="result-item-header">
                            <div><span class="result-name">华发股份</span><span class="result-code">600325</span></div>
                            <span class="vol-tag medium">1.71x</span>
                        </div>
                        <div style="font-size:12px;color:#888;">01-29涨+8.3% | 现价4.42</div>
                    </div>
                    <div class="result-item" onclick="viewStock('002459')">
                        <div class="result-item-header">
                            <div><span class="result-name">晶澳科技</span><span class="result-code">002459</span></div>
                            <span class="vol-tag medium">1.69x</span>
                        </div>
                        <div style="font-size:12px;color:#888;">01-23涨+8.9% | 现价11.95</div>
                    </div>
                </div>
                
                <div class="results-header" style="margin-top:20px;">筛选结果</div>
                <div id="resultsContainer">
                    <div class="empty-state" style="padding:30px;">
                        <div>点击上方股票查看K线</div>
                        <div style="font-size:12px;color:#666;margin-top:5px;">或使用筛选功能搜索更多</div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let chart = null;
        let currentData = [];
        let selectedRange = { start: 0, end: 0 };

        function initChart() {
            chart = echarts.init(document.getElementById('chart'));
            chart.on('datazoom', function(params) {
                if (currentData.length === 0) return;
                
                let startValue, endValue;
                if (params.batch) {
                    startValue = params.batch[0].startValue;
                    endValue = params.batch[0].endValue;
                } else {
                    const opt = chart.getOption();
                    startValue = opt.dataZoom[0].startValue;
                    endValue = opt.dataZoom[0].endValue;
                }
                
                if (startValue !== undefined && endValue !== undefined) {
                    selectedRange.start = Math.max(0, Math.floor(startValue));
                    selectedRange.end = Math.min(currentData.length - 1, Math.ceil(endValue));
                    updateSelectionInfo();
                }
            });
        }

        function updateSelectionInfo() {
            const len = selectedRange.end - selectedRange.start + 1;
            if (len >= 3 && currentData.length > 0) {
                const startDate = currentData[selectedRange.start]?.date || '';
                const endDate = currentData[selectedRange.end]?.date || '';
                document.getElementById('selectionInfo').style.display = 'block';
                document.getElementById('selectionRange').textContent = 
                    `${startDate} ~ ${endDate} (${len}根K线)`;
                document.getElementById('findBtn').disabled = false;
            } else {
                document.getElementById('selectionInfo').style.display = 'none';
                document.getElementById('findBtn').disabled = true;
            }
        }

        async function loadStock() {
            const code = document.getElementById('stockCode').value.trim();
            if (!code) {
                alert('请输入股票代码');
                return;
            }

            try {
                const res = await fetch(`/api/kline/${code}?days=120`);
                const data = await res.json();
                
                if (!data.success) {
                    alert('加载失败: ' + (data.error || '未知错误'));
                    return;
                }

                currentData = data.data;
                document.getElementById('stockName').textContent = data.name || code;
                document.getElementById('displayCode').textContent = `(${code})`;
                
                renderChart(data.data);
                
                // 默认选择最后20根K线
                const defaultStart = Math.max(0, data.data.length - 20);
                selectedRange = { start: defaultStart, end: data.data.length - 1 };
                updateSelectionInfo();
                
            } catch (e) {
                alert('请求失败: ' + e.message);
            }
        }

        function renderChart(data) {
            const dates = data.map(d => d.date);
            const klineData = data.map(d => [d.open, d.close, d.low, d.high]);
            const volumes = data.map((d, i) => ({
                value: d.volume,
                itemStyle: { color: d.close >= d.open ? '#ef4444' : '#22c55e' }
            }));

            const option = {
                backgroundColor: 'transparent',
                animation: false,
                tooltip: {
                    trigger: 'axis',
                    axisPointer: { type: 'cross' },
                    backgroundColor: 'rgba(30, 42, 74, 0.95)',
                    borderColor: '#3d4f7c',
                    textStyle: { color: '#fff', fontSize: 12 },
                    formatter: function(params) {
                        const k = params.find(p => p.seriesName === 'K线');
                        const v = params.find(p => p.seriesName === '成交量');
                        if (!k) return '';
                        const d = k.data;
                        let html = `<b>${k.axisValue}</b><br/>`;
                        html += `开: ${d[1]} 收: ${d[2]}<br/>`;
                        html += `高: ${d[4]} 低: ${d[3]}<br/>`;
                        if (v) html += `量: ${(v.data.value/10000).toFixed(0)}万`;
                        return html;
                    }
                },
                grid: [
                    { left: '8%', right: '3%', top: '5%', height: '50%' },
                    { left: '8%', right: '3%', top: '62%', height: '20%' }
                ],
                xAxis: [
                    { type: 'category', data: dates, gridIndex: 0, axisLine: { lineStyle: { color: '#3d4f7c' }}, axisLabel: { color: '#888', fontSize: 11 }, axisTick: { show: false }},
                    { type: 'category', data: dates, gridIndex: 1, axisLine: { lineStyle: { color: '#3d4f7c' }}, axisLabel: { color: '#888', fontSize: 11 }, axisTick: { show: false }}
                ],
                yAxis: [
                    { scale: true, gridIndex: 0, splitLine: { lineStyle: { color: '#2a3a5a', type: 'dashed' }}, axisLabel: { color: '#888' }, axisLine: { show: false }},
                    { scale: true, gridIndex: 1, splitLine: { lineStyle: { color: '#2a3a5a', type: 'dashed' }}, axisLabel: { color: '#888', formatter: v => (v/10000).toFixed(0) + '万' }, axisLine: { show: false }}
                ],
                dataZoom: [
                    { type: 'slider', xAxisIndex: [0, 1], start: 60, end: 100, bottom: 5, height: 25,
                      borderColor: '#3d4f7c', backgroundColor: '#1e2a4a',
                      fillerColor: 'rgba(255,159,67,0.3)', handleStyle: { color: '#ff9f43' },
                      textStyle: { color: '#888' }, brushSelect: false
                    },
                    { type: 'inside', xAxisIndex: [0, 1], start: 60, end: 100 }
                ],
                series: [
                    {
                        name: 'K线', type: 'candlestick', data: klineData, xAxisIndex: 0, yAxisIndex: 0,
                        itemStyle: { color: '#ef4444', color0: '#22c55e', borderColor: '#ef4444', borderColor0: '#22c55e' }
                    },
                    {
                        name: '成交量', type: 'bar', data: volumes, xAxisIndex: 1, yAxisIndex: 1, barWidth: '60%'
                    }
                ]
            };
            
            chart.setOption(option, true);
        }

        async function findSimilar() {
            if (currentData.length === 0) {
                alert('请先加载股票K线');
                return;
            }

            const patternData = currentData.slice(selectedRange.start, selectedRange.end + 1);
            if (patternData.length < 3) {
                alert('请至少选择3根K线');
                return;
            }

            const btn = document.getElementById('findBtn');
            const container = document.getElementById('resultsContainer');
            
            btn.disabled = true;
            btn.textContent = '搜索中...';
            container.innerHTML = `
                <div class="loading">
                    <div class="loading-spinner"></div>
                    <div>正在扫描全市场，请稍候...</div>
                    <div style="margin-top:10px;font-size:12px;color:#666;">约需30-60秒</div>
                </div>
            `;

            try {
                const res = await fetch('/api/find_similar', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        code: document.getElementById('stockCode').value.trim(),
                        start_idx: selectedRange.start,
                        end_idx: selectedRange.end,
                        pattern_data: patternData
                    })
                });
                
                const data = await res.json();
                
                if (!data.success) {
                    container.innerHTML = `<div class="empty-state"><div>搜索失败: ${data.error}</div></div>`;
                    return;
                }

                if (data.results.length === 0) {
                    container.innerHTML = `
                        <div class="empty-state">
                            <div class="empty-state-icon">😔</div>
                            <div>未找到相似形态</div>
                            <div style="margin-top:10px;font-size:12px;color:#666;">尝试选择更有特征的K线组合</div>
                        </div>
                    `;
                    return;
                }

                let html = `<div class="result-count">找到 ${data.count} 个相似形态</div>`;
                data.results.forEach(r => {
                    const scoreClass = r.score >= 85 ? 'high' : '';
                    html += `
                        <div class="result-item" onclick="viewStock('${r.code}')">
                            <div class="result-item-header">
                                <div>
                                    <span class="result-name">${r.name}</span>
                                    <span class="result-code">${r.code}</span>
                                </div>
                                <span class="result-score ${scoreClass}">${r.score}%</span>
                            </div>
                            <div style="font-size:12px;color:#888;">
                                匹配位置: 第${r.match_idx + 1}~${r.match_idx + r.match_len}根K线
                            </div>
                        </div>
                    `;
                });
                container.innerHTML = html;

            } catch (e) {
                container.innerHTML = `<div class="empty-state"><div>请求失败: ${e.message}</div></div>`;
            } finally {
                btn.disabled = false;
                btn.textContent = '🔍 查找相似形态';
            }
        }

        async function scanVolume() {
            const btn = document.getElementById('scanVolBtn');
            const container = document.getElementById('resultsContainer');
            
            const days = parseInt(document.getElementById('volDays').value);
            const volRatio = parseFloat(document.getElementById('volRatio').value);
            const priceDir = parseInt(document.getElementById('priceDir').value);
            
            btn.disabled = true;
            btn.textContent = '扫描中...';
            container.innerHTML = `
                <div class="loading">
                    <div class="loading-spinner"></div>
                    <div>正在扫描全市场放量股票...</div>
                    <div style="margin-top:10px;font-size:12px;color:#666;">约需30-60秒</div>
                </div>
            `;

            try {
                const res = await fetch('/api/scan_volume', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        days: days,
                        vol_ratio: volRatio,
                        price_change: priceDir
                    })
                });
                
                const data = await res.json();
                
                if (!data.success) {
                    container.innerHTML = `<div class="empty-state"><div>扫描失败: ${data.error}</div></div>`;
                    return;
                }

                if (data.results.length === 0) {
                    container.innerHTML = `
                        <div class="empty-state">
                            <div class="empty-state-icon">😔</div>
                            <div>未找到符合条件的股票</div>
                            <div style="margin-top:10px;font-size:12px;color:#666;">尝试降低量比要求</div>
                        </div>
                    `;
                    return;
                }

                let html = `<div class="result-count">找到 ${data.count} 只放量股票</div>`;
                data.results.forEach(r => {
                    const volClass = r.vol_ratio >= 3 ? 'high' : 'medium';
                    const priceColor = r.price_change >= 0 ? '#ef4444' : '#22c55e';
                    html += `
                        <div class="result-item" onclick="viewStock('${r.code}')">
                            <div class="result-item-header">
                                <div>
                                    <span class="result-name">${r.name}</span>
                                    <span class="result-code">${r.code}</span>
                                    <span class="vol-tag ${volClass}">${r.vol_ratio}倍量</span>
                                </div>
                            </div>
                            <div style="font-size:13px;display:flex;justify-content:space-between;margin-top:5px;">
                                <span>现价: ¥${r.price.toFixed(2)}</span>
                                <span style="color:${priceColor};">${r.price_change >= 0 ? '+' : ''}${r.price_change}%</span>
                            </div>
                            <div style="font-size:12px;color:#888;margin-top:3px;">
                                近期量: ${(r.recent_vol/10000).toFixed(0)}万 | 基准量: ${(r.base_vol/10000).toFixed(0)}万
                            </div>
                        </div>
                    `;
                });
                container.innerHTML = html;

            } catch (e) {
                container.innerHTML = `<div class="empty-state"><div>请求失败: ${e.message}</div></div>`;
            } finally {
                btn.disabled = false;
                btn.textContent = '🔥 扫描放量股票';
            }
        }

        function viewStock(code) {
            document.getElementById('stockCode').value = code;
            loadStock();
        }

        window.addEventListener('resize', () => chart && chart.resize());
        initChart();
    </script>
</body>
</html>
'''

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>量化交易系统</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #fff; min-height: 100vh; padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        .header { 
            display: flex; justify-content: space-between; align-items: center;
            padding: 20px; background: rgba(255,255,255,0.05); border-radius: 16px;
            margin-bottom: 20px;
        }
        .header h1 { font-size: 24px; }
        .time { color: #888; font-size: 14px; }
        .cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 20px; }
        .card {
            background: rgba(255,255,255,0.08); border-radius: 16px; padding: 24px;
            transition: transform 0.3s;
        }
        .card:hover { transform: translateY(-5px); }
        .card-label { color: #888; font-size: 14px; margin-bottom: 8px; }
        .card-value { font-size: 28px; font-weight: 600; }
        .positive { color: #00d4aa; }
        .negative { color: #ff6b6b; }
        .section { 
            background: rgba(255,255,255,0.05); border-radius: 16px; 
            padding: 24px; margin-bottom: 20px;
        }
        .section-title { font-size: 18px; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }
        .section-title::before { content: ""; width: 4px; height: 20px; background: #00d4aa; border-radius: 2px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.1); }
        th { color: #888; font-weight: 500; font-size: 14px; }
        td { font-size: 15px; }
        .stock-code { color: #00d4aa; font-weight: 500; }
        .pnl-positive { color: #00d4aa; }
        .pnl-negative { color: #ff6b6b; }
        .grid-2 { display: grid; grid-template-columns: 2fr 1fr; gap: 20px; }
        .chart-placeholder {
            height: 200px; background: rgba(0,0,0,0.2); border-radius: 12px;
            display: flex; align-items: center; justify-content: center; color: #666;
        }
        .refresh-btn {
            background: #00d4aa; color: #1a1a2e; border: none; padding: 10px 20px;
            border-radius: 8px; cursor: pointer; font-weight: 600; transition: 0.3s;
        }
        .refresh-btn:hover { background: #00b894; }
        .status-dot { 
            width: 8px; height: 8px; background: #00d4aa; border-radius: 50%;
            display: inline-block; margin-right: 8px; animation: pulse 2s infinite;
        }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .mini-table { font-size: 13px; }
        .mini-table td, .mini-table th { padding: 8px; }
        .empty-msg { color: #666; text-align: center; padding: 40px; }
        @media (max-width: 1200px) { .cards { grid-template-columns: repeat(2, 1fr); } }
        @media (max-width: 768px) { 
            .cards { grid-template-columns: 1fr; } 
            .grid-2 { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 量化交易系统</h1>
            <div>
                <span class="status-dot" id="statusDot"></span>
                <span id="autoStatus" class="time">加载中...</span>
                <span id="updateTime" class="time" style="margin-left: 16px;"></span>
                <button class="refresh-btn" onclick="refresh()" style="margin-left: 16px;">刷新</button>
                <button class="refresh-btn" onclick="runScan()" style="margin-left: 8px; background: #ff9f43;">立即扫描</button>
            </div>
        </div>

        <div class="cards">
            <div class="card">
                <div class="card-label">总资产</div>
                <div class="card-value" id="totalValue">--</div>
            </div>
            <div class="card">
                <div class="card-label">持仓市值</div>
                <div class="card-value" id="positionValue">--</div>
            </div>
            <div class="card">
                <div class="card-label">可用现金</div>
                <div class="card-value" id="cash">--</div>
            </div>
            <div class="card">
                <div class="card-label">总收益</div>
                <div class="card-value" id="totalReturn">--</div>
            </div>
        </div>

        <div class="grid-2">
            <div class="section">
                <div class="section-title">持仓明细</div>
                <table id="positionsTable">
                    <thead>
                        <tr>
                            <th>代码</th>
                            <th>名称</th>
                            <th>持仓</th>
                            <th>成本</th>
                            <th>现价</th>
                            <th>涨跌</th>
                            <th>市值</th>
                            <th>盈亏</th>
                        </tr>
                    </thead>
                    <tbody></tbody>
                </table>
                <div id="emptyPosition" class="empty-msg" style="display:none;">暂无持仓</div>
            </div>
            <div class="section">
                <div class="section-title">市场行情</div>
                <table class="mini-table" id="marketTable">
                    <thead><tr><th>代码</th><th>名称</th><th>价格</th><th>涨跌</th></tr></thead>
                    <tbody></tbody>
                </table>
            </div>
        </div>

        <div class="grid-2">
            <div class="section">
                <div class="section-title">交易记录</div>
                <table class="mini-table" id="historyTable">
                    <thead>
                        <tr><th>时间</th><th>类型</th><th>代码</th><th>名称</th><th>价格</th><th>数量</th><th>金额</th></tr>
                    </thead>
                    <tbody></tbody>
                </table>
                <div id="emptyHistory" class="empty-msg" style="display:none;">暂无交易记录</div>
            </div>
            <div class="section">
                <div class="section-title">自动交易日志</div>
                <pre id="tradeLog" style="background: rgba(0,0,0,0.3); padding: 16px; border-radius: 8px; font-size: 12px; max-height: 300px; overflow-y: auto; white-space: pre-wrap; color: #aaa;">等待数据...</pre>
            </div>
        </div>
    </div>

    <script>
        function formatMoney(n) { return n.toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2}); }
        function formatPct(n) { return (n >= 0 ? '+' : '') + n.toFixed(2) + '%'; }

        async function fetchStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                
                document.getElementById('updateTime').textContent = data.time;
                document.getElementById('totalValue').textContent = '¥' + formatMoney(data.total_value);
                document.getElementById('positionValue').textContent = '¥' + formatMoney(data.position_value);
                document.getElementById('cash').textContent = '¥' + formatMoney(data.cash);
                
                const retEl = document.getElementById('totalReturn');
                retEl.textContent = (data.total_return >= 0 ? '+' : '') + formatMoney(data.total_return) + ' (' + formatPct(data.total_return_pct) + ')';
                retEl.className = 'card-value ' + (data.total_return >= 0 ? 'positive' : 'negative');

                // 持仓
                const tbody = document.querySelector('#positionsTable tbody');
                tbody.innerHTML = '';
                if (data.positions.length === 0) {
                    document.getElementById('emptyPosition').style.display = 'block';
                    document.querySelector('#positionsTable').style.display = 'none';
                } else {
                    document.getElementById('emptyPosition').style.display = 'none';
                    document.querySelector('#positionsTable').style.display = 'table';
                    data.positions.forEach(p => {
                        const pnlClass = p.pnl >= 0 ? 'pnl-positive' : 'pnl-negative';
                        const changeClass = p.change >= 0 ? 'pnl-positive' : 'pnl-negative';
                        tbody.innerHTML += `<tr>
                            <td class="stock-code">${p.code}</td>
                            <td>${p.name}</td>
                            <td>${p.shares}股</td>
                            <td>${p.cost.toFixed(2)}</td>
                            <td>${p.price.toFixed(2)}</td>
                            <td class="${changeClass}">${formatPct(p.change)}</td>
                            <td>¥${formatMoney(p.value)}</td>
                            <td class="${pnlClass}">${(p.pnl>=0?'+':'') + formatMoney(p.pnl)} (${formatPct(p.pnl_pct)})</td>
                        </tr>`;
                    });
                }

                // 交易记录
                const htbody = document.querySelector('#historyTable tbody');
                htbody.innerHTML = '';
                if (data.history.length === 0) {
                    document.getElementById('emptyHistory').style.display = 'block';
                    document.querySelector('#historyTable').style.display = 'none';
                } else {
                    document.getElementById('emptyHistory').style.display = 'none';
                    document.querySelector('#historyTable').style.display = 'table';
                    data.history.reverse().forEach(h => {
                        const typeClass = h.type === 'buy' ? 'pnl-positive' : 'pnl-negative';
                        htbody.innerHTML += `<tr>
                            <td>${h.date}</td>
                            <td class="${typeClass}">${h.type === 'buy' ? '买入' : '卖出'}</td>
                            <td class="stock-code">${h.code}</td>
                            <td>${h.name}</td>
                            <td>${h.price.toFixed(2)}</td>
                            <td>${h.shares}股</td>
                            <td>¥${formatMoney(h.amount)}</td>
                        </tr>`;
                    });
                }
            } catch (e) { console.error('获取状态失败:', e); }
        }

        async function fetchMarket() {
            try {
                const res = await fetch('/api/market');
                const data = await res.json();
                const tbody = document.querySelector('#marketTable tbody');
                tbody.innerHTML = '';
                data.stocks.forEach(s => {
                    const changeClass = s.change >= 0 ? 'pnl-positive' : 'pnl-negative';
                    tbody.innerHTML += `<tr>
                        <td class="stock-code">${s.code}</td>
                        <td>${s.name}</td>
                        <td>${s.price.toFixed(2)}</td>
                        <td class="${changeClass}">${formatPct(s.change)}</td>
                    </tr>`;
                });
            } catch (e) { console.error('获取行情失败:', e); }
        }

        async function fetchAutoStatus() {
            try {
                const res = await fetch('/api/auto_status');
                const data = await res.json();
                
                const dot = document.getElementById('statusDot');
                const statusEl = document.getElementById('autoStatus');
                
                if (data.is_trading_time) {
                    dot.style.background = '#00d4aa';
                    statusEl.textContent = '自动交易中 | 已扫描' + data.scan_count + '次';
                    statusEl.style.color = '#00d4aa';
                } else {
                    dot.style.background = '#ff9f43';
                    statusEl.textContent = '非交易时间 | 已扫描' + data.scan_count + '次';
                    statusEl.style.color = '#ff9f43';
                }
                
                if (data.last_result) {
                    document.getElementById('tradeLog').textContent = 
                        '上次扫描: ' + (data.last_scan || '-') + '\\n\\n' + data.last_result;
                }
            } catch (e) { console.error('获取自动状态失败:', e); }
        }

        function refresh() {
            fetchStatus();
            fetchMarket();
            fetchAutoStatus();
        }

        async function runScan() {
            const btn = document.querySelector('button[onclick="runScan()"]');
            btn.textContent = '扫描中...';
            btn.disabled = true;
            try {
                const res = await fetch('/api/scan');
                const data = await res.json();
                if (data.success) {
                    alert('扫描交易完成！\\n' + (data.message || ''));
                    refresh();
                } else {
                    alert('扫描失败: ' + (data.error || '未知错误'));
                }
            } catch (e) {
                alert('请求失败: ' + e.message);
            } finally {
                btn.textContent = '扫描交易';
                btn.disabled = false;
            }
        }

        // 初始加载
        refresh();
        // 每10秒自动刷新
        setInterval(refresh, 10000);
    </script>
</body>
</html>
'''


if __name__ == '__main__':
    import sys
    
    # 命令行扫描模式
    if len(sys.argv) > 1 and sys.argv[1] == '--scan':
        print("="*60)
        print("全市场扫描 - 筛选近期放量股票")
        print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        # 直接调用扫描逻辑
        try:
            # 模拟request.json
            class MockRequest:
                def __init__(self):
                    self.json = {'days': 5, 'vol_ratio': 2.0, 'price_change': 1, 'max_pages': 50, 'limit': 9999}
            
            original_request = request
            request = MockRequest()
            
            result = api_scan_volume()
            data = json.loads(result.get_data(as_text=True))
            
            request = original_request
            
            if data.get('success'):
                results = data.get('results', [])
                count = data.get('count', len(results))
                
                print(f"\n筛选结果: 找到 {count} 只放量股票\n")
                print("="*100)
                print(f"{'代码':<8} {'名称':<12} {'现价':<8} {'量比':<8} {'涨跌幅':<10} {'近期量':<12} {'基准量':<12}")
                print("="*100)
                
                for r in results[:50]:
                    vol_tag = "🔥" if r['vol_ratio'] >= 3 else "📈"
                    price_color = "+" if r['price_change'] >= 0 else ""
                    print(f"{r['code']:<8} {r['name']:<12} {r['price']:<8.2f} {vol_tag}{r['vol_ratio']:<7.2f}x "
                          f"{price_color}{r['price_change']:<9.2f}% {r['recent_vol']/10000:<11.0f}万 {r['base_vol']/10000:<11.0f}万")
                
                print("="*100)
                print(f"\n共找到 {count} 只符合条件的股票")
                
                # 保存文件
                output_file = f'放量股票_{datetime.now().strftime("%Y%m%d")}.txt'
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(f"筛选时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"筛选条件: 最近5天，量比≥2.0倍，要求上涨\n")
                    f.write("="*100 + "\n")
                    f.write(f"{'代码':<8} {'名称':<12} {'现价':<8} {'量比':<8} {'涨跌幅':<10} {'近期量':<12} {'基准量':<12}\n")
                    f.write("="*100 + "\n")
                    for r in results:
                        price_color = "+" if r['price_change'] >= 0 else ""
                        f.write(f"{r['code']:<8} {r['name']:<12} {r['price']:<8.2f} {r['vol_ratio']:<8.2f}x "
                                f"{price_color}{r['price_change']:<9.2f}% {r['recent_vol']/10000:<11.0f}万 {r['base_vol']/10000:<11.0f}万\n")
                
                print(f"\n结果已保存到: {output_file}")
            else:
                print(f"扫描失败: {data.get('error', '未知错误')}")
        except Exception as e:
            print(f"执行失败: {str(e)}")
            import traceback
            traceback.print_exc()
        sys.exit(0)
    
    # Web服务器模式
    print("="*50)
    print("量化交易系统 - 全自动交易服务")
    print("="*50)
    print("访问地址: http://localhost:5000")
    print("="*50)
    print("功能说明:")
    print("  - 交易时间(9:30-11:30, 13:00-15:00): 每60秒自动扫描")
    print("  - 非交易时间: 每5分钟检查一次")
    print("  - 符合条件(评分>=75)自动买入")
    print("  - 所有操作实时显示在Web页面")
    print("="*50)
    print("按 Ctrl+C 停止服务")
    print("="*50)
    
    # 启动自动交易后台线程
    trade_thread = threading.Thread(target=auto_trade_loop, daemon=True)
    trade_thread.start()
    print("[启动] 自动交易线程已启动")
    
    app.run(host='0.0.0.0', port=5000, debug=False)
