"""可视化股票分析工具 - Web界面"""
from flask import Flask, render_template, request, jsonify
import pandas as pd
import akshare as ak
import ta
import json

app = Flask(__name__)

# 样本数据存储
samples_file = 'winner_samples.json'

def load_samples():
    try:
        with open(samples_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def save_samples(samples):
    with open(samples_file, 'w', encoding='utf-8') as f:
        json.dump(samples, f, ensure_ascii=False, indent=2)

def get_stock_features(code, date=None):
    """获取股票在指定日期的技术特征"""
    try:
        df = ak.stock_zh_a_hist(symbol=code, period='daily', adjust='qfq')
        if df is None or len(df) < 25:
            return None
        
        if date:
            df['日期'] = pd.to_datetime(df['日期'])
            target = pd.to_datetime(date)
            df = df[df['日期'] <= target]
        
        df = df.tail(60)
        if len(df) < 20:
            return None
        
        close = df['收盘']
        
        # 计算指标
        df['MA5'] = close.rolling(5).mean()
        df['MA10'] = close.rolling(10).mean()
        df['MA20'] = close.rolling(20).mean()
        
        macd = ta.trend.MACD(close)
        df['MACD'] = macd.macd()
        df['MACD_signal'] = macd.macd_signal()
        df['RSI'] = ta.momentum.RSIIndicator(close).rsi()
        df['VOL_MA5'] = df['成交量'].rolling(5).mean()
        
        latest = df.iloc[-1]
        
        # 获取股票名称
        try:
            all_stocks = ak.stock_zh_a_spot_em()
            name_row = all_stocks[all_stocks['代码'] == code]
            name = name_row['名称'].values[0] if len(name_row) > 0 else code
        except:
            name = code
        
        return {
            'code': code,
            'name': name,
            'date': str(latest['日期'])[:10] if '日期' in latest else date,
            'price': float(latest['收盘']),
            'ma5': float(latest['MA5']),
            'ma10': float(latest['MA10']),
            'ma20': float(latest['MA20']),
            'ma_bullish': bool(latest['MA5'] > latest['MA10'] > latest['MA20']),
            'macd': float(latest['MACD']),
            'macd_signal': float(latest['MACD_signal']),
            'macd_golden': bool(latest['MACD'] > latest['MACD_signal']),
            'rsi': float(latest['RSI']),
            'vol_ratio': float(latest['成交量'] / latest['VOL_MA5']) if latest['VOL_MA5'] > 0 else 0,
            'price_vs_ma20': float((latest['收盘'] - latest['MA20']) / latest['MA20'] * 100),
            # K线数据用于图表
            'kline': df.tail(30)[['日期', '开盘', '收盘', '最高', '最低', '成交量']].to_dict('records')
        }
    except Exception as e:
        print(f"Error: {e}")
        return None

def analyze_all_samples():
    """分析所有样本的共同特征"""
    samples = load_samples()
    if not samples:
        return None
    
    features = {
        'ma_bullish': 0,
        'macd_golden': 0,
        'rsi_sum': 0,
        'vol_ratio_sum': 0,
        'price_vs_ma20_sum': 0,
        'count': len(samples)
    }
    
    for s in samples:
        if s.get('ma_bullish'):
            features['ma_bullish'] += 1
        if s.get('macd_golden'):
            features['macd_golden'] += 1
        features['rsi_sum'] += s.get('rsi', 50)
        features['vol_ratio_sum'] += s.get('vol_ratio', 1)
        features['price_vs_ma20_sum'] += s.get('price_vs_ma20', 0)
    
    n = features['count']
    return {
        'count': n,
        'ma_bullish_pct': features['ma_bullish'] / n * 100,
        'macd_golden_pct': features['macd_golden'] / n * 100,
        'rsi_avg': features['rsi_sum'] / n,
        'vol_ratio_avg': features['vol_ratio_sum'] / n,
        'price_vs_ma20_avg': features['price_vs_ma20_sum'] / n,
    }

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>牛股特征分析器</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Microsoft YaHei', sans-serif; background: #1a1a2e; color: #eee; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { text-align: center; color: #00d4ff; margin-bottom: 20px; }
        
        .input-section { background: #16213e; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
        .input-row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
        input, select { padding: 10px 15px; border: none; border-radius: 5px; background: #0f3460; color: #fff; }
        input:focus { outline: 2px solid #00d4ff; }
        button { padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; }
        .btn-primary { background: #00d4ff; color: #000; }
        .btn-success { background: #00ff88; color: #000; }
        .btn-danger { background: #ff4757; color: #fff; }
        button:hover { opacity: 0.8; }
        
        .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        .card { background: #16213e; padding: 20px; border-radius: 10px; }
        .card h3 { color: #00d4ff; margin-bottom: 15px; border-bottom: 1px solid #0f3460; padding-bottom: 10px; }
        
        .feature-item { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #0f3460; }
        .feature-label { color: #aaa; }
        .feature-value { font-weight: bold; }
        .positive { color: #00ff88; }
        .negative { color: #ff4757; }
        
        .chart { height: 300px; }
        
        .samples-list { max-height: 400px; overflow-y: auto; }
        .sample-item { display: flex; justify-content: space-between; align-items: center; padding: 10px; 
                       background: #0f3460; margin-bottom: 5px; border-radius: 5px; }
        .sample-info { flex: 1; }
        .sample-code { color: #00d4ff; font-weight: bold; }
        .sample-gain { color: #00ff88; }
        
        .stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 15px; }
        .stat-box { background: #0f3460; padding: 15px; border-radius: 8px; text-align: center; }
        .stat-value { font-size: 24px; font-weight: bold; color: #00d4ff; }
        .stat-label { color: #aaa; font-size: 12px; margin-top: 5px; }
        
        .progress-bar { height: 20px; background: #0f3460; border-radius: 10px; overflow: hidden; margin: 5px 0; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, #00d4ff, #00ff88); transition: width 0.3s; }
        
        #loading { display: none; position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%);
                   background: rgba(0,0,0,0.8); padding: 20px 40px; border-radius: 10px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 牛股特征分析器</h1>
        
        <div class="input-section">
            <div class="input-row">
                <input type="text" id="stockCode" placeholder="股票代码 如 002309" style="width: 150px;">
                <input type="date" id="stockDate" placeholder="分析日期(可选)">
                <button class="btn-primary" onclick="analyzeStock()">分析股票</button>
                <button class="btn-success" onclick="addToSamples()">添加到样本库</button>
                <span style="margin-left: 20px; color: #aaa;">|</span>
                <input type="number" id="gainPct" placeholder="涨幅%" style="width: 100px;" value="30">
                <button class="btn-primary" onclick="findWinners()">自动找牛股</button>
            </div>
        </div>
        
        <div class="grid">
            <div class="card">
                <h3>📊 当前股票分析</h3>
                <div id="stockInfo">
                    <p style="color: #aaa;">输入股票代码后点击"分析股票"</p>
                </div>
                <div id="klineChart" class="chart"></div>
            </div>
            
            <div class="card">
                <h3>📈 技术指标</h3>
                <div id="indicators">
                    <p style="color: #aaa;">等待分析...</p>
                </div>
            </div>
        </div>
        
        <div class="grid" style="margin-top: 20px;">
            <div class="card">
                <h3>🏆 样本库 (<span id="sampleCount">0</span>只)</h3>
                <div class="samples-list" id="samplesList">
                    <p style="color: #aaa;">暂无样本，分析股票后点击"添加到样本库"</p>
                </div>
            </div>
            
            <div class="card">
                <h3>🔍 共同特征分析</h3>
                <div id="commonFeatures">
                    <p style="color: #aaa;">添加样本后自动分析共同特征</p>
                </div>
            </div>
        </div>
    </div>
    
    <div id="loading">⏳ 加载中...</div>
    
    <script>
        let currentStock = null;
        let klineChart = null;
        
        function showLoading() { document.getElementById('loading').style.display = 'block'; }
        function hideLoading() { document.getElementById('loading').style.display = 'none'; }
        
        async function analyzeStock() {
            const code = document.getElementById('stockCode').value.trim();
            const date = document.getElementById('stockDate').value;
            if (!code) { alert('请输入股票代码'); return; }
            
            showLoading();
            try {
                const res = await fetch(`/api/analyze?code=${code}&date=${date}`);
                const data = await res.json();
                hideLoading();
                
                if (data.error) { alert(data.error); return; }
                
                currentStock = data;
                renderStockInfo(data);
                renderIndicators(data);
                renderKline(data.kline);
            } catch (e) {
                hideLoading();
                alert('分析失败: ' + e.message);
            }
        }
        
        function renderStockInfo(data) {
            document.getElementById('stockInfo').innerHTML = `
                <div style="font-size: 24px; margin-bottom: 10px;">
                    <span class="sample-code">${data.code}</span> ${data.name}
                </div>
                <div class="feature-item">
                    <span class="feature-label">当前价格</span>
                    <span class="feature-value">${data.price.toFixed(2)}</span>
                </div>
                <div class="feature-item">
                    <span class="feature-label">分析日期</span>
                    <span class="feature-value">${data.date}</span>
                </div>
            `;
        }
        
        function renderIndicators(data) {
            const maClass = data.ma_bullish ? 'positive' : 'negative';
            const macdClass = data.macd_golden ? 'positive' : 'negative';
            const rsiClass = data.rsi < 30 ? 'positive' : (data.rsi > 70 ? 'negative' : '');
            
            document.getElementById('indicators').innerHTML = `
                <div class="feature-item">
                    <span class="feature-label">均线排列</span>
                    <span class="feature-value ${maClass}">${data.ma_bullish ? '多头 ✓' : '非多头'}</span>
                </div>
                <div class="feature-item">
                    <span class="feature-label">MACD状态</span>
                    <span class="feature-value ${macdClass}">${data.macd_golden ? '金叉 ✓' : '死叉'}</span>
                </div>
                <div class="feature-item">
                    <span class="feature-label">RSI</span>
                    <span class="feature-value ${rsiClass}">${data.rsi.toFixed(1)}</span>
                </div>
                <div class="feature-item">
                    <span class="feature-label">量比</span>
                    <span class="feature-value">${data.vol_ratio.toFixed(2)}</span>
                </div>
                <div class="feature-item">
                    <span class="feature-label">距MA20</span>
                    <span class="feature-value">${data.price_vs_ma20.toFixed(1)}%</span>
                </div>
                <div class="feature-item">
                    <span class="feature-label">MA5/MA10/MA20</span>
                    <span class="feature-value">${data.ma5.toFixed(2)} / ${data.ma10.toFixed(2)} / ${data.ma20.toFixed(2)}</span>
                </div>
            `;
        }
        
        function renderKline(klineData) {
            if (!klineChart) {
                klineChart = echarts.init(document.getElementById('klineChart'));
            }
            
            const dates = klineData.map(d => String(d['日期']).slice(0, 10));
            const values = klineData.map(d => [d['开盘'], d['收盘'], d['最低'], d['最高']]);
            
            klineChart.setOption({
                backgroundColor: 'transparent',
                xAxis: { data: dates, axisLabel: { color: '#aaa' } },
                yAxis: { scale: true, axisLabel: { color: '#aaa' } },
                series: [{
                    type: 'candlestick',
                    data: values,
                    itemStyle: { color: '#ff4757', color0: '#00ff88', borderColor: '#ff4757', borderColor0: '#00ff88' }
                }]
            });
        }
        
        async function addToSamples() {
            if (!currentStock) { alert('请先分析一只股票'); return; }
            
            const res = await fetch('/api/add_sample', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(currentStock)
            });
            const data = await res.json();
            alert(data.message);
            loadSamples();
        }
        
        async function loadSamples() {
            const res = await fetch('/api/samples');
            const data = await res.json();
            
            document.getElementById('sampleCount').textContent = data.samples.length;
            
            if (data.samples.length === 0) {
                document.getElementById('samplesList').innerHTML = '<p style="color: #aaa;">暂无样本</p>';
                document.getElementById('commonFeatures').innerHTML = '<p style="color: #aaa;">添加样本后自动分析</p>';
                return;
            }
            
            let html = '';
            data.samples.forEach((s, i) => {
                html += `
                    <div class="sample-item">
                        <div class="sample-info">
                            <span class="sample-code">${s.code}</span> ${s.name}
                            <span style="color: #aaa; margin-left: 10px;">${s.date}</span>
                        </div>
                        <button class="btn-danger" onclick="removeSample(${i})" style="padding: 5px 10px;">删除</button>
                    </div>
                `;
            });
            document.getElementById('samplesList').innerHTML = html;
            
            // 渲染共同特征
            if (data.analysis) {
                const a = data.analysis;
                document.getElementById('commonFeatures').innerHTML = `
                    <div class="stats-grid">
                        <div class="stat-box">
                            <div class="stat-value">${a.count}</div>
                            <div class="stat-label">样本数量</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-value">${a.rsi_avg.toFixed(1)}</div>
                            <div class="stat-label">平均RSI</div>
                        </div>
                        <div class="stat-box">
                            <div class="stat-value">${a.vol_ratio_avg.toFixed(2)}</div>
                            <div class="stat-label">平均量比</div>
                        </div>
                    </div>
                    <div style="margin-top: 15px;">
                        <div class="feature-item">
                            <span>均线多头占比</span>
                            <span>${a.ma_bullish_pct.toFixed(0)}%</span>
                        </div>
                        <div class="progress-bar"><div class="progress-fill" style="width: ${a.ma_bullish_pct}%"></div></div>
                        
                        <div class="feature-item">
                            <span>MACD金叉占比</span>
                            <span>${a.macd_golden_pct.toFixed(0)}%</span>
                        </div>
                        <div class="progress-bar"><div class="progress-fill" style="width: ${a.macd_golden_pct}%"></div></div>
                    </div>
                `;
            }
        }
        
        async function removeSample(index) {
            await fetch(`/api/remove_sample/${index}`, { method: 'DELETE' });
            loadSamples();
        }
        
        async function findWinners() {
            const gain = document.getElementById('gainPct').value || 30;
            showLoading();
            try {
                const res = await fetch(`/api/find_winners?min_gain=${gain}`);
                const data = await res.json();
                hideLoading();
                alert(`找到 ${data.count} 只牛股，已添加到样本库`);
                loadSamples();
            } catch (e) {
                hideLoading();
                alert('查找失败: ' + e.message);
            }
        }
        
        // 页面加载时获取样本
        loadSamples();
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return HTML_TEMPLATE

@app.route('/api/analyze')
def api_analyze():
    code = request.args.get('code', '').strip()
    date = request.args.get('date', '').strip() or None
    
    if not code:
        return jsonify({'error': '请输入股票代码'})
    
    # 补齐代码
    code = code.zfill(6)
    
    data = get_stock_features(code, date)
    if not data:
        return jsonify({'error': '获取数据失败，请检查股票代码'})
    
    return jsonify(data)

@app.route('/api/samples')
def api_samples():
    samples = load_samples()
    analysis = analyze_all_samples()
    return jsonify({'samples': samples, 'analysis': analysis})

@app.route('/api/add_sample', methods=['POST'])
def api_add_sample():
    data = request.json
    samples = load_samples()
    
    # 检查是否已存在
    for s in samples:
        if s['code'] == data['code'] and s['date'] == data['date']:
            return jsonify({'message': '该样本已存在'})
    
    samples.append(data)
    save_samples(samples)
    return jsonify({'message': f"已添加 {data['code']} {data['name']}"})

@app.route('/api/remove_sample/<int:index>', methods=['DELETE'])
def api_remove_sample(index):
    samples = load_samples()
    if 0 <= index < len(samples):
        removed = samples.pop(index)
        save_samples(samples)
        return jsonify({'message': f"已删除 {removed['code']}"})
    return jsonify({'error': '索引无效'})

@app.route('/api/find_winners')
def api_find_winners():
    min_gain = int(request.args.get('min_gain', 30))
    # 简化版：只找前100只股票中的牛股
    try:
        df = ak.stock_zh_a_spot_em()
        df = df[df['代码'].str.match(r'^(60|00)')]
        df = df[~df['名称'].str.contains('ST')]
        df = df.nlargest(100, '成交额')
        
        count = 0
        samples = load_samples()
        
        for _, row in df.iterrows():
            code = row['代码']
            data = get_stock_features(code)
            if data and data.get('price_vs_ma20', 0) > min_gain * 0.5:
                # 检查是否已存在
                exists = any(s['code'] == code for s in samples)
                if not exists:
                    samples.append(data)
                    count += 1
                    if count >= 10:
                        break
        
        save_samples(samples)
        return jsonify({'count': count})
    except Exception as e:
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    print("="*50)
    print("牛股特征分析器已启动")
    print("打开浏览器访问: http://127.0.0.1:5000")
    print("="*50)
    app.run(debug=True, port=5000)
