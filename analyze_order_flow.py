#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
订单流分析工具
区分逐笔大单和合单大单

核心理解：
1. 逐笔大单 = 单笔成交就是大单（最强信号，主力直接扫货）
2. 3秒合单大单 = 3秒内累计成交达到大单（次强信号，主力分批吃）
3. 小单累积 = 散户行为
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List
import time

class OrderFlowAnalyzer:
    """订单流分析器"""
    
    def __init__(self):
        # 大单标准（可根据股价调整）
        self.single_big_threshold = 50000  # 逐笔大单：5万元
        self.merged_big_threshold = 100000  # 合单大单：10万元
        self.merge_window = 3  # 合单时间窗口：3秒
        
    def get_tick_data(self, symbol: str, date: str = None) -> pd.DataFrame:
        """获取分笔数据"""
        try:
            print(f"正在获取{symbol}的分笔数据...")
            df = ak.stock_zh_a_tick_tx_js(symbol=symbol)
            
            if df is None or len(df) == 0:
                return pd.DataFrame()
            
            # 计算成交金额
            df['成交金额'] = df['成交量'] * df['成交价']
            
            # 转换时间
            df['时间'] = pd.to_datetime(df['成交时间'])
            df = df.sort_values('时间')
            
            return df
            
        except Exception as e:
            print(f"获取数据失败: {e}")
            return pd.DataFrame()
    
    def classify_single_orders(self, df: pd.DataFrame) -> pd.DataFrame:
        """分类逐笔订单"""
        
        # 逐笔订单分类
        df['逐笔类型'] = pd.cut(
            df['成交金额'],
            bins=[0, 10000, self.single_big_threshold, float('inf')],
            labels=['小单', '中单', '逐笔大单']
        )
        
        return df
    
    def detect_merged_big_orders(self, df: pd.DataFrame) -> List[Dict]:
        """
        检测3秒合单大单（量化拆单识别）
        
        关键：量化程序会把大单拆成小单，在3秒内快速扫过多个价位
        特征：
        1. 时间极短（3秒内）
        2. 连续小单
        3. 累计金额大
        4. 价格连续上扫（关键！）
        """
        
        merged_orders = []
        
        # 按3秒窗口聚合
        df['时间戳'] = df['时间'].astype(np.int64) // 10**9
        
        processed_windows = set()  # 避免重复
        
        for i in range(len(df)):
            current_time = df.iloc[i]['时间戳']
            
            # 避免重复处理同一个窗口
            if current_time in processed_windows:
                continue
            
            # 找3秒内的所有成交
            window_start = current_time
            window_end = current_time + self.merge_window
            
            window_data = df[
                (df['时间戳'] >= window_start) & 
                (df['时间戳'] < window_end)
            ]
            
            if len(window_data) < 3:  # 至少3笔（量化拆单特征）
                continue
            
            # 分析买盘和卖盘
            buy_orders = window_data[window_data['性质'] == '买盘']
            sell_orders = window_data[window_data['性质'] == '卖盘']
            
            # 检测买盘扫单
            if len(buy_orders) >= 3:
                buy_amount = buy_orders['成交金额'].sum()
                
                if buy_amount >= self.merged_big_threshold:
                    # 检测是否连续上扫（关键特征！）
                    buy_prices = buy_orders['成交价'].values
                    price_range = buy_prices.max() - buy_prices.min()
                    avg_price = buy_prices.mean()
                    price_spread = (price_range / avg_price * 100) if avg_price > 0 else 0
                    
                    # 判断是否为扫单（价格跨度>0.3%）
                    is_sweep = price_spread > 0.3
                    
                    # 计算扫单强度（笔数密度）
                    sweep_intensity = len(buy_orders) / self.merge_window  # 笔/秒
                    
                    merged_orders.append({
                        '时间': df.iloc[i]['时间'],
                        '起始价': buy_prices.min(),
                        '结束价': buy_prices.max(),
                        '价格跨度': price_spread,
                        '合单金额': buy_amount,
                        '笔数': len(buy_orders),
                        '方向': '买盘',
                        '是否扫单': is_sweep,
                        '扫单强度': sweep_intensity,
                        '类型': '量化拆单' if is_sweep and sweep_intensity > 1 else '普通合单'
                    })
                    
                    processed_windows.add(current_time)
            
            # 检测卖盘扫单
            if len(sell_orders) >= 3:
                sell_amount = sell_orders['成交金额'].sum()
                
                if sell_amount >= self.merged_big_threshold:
                    sell_prices = sell_orders['成交价'].values
                    price_range = sell_prices.max() - sell_prices.min()
                    avg_price = sell_prices.mean()
                    price_spread = (price_range / avg_price * 100) if avg_price > 0 else 0
                    
                    is_sweep = price_spread > 0.3
                    sweep_intensity = len(sell_orders) / self.merge_window
                    
                    merged_orders.append({
                        '时间': df.iloc[i]['时间'],
                        '起始价': sell_prices.max(),
                        '结束价': sell_prices.min(),
                        '价格跨度': price_spread,
                        '合单金额': sell_amount,
                        '笔数': len(sell_orders),
                        '方向': '卖盘',
                        '是否扫单': is_sweep,
                        '扫单强度': sweep_intensity,
                        '类型': '量化拆单' if is_sweep and sweep_intensity > 1 else '普通合单'
                    })
                    
                    processed_windows.add(current_time)
        
        return merged_orders
    
    def analyze_support_action(self, df: pd.DataFrame) -> Dict:
        """分析托价动作"""
        
        # 1. 逐笔大单分析
        single_big = df[df['逐笔类型'] == '逐笔大单']
        single_big_buy = single_big[single_big['性质'] == '买盘']
        single_big_sell = single_big[single_big['性质'] == '卖盘']
        
        print(f"\n【逐笔大单分析】（最强信号）")
        print(f"  逐笔大单买入: {len(single_big_buy)}笔, {single_big_buy['成交金额'].sum()/10000:.2f}万元")
        print(f"  逐笔大单卖出: {len(single_big_sell)}笔, {single_big_sell['成交金额'].sum()/10000:.2f}万元")
        
        if len(single_big_buy) > 0:
            print(f"\n  逐笔大单买入详情（前10笔）：")
            display = single_big_buy.head(10)[['成交时间', '成交价', '成交量', '成交金额']]
            print(display.to_string(index=False))
            
            # 逐笔大单的托价位
            single_support_price = single_big_buy['成交价'].median()
            print(f"\n  ✓ 逐笔大单托价位: {single_support_price:.2f}")
        else:
            single_support_price = None
            print(f"  未发现逐笔大单买入")
        
        # 2. 合单大单分析（量化拆单识别）
        print(f"\n【3秒合单大单分析】（量化拆单识别）")
        merged_orders = self.detect_merged_big_orders(df)
        
        if merged_orders:
            merged_df = pd.DataFrame(merged_orders)
            merged_buy = merged_df[merged_df['方向'] == '买盘']
            merged_sell = merged_df[merged_df['方向'] == '卖盘']
            
            # 区分量化拆单和普通合单
            quant_sweep_buy = merged_buy[merged_buy['类型'] == '量化拆单']
            normal_buy = merged_buy[merged_buy['类型'] == '普通合单']
            
            print(f"  量化拆单买入: {len(quant_sweep_buy)}次, {quant_sweep_buy['合单金额'].sum()/10000:.2f}万元")
            print(f"  普通合单买入: {len(normal_buy)}次, {normal_buy['合单金额'].sum()/10000:.2f}万元")
            print(f"  合单大单卖出: {len(merged_sell)}次, {merged_sell['合单金额'].sum()/10000:.2f}万元")
            
            if len(quant_sweep_buy) > 0:
                print(f"\n  🎯 量化拆单买入详情（前10次）：")
                display = quant_sweep_buy.head(10)[['时间', '起始价', '结束价', '价格跨度', '合单金额', '笔数', '扫单强度']]
                print(display.to_string(index=False))
                
                # 量化拆单的托价位（取结束价，因为是扫到的最高价）
                merged_support_price = quant_sweep_buy['结束价'].median()
                print(f"\n  ✓ 量化拆单托价位: {merged_support_price:.2f}")
                print(f"  说明：主力用量化程序拆单吸筹，隐蔽性强！")
            elif len(normal_buy) > 0:
                print(f"\n  普通合单买入详情（前10次）：")
                display = normal_buy.head(10)[['时间', '起始价', '结束价', '合单金额', '笔数']]
                print(display.to_string(index=False))
                
                merged_support_price = normal_buy['起始价'].median()
                print(f"\n  ✓ 普通合单托价位: {merged_support_price:.2f}")
            else:
                merged_support_price = None
                print(f"  未发现合单大单买入")
        else:
            merged_support_price = None
            quant_sweep_buy = pd.DataFrame()
            print(f"  未发现合单大单")
        
        # 3. 综合评估
        print(f"\n【托价信号评估】")
        
        signal_strength = 0
        signal_type = []
        support_price = None
        
        if single_support_price is not None:
            signal_strength += 50  # 逐笔大单权重最高
            signal_type.append("逐笔大单托价")
            support_price = single_support_price
        
        # 量化拆单的权重
        if len(quant_sweep_buy) > 0:
            signal_strength += 40  # 量化拆单权重很高（说明主力在隐蔽吸筹）
            signal_type.append("量化拆单托价")
            if support_price is None:
                support_price = merged_support_price
            else:
                support_price = (support_price + merged_support_price) / 2
        elif merged_support_price is not None:
            signal_strength += 25  # 普通合单权重较低
            signal_type.append("普通合单托价")
            if support_price is None:
                support_price = merged_support_price
            else:
                support_price = (support_price + merged_support_price) / 2
        
        # 判断托价的持续性
        if len(single_big_buy) >= 3 or len(quant_sweep_buy) >= 3:
            signal_strength += 20
            signal_type.append("持续托价")
        
        print(f"  信号强度: {signal_strength}/110")
        print(f"  信号类型: {', '.join(signal_type) if signal_type else '无明显托价'}")
        if support_price:
            print(f"  综合托价位: {support_price:.2f}")
        
        return {
            'signal_strength': signal_strength,
            'signal_type': signal_type,
            'support_price': support_price,
            'single_big_buy_count': len(single_big_buy),
            'single_big_buy_amount': single_big_buy['成交金额'].sum(),
            'quant_sweep_count': len(quant_sweep_buy),
            'quant_sweep_amount': quant_sweep_buy['合单金额'].sum() if len(quant_sweep_buy) > 0 else 0,
            'merged_big_buy_count': len(merged_buy) if merged_orders else 0,
            'merged_big_buy_amount': merged_buy['合单金额'].sum() if merged_orders and len(merged_buy) > 0 else 0
        }
    
    def analyze_closing_pullback(self, df: pd.DataFrame, support_price: float) -> Dict:
        """分析尾盘回落"""
        
        # 找尾盘时段（最后30分钟）
        last_time = df.iloc[-1]['时间']
        closing_start = last_time - timedelta(minutes=30)
        
        closing_df = df[df['时间'] >= closing_start]
        
        if len(closing_df) == 0:
            return None
        
        # 全天最高价
        intraday_high = df['成交价'].max()
        
        # 尾盘价格
        closing_prices = closing_df['成交价'].values
        closing_high = closing_prices.max()
        closing_low = closing_prices.min()
        closing_final = closing_prices[-1]
        
        # 判断尾盘回落
        pullback_from_high = (intraday_high - closing_final) / intraday_high * 100
        
        is_pullback = closing_final < intraday_high * 0.98
        
        # 判断是否守住支撑
        if support_price:
            position_vs_support = (closing_final - support_price) / support_price * 100
            hold_support = closing_final >= support_price * 0.98
        else:
            position_vs_support = None
            hold_support = False
        
        return {
            'is_pullback': is_pullback,
            'hold_support': hold_support,
            'pullback_from_high': pullback_from_high,
            'position_vs_support': position_vs_support,
            'intraday_high': intraday_high,
            'closing_final': closing_final,
            'support_price': support_price
        }
    
    def analyze_stock(self, symbol: str, name: str = None) -> Dict:
        """综合分析"""
        
        print("=" * 70)
        print(f"订单流分析: {name or symbol} ({symbol})")
        print("=" * 70)
        
        # 获取数据
        df = self.get_tick_data(symbol)
        
        if len(df) == 0:
            print("无法获取数据")
            return None
        
        print(f"\n总成交笔数: {len(df)}")
        
        # 分类订单
        df = self.classify_single_orders(df)
        
        # 分析托价
        support_analysis = self.analyze_support_action(df)
        
        # 分析尾盘
        if support_analysis['support_price']:
            closing_analysis = self.analyze_closing_pullback(df, support_analysis['support_price'])
            
            if closing_analysis:
                print(f"\n【尾盘回落分析】")
                print(f"  盘中最高: {closing_analysis['intraday_high']:.2f}")
                print(f"  收盘价: {closing_analysis['closing_final']:.2f}")
                print(f"  回落幅度: {closing_analysis['pullback_from_high']:.2f}%")
                
                if closing_analysis['is_pullback']:
                    print(f"  ✓ 确认尾盘回落")
                    
                    if closing_analysis['hold_support']:
                        print(f"  ✓ 守住托价位 {closing_analysis['support_price']:.2f}")
                        print(f"  相对托价位: {closing_analysis['position_vs_support']:+.2f}%")
                        print(f"\n  🌟 符合'托价+回落'模式！")
        else:
            closing_analysis = None
        
        # 综合评分
        total_score = support_analysis['signal_strength']
        
        if closing_analysis and closing_analysis['is_pullback'] and closing_analysis['hold_support']:
            total_score += 20  # 尾盘回落加分
        
        print(f"\n【综合评分】")
        print(f"  总分: {total_score}/130")
        
        if total_score >= 80:
            print(f"  🌟 强烈买入信号！")
        elif total_score >= 60:
            print(f"  ✓ 买入信号")
        else:
            print(f"  观察信号")
        
        print("=" * 70)
        
        return {
            'symbol': symbol,
            'name': name or symbol,
            'support_analysis': support_analysis,
            'closing_analysis': closing_analysis,
            'total_score': total_score
        }


def main():
    """主函数"""
    
    print("=" * 70)
    print("订单流分析工具")
    print("区分逐笔大单和合单大单")
    print("=" * 70)
    print("\n信号强度：")
    print("  逐笔大单托价 = 最强信号（主力直接扫货，不拆单）")
    print("  量化拆单托价 = 次强信号（主力用程序拆单，隐蔽吸筹）")
    print("  普通合单托价 = 较弱信号（可能是散户凑巧）")
    print("\n量化拆单特征：")
    print("  1. 3秒内连续多笔小单")
    print("  2. 价格连续上扫（跨越多个价位）")
    print("  3. 累计金额达到大单标准")
    print("=" * 70)
    
    analyzer = OrderFlowAnalyzer()
    
    # 分析久其软件
    symbol = "002279"
    name = "久其软件"
    
    result = analyzer.analyze_stock(symbol, name)
    
    print("\n分析完成！")


if __name__ == '__main__':
    main()
