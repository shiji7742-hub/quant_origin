"""测试涨停破位洗盘战法 - 榕基软件"""
import akshare as ak
import pandas as pd
from strategies import strategy_limit_up_washout

def test_rongji():
    """测试榕基软件在2025年10月14日-23日是否触发战法"""
    symbol = "002474"
    print(f"获取榕基软件({symbol})历史数据...")
    
    # 获取历史数据（需要多取一些用于计算）
    df = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq", 
                            start_date="20250901", end_date="20251023")
    
    if df is None or len(df) == 0:
        print("获取数据失败")
        return
    
    print(f"获取到 {len(df)} 条数据")
    print(f"日期范围: {df['日期'].iloc[0]} ~ {df['日期'].iloc[-1]}")
    print()
    
    # 遍历10月14日到23日，逐日检测
    test_dates = []
    for i, row in df.iterrows():
        date_str = str(row['日期'])
        if '2025-10-14' <= date_str <= '2025-10-23':
            test_dates.append(i)
    
    print("=" * 60)
    print("逐日检测涨停破位洗盘战法:")
    print("=" * 60)
    
    for idx in test_dates:
        # 截取到当天的数据
        df_slice = df.loc[:idx].copy()
        date = df.loc[idx, '日期']
        close = df.loc[idx, '收盘']
        open_p = df.loc[idx, '开盘']
        pct = (close - open_p) / open_p * 100
        
        result = strategy_limit_up_washout(df_slice)
        
        status = "✓ 触发!" if result['触发'] else "✗"
        print(f"\n{date} | 开盘:{open_p:.2f} 收盘:{close:.2f} 涨幅:{pct:.2f}% | {status}")
        print(f"  说明: {result['说明']}")
        print(f"  条件: {result['条件']}")

if __name__ == "__main__":
    test_rongji()
