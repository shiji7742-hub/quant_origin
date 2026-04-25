#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主力对敲控盘扫描 - 识别主力建仓语言
核心逻辑：大单托价 → 释放抛压 → 横盘吸筹 → 再次托价
这是主力通过对敲手法控制股价、消化抛压、完成建仓的过程
"""

import akshare as ak
import pandas as pd
from datetime import datetime, timedelta
import time
from typing import Dict, List, Tuple
import numpy as np

class MarketMakerControlScanner:
    """主力对敲控盘扫描器"""
    
    def __init__(self):
        self.big_order_threshold = 50000  # 大单金额阈值（元）
        self.small_order_threshold = 10000  # 小单金额阈值（元）
        
    def get_realtime_tick_data(self, symbol: str) -> pd.DataFrame:
        """获取实时分笔数据"""
        try:
            # 获取实时分笔成交
            df = ak.stock_zh_a_tick_tx(symbol=symbol)
            if df is None or len(df) == 0:
                return pd.DataFrame()
            
            # 计算成交金额
            df['amount'] = df['成交量'] * df['成交价']
            
            # 判断买卖方向（简化版）
            df['direction'] = df['性质'].map({
                '买盘': 1,
                '卖盘': -1,
                '中性盘': 0
            })
            
            # 分类订单大小
            df['order_type'] = pd.cut(
                df['amount'],
                bins=[0, self.small_order_threshold, self.big_order_threshold, float('inf')],
                labels=['小单', '中单', '大单']
            )
            
            return df
            
        except Exception as e:
            print(f"获取{symbol}分笔数据失败: {e}")
            return pd.DataFrame()
    
    def analyze_absorption_pattern(self, df: pd.DataFrame) -> Dict:
        """分析主力对敲控盘模式"""
        if len(df) == 0:
            return None
        
        # 按时间窗口分析（每3分钟一个窗口，更敏感）
        df['time'] = pd.to_datetime(df['成交时间'])
        df = df.set_index('time')
        
        # 3分钟重采样（捕捉主力的操作节奏）
        windows = df.resample('3T')
        
        patterns = []
        
        for window_time, window_data in windows:
            if len(window_data) < 10:  # 数据太少跳过
                continue
            
            # 分析这个窗口的特征
            analysis = self._analyze_window(window_data)
            
            if analysis['is_market_maker_control']:
                patterns.append({
                    'time': window_time,
                    **analysis
                })
        
        if not patterns:
            return None
        
        # 返回最新的控盘模式
        latest = patterns[-1]
        
        # 分析控盘的持续性（关键！）
        # 如果多个窗口都出现控盘，说明主力在持续建仓
        continuous_control = len(patterns) >= 3
        
        return {
            'symbol': df.iloc[0].get('代码', ''),
            'name': df.iloc[0].get('名称', ''),
            'latest_pattern': latest,
            'pattern_count': len(patterns),
            'continuous_control': continuous_control,  # 是否持续控盘
            'all_patterns': patterns
        }
    
    def _analyze_window(self, window_data: pd.DataFrame) -> Dict:
        """分析单个时间窗口 - 识别主力对敲控盘模式"""
        
        # 按时间排序，分析订单流的时序特征
        window_data = window_data.sort_index()
        
        # 1. 统计各类订单
        small_sell = window_data[
            (window_data['order_type'] == '小单') & 
            (window_data['direction'] == -1)
        ]
        small_sell_count = len(small_sell)
        small_sell_amount = small_sell['amount'].sum() if len(small_sell) > 0 else 0
        
        # 大单主动买入（托价）
        big_buy = window_data[
            (window_data['order_type'] == '大单') & 
            (window_data['direction'] == 1)
        ]
        big_buy_count = len(big_buy)
        big_buy_amount = big_buy['amount'].sum() if len(big_buy) > 0 else 0
        
        # 所有买单（包括中单）
        all_buy = window_data[window_data['direction'] == 1]
        all_buy_amount = all_buy['amount'].sum() if len(all_buy) > 0 else 0
        
        # 2. 价格分析
        prices = window_data['成交价'].values
        avg_price = window_data['成交价'].mean()
        price_range = window_data['成交价'].max() - window_data['成交价'].min()
        price_volatility = (price_range / avg_price * 100) if avg_price > 0 else 0
        
        # 3. 判断横盘（主力控盘的标志）
        is_consolidation = price_volatility < 1.5  # 更严格的横盘标准
        
        # 4. 分析订单流的时序特征（关键！）
        # 检测"托-吸-托"的节奏
        control_pattern_score = 0
        
        if len(window_data) >= 10:
            # 将窗口分成3段，看是否有"托-吸-托"的节奏
            segment_size = len(window_data) // 3
            
            for i in range(3):
                start_idx = i * segment_size
                end_idx = (i + 1) * segment_size if i < 2 else len(window_data)
                segment = window_data.iloc[start_idx:end_idx]
                
                # 统计这一段的大单买入
                seg_big_buy = segment[
                    (segment['order_type'] == '大单') & 
                    (segment['direction'] == 1)
                ]
                
                if len(seg_big_buy) > 0:
                    control_pattern_score += 1
        
        # 5. 计算主力控盘强度
        # 不仅看金额，更要看"托"的动作是否明显
        control_strength = 0
        if small_sell_amount > 0:
            # 大单买入 vs 小单卖出的比例
            control_strength = (big_buy_amount / small_sell_amount) * 100
        
        # 6. 判断是否为主力对敲控盘模式
        is_market_maker_control = (
            big_buy_count >= 2 and  # 至少2次大单托价
            small_sell_count >= 3 and  # 有散户抛压
            control_strength >= 100 and  # 大单能托住抛压
            is_consolidation and  # 价格被控制住（横盘）
            control_pattern_score >= 2  # 有节奏性的托价动作
        )
        
        # 7. 分析价格支撑位（主力托价的位置）
        support_price = None
        if len(big_buy) > 0:
            # 大单买入的平均价格，就是主力的托价位
            support_price = big_buy['成交价'].mean()
        
        # 8. 计算抛压释放程度
        pressure_release_ratio = 0
        if all_buy_amount > 0:
            # 小单卖出被消化的比例
            pressure_release_ratio = (small_sell_amount / all_buy_amount) * 100
        
        return {
            'is_market_maker_control': is_market_maker_control,
            'control_strength': control_strength,
            'control_pattern_score': control_pattern_score,
            'small_sell_count': small_sell_count,
            'small_sell_amount': small_sell_amount,
            'big_buy_count': big_buy_count,
            'big_buy_amount': big_buy_amount,
            'all_buy_amount': all_buy_amount,
            'price_volatility': price_volatility,
            'is_consolidation': is_consolidation,
            'avg_price': avg_price,
            'support_price': support_price,
            'pressure_release_ratio': pressure_release_ratio,
            'price_range': price_range
        }
    
    def scan_market(self, stock_pool: List[str] = None) -> List[Dict]:
        """扫描市场寻找大单吃货信号"""
        
        if stock_pool is None:
            # 获取活跃股票池（这里简化处理）
            stock_pool = self._get_active_stocks()
        
        results = []
        
        for i, symbol in enumerate(stock_pool):
            print(f"扫描进度: {i+1}/{len(stock_pool)} - {symbol}")
            
            # 获取分笔数据
            tick_data = self.get_realtime_tick_data(symbol)
            
            if len(tick_data) == 0:
                continue
            
            # 分析吸货模式
            pattern = self.analyze_absorption_pattern(tick_data)
            
            if pattern and pattern['latest_pattern']['is_market_maker_control']:
                results.append(pattern)
                continuous = "持续控盘" if pattern['continuous_control'] else "单次"
                print(f"  ✓ 发现控盘信号: {pattern['name']} - 强度{pattern['latest_pattern']['control_strength']:.1f}% ({continuous})")
            
            # 避免请求过快
            time.sleep(0.5)
        
        return results
    
    def _get_active_stocks(self) -> List[str]:
        """获取活跃股票池"""
        try:
            # 获取涨幅榜前100
            df = ak.stock_zh_a_spot_em()
            df = df.sort_values('涨跌幅', ascending=False).head(100)
            return df['代码'].tolist()
        except:
            return []
    
    def generate_report(self, results: List[Dict], output_file: str = None):
        """生成扫描报告"""
        
        if not results:
            print("未发现主力控盘信号")
            return
        
        # 优先排序：持续控盘 > 控盘强度
        results.sort(key=lambda x: (
            x['continuous_control'],
            x['latest_pattern']['control_strength']
        ), reverse=True)
        
        # 生成报告
        report_data = []
        
        for r in results:
            latest = r['latest_pattern']
            report_data.append({
                '代码': r['symbol'],
                '名称': r['name'],
                '控盘强度': f"{latest['control_strength']:.1f}%",
                '控盘节奏': f"{latest['control_pattern_score']}/3",
                '托价次数': latest['big_buy_count'],
                '托价金额': f"{latest['big_buy_amount']/10000:.2f}万",
                '抛压释放': f"{latest['pressure_release_ratio']:.1f}%",
                '托价位': f"{latest['support_price']:.2f}" if latest['support_price'] else '-',
                '价格波动': f"{latest['price_volatility']:.2f}%",
                '横盘控制': '是' if latest['is_consolidation'] else '否',
                '持续控盘': '是' if r['continuous_control'] else '否',
                '控盘次数': r['pattern_count'],
                '最新时间': r['latest_pattern']['time']
            })
        
        df_report = pd.DataFrame(report_data)
        
        # 输出到Excel
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f'主力控盘扫描_{timestamp}.xlsx'
        
        df_report.to_excel(output_file, index=False, engine='openpyxl')
        print(f"\n报告已生成: {output_file}")
        print(f"共发现 {len(results)} 只股票有主力控盘信号")
        
        # 打印前10名
        print("\n【控盘强度TOP10】")
        print(df_report.head(10).to_string(index=False))
        
        return df_report


def main():
    """主函数"""
    print("=" * 60)
    print("主力对敲控盘扫描系统 - 识别建仓语言")
    print("=" * 60)
    print("\n策略逻辑：")
    print("1. 大单托价（主力主动买入，托住股价）")
    print("2. 释放抛压（让散户卖单在托价位成交）")
    print("3. 横盘吸筹（价格被控制，持续吸筹）")
    print("4. 再次托价（确认主力还在控盘）")
    print("\n这是主力通过对敲手法完成建仓的过程！")
    print("=" * 60)
    
    scanner = MarketMakerControlScanner()
    
    # 可以指定股票池，或者自动获取活跃股票
    # stock_pool = ['000001', '600000', '000002']  # 示例
    stock_pool = None  # 自动获取
    
    print("\n开始扫描...")
    results = scanner.scan_market(stock_pool)
    
    print("\n生成报告...")
    scanner.generate_report(results)
    
    print("\n扫描完成！")


if __name__ == '__main__':
    main()
