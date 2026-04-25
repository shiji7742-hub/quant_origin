#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
尾盘回落分析工具
专门分析"盘中托价 + 尾盘回落"的组合信号

核心逻辑：
如果盘中有明显的主力托价动作，尾盘回落反而是好事！
- 洗盘：吓出短线客
- 隐蔽：不想暴露意图
- 降成本：第二天继续吸筹
"""

import akshare as ak
import pandas as pd
from datetime import datetime, time as dt_time
import numpy as np
from typing import Dict, List

class ClosingPullbackAnalyzer:
    """尾盘回落分析器"""
    
    def __init__(self):
        self.big_order_threshold = 50000
        
    def get_intraday_data(self, symbol: str) -> pd.DataFrame:
        """获取日内分时数据"""
        try:
            # 获取分时数据
            df = ak.stock_zh_a_hist_min_em(symbol=symbol, period='1', adjust='')
            if df is None or len(df) == 0:
                return pd.DataFrame()
            
            df['时间'] = pd.to_datetime(df['时间'])
            df = df.sort_values('时间')
            
            return df
            
        except Exception as e:
            print(f"获取{symbol}数据失败: {e}")
            return pd.DataFrame()
    
    def get_tick_data(self, symbol: str) -> pd.DataFrame:
        """获取分笔数据"""
        try:
            df = ak.stock_zh_a_tick_tx(symbol=symbol)
            if df is None or len(df) == 0:
                return pd.DataFrame()
            
            df['amount'] = df['成交量'] * df['成交价']
            df['direction'] = df['性质'].map({'买盘': 1, '卖盘': -1, '中性盘': 0})
            df['time'] = pd.to_datetime(df['成交时间'])
            
            return df.sort_values('time')
            
        except Exception as e:
            return pd.DataFrame()
    
    def detect_intraday_support(self, df: pd.DataFrame) -> Dict:
        """检测盘中托价行为"""
        
        # 排除尾盘（14:30之后）
        df = df[df['时间'].dt.time < dt_time(14, 30)]
        
        if len(df) < 20:
            return None
        
        # 分析价格走势
        prices = df['收盘'].values
        volumes = df['成交量'].values
        
        # 找到明显的支撑位（价格多次触及但不破）
        price_min = prices.min()
        price_max = prices.max()
        price_range = price_max - price_min
        
        # 将价格分成20个区间
        bins = np.linspace(price_min, price_max, 21)
        price_counts = np.histogram(prices, bins=bins)[0]
        
        # 找到价格集中的区间（支撑位）
        support_idx = np.argmax(price_counts)
        support_price = (bins[support_idx] + bins[support_idx + 1]) / 2
        
        # 统计在支撑位附近的成交量
        near_support = df[
            (df['收盘'] >= support_price * 0.995) &
            (df['收盘'] <= support_price * 1.005)
        ]
        support_volume = near_support['成交量'].sum()
        total_volume = volumes.sum()
        support_volume_ratio = support_volume / total_volume if total_volume > 0 else 0
        
        # 判断是否有明显托价（价格集中 + 成交量大）
        has_support = (
            support_volume_ratio > 0.3 and  # 30%以上成交在支撑位
            len(near_support) >= 5  # 至少5个时间点
        )
        
        return {
            'has_support': has_support,
            'support_price': support_price,
            'support_volume_ratio': support_volume_ratio,
            'intraday_high': price_max,
            'intraday_low': price_min,
            'price_range': price_range
        }
    
    def analyze_closing_period(self, df: pd.DataFrame, support_info: Dict) -> Dict:
        """分析尾盘走势"""
        
        # 尾盘时段（14:30-15:00）
        closing_df = df[df['时间'].dt.time >= dt_time(14, 30)]
        
        if len(closing_df) < 5:
            return None
        
        # 尾盘价格走势
        closing_prices = closing_df['收盘'].values
        closing_volumes = closing_df['成交量'].values
        
        closing_high = closing_prices.max()
        closing_low = closing_prices.min()
        closing_price = closing_prices[-1]
        
        # 尾盘成交量占比
        closing_volume = closing_volumes.sum()
        total_volume = df['成交量'].sum()
        closing_volume_ratio = closing_volume / total_volume if total_volume > 0 else 0
        
        # 判断是否尾盘回落
        support_price = support_info['support_price']
        intraday_high = support_info['intraday_high']
        
        # 回落幅度
        pullback_from_high = (intraday_high - closing_price) / intraday_high * 100
        
        # 相对支撑位的位置
        position_vs_support = (closing_price - support_price) / support_price * 100
        
        # 判断是否健康回落
        is_pullback = (
            closing_price < intraday_high * 0.98 and  # 从高点回落超过2%
            closing_price >= support_price * 0.98  # 但不破支撑位
        )
        
        is_healthy = (
            closing_volume_ratio < 0.25 and  # 尾盘成交量<25%（萎缩）
            closing_low >= support_price * 0.97  # 尾盘最低价不破支撑
        )
        
        return {
            'is_pullback': is_pullback,
            'is_healthy': is_healthy,
            'is_good_signal': is_pullback and is_healthy,
            'pullback_from_high': pullback_from_high,
            'position_vs_support': position_vs_support,
            'closing_volume_ratio': closing_volume_ratio,
            'closing_price': closing_price,
            'intraday_high': intraday_high,
            'support_price': support_price
        }
    
    def analyze_big_orders_in_closing(self, symbol: str) -> Dict:
        """分析尾盘大单情况"""
        
        tick_df = self.get_tick_data(symbol)
        if len(tick_df) == 0:
            return None
        
        # 尾盘时段
        last_time = tick_df.iloc[-1]['time']
        closing_start = last_time.replace(hour=14, minute=30, second=0)
        
        closing_ticks = tick_df[tick_df['time'] >= closing_start]
        
        if len(closing_ticks) == 0:
            return None
        
        # 统计尾盘大单
        big_sells = closing_ticks[
            (closing_ticks['amount'] >= self.big_order_threshold) &
            (closing_ticks['direction'] == -1)
        ]
        
        big_buys = closing_ticks[
            (closing_ticks['amount'] >= self.big_order_threshold) &
            (closing_ticks['direction'] == 1)
        ]
        
        return {
            'big_sell_count': len(big_sells),
            'big_sell_amount': big_sells['amount'].sum() if len(big_sells) > 0 else 0,
            'big_buy_count': len(big_buys),
            'big_buy_amount': big_buys['amount'].sum() if len(big_buys) > 0 else 0,
            'has_big_sell': len(big_sells) > 0,
            'has_big_buy': len(big_buys) > 0
        }
    
    def analyze_stock(self, symbol: str, name: str = None) -> Dict:
        """综合分析"""
        
        print(f"\n分析 {name or symbol}...")
        
        # 1. 获取分时数据
        df = self.get_intraday_data(symbol)
        if len(df) == 0:
            print("  无法获取数据")
            return None
        
        # 2. 检测盘中托价
        support_info = self.detect_intraday_support(df)
        
        if not support_info or not support_info['has_support']:
            print("  盘中无明显托价")
            return None
        
        print(f"  ✓ 发现盘中托价: {support_info['support_price']:.2f}")
        
        # 3. 分析尾盘走势
        closing_info = self.analyze_closing_period(df, support_info)
        
        if not closing_info:
            print("  无尾盘数据")
            return None
        
        # 4. 分析尾盘大单
        big_orders = self.analyze_big_orders_in_closing(symbol)
        
        # 5. 综合判断
        if closing_info['is_good_signal']:
            print(f"  🌟 尾盘健康回落! 回落{closing_info['pullback_from_high']:.2f}%")
            print(f"     支撑位: {support_info['support_price']:.2f}")
            print(f"     收盘价: {closing_info['closing_price']:.2f}")
            print(f"     相对支撑: {closing_info['position_vs_support']:+.2f}%")
            
            # 判断信号强度
            signal_strength = 0
            reasons = []
            
            if closing_info['position_vs_support'] > -1 and closing_info['position_vs_support'] < 2:
                signal_strength += 30
                reasons.append("收盘价接近支撑位")
            
            if closing_info['closing_volume_ratio'] < 0.2:
                signal_strength += 25
                reasons.append("尾盘成交量极度萎缩")
            
            if support_info['support_volume_ratio'] > 0.4:
                signal_strength += 25
                reasons.append("盘中支撑位成交活跃")
            
            if big_orders and not big_orders['has_big_sell']:
                signal_strength += 20
                reasons.append("尾盘无大单砸盘")
            
            print(f"     信号强度: {signal_strength}/100")
            print(f"     理由: {', '.join(reasons)}")
            
            return {
                'symbol': symbol,
                'name': name or symbol,
                'is_good_signal': True,
                'signal_strength': signal_strength,
                'support_info': support_info,
                'closing_info': closing_info,
                'big_orders': big_orders,
                'reasons': reasons
            }
        else:
            if closing_info['is_pullback']:
                print(f"  ⚠️ 尾盘回落但不健康（成交量未萎缩或破支撑）")
            else:
                print(f"  盘中托价，尾盘未回落")
            
            return None
    
    def scan_market(self, stock_pool: List[str] = None) -> List[Dict]:
        """扫描市场"""
        
        if stock_pool is None:
            # 获取今日涨幅榜
            try:
                df = ak.stock_zh_a_spot_em()
                # 筛选涨幅0-5%的股票（温和上涨）
                df = df[(df['涨跌幅'] > 0) & (df['涨跌幅'] < 5)]
                df = df.sort_values('涨跌幅', ascending=False).head(100)
                stock_pool = df['代码'].tolist()
            except:
                return []
        
        results = []
        
        for i, symbol in enumerate(stock_pool):
            print(f"\n进度: {i+1}/{len(stock_pool)}")
            
            result = self.analyze_stock(symbol)
            
            if result:
                results.append(result)
        
        return results
    
    def generate_report(self, results: List[Dict], output_file: str = None):
        """生成报告"""
        
        if not results:
            print("\n未发现'盘中托价+尾盘回落'信号")
            return
        
        # 按信号强度排序
        results.sort(key=lambda x: x['signal_strength'], reverse=True)
        
        report_data = []
        
        for r in results:
            support = r['support_info']
            closing = r['closing_info']
            
            report_data.append({
                '代码': r['symbol'],
                '名称': r['name'],
                '信号强度': f"{r['signal_strength']}/100",
                '支撑价': f"{support['support_price']:.2f}",
                '收盘价': f"{closing['closing_price']:.2f}",
                '相对支撑': f"{closing['position_vs_support']:+.2f}%",
                '回落幅度': f"{closing['pullback_from_high']:.2f}%",
                '尾盘成交占比': f"{closing['closing_volume_ratio']*100:.1f}%",
                '支撑成交占比': f"{support['support_volume_ratio']*100:.1f}%",
                '信号理由': ', '.join(r['reasons'])
            })
        
        df_report = pd.DataFrame(report_data)
        
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f'尾盘回落信号_{timestamp}.xlsx'
        
        df_report.to_excel(output_file, index=False, engine='openpyxl')
        
        print(f"\n{'='*70}")
        print(f"报告已生成: {output_file}")
        print(f"共发现 {len(results)} 只股票有'盘中托价+尾盘回落'信号")
        print(f"{'='*70}")
        
        print("\n【信号强度TOP10】")
        print(df_report.head(10).to_string(index=False))
        
        return df_report


def main():
    """主函数"""
    print("=" * 70)
    print("尾盘回落分析系统")
    print("=" * 70)
    print("\n核心逻辑：")
    print("  盘中有托价 + 尾盘回落 = 好信号！")
    print("\n为什么？")
    print("  1. 洗盘：吓出短线客")
    print("  2. 隐蔽：不想暴露意图，避免上龙虎榜")
    print("  3. 降成本：第二天可以更低位置继续吸")
    print("\n关键判断：")
    print("  ✓ 盘中有明显托价动作")
    print("  ✓ 尾盘回落但不破托价位")
    print("  ✓ 尾盘成交量萎缩")
    print("  ✓ 无大单砸盘")
    print("=" * 70)
    
    analyzer = ClosingPullbackAnalyzer()
    
    print("\n开始扫描市场...")
    results = analyzer.scan_market()
    
    print("\n生成报告...")
    analyzer.generate_report(results)
    
    print("\n扫描完成！")
    print("\n💡 操作建议：")
    print("  - 信号强度>80分：重点关注，第二天低开可以买入")
    print("  - 信号强度60-80分：观察，等待第二天再次托价确认")
    print("  - 止损：跌破支撑价2%")


if __name__ == '__main__':
    main()
