"""回测指定日期的战法"""
import akshare as ak
import pandas as pd
from strategies import strategy_limit_up_washout

def get_history_data(symbol: str, start_date: str, end_date: str):
    """获取历史数据"""
    df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
    return df

def backtest_on_date(symbol: str, test_date: str, lookback_days: int = 30):
    """
    在指定日期回测战法
    test_date: 测试日期，格式 20251023
    lookback_days: 往前看多少天的数据
    """
    # 获取足够的历史数据
    end_date = test_date
    # 往前多取一些数据
    start_dt = pd.to_datetime(test_date) - pd.Timedelta(days=lookback_days + 30)
    start_date = start_dt.strftime('%Y%m%d')
    
    print(f"获取 {symbol} 从 {start_date} 到 {end_date} 的数据...")
    df = get_history_data(symbol, start_date, end_date)
    
    if df is None or len(df) == 0:
        print("获取数据失败")
        return
    
    print(f"共获取 {len(df)} 条数据")
    print(f"日期范围: {df['日期'].iloc[0]} ~ {df['日期'].iloc[-1]}")
    
    # 显示最后几天的数据
    print("\n最近几天行情:")
    print(df[['日期', '开盘', '最高', '最低', '收盘', '涨跌幅', '成交量']].tail(10).to_string())
    
    # 测试战法
    print("\n--- 战法检测 ---")
    result = strategy_limit_up_washout(df)
    
    print(f"触发: {result['触发']}")
    print(f"说明: {result['说明']}")
    print(f"条件: {result['条件']}")
    
    return result

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("用法: python backtest_strategy.py <股票代码> <测试日期>")
        print("示例: python backtest_strategy.py 002474 20251023")
        print("      测试榕基软件在2025年10月23日是否触发涨停破位洗盘战法")
    else:
        symbol = sys.argv[1]
        test_date = sys.argv[2]
        backtest_on_date(symbol, test_date)
