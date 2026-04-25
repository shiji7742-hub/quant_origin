"""龙虎榜数据查询"""
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta

def get_lhb_today():
    """获取今日龙虎榜"""
    print("获取今日龙虎榜...")
    try:
        df = ak.stock_lhb_detail_em()
        if df is not None and len(df) > 0:
            print(f"今日龙虎榜共 {len(df)} 条记录")
            return df
    except Exception as e:
        print(f"获取失败: {e}")
    return None

def get_lhb_by_date(date_str):
    """获取指定日期龙虎榜
    date_str: 格式 '20260107'
    """
    print(f"获取 {date_str} 龙虎榜...")
    try:
        df = ak.stock_lhb_detail_em(start_date=date_str, end_date=date_str)
        if df is not None and len(df) > 0:
            print(f"共 {len(df)} 条记录")
            return df
    except Exception as e:
        print(f"获取失败: {e}")
    return None

def get_lhb_stock_detail(symbol):
    """获取个股龙虎榜历史"""
    print(f"获取 {symbol} 龙虎榜历史...")
    try:
        df = ak.stock_lhb_stock_detail_em(symbol=symbol)
        if df is not None and len(df) > 0:
            print(f"共 {len(df)} 条历史记录")
            return df
    except Exception as e:
        print(f"获取失败: {e}")
    return None

def get_lhb_jgmx():
    """获取机构买卖明细"""
    print("获取机构买卖明细...")
    try:
        df = ak.stock_lhb_jgmmtj_em()
        if df is not None and len(df) > 0:
            print(f"共 {len(df)} 条记录")
            return df
    except Exception as e:
        print(f"获取失败: {e}")
    return None

def get_lhb_yybpm():
    """获取营业部排名"""
    print("获取营业部排名...")
    try:
        df = ak.stock_lhb_yybpm_em()
        if df is not None and len(df) > 0:
            print(f"共 {len(df)} 条记录")
            return df
    except Exception as e:
        print(f"获取失败: {e}")
    return None

def analyze_lhb(df):
    """分析龙虎榜数据"""
    if df is None or len(df) == 0:
        print("无数据")
        return
    
    print("\n" + "=" * 60)
    print("龙虎榜分析")
    print("=" * 60)
    
    # 显示列名
    print(f"数据列: {list(df.columns)}")
    print(f"\n前10条记录:")
    print(df.head(10).to_string())

if __name__ == "__main__":
    # 获取今日龙虎榜
    df = get_lhb_today()
    analyze_lhb(df)
    
    print("\n" + "=" * 60)
    
    # 获取机构买卖
    df_jg = get_lhb_jgmx()
    if df_jg is not None:
        print("\n机构买卖明细:")
        print(df_jg.head(10).to_string())
