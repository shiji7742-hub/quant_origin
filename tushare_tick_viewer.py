#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tushare 逐笔/分钟数据查看器

使用前请先：
1. 注册 Tushare Pro: https://tushare.pro/register
2. 获取你的 token（在个人中心）
3. 优先设置环境变量 TUSHARE_TOKEN；如需本地调试，也只在本地填写下方变量，且不要提交到仓库
"""

import tushare as ts
import pandas as pd
from datetime import datetime, timedelta
import os

# ========== 请在这里填入你的 Tushare Token（仅限本地，不要提交） ==========
TUSHARE_TOKEN = ""
# ===================================================

def init_tushare():
    """初始化 Tushare"""
    token = TUSHARE_TOKEN or os.environ.get('TUSHARE_TOKEN', '')
    if not token:
        print("=" * 60)
        print("错误：请先设置 Tushare Token！")
        print()
        print("获取方式：")
        print("1. 注册 https://tushare.pro/register")
        print("2. 登录后在个人中心复制 token")
        print("3. 将 token 填入本文件顶部的 TUSHARE_TOKEN 变量")
        print("=" * 60)
        return None
    
    ts.set_token(token)
    pro = ts.pro_api()
    
    # 检查积分
    try:
        user = pro.query('user')
        if user is not None and not user.empty:
            points = user.iloc[0].get('point', 0)
            print(f"当前积分: {points}")
            if points < 2000:
                print("提示：积分不足2000，部分接口可能无法使用")
                print("可以通过完善资料、分享等方式获取更多积分")
    except:
        pass
    
    return pro

def get_tick_data(pro, ts_code, trade_date=None):
    """
    获取逐笔成交数据
    注意：逐笔数据需要5000+积分
    """
    if trade_date is None:
        trade_date = datetime.now().strftime('%Y%m%d')
    
    try:
        # 尝试获取逐笔数据（需要高积分）
        df = pro.stk_mins(ts_code=ts_code, trade_date=trade_date, freq='1min')
        if df is not None and not df.empty:
            print(f"获取到 {len(df)} 条分钟数据")
            return df, 'mins'
    except Exception as e:
        print(f"分钟数据接口失败: {e}")
    
    try:
        # 尝试获取tick数据
        df = pro.query('tick', ts_code=ts_code, trade_date=trade_date)
        if df is not None and not df.empty:
            print(f"获取到 {len(df)} 条tick数据")
            return df, 'tick'
    except Exception as e:
        print(f"Tick数据接口失败: {e}")
    
    return None, None

def get_minute_data(pro, ts_code, start_date=None, end_date=None):
    """获取分钟线数据"""
    if end_date is None:
        end_date = datetime.now().strftime('%Y%m%d %H:%M:%S')
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=1)).strftime('%Y%m%d %H:%M:%S')
    
    try:
        df = ts.pro_bar(ts_code=ts_code, freq='1min', start_date=start_date, end_date=end_date)
        if df is not None and not df.empty:
            return df
    except Exception as e:
        print(f"分钟线接口失败: {e}")
    
    return None

def format_code(code):
    """格式化股票代码为Tushare格式"""
    code = code.strip()
    if code.startswith('6'):
        return f"{code}.SH"
    elif code.startswith('0') or code.startswith('3'):
        return f"{code}.SZ"
    elif '.' in code:
        return code
    return code

def print_data(df, data_type='mins'):
    """打印数据"""
    if df is None or df.empty:
        print("无数据")
        return
    
    print("\n" + "=" * 80)
    print(f"数据类型: {data_type}")
    print(f"数据条数: {len(df)}")
    print(f"列名: {df.columns.tolist()}")
    print("=" * 80)
    
    # 显示前20条
    print("\n最近20条数据：")
    print(df.head(20).to_string())
    
    # 统计
    if 'vol' in df.columns:
        print(f"\n总成交量: {df['vol'].sum():,.0f}")
    if 'amount' in df.columns:
        print(f"总成交额: {df['amount'].sum():,.0f}")

def main():
    print("=" * 60)
    print("Tushare 数据查看器")
    print("=" * 60)
    
    pro = init_tushare()
    if pro is None:
        return
    
    while True:
        print("\n请输入股票代码（如 002279，输入 q 退出）：")
        code = input("> ").strip()
        
        if code.lower() == 'q':
            break
        
        if not code:
            continue
        
        ts_code = format_code(code)
        print(f"\n查询: {ts_code}")
        
        # 尝试获取数据
        print("\n1. 尝试获取分钟线数据...")
        df = get_minute_data(pro, ts_code)
        if df is not None:
            print_data(df, 'minute')
        else:
            print("分钟线数据获取失败")
        
        print("\n2. 尝试获取tick/分钟数据...")
        df, dtype = get_tick_data(pro, ts_code)
        if df is not None:
            print_data(df, dtype)
        else:
            print("Tick数据获取失败（可能积分不足）")

if __name__ == '__main__':
    main()
