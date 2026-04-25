"""
年报扭亏策略 - 真实数据回测
尝试获取真实的扭亏股票数据进行回测
"""
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import time
from data_fetcher import get_stock_history

# 一些已知的2024年可能扭亏的股票（需要验证）
# 这些是根据公开信息整理的案例
KNOWN_TURNAROUND_STOCKS = [
    # 格式: (代码, 名称, 年报披露日期估计)
    ('600000', '浦发银行', '2025-03-28'),
    ('600036', '招商银行', '2025-03-25'),
    ('601398', '工商银行', '2025-03-28'),
    ('601988', '中国银行', '2025-03-29'),
    ('600519', '贵州茅台', '2025-04-01'),
    ('000858', '五粮液', '2025-04-10'),
    ('000002', '万科A', '2025-03-30'),
    ('600030', '中信证券', '2025-04-15'),
    ('601318', '中国平安', '2025-03-20'),
    ('600887', '伊利股份', '2025-04-08'),
]

def test_data_access():
    """测试数据获取"""
    print("=" * 80)
    print("测试数据获取")
    print("=" * 80)
    
    test_code = '600000'
    print(f"\n尝试获取 {test_code} 的数据...")
    
    try:
        # 测试K线数据
        print("1. 测试K线数据...")
        df = get_stock_history(test_code, days=30)
        if df is not None and len(df) > 0:
            print(f"   ✓ 成功获取K线数据，共{len(df)}条")
            print(f"   最新日期: {df.iloc[-1]['日期']}")
            print(f"   最新价格: {df.iloc[-1]['收盘']}")
            return True
        else:
            print("   ✗ K线数据为空")
            return False
    except Exception as e:
        print(f"   ✗ 获取失败: {e}")
        return False


def check_stock_signal(code, name, days=10):
    """检查单只股票的信号"""
    try:
        df = get_stock_history(code, days=30)
        if df is None or len(df) < days:
            return None
        
        # 取最近10天
        recent = df.tail(days)
        
        # 计算横盘（波动率）
        high = recent['最高'].max()
        low = recent['最低'].min()
        avg_price = recent['收盘'].mean()
        volatility = (high - low) / avg_price
        is_sideways = volatility < 0.05
        
        # 计算振幅
        recent['振幅'] = (recent['最高'] - recent['最低']) / recent['最低'] * 100
        avg_amplitude = recent['振幅'].mean()
        low_amplitude = avg_amplitude < 5.0
        
        # 计算换手率（如果有）
        if '换手率' in recent.columns:
            avg_turnover = recent['换手率'].mean()
            low_turnover = avg_turnover < 3.0
        else:
            avg_turnover = 0
            low_turnover = False
        
        # 计算信号评分
        signal_score = 0
        if is_sideways:
            signal_score += 40
        if low_amplitude:
            signal_score += 30
        if low_turnover:
            signal_score += 30
        
        return {
            'code': code,
            'name': name,
            'latest_price': recent.iloc[-1]['收盘'],
            'volatility': volatility * 100,
            'is_sideways': is_sideways,
            'avg_amplitude': avg_amplitude,
            'low_amplitude': low_amplitude,
            'avg_turnover': avg_turnover,
            'low_turnover': low_turnover,
            'signal_score': signal_score,
            'signal_type': '强信号' if signal_score >= 70 else ('中等信号' if signal_score >= 40 else '弱信号')
        }
    except Exception as e:
        print(f"   检查失败: {e}")
        return None


def real_backtest():
    """真实数据回测"""
    print("=" * 80)
    print("年报扭亏策略 - 真实数据回测")
    print("=" * 80)
    
    # 先测试数据获取
    print("\n[步骤1] 测试数据获取...")
    if not test_data_access():
        print("\n✗ 数据获取失败，无法进行真实回测")
        print("\n可能原因:")
        print("  1. 网络连接问题")
        print("  2. API限制")
        print("  3. 数据源暂时不可用")
        print("\n建议:")
        print("  1. 检查网络连接")
        print("  2. 稍后重试")
        print("  3. 或使用模拟回测: python demo_backtest_results.py")
        return None
    
    print("\n✓ 数据获取正常，开始回测...")
    
    # 扫描已知股票
    print("\n[步骤2] 扫描已知股票的当前信号...")
    results = []
    
    for i, (code, name, report_date) in enumerate(KNOWN_TURNAROUND_STOCKS, 1):
        print(f"\n[{i}/{len(KNOWN_TURNAROUND_STOCKS)}] 检查 {code} {name}")
        
        signal_info = check_stock_signal(code, name)
        
        if signal_info:
            print(f"  信号评分: {signal_info['signal_score']}分 ({signal_info['signal_type']})")
            print(f"  波动率: {signal_info['volatility']:.2f}%")
            print(f"  振幅: {signal_info['avg_amplitude']:.2f}%")
            print(f"  换手率: {signal_info['avg_turnover']:.2f}%")
            
            signal_info['report_date'] = report_date
            results.append(signal_info)
        
        time.sleep(0.5)  # 避免请求过快
    
    if len(results) == 0:
        print("\n✗ 未能获取任何股票数据")
        return None
    
    # 生成报告
    df = pd.DataFrame(results)
    
    print("\n" + "=" * 80)
    print("当前信号扫描结果")
    print("=" * 80)
    
    print(f"\n成功扫描: {len(df)} 只股票")
    print("\n按信号评分排序:")
    print(df[['code', 'name', 'signal_score', 'signal_type', 'latest_price']].sort_values('signal_score', ascending=False).to_string(index=False))
    
    # 统计
    print("\n" + "=" * 80)
    print("信号分布")
    print("=" * 80)
    
    strong = df[df['signal_score'] >= 70]
    medium = df[(df['signal_score'] >= 40) & (df['signal_score'] < 70)]
    weak = df[df['signal_score'] < 40]
    
    print(f"\n强信号(≥70分): {len(strong)} 只")
    if len(strong) > 0:
        for _, row in strong.iterrows():
            print(f"  {row['code']} {row['name']} - {row['signal_score']}分")
    
    print(f"\n中等信号(40-69分): {len(medium)} 只")
    if len(medium) > 0:
        for _, row in medium.iterrows():
            print(f"  {row['code']} {row['name']} - {row['signal_score']}分")
    
    print(f"\n弱信号(<40分): {len(weak)} 只")
    if len(weak) > 0:
        for _, row in weak.iterrows():
            print(f"  {row['code']} {row['name']} - {row['signal_score']}分")
    
    # 保存结果
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'真实信号扫描_{timestamp}.xlsx'
    df.to_excel(filename, index=False, engine='openpyxl')
    
    print("\n" + "=" * 80)
    print(f"结果已保存到: {filename}")
    print("=" * 80)
    
    print("\n说明:")
    print("  这是当前时点的信号扫描，不是历史回测")
    print("  因为:")
    print("  1. 这些股票的年报还未披露（预计2025年3-4月）")
    print("  2. 无法确认它们是否真的会扭亏")
    print("  3. 无法计算年报后的收益")
    
    print("\n要进行真实历史回测，需要:")
    print("  1. 找到已经披露年报且确认扭亏的股票")
    print("  2. 获取年报前的K线数据检查信号")
    print("  3. 获取年报后的K线数据计算收益")
    
    print("\n当前可以做的:")
    print("  1. 观察这些股票的信号强度")
    print("  2. 等待年报披露后验证")
    print("  3. 跟踪记录，积累真实案例")
    
    return df


def try_historical_backtest():
    """尝试历史回测（2024年已披露的）"""
    print("=" * 80)
    print("尝试获取2024年已披露年报的股票")
    print("=" * 80)
    
    try:
        # 尝试获取年报披露数据
        print("\n尝试获取年报披露时间表...")
        df = ak.stock_report_disclosure(date="2024-12-31")
        
        if df is not None and len(df) > 0:
            print(f"✓ 获取到 {len(df)} 条记录")
            print("\n前10条:")
            print(df.head(10))
            
            # 筛选已披露的
            date_col = None
            for col in ['实际披露日期', '披露日期']:
                if col in df.columns:
                    date_col = col
                    break
            
            if date_col:
                df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
                df_disclosed = df[df[date_col] < datetime.now()]
                print(f"\n已披露: {len(df_disclosed)} 只")
                
                return df_disclosed
        else:
            print("✗ 未获取到数据")
            return None
    
    except Exception as e:
        print(f"✗ 获取失败: {e}")
        return None


if __name__ == '__main__':
    print("\n年报扭亏策略 - 真实数据回测")
    print("=" * 80)
    print("尝试使用真实数据进行回测")
    print("=" * 80)
    
    print("\n选择模式:")
    print("1. 当前信号扫描（扫描已知股票的当前信号）")
    print("2. 尝试历史回测（需要API支持）")
    
    choice = input("\n请选择 (1/2): ").strip()
    
    if choice == '1':
        df = real_backtest()
    elif choice == '2':
        df = try_historical_backtest()
        if df is not None:
            print("\n获取到历史数据，但需要进一步处理")
            print("建议手动筛选扭亏股票后使用 interactive_backtest.py 回测")
    else:
        print("无效选择")
