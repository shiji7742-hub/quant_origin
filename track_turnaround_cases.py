"""
扭亏案例跟踪工具
记录和管理扭亏股票案例
"""
import pandas as pd
from datetime import datetime
import os

CASES_FILE = '扭亏案例跟踪.xlsx'

def load_cases():
    """加载已有案例"""
    if os.path.exists(CASES_FILE):
        try:
            df = pd.read_excel(CASES_FILE, engine='openpyxl')
            return df
        except:
            return create_empty_df()
    else:
        return create_empty_df()


def create_empty_df():
    """创建空的案例表"""
    return pd.DataFrame(columns=[
        '股票代码', '股票名称', '行业', 
        '2023利润(万)', '2024利润(万)', '扭亏幅度%',
        '年报披露日期', '数据来源',
        '年报前信号评分', '波动率%', '振幅%', '换手率%',
        '1日收益%', '3日收益%', '5日收益%', '10日收益%',
        '验证状态', '添加日期', '备注'
    ])


def add_case():
    """添加新案例"""
    print("=" * 60)
    print("添加扭亏案例")
    print("=" * 60)
    
    code = input("\n股票代码 (6位): ").strip()
    if len(code) != 6:
        print("✗ 代码格式错误")
        return
    
    name = input("股票名称: ").strip()
    industry = input("所属行业: ").strip()
    
    print("\n财务数据:")
    profit_2023 = input("2023年利润(万元，亏损输入负数): ").strip()
    profit_2024 = input("2024年利润(万元): ").strip()
    
    try:
        p2023 = float(profit_2023)
        p2024 = float(profit_2024)
        
        if p2023 >= 0:
            print("✗ 2023年必须是亏损")
            return
        
        if p2024 <= 0:
            print("✗ 2024年必须是盈利")
            return
        
        turnaround_ratio = (p2024 - p2023) / abs(p2023) * 100
    except:
        print("✗ 利润数据格式错误")
        return
    
    report_date = input("\n年报披露日期 (YYYY-MM-DD): ").strip()
    try:
        datetime.strptime(report_date, '%Y-%m-%d')
    except:
        print("✗ 日期格式错误")
        return
    
    source = input("数据来源 (如：东方财富网、公司公告): ").strip()
    
    print("\n年报前信号（如果还未披露，可留空）:")
    signal_score = input("信号评分 (0-100): ").strip()
    volatility = input("波动率% (如：4.97): ").strip()
    amplitude = input("振幅% (如：1.37): ").strip()
    turnover = input("换手率% (如：0.91): ").strip()
    
    print("\n年报后收益（如果还未披露，可留空）:")
    ret_1d = input("1日收益% (如：3.5): ").strip()
    ret_3d = input("3日收益% (如：5.2): ").strip()
    ret_5d = input("5日收益% (如：6.8): ").strip()
    ret_10d = input("10日收益% (如：8.3): ").strip()
    
    status = input("\n验证状态 (待验证/已验证/跟踪中): ").strip() or "待验证"
    notes = input("备注: ").strip()
    
    # 创建新记录
    new_case = {
        '股票代码': code,
        '股票名称': name,
        '行业': industry,
        '2023利润(万)': p2023,
        '2024利润(万)': p2024,
        '扭亏幅度%': round(turnaround_ratio, 2),
        '年报披露日期': report_date,
        '数据来源': source,
        '年报前信号评分': int(signal_score) if signal_score else None,
        '波动率%': float(volatility) if volatility else None,
        '振幅%': float(amplitude) if amplitude else None,
        '换手率%': float(turnover) if turnover else None,
        '1日收益%': float(ret_1d) if ret_1d else None,
        '3日收益%': float(ret_3d) if ret_3d else None,
        '5日收益%': float(ret_5d) if ret_5d else None,
        '10日收益%': float(ret_10d) if ret_10d else None,
        '验证状态': status,
        '添加日期': datetime.now().strftime('%Y-%m-%d'),
        '备注': notes
    }
    
    # 加载现有案例
    df = load_cases()
    
    # 检查是否已存在
    if code in df['股票代码'].values:
        print(f"\n✗ {code} {name} 已存在")
        update = input("是否更新? (y/n): ").strip().lower()
        if update == 'y':
            df = df[df['股票代码'] != code]
        else:
            return
    
    # 添加新案例
    df = pd.concat([df, pd.DataFrame([new_case])], ignore_index=True)
    
    # 保存
    df.to_excel(CASES_FILE, index=False, engine='openpyxl')
    
    print(f"\n✓ 已添加案例: {code} {name}")
    print(f"扭亏幅度: {turnaround_ratio:.2f}%")
    print(f"保存到: {CASES_FILE}")


def view_cases():
    """查看所有案例"""
    df = load_cases()
    
    if len(df) == 0:
        print("\n暂无案例记录")
        return
    
    print("=" * 80)
    print(f"扭亏案例列表 (共{len(df)}个)")
    print("=" * 80)
    
    # 按验证状态分组
    for status in ['已验证', '跟踪中', '待验证']:
        df_status = df[df['验证状态'] == status]
        if len(df_status) > 0:
            print(f"\n【{status}】{len(df_status)}个")
            for _, row in df_status.iterrows():
                print(f"\n{row['股票代码']} {row['股票名称']} ({row['行业']})")
                print(f"  扭亏: {row['2023利润(万)']}万 → {row['2024利润(万)']}万 ({row['扭亏幅度%']}%)")
                print(f"  披露日期: {row['年报披露日期']}")
                
                if pd.notna(row['年报前信号评分']):
                    print(f"  信号评分: {row['年报前信号评分']}分")
                
                if pd.notna(row['5日收益%']):
                    print(f"  5日收益: {row['5日收益%']}%")
                
                if row['备注']:
                    print(f"  备注: {row['备注']}")


def statistics():
    """统计分析"""
    df = load_cases()
    
    if len(df) == 0:
        print("\n暂无案例记录")
        return
    
    print("=" * 80)
    print("案例统计分析")
    print("=" * 80)
    
    print(f"\n总案例数: {len(df)}")
    print(f"已验证: {len(df[df['验证状态']=='已验证'])}")
    print(f"跟踪中: {len(df[df['验证状态']=='跟踪中'])}")
    print(f"待验证: {len(df[df['验证状态']=='待验证'])}")
    
    # 行业分布
    print("\n行业分布:")
    industry_counts = df['行业'].value_counts()
    for industry, count in industry_counts.items():
        print(f"  {industry}: {count}个")
    
    # 扭亏幅度统计
    print(f"\n扭亏幅度:")
    print(f"  平均: {df['扭亏幅度%'].mean():.2f}%")
    print(f"  最大: {df['扭亏幅度%'].max():.2f}%")
    print(f"  最小: {df['扭亏幅度%'].min():.2f}%")
    
    # 信号统计（已有信号的）
    df_with_signal = df[df['年报前信号评分'].notna()]
    if len(df_with_signal) > 0:
        print(f"\n信号统计 (样本{len(df_with_signal)}个):")
        print(f"  平均评分: {df_with_signal['年报前信号评分'].mean():.2f}")
        print(f"  强信号(≥70): {len(df_with_signal[df_with_signal['年报前信号评分']>=70])}个")
        print(f"  中等信号(40-69): {len(df_with_signal[(df_with_signal['年报前信号评分']>=40)&(df_with_signal['年报前信号评分']<70)])}个")
        print(f"  弱信号(<40): {len(df_with_signal[df_with_signal['年报前信号评分']<40])}个")
    
    # 收益统计（已有收益的）
    df_with_return = df[df['5日收益%'].notna()]
    if len(df_with_return) > 0:
        print(f"\n收益统计 (样本{len(df_with_return)}个):")
        for days in [1, 3, 5, 10]:
            col = f'{days}日收益%'
            if col in df_with_return.columns:
                valid = df_with_return[df_with_return[col].notna()]
                if len(valid) > 0:
                    avg = valid[col].mean()
                    win_rate = (valid[col] > 0).sum() / len(valid) * 100
                    print(f"  {days}日: 平均{avg:.2f}%, 胜率{win_rate:.1f}%")


def export_for_backtest():
    """导出用于回测"""
    df = load_cases()
    
    if len(df) == 0:
        print("\n暂无案例记录")
        return
    
    # 筛选已验证的案例
    df_verified = df[df['验证状态'] == '已验证']
    
    if len(df_verified) == 0:
        print("\n暂无已验证的案例")
        return
    
    print(f"\n找到 {len(df_verified)} 个已验证案例")
    
    # 生成回测脚本
    print("\n可用于 interactive_backtest.py 的数据:")
    print("\ntest_stocks = [")
    for _, row in df_verified.iterrows():
        print(f"    ('{row['股票代码']}', '{row['股票名称']}', '{row['年报披露日期']}'),")
    print("]")
    
    # 保存到文件
    filename = '已验证案例_回测数据.txt'
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("# 已验证的扭亏案例\n")
        f.write("# 可直接复制到 interactive_backtest.py 使用\n\n")
        f.write("test_stocks = [\n")
        for _, row in df_verified.iterrows():
            f.write(f"    ('{row['股票代码']}', '{row['股票名称']}', '{row['年报披露日期']}'),\n")
        f.write("]\n")
    
    print(f"\n已保存到: {filename}")


def main():
    """主菜单"""
    while True:
        print("\n" + "=" * 60)
        print("扭亏案例跟踪工具")
        print("=" * 60)
        print("1. 添加新案例")
        print("2. 查看所有案例")
        print("3. 统计分析")
        print("4. 导出回测数据")
        print("5. 退出")
        print("=" * 60)
        
        choice = input("\n请选择 (1-5): ").strip()
        
        if choice == '1':
            add_case()
        elif choice == '2':
            view_cases()
        elif choice == '3':
            statistics()
        elif choice == '4':
            export_for_backtest()
        elif choice == '5':
            print("\n再见！")
            break
        else:
            print("无效选择")


if __name__ == '__main__':
    print("\n扭亏案例跟踪工具")
    print("=" * 60)
    print("用于记录和管理年报扭亏股票案例")
    print("=" * 60)
    
    main()
