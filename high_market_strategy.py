"""
大盘高位时的板块选择策略
分析2025年10-12月（大盘高位）哪些板块还能赚钱
"""
import pandas as pd
import akshare as ak
import numpy as np

def analyze_high_market_sectors():
    """分析大盘高位时的板块表现"""
    
    # 读取回测数据
    df = pd.read_excel('潜力板块信号收益回测.xlsx', sheet_name='详细回测数据')
    df['回撤数值'] = df['回撤幅度'].str.replace('%', '').astype(float)
    
    print("=" * 70)
    print("大盘高位时的板块选择策略")
    print("=" * 70)
    
    # 筛选10-12月信号（大盘高位期）
    high_market = df[df['月份'].isin(['10月', '11月', '12月'])]
    
    print(f"\n2025年10-12月（大盘高位期）信号分析")
    print(f"总信号数: {len(high_market)}")
    print(f"平均1个月收益: {high_market['1个月收益'].mean():.1f}%")
    print(f"平均4个月收益: {high_market['4个月收益'].mean():.1f}%")
    
    # 找出高位期还能赚钱的板块
    print("\n" + "=" * 70)
    print("【高位期表现好的板块特征】")
    print("=" * 70)
    
    # 按收益分组
    winners = high_market[high_market['1个月收益'] > 10]
    losers = high_market[high_market['1个月收益'] < 0]
    
    print(f"\n1个月收益>10%的板块: {len(winners)}个")
    if len(winners) > 0:
        print("\n赢家板块:")
        for _, r in winners.sort_values('1个月收益', ascending=False).iterrows():
            print(f"  {r['月份']} {r['板块']}: 1月+{r['1个月收益']:.1f}%, 回撤{r['回撤幅度']}")
        
        print(f"\n赢家特征:")
        print(f"  平均回撤: {winners['回撤数值'].mean():.1f}%")
        print(f"  回撤中位数: {winners['回撤数值'].median():.1f}%")
    
    print(f"\n1个月收益<0%的板块: {len(losers)}个")
    if len(losers) > 0:
        print(f"\n输家特征:")
        print(f"  平均回撤: {losers['回撤数值'].mean():.1f}%")
    
    # 分析高位期的最佳策略
    print("\n" + "=" * 70)
    print("【高位期策略分析】")
    print("=" * 70)
    
    # 按回撤分组看高位期表现
    def get_dd_group(x):
        if x < 10: return '5-10%'
        elif x < 15: return '10-15%'
        else: return '15-20%'
    
    high_market['回撤区间'] = high_market['回撤数值'].apply(get_dd_group)
    
    dd_stats = high_market.groupby('回撤区间').agg({
        '1个月收益': 'mean',
        '板块': 'count'
    }).round(1)
    dd_stats.columns = ['1个月收益', '数量']
    
    print("\n高位期各回撤区间表现:")
    for dd in ['5-10%', '10-15%', '15-20%']:
        if dd in dd_stats.index:
            r = dd_stats.loc[dd]
            print(f"  {dd}: 1个月{r['1个月收益']:+.1f}%, 样本{int(r['数量'])}个")

def scan_laggard_sectors():
    """扫描滞涨板块（大盘涨但板块没涨的）"""
    print("\n" + "=" * 70)
    print("【当前滞涨板块扫描】")
    print("=" * 70)
    print("\n寻找：大盘在高位，但板块还在低位的机会")
    
    try:
        # 获取所有板块
        sectors = ak.stock_board_concept_name_em()
        
        results = []
        print("\n扫描中...")
        
        for i, row in sectors.head(100).iterrows():
            sector_name = row['板块名称']
            today_change = float(row['涨跌幅'])
            
            try:
                # 获取板块成分股历史
                cons = ak.stock_board_concept_cons_em(symbol=sector_name)
                if cons is None or len(cons) < 3:
                    continue
                
                # 取前3只股票
                top_stocks = cons.head(3)['代码'].tolist()
                
                all_returns = []
                for symbol in top_stocks:
                    try:
                        hist = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
                        if hist is not None and len(hist) > 60:
                            # 计算近60日涨幅
                            ret_60d = (hist['收盘'].iloc[-1] / hist['收盘'].iloc[-60] - 1) * 100
                            # 计算近20日涨幅
                            ret_20d = (hist['收盘'].iloc[-1] / hist['收盘'].iloc[-20] - 1) * 100
                            all_returns.append({'60d': ret_60d, '20d': ret_20d})
                    except:
                        continue
                
                if len(all_returns) >= 2:
                    avg_60d = np.mean([r['60d'] for r in all_returns])
                    avg_20d = np.mean([r['20d'] for r in all_returns])
                    
                    # 滞涨条件：60日涨幅<10%，近20日涨幅<5%
                    if avg_60d < 10 and avg_20d < 5:
                        results.append({
                            '板块': sector_name,
                            '今日涨幅': today_change,
                            '60日涨幅': round(avg_60d, 1),
                            '20日涨幅': round(avg_20d, 1),
                        })
            except:
                continue
        
        # 按60日涨幅排序（越低越滞涨）
        results = sorted(results, key=lambda x: x['60日涨幅'])
        
        print(f"\n发现 {len(results)} 个滞涨板块:")
        print("-" * 60)
        print(f"{'板块':<15} {'今日':>8} {'20日':>8} {'60日':>8}")
        print("-" * 60)
        
        for r in results[:20]:
            print(f"{r['板块']:<15} {r['今日涨幅']:>+7.1f}% {r['20日涨幅']:>+7.1f}% {r['60日涨幅']:>+7.1f}%")
        
        return results
        
    except Exception as e:
        print(f"扫描失败: {e}")
        return []

def print_high_market_strategy():
    """打印高位策略"""
    print("\n" + "=" * 70)
    print("【大盘高位时的选板块策略】")
    print("=" * 70)
    
    strategy = """
┌─────────────────────────────────────────────────────────────────┐
│                    大盘高位时的三种策略                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  策略1: 【滞涨补涨】                                            │
│  ─────────────────                                              │
│  逻辑: 大盘涨了，但有些板块没涨，可能会补涨                     │
│  条件:                                                          │
│    - 大盘近60日涨幅 > 15%                                       │
│    - 板块近60日涨幅 < 10%                                       │
│    - 板块近期有企稳迹象（近5日不跌）                            │
│  风险: 中等（可能是弱势板块，不会补涨）                         │
│  持有期: 1-2个月                                                │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  策略2: 【强势延续】                                            │
│  ─────────────────                                              │
│  逻辑: 强者恒强，跟随主线板块                                   │
│  条件:                                                          │
│    - 板块是当前市场主线（如AI、科技）                           │
│    - 近期有回调但不破趋势                                       │
│    - 回调幅度5-10%                                              │
│  风险: 较高（高位追涨）                                         │
│  持有期: 短线1-2周                                              │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  策略3: 【防守等待】（推荐）                                    │
│  ─────────────────────                                          │
│  逻辑: 高位不追，等回调再买                                     │
│  操作:                                                          │
│    - 现在只观察，记录潜力板块                                   │
│    - 等大盘回调10-15%后再建仓                                   │
│    - 或者等2026年Q2低点                                         │
│  风险: 最低                                                     │
│  预期: 错过短期机会，但避免高位套牢                             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

【当前建议】

大盘位置: 95%（高位）
推荐策略: 策略3（防守等待）

具体操作:
1. 不急于建仓，保持观望
2. 记录当前出现潜力信号的板块（如GDR、电子后视镜等）
3. 设置监控：大盘跌破MA20或回调10%时提醒
4. 等待更好的买入时机

如果一定要操作:
- 只用20%仓位
- 选择滞涨板块（策略1）
- 设置严格止损（-5%）
"""
    print(strategy)

if __name__ == "__main__":
    analyze_high_market_sectors()
    laggards = scan_laggard_sectors()
    print_high_market_strategy()
