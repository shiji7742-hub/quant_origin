"""
年报扭亏策略回测
回测逻辑：找到最近已发布年报扭亏的股票，检查年报前一天的信号和后续表现
"""
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from data_fetcher import get_stock_history
import time

def get_recent_annual_reports(days_back=60):
    """
    获取最近已发布年报的股票
    
    Args:
        days_back: 往前查找天数
    
    Returns:
        DataFrame: 包含股票代码、名称、实际披露日期
    """
    try:
        # 获取2024年年报披露情况
        df = ak.stock_report_disclosure(date="2024-12-31")
        
        if df is None or len(df) == 0:
            print("未获取到年报披露数据")
            return pd.DataFrame()
        
        # 找到实际披露日期列
        date_col = None
        for col in ['实际披露日期', '披露日期', '预约披露日期']:
            if col in df.columns:
                date_col = col
                break
        
        if date_col is None:
            print(f"未找到日期列，可用列: {df.columns.tolist()}")
            return pd.DataFrame()
        
        # 转换日期
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        df = df.dropna(subset=[date_col])
        
        # 筛选最近days_back天内披露的
        today = datetime.now()
        start_date = today - timedelta(days=days_back)
        
        df = df[(df[date_col] >= start_date) & (df[date_col] <= today)]
        
        # 统一列名
        result = pd.DataFrame()
        for col in ['股票代码', '代码']:
            if col in df.columns:
                result['股票代码'] = df[col]
                break
        
        for col in ['股票简称', '简称', '名称']:
            if col in df.columns:
                result['股票名称'] = df[col]
                break
        
        result['披露日期'] = df[date_col]
        
        return result
    
    except Exception as e:
        print(f"获取年报披露数据失败: {e}")
        return pd.DataFrame()


def check_annual_turnaround(symbol):
    """
    检查年报是否扭亏
    
    Args:
        symbol: 股票代码
    
    Returns:
        dict: 扭亏信息
    """
    try:
        # 获取财务数据
        df = ak.stock_financial_report_sina(stock=symbol, symbol="利润表")
        
        if df is None or len(df) < 2:
            return {'is_turnaround': False, 'reason': '财务数据不足'}
        
        df = df.sort_values('报告期', ascending=False)
        
        # 找到2024年报和2023年报
        annual_2024 = df[df['报告期'].str.contains('2024')]
        annual_2023 = df[df['报告期'].str.contains('2023')]
        
        if len(annual_2024) == 0 or len(annual_2023) == 0:
            return {'is_turnaround': False, 'reason': '年报数据不全'}
        
        profit_2024 = annual_2024.iloc[0].get('净利润', 0)
        profit_2023 = annual_2023.iloc[0].get('净利润', 0)
        
        # 判断扭亏：2023亏损，2024盈利
        is_turnaround = (profit_2023 < 0) and (profit_2024 > 0)
        
        return {
            'is_turnaround': is_turnaround,
            'profit_2024': profit_2024,
            'profit_2023': profit_2023,
            'reason': '年报扭亏' if is_turnaround else '未扭亏'
        }
    
    except Exception as e:
        return {'is_turnaround': False, 'reason': f'获取失败: {e}'}


def check_signal_before_report(df, report_date, days_before=1):
    """
    检查年报前N天的信号
    
    Args:
        df: K线数据
        report_date: 年报披露日期
        days_before: 提前天数
    
    Returns:
        dict: 信号检测结果
    """
    if df is None or len(df) < 10:
        return {'has_signal': False, 'reason': '数据不足'}
    
    # 找到年报前一天的数据
    df['日期'] = pd.to_datetime(df['日期'])
    target_date = report_date - timedelta(days=days_before)
    
    # 找到最接近的交易日
    df_before = df[df['日期'] <= target_date]
    if len(df_before) == 0:
        return {'has_signal': False, 'reason': '无年报前数据'}
    
    # 获取年报前10天的数据
    signal_idx = len(df_before) - 1
    start_idx = max(0, signal_idx - 9)
    df_signal = df.iloc[start_idx:signal_idx+1]
    
    if len(df_signal) < 5:
        return {'has_signal': False, 'reason': '信号期数据不足'}
    
    # 检查横盘（波动率<5%）
    high = df_signal['最高'].max()
    low = df_signal['最低'].min()
    avg_price = df_signal['收盘'].mean()
    volatility = (high - low) / avg_price
    is_sideways = volatility < 0.05
    
    # 检查振幅（主力控盘）
    df_signal['振幅'] = (df_signal['最高'] - df_signal['最低']) / df_signal['最低'] * 100
    avg_amplitude = df_signal['振幅'].mean()
    low_amplitude = avg_amplitude < 5.0
    
    # 检查换手率（如果有）
    if '换手率' in df_signal.columns:
        avg_turnover = df_signal['换手率'].mean()
        low_turnover = avg_turnover < 3.0
    else:
        avg_turnover = 0
        low_turnover = False
    
    # 综合判断
    has_signal = is_sideways or low_amplitude or low_turnover
    
    signal_date = df_signal.iloc[-1]['日期']
    signal_price = df_signal.iloc[-1]['收盘']
    
    return {
        'has_signal': has_signal,
        'signal_date': signal_date,
        'signal_price': signal_price,
        'volatility': volatility * 100,
        'is_sideways': is_sideways,
        'avg_amplitude': avg_amplitude,
        'low_amplitude': low_amplitude,
        'avg_turnover': avg_turnover,
        'low_turnover': low_turnover,
        'reason': f"波动{volatility*100:.1f}%，振幅{avg_amplitude:.1f}%，换手{avg_turnover:.1f}%"
    }


def calculate_returns_after_report(df, report_date, holding_days=[1, 3, 5, 10]):
    """
    计算年报后的收益率
    
    Args:
        df: K线数据
        report_date: 年报披露日期
        holding_days: 持有天数列表
    
    Returns:
        dict: 各持有期收益率
    """
    if df is None or len(df) < 5:
        return {f'{d}日收益': None for d in holding_days}
    
    df['日期'] = pd.to_datetime(df['日期'])
    
    # 找到年报当天或之后的第一个交易日
    df_after = df[df['日期'] >= report_date]
    if len(df_after) == 0:
        return {f'{d}日收益': None for d in holding_days}
    
    buy_price = df_after.iloc[0]['开盘']  # 年报当天开盘价买入
    buy_date = df_after.iloc[0]['日期']
    
    returns = {'买入日期': buy_date, '买入价': buy_price}
    
    for days in holding_days:
        if len(df_after) > days:
            sell_price = df_after.iloc[days]['收盘']
            ret = (sell_price - buy_price) / buy_price * 100
            returns[f'{days}日收益'] = ret
        else:
            returns[f'{days}日收益'] = None
    
    return returns


def backtest_annual_turnaround(days_back=60, manual_stocks=None):
    """
    回测年报扭亏策略
    
    Args:
        days_back: 往前查找天数
        manual_stocks: 手动指定股票列表 [(代码, 名称, 披露日期), ...]
    
    Returns:
        DataFrame: 回测结果
    """
    print("=" * 80)
    print("年报扭亏策略回测")
    print("=" * 80)
    
    # 1. 获取最近已披露年报的股票
    if manual_stocks:
        print(f"\n[1/4] 使用手动指定的 {len(manual_stocks)} 只股票...")
        recent_reports = pd.DataFrame(manual_stocks, columns=['股票代码', '股票名称', '披露日期'])
        recent_reports['披露日期'] = pd.to_datetime(recent_reports['披露日期'])
    else:
        print(f"\n[1/4] 获取最近{days_back}天内已披露年报的股票...")
        recent_reports = get_recent_annual_reports(days_back)
    
    if len(recent_reports) == 0:
        print("未找到已披露年报的股票")
        print("\n提示: 可以使用 manual_stocks 参数手动指定")
        print("示例: backtest_annual_turnaround(manual_stocks=[('600000', '浦发银行', '2025-03-28')])")
        return pd.DataFrame()
    
    print(f"找到 {len(recent_reports)} 只股票已披露年报")
    
    # 2. 逐个回测
    results = []
    total = len(recent_reports)
    
    for idx, row in recent_reports.iterrows():
        symbol = row['股票代码']
        name = row['股票名称']
        report_date = row['披露日期']
        
        print(f"\n[{idx+1}/{total}] 回测 {symbol} {name} (披露日期: {report_date.strftime('%Y-%m-%d')})")
        
        try:
            # 检查是否年报扭亏
            print("  - 检查年报扭亏...")
            turnaround_info = check_annual_turnaround(symbol)
            
            if not turnaround_info['is_turnaround']:
                print(f"    ✗ {turnaround_info['reason']}")
                continue
            
            print(f"    ✓ 年报扭亏: 2024年盈利 {turnaround_info['profit_2024']/10000:.2f}万")
            
            # 获取K线数据（年报前后各30天）
            print("  - 获取K线数据...")
            df = get_stock_history(symbol, days=90)
            
            if df is None or len(df) < 20:
                print("    ✗ K线数据不足")
                continue
            
            # 检查年报前一天的信号
            print("  - 检查年报前信号...")
            signal_info = check_signal_before_report(df, report_date, days_before=1)
            
            if not signal_info['has_signal']:
                print(f"    ✗ {signal_info['reason']}")
                signal_score = 0
            else:
                print(f"    ✓ {signal_info['reason']}")
                signal_score = 0
                signal_score += 40 if signal_info['is_sideways'] else 0
                signal_score += 30 if signal_info['low_amplitude'] else 0
                signal_score += 30 if signal_info['low_turnover'] else 0
            
            # 计算年报后收益
            print("  - 计算年报后收益...")
            returns_info = calculate_returns_after_report(df, report_date, [1, 3, 5, 10])
            
            if returns_info.get('1日收益') is not None:
                print(f"    收益: 1日{returns_info['1日收益']:.2f}%, " +
                      f"3日{returns_info.get('3日收益', 0):.2f}%, " +
                      f"5日{returns_info.get('5日收益', 0):.2f}%, " +
                      f"10日{returns_info.get('10日收益', 0):.2f}%")
            
            # 汇总结果
            result = {
                '股票代码': symbol,
                '股票名称': name,
                '披露日期': report_date.strftime('%Y-%m-%d'),
                '年报扭亏': '✓',
                '2024利润(万)': turnaround_info['profit_2024'] / 10000,
                '2023利润(万)': turnaround_info['profit_2023'] / 10000,
                '年报前信号': '✓' if signal_info['has_signal'] else '✗',
                '信号评分': signal_score,
                '波动率%': signal_info.get('volatility', 0),
                '振幅%': signal_info.get('avg_amplitude', 0),
                '换手率%': signal_info.get('avg_turnover', 0),
                '横盘': '✓' if signal_info.get('is_sideways') else '✗',
                '低振幅': '✓' if signal_info.get('low_amplitude') else '✗',
                '低换手': '✓' if signal_info.get('low_turnover') else '✗',
                '买入价': returns_info.get('买入价', 0),
                '1日收益%': returns_info.get('1日收益'),
                '3日收益%': returns_info.get('3日收益'),
                '5日收益%': returns_info.get('5日收益'),
                '10日收益%': returns_info.get('10日收益'),
            }
            
            results.append(result)
            
            time.sleep(0.5)
        
        except Exception as e:
            print(f"  ✗ 处理失败: {e}")
            continue
    
    # 3. 生成统计
    if len(results) == 0:
        print("\n未找到符合条件的股票")
        return pd.DataFrame()
    
    df_result = pd.DataFrame(results)
    
    print("\n" + "=" * 80)
    print("回测结果统计")
    print("=" * 80)
    
    # 整体统计
    total_count = len(df_result)
    signal_count = len(df_result[df_result['年报前信号'] == '✓'])
    
    print(f"\n样本总数: {total_count}")
    print(f"有信号数: {signal_count} ({signal_count/total_count*100:.1f}%)")
    
    # 收益统计
    for days in [1, 3, 5, 10]:
        col = f'{days}日收益%'
        valid_data = df_result[df_result[col].notna()]
        
        if len(valid_data) > 0:
            avg_return = valid_data[col].mean()
            win_rate = len(valid_data[valid_data[col] > 0]) / len(valid_data) * 100
            max_return = valid_data[col].max()
            min_return = valid_data[col].min()
            
            print(f"\n{days}日持有:")
            print(f"  平均收益: {avg_return:.2f}%")
            print(f"  胜率: {win_rate:.1f}%")
            print(f"  最大收益: {max_return:.2f}%")
            print(f"  最大亏损: {min_return:.2f}%")
    
    # 有信号 vs 无信号对比
    print("\n" + "=" * 80)
    print("信号有效性分析")
    print("=" * 80)
    
    df_with_signal = df_result[df_result['年报前信号'] == '✓']
    df_without_signal = df_result[df_result['年报前信号'] == '✗']
    
    for days in [1, 3, 5, 10]:
        col = f'{days}日收益%'
        
        with_signal = df_with_signal[df_with_signal[col].notna()]
        without_signal = df_without_signal[df_without_signal[col].notna()]
        
        if len(with_signal) > 0 and len(without_signal) > 0:
            avg_with = with_signal[col].mean()
            avg_without = without_signal[col].mean()
            
            print(f"\n{days}日持有:")
            print(f"  有信号平均收益: {avg_with:.2f}%")
            print(f"  无信号平均收益: {avg_without:.2f}%")
            print(f"  信号优势: {avg_with - avg_without:+.2f}%")
    
    # 4. 保存结果
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'年报扭亏回测_{timestamp}.xlsx'
    
    # 按1日收益排序
    df_result = df_result.sort_values('1日收益%', ascending=False, na_position='last')
    
    df_result.to_excel(filename, index=False, engine='openpyxl')
    print(f"\n回测结果已保存到: {filename}")
    
    return df_result


if __name__ == '__main__':
    # 方式1: 自动回测最近60天披露的年报
    # df = backtest_annual_turnaround(days_back=60)
    
    # 方式2: 手动指定股票（推荐）
    # 格式: (股票代码, 股票名称, 披露日期)
    manual_list = [
        # 示例：请替换为实际的扭亏股票
        ('600000', '浦发银行', '2025-03-28'),
        ('000001', '平安银行', '2025-03-25'),
        ('600519', '贵州茅台', '2025-04-01'),
        # 添加更多已知的扭亏股票...
    ]
    
    print("=" * 80)
    print("提示: 请在 manual_list 中添加最近已披露年报扭亏的股票")
    print("或者取消注释第一行，使用自动扫描模式")
    print("=" * 80)
    print()
    
    # 使用手动列表回测
    df = backtest_annual_turnaround(manual_stocks=manual_list)
