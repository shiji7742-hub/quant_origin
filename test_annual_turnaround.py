"""
测试年报扭亏策略
"""
from scan_annual_report_turnaround import (
    check_quarterly_turnaround,
    check_sideways_consolidation,
    check_big_order_push,
    check_main_control
)
from data_fetcher import get_stock_history, get_intraday_data

def test_single_stock(symbol, name=""):
    """测试单只股票"""
    print("=" * 60)
    print(f"测试股票: {symbol} {name}")
    print("=" * 60)
    
    # 1. 检查季报扭亏
    print("\n[1] 检查季报扭亏...")
    turnaround_info = check_quarterly_turnaround(symbol)
    print(f"结果: {turnaround_info}")
    
    # 2. 获取K线数据
    print("\n[2] 获取K线数据...")
    df = get_stock_history(symbol, days=30)
    if df is None or len(df) == 0:
        print("✗ 获取K线数据失败")
        return
    print(f"✓ 获取到 {len(df)} 天K线数据")
    
    # 3. 检查横盘整理
    print("\n[3] 检查横盘整理...")
    sideways_info = check_sideways_consolidation(df, days=10, max_volatility=0.05)
    print(f"结果: {sideways_info}")
    
    # 4. 获取分时数据
    print("\n[4] 获取分时数据...")
    df_intraday = get_intraday_data(symbol, days=1)
    if df_intraday is None or len(df_intraday) == 0:
        print("✗ 获取分时数据失败")
    else:
        print(f"✓ 获取到 {len(df_intraday)} 条分时数据")
        
        # 5. 检查大单上打
        print("\n[5] 检查大单上打...")
        big_order_info = check_big_order_push(df_intraday, threshold=0.2)
        print(f"结果: {big_order_info}")
    
    # 6. 检查主力控盘
    print("\n[6] 检查主力控盘...")
    control_info = check_main_control(df, days=10)
    print(f"结果: {control_info}")
    
    # 综合评分
    print("\n" + "=" * 60)
    print("综合评估:")
    score = 0
    if turnaround_info.get('is_turnaround'):
        print("✓ 季报扭亏 (+30分)")
        score += 30
    else:
        print(f"✗ 季报未扭亏: {turnaround_info.get('reason')}")
    
    if sideways_info.get('is_sideways'):
        print(f"✓ 横盘整理 (+25分) - 波动率{sideways_info['volatility_pct']:.2f}%")
        score += 25
    else:
        print(f"✗ 波动较大: {sideways_info.get('reason')}")
    
    if df_intraday is not None and big_order_info.get('has_big_push'):
        print(f"✓ 大单上打 (+25分) - 大单占比{big_order_info['big_order_ratio']*100:.1f}%")
        score += 25
    else:
        print("✗ 大单不明显")
    
    if control_info.get('has_control'):
        print(f"✓ 主力控盘 (+20分) - {control_info.get('reason')}")
        score += 20
    else:
        print("○ 控盘不明显")
    
    print(f"\n综合评分: {score}/100")
    if score >= 80:
        print("评级: ⭐⭐⭐ 强烈推荐")
    elif score >= 60:
        print("评级: ⭐⭐ 值得关注")
    elif score >= 40:
        print("评级: ⭐ 观察")
    else:
        print("评级: 不符合条件")
    print("=" * 60)


if __name__ == '__main__':
    # 测试示例股票（请替换为实际股票代码）
    test_stocks = [
        ('600000', '浦发银行'),
        ('000001', '平安银行'),
        # 添加更多测试股票...
    ]
    
    for symbol, name in test_stocks:
        test_single_stock(symbol, name)
        print("\n\n")
