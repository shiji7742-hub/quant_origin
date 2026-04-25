"""
严格筛选潜力板块 - 排除已有主升的板块
关键：累计涨幅不能太大，要找真正"启动前"的板块
"""
import akshare as ak
import pandas as pd
from datetime import datetime

def get_sector_history(sector_name, start_date='20250901', end_date='20260115'):
    """获取板块历史数据"""
    try:
        df = ak.stock_board_concept_cons_em(symbol=sector_name)
        if df is None or len(df) == 0:
            return None
        
        top_stocks = df.head(3)['代码'].tolist()
        
        all_data = []
        for symbol in top_stocks:
            try:
                hist = ak.stock_zh_a_hist(
                    symbol=symbol, 
                    period="daily", 
                    start_date=start_date,
                    end_date=end_date,
                    adjust="qfq"
                )
                if hist is not None and len(hist) > 30:
                    hist['涨跌幅'] = hist['收盘'].pct_change() * 100
                    hist['日期'] = pd.to_datetime(hist['日期'])
                    all_data.append(hist[['日期', '涨跌幅']].set_index('日期'))
            except:
                continue
        
        if len(all_data) == 0:
            return None
        
        combined = pd.concat([d['涨跌幅'] for d in all_data], axis=1)
        return combined.mean(axis=1)
    except:
        return None

def analyze_sector_strict(sector_name):
    """严格分析板块 - 排除已有主升的"""
    data = get_sector_history(sector_name)
    if data is None:
        return None
    
    data = data.dropna()
    if len(data) < 50:
        return None
    
    # 计算各阶段涨幅
    monthly = {}
    for month in ['2025-09', '2025-10', '2025-11', '2025-12', '2026-01']:
        month_data = data[data.index.strftime('%Y-%m') == month]
        if len(month_data) > 0:
            monthly[month] = round(month_data.sum(), 1)
    
    # 计算总涨幅
    total_return = data.sum()
    
    # 找爆发
    old_period = data.iloc[:-15]
    surge_days = old_period[old_period > 2.5]
    if len(surge_days) == 0:
        return None
    
    max_surge = surge_days.max()
    max_surge_date = surge_days.idxmax()
    surge_count = len(surge_days)
    
    # 爆发后数据
    after_surge = data[data.index >= max_surge_date]
    
    # 计算回撤
    cumsum = after_surge.cumsum()
    max_gain = cumsum.max()
    current_gain = cumsum.iloc[-1]
    drawdown = max_gain - current_gain
    
    # 近期数据
    recent_15d = data.iloc[-15:].sum()
    recent_5d = data.iloc[-5:].sum()
    
    # 检查是否已有主升
    # 条件：任意连续两个月涨幅超过30%，视为已有主升
    has_main_rise = False
    months_list = list(monthly.values())
    for i in range(len(months_list) - 1):
        if months_list[i] + months_list[i+1] > 30:
            has_main_rise = True
            break
    
    # 或者总涨幅超过40%也视为已有主升
    if total_return > 40:
        has_main_rise = True
    
    return {
        'surge_date': max_surge_date.strftime('%Y-%m-%d'),
        'surge_value': round(max_surge, 2),
        'surge_count': surge_count,
        'drawdown': round(drawdown, 2),
        'recent_15d': round(recent_15d, 2),
        'recent_5d': round(recent_5d, 2),
        'total_return': round(total_return, 1),
        'monthly': monthly,
        'has_main_rise': has_main_rise
    }

def main():
    print("=" * 70)
    print("严格筛选潜力板块 - 排除已有主升的板块")
    print(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print("\n筛选条件：")
    print("  1. 有过爆发（单日>2.5%）")
    print("  2. 有回撤（洗盘）")
    print("  3. 总涨幅<40%（排除已主升）")
    print("  4. 连续两月涨幅<30%（排除已主升）")
    
    # 候选板块列表
    candidates = [
        # 之前扫描发现的
        'GDR', '电子后视镜', '环氧丙烷', '举牌', '3D摄像头',
        '培育钻石', '熔盐储能', '鸡肉概念', '低碳冶金',
        '科创板做市商', '乳业',
        # 热门板块
        '低空经济', '机器人概念', '人形机器人', '卫星互联网',
        '算力概念', '数据要素', '华为概念', '军工',
        # 补充一些可能的板块
        '光伏', '风电', '核电', '电力', '煤炭',
        '银行', '保险', '券商', '地产', '建材',
        '医药', '白酒', '食品饮料', '家电', '汽车',
        '钢铁', '有色', '化工', '纺织服装', '农业',
        '传媒', '游戏', '教育', '旅游', '航空',
        '港口', '高速公路', '物流', '零售', '电商',
    ]
    
    results = []
    
    for name in candidates:
        print(f"分析 {name}...", end=" ")
        info = analyze_sector_strict(name)
        
        if info is None:
            print("×")
            continue
        
        # 排除已有主升的
        if info['has_main_rise']:
            print(f"× (已主升，总涨幅{info['total_return']}%)")
            continue
        
        # 排除回撤太小的（没洗盘）
        if info['drawdown'] < 3:
            print(f"× (回撤太小{info['drawdown']}%)")
            continue
        
        # 排除近期大涨的（已启动）
        if info['recent_15d'] > 15:
            print(f"× (近期已启动，15日+{info['recent_15d']}%)")
            continue
        
        # 计算评分
        score = 0
        if info['drawdown'] >= 8:
            score += 3
        elif info['drawdown'] >= 5:
            score += 2
        else:
            score += 1
        
        if info['surge_count'] >= 5:
            score += 3
        elif info['surge_count'] >= 3:
            score += 2
        else:
            score += 1
        
        if -3 < info['recent_5d'] < 3:
            score += 2
        
        if info['surge_value'] >= 5:
            score += 2
        elif info['surge_value'] >= 3:
            score += 1
        
        info['name'] = name
        info['score'] = score
        results.append(info)
        print(f"✓ 评分:{score}")
    
    # 按评分排序
    results = sorted(results, key=lambda x: x['score'], reverse=True)
    
    # 打印结果
    print("\n" + "=" * 70)
    print(f"【真正的潜力板块】共 {len(results)} 个")
    print("=" * 70)
    
    if not results:
        print("\n未发现符合条件的板块")
        return
    
    for i, r in enumerate(results, 1):
        print(f"\n{i}. 【{r['name']}】 评分: {r['score']}")
        print(f"   爆发: {r['surge_date']} +{r['surge_value']}% ({r['surge_count']}次)")
        print(f"   回撤: {r['drawdown']}% | 总涨幅: {r['total_return']}%")
        print(f"   近15日: {r['recent_15d']}% | 近5日: {r['recent_5d']}%")
        print(f"   月度: ", end="")
        for month, ret in r['monthly'].items():
            m = month.split('-')[1]
            print(f"{m}月:{ret:+.0f}% ", end="")
        print()
    
    # 对比商业航天
    print("\n" + "=" * 70)
    print("【对比：商业航天启动前特征】")
    print("=" * 70)
    print("商业航天在11月信号时的特征：")
    print("  - 9月有爆发（+6.5%）")
    print("  - 10月震荡（+2.6%）")
    print("  - 11月洗盘（-6.8%）← 信号出现")
    print("  - 总涨幅较小，没有主升过")
    print("  - 回撤7-10%")
    
    print("\n上述板块中，最接近这个特征的是：")
    for r in results[:3]:
        print(f"  ★ {r['name']}: 回撤{r['drawdown']}%, 总涨幅{r['total_return']}%")

if __name__ == "__main__":
    main()
