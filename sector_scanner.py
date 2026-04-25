"""板块异动扫描器 - 寻找爆发后退潮的板块"""
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def get_all_sectors():
    """获取所有概念板块（带当日涨跌幅）"""
    try:
        df = ak.stock_board_concept_name_em()
        return df
    except Exception as e:
        print(f"获取板块列表失败: {e}")
        return pd.DataFrame()

def get_sector_history_via_etf(sector_name, days=30):
    """
    通过板块成分股的龙头股来估算板块走势
    """
    try:
        # 获取板块成分股
        df = ak.stock_board_concept_cons_em(symbol=sector_name)
        if df is None or len(df) == 0:
            return None
        
        # 取涨幅最大的3只作为代表
        top_stocks = df.nlargest(3, '涨跌幅')['代码'].tolist()
        
        all_data = []
        for symbol in top_stocks:
            try:
                hist = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
                if hist is not None and len(hist) >= days:
                    hist = hist.tail(days)
                    hist['涨跌幅'] = hist['收盘'].pct_change() * 100
                    hist['日期'] = pd.to_datetime(hist['日期'])
                    all_data.append(hist[['日期', '涨跌幅']].set_index('日期'))
            except:
                continue
        
        if len(all_data) == 0:
            return None
        
        combined = pd.concat(all_data, axis=1)
        return combined.mean(axis=1)
    except:
        return None

def analyze_sector_surge_simple(sector_row):
    """
    简单分析板块是否有异动特征
    基于当前数据快速判断
    """
    try:
        name = sector_row['板块名称']
        change = float(sector_row['涨跌幅'])
        up_count = int(sector_row['上涨家数'])
        down_count = int(sector_row['下跌家数'])
        total = up_count + down_count
        
        # 计算上涨比例
        up_ratio = up_count / total if total > 0 else 0
        
        return {
            '板块名称': name,
            '板块代码': sector_row['板块代码'],
            '当日涨幅': change,
            '上涨家数': up_count,
            '下跌家数': down_count,
            '上涨比例': round(up_ratio * 100, 1),
            '领涨股': sector_row.get('领涨股票', ''),
            '领涨涨幅': sector_row.get('领涨股票-涨跌幅', 0)
        }
    except:
        return None

def detect_sector_surge(daily_returns, surge_threshold=2.0, drop_threshold=-1.0):
    """
    检测板块异动模式：早期爆发后未主升，一直徘徊或下杀
    
    逻辑：
    1. 在30-60天前有过爆发（单日涨幅>3%）
    2. 爆发后没有开启主升（累计涨幅不超过爆发涨幅的2倍）
    3. 当前价格相对爆发时没有明显上涨，甚至下跌
    """
    if daily_returns is None or len(daily_returns) < 30:
        return False, None
    
    # 去掉NaN
    daily_returns = daily_returns.dropna()
    
    if len(daily_returns) < 30:
        return False, None
    
    # 分成两段：前半段（1-2个月前）和后半段（近期）
    old_period = daily_returns.iloc[:-15]  # 15天前的数据
    recent_period = daily_returns.iloc[-15:]  # 最近15天
    
    # 在前半段找爆发日（单日涨幅 > 3%）
    surge_days = old_period[old_period > 3.0]
    
    if len(surge_days) == 0:
        return False, None
    
    # 找最大的一次爆发
    max_surge_idx = surge_days.idxmax()
    max_surge_value = surge_days.max()
    
    # 爆发后到现在的数据
    after_surge = daily_returns[daily_returns.index >= max_surge_idx]
    
    if len(after_surge) < 10:
        return False, None
    
    # 计算爆发后的累计涨幅
    cumulative_after = after_surge.sum()
    
    # 计算近期表现
    recent_sum = recent_period.sum()
    
    # 计算从爆发后高点的回撤
    cumsum = after_surge.cumsum()
    max_gain = cumsum.max()
    current_gain = cumsum.iloc[-1]
    drawdown_from_high = max_gain - current_gain
    
    # 判断是否"未主升"：
    # 1. 爆发后累计涨幅 < 爆发涨幅的3倍（没有走出主升）
    # 2. 或者从高点回撤超过5%
    # 3. 近期表现不佳（近15日累计 < 5%）
    no_main_rise = (cumulative_after < max_surge_value * 3) or (drawdown_from_high > 5)
    recent_weak = recent_sum < 5
    
    if no_main_rise and recent_weak:
        return True, {
            '爆发日期': max_surge_idx.strftime('%Y-%m-%d'),
            '爆发涨幅': round(max_surge_value, 2),
            '爆发后累计': round(cumulative_after, 2),
            '爆发后天数': len(after_surge),
            '近15日累计': round(recent_sum, 2),
            '高点回撤': round(drawdown_from_high, 2),
            '当前状态': '下杀中' if recent_sum < -3 else ('横盘' if abs(recent_sum) < 3 else '弱反弹')
        }
    
    return False, None

def scan_surge_sectors_fast():
    """
    快速扫描板块异动
    直接使用实时数据，不需要历史回测
    """
    print("正在获取板块实时数据...")
    df = get_all_sectors()
    
    if df.empty:
        print("获取板块数据失败")
        return []
    
    print(f"共 {len(df)} 个板块")
    
    results = []
    for _, row in df.iterrows():
        info = analyze_sector_surge_simple(row)
        if info:
            results.append(info)
    
    # 按涨幅排序
    results = sorted(results, key=lambda x: x['当日涨幅'], reverse=True)
    
    return results

def scan_surge_and_drop(days=60, top_n=50):
    """
    扫描早期爆发后未主升的板块
    
    参数：
    - days: 回看天数（需要60天以上才能看到1-2个月前的数据）
    - top_n: 分析板块数量
    """
    print("正在获取板块列表...")
    df = get_all_sectors()
    
    if df.empty:
        return []
    
    # 随机取一些板块来分析（避免太慢）
    sectors_to_analyze = df.sample(min(top_n, len(df)))
    
    print(f"将深度分析 {len(sectors_to_analyze)} 个板块（回看{days}天）...")
    
    results = []
    for i, (_, row) in enumerate(sectors_to_analyze.iterrows()):
        name = row['板块名称']
        today_change = float(row['涨跌幅'])
        print(f"[{i+1}/{len(sectors_to_analyze)}] 分析 {name}...", end=" ")
        
        daily_returns = get_sector_history_via_etf(name, days)
        
        if daily_returns is None:
            print("数据获取失败")
            continue
        
        is_surge, details = detect_sector_surge(daily_returns)
        
        if is_surge:
            print(f"✓ 符合条件！")
            results.append({
                '板块名称': name,
                '板块代码': row['板块代码'],
                '当日涨幅': today_change,
                '上涨家数': int(row['上涨家数']),
                '下跌家数': int(row['下跌家数']),
                **details
            })
        else:
            print("×")
    
    # 按爆发后累计涨幅排序（越低越好，说明没主升）
    results = sorted(results, key=lambda x: x['爆发后累计'])
    
    return results

def get_sector_stocks_detail(sector_name):
    """获取板块成分股详细信息"""
    try:
        df = ak.stock_board_concept_cons_em(symbol=sector_name)
        return df[['代码', '名称', '最新价', '涨跌幅', '换手率']].to_dict('records')
    except:
        return []

if __name__ == "__main__":
    print("=" * 60)
    print("板块异动扫描器 - 寻找早期爆发后未主升的板块")
    print("=" * 60)
    
    # 深度分析：找1-2个月前爆发后未主升的板块
    print("\n【深度分析：寻找早期爆发后未主升的板块】")
    print("条件：1-2个月前有过单日涨幅>3%的爆发，之后没有走出主升浪")
    
    surge_results = scan_surge_and_drop(days=60, top_n=80)
    
    if surge_results:
        print(f"\n{'='*60}")
        print(f"发现 {len(surge_results)} 个符合条件的板块:")
        print("=" * 60)
        
        for r in surge_results:
            status = r['当前状态']
            if status == '下杀中':
                status_emoji = "📉"
            elif status == '横盘':
                status_emoji = "➡️"
            else:
                status_emoji = "📈"
            
            print(f"\n{status_emoji}【{r['板块名称']}】")
            print(f"  爆发日期: {r['爆发日期']} | 爆发涨幅: +{r['爆发涨幅']}%")
            print(f"  爆发后累计: {r['爆发后累计']}% | 高点回撤: {r['高点回撤']}%")
            print(f"  近15日: {r['近15日累计']}% | 当前状态: {r['当前状态']}")
            print(f"  今日: {r['当日涨幅']:.2f}% | 上涨{r['上涨家数']}家 下跌{r['下跌家数']}家")
    else:
        print("未发现符合条件的板块")
