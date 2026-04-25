#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
久其软件（002279）案例回测
回测日期：2026年1月20日
验证"盘中托价+尾盘回落"策略
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['SimHei']
matplotlib.rcParams['axes.unicode_minus'] = False

def analyze_jiuqi_20260120():
    """分析久其软件1月20日的走势"""
    
    symbol = "002279"
    name = "久其软件"
    date = "20260120"
    
    print("=" * 70)
    print(f"{name}（{symbol}）案例分析")
    print(f"日期：2026年1月20日")
    print("=" * 70)
    
    # 1. 获取日K线数据（看大背景）
    print("\n【一、日线背景分析】")
    try:
        df_daily = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
        df_daily['日期'] = pd.to_datetime(df_daily['日期'])
        
        # 找到1月20日前后的数据
        target_date = pd.to_datetime('2026-01-20')
        recent = df_daily[df_daily['日期'] <= target_date].tail(10)
        
        if len(recent) > 0:
            print(f"\n最近10个交易日走势：")
            print(recent[['日期', '开盘', '收盘', '最高', '最低', '涨跌幅', '成交量']].to_string(index=False))
            
            # 1月20日当天数据
            day_data = recent[recent['日期'] == target_date]
            if len(day_data) > 0:
                day_data = day_data.iloc[0]
                print(f"\n1月20日当天：")
                print(f"  开盘: {day_data['开盘']:.2f}")
                print(f"  收盘: {day_data['收盘']:.2f}")
                print(f"  最高: {day_data['最高']:.2f}")
                print(f"  最低: {day_data['最低']:.2f}")
                print(f"  涨跌幅: {day_data['涨跌幅']:.2f}%")
                print(f"  振幅: {day_data['振幅']:.2f}%")
                print(f"  成交量: {day_data['成交量']/10000:.2f}万手")
                
                # 分析尾盘回落
                intraday_high = day_data['最高']
                close_price = day_data['收盘']
                pullback = (intraday_high - close_price) / intraday_high * 100
                
                print(f"\n尾盘回落分析：")
                print(f"  盘中最高: {intraday_high:.2f}")
                print(f"  收盘价: {close_price:.2f}")
                print(f"  回落幅度: {pullback:.2f}%")
                
                if pullback > 1:
                    print(f"  ✓ 确认尾盘回落！")
                
    except Exception as e:
        print(f"获取日线数据失败: {e}")
    
    # 2. 获取分笔成交数据（看大单）
    print("\n【二、分笔成交分析（大单识别）】")
    try:
        # 获取分笔数据
        df_tick = ak.stock_zh_a_tick_tx_js(symbol=symbol)
        
        if df_tick is not None and len(df_tick) > 0:
            print(f"\n分笔数据点数: {len(df_tick)}")
            
            # 计算成交金额
            df_tick['成交金额'] = df_tick['成交量'] * df_tick['成交价']
            
            # 分类订单大小
            big_threshold = 50000  # 5万元为大单
            mid_threshold = 10000  # 1万元为中单
            
            df_tick['订单类型'] = pd.cut(
                df_tick['成交金额'],
                bins=[0, mid_threshold, big_threshold, float('inf')],
                labels=['小单', '中单', '大单']
            )
            
            # 统计各类订单
            print(f"\n订单分类统计：")
            print(df_tick['订单类型'].value_counts())
            
            # 分析大单
            big_orders = df_tick[df_tick['订单类型'] == '大单']
            print(f"\n大单详情（前20笔）：")
            if len(big_orders) > 0:
                big_orders_display = big_orders.head(20)[['成交时间', '成交价', '成交量', '成交金额', '性质']]
                print(big_orders_display.to_string(index=False))
                
                # 统计大单买卖
                big_buy = big_orders[big_orders['性质'] == '买盘']
                big_sell = big_orders[big_orders['性质'] == '卖盘']
                
                print(f"\n大单统计：")
                print(f"  大单买入: {len(big_buy)}笔, 金额: {big_buy['成交金额'].sum()/10000:.2f}万元")
                print(f"  大单卖出: {len(big_sell)}笔, 金额: {big_sell['成交金额'].sum()/10000:.2f}万元")
                print(f"  大单净买入: {(big_buy['成交金额'].sum() - big_sell['成交金额'].sum())/10000:.2f}万元")
            else:
                print("  未发现大单")
            
            # 分析托价位（大单买入集中的价格）
            if len(big_buy) > 0:
                support_prices = big_buy['成交价'].values
                support_price = np.median(support_prices)  # 中位数作为托价位
                
                print(f"\n托价位分析（基于大单买入）：")
                print(f"  大单买入价格范围: {support_prices.min():.2f} - {support_prices.max():.2f}")
                print(f"  大单买入中位数: {support_price:.2f}")
                print(f"  ✓ 主力托价位: {support_price:.2f}")
        
    except Exception as e:
        print(f"获取分笔数据失败: {e}")
        print("尝试使用分时数据...")
    
    # 3. 获取分时数据（看整体走势）
    print("\n【三、分时走势分析】")
    try:
        df_min = ak.stock_zh_a_hist_min_em(symbol=symbol, period='1', adjust='', start_date='2026-01-20 09:30:00', end_date='2026-01-20 15:00:00')
        
        if df_min is not None and len(df_min) > 0:
            df_min['时间'] = pd.to_datetime(df_min['时间'])
            df_min = df_min.sort_values('时间')
            
            print(f"\n分时数据点数: {len(df_min)}")
            
            # 分析不同时段
            morning = df_min[df_min['时间'].dt.time < pd.Timestamp('11:30').time()]
            afternoon_early = df_min[(df_min['时间'].dt.time >= pd.Timestamp('13:00').time()) & 
                                     (df_min['时间'].dt.time < pd.Timestamp('14:30').time())]
            closing = df_min[df_min['时间'].dt.time >= pd.Timestamp('14:30').time()]
            
            print(f"\n时段划分：")
            print(f"  上午: {len(morning)}个数据点")
            print(f"  下午前段: {len(afternoon_early)}个数据点")
            print(f"  尾盘: {len(closing)}个数据点")
            
            # 找支撑位（价格集中的区域）
            prices = df_min['收盘'].values
            price_min = prices.min()
            price_max = prices.max()
            
            # 统计价格分布
            bins = np.linspace(price_min, price_max, 20)
            hist, bin_edges = np.histogram(prices, bins=bins)
            
            # 找到最集中的价格区间（支撑位）
            max_count_idx = np.argmax(hist)
            support_price = (bin_edges[max_count_idx] + bin_edges[max_count_idx + 1]) / 2
            
            print(f"\n价格分析：")
            print(f"  最低价: {price_min:.2f}")
            print(f"  最高价: {price_max:.2f}")
            print(f"  价格区间: {price_max - price_min:.2f}")
            print(f"  支撑位（价格集中区）: {support_price:.2f}")
            
            # 分析尾盘走势
            if len(closing) > 0:
                closing_prices = closing['收盘'].values
                closing_high = closing_prices.max()
                closing_low = closing_prices.min()
                closing_final = closing_prices[-1]
                
                print(f"\n尾盘走势：")
                print(f"  尾盘最高: {closing_high:.2f}")
                print(f"  尾盘最低: {closing_low:.2f}")
                print(f"  收盘价: {closing_final:.2f}")
                
                # 判断尾盘回落
                if closing_final < price_max * 0.98:
                    print(f"  ✓ 尾盘从高点回落")
                    
                    # 判断是否守住支撑
                    if closing_final >= support_price * 0.98:
                        print(f"  ✓ 守住支撑位 {support_price:.2f}")
                        print(f"  🌟 符合'盘中托价+尾盘回落'模式！")
                    else:
                        print(f"  ⚠️ 跌破支撑位")
            
            # 绘制分时图
            plt.figure(figsize=(14, 8))
            
            # 主图：分时价格
            plt.subplot(2, 1, 1)
            plt.plot(df_min['时间'], df_min['收盘'], 'b-', linewidth=1, label='价格')
            plt.axhline(y=support_price, color='r', linestyle='--', linewidth=1, label=f'支撑位 {support_price:.2f}')
            plt.axhline(y=price_max, color='g', linestyle='--', linewidth=1, label=f'最高价 {price_max:.2f}')
            
            # 标注尾盘区域
            if len(closing) > 0:
                plt.axvspan(closing.iloc[0]['时间'], closing.iloc[-1]['时间'], 
                           alpha=0.2, color='yellow', label='尾盘时段')
            
            plt.title(f'{name}（{symbol}）2026-01-20 分时走势', fontsize=14, fontweight='bold')
            plt.ylabel('价格（元）', fontsize=12)
            plt.legend(loc='best')
            plt.grid(True, alpha=0.3)
            
            # 副图：成交量
            plt.subplot(2, 1, 2)
            colors = ['red' if df_min.iloc[i]['收盘'] >= df_min.iloc[i]['开盘'] else 'green' 
                     for i in range(len(df_min))]
            plt.bar(df_min['时间'], df_min['成交量'], color=colors, alpha=0.6, width=0.0003)
            plt.ylabel('成交量', fontsize=12)
            plt.xlabel('时间', fontsize=12)
            plt.grid(True, alpha=0.3)
            
            plt.tight_layout()
            
            # 保存图片
            filename = f'{name}_20260120_分时分析.png'
            plt.savefig(filename, dpi=150, bbox_inches='tight')
            print(f"\n分时图已保存: {filename}")
            
            plt.close()
            
    except Exception as e:
        print(f"获取分时数据失败: {e}")
    
    # 4. 后续走势验证
    print("\n【四、后续走势验证】")
    try:
        df_daily = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
        df_daily['日期'] = pd.to_datetime(df_daily['日期'])
        
        # 1月20日之后的走势
        target_date = pd.to_datetime('2026-01-20')
        after = df_daily[df_daily['日期'] > target_date].head(5)
        
        if len(after) > 0:
            print(f"\n1月20日之后的走势：")
            print(after[['日期', '开盘', '收盘', '最高', '最低', '涨跌幅']].to_string(index=False))
            
            # 计算如果1月20日收盘买入的收益
            if len(day_data) > 0:
                buy_price = day_data['收盘']
                
                print(f"\n如果1月20日收盘买入（{buy_price:.2f}元）：")
                
                for idx, row in after.iterrows():
                    days = (row['日期'] - target_date).days
                    profit = (row['收盘'] - buy_price) / buy_price * 100
                    print(f"  {row['日期'].strftime('%Y-%m-%d')} (T+{days}): "
                          f"收盘{row['收盘']:.2f}, 收益{profit:+.2f}%")
        else:
            print("暂无后续数据")
            
    except Exception as e:
        print(f"获取后续数据失败: {e}")
    
    # 5. 策略评分
    print("\n【五、策略信号评分】")
    print("\n根据'盘中托价+尾盘回落'策略评分：")
    
    score = 0
    reasons = []
    
    # 评分标准
    if 'day_data' in locals() and len(day_data) > 0:
        # 1. 尾盘回落（30分）
        if pullback > 1:
            score += 30
            reasons.append(f"尾盘回落{pullback:.2f}%")
        
        # 2. 振幅适中（20分）
        if 3 < day_data['振幅'] < 8:
            score += 20
            reasons.append(f"振幅{day_data['振幅']:.2f}%适中")
        
        # 3. 涨幅温和（20分）
        if 0 < day_data['涨跌幅'] < 5:
            score += 20
            reasons.append(f"涨幅{day_data['涨跌幅']:.2f}%温和")
        
        # 4. 收盘价接近支撑位（30分）
        if 'support_price' in locals():
            position = (day_data['收盘'] - support_price) / support_price * 100
            if -2 < position < 2:
                score += 30
                reasons.append(f"收盘价接近支撑位({position:+.2f}%)")
    
    print(f"\n总分: {score}/100")
    print(f"评分理由: {', '.join(reasons)}")
    
    if score >= 80:
        print(f"\n🌟 强烈买入信号！")
        print(f"建议：第二天低开到支撑位附近买入")
    elif score >= 60:
        print(f"\n✓ 买入信号")
        print(f"建议：观察第二天走势，低开可以考虑")
    else:
        print(f"\n⚠️ 信号不明显")
        print(f"建议：继续观察")
    
    print("\n" + "=" * 70)


def main():
    """主函数"""
    analyze_jiuqi_20260120()


if __name__ == '__main__':
    main()
