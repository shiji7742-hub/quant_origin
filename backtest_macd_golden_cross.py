"""
MACD金叉策略回测
回测不同参数和条件下的策略表现
"""
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from scan_macd_golden_cross import calculate_macd, detect_macd_golden_cross
import warnings
warnings.filterwarnings('ignore')


def backtest_stock(code, name, start_date='20250101', end_date='20260115'):
    """回测单只股票的MACD金叉策略"""
    try:
        # 获取历史数据
        df = ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=start_date,
            end_date=end_date,
            adjust="qfq"
        )
        
        if df is None or len(df) < 100:
            return []
        
        df['日期'] = pd.to_datetime(df['日期'])
        df = calculate_macd(df)
        
        signals = []
        
        # 遍历每一天，检测金叉
        for i in range(50, len(df) - 1):  # 留一天用于计算收益
            # 检查是否金叉
            if df.iloc[i]['MACD'] > df.iloc[i]['Signal'] and \
               df.iloc[i-1]['MACD'] <= df.iloc[i-1]['Signal']:
                
                signal_date = df.iloc[i]['日期']
                signal_price = df.iloc[i]['收盘']
                macd_value = df.iloc[i]['MACD']
                signal_value = df.iloc[i]['Signal']
                position = '0轴上方' if macd_value > 0 else '0轴下方'
                
                # 计算后续收益
                returns = {}
                for days, label in [(1, '1日'), (3, '3日'), (5, '5日'), 
                                   (10, '10日'), (20, '20日')]:
                    if i + days < len(df):
                        future_price = df.iloc[i + days]['收盘']
                        ret = (future_price - signal_price) / signal_price * 100
                        returns[f'{label}收益'] = round(ret, 2)
                        
                        # 计算期间最大回撤
                        period_data = df.iloc[i:i+days+1]
                        max_dd = ((period_data['收盘'].min() - signal_price) / signal_price * 100)
                        returns[f'{label}最大回撤'] = round(max_dd, 2)
                
                # 找到死叉日期（如果有）
                death_cross_idx = None
                for j in range(i + 1, min(i + 60, len(df))):
                    if df.iloc[j]['MACD'] < df.iloc[j]['Signal'] and \
                       df.iloc[j-1]['MACD'] >= df.iloc[j-1]['Signal']:
                        death_cross_idx = j
                        break
                
                if death_cross_idx:
                    death_cross_date = df.iloc[death_cross_idx]['日期']
                    death_cross_price = df.iloc[death_cross_idx]['收盘']
                    hold_days = death_cross_idx - i
                    hold_return = (death_cross_price - signal_price) / signal_price * 100
                else:
                    death_cross_date = None
                    hold_days = None
                    hold_return = None
                
                signals.append({
                    '代码': code,
                    '名称': name,
                    '金叉日期': signal_date,
                    '金叉价格': round(signal_price, 2),
                    'MACD': round(macd_value, 4),
                    'Signal': round(signal_value, 4),
                    '位置': position,
                    '死叉日期': death_cross_date,
                    '持有天数': hold_days,
                    '持有收益': round(hold_return, 2) if hold_return else None,
                    **returns
                })
        
        return signals
        
    except Exception as e:
        return []


def backtest_sample_stocks(sample_size=100):
    """回测样本股票"""
    print("=" * 70)
    print("MACD金叉策略回测")
    print("=" * 70)
    print(f"回测期间: 2025-01-01 至 2026-01-15")
    print(f"样本数量: {sample_size}只")
    
    # 获取股票列表
    print("\n获取股票列表...")
    df_stocks = ak.stock_zh_a_spot_em()
    df_stocks = df_stocks[df_stocks['代码'].str.match(r'^(60|00)')]
    df_stocks = df_stocks[~df_stocks['名称'].str.contains('ST')]
    
    # 随机抽样
    import random
    stocks = df_stocks[['代码', '名称']].to_dict('records')
    random.shuffle(stocks)
    stocks = stocks[:sample_size]
    
    print(f"开始回测 {len(stocks)} 只股票...")
    
    all_signals = []
    completed = 0
    
    for stock in stocks:
        completed += 1
        if completed % 10 == 0:
            print(f"  进度: {completed}/{len(stocks)}")
        
        signals = backtest_stock(stock['代码'], stock['名称'])
        all_signals.extend(signals)
    
    print(f"\n回测完成！共发现 {len(all_signals)} 个金叉信号")
    
    return pd.DataFrame(all_signals)


def analyze_results(df):
    """分析回测结果"""
    if len(df) == 0:
        print("没有数据可分析")
        return
    
    print("\n" + "=" * 70)
    print("回测结果分析")
    print("=" * 70)
    
    # 按位置分组
    above_zero = df[df['位置'] == '0轴上方']
    below_zero = df[df['位置'] == '0轴下方']
    
    print(f"\n总信号数: {len(df)}")
    print(f"  0轴上方: {len(above_zero)} ({len(above_zero)/len(df)*100:.1f}%)")
    print(f"  0轴下方: {len(below_zero)} ({len(below_zero)/len(df)*100:.1f}%)")
    
    # 各周期收益统计
    print("\n" + "=" * 70)
    print("各周期收益统计")
    print("=" * 70)
    
    periods = ['1日', '3日', '5日', '10日', '20日']
    
    for period in periods:
        col = f'{period}收益'
        if col not in df.columns:
            continue
        
        valid = df[col].dropna()
        if len(valid) == 0:
            continue
        
        win_rate = (valid > 0).sum() / len(valid) * 100
        avg_return = valid.mean()
        median_return = valid.median()
        max_return = valid.max()
        min_return = valid.min()
        
        print(f"\n【{period}收益】")
        print(f"  信号数: {len(valid)}")
        print(f"  胜率: {win_rate:.1f}%")
        print(f"  平均收益: {avg_return:+.2f}%")
        print(f"  中位数收益: {median_return:+.2f}%")
        print(f"  最大收益: {max_return:+.2f}%")
        print(f"  最大亏损: {min_return:+.2f}%")
        
        # 分位置统计
        if len(above_zero) > 0:
            above_valid = above_zero[col].dropna()
            if len(above_valid) > 0:
                print(f"  0轴上方: 胜率{(above_valid > 0).sum() / len(above_valid) * 100:.1f}%, "
                      f"平均{above_valid.mean():+.2f}%")
        
        if len(below_zero) > 0:
            below_valid = below_zero[col].dropna()
            if len(below_valid) > 0:
                print(f"  0轴下方: 胜率{(below_valid > 0).sum() / len(below_valid) * 100:.1f}%, "
                      f"平均{below_valid.mean():+.2f}%")
    
    # 持有到死叉统计
    print("\n" + "=" * 70)
    print("持有到死叉统计")
    print("=" * 70)
    
    with_death = df[df['持有收益'].notna()]
    if len(with_death) > 0:
        print(f"\n有死叉信号数: {len(with_death)} ({len(with_death)/len(df)*100:.1f}%)")
        print(f"平均持有天数: {with_death['持有天数'].mean():.1f}天")
        print(f"平均持有收益: {with_death['持有收益'].mean():+.2f}%")
        print(f"持有胜率: {(with_death['持有收益'] > 0).sum() / len(with_death) * 100:.1f}%")
        
        # 按位置统计
        above_death = with_death[with_death['位置'] == '0轴上方']
        below_death = with_death[with_death['位置'] == '0轴下方']
        
        if len(above_death) > 0:
            print(f"\n0轴上方持有到死叉:")
            print(f"  平均持有天数: {above_death['持有天数'].mean():.1f}天")
            print(f"  平均收益: {above_death['持有收益'].mean():+.2f}%")
            print(f"  胜率: {(above_death['持有收益'] > 0).sum() / len(above_death) * 100:.1f}%")
        
        if len(below_death) > 0:
            print(f"\n0轴下方持有到死叉:")
            print(f"  平均持有天数: {below_death['持有天数'].mean():.1f}天")
            print(f"  平均收益: {below_death['持有收益'].mean():+.2f}%")
            print(f"  胜率: {(below_death['持有收益'] > 0).sum() / len(below_death) * 100:.1f}%")
    
    # MACD值分组统计
    print("\n" + "=" * 70)
    print("按MACD值分组统计（10日收益）")
    print("=" * 70)
    
    if '10日收益' in df.columns:
        df['MACD分组'] = pd.cut(df['MACD'], 
                               bins=[-np.inf, -0.5, 0, 0.5, 1.0, np.inf],
                               labels=['<-0.5', '-0.5~0', '0~0.5', '0.5~1.0', '>1.0'])
        
        for group in ['<-0.5', '-0.5~0', '0~0.5', '0.5~1.0', '>1.0']:
            group_data = df[df['MACD分组'] == group]['10日收益'].dropna()
            if len(group_data) > 0:
                print(f"\nMACD {group}:")
                print(f"  信号数: {len(group_data)}")
                print(f"  胜率: {(group_data > 0).sum() / len(group_data) * 100:.1f}%")
                print(f"  平均收益: {group_data.mean():+.2f}%")


def export_results(df):
    """导出回测结果"""
    if len(df) == 0:
        return
    
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    
    filename = f"MACD金叉回测_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        # Sheet1: 全部信号
        df.to_excel(writer, index=False, sheet_name='全部信号')
        
        # Sheet2: 0轴上方
        above = df[df['位置'] == '0轴上方']
        if len(above) > 0:
            above.to_excel(writer, index=False, sheet_name='0轴上方')
        
        # Sheet3: 0轴下方
        below = df[df['位置'] == '0轴下方']
        if len(below) > 0:
            below.to_excel(writer, index=False, sheet_name='0轴下方')
        
        # Sheet4: 统计分析
        stats = []
        for period in ['1日', '3日', '5日', '10日', '20日']:
            col = f'{period}收益'
            if col in df.columns:
                valid = df[col].dropna()
                if len(valid) > 0:
                    stats.append({
                        '周期': period,
                        '信号数': len(valid),
                        '胜率': f"{(valid > 0).sum() / len(valid) * 100:.1f}%",
                        '平均收益': f"{valid.mean():+.2f}%",
                        '中位数收益': f"{valid.median():+.2f}%",
                        '最大收益': f"{valid.max():+.2f}%",
                        '最大亏损': f"{valid.min():+.2f}%"
                    })
        
        stats_df = pd.DataFrame(stats)
        stats_df.to_excel(writer, index=False, sheet_name='统计分析')
    
    print(f"\n✓ 回测结果已保存: {filename}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='MACD金叉策略回测')
    parser.add_argument('--sample', type=int, default=100, help='样本数量')
    args = parser.parse_args()
    
    # 回测
    df = backtest_sample_stocks(sample_size=args.sample)
    
    # 分析
    analyze_results(df)
    
    # 导出
    export_results(df)


if __name__ == "__main__":
    main()
