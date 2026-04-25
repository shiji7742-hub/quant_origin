"""交易日历 - 判断是否为交易日"""
import datetime
import akshare as ak

def is_trading_day(date=None) -> bool:
    """判断是否为交易日"""
    if date is None:
        date = datetime.date.today()
    
    # 周末直接返回False
    if date.weekday() >= 5:
        return False
    
    try:
        # 获取交易日历
        df = ak.tool_trade_date_hist_sina()
        trade_dates = set(df['trade_date'].astype(str))
        date_str = date.strftime('%Y-%m-%d')
        return date_str in trade_dates
    except:
        # 如果获取失败，默认周一到周五为交易日
        return date.weekday() < 5

def get_next_trading_day(date=None):
    """获取下一个交易日"""
    if date is None:
        date = datetime.date.today()
    
    next_day = date + datetime.timedelta(days=1)
    while not is_trading_day(next_day):
        next_day += datetime.timedelta(days=1)
    return next_day

if __name__ == "__main__":
    today = datetime.date.today()
    print(f"今天: {today}")
    print(f"是否交易日: {is_trading_day(today)}")
    print(f"下一个交易日: {get_next_trading_day(today)}")
