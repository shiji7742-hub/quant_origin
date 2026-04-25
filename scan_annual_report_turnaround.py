"""
年报扭亏策略扫描
规律：年报前一天，季报扭亏 + 横盘整理 + 大单间歇性上打 = 年报可能扭亏
"""
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from data_fetcher import get_all_stocks, get_stock_history, get_intraday_data
from indicators import calculate_indicators
import time

def get_upcoming_annual_reports(days_ahead=3):
    """
    获取即将发布年报的股票列表
    
    Args:
        days_ahead: 提前几天预警（默认3天）
    
    Returns:
        DataFrame: 包含股票代码、名称、预约披露日期
    """
    try:
        # 获取年报预约披露时间表（使用2024年年报）
        # API: stock_report_disclosure
        df = ak.stock_report_disclosure(date="2024-12-31")
        
        if df is None or len(df) == 0:
            print("未获取到年报披露时间表")
            return pd.DataFrame()
        
        # 列名可能是：股票代码、股票简称、预约披露日期
        # 转换日期格式
        date_col = None
        for col in ['预约披露日期', '披露日期', '实际披露日期']:
            if col in df.columns:
                date_col = col
                break
        
        if date_col is None:
            print(f"未找到日期列，可用列: {df.columns.tolist()}")
            return pd.DataFrame()
        
        df[date_col] = pd.to_datetime(df[date_col])
        
        # 筛选未来days_ahead天内要披露的
        today = datetime.now()
        target_date = today + timedelta(days=days_ahead)
        
        df = df[
            (df[date_col] >= today) & 
            (df[date_col] <= target_date)
        ]
        
        # 统一列名
        result_cols = []
        for col in ['股票代码', '代码']:
            if col in df.columns:
                result_cols.append(col)
                break
        
        for col in ['股票简称', '简称', '名称']:
            if col in df.columns:
                result_cols.append(col)
                break
        
        result_cols.append(date_col)
        
        df_result = df[result_cols].copy()
        df_result.columns = ['股票代码', '股票简称', '预约披露日期']
        
        return df_result
    
    except Exception as e:
        print(f"获取年报披露时间表失败: {e}")
        print("提示: 可能需要手动指定股票列表进行测试")
        return pd.DataFrame()


def check_quarterly_turnaround(symbol):
    """
    检查最近季报是否扭亏
    
    Args:
        symbol: 股票代码
    
    Returns:
        dict: {'is_turnaround': bool, 'q3_profit': float, 'q2_profit': float}
    """
    try:
        # 获取财务数据
        df = ak.stock_financial_report_sina(stock=symbol, symbol="利润表")
        
        if df is None or len(df) < 2:
            return {'is_turnaround': False, 'reason': '财务数据不足'}
        
        # 获取最近两个季度的净利润
        df = df.sort_values('报告期', ascending=False)
        latest_quarter = df.iloc[0]
        prev_quarter = df.iloc[1]
        
        # 提取净利润（单位：元）
        latest_profit = latest_quarter.get('净利润', 0)
        prev_profit = prev_quarter.get('净利润', 0)
        
        # 判断是否扭亏：上季度亏损，本季度盈利
        is_turnaround = (prev_profit < 0) and (latest_profit > 0)
        
        return {
            'is_turnaround': is_turnaround,
            'latest_quarter': latest_quarter['报告期'],
            'latest_profit': latest_profit,
            'prev_quarter': prev_quarter['报告期'],
            'prev_profit': prev_profit,
            'reason': '季报扭亏' if is_turnaround else '未扭亏'
        }
    
    except Exception as e:
        return {'is_turnaround': False, 'reason': f'获取财务数据失败: {e}'}


def check_sideways_consolidation(df, days=10, max_volatility=0.05):
    """
    检查是否横盘整理
    
    Args:
        df: K线数据
        days: 检查天数
        max_volatility: 最大波动率阈值（默认5%）
    
    Returns:
        dict: {'is_sideways': bool, 'volatility': float}
    """
    if df is None or len(df) < days:
        return {'is_sideways': False, 'volatility': 0, 'reason': '数据不足'}
    
    recent = df.tail(days)
    high = recent['最高'].max()
    low = recent['最低'].min()
    avg_price = recent['收盘'].mean()
    
    # 计算波动率
    volatility = (high - low) / avg_price
    
    is_sideways = volatility <= max_volatility
    
    return {
        'is_sideways': is_sideways,
        'volatility': volatility,
        'volatility_pct': volatility * 100,
        'high': high,
        'low': low,
        'reason': f'{days}日波动率{volatility*100:.2f}%' + ('，横盘整理' if is_sideways else '，波动较大')
    }


def check_big_order_push(df_intraday, threshold=0.3):
    """
    检查是否有大单间歇性上打
    
    Args:
        df_intraday: 分时数据（5分钟K线）
        threshold: 大单成交占比阈值（默认30%）
    
    Returns:
        dict: {'has_big_push': bool, 'big_order_ratio': float}
    """
    if df_intraday is None or len(df_intraday) < 10:
        return {'has_big_push': False, 'reason': '分时数据不足'}
    
    # 使用最近1天的数据（约48条5分钟K线）
    recent = df_intraday.tail(48)
    
    # 计算成交量均值和标准差
    vol_mean = recent['成交量'].mean()
    vol_std = recent['成交量'].std()
    
    # 大单定义：成交量 > 均值 + 1.5倍标准差
    big_order_threshold = vol_mean + 1.5 * vol_std
    big_orders = recent[recent['成交量'] > big_order_threshold]
    
    # 大单占比
    big_order_ratio = len(big_orders) / len(recent)
    
    # 检查大单是否向上（收盘价 > 开盘价）
    if len(big_orders) > 0:
        up_orders = big_orders[big_orders['收盘'] > big_orders['开盘']]
        up_ratio = len(up_orders) / len(big_orders)
    else:
        up_ratio = 0
    
    # 判断：大单占比 > 阈值 且 向上大单占比 > 60%
    has_big_push = (big_order_ratio > threshold) and (up_ratio > 0.6)
    
    return {
        'has_big_push': has_big_push,
        'big_order_ratio': big_order_ratio,
        'big_order_count': len(big_orders),
        'up_order_ratio': up_ratio,
        'reason': f'大单占比{big_order_ratio*100:.1f}%，向上{up_ratio*100:.1f}%' + ('，主力上攻' if has_big_push else '')
    }


def check_main_control(df, days=10):
    """
    检查主力控盘迹象
    
    Args:
        df: K线数据
        days: 检查天数
    
    Returns:
        dict: {'has_control': bool, 'turnover_rate': float}
    """
    if df is None or len(df) < days:
        return {'has_control': False, 'reason': '数据不足'}
    
    recent = df.tail(days)
    
    # 计算换手率（如果有）
    if '换手率' in recent.columns:
        avg_turnover = recent['换手率'].mean()
        # 低换手率（<3%）+ 横盘 = 主力控盘
        low_turnover = avg_turnover < 3.0
    else:
        low_turnover = False
        avg_turnover = 0
    
    # 计算振幅
    recent['振幅'] = (recent['最高'] - recent['最低']) / recent['最低'] * 100
    avg_amplitude = recent['振幅'].mean()
    
    # 低振幅（<5%）= 控盘
    low_amplitude = avg_amplitude < 5.0
    
    has_control = low_turnover or low_amplitude
    
    return {
        'has_control': has_control,
        'avg_turnover': avg_turnover,
        'avg_amplitude': avg_amplitude,
        'reason': f'换手率{avg_turnover:.2f}%，振幅{avg_amplitude:.2f}%' + ('，主力控盘' if has_control else '')
    }


def scan_annual_turnaround_stocks(days_ahead=3, save_excel=True, manual_stocks=None):
    """
    扫描年报扭亏潜力股
    
    Args:
        days_ahead: 提前几天预警
        save_excel: 是否保存Excel
        manual_stocks: 手动指定股票列表 [(代码, 名称, 日期), ...]
    
    Returns:
        DataFrame: 符合条件的股票列表
    """
    print("=" * 60)
    print("年报扭亏策略扫描")
    print("=" * 60)
    
    # 1. 获取即将发布年报的股票
    if manual_stocks:
        print(f"\n[1/5] 使用手动指定的 {len(manual_stocks)} 只股票...")
        upcoming_reports = pd.DataFrame(manual_stocks, columns=['股票代码', '股票简称', '预约披露日期'])
        upcoming_reports['预约披露日期'] = pd.to_datetime(upcoming_reports['预约披露日期'])
    else:
        print(f"\n[1/5] 获取未来{days_ahead}天内要发布年报的股票...")
        upcoming_reports = get_upcoming_annual_reports(days_ahead)
    
    if len(upcoming_reports) == 0:
        print("未找到即将发布年报的股票")
        print("\n提示: 可以使用 manual_stocks 参数手动指定股票列表")
        print("示例: scan_annual_turnaround_stocks(manual_stocks=[('600000', '浦发银行', '2026-03-01')])")
        return pd.DataFrame()
    
    print(f"找到 {len(upcoming_reports)} 只股票即将发布年报")
    
    # 2. 逐个检查
    results = []
    total = len(upcoming_reports)
    
    for idx, row in upcoming_reports.iterrows():
        symbol = row['股票代码']
        name = row['股票简称']
        report_date = row['预约披露日期']
        
        print(f"\n[{idx+1}/{total}] 检查 {symbol} {name} (年报日期: {report_date.strftime('%Y-%m-%d')})")
        
        try:
            # 检查季报是否扭亏
            print("  - 检查季报扭亏...")
            turnaround_info = check_quarterly_turnaround(symbol)
            
            if not turnaround_info['is_turnaround']:
                print(f"    ✗ {turnaround_info['reason']}")
                continue
            
            print(f"    ✓ 季报扭亏: {turnaround_info['latest_quarter']} 盈利 {turnaround_info['latest_profit']/10000:.2f}万")
            
            # 获取K线数据
            print("  - 获取K线数据...")
            df = get_stock_history(symbol, days=30)
            
            if df is None or len(df) < 10:
                print("    ✗ K线数据不足")
                continue
            
            # 检查横盘整理
            print("  - 检查横盘整理...")
            sideways_info = check_sideways_consolidation(df, days=10, max_volatility=0.05)
            
            if not sideways_info['is_sideways']:
                print(f"    ✗ {sideways_info['reason']}")
                continue
            
            print(f"    ✓ {sideways_info['reason']}")
            
            # 获取分时数据
            print("  - 获取分时数据...")
            df_intraday = get_intraday_data(symbol, days=1)
            
            # 检查大单上打
            print("  - 检查大单上打...")
            big_order_info = check_big_order_push(df_intraday, threshold=0.2)
            
            if not big_order_info['has_big_push']:
                print(f"    ✗ {big_order_info['reason']}")
                # 不强制要求，继续
            else:
                print(f"    ✓ {big_order_info['reason']}")
            
            # 检查主力控盘
            print("  - 检查主力控盘...")
            control_info = check_main_control(df, days=10)
            print(f"    {'✓' if control_info['has_control'] else '○'} {control_info['reason']}")
            
            # 汇总结果
            latest = df.iloc[-1]
            result = {
                '股票代码': symbol,
                '股票名称': name,
                '年报日期': report_date.strftime('%Y-%m-%d'),
                '距离天数': (report_date - datetime.now()).days,
                '最新价': latest['收盘'],
                '季报扭亏': '✓',
                '扭亏季度': turnaround_info['latest_quarter'],
                '最新季度利润(万)': turnaround_info['latest_profit'] / 10000,
                '横盘整理': '✓' if sideways_info['is_sideways'] else '✗',
                '波动率': f"{sideways_info['volatility_pct']:.2f}%",
                '大单上打': '✓' if big_order_info['has_big_push'] else '✗',
                '大单占比': f"{big_order_info['big_order_ratio']*100:.1f}%",
                '主力控盘': '✓' if control_info['has_control'] else '○',
                '换手率': f"{control_info['avg_turnover']:.2f}%",
                '振幅': f"{control_info['avg_amplitude']:.2f}%",
                '综合评分': 0
            }
            
            # 计算综合评分
            score = 0
            score += 30 if turnaround_info['is_turnaround'] else 0  # 季报扭亏
            score += 25 if sideways_info['is_sideways'] else 0      # 横盘整理
            score += 25 if big_order_info['has_big_push'] else 0    # 大单上打
            score += 20 if control_info['has_control'] else 0       # 主力控盘
            result['综合评分'] = score
            
            results.append(result)
            print(f"  ✓ 符合条件！综合评分: {score}")
            
            time.sleep(0.5)  # 避免请求过快
        
        except Exception as e:
            print(f"  ✗ 处理失败: {e}")
            continue
    
    # 3. 生成结果
    if len(results) == 0:
        print("\n未找到符合条件的股票")
        return pd.DataFrame()
    
    df_result = pd.DataFrame(results)
    df_result = df_result.sort_values('综合评分', ascending=False)
    
    print("\n" + "=" * 60)
    print(f"扫描完成！找到 {len(df_result)} 只潜力股")
    print("=" * 60)
    print(df_result.to_string(index=False))
    
    # 4. 保存Excel
    if save_excel:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'年报扭亏潜力股_{timestamp}.xlsx'
        df_result.to_excel(filename, index=False, engine='openpyxl')
        print(f"\n结果已保存到: {filename}")
    
    return df_result


if __name__ == '__main__':
    # 方式1: 自动扫描未来3天内要发布年报的股票
    # df = scan_annual_turnaround_stocks(days_ahead=3, save_excel=True)
    
    # 方式2: 手动指定股票列表（推荐用于测试）
    # 格式: (股票代码, 股票名称, 年报日期)
    manual_list = [
        ('600000', '浦发银行', '2026-03-28'),
        ('000001', '平安银行', '2026-03-25'),
        # 添加更多股票...
    ]
    
    print("提示: 请根据实际情况修改 manual_list 中的股票列表")
    print("或者取消注释第一行，使用自动扫描模式\n")
    
    # 使用手动列表扫描
    df = scan_annual_turnaround_stocks(manual_stocks=manual_list, save_excel=True)
