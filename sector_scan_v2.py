"""
板块异动扫描 V2 - 不依赖akshare，直接请求API
"""
import requests
import pandas as pd
import json
import os
from datetime import datetime

def log(msg):
    print(msg, flush=True)

# 清除代理
for key in list(os.environ.keys()):
    if 'proxy' in key.lower():
        del os.environ[key]

session = requests.Session()
session.trust_env = False
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://quote.eastmoney.com/'
})


def get_sector_list_em():
    """从东方财富获取概念板块列表"""
    log("  尝试东方财富API...")
    url = 'https://79.push2.eastmoney.com/api/qt/clist/get'
    params = {
        'pn': 1, 'pz': 100, 'po': 1, 'np': 1,
        'ut': 'bd1d9ddb04089700cf9c27f6f7426281',
        'fltt': 2, 'invt': 2, 'fid': 'f3',
        'fs': 'm:90+t:3+f:!50',
        'fields': 'f2,f3,f4,f12,f14,f104,f105'
    }
    try:
        r = session.get(url, params=params, timeout=15)
        data = r.json()
        if data.get('data') and data['data'].get('diff'):
            items = data['data']['diff']
            results = []
            for item in items:
                results.append({
                    '板块代码': item.get('f12', ''),
                    '板块名称': item.get('f14', ''),
                    '涨跌幅': item.get('f3', 0),
                    '上涨家数': item.get('f104', 0),
                    '下跌家数': item.get('f105', 0),
                })
            return results
    except Exception as e:
        log(f"    东方财富失败: {e}")
    return None


def get_sector_list_ths():
    """从同花顺获取行业板块"""
    log("  尝试同花顺API...")
    url = 'https://dq.10jqka.com.cn/fuyao/hot_list_data/out/hot_list/v1/stock'
    params = {'stock_type': 'block', 'type': 'gnbk', 'list_type': 'normal'}
    headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.10jqka.com.cn/'}
    try:
        r = session.get(url, params=params, headers=headers, timeout=15)
        data = r.json()
        if data.get('data') and data['data'].get('stock_list'):
            items = data['data']['stock_list']
            results = []
            for item in items[:50]:
                results.append({
                    '板块代码': item.get('code', ''),
                    '板块名称': item.get('name', ''),
                    '涨跌幅': float(item.get('rate', 0)),
                })
            return results
    except Exception as e:
        log(f"    同花顺失败: {e}")
    return None


def get_sector_list_sina():
    """从新浪获取行业板块"""
    log("  尝试新浪API...")
    url = 'https://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/Market_Center.getHQNodes'
    try:
        r = session.get(url, timeout=15)
        # 新浪返回的是所有板块分类，需要解析
        text = r.text
        if text and 'null' not in text:
            log(f"    新浪有响应，长度{len(text)}")
    except Exception as e:
        log(f"    新浪失败: {e}")
    return None


def get_stock_kline(code, days=80):
    """获取个股K线"""
    code = str(code).zfill(6)
    if code.startswith('6'):
        kcode = f'sh{code}'
    else:
        kcode = f'sz{code}'
    
    url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={kcode},day,,,{days},qfq'
    try:
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
        
        df = pd.DataFrame([d[:6] for d in days_data], 
                        columns=['日期','开盘','收盘','最高','最低','成交量'])
        for col in ['开盘','收盘','最高','最低','成交量']:
            df[col] = df[col].astype(float)
        df['日期'] = pd.to_datetime(df['日期'])
        df['涨跌幅'] = df['收盘'].pct_change() * 100
        return df
    except:
        return None


def get_industry_stocks():
    """获取行业龙头股 - 用于估算板块走势"""
    # 预定义的行业龙头股列表
    industry_leaders = {
        '人工智能': ['002230', '300474', '002415'],  # 科大讯飞、景嘉微、海康威视
        '机器人': ['002747', '300024', '300607'],    # 埃斯顿、机器人、拓斯达
        '芯片': ['002371', '603501', '688981'],      # 北方华创、韦尔股份、中芯国际
        '新能源车': ['002594', '300750', '002466'],   # 比亚迪、宁德时代、天齐锂业
        '光伏': ['601012', '002459', '600438'],       # 隆基绿能、晶澳科技、通威股份
        '医药': ['600276', '000538', '300760'],       # 恒瑞医药、云南白药、迈瑞医疗
        '白酒': ['600519', '000858', '000568'],       # 贵州茅台、五粮液、泸州老窖
        '银行': ['601398', '601939', '600036'],       # 工商银行、建设银行、招商银行
        '军工': ['600893', '000768', '600760'],       # 航发动力、中航西飞、中航沈飞
        '消费电子': ['002475', '002241', '603160'],   # 立讯精密、歌尔股份、汇顶科技
        '半导体设备': ['002371', '688012', '300661'],  # 北方华创、中微公司、圣邦股份
        '储能': ['002074', '300014', '300724'],       # 国轩高科、亿纬锂能、捷佳伟创
        '传媒': ['002027', '300413', '002602'],       # 分众传媒、芒果超媒、世纪华通
        '游戏': ['002555', '002624', '002174'],       # 三七互娱、完美世界、游族网络
        '建材': ['600585', '000401', '002271'],       # 海螺水泥、冀东水泥、东方雨虹
    }
    return industry_leaders


def estimate_sector_trend(stocks):
    """用成分股估算板块走势"""
    all_data = []
    for code in stocks:
        df = get_stock_kline(code)
        if df is not None and len(df) > 30:
            all_data.append(df[['日期', '涨跌幅']].set_index('日期')['涨跌幅'])
    
    if len(all_data) == 0:
        return None
    
    combined = pd.concat(all_data, axis=1)
    return combined.mean(axis=1)


def detect_sector_signal(daily_returns):
    """检测板块异动信号"""
    if daily_returns is None or len(daily_returns) < 45:
        return False, None, "数据不足"
    
    daily_returns = daily_returns.dropna()
    if len(daily_returns) < 45:
        return False, None, "有效数据不足"
    
    old_period = daily_returns.iloc[:-15]
    recent_15d = daily_returns.iloc[-15:]
    recent_5d = daily_returns.iloc[-5:]
    
    # 找早期爆发
    surge_days = old_period[old_period > 3.0]
    if len(surge_days) == 0:
        return False, None, "无早期爆发"
    
    max_surge_value = surge_days.max()
    max_surge_idx = surge_days.idxmax()
    
    # 计算回撤
    after_surge = daily_returns[daily_returns.index >= max_surge_idx]
    if len(after_surge) < 10:
        return False, None, "爆发后数据不足"
    
    cumsum = after_surge.cumsum()
    max_gain = cumsum.max()
    current_gain = cumsum.iloc[-1]
    drawdown = max_gain - current_gain
    
    recent_15d_sum = recent_15d.sum()
    recent_5d_sum = recent_5d.sum()
    
    # 检查条件
    if drawdown < 5:
        return False, None, f"回撤不足({drawdown:.1f}%)"
    if drawdown > 15:
        return False, None, f"回撤过大({drawdown:.1f}%)"
    if recent_15d_sum > 5:
        return False, None, f"近15日涨太多({recent_15d_sum:.1f}%)"
    if recent_5d_sum < -5:
        return False, None, f"近5日跌太多({recent_5d_sum:.1f}%)"
    
    return True, {
        'surge_date': max_surge_idx.strftime('%Y-%m-%d'),
        'surge_value': round(max_surge_value, 2),
        'drawdown': round(drawdown, 2),
        'recent_15d': round(recent_15d_sum, 2),
        'recent_5d': round(recent_5d_sum, 2)
    }, "符合条件"


def run_scan():
    log("="*60)
    log("板块异动扫描 V2")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*60)
    
    log("\n策略说明:")
    log("  条件: 早期爆发(>3%) → 回撤5-15% → 近期企稳")
    
    # 尝试获取板块列表
    log("\n[1] 获取板块列表...")
    sectors = get_sector_list_em()
    if not sectors:
        sectors = get_sector_list_ths()
    if not sectors:
        log("  API获取失败，使用预定义行业龙头")
        sectors = None
    
    if sectors:
        log(f"  获取到 {len(sectors)} 个板块")
    
    # 使用预定义行业
    log("\n[2] 使用预定义行业龙头分析...")
    industry_leaders = get_industry_stocks()
    log(f"  共 {len(industry_leaders)} 个行业")
    
    results = []
    for industry, stocks in industry_leaders.items():
        log(f"\n  分析: {industry}")
        
        trend = estimate_sector_trend(stocks)
        if trend is None:
            log(f"    -> 无法获取数据")
            continue
        
        log(f"    数据: {len(trend)}天")
        
        is_signal, details, reason = detect_sector_signal(trend)
        
        if is_signal:
            log(f"    -> ✓ 符合条件!")
            log(f"       爆发{details['surge_date']} +{details['surge_value']}%")
            log(f"       回撤{details['drawdown']}% 近5日{details['recent_5d']:+.1f}%")
            results.append({
                '板块': industry,
                '龙头股': stocks,
                **details
            })
        else:
            log(f"    -> ✗ {reason}")
    
    # 结果
    log("\n" + "="*60)
    log("扫描结果")
    log("="*60)
    
    if results:
        log(f"\n发现 {len(results)} 个潜力板块:")
        for r in results:
            log(f"\n  【{r['板块']}】")
            log(f"    爆发日期: {r['surge_date']} +{r['surge_value']}%")
            log(f"    回撤幅度: {r['drawdown']}%")
            log(f"    近5日: {r['recent_5d']:+.1f}%")
            log(f"    龙头股: {', '.join(r['龙头股'])}")
    else:
        log("\n当前无符合条件的板块")
    
    log("\n" + "="*60)


if __name__ == "__main__":
    run_scan()
