"""
分时横盘托单监测
监测横盘个股在跌破支撑时是否有大单护盘
"""
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime
import time
import os

class SupportDefenseMonitor:
    def __init__(self, stock_codes, check_interval=5):
        """
        初始化托单监测器
        :param stock_codes: 股票代码列表
        :param check_interval: 检查间隔（秒）
        """
        self.stock_codes = stock_codes
        self.check_interval = check_interval
        self.history_data = {}  # 存储历史分时数据
        
    def get_minute_data(self, stock_code):
        """获取分时数据"""
        try:
            symbol = f"sh{stock_code}" if stock_code.startswith('6') else f"sz{stock_code}"
            df = ak.stock_zh_a_hist_min_em(symbol=stock_code, period='1', adjust='')
            
            if df.empty:
                return None
            
            # 只取今天的数据
            df['时间'] = pd.to_datetime(df['时间'])
            today = datetime.now().date()
            df = df[df['时间'].dt.date == today]
            
            return df
        except Exception as e:
            print(f"获取 {stock_code} 分时数据失败: {e}")
            return None
    
    def get_tick_data(self, stock_code):
        """获取逐笔成交数据"""
        try:
            symbol = f"sh{stock_code}" if stock_code.startswith('6') else f"sz{stock_code}"
            df = ak.stock_zh_a_tick_tx_js(symbol=symbol)
            
            if df.empty:
                return None
            
            df['成交额(万)'] = df['成交价'] * df['成交量'] / 10000
            return df
        except Exception as e:
            return None
    
    def is_sideways(self, df, window=10, threshold=1.5):
        """
        判断是否横盘
        :param df: 分时数据
        :param window: 观察窗口（分钟）
        :param threshold: 波动阈值（%）
        """
        if len(df) < window:
            return False, None
        
        recent = df.tail(window)
        high = recent['最高'].max()
        low = recent['最低'].min()
        avg = recent['收盘'].mean()
        
        # 计算波动幅度
        volatility = (high - low) / avg * 100
        
        # 横盘：波动小于阈值
        is_sideways = volatility < threshold
        
        return is_sideways, {
            'high': high,
            'low': low,
            'avg': avg,
            'volatility': volatility,
            'support': low  # 支撑位
        }
    
    def detect_breakdown_defense(self, stock_code, minute_df, tick_df):
        """
        检测跌破支撑后的大单护盘
        """
        if minute_df is None or tick_df is None or len(minute_df) < 10:
            return None
        
        # 1. 判断是否横盘
        is_side, side_info = self.is_sideways(minute_df, window=10, threshold=1.5)
        
        if not is_side:
            return None
        
        # 2. 获取当前价格和支撑位
        current_price = minute_df['收盘'].iloc[-1]
        support = side_info['support']
        
        # 3. 判断是否接近或跌破支撑
        distance_to_support = (current_price - support) / support * 100
        
        # 如果距离支撑位在 -0.3% 到 0.1% 之间，认为是关键位置
        if not (-0.3 <= distance_to_support <= 0.1):
            return None
        
        # 4. 检查最近的大单情况
        recent_ticks = tick_df.head(20)  # 最近20笔
        
        # 计算大单（≥50万）
        big_orders = recent_ticks[recent_ticks['成交额(万)'] >= 50]
        
        if big_orders.empty:
            return None
        
        # 5. 分析大单方向
        buy_big = big_orders[big_orders['性质'] == '买盘']
        sell_big = big_orders[big_orders['性质'] == '卖盘']
        
        buy_amount = buy_big['成交额(万)'].sum() if not buy_big.empty else 0
        sell_amount = sell_big['成交额(万)'].sum() if not sell_big.empty else 0
        
        # 6. 判断是否有护盘迹象
        # 条件：接近支撑 + 买入大单明显多于卖出大单
        if buy_amount > sell_amount * 1.5 and buy_amount > 100:
            return {
                'type': '托单护盘',
                'support': support,
                'current_price': current_price,
                'distance': distance_to_support,
                'buy_big_amount': buy_amount,
                'sell_big_amount': sell_amount,
                'buy_big_count': len(buy_big),
                'sell_big_count': len(sell_big),
                'side_info': side_info,
                'recent_ticks': recent_ticks.head(10)
            }
        
        # 7. 判断是否要跌破
        elif sell_amount > buy_amount * 1.5 and sell_amount > 100:
            return {
                'type': '即将跌破',
                'support': support,
                'current_price': current_price,
                'distance': distance_to_support,
                'buy_big_amount': buy_amount,
                'sell_big_amount': sell_amount,
                'buy_big_count': len(buy_big),
                'sell_big_count': len(sell_big),
                'side_info': side_info,
                'recent_ticks': recent_ticks.head(10)
            }
        
        return None
    
    def analyze_stock(self, stock_code):
        """分析单只股票"""
        # 获取数据
        minute_df = self.get_minute_data(stock_code)
        tick_df = self.get_tick_data(stock_code)
        
        if minute_df is None:
            return None
        
        # 获取基本信息
        try:
            spot_df = ak.stock_zh_a_spot_em()
            stock_info = spot_df[spot_df['代码'] == stock_code]
            
            if stock_info.empty:
                return None
            
            name = stock_info['名称'].values[0]
            price = stock_info['最新价'].values[0]
            change = stock_info['涨跌幅'].values[0]
        except:
            name = stock_code
            price = minute_df['收盘'].iloc[-1]
            change = 0
        
        # 检测托单
        signal = self.detect_breakdown_defense(stock_code, minute_df, tick_df)
        
        if signal is None:
            return None
        
        return {
            'code': stock_code,
            'name': name,
            'price': price,
            'change': change,
            'signal': signal
        }
    
    def print_signal(self, result):
        """打印信号"""
        if result is None:
            return
        
        signal = result['signal']
        
        print(f"\n{'='*80}")
        if signal['type'] == '托单护盘':
            print(f"🛡️  【托单护盘】{result['name']} ({result['code']})")
        else:
            print(f"⚠️  【即将跌破】{result['name']} ({result['code']})")
        print(f"{'='*80}")
        
        print(f"\n📊 基本信息:")
        print(f"  当前价: {result['price']:.2f}  涨跌幅: {result['change']:+.2f}%")
        
        print(f"\n📈 横盘信息:")
        side_info = signal['side_info']
        print(f"  横盘区间: {side_info['low']:.2f} - {side_info['high']:.2f}")
        print(f"  波动幅度: {side_info['volatility']:.2f}%")
        print(f"  支撑位: {signal['support']:.2f}")
        print(f"  距支撑: {signal['distance']:+.2f}%")
        
        print(f"\n💰 大单情况:")
        print(f"  买入大单: {signal['buy_big_count']}笔  {signal['buy_big_amount']:.2f}万")
        print(f"  卖出大单: {signal['sell_big_count']}笔  {signal['sell_big_amount']:.2f}万")
        
        if signal['type'] == '托单护盘':
            print(f"  ✅ 买入大单占优，有护盘迹象")
        else:
            print(f"  ❌ 卖出大单占优，可能跌破")
        
        print(f"\n🔍 最近成交:")
        for idx, row in signal['recent_ticks'].iterrows():
            order_type = "🔴买" if row['性质'] == '买盘' else "🟢卖" if row['性质'] == '卖盘' else "⚪中"
            amount = row['成交额(万)']
            
            if amount >= 100:
                flag = "💎💎💎"
            elif amount >= 50:
                flag = "💎💎"
            elif amount >= 20:
                flag = "💎"
            else:
                flag = "   "
            
            print(f"  {flag} {row['成交时间']} {order_type} {row['成交价']:.2f} × {row['成交量']:>6} = {amount:>8.2f}万")
    
    def monitor_loop(self):
        """循环监测"""
        print(f"\n{'#'*80}")
        print(f"分时横盘托单监测系统")
        print(f"{'#'*80}")
        print(f"监测股票: {', '.join(self.stock_codes)}")
        print(f"检查间隔: {self.check_interval}秒")
        print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'#'*80}\n")
        
        signal_count = 0
        
        try:
            while True:
                current_time = datetime.now()
                
                # 只在交易时间运行
                if not (9 <= current_time.hour < 15):
                    print(f"[{current_time.strftime('%H:%M:%S')}] 非交易时间，等待中...")
                    time.sleep(60)
                    continue
                
                print(f"\n[{current_time.strftime('%H:%M:%S')}] 扫描中...")
                
                for stock_code in self.stock_codes:
                    try:
                        result = self.analyze_stock(stock_code)
                        
                        if result:
                            signal_count += 1
                            self.print_signal(result)
                            
                            # 发出提示音（Windows）
                            try:
                                import winsound
                                winsound.Beep(1000, 500)
                            except:
                                pass
                        
                    except Exception as e:
                        print(f"  {stock_code}: 分析出错 - {e}")
                
                if signal_count == 0:
                    print(f"  暂无信号")
                
                print(f"\n等待 {self.check_interval} 秒... (Ctrl+C 退出)")
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            print(f"\n\n监测已停止，共发现 {signal_count} 个信号")


def main():
    """主函数"""
    print("分时横盘托单监测")
    print("="*80)
    print("功能：监测横盘个股在跌破支撑时是否有大单护盘")
    print("="*80)
    
    # 输入股票代码
    stock_input = input("\n请输入股票代码（多个用逗号分隔）: ").strip()
    
    if not stock_input:
        # 尝试读取持仓
        try:
            with open('my_holdings.txt', 'r', encoding='utf-8') as f:
                stock_codes = [line.strip() for line in f if line.strip()]
            print(f"已加载持仓股票: {', '.join(stock_codes)}")
        except:
            print("未找到持仓文件，请输入股票代码")
            return
    else:
        stock_codes = [code.strip() for code in stock_input.split(',')]
    
    # 输入检查间隔
    interval_input = input("请输入检查间隔（秒，默认5）: ").strip()
    interval = int(interval_input) if interval_input else 5
    
    # 创建监测器
    monitor = SupportDefenseMonitor(stock_codes, interval)
    
    # 开始监测
    monitor.monitor_loop()


if __name__ == "__main__":
    main()
