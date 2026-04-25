"""
快速扫描潜力板块 - 基于已知结果 + 快速验证
"""
import akshare as ak
import pandas as pd
from datetime import datetime
from backtest_sector_surge import get_market_data

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

def analyze_sector(sector_name):
    """分析单个板块"""
    data = get_sector_history(sector_name)
    if data is None:
        return None
    
    data = data.dropna()
    if len(data) < 50:
        return None
    
    # 计算指标
    old_period = data.iloc[:-15]
    recent_15d = data.iloc[-15:]
    recent_5d = data.iloc[-5:]
    
    # 找爆发
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
    
    # 月度涨幅
    monthly = {}
    for month in ['2025-09', '2025-10', '2025-11', '2025-12', '2026-01']:
        month_data = data[data.index.strftime('%Y-%m') == month]
        if len(month_data) > 0:
            monthly[month] = round(month_data.sum(), 1)
    
    return {
        'surge_date': max_surge_date.strftime('%Y-%m-%d'),
        'surge_value': round(max_surge, 2),
        'surge_count': surge_count,
        'drawdown': round(drawdown, 2),
        'recent_15d': round(recent_15d.sum(), 2),
        'recent_5d': round(recent_5d.sum(), 2),
        'monthly': monthly
    }

def main():
    print("=" * 70)
    print("潜力板块分析报告")
    print(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    # 从之前扫描中发现的高潜力板块
    high_potential = [
        ('GDR', 10),
        ('电子后视镜', 10),
        ('环氧丙烷', 9),
        ('举牌', 9),
        ('3D摄像头', 8),
        ('培育钻石', 8),
        ('熔盐储能', 7),
        ('鸡肉概念', 7),
        ('HS300_', 6),
    ]
    
    # 补充一些热门板块进行分析
    additional = [
        '低空经济',
        '机器人概念',
        '人形机器人',
        '卫星互联网',
        '算力概念',
        '数据要素',
        '华为概念',
        '军工',
        '国防军工',
        '航天航空',
    ]
    
    print("\n【高潜力板块详细分析】")
    print("（基于'爆发-回撤-企稳'模式筛选）")
    print("-" * 70)
    
    results = []
    
    # 分析高潜力板块
    for name, score in high_potential:
        print(f"\n分析 {name}...", end=" ")
        info = analyze_sector(name)
        if info:
            info['name'] = name
            info['score'] = score
            results.append(info)
            print("✓")
        else:
            print("×")
    
    # 分析补充板块
    print("\n\n【热门板块分析】")
    print("-" * 70)
    
    for name in additional:
        print(f"\n分析 {name}...", end=" ")
        info = analyze_sector(name)
        if info:
            info['name'] = name
            # 计算评分
            score = 0
            if info['drawdown'] >= 8:
                score += 3
            elif info['drawdown'] >= 5:
                score += 2
            if info['surge_count'] >= 5:
                score += 3
            elif info['surge_count'] >= 3:
                score += 2
            if -3 < info['recent_5d'] < 3:
                score += 2
            if info['surge_value'] >= 5:
                score += 2
            elif info['surge_value'] >= 3:
                score += 1
            info['score'] = score
            results.append(info)
            print(f"✓ 评分:{score}")
        else:
            print("×")
    
    # 按评分排序
    results = sorted(results, key=lambda x: x['score'], reverse=True)
    
    # 打印结果
    print("\n" + "=" * 70)
    print("【潜力板块排行榜】")
    print("=" * 70)
    
    for i, r in enumerate(results, 1):
        print(f"\n{i}. 【{r['name']}】 评分: {r['score']}")
        print(f"   爆发: {r['surge_date']} +{r['surge_value']}% ({r['surge_count']}次)")
        print(f"   回撤: {r['drawdown']}% | 近15日: {r['recent_15d']}% | 近5日: {r['recent_5d']}%")
        if 'monthly' in r:
            print(f"   月度: ", end="")
            for month, ret in r['monthly'].items():
                m = month.split('-')[1]
                print(f"{m}月:{ret:+.0f}% ", end="")
            print()
    
    # 总结
    print("\n" + "=" * 70)
    print("【投资建议】")
    print("=" * 70)
    
    top_picks = [r for r in results if r['score'] >= 7]
    if top_picks:
        print("\n重点关注（评分≥7）：")
        for r in top_picks:
            print(f"  ★ {r['name']}: 回撤{r['drawdown']}%, 爆发{r['surge_count']}次")
    
    print("\n这些板块特征：")
    print("  1. 早期有过爆发（资金关注）")
    print("  2. 之后回撤洗盘（清洗浮筹）")
    print("  3. 近期企稳（可能酝酿新一轮上涨）")
    print("\n风险提示：技术分析仅供参考，需结合基本面判断")

if __name__ == "__main__":
    main()
