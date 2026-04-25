"""
大盘高位时的快速板块筛选
"""
import akshare as ak
import pandas as pd

def get_sectors_with_history():
    """获取板块及其历史涨幅"""
    print("获取板块数据...")
    
    # 获取板块列表
    df = ak.stock_board_concept_name_em()
    
    # 获取板块历史数据
    print("获取板块历史涨幅...")
    results = []
    
    for idx, row in df.iterrows():
        name = row['板块名称']
        code = row['板块代码']
        
        try:
            # 获取板块历史K线
            hist = ak.stock_board_concept_hist_em(
                symbol=name,
                period="日k",
                start_date="20251101",
                end_date="20260116",
                adjust=""
            )
            
            if hist is None or len(hist) < 20:
                continue
            
            # 计算涨幅
            hist['日期'] = pd.to_datetime(hist['日期'])
            hist = hist.sort_values('日期')
            
            # 各时间段涨幅
            if len(hist) >= 5:
                ret_5d = (hist['收盘'].iloc[-1] / hist['收盘'].iloc[-6] - 1) * 100
            else:
                ret_5d = 0
            
            if len(hist) >= 10:
                ret_10d = (hist['收盘'].iloc[-1] / hist['收盘'].iloc[-11] - 1) * 100
            else:
                ret_10d = 0
            
            if len(hist) >= 20:
                ret_20d = (hist['收盘'].iloc[-1] / hist['收盘'].iloc[-21] - 1) * 100
            else:
                ret_20d = 0
            
            # 总涨幅
            ret_total = (hist['收盘'].iloc[-1] / hist['收盘'].iloc[0] - 1) * 100
            
            # 回撤
            high = hist['收盘'].max()
            current = hist['收盘'].iloc[-1]
            drawdown = (high - current) / high * 100
            
            results.append({
                '板块': name,
                '当日涨幅': float(row['涨跌幅']),
                '5日涨幅': round(ret_5d, 2),
                '10日涨幅': round(ret_10d, 2),
                '20日涨幅': round(ret_20d, 2),
                '60日涨幅': round(ret_total, 2),
                '回撤': round(drawdown, 2),
            })
            
            if len(results) % 20 == 0:
                print(f"  已处理 {len(results)} 个板块...")
                
        except Exception as e:
            continue
    
    return pd.DataFrame(results)

def analyze_high_market(df):
    """分析高位市场下的板块机会"""
    
    print("\n" + "=" * 70)
    print("大盘高位时的板块选择")
    print("=" * 70)
    
    # 1. 滞涨板块（60日涨幅<10%，但近期企稳）
    print("\n【策略1：滞涨补涨型】★★★ 首选")
    print("-" * 50)
    print("特点：大盘涨了30%，但这些板块涨幅小")
    print("逻辑：资金轮动可能补涨\n")
    
    laggards = df[(df['60日涨幅'] < 10) & (df['5日涨幅'] > -3) & (df['回撤'] < 8)]
    laggards = laggards.sort_values('60日涨幅').head(15)
    
    if len(laggards) > 0:
        print(f"{'板块':<15} {'60日':>8} {'20日':>8} {'5日':>8} {'回撤':>8}")
        print("-" * 50)
        for _, r in laggards.iterrows():
            print(f"{r['板块']:<15} {r['60日涨幅']:>+7.1f}% {r['20日涨幅']:>+7.1f}% {r['5日涨幅']:>+7.1f}% {r['回撤']:>7.1f}%")
    
    # 2. 调整企稳型（涨过但回调了）
    print("\n\n【策略2：调整企稳型】★★ 次选")
    print("-" * 50)
    print("特点：之前涨过，回调后企稳")
    print("逻辑：洗盘充分，可能二次启动\n")
    
    adjusted = df[(df['60日涨幅'] > 10) & (df['回撤'] > 8) & (df['5日涨幅'] > -2)]
    adjusted = adjusted.sort_values('回撤', ascending=False).head(15)
    
    if len(adjusted) > 0:
        print(f"{'板块':<15} {'60日':>8} {'回撤':>8} {'5日':>8}")
        print("-" * 50)
        for _, r in adjusted.iterrows():
            print(f"{r['板块']:<15} {r['60日涨幅']:>+7.1f}% {r['回撤']:>7.1f}% {r['5日涨幅']:>+7.1f}%")
    
    # 3. 强势板块（谨慎）
    print("\n\n【策略3：强势领涨型】★ 谨慎追高")
    print("-" * 50)
    print("特点：持续强势，但追高风险大\n")
    
    strong = df[(df['60日涨幅'] > 30) & (df['20日涨幅'] > 10) & (df['5日涨幅'] > 0)]
    strong = strong.sort_values('60日涨幅', ascending=False).head(10)
    
    if len(strong) > 0:
        print(f"{'板块':<15} {'60日':>8} {'20日':>8} {'5日':>8}")
        print("-" * 50)
        for _, r in strong.iterrows():
            print(f"{r['板块']:<15} {r['60日涨幅']:>+7.1f}% {r['20日涨幅']:>+7.1f}% {r['5日涨幅']:>+7.1f}%")
    
    # 4. 回避板块
    print("\n\n【回避】弱势板块")
    print("-" * 50)
    
    weak = df[(df['60日涨幅'] < 0) | ((df['20日涨幅'] < -5) & (df['5日涨幅'] < -2))]
    weak = weak.sort_values('60日涨幅').head(10)
    
    if len(weak) > 0:
        print(f"{'板块':<15} {'60日':>8} {'20日':>8} {'5日':>8}")
        print("-" * 50)
        for _, r in weak.iterrows():
            print(f"{r['板块']:<15} {r['60日涨幅']:>+7.1f}% {r['20日涨幅']:>+7.1f}% {r['5日涨幅']:>+7.1f}%")
    
    # 总结
    print("\n" + "=" * 70)
    print("【高位操作策略总结】")
    print("=" * 70)
    print("""
┌─────────────────────────────────────────────────────┐
│  大盘高位时的核心思路：                              │
│                                                     │
│  1. 不追涨已经涨很多的板块                          │
│  2. 找滞涨板块 - 大盘涨了它没涨，可能补涨           │
│  3. 找调整充分的板块 - 回调过，风险释放             │
│  4. 控制仓位 - 高位时仓位不超过50%                  │
│  5. 设好止损 - 单票止损5%，总止损10%                │
└─────────────────────────────────────────────────────┘

【具体操作】
1. 滞涨板块：可以建仓，但要分批，先30%仓位
2. 调整企稳：等5日线走平或向上再介入
3. 强势板块：只做短线，快进快出
4. 弱势板块：坚决回避，不抄底
""")

if __name__ == "__main__":
    df = get_sectors_with_history()
    if len(df) > 0:
        analyze_high_market(df)
        
        # 保存数据
        df.to_excel("高位板块分析.xlsx", index=False)
        print("\n✓ 数据已保存到: 高位板块分析.xlsx")
