"""
回测通富微电(002156)
"""
import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
from data_fetcher import get_stock_history

def backtest_tongfu():
    """回测通富微电"""
    code = '002156'
    name = '通富微电'
    
    print("=" * 80)
    print(f"回测: {code} {name}")
    print("=" * 80)
    
    # 1. 获取K线数据
    print("\n[1] 获取K线数据...")
    try:
        df = get_stock_history(code, days=120)
        if df is None or len(df) == 0:
            print("✗ 未获取到数据")
            return
        
        print(f"✓ 获取到 {len(df)} 天K线数据")
        print(f"数据范围: {df.iloc[0]['日期']} 至 {df.iloc[-1]['日期']}")
        
        # 显示最近10天
        print("\n最近10天数据:")
        recent = df.tail(10)
        print(recent[['日期', '开盘', '收盘', '最高', '最低', '成交量', '涨跌幅']].to_string(index=False))
        
    except Exception as e:
        print(f"✗ 获取失败: {e}")
        return
    
    # 2. 分析当前信号
    print("\n" + "=" * 80)
    print("[2] 分析当前信号")
    print("=" * 80)
    
    # 取最近10天分析
    recent_10 = df.tail(10).copy()
    
    # 计算横盘（波动率）
    high = recent_10['最高'].max()
    low = recent_10['最低'].min()
    avg_price = recent_10['收盘'].mean()
    volatility = (high - low) / avg_price
    is_sideways = volatility < 0.05
    
    print(f"\n横盘分析（近10日）:")
    print(f"  最高价: {high:.2f}")
    print(f"  最低价: {low:.2f}")
    print(f"  平均价: {avg_price:.2f}")
    print(f"  波动率: {volatility*100:.2f}%")
    print(f"  是否横盘: {'✓' if is_sideways else '✗'} (标准<5%)")
    
    # 计算振幅
    recent_10['振幅'] = (recent_10['最高'] - recent_10['最低']) / recent_10['最低'] * 100
    avg_amplitude = recent_10['振幅'].mean()
    low_amplitude = avg_amplitude < 5.0
    
    print(f"\n振幅分析（近10日）:")
    print(f"  平均振幅: {avg_amplitude:.2f}%")
    print(f"  是否低振幅: {'✓' if low_amplitude else '✗'} (标准<5%)")
    
    # 计算换手率
    if '换手率' in recent_10.columns:
        avg_turnover = recent_10['换手率'].mean()
        low_turnover = avg_turnover < 3.0
        print(f"\n换手率分析（近10日）:")
        print(f"  平均换手率: {avg_turnover:.2f}%")
        print(f"  是否低换手: {'✓' if low_turnover else '✗'} (标准<3%)")
    else:
        avg_turnover = 0
        low_turnover = False
        print(f"\n换手率分析: 数据不可用")
    
    # 计算信号评分
    signal_score = 0
    if is_sideways:
        signal_score += 40
    if low_amplitude:
        signal_score += 30
    if low_turnover:
        signal_score += 30
    
    print(f"\n" + "=" * 80)
    print("信号评分")
    print("=" * 80)
    print(f"\n总分: {signal_score}/100")
    print(f"  横盘整理: {'✓ +40' if is_sideways else '✗ +0'}")
    print(f"  低振幅: {'✓ +30' if low_amplitude else '✗ +0'}")
    print(f"  低换手: {'✓ +30' if low_turnover else '✗ +0'}")
    
    if signal_score >= 70:
        signal_type = "⭐⭐⭐ 强信号"
    elif signal_score >= 40:
        signal_type = "⭐⭐ 中等信号"
    else:
        signal_type = "⭐ 弱信号"
    
    print(f"\n信号类型: {signal_type}")
    
    # 3. 分析近期走势
    print("\n" + "=" * 80)
    print("[3] 近期走势分析")
    print("=" * 80)
    
    recent_20 = df.tail(20)
    recent_60 = df.tail(60)
    
    # 计算涨跌幅
    price_20d_ago = recent_20.iloc[0]['收盘']
    price_60d_ago = recent_60.iloc[0]['收盘']
    price_now = recent_20.iloc[-1]['收盘']
    change_20d = (price_now - price_20d_ago) / price_20d_ago * 100
    change_60d = (price_now - price_60d_ago) / price_60d_ago * 100
    
    print(f"\n近期表现:")
    print(f"  20日前价格: {price_20d_ago:.2f}")
    print(f"  60日前价格: {price_60d_ago:.2f}")
    print(f"  当前价格: {price_now:.2f}")
    print(f"  20日涨跌: {change_20d:+.2f}%")
    print(f"  60日涨跌: {change_60d:+.2f}%")
    
    # 计算最大回撤
    max_price_20 = recent_20['最高'].max()
    min_price_20 = recent_20['最低'].min()
    max_drawdown_20 = (min_price_20 - max_price_20) / max_price_20 * 100
    
    print(f"\n20日波动:")
    print(f"  最高价: {max_price_20:.2f}")
    print(f"  最低价: {min_price_20:.2f}")
    print(f"  最大回撤: {max_drawdown_20:.2f}%")
    
    # 4. 成交量分析
    print("\n" + "=" * 80)
    print("[4] 成交量分析")
    print("=" * 80)
    
    vol_recent_5 = recent_20['成交量'].tail(5).mean()
    vol_prev_15 = recent_20['成交量'].head(15).mean()
    vol_ratio = vol_recent_5 / vol_prev_15 if vol_prev_15 > 0 else 0
    
    print(f"\n成交量对比:")
    print(f"  近5日均量: {vol_recent_5:.0f}")
    print(f"  前15日均量: {vol_prev_15:.0f}")
    print(f"  量比: {vol_ratio:.2f}")
    
    if vol_ratio > 1.5:
        vol_status = "✓ 近期放量"
    elif vol_ratio > 0.7:
        vol_status = "○ 量能正常"
    else:
        vol_status = "✗ 近期缩量"
    print(f"  评价: {vol_status}")
    
    # 5. 行业背景
    print("\n" + "=" * 80)
    print("[5] 行业背景")
    print("=" * 80)
    
    print(f"\n{name} - 半导体封测行业")
    print(f"  行业地位: 国内封测龙头之一")
    print(f"  业务特点: 受益于国产替代和半导体周期")
    print(f"  扭亏逻辑: 半导体行业复苏，订单回暖")
    
    # 6. 综合评估
    print("\n" + "=" * 80)
    print("[6] 综合评估")
    print("=" * 80)
    
    print(f"\n{code} {name} 当前状态:")
    print(f"  信号评分: {signal_score}/100 ({signal_type})")
    print(f"  波动率: {volatility*100:.2f}%")
    print(f"  振幅: {avg_amplitude:.2f}%")
    print(f"  换手率: {avg_turnover:.2f}%")
    print(f"  20日涨跌: {change_20d:+.2f}%")
    print(f"  60日涨跌: {change_60d:+.2f}%")
    print(f"  量比: {vol_ratio:.2f}")
    
    print(f"\n策略建议:")
    if signal_score >= 70:
        print("  ⭐⭐⭐ 强烈推荐")
        print("  - 符合年报扭亏策略的强信号特征")
        print("  - 半导体行业景气度回升")
        print("  - 建议年报前1-2天关注")
        print("  - 如确认扭亏，可考虑介入")
    elif signal_score >= 40:
        print("  ⭐⭐ 值得关注")
        print("  - 部分信号满足")
        print("  - 行业基本面改善")
        print("  - 可以观察，等待更明确信号")
    else:
        print("  ⭐ 观察为主")
        print("  - 信号不足")
        print("  - 等待更好的介入时机")
    
    print(f"\n操作要点:")
    print(f"  1. 确认2024年报是否扭亏")
    print(f"  2. 关注年报披露日期（预计2025年3-4月）")
    print(f"  3. 观察年报前是否有大单上打")
    print(f"  4. 止损位: 跌破横盘区间或-5%")
    print(f"  5. 目标收益: 5-10%（根据信号强度）")
    
    print(f"\n风险提示:")
    print(f"  1. 半导体行业波动较大")
    print(f"  2. 需要确认实际扭亏情况")
    print(f"  3. 注意大盘环境影响")
    print(f"  4. 控制仓位，分批建仓")
    
    # 7. 与久其软件对比
    print("\n" + "=" * 80)
    print("[7] 与久其软件对比")
    print("=" * 80)
    
    print(f"\n相似点:")
    print(f"  ✓ 都是季报扭亏")
    print(f"  ✓ 都有横盘整理特征")
    print(f"  ✓ 都有主力控盘迹象")
    print(f"  ✓ 都符合年报扭亏策略")
    
    print(f"\n差异点:")
    print(f"  - 行业不同: 半导体 vs 软件")
    print(f"  - 市值不同: 通富微电更大")
    print(f"  - 波动性: 半导体波动更大")
    
    # 保存结果
    result = {
        '股票代码': code,
        '股票名称': name,
        '行业': '半导体封测',
        '分析日期': datetime.now().strftime('%Y-%m-%d'),
        '最新价': price_now,
        '信号评分': signal_score,
        '信号类型': signal_type,
        '波动率%': round(volatility*100, 2),
        '振幅%': round(avg_amplitude, 2),
        '换手率%': round(avg_turnover, 2),
        '20日涨跌%': round(change_20d, 2),
        '60日涨跌%': round(change_60d, 2),
        '量比': round(vol_ratio, 2),
        '横盘': '✓' if is_sideways else '✗',
        '低振幅': '✓' if low_amplitude else '✗',
        '低换手': '✓' if low_turnover else '✗',
        '量能状态': vol_status,
    }
    
    df_result = pd.DataFrame([result])
    filename = f'{name}_{code}_回测_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
    df_result.to_excel(filename, index=False, engine='openpyxl')
    
    print(f"\n" + "=" * 80)
    print(f"回测结果已保存到: {filename}")
    print("=" * 80)
    
    return df_result


if __name__ == '__main__':
    backtest_tongfu()
