#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
实时监测大单吃货 - 盯盘工具
持续监测指定股票的大单吸货行为
"""

import akshare as ak
import pandas as pd
from datetime import datetime
import time
from collections import deque
import os

class RealtimeAbsorptionMonitor:
    """实时大单吃货监测器"""
    
    def __init__(self, symbols: list, alert_threshold: float = 150.0):
        """
        初始化监测器
        
        Args:
            symbols: 要监测的股票代码列表
            alert_threshold: 吸货强度预警阈值（%）
        """
        self.symbols = symbols
        self.alert_threshold = alert_threshold
        self.history = {symbol: deque(maxlen=100) for symbol in symbols}
        self.last_alert_time = {}
        
    def get_latest_ticks(self, symbol: str, n: int = 50) -> pd.DataFrame:
        """获取最新N笔成交"""
        try:
            df = ak.stock_zh_a_tick_tx(symbol=symbol)
            if df is None or len(df) == 0:
                return pd.DataFrame()
            
            # 只取最新N笔
            df = df.tail(n).copy()
            
            # 计算金额
            df['amount'] = df['成交量'] * df['成交价']
            
            # 判断方向
            df['direction'] = df['性质'].map({
                '买盘': 1,
                '卖盘': -1,
                '中性盘': 0
            })
            
            return df
            
        except Exception as e:
            print(f"获取{symbol}数据失败: {e}")
            return pd.DataFrame()
    
    def analyze_absorption(self, df: pd.DataFrame) -> dict:
        """分析当前吸货情况"""
        if len(df) == 0:
            return None
        
        # 定义大单和小单
        big_threshold = 50000
        small_threshold = 10000
        
        # 小单卖出
        small_sell = df[
            (df['amount'] < small_threshold) & 
            (df['direction'] == -1)
        ]
        
        # 大单买入
        big_buy = df[
            (df['amount'] >= big_threshold) & 
            (df['direction'] == 1)
        ]
        
        # 中单买入
        mid_buy = df[
            (df['amount'] >= small_threshold) &
            (df['amount'] < big_threshold) &
            (df['direction'] == 1)
        ]
        
        # 统计
        small_sell_count = len(small_sell)
        small_sell_amount = small_sell['amount'].sum()
        
        big_buy_count = len(big_buy)
        big_buy_amount = big_buy['amount'].sum()
        
        mid_buy_count = len(mid_buy)
        mid_buy_amount = mid_buy['amount'].sum()
        
        total_buy_amount = big_buy_amount + mid_buy_amount
        
        # 价格分析
        current_price = df.iloc[-1]['成交价']
        price_std = df['成交价'].std()
        price_range = df['成交价'].max() - df['成交价'].min()
        avg_price = df['成交价'].mean()
        
        # 横盘判断
        volatility = (price_range / avg_price * 100) if avg_price > 0 else 0
        is_consolidation = volatility < 1.5
        
        # 吸货强度
        absorption_strength = 0
        if small_sell_amount > 0:
            absorption_strength = (total_buy_amount / small_sell_amount) * 100
        
        # 判断是否为吸货信号
        is_absorption = (
            small_sell_count >= 3 and
            big_buy_count >= 1 and
            absorption_strength >= 100 and
            is_consolidation
        )
        
        return {
            'is_absorption': is_absorption,
            'absorption_strength': absorption_strength,
            'small_sell_count': small_sell_count,
            'small_sell_amount': small_sell_amount,
            'big_buy_count': big_buy_count,
            'big_buy_amount': big_buy_amount,
            'mid_buy_count': mid_buy_count,
            'mid_buy_amount': mid_buy_amount,
            'current_price': current_price,
            'volatility': volatility,
            'is_consolidation': is_consolidation,
            'avg_price': avg_price
        }
    
    def monitor_once(self):
        """执行一次监测"""
        results = []
        
        for symbol in self.symbols:
            # 获取最新数据
            df = self.get_latest_ticks(symbol)
            
            if len(df) == 0:
                continue
            
            # 分析吸货
            analysis = self.analyze_absorption(df)
            
            if analysis is None:
                continue
            
            # 获取股票名称
            name = df.iloc[0].get('名称', symbol)
            
            # 记录历史
            self.history[symbol].append({
                'time': datetime.now(),
                'analysis': analysis
            })
            
            # 判断是否需要预警
            if analysis['is_absorption'] and analysis['absorption_strength'] >= self.alert_threshold:
                # 避免频繁预警（5分钟内只预警一次）
                last_alert = self.last_alert_time.get(symbol, datetime.min)
                if (datetime.now() - last_alert).seconds > 300:
                    self.alert(symbol, name, analysis)
                    self.last_alert_time[symbol] = datetime.now()
            
            results.append({
                'symbol': symbol,
                'name': name,
                'analysis': analysis
            })
        
        return results
    
    def alert(self, symbol: str, name: str, analysis: dict):
        """发出预警"""
        print("\n" + "=" * 60)
        print(f"🔥 【吸货预警】 {name}({symbol})")
        print("=" * 60)
        print(f"吸货强度: {analysis['absorption_strength']:.1f}%")
        print(f"当前价格: {analysis['current_price']:.2f}")
        print(f"大单买入: {analysis['big_buy_count']}笔 / {analysis['big_buy_amount']/10000:.2f}万")
        print(f"小单卖出: {analysis['small_sell_count']}笔 / {analysis['small_sell_amount']/10000:.2f}万")
        print(f"价格波动: {analysis['volatility']:.2f}%")
        print(f"横盘状态: {'是' if analysis['is_consolidation'] else '否'}")
        print("=" * 60)
        
        # 可以在这里添加声音提醒、微信通知等
        # os.system('echo \a')  # 系统提示音
    
    def display_status(self, results: list):
        """显示当前状态"""
        os.system('cls' if os.name == 'nt' else 'clear')
        
        print("=" * 80)
        print(f"大单吃货实时监测 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        if not results:
            print("暂无数据")
            return
        
        # 表头
        print(f"{'代码':<10} {'名称':<10} {'当前价':<8} {'吸货强度':<10} {'大单':<8} {'小单':<8} {'横盘':<6} {'状态'}")
        print("-" * 80)
        
        for r in results:
            symbol = r['symbol']
            name = r['name']
            a = r['analysis']
            
            status = "🔥吸货中" if a['is_absorption'] else "观察中"
            consolidation = "是" if a['is_consolidation'] else "否"
            
            print(f"{symbol:<10} {name:<10} {a['current_price']:<8.2f} "
                  f"{a['absorption_strength']:<10.1f} "
                  f"{a['big_buy_count']:<8} "
                  f"{a['small_sell_count']:<8} "
                  f"{consolidation:<6} "
                  f"{status}")
        
        print("=" * 80)
        print(f"预警阈值: {self.alert_threshold}% | 刷新间隔: 10秒 | 按Ctrl+C退出")
    
    def run(self, interval: int = 10):
        """持续运行监测"""
        print("启动实时监测...")
        print(f"监测股票: {', '.join(self.symbols)}")
        print(f"预警阈值: {self.alert_threshold}%")
        print(f"刷新间隔: {interval}秒")
        print("\n按Ctrl+C停止监测\n")
        
        try:
            while True:
                results = self.monitor_once()
                self.display_status(results)
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n\n监测已停止")
            self.save_history()
    
    def save_history(self):
        """保存监测历史"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'吸货监测历史_{timestamp}.txt'
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("大单吸货监测历史\n")
            f.write("=" * 60 + "\n\n")
            
            for symbol, records in self.history.items():
                if not records:
                    continue
                
                f.write(f"\n{symbol}:\n")
                f.write("-" * 60 + "\n")
                
                for record in records:
                    time_str = record['time'].strftime('%H:%M:%S')
                    a = record['analysis']
                    
                    if a['is_absorption']:
                        f.write(f"{time_str} - 吸货强度: {a['absorption_strength']:.1f}% "
                               f"价格: {a['current_price']:.2f}\n")
        
        print(f"历史记录已保存: {filename}")


def main():
    """主函数"""
    print("=" * 60)
    print("实时大单吃货监测系统")
    print("=" * 60)
    
    # 配置要监测的股票（可以从文件读取或手动输入）
    symbols = [
        '000001',  # 平安银行
        '600000',  # 浦发银行
        '000002',  # 万科A
        # 添加更多股票...
    ]
    
    # 也可以从持仓文件读取
    try:
        with open('my_holdings.txt', 'r', encoding='utf-8') as f:
            holdings = [line.strip() for line in f if line.strip()]
            if holdings:
                symbols = holdings
                print(f"从持仓文件读取到 {len(symbols)} 只股票")
    except:
        pass
    
    # 创建监测器
    monitor = RealtimeAbsorptionMonitor(
        symbols=symbols,
        alert_threshold=150.0  # 吸货强度超过150%时预警
    )
    
    # 开始监测
    monitor.run(interval=10)


if __name__ == '__main__':
    main()
