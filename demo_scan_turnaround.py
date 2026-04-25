"""
年报扭亏策略扫描演示
使用模拟数据展示扫描流程和结果
"""
import pandas as pd
from datetime import datetime

def demo_scan():
    """演示扫描流程"""
    print("=" * 80)
    print("年报扭亏策略扫描 - 演示版")
    print("=" * 80)
    print("\n注意: 这是演示版本，使用模拟数据展示扫描流程")
    print("实际使用时会连接真实数据源\n")
    
    # 模拟扫描结果
    demo_results = [
        {
            '股票代码': '600000',
            '股票名称': '浦发银行',
            '年报日期': '2026-03-28',
            '距离天数': 65,
            '最新价': 8.50,
            '季报扭亏': '✓',
            '扭亏季度': '2025Q3',
            '最新季度利润(万)': 8500,
            '横盘整理': '✓',
            '波动率': '3.2%',
            '大单上打': '✓',
            '大单占比': '28.5%',
            '主力控盘': '✓',
            '换手率': '2.1%',
            '振幅': '4.3%',
            '综合评分': 100
        },
        {
            '股票代码': '000001',
            '股票名称': '平安银行',
            '年报日期': '2026-03-25',
            '距离天数': 62,
            '最新价': 12.30,
            '季报扭亏': '✓',
            '扭亏季度': '2025Q3',
            '最新季度利润(万)': 12000,
            '横盘整理': '✓',
            '波动率': '4.5%',
            '大单上打': '✗',
            '大单占比': '15.2%',
            '主力控盘': '✓',
            '换手率': '2.8%',
            '振幅': '4.8%',
            '综合评分': 70
        },
        {
            '股票代码': '600519',
            '股票名称': '贵州茅台',
            '年报日期': '2026-04-01',
            '距离天数': 69,
            '最新价': 1650.00,
            '季报扭亏': '✓',
            '扭亏季度': '2025Q3',
            '最新季度利润(万)': 5000,
            '横盘整理': '✓',
            '波动率': '4.8%',
            '大单上打': '✗',
            '大单占比': '18.0%',
            '主力控盘': '○',
            '换手率': '3.5%',
            '振幅': '5.2%',
            '综合评分': 55
        },
        {
            '股票代码': '000002',
            '股票名称': '万科A',
            '年报日期': '2026-03-30',
            '距离天数': 67,
            '最新价': 8.80,
            '季报扭亏': '✓',
            '扭亏季度': '2025Q3',
            '最新季度利润(万)': 3000,
            '横盘整理': '✗',
            '波动率': '8.5%',
            '大单上打': '✗',
            '大单占比': '12.0%',
            '主力控盘': '✗',
            '换手率': '5.2%',
            '振幅': '7.8%',
            '综合评分': 30
        }
    ]
    
    df = pd.DataFrame(demo_results)
    
    print("\n" + "=" * 80)
    print("扫描结果")
    print("=" * 80)
    print(f"\n找到 {len(df)} 只即将发布年报的扭亏股票\n")
    
    # 按评分排序
    df = df.sort_values('综合评分', ascending=False)
    
    # 显示结果
    print(df.to_string(index=False))
    
    # 分类统计
    print("\n" + "=" * 80)
    print("评级分布")
    print("=" * 80)
    
    strong = df[df['综合评分'] >= 80]
    medium = df[(df['综合评分'] >= 60) & (df['综合评分'] < 80)]
    weak = df[(df['综合评分'] >= 40) & (df['综合评分'] < 60)]
    poor = df[df['综合评分'] < 40]
    
    print(f"\n⭐⭐⭐ 强烈推荐 (≥80分): {len(strong)} 只")
    if len(strong) > 0:
        for _, row in strong.iterrows():
            print(f"  - {row['股票代码']} {row['股票名称']} ({row['综合评分']}分)")
    
    print(f"\n⭐⭐ 值得关注 (60-79分): {len(medium)} 只")
    if len(medium) > 0:
        for _, row in medium.iterrows():
            print(f"  - {row['股票代码']} {row['股票名称']} ({row['综合评分']}分)")
    
    print(f"\n⭐ 观察 (40-59分): {len(weak)} 只")
    if len(weak) > 0:
        for _, row in weak.iterrows():
            print(f"  - {row['股票代码']} {row['股票名称']} ({row['综合评分']}分)")
    
    print(f"\n✗ 不符合 (<40分): {len(poor)} 只")
    if len(poor) > 0:
        for _, row in poor.iterrows():
            print(f"  - {row['股票代码']} {row['股票名称']} ({row['综合评分']}分)")
    
    # 详细分析
    print("\n" + "=" * 80)
    print("重点推荐分析")
    print("=" * 80)
    
    if len(strong) > 0:
        print("\n强烈推荐股票详情:\n")
        for _, row in strong.iterrows():
            print(f"【{row['股票代码']} {row['股票名称']}】")
            print(f"  年报日期: {row['年报日期']} (还有{row['距离天数']}天)")
            print(f"  最新价格: {row['最新价']}")
            print(f"  季报扭亏: {row['扭亏季度']} 盈利{row['最新季度利润(万)']}万")
            print(f"  横盘整理: {row['横盘整理']} (波动率{row['波动率']})")
            print(f"  大单上打: {row['大单上打']} (大单占比{row['大单占比']})")
            print(f"  主力控盘: {row['主力控盘']} (换手率{row['换手率']}, 振幅{row['振幅']})")
            print(f"  综合评分: {row['综合评分']}/100")
            print(f"\n  操作建议:")
            print(f"    - 年报前2-3天开始关注")
            print(f"    - 分批建仓，单只仓位10-15%")
            print(f"    - 止损位: 跌破横盘区间")
            print(f"    - 目标收益: 5-10%")
            print()
    else:
        print("\n当前暂无强烈推荐的股票")
        print("建议:")
        print("  1. 继续观察中等评分的股票")
        print("  2. 等待更多年报披露临近")
        print("  3. 关注新的扭亏公告")
    
    # 保存结果
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'年报扭亏扫描_演示_{timestamp}.xlsx'
    df.to_excel(filename, index=False, engine='openpyxl')
    print("\n" + "=" * 80)
    print(f"结果已保存到: {filename}")
    print("=" * 80)
    
    print("\n提示:")
    print("  这是演示版本，实际使用时:")
    print("  1. 会自动获取真实的年报披露时间表")
    print("  2. 会实时检查季报扭亏情况")
    print("  3. 会分析最新的K线和盘口数据")
    print("  4. 评分和推荐会基于真实数据")
    
    return df


if __name__ == '__main__':
    print("\n年报扭亏策略扫描演示")
    print("=" * 80)
    print("这是一个演示版本，展示扫描流程和结果格式")
    print("实际使用时会连接真实数据源")
    print("=" * 80)
    
    choice = input("\n是否继续演示? (y/n): ").strip().lower()
    
    if choice == 'y':
        df = demo_scan()
        
        print("\n\n演示完成！")
        print("\n实际使用:")
        print("  python scan_annual_report_turnaround.py")
        print("\n或修改脚本中的 manual_list 添加真实股票")
    else:
        print("已取消")
