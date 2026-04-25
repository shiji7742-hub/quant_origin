"""分析交易记录，找出优化指标"""
import pandas as pd

def analyze():
    df = pd.read_excel(r'C:\Users\shiji\Desktop\股票统计(1).xlsx', header=1)
    df = df[df['代码'].notna() & (df['代码'] != '批次二')]
    df = df[df['当日盈亏率'].notna()]
    
    print('=== 盈亏与各指标关系 ===\n')
    
    # 量比与盈亏
    print('【量比分析】')
    df['量比'] = pd.to_numeric(df['量比'], errors='coerce')
    high_vol = df[df['量比'] > 2]
    low_vol = df[df['量比'] <= 2]
    if len(high_vol) > 0:
        print(f'量比>2: {len(high_vol)}笔, 平均盈亏: {high_vol["当日盈亏率"].mean()*100:.2f}%')
    if len(low_vol) > 0:
        print(f'量比<=2: {len(low_vol)}笔, 平均盈亏: {low_vol["当日盈亏率"].mean()*100:.2f}%')
    print()
    
    # 今日涨幅与盈亏
    print('【扫描点涨幅分析】')
    df['今日涨幅'] = pd.to_numeric(df['今日涨幅'], errors='coerce')
    high_gain = df[df['今日涨幅'] > 0.06]
    low_gain = df[df['今日涨幅'] <= 0.06]
    if len(high_gain) > 0:
        print(f'涨幅>6%: {len(high_gain)}笔, 平均盈亏: {high_gain["当日盈亏率"].mean()*100:.2f}%')
    if len(low_gain) > 0:
        print(f'涨幅<=6%: {len(low_gain)}笔, 平均盈亏: {low_gain["当日盈亏率"].mean()*100:.2f}%')
    print()
    
    # 详细数据
    print('【详细数据】')
    for _, row in df.iterrows():
        profit = '盈' if row['当日盈亏率'] > 0 else '亏'
        print(f"{row['名称']}: 量比{row['量比']:.2f}, 涨幅{row['今日涨幅']*100:.1f}%, 盈亏{row['当日盈亏率']*100:.2f}% [{profit}]")
    
    print('\n=== 建议 ===')
    # 找出盈利的特征
    win = df[df['当日盈亏率'] > 0]
    if len(win) > 0:
        print(f"盈利交易特征: 量比={win['量比'].mean():.2f}, 涨幅={win['今日涨幅'].mean()*100:.1f}%")
    
    lose = df[df['当日盈亏率'] < 0]
    if len(lose) > 0:
        print(f"亏损交易特征: 量比={lose['量比'].mean():.2f}, 涨幅={lose['今日涨幅'].mean()*100:.1f}%")

if __name__ == "__main__":
    analyze()
