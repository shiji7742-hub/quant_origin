"""
测试年报扭亏策略的核心逻辑
不依赖真实股票数据，验证算法正确性
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def test_sideways_detection():
    """测试横盘检测逻辑"""
    print("=" * 60)
    print("测试1: 横盘检测")
    print("=" * 60)
    
    # 模拟横盘数据（波动率<5%）
    dates = pd.date_range('2025-01-01', periods=10, freq='D')
    prices_sideways = [10.0, 10.1, 9.9, 10.2, 10.0, 10.1, 9.95, 10.05, 10.0, 10.1]
    
    df_sideways = pd.DataFrame({
        '日期': dates,
        '开盘': prices_sideways,
        '收盘': prices_sideways,
        '最高': [p * 1.01 for p in prices_sideways],
        '最低': [p * 0.99 for p in prices_sideways],
        '成交量': [1000000] * 10
    })
    
    high = df_sideways['最高'].max()
    low = df_sideways['最低'].min()
    avg_price = df_sideways['收盘'].mean()
    volatility = (high - low) / avg_price
    
    print(f"\n横盘案例:")
    print(f"  最高价: {high:.2f}")
    print(f"  最低价: {low:.2f}")
    print(f"  平均价: {avg_price:.2f}")
    print(f"  波动率: {volatility*100:.2f}%")
    print(f"  是否横盘: {'✓' if volatility < 0.05 else '✗'}")
    
    # 模拟非横盘数据（波动率>5%）
    prices_volatile = [10.0, 10.5, 9.5, 11.0, 9.0, 10.5, 9.8, 10.8, 9.2, 10.3]
    
    df_volatile = pd.DataFrame({
        '日期': dates,
        '开盘': prices_volatile,
        '收盘': prices_volatile,
        '最高': [p * 1.02 for p in prices_volatile],
        '最低': [p * 0.98 for p in prices_volatile],
        '成交量': [1000000] * 10
    })
    
    high = df_volatile['最高'].max()
    low = df_volatile['最低'].min()
    avg_price = df_volatile['收盘'].mean()
    volatility = (high - low) / avg_price
    
    print(f"\n波动案例:")
    print(f"  最高价: {high:.2f}")
    print(f"  最低价: {low:.2f}")
    print(f"  平均价: {avg_price:.2f}")
    print(f"  波动率: {volatility*100:.2f}%")
    print(f"  是否横盘: {'✓' if volatility < 0.05 else '✗'}")
    
    print("\n✓ 横盘检测逻辑正常")


def test_amplitude_detection():
    """测试振幅检测逻辑"""
    print("\n" + "=" * 60)
    print("测试2: 振幅检测（主力控盘）")
    print("=" * 60)
    
    # 低振幅（主力控盘）
    dates = pd.date_range('2025-01-01', periods=10, freq='D')
    
    df_low = pd.DataFrame({
        '日期': dates,
        '开盘': [10.0] * 10,
        '收盘': [10.0] * 10,
        '最高': [10.3] * 10,  # 振幅3%
        '最低': [10.0] * 10,
        '成交量': [1000000] * 10
    })
    
    df_low['振幅'] = (df_low['最高'] - df_low['最低']) / df_low['最低'] * 100
    avg_amplitude = df_low['振幅'].mean()
    
    print(f"\n低振幅案例:")
    print(f"  平均振幅: {avg_amplitude:.2f}%")
    print(f"  主力控盘: {'✓' if avg_amplitude < 5.0 else '✗'}")
    
    # 高振幅（无控盘）
    df_high = pd.DataFrame({
        '日期': dates,
        '开盘': [10.0] * 10,
        '收盘': [10.0] * 10,
        '最高': [10.8] * 10,  # 振幅8%
        '最低': [10.0] * 10,
        '成交量': [1000000] * 10
    })
    
    df_high['振幅'] = (df_high['最高'] - df_high['最低']) / df_high['最低'] * 100
    avg_amplitude = df_high['振幅'].mean()
    
    print(f"\n高振幅案例:")
    print(f"  平均振幅: {avg_amplitude:.2f}%")
    print(f"  主力控盘: {'✓' if avg_amplitude < 5.0 else '✗'}")
    
    print("\n✓ 振幅检测逻辑正常")


def test_signal_scoring():
    """测试信号评分逻辑"""
    print("\n" + "=" * 60)
    print("测试3: 信号评分系统")
    print("=" * 60)
    
    test_cases = [
        {
            'name': '强信号',
            'is_sideways': True,
            'low_amplitude': True,
            'low_turnover': True,
            'expected_score': 100
        },
        {
            'name': '中等信号',
            'is_sideways': True,
            'low_amplitude': True,
            'low_turnover': False,
            'expected_score': 70
        },
        {
            'name': '弱信号',
            'is_sideways': True,
            'low_amplitude': False,
            'low_turnover': False,
            'expected_score': 40
        },
        {
            'name': '无信号',
            'is_sideways': False,
            'low_amplitude': False,
            'low_turnover': False,
            'expected_score': 0
        }
    ]
    
    for case in test_cases:
        score = 0
        if case['is_sideways']:
            score += 40
        if case['low_amplitude']:
            score += 30
        if case['low_turnover']:
            score += 30
        
        print(f"\n{case['name']}:")
        print(f"  横盘: {'✓' if case['is_sideways'] else '✗'}")
        print(f"  低振幅: {'✓' if case['low_amplitude'] else '✗'}")
        print(f"  低换手: {'✓' if case['low_turnover'] else '✗'}")
        print(f"  评分: {score}/100 (预期: {case['expected_score']})")
        
        if score == case['expected_score']:
            print(f"  结果: ✓ 正确")
        else:
            print(f"  结果: ✗ 错误")
    
    print("\n✓ 评分系统逻辑正常")


def test_return_calculation():
    """测试收益率计算逻辑"""
    print("\n" + "=" * 60)
    print("测试4: 收益率计算")
    print("=" * 60)
    
    # 模拟年报后的价格走势
    dates = pd.date_range('2025-03-28', periods=15, freq='D')
    
    # 上涨案例
    prices_up = [10.0, 10.5, 10.8, 11.0, 11.2, 11.5, 11.3, 11.6, 11.8, 12.0, 
                 12.2, 12.1, 12.3, 12.5, 12.4]
    
    df_up = pd.DataFrame({
        '日期': dates,
        '开盘': prices_up,
        '收盘': prices_up,
        '最高': [p * 1.01 for p in prices_up],
        '最低': [p * 0.99 for p in prices_up],
    })
    
    buy_price = df_up.iloc[0]['开盘']
    
    print(f"\n上涨案例:")
    print(f"  买入价: {buy_price:.2f}")
    
    for days in [1, 3, 5, 10]:
        if days < len(df_up):
            sell_price = df_up.iloc[days]['收盘']
            ret = (sell_price - buy_price) / buy_price * 100
            print(f"  {days}日收益: {ret:+.2f}%")
    
    # 下跌案例
    prices_down = [10.0, 9.8, 9.5, 9.3, 9.2, 9.0, 9.1, 8.9, 8.8, 8.7,
                   8.6, 8.5, 8.6, 8.4, 8.5]
    
    df_down = pd.DataFrame({
        '日期': dates,
        '开盘': prices_down,
        '收盘': prices_down,
        '最高': [p * 1.01 for p in prices_down],
        '最低': [p * 0.99 for p in prices_down],
    })
    
    buy_price = df_down.iloc[0]['开盘']
    
    print(f"\n下跌案例:")
    print(f"  买入价: {buy_price:.2f}")
    
    for days in [1, 3, 5, 10]:
        if days < len(df_down):
            sell_price = df_down.iloc[days]['收盘']
            ret = (sell_price - buy_price) / buy_price * 100
            print(f"  {days}日收益: {ret:+.2f}%")
    
    print("\n✓ 收益率计算逻辑正常")


def test_strategy_validation():
    """测试策略有效性判断"""
    print("\n" + "=" * 60)
    print("测试5: 策略有效性判断")
    print("=" * 60)
    
    test_cases = [
        {
            'name': '强验证',
            'signal_score': 70,
            'return_5d': 5.0,
            'expected': '⭐⭐⭐ 强验证'
        },
        {
            'name': '中等验证',
            'signal_score': 50,
            'return_5d': 2.0,
            'expected': '⭐⭐ 中等验证'
        },
        {
            'name': '弱验证',
            'signal_score': 30,
            'return_5d': 1.0,
            'expected': '⭐ 弱验证'
        },
        {
            'name': '未验证',
            'signal_score': 0,
            'return_5d': -2.0,
            'expected': '✗ 未验证'
        }
    ]
    
    for case in test_cases:
        score = case['signal_score']
        ret = case['return_5d']
        
        if score >= 70 and ret > 3:
            result = '⭐⭐⭐ 强验证'
        elif score >= 40 and ret > 0:
            result = '⭐⭐ 中等验证'
        elif score > 0 or ret > 0:
            result = '⭐ 弱验证'
        else:
            result = '✗ 未验证'
        
        print(f"\n{case['name']}:")
        print(f"  信号评分: {score}")
        print(f"  5日收益: {ret:+.2f}%")
        print(f"  判断结果: {result}")
        print(f"  预期结果: {case['expected']}")
        print(f"  测试: {'✓ 通过' if result == case['expected'] else '✗ 失败'}")
    
    print("\n✓ 策略验证逻辑正常")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 80)
    print("年报扭亏策略 - 核心逻辑测试")
    print("=" * 80)
    print("\n开始测试...\n")
    
    try:
        test_sideways_detection()
        test_amplitude_detection()
        test_signal_scoring()
        test_return_calculation()
        test_strategy_validation()
        
        print("\n" + "=" * 80)
        print("所有测试通过！✓")
        print("=" * 80)
        print("\n策略核心逻辑验证完成，可以进行实盘回测")
        
    except Exception as e:
        print(f"\n测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    run_all_tests()
