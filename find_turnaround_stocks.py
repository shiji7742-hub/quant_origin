"""
查找最近扭亏的股票
用于回测准备
"""
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import time

def find_recent_turnaround_stocks(year=2024, save_excel=True):
    """
    查找指定年份扭亏的股票
    
    Args:
        year: 年份
        save_excel: 是否保存Excel
    
    Returns:
        DataFrame: 扭亏股票列表
    """
    print("=" * 60)
    print(f"查找{year}年扭亏股票")
    print("=" * 60)
    
    # 获取所有A股列表
    print("\n[1/3] 获取A股列表...")
    try:
        df_stocks = ak.stock_zh_a_spot_em()
        # 只保留主板（60、00开头）
        df_stocks = df_stocks[df_stocks['代码'].str.match(r'^(60|00)')]
        print(f"找到 {len(df_stocks)} 只主板股票")
    except Exception as e:
        print(f"获取股票列表失败: {e}")
        return pd.DataFrame()
    
    # 逐个检查
    print(f"\n[2/3] 检查{year}年报扭亏情况...")
    results = []
    total = len(df_stocks)
    
    for idx, row in df_stocks.iterrows():
        symbol = row['代码']
        name = row['名称']
        
        if (idx + 1) % 50 == 0:
            print(f"  进度: {idx+1}/{total} ({(idx+1)/total*100:.1f}%)")
        
        try:
            # 获取财务数据
            df_finance = ak.stock_financial_report_sina(stock=symbol, symbol="利润表")
            
            if df_finance is None or len(df_finance) < 2:
                continue
            
            df_finance = df_finance.sort_values('报告期', ascending=False)
            
            # 找到目标年份和前一年的年报
            current_year = df_finance[df_finance['报告期'].str.contains(str(year))]
            prev_year = df_finance[df_finance['报告期'].str.contains(str(year-1))]
            
            if len(current_year) == 0 or len(prev_year) == 0:
                continue
            
            profit_current = current_year.iloc[0].get('净利润', 0)
            profit_prev = prev_year.iloc[0].get('净利润', 0)
            
            # 判断扭亏
            if profit_prev < 0 and profit_current > 0:
                results.append({
                    '股票代码': symbol,
                    '股票名称': name,
                    f'{year-1}年利润(万)': profit_prev / 10000,
                    f'{year}年利润(万)': profit_current / 10000,
                    '扭亏幅度(万)': (profit_current - profit_prev) / 10000,
                    '最新价': row['最新价'],
                    '涨跌幅': row['涨跌幅'],
                })
                print(f"  ✓ 找到: {symbol} {name} - {year-1}年亏损{profit_prev/10000:.0f}万 → {year}年盈利{profit_current/10000:.0f}万")
            
            time.sleep(0.1)  # 避免请求过快
        
        except Exception as e:
            continue
    
    # 生成结果
    if len(results) == 0:
        print(f"\n未找到{year}年扭亏的股票")
        return pd.DataFrame()
    
    df_result = pd.DataFrame(results)
    df_result = df_result.sort_values(f'{year}年利润(万)', ascending=False)
    
    print("\n" + "=" * 60)
    print(f"找到 {len(df_result)} 只扭亏股票")
    print("=" * 60)
    print(df_result.to_string(index=False))
    
    # 保存Excel
    if save_excel:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'{year}年扭亏股票_{timestamp}.xlsx'
        df_result.to_excel(filename, index=False, engine='openpyxl')
        print(f"\n结果已保存到: {filename}")
    
    return df_result


def get_report_disclosure_dates(year=2024):
    """
    获取年报披露时间表
    
    Args:
        year: 年份
    
    Returns:
        DataFrame: 披露时间表
    """
    print("=" * 60)
    print(f"获取{year}年报披露时间表")
    print("=" * 60)
    
    try:
        df = ak.stock_report_disclosure(date=f"{year}-12-31")
        
        if df is None or len(df) == 0:
            print("未获取到披露时间表")
            return pd.DataFrame()
        
        print(f"\n获取到 {len(df)} 条记录")
        print("\n可用列:")
        print(df.columns.tolist())
        print("\n前10条数据:")
        print(df.head(10))
        
        # 保存
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'{year}年报披露时间表_{timestamp}.xlsx'
        df.to_excel(filename, index=False, engine='openpyxl')
        print(f"\n已保存到: {filename}")
        
        return df
    
    except Exception as e:
        print(f"获取失败: {e}")
        return pd.DataFrame()


def quick_check_turnaround(symbol_list):
    """
    快速检查指定股票是否扭亏
    
    Args:
        symbol_list: 股票代码列表
    
    Returns:
        DataFrame: 检查结果
    """
    print("=" * 60)
    print("快速检查股票扭亏情况")
    print("=" * 60)
    
    results = []
    
    for symbol in symbol_list:
        print(f"\n检查 {symbol}...")
        
        try:
            # 获取股票信息
            df_info = ak.stock_zh_a_spot_em()
            stock_info = df_info[df_info['代码'] == symbol]
            
            if len(stock_info) == 0:
                print(f"  ✗ 未找到股票信息")
                continue
            
            name = stock_info.iloc[0]['名称']
            
            # 获取财务数据
            df_finance = ak.stock_financial_report_sina(stock=symbol, symbol="利润表")
            
            if df_finance is None or len(df_finance) < 2:
                print(f"  ✗ 财务数据不足")
                continue
            
            df_finance = df_finance.sort_values('报告期', ascending=False)
            
            # 显示最近几期利润
            print(f"  {name} 最近利润情况:")
            for i in range(min(4, len(df_finance))):
                period = df_finance.iloc[i]['报告期']
                profit = df_finance.iloc[i].get('净利润', 0) / 10000
                print(f"    {period}: {profit:+.0f}万")
            
            # 检查2024年报扭亏
            annual_2024 = df_finance[df_finance['报告期'].str.contains('2024')]
            annual_2023 = df_finance[df_finance['报告期'].str.contains('2023')]
            
            if len(annual_2024) > 0 and len(annual_2023) > 0:
                profit_2024 = annual_2024.iloc[0].get('净利润', 0)
                profit_2023 = annual_2023.iloc[0].get('净利润', 0)
                
                is_turnaround = (profit_2023 < 0) and (profit_2024 > 0)
                
                results.append({
                    '股票代码': symbol,
                    '股票名称': name,
                    '2023年利润(万)': profit_2023 / 10000,
                    '2024年利润(万)': profit_2024 / 10000,
                    '是否扭亏': '✓' if is_turnaround else '✗',
                })
                
                if is_turnaround:
                    print(f"  ✓ 2024年报扭亏")
                else:
                    print(f"  ✗ 未扭亏")
            
            time.sleep(0.3)
        
        except Exception as e:
            print(f"  ✗ 检查失败: {e}")
            continue
    
    if len(results) > 0:
        df_result = pd.DataFrame(results)
        print("\n" + "=" * 60)
        print("检查结果汇总")
        print("=" * 60)
        print(df_result.to_string(index=False))
        return df_result
    
    return pd.DataFrame()


if __name__ == '__main__':
    print("年报扭亏股票查找工具")
    print("=" * 60)
    print("1. 查找2024年扭亏股票（全市场扫描，耗时较长）")
    print("2. 获取2024年报披露时间表")
    print("3. 快速检查指定股票")
    print("=" * 60)
    
    choice = input("\n请选择功能 (1/2/3): ").strip()
    
    if choice == '1':
        df = find_recent_turnaround_stocks(year=2024, save_excel=True)
    
    elif choice == '2':
        df = get_report_disclosure_dates(year=2024)
    
    elif choice == '3':
        print("\n请输入股票代码（多个代码用逗号分隔）:")
        codes = input("代码: ").strip().split(',')
        codes = [c.strip() for c in codes if c.strip()]
        
        if codes:
            df = quick_check_turnaround(codes)
        else:
            print("未输入有效代码")
    
    else:
        print("无效选择")
