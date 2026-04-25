#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
历史回测 - 盘中托价+尾盘回落策略
采用抽样方式，选择关键交易日回测
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime
import time
import random
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
                        wait_time = delay * (2 ** attempt)  # 指数退避
                        time.sleep(wait_time)
                    else:
                        raise e
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
    
    # 热门题材（需要定期更新）
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


def analyze_day_signal(symbol: str, name: str, date: str, debug=False) -> dict:
    """分析某一天的信号"""
    
    try:
        # 获取日K数据（带重试）
        df = get_stock_data(symbol)
        
        if df is None:
            if debug:
                print(f"    {name}({symbol}): 网络错误")
            return {'error': 'network'}
        
        df['日期'] = pd.to_datetime(df['日期'])
        
        target_date = pd.to_datetime(date)
        day_data = df[df['日期'] == target_date]
        
        if len(day_data) == 0:
            if debug:
                print(f"    {name}({symbol}): 无{date}数据")
            return {'error': 'no_data'}
        
        day_data = day_data.iloc[0]
        
        # 过滤
        should_filter, reason = should_filter_stock(name, day_data['收盘'])
        if should_filter:
            if debug:
                print(f"    {name}({symbol}): 过滤-{reason}")
            return {'error': 'filtered'}
        
        # 基本过滤（放宽条件）
        if abs(day_data['涨跌幅']) > 9.5:  # 涨跌停
            if debug:
                print(f"    {name}({symbol}): 涨跌停{day_data['涨跌幅']:.2f}%")
            return {'error': 'limit'}
        if day_data['振幅'] < 1.5 or day_data['振幅'] > 20:  # 放宽振幅范围
            if debug:
                print(f"    {name}({symbol}): 振幅异常{day_data['振幅']:.2f}%")
            return {'error': 'amplitude'}
        if day_data['成交量'] < 50:  # 降低成交量要求
            if debug:
                print(f"    {name}({symbol}): 成交量太小")
            return {'error': 'volume'}
        
        # 核心信号：尾盘回落（降低门槛）
        pullback = (day_data['最高'] - day_data['收盘']) / day_data['最高'] * 100
        
        if pullback < 0.5:  # 降低到0.5%
            if debug:
                print(f"    {name}({symbol}): 回落不足{pullback:.2f}%")
            return {'error': 'no_pullback'}
        
        # 支撑位判断（简化版：用最低价+1%）
        support_price = day_data['最低'] * 1.01
        hold_support = day_data['收盘'] >= support_price
        
        if not hold_support:  # 没守住支撑
            if debug:
                print(f"    {name}({symbol}): 未守住支撑")
            return {'error': 'no_support'}
        
        # 评分（降低门槛）
        score = 0
        if pullback >= 1:
            score += 30
        if pullback >= 2:  # 降低到2%
            score += 10
        if pullback >= 4:  # 降低到4%
            score += 10
        if hold_support:
            score += 30
        if 2 <= day_data['振幅'] <= 10:  # 放宽振幅范围
            score += 20
        if -3 <= day_data['涨跌幅'] <= 5:  # 放宽涨跌幅范围
            score += 10
        
        if score < 70:  # 降低评分门槛到70
            if debug:
                print(f"    {name}({symbol}): 评分不足{score}")
            return {'error': 'low_score'}
        
        if debug:
            print(f"    {name}({symbol}): ✓ 发现信号! 评分{score} 回落{pullback:.2f}%")
        
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
        if debug:
            print(f"    {name}({symbol}): 错误-{e}")
        return {'error': 'exception'}


def get_sample_dates(start_date: str, end_date: str, sample_size: int = 20) -> list:
    """获取抽样日期"""
    
    try:
        # 获取交易日
        df = ak.stock_zh_index_daily(symbol="sh000001")
        df['date'] = pd.to_datetime(df['date'])
        
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
        
        trading_days = df[
            (df['date'] >= start) & 
            (df['date'] <= end)
        ]['date'].dt.strftime('%Y-%m-%d').tolist()
        
        # 随机抽样
        if len(trading_days) > sample_size:
            sampled = random.sample(trading_days, sample_size)
            sampled.sort()
            return sampled
        else:
            return trading_days
            
    except:
        # 备用：手动指定一些日期
        return [
            '2026-01-20', '2026-01-17', '2026-01-16', '2026-01-15',
            '2026-01-14', '2026-01-13', '2026-01-10', '2026-01-09',
            '2026-01-08', '2026-01-07', '2026-01-06', '2026-01-03',
            '2025-12-31', '2025-12-30', '2025-12-27', '2025-12-26',
            '2025-12-25', '2025-12-24', '2025-12-23', '2025-12-20',
        ]


def get_stock_pool() -> list:
    """获取股票池 - 主板非ST股票（无限重试直到成功）"""
    
    retry_count = 0
    
    while True:  # 无限重试
        try:
            print(f"获取股票池... (尝试 {retry_count + 1})")
            df = ak.stock_zh_a_spot_em()
            
            print(f"  ✓ 成功获取数据!")
            print(f"  原始股票数: {len(df)}")
            
            # 过滤ST股票
            df = df[~df['名称'].str.contains('ST|st|\\*', regex=True, na=False)]
            print(f"  过滤ST后: {len(df)}")
            
            # 筛选条件
            df = df[
                (df['成交额'] > 50000000) &  # 成交额>5000万
                (df['最新价'] >= 5) &  # 价格>=5元
                (df['最新价'] <= 50) &  # 价格<=50元
                (df['涨跌幅'].abs() < 9.5)  # 非涨跌停
            ]
            print(f"  基本筛选后: {len(df)}")
            
            # 按成交额排序，取全部（不限制数量）
            df = df.sort_values('成交额', ascending=False)
            
            stock_list = [(row['代码'], row['名称']) for _, row in df.iterrows()]
            print(f"  最终股票池: {len(stock_list)} 只")
            print(f"  示例: {stock_list[:5]}")
            
            return stock_list
            
        except Exception as e:
            retry_count += 1
            print(f"  ✗ 获取失败: {e}")
            
            wait_time = min(3 * (2 ** min(retry_count - 1, 3)), 30)  # 指数退避，最多等待30秒
            print(f"  等待 {wait_time} 秒后重试... (已尝试{retry_count}次)")
            time.sleep(wait_time)


def run_backtest():
    """运行回测"""
    
    print("=" * 70)
    print("历史回测 - 盘中托价+尾盘回落策略")
    print("=" * 70)
    
    # 获取抽样日期
    print("\n获取回测日期...")
    dates = get_sample_dates('2025-11-01', '2026-01-24', sample_size=20)
    print(f"抽样 {len(dates)} 个交易日")
    print(f"日期范围: {dates[0]} 至 {dates[-1]}")
    
    # 获取股票池
    stock_pool = get_stock_pool()
    
    # 回测
    all_signals = []
    total_checked = 0
    debug_stats = {
        'total': 0,
        'no_data': 0,
        'filtered': 0,
        'no_pullback': 0,
        'no_support': 0,
        'low_score': 0,
        'success': 0
    }
    
    print(f"\n开始回测...")
    print(f"预计检查: {len(dates)} 天 × {len(stock_pool)} 只 = {len(dates) * len(stock_pool)} 次")
    
    for date_idx, date in enumerate(dates):
        print(f"\n{'='*70}")
        print(f"[{date_idx+1}/{len(dates)}] {date}")
        print(f"{'='*70}")
        
        day_signals = []
        day_stats = {'checked': 0, 'network_error': 0, 'found': 0}
        
        # 前3只股票开启调试模式
        for idx, (symbol, name) in enumerate(stock_pool):
            total_checked += 1
            debug_stats['total'] += 1
            day_stats['checked'] += 1
            
            debug_mode = (idx < 3)  # 前3只开启调试
            
            result = analyze_day_signal(symbol, name, date, debug=debug_mode)
            
            # 每只股票之间增加延迟
            time.sleep(1.5)  # 增加到1.5秒
            
            # 判断结果类型
            if result is None:
                debug_stats['no_data'] += 1
            elif isinstance(result, dict) and 'error' in result:
                # 有错误，但继续处理
                if result['error'] == 'network':
                    day_stats['network_error'] += 1
                    debug_stats['no_data'] += 1
            else:
                # 找到信号
                day_signals.append(result)
                debug_stats['success'] += 1
                day_stats['found'] += 1
                t1_str = f"T+1:{result['t1']:+.2f}%" if result['t1'] else ""
                print(f"  [信号] {name}({symbol}) 评分:{result['score']} 回落:{result['pullback']:.2f}% {t1_str}")
        
        all_signals.extend(day_signals)
        print(f"\n当日统计: 检查{day_stats['checked']}只, 网络错误{day_stats['network_error']}只, 发现{day_stats['found']}个信号")
        
        # 每5天显示一次调试信息
        if (date_idx + 1) % 5 == 0:
            print(f"\n{'='*70}")
            print(f"累计统计 (已完成{date_idx+1}/{len(dates)}天)")
            print(f"{'='*70}")
            print(f"  总检查: {debug_stats['total']}")
            print(f"  网络错误: {debug_stats['no_data']}")
            print(f"  发现信号: {debug_stats['success']}")
            if debug_stats['total'] > 0:
                print(f"  信号率: {debug_stats['success']/debug_stats['total']*100:.3f}%")
                print(f"  成功率: {(debug_stats['total']-debug_stats['no_data'])/debug_stats['total']*100:.1f}%")
        
        # 每天之间增加延迟
        time.sleep(3)  # 增加到3秒
    
    # 生成报告
    print(f"\n{'='*70}")
    print("回测完成！")
    print(f"{'='*70}")
    print(f"检查次数: {total_checked}")
    print(f"发现信号: {len(all_signals)}")
    print(f"信号率: {len(all_signals)/total_checked*100:.2f}%")
    
    if len(all_signals) == 0:
        print("\n未发现符合条件的信号")
        return
    
    # 转换为DataFrame
    df = pd.DataFrame(all_signals)
    
    # 保存Excel
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'历史回测结果_{timestamp}.xlsx'
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
        t1_losses = len(t1_data[t1_data['t1'] <= 0])
        t1_win_rate = t1_wins / len(t1_data) * 100
        t1_avg = t1_data['t1'].mean()
        t1_median = t1_data['t1'].median()
        t1_max = t1_data['t1'].max()
        t1_min = t1_data['t1'].min()
        
        print(f"\nT+1表现:")
        print(f"  样本数: {len(t1_data)}")
        print(f"  盈利: {t1_wins} 次")
        print(f"  亏损: {t1_losses} 次")
        print(f"  胜率: {t1_win_rate:.1f}%")
        print(f"  平均收益: {t1_avg:+.2f}%")
        print(f"  中位数收益: {t1_median:+.2f}%")
        print(f"  最大收益: {t1_max:+.2f}%")
        print(f"  最大亏损: {t1_min:+.2f}%")
        
        # 盈亏比
        wins = t1_data[t1_data['t1'] > 0]['t1']
        losses = t1_data[t1_data['t1'] <= 0]['t1']
        if len(wins) > 0 and len(losses) > 0:
            avg_win = wins.mean()
            avg_loss = abs(losses.mean())
            profit_loss_ratio = avg_win / avg_loss if avg_loss > 0 else 0
            print(f"  平均盈利: {avg_win:+.2f}%")
            print(f"  平均亏损: {-avg_loss:+.2f}%")
            print(f"  盈亏比: {profit_loss_ratio:.2f}")
    
    # T+3统计
    t3_data = df[df['t3'].notna()]
    if len(t3_data) > 0:
        t3_win_rate = len(t3_data[t3_data['t3'] > 0]) / len(t3_data) * 100
        t3_avg = t3_data['t3'].mean()
        
        print(f"\nT+3表现:")
        print(f"  样本数: {len(t3_data)}")
        print(f"  胜率: {t3_win_rate:.1f}%")
        print(f"  平均收益: {t3_avg:+.2f}%")
    
    # T+5统计
    t5_data = df[df['t5'].notna()]
    if len(t5_data) > 0:
        t5_win_rate = len(t5_data[t5_data['t5'] > 0]) / len(t5_data) * 100
        t5_avg = t5_data['t5'].mean()
        
        print(f"\nT+5表现:")
        print(f"  样本数: {len(t5_data)}")
        print(f"  胜率: {t5_win_rate:.1f}%")
        print(f"  平均收益: {t5_avg:+.2f}%")
    
    # 按评分分组
    print(f"\n{'='*70}")
    print("按评分分组统计")
    print(f"{'='*70}")
    
    for min_score in [100, 90, 80]:
        group = df[(df['score'] >= min_score) & (df['t1'].notna())]
        if len(group) > 0:
            win_rate = len(group[group['t1'] > 0]) / len(group) * 100
            avg_return = group['t1'].mean()
            print(f"\n评分≥{min_score}:")
            print(f"  样本数: {len(group)}")
            print(f"  胜率: {win_rate:.1f}%")
            print(f"  平均收益: {avg_return:+.2f}%")
    
    # TOP10和BOTTOM10
    print(f"\n{'='*70}")
    print("收益TOP10")
    print(f"{'='*70}")
    top10 = df[df['t1'].notna()].nlargest(10, 't1')
    print(top10[['date', 'name', 'score', 'pullback', 't1']].to_string(index=False))
    
    print(f"\n{'='*70}")
    print("亏损TOP10")
    print(f"{'='*70}")
    bottom10 = df[df['t1'].notna()].nsmallest(10, 't1')
    print(bottom10[['date', 'name', 'score', 'pullback', 't1']].to_string(index=False))
    
    print(f"\n{'='*70}")


def main():
    run_backtest()


if __name__ == '__main__':
    main()
