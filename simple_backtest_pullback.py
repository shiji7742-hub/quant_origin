#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版回测 - 只回测最近5天
网络不稳定时，最近的数据更容易获取
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
from functools import wraps


def retry_on_error(max_retries=3, delay=2):
    """重试装饰器"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt < max_retries - 1:
                        wait_time = delay * (2 ** attempt)
                        time.sleep(wait_time)
                    else:
                        return None
            return None
        return wrapper
    return decorator


def should_filter_stock(name: str, price: float = None) -> tuple:
    """过滤不适合的股票"""
    
    # ST股票
    if 'ST' in name or 'st' in name or '*' in name:
        return True, "ST股票"
    
    # 权重板块
    weight_sectors = ['银行', '保险', '券商', '证券', '信托']
    for keyword in weight_sectors:
        if keyword in name:
            return True, f"权重-{keyword}"
    
    # 白酒
    if any(x in name for x in ['茅台', '五粮液', '泸州', '洋河', '汾酒', '古井']):
        return True, "白酒"
    
    # 热门题材
    hot_themes = ['航天', '卫星', '火箭', '空间', '低空']
    for keyword in hot_themes:
        if keyword in name:
            return True, f"热门-{keyword}"
    
    # 价格过滤
    if price:
        if price < 3:
            return True, "低价股"
        if price > 100:
            return True, "超高价"
    
    return False, None


@retry_on_error(max_retries=3, delay=2)
def get_stock_data(symbol: str):
    """获取股票数据（带重试）"""
    return ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")


def analyze_day_signal(symbol: str, name: str, date: str) -> dict:
    """分析某一天的信号"""
    
    try:
        # 获取日K数据
        df = get_stock_data(symbol)
        
        if df is None:
            return None
        
        df['日期'] = pd.to_datetime(df['日期'])
        
        target_date = pd.to_datetime(date)
        day_data = df[df['日期'] == target_date]
        
        if len(day_data) == 0:
            return None
        
        day_data = day_data.iloc[0]
        
        # 过滤
        should_filter, reason = should_filter_stock(name, day_data['收盘'])
        if should_filter:
            return None
        
        # 基本过滤
        if abs(day_data['涨跌幅']) > 9.5:
            return None
        if day_data['振幅'] < 1.5 or day_data['振幅'] > 20:
            return None
        if day_data['成交量'] < 50:
            return None
        
        # 核心信号：尾盘回落
        pullback = (day_data['最高'] - day_data['收盘']) / day_data['最高'] * 100
        
        if pullback < 0.5:
            return None
        
        # 支撑位判断
        support_price = day_data['最低'] * 1.01
        hold_support = day_data['收盘'] >= support_price
        
        if not hold_support:
            return None
        
        # 评分
        score = 0
        if pullback >= 1:
            score += 30
        if pullback >= 2:
            score += 10
        if pullback >= 4:
            score += 10
        if hold_support:
            score += 30
        if 2 <= day_data['振幅'] <= 10:
            score += 20
        if -3 <= day_data['涨跌幅'] <= 5:
            score += 10
        
        if score < 70:
            return None
        
        # 获取后续收益
        after_data = df[df['日期'] > target_date].head(5)
        
        returns = []
        for i in range(min(5, len(after_data))):
            ret = (after_data.iloc[i]['收盘'] - day_data['收盘']) / day_data['收盘'] * 100
            returns.append(ret)
        
        while len(returns) < 5:
            returns.append(None)
        
        return {
            'symbol': symbol,
            'name': name,
            'date': date,
            'score': score,
            'close': day_data['收盘'],
            'change': day_data['涨跌幅'],
            'amplitude': day_data['振幅'],
            'pullback': pullback,
            't1': returns[0],
            't2': returns[1],
            't3': returns[2],
            't4': returns[3],
            't5': returns[4]
        }
        
    except Exception as e:
        return None


def get_recent_trading_days(days=5):
    """获取最近N个交易日"""
    
    try:
        df = ak.stock_zh_index_daily(symbol="sh000001")
        df['date'] = pd.to_datetime(df['date'])
        
        # 获取最近的交易日
        recent_days = df.tail(days + 5)['date'].dt.strftime('%Y-%m-%d').tolist()
        return recent_days[-days:]
        
    except:
        # 备用：手动计算
        today = datetime.now()
        dates = []
        for i in range(days * 2):  # 多取一些，排除周末
            d = today - timedelta(days=i)
            if d.weekday() < 5:  # 周一到周五
                dates.append(d.strftime('%Y-%m-%d'))
            if len(dates) >= days:
                break
        return dates[:days]


def get_active_stocks():
    """获取活跃股票池（精选50只）"""
    
    # 手动精选活跃的中小市值股票
    stock_list = [
        # 科技股
        ('002279', '久其软件'), ('002230', '科大讯飞'), ('000063', '中兴通讯'),
        ('002415', '海康威视'), ('002371', '北方华创'), ('002475', '立讯精密'),
        ('300124', '汇川技术'), ('300750', '宁德时代'), ('002460', '赣锋锂业'),
        
        # 医药股
        ('600276', '恒瑞医药'), ('603259', '药明康德'), ('300015', '爱尔眼科'),
        ('000661', '长春高新'), ('300347', '泰格医药'),
        
        # 消费股
        ('000333', '美的集团'), ('000651', '格力电器'), ('002594', '比亚迪'),
        ('600887', '伊利股份'), ('000858', '五粮液'),
        
        # 地产股
        ('000002', '万科A'), ('001979', '招商蛇口'), ('600048', '保利发展'),
        
        # 新能源
        ('300274', '阳光电源'), ('002129', '中环股份'), ('601012', '隆基绿能'),
        
        # 半导体
        ('688981', '中芯国际'), ('603501', '韦尔股份'), ('002049', '紫光国微'),
        ('688008', '澜起科技'), ('688012', '中微公司'),
        
        # 军工
        ('002179', '中航光电'), ('600893', '航发动力'), ('002013', '中航机电'),
        
        # 通信
        ('600050', '中国联通'), ('000938', '紫光股份'), ('002281', '光迅科技'),
        
        # 汽车
        ('601633', '长城汽车'), ('000625', '长安汽车'), ('600104', '上汽集团'),
        
        # 化工
        ('600309', '万华化学'), ('002648', '卫星化学'), ('600426', '华鲁恒升'),
        
        # 机械
        ('002008', '大族激光'), ('300450', '先导智能'), ('688169', '石头科技'),
        
        # 其他
        ('002352', '顺丰控股'), ('002027', '分众传媒'), ('300059', '东方财富'),
    ]
    
    return stock_list


def run_simple_backtest():
    """运行简化版回测"""
    
    print("=" * 70)
    print("简化版回测 - 盘中托价+尾盘回落策略")
    print("=" * 70)
    
    # 获取最近5个交易日
    print("\n获取最近交易日...")
    dates = get_recent_trading_days(days=5)
    print(f"回测日期: {dates}")
    
    # 获取股票池
    print(f"\n获取股票池...")
    stock_pool = get_active_stocks()
    print(f"股票池: {len(stock_pool)} 只")
    
    # 回测
    all_signals = []
    total_checked = 0
    total_success = 0
    total_failed = 0
    
    print(f"\n开始回测...")
    print(f"预计检查: {len(dates)} 天 × {len(stock_pool)} 只 = {len(dates) * len(stock_pool)} 次")
    
    for date_idx, date in enumerate(dates):
        print(f"\n{'='*70}")
        print(f"[{date_idx+1}/{len(dates)}] {date}")
        print(f"{'='*70}")
        
        day_signals = []
        day_success = 0
        day_failed = 0
        
        for idx, (symbol, name) in enumerate(stock_pool):
            total_checked += 1
            
            # 显示进度
            if (idx + 1) % 10 == 0:
                print(f"  进度: {idx+1}/{len(stock_pool)} (成功:{day_success}, 失败:{day_failed})")
            
            result = analyze_day_signal(symbol, name, date)
            
            if result is None:
                day_failed += 1
                total_failed += 1
            else:
                day_success += 1
                total_success += 1
                day_signals.append(result)
                t1_str = f"T+1:{result['t1']:+.2f}%" if result['t1'] else ""
                print(f"  [信号] {name}({symbol}) 评分:{result['score']} 回落:{result['pullback']:.2f}% {t1_str}")
            
            time.sleep(1.5)  # 延迟
        
        all_signals.extend(day_signals)
        print(f"\n当日统计: 检查{len(stock_pool)}只, 成功{day_success}只, 失败{day_failed}只, 发现{len(day_signals)}个信号")
        
        time.sleep(3)
    
    # 生成报告
    print(f"\n{'='*70}")
    print("回测完成！")
    print(f"{'='*70}")
    print(f"总检查: {total_checked}")
    print(f"成功获取: {total_success} ({total_success/total_checked*100:.1f}%)")
    print(f"获取失败: {total_failed} ({total_failed/total_checked*100:.1f}%)")
    print(f"发现信号: {len(all_signals)}")
    
    if len(all_signals) == 0:
        print("\n未发现符合条件的信号")
        return
    
    # 转换为DataFrame
    df = pd.DataFrame(all_signals)
    
    # 保存Excel
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'简化回测结果_{timestamp}.xlsx'
    df.to_excel(filename, index=False, engine='openpyxl')
    print(f"\n详细结果已保存: {filename}")
    
    # 统计分析
    print(f"\n{'='*70}")
    print("策略表现统计")
    print(f"{'='*70}")
    
    # T+1统计
    t1_data = df[df['t1'].notna()]
    if len(t1_data) > 0:
        t1_wins = len(t1_data[t1_data['t1'] > 0])
        t1_win_rate = t1_wins / len(t1_data) * 100
        t1_avg = t1_data['t1'].mean()
        t1_median = t1_data['t1'].median()
        
        print(f"\nT+1表现:")
        print(f"  样本数: {len(t1_data)}")
        print(f"  盈利: {t1_wins} 次")
        print(f"  胜率: {t1_win_rate:.1f}%")
        print(f"  平均收益: {t1_avg:+.2f}%")
        print(f"  中位数收益: {t1_median:+.2f}%")
    
    # 按评分分组
    print(f"\n{'='*70}")
    print("按评分分组统计")
    print(f"{'='*70}")
    
    for min_score in [100, 90, 80, 70]:
        group = df[(df['score'] >= min_score) & (df['t1'].notna())]
        if len(group) > 0:
            win_rate = len(group[group['t1'] > 0]) / len(group) * 100
            avg_return = group['t1'].mean()
            print(f"\n评分≥{min_score}:")
            print(f"  样本数: {len(group)}")
            print(f"  胜率: {win_rate:.1f}%")
            print(f"  平均收益: {avg_return:+.2f}%")
    
    # 详细列表
    print(f"\n{'='*70}")
    print("所有信号详情")
    print(f"{'='*70}")
    print(df[['date', 'name', 'score', 'pullback', 't1', 't2', 't3']].to_string(index=False))


def main():
    run_simple_backtest()


if __name__ == '__main__':
    main()
