#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
主力对敲语言识别器
专门识别主力通过对敲手法控盘的"语言"

核心理解：
1. 大单托价 = 主力说"这个价位我要"
2. 释放抛压 = 让散户卖单在托价位成交
3. 横盘控制 = 主力刻意维持价格稳定
4. 再次托价 = 主力说"我还要，继续建仓"

这不是自然的市场行为，而是主力的刻意操作！
"""

import akshare as ak
import pandas as pd
from datetime import datetime
import time
from typing import Dict, List
import numpy as np

class MarketMakerLanguageDetector:
    """主力对敲语言识别器"""
    
    def __init__(self):
        self.big_order_threshold = 50000
        self.small_order_threshold = 10000
        
    def get_tick_data(self, symbol: str) -> pd.DataFrame:
        """获取分笔数据"""
        try:
            df = ak.stock_zh_a_tick_tx(symbol=symbol)
            if df is None or len(df) == 0:
                return pd.DataFrame()
            
            df['amount'] = df['成交量'] * df['成交价']
            df['direction'] = df['性质'].map({'买盘': 1, '卖盘': -1, '中性盘': 0})
            df['time'] = pd.to_datetime(df['成交时间'])
            
            # 分类订单
            df['order_size'] = pd.cut(
                df['amount'],
                bins=[0, self.small_order_threshold, self.big_order_threshold, float('inf')],
                labels=['小单', '中单', '大单']
            )
            
            return df.sort_values('time')
            
        except Exception as e:
            print(f"获取{symbol}数据失败: {e}")
            return pd.DataFrame()
    
    def detect_support_action(self, df: pd.DataFrame, window_minutes: int = 3) -> List[Dict]:
        """
        检测"托价"动作
        
        托价特征：
        1. 大单主动买入
        2. 价格被托住（不再下跌）
        3. 成交价格集中在某个区间
        """
        if len(df) == 0:
            return []
        
        df = df.set_index('time')
        windows = df.resample(f'{window_minutes}T')
        
        support_actions = []
        
        for window_time, window_data in windows:
            if len(window_data) < 5:
                continue
            
            # 找大单买入
            big_buys = window_data[
                (window_data['order_size'] == '大单') & 
                (window_data['direction'] == 1)
            ]
            
            if len(big_buys) == 0:
                continue
            
            # 分析托价效果
            prices = window_data['成交价'].values
            big_buy_prices = big_buys['成交价'].values
            
            # 托价位（大单买入的平均价格）
            support_price = big_buy_prices.mean()
            
            # 价格是否被托住（后续价格不低于托价位）
            prices_after_support = prices[len(prices)//2:]  # 后半段价格
            is_supported = np.mean(prices_after_support) >= support_price * 0.995
            
            # 价格集中度（横盘特征）
            price_std = prices.std()
            price_concentration = 1 - (price_std / support_price)
            
            if is_supported and price_concentration > 0.98:  # 价格波动<2%
                support_actions.append({
                    'time': window_time,
                    'support_price': support_price,
                    'big_buy_count': len(big_buys),
                    'big_buy_amount': big_buys['amount'].sum(),
                    'price_concentration': price_concentration,
                    'is_supported': is_supported
                })
        
        return support_actions
    
    def detect_pressure_release(self, df: pd.DataFrame, support_price: float) -> Dict:
        """
        检测"释放抛压"
        
        抛压释放特征：
        1. 小单卖出在托价位附近成交
        2. 卖单被大单或中单接住
        3. 价格没有跌破托价位
        """
        # 找托价位附近的交易（±0.5%）
        near_support = df[
            (df['成交价'] >= support_price * 0.995) &
            (df['成交价'] <= support_price * 1.005)
        ]
        
        if len(near_support) == 0:
            return None
        
        # 统计卖单（抛压）
        sell_orders = near_support[near_support['direction'] == -1]
        small_sells = sell_orders[sell_orders['order_size'] == '小单']
        
        # 统计买单（接盘）
        buy_orders = near_support[near_support['direction'] == 1]
        big_mid_buys = buy_orders[buy_orders['order_size'].isin(['大单', '中单'])]
        
        if len(small_sells) == 0:
            return None
        
        # 计算抛压释放程度
        sell_amount = small_sells['amount'].sum()
        buy_amount = big_mid_buys['amount'].sum()
        
        release_ratio = (buy_amount / sell_amount) if sell_amount > 0 else 0
        
        return {
            'small_sell_count': len(small_sells),
            'small_sell_amount': sell_amount,
            'big_mid_buy_count': len(big_mid_buys),
            'big_mid_buy_amount': buy_amount,
            'release_ratio': release_ratio,
            'is_fully_absorbed': release_ratio >= 1.0
        }
    
    def detect_control_rhythm(self, support_actions: List[Dict]) -> Dict:
        """
        检测"控盘节奏"
        
        节奏特征：
        1. 多次托价动作（不是一次性）
        2. 托价位逐步抬高（建仓完成后准备拉升）
        3. 时间间隔规律（3-5分钟一次）
        """
        if len(support_actions) < 2:
            return {
                'has_rhythm': False,
                'rhythm_score': 0
            }
        
        # 分析托价位的变化
        support_prices = [a['support_price'] for a in support_actions]
        price_trend = np.polyfit(range(len(support_prices)), support_prices, 1)[0]
        
        # 分析时间间隔
        times = [a['time'] for a in support_actions]
        intervals = [(times[i+1] - times[i]).seconds / 60 for i in range(len(times)-1)]
        avg_interval = np.mean(intervals) if intervals else 0
        
        # 节奏评分
        rhythm_score = 0
        
        # 1. 多次托价（+30分）
        if len(support_actions) >= 3:
            rhythm_score += 30
        elif len(support_actions) >= 2:
            rhythm_score += 20
        
        # 2. 托价位逐步抬高（+40分）
        if price_trend > 0:
            rhythm_score += 40
        
        # 3. 时间间隔规律（+30分）
        if 2 <= avg_interval <= 6:  # 2-6分钟间隔
            rhythm_score += 30
        
        has_rhythm = rhythm_score >= 60
        
        return {
            'has_rhythm': has_rhythm,
            'rhythm_score': rhythm_score,
            'support_count': len(support_actions),
            'price_trend': 'up' if price_trend > 0 else 'flat',
            'avg_interval_minutes': avg_interval
        }
    
    def detect_closing_pullback(self, df: pd.DataFrame, support_actions: List[Dict]) -> Dict:
        """
        检测尾盘回落（重要信号！）
        
        尾盘回落特征：
        1. 盘中有托价动作（主力在吸）
        2. 尾盘价格回落（主力洗盘）
        3. 但不破托价位（主力没走）
        4. 成交量萎缩（不是恐慌抛售）
        
        为什么尾盘回落是好事？
        - 洗盘：吓出短线客
        - 隐蔽：不想暴露意图，避免上龙虎榜
        - 降成本：第二天可以更低位置继续吸
        """
        if len(support_actions) == 0:
            return None
        
        # 获取最高托价位
        max_support_price = max([a['support_price'] for a in support_actions])
        
        # 分析尾盘（最后30分钟）
        df = df.sort_values('time')
        last_time = df.iloc[-1]['time']
        closing_period_start = last_time - pd.Timedelta(minutes=30)
        
        closing_df = df[df['time'] >= closing_period_start]
        
        if len(closing_df) < 10:
            return None
        
        # 尾盘价格走势
        closing_prices = closing_df['成交价'].values
        closing_high = closing_prices.max()
        closing_low = closing_prices.min()
        current_price = closing_prices[-1]
        
        # 尾盘成交量
        closing_volume = closing_df['成交量'].sum()
        total_volume = df['成交量'].sum()
        closing_volume_ratio = closing_volume / total_volume if total_volume > 0 else 0
        
        # 判断是否尾盘回落
        is_pullback = (
            closing_high > max_support_price * 1.005 and  # 盘中曾经拉高
            current_price < closing_high * 0.995 and  # 尾盘回落
            current_price >= max_support_price * 0.98  # 但不破托价位（关键！）
        )
        
        # 判断是否健康回落（成交量萎缩）
        is_healthy = closing_volume_ratio < 0.25  # 尾盘成交量<25%
        
        # 计算回落幅度
        pullback_ratio = (closing_high - current_price) / closing_high * 100 if closing_high > 0 else 0
        
        # 相对托价位的位置
        position_vs_support = (current_price - max_support_price) / max_support_price * 100
        
        return {
            'is_pullback': is_pullback,
            'is_healthy': is_healthy,
            'is_good_signal': is_pullback and is_healthy,  # 健康的尾盘回落 = 好信号
            'pullback_ratio': pullback_ratio,
            'position_vs_support': position_vs_support,
            'closing_volume_ratio': closing_volume_ratio,
            'max_support_price': max_support_price,
            'closing_high': closing_high,
            'current_price': current_price
        }
    
    def analyze_stock(self, symbol: str, name: str = None) -> Dict:
        """分析单只股票的主力对敲语言"""
        
        print(f"\n分析 {name or symbol}...")
        
        # 获取数据
        df = self.get_tick_data(symbol)
        if len(df) == 0:
            return None
        
        # 1. 检测托价动作
        support_actions = self.detect_support_action(df)
        
        if not support_actions:
            print("  未发现托价动作")
            return None
        
        print(f"  发现 {len(support_actions)} 次托价动作")
        
        # 2. 检测抛压释放（针对最近的托价位）
        latest_support = support_actions[-1]
        pressure_release = self.detect_pressure_release(df, latest_support['support_price'])
        
        if pressure_release:
            print(f"  抛压释放: {pressure_release['release_ratio']:.1f}倍")
        
        # 3. 检测控盘节奏
        rhythm = self.detect_control_rhythm(support_actions)
        
        if rhythm['has_rhythm']:
            print(f"  ✓ 发现控盘节奏! 评分: {rhythm['rhythm_score']}/100")
        
        # 4. 检测尾盘回落（重要！）
        closing_pullback = self.detect_closing_pullback(df, support_actions)
        
        if closing_pullback and closing_pullback['is_good_signal']:
            print(f"  🌟 尾盘健康回落! 回落{closing_pullback['pullback_ratio']:.2f}% (好信号)")
        
        # 5. 综合判断
        is_market_maker_control = (
            len(support_actions) >= 2 and  # 至少2次托价
            rhythm['has_rhythm'] and  # 有节奏
            (pressure_release and pressure_release['is_fully_absorbed'])  # 抛压被吸收
        )
        
        # 6. 计算当前价格相对托价位的位置
        current_price = df.iloc[-1]['成交价']
        latest_support_price = latest_support['support_price']
        price_position = (current_price - latest_support_price) / latest_support_price * 100
        
        # 7. 综合评分（加入尾盘回落因素）
        total_score = rhythm['rhythm_score']
        if closing_pullback and closing_pullback['is_good_signal']:
            total_score += 20  # 健康的尾盘回落加20分
        
        return {
            'symbol': symbol,
            'name': name or symbol,
            'is_market_maker_control': is_market_maker_control,
            'support_actions': support_actions,
            'latest_support_price': latest_support_price,
            'current_price': current_price,
            'price_position': price_position,
            'pressure_release': pressure_release,
            'rhythm': rhythm,
            'closing_pullback': closing_pullback,
            'control_strength': total_score  # 包含尾盘回落的综合评分
        }
    
    def scan_market(self, stock_pool: List[str] = None) -> List[Dict]:
        """扫描市场"""
        
        if stock_pool is None:
            # 获取活跃股票
            try:
                df = ak.stock_zh_a_spot_em()
                df = df.sort_values('涨跌幅', ascending=False).head(100)
                stock_pool = df['代码'].tolist()
            except:
                return []
        
        results = []
        
        for i, symbol in enumerate(stock_pool):
            print(f"\n进度: {i+1}/{len(stock_pool)}")
            
            result = self.analyze_stock(symbol)
            
            if result and result['is_market_maker_control']:
                results.append(result)
                print(f"  🔥 确认主力控盘!")
            
            time.sleep(0.5)
        
        return results
    
    def generate_report(self, results: List[Dict], output_file: str = None):
        """生成报告"""
        
        if not results:
            print("\n未发现主力对敲控盘信号")
            return
        
        # 按控盘强度排序
        results.sort(key=lambda x: x['control_strength'], reverse=True)
        
        report_data = []
        
        for r in results:
            rhythm = r['rhythm']
            pressure = r['pressure_release']
            closing = r.get('closing_pullback')
            
            # 尾盘回落信息
            closing_info = '-'
            if closing and closing['is_pullback']:
                if closing['is_good_signal']:
                    closing_info = f"✓ 健康回落{closing['pullback_ratio']:.1f}%"
                else:
                    closing_info = f"回落{closing['pullback_ratio']:.1f}%"
            
            report_data.append({
                '代码': r['symbol'],
                '名称': r['name'],
                '控盘评分': f"{r['control_strength']}/120",  # 满分120（含尾盘加分）
                '托价次数': rhythm['support_count'],
                '托价趋势': '抬高' if rhythm['price_trend'] == 'up' else '平稳',
                '托价间隔': f"{rhythm['avg_interval_minutes']:.1f}分钟",
                '最新托价': f"{r['latest_support_price']:.2f}",
                '当前价格': f"{r['current_price']:.2f}",
                '价格位置': f"{r['price_position']:+.2f}%",
                '尾盘回落': closing_info,
                '抛压释放': f"{pressure['release_ratio']:.1f}倍" if pressure else '-',
                '完全吸收': '是' if pressure and pressure['is_fully_absorbed'] else '否'
            })
        
        df_report = pd.DataFrame(report_data)
        
        if output_file is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f'主力对敲语言_{timestamp}.xlsx'
        
        df_report.to_excel(output_file, index=False, engine='openpyxl')
        
        print(f"\n{'='*60}")
        print(f"报告已生成: {output_file}")
        print(f"共发现 {len(results)} 只股票有主力对敲控盘信号")
        print(f"{'='*60}")
        
        print("\n【控盘强度TOP10】")
        print(df_report.head(10).to_string(index=False))
        
        return df_report


def main():
    """主函数"""
    print("=" * 70)
    print("主力对敲语言识别系统")
    print("=" * 70)
    print("\n什么是对敲语言？")
    print("-" * 70)
    print("主力通过大单托价的动作，向市场传递信号：")
    print("  1. 大单托价 → '这个价位我要'")
    print("  2. 释放抛压 → '散户的卖单我全接'")
    print("  3. 横盘控制 → '价格我说了算'")
    print("  4. 再次托价 → '我还要，继续建仓'")
    print("  5. 尾盘回落 → '洗盘+降成本，明天继续吸' (好信号!)")
    print("\n这不是自然的市场行为，而是主力的刻意操作！")
    print("识别这种语言，就能跟上主力的节奏。")
    print("\n🌟 特别关注：尾盘回落但不破托价位 = 主力洗盘 = 好信号！")
    print("=" * 70)
    
    detector = MarketMakerLanguageDetector()
    
    print("\n开始扫描市场...")
    results = detector.scan_market()
    
    print("\n生成报告...")
    detector.generate_report(results)
    
    print("\n扫描完成！")


if __name__ == '__main__':
    main()
