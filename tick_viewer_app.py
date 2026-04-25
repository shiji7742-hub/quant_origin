#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
逐笔成交查看Web应用
"""

from flask import Flask, render_template_string, jsonify, request
from flask_cors import CORS
import akshare as ak
import pandas as pd
from datetime import datetime

app = Flask(__name__)
CORS(app)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>逐笔成交查看器</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: "Microsoft YaHei", sans-serif; background: #1a1a2e; color: #fff; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        .header { background: #16213e; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
        h1 { color: #00d4ff; margin-bottom: 15px; }
        .search-box { display: flex; gap: 10px; align-items: center; margin-bottom: 15px; }
        input { padding: 10px 15px; border: none; border-radius: 5px; background: #0f3460; color: #fff; font-size: 16px; }
        button { padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; }
        .btn-primary { background: #00d4ff; color: #000; }
        .btn-primary:hover { background: #00b8e6; }
        .stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin-bottom: 20px; }
        .stat-card { background: #16213e; padding: 15px; border-radius: 8px; text-align: center; }
        .stat-value { font-size: 24px; color: #00d4ff; font-weight: bold; }
        .stat-label { color: #888; font-size: 12px; margin-top: 5px; }
        .table-container { background: #16213e; border-radius: 10px; overflow: hidden; }
        table { width: 100%; border-collapse: collapse; }
        th { background: #0f3460; padding: 12px; text-align: left; color: #00d4ff; }
        td { padding: 10px 12px; border-bottom: 1px solid #0f3460; }
        .buy { color: #ff4757; }
        .sell { color: #2ed573; }
        .neutral { color: #888; }
        .big1 { background: rgba(255, 215, 0, 0.1); }
        .big2 { background: rgba(255, 215, 0, 0.2); }
        .big3 { background: rgba(255, 215, 0, 0.3); }
        #status { padding: 20px; text-align: center; color: #888; }
        #error { color: #ff4757; padding: 20px; text-align: center; display: none; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>逐笔成交查看器</h1>
            <div class="search-box">
                <input type="text" id="code" placeholder="股票代码 如 002279" value="002279">
                <button class="btn-primary" id="searchBtn" onclick="search()">查询</button>
                <span id="stockInfo" style="color: #888; margin-left: 20px;"></span>
            </div>
        </div>
        
        <div id="error"></div>
        
        <div class="stats" id="stats" style="display: none;">
            <div class="stat-card"><div class="stat-value" id="totalCount">0</div><div class="stat-label">总笔数</div></div>
            <div class="stat-card"><div class="stat-value" id="totalAmount">0</div><div class="stat-label">总金额(万)</div></div>
            <div class="stat-card"><div class="stat-value" id="buyAmount" style="color:#ff4757">0</div><div class="stat-label">买盘(万)</div></div>
            <div class="stat-card"><div class="stat-value" id="sellAmount" style="color:#2ed573">0</div><div class="stat-label">卖盘(万)</div></div>
        </div>
        
        <div class="table-container">
            <div id="status">请输入股票代码后点击查询</div>
            <table id="table" style="display: none;">
                <thead>
                    <tr><th>时间</th><th>方向</th><th>价格</th><th>数量</th><th>金额(万)</th><th>类型</th></tr>
                </thead>
                <tbody id="tbody"></tbody>
            </table>
        </div>
    </div>
    
    <script>
        function search() {
            var code = document.getElementById('code').value.trim();
            if (!code) { alert('请输入股票代码'); return; }
            
            document.getElementById('searchBtn').textContent = '查询中...';
            document.getElementById('searchBtn').disabled = true;
            document.getElementById('status').textContent = '正在加载数据...';
            document.getElementById('status').style.display = 'block';
            document.getElementById('table').style.display = 'none';
            document.getElementById('stats').style.display = 'none';
            document.getElementById('error').style.display = 'none';
            
            fetch('/api/tick/' + code)
                .then(function(res) { return res.json(); })
                .then(function(data) {
                    document.getElementById('searchBtn').textContent = '查询';
                    document.getElementById('searchBtn').disabled = false;
                    
                    if (data.error) {
                        document.getElementById('error').textContent = data.error;
                        document.getElementById('error').style.display = 'block';
                        document.getElementById('status').style.display = 'none';
                        return;
                    }
                    
                    document.getElementById('stockInfo').textContent = data.name + ' | 最新价: ' + (data.price || '--');
                    document.getElementById('totalCount').textContent = data.stats.count;
                    document.getElementById('totalAmount').textContent = data.stats.total.toFixed(2);
                    document.getElementById('buyAmount').textContent = data.stats.buy.toFixed(2);
                    document.getElementById('sellAmount').textContent = data.stats.sell.toFixed(2);
                    document.getElementById('stats').style.display = 'grid';
                    
                    var tbody = document.getElementById('tbody');
                    tbody.innerHTML = '';
                    
                    data.ticks.forEach(function(t) {
                        var tr = document.createElement('tr');
                        var dirClass = t.dir === '买盘' ? 'buy' : (t.dir === '卖盘' ? 'sell' : 'neutral');
                        var dirText = t.dir === '买盘' ? '🔴买' : (t.dir === '卖盘' ? '🟢卖' : '⚪中');
                        var bigClass = t.amount >= 100 ? 'big3' : (t.amount >= 50 ? 'big2' : (t.amount >= 20 ? 'big1' : ''));
                        var flag = t.amount >= 100 ? '💎💎💎' : (t.amount >= 50 ? '💎💎' : (t.amount >= 20 ? '💎' : ''));
                        tr.className = bigClass;
                        tr.innerHTML = '<td>' + t.time + '</td><td class="' + dirClass + '">' + dirText + '</td><td>' + t.price.toFixed(2) + '</td><td>' + t.vol + '</td><td>' + flag + ' ' + t.amount.toFixed(2) + '</td><td>' + t.type + '</td>';
                        tbody.appendChild(tr);
                    });
                    
                    document.getElementById('status').style.display = 'none';
                    document.getElementById('table').style.display = 'table';
                })
                .catch(function(err) {
                    document.getElementById('searchBtn').textContent = '查询';
                    document.getElementById('searchBtn').disabled = false;
                    document.getElementById('error').textContent = '请求失败: ' + err.message;
                    document.getElementById('error').style.display = 'block';
                    document.getElementById('status').style.display = 'none';
                });
        }
        
        document.getElementById('code').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') search();
        });
    </script>
</body>
</html>
'''

def get_symbol(code):
    if code.startswith('6'):
        return f"sh{code}"
    return f"sz{code}"

def get_name(code):
    try:
        df = ak.stock_zh_a_spot_em()
        row = df[df['代码'] == code]
        if not row.empty:
            return row.iloc[0]['名称']
    except:
        pass
    return code

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/tick/<code>')
def get_tick(code):
    try:
        symbol = get_symbol(code)
        df = None
        
        # 尝试获取实时数据
        try:
            df = ak.stock_zh_a_tick_tx_js(symbol=symbol)
            print(f"[实时接口] 获取到 {len(df) if df is not None else 0} 条")
            if df is not None:
                print(f"[实时接口] 列名: {df.columns.tolist()}")
        except Exception as e:
            print(f"[实时接口] 失败: {e}")
        
        if df is None or len(df) == 0:
            try:
                df = ak.stock_zh_a_tick_tx(symbol=symbol)
                print(f"[备用接口] 获取到 {len(df) if df is not None else 0} 条")
                if df is not None:
                    print(f"[备用接口] 列名: {df.columns.tolist()}")
            except Exception as e:
                print(f"[备用接口] 失败: {e}")
        
        if df is None or len(df) == 0:
            return jsonify({'error': '暂无数据，可能是非交易时间或股票代码错误'})
        
        # 统一列名（不同接口返回的列名可能不同）
        # 先打印原始列名
        print(f"[原始列名] {df.columns.tolist()}")
        
        col_map = {
            '成交价格': '成交价',
            'price': '成交价',
            '价格': '成交价',
            '成交数量': '成交量',
            'volume': '成交量',
            '数量': '成交量',
            '成交时刻': '成交时间',
            'time': '成交时间',
            '时间': '成交时间',
            '买卖方向': '性质',
            '方向': '性质',
            'direction': '性质',
        }
        df = df.rename(columns=col_map)
        
        # 如果有成交金额列，可以直接用
        if '成交金额' in df.columns and '成交价' not in df.columns:
            # 从成交金额反推成交价
            if '成交量' in df.columns:
                df['成交价'] = df['成交金额'] / df['成交量']
        
        print(f"[处理后] 列名: {df.columns.tolist()}")
        
        # 检查必要的列是否存在
        if '成交价' not in df.columns:
            return jsonify({'error': f'数据格式错误，缺少成交价列。实际列名: {df.columns.tolist()}'})
        if '成交量' not in df.columns:
            return jsonify({'error': f'数据格式错误，缺少成交量列。实际列名: {df.columns.tolist()}'})
        
        # 处理数据
        df['金额'] = df['成交价'].astype(float) * df['成交量'].astype(float) / 10000
        
        # 分类
        def get_type(amt):
            if amt >= 100: return '超大单'
            if amt >= 50: return '大单'
            if amt >= 20: return '中单'
            return '小单'
        
        ticks = []
        for _, row in df.iterrows():
            direction = row.get('性质', '')
            if not direction:
                direction = '中性盘'
            ticks.append({
                'time': str(row.get('成交时间', ''))[:8],
                'dir': direction,
                'price': float(row['成交价']),
                'vol': int(row['成交量']),
                'amount': float(row['金额']),
                'type': get_type(row['金额'])
            })
        
        # 统计
        if '性质' in df.columns:
            buy = df[df['性质'] == '买盘']['金额'].sum()
            sell = df[df['性质'] == '卖盘']['金额'].sum()
        else:
            buy = 0
            sell = 0
        
        name = get_name(code)
        price = df['成交价'].iloc[-1] if len(df) > 0 else None
        
        return jsonify({
            'code': code,
            'name': name,
            'price': float(price) if price else None,
            'ticks': ticks,
            'stats': {
                'count': len(df),
                'total': float(df['金额'].sum()),
                'buy': float(buy),
                'sell': float(sell)
            }
        })
    except Exception as e:
        import traceback
        print(f"[错误] {e}")
        traceback.print_exc()
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    print("=" * 50)
    print("逐笔成交查看器")
    print("访问: http://localhost:5001")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5001, debug=True)
