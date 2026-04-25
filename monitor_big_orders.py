"""
盘口大单监测工具
实时监控股票的大单流入流出情况
"""
import akshare as ak
import pandas as pd
import time
from datetime import datetime
import os

class BigOrderMonitor:
    def __init__(self, stock_codes, big_order_threshold=100):
        """
        初始化大单监测器
        :param stock_codes: 要监测的股票代码列表，如 ['600519', '000001']
        :param big_order_threshold: 大单阈值（万元），默认100万
        """
        self.stock_codes = stock_codes
        self.big_order_threshold = big_order_threshold
        self.last_data = {}
        
    def get_realtime_data(self, stock_code):
        """获取实时行情数据"""
        try:
            # 获取实时行情
            df = ak.stock_zh_a_spot_em()
            stock_data = df[df['代码'] == stock_code]
            
            if stock_data.empty:
                return None
                
            return {
                '代码': stock_code,
                '名称': stock_data['名称'].values[0],
                '最新价': stock_data['最新价'].values[0],
                '涨跌幅': stock_data['涨跌幅'].values[0],
                '成交量': stock_data['成交量'].values[0],
                '成交额': stock_data['成交额'].values[0],
                '换手率': stock_data['换手率'].values[0],
            }
        except Exception as e:
            print(f"获取 {stock_code} 实时数据失败: {e}")
            return None
    
    def get_money_flow(self, stock_code):
        """获取资金流向数据"""
        try:
            # 获取个股资金流
            df = ak.stock_individual_fund_flow_rank(symbol="即时")
            stock_flow = df[df['代码'] == stock_code]
            
            if stock_flow.empty:
                return None
                
            return {
                '主力净流入': stock_flow['主力净流入-净额'].values[0] if '主力净流入-净额' in stock_flow.columns else 0,
                '主力净占比': stock_flow['主力净流入-净占比'].values[0] if '主力净流入-净占比' in stock_flow.columns else 0,
                '超大单净流入': stock_flow['超大单净流入-净额'].values[0] if '超大单净流入-净额' in stock_flow.columns else 0,
                '超大单净占比': stock_flow['超大单净流入-净占比'].values[0] if '超大单净流入-净占比' in stock_flow.columns else 0,
                '大单净流入': stock_flow['大单净流入-净额'].values[0] if '大单净流入-净额' in stock_flow.columns else 0,
                '大单净占比': stock_flow['大单净流入-净占比'].values[0] if '大单净流入-净占比' in stock_flow.columns else 0,
            }
        except Exception as e:
            print(f"获取 {stock_code} 资金流向失败: {e}")
            return None
    
    def get_tick_data(self, stock_code):
        """获取分时成交数据（最近的逐笔交易）"""
        try:
            # 获取分时成交
            symbol = f"sh{stock_code}" if stock_code.startswith('6') else f"sz{stock_code}"
            df = ak.stock_zh_a_tick_tx_js(symbol=symbol)
            
            if df.empty:
                return None
            
            # 计算大单
            df['成交额'] = df['成交价'] * df['成交量'] / 10000  # 转换为万元
            big_orders = df[df['成交额'] >= self.big_order_threshold]
            
            return {
                '最新10笔': df.head(10),
                '大单笔数': len(big_orders),
                '大单总额': big_orders['成交额'].sum() if not big_orders.empty else 0,
            }
        except Exception as e:
            print(f"获取 {stock_code} 分时数据失败: {e}")
            return None
    
    def analyze_big_order(self, stock_code):
        """综合分析大单情况"""
        print(f"\n{'='*60}")
        print(f"【{stock_code}】大单分析 - {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'='*60}")
        
        # 1. 实时行情
        realtime = self.get_realtime_data(stock_code)
        if realtime:
            print(f"\n📊 实时行情:")
            print(f"  {realtime['名称']} ({realtime['代码']})")
            print(f"  最新价: {realtime['最新价']:.2f}  涨跌幅: {realtime['涨跌幅']:.2f}%")
            print(f"  成交额: {realtime['成交额']/100000000:.2f}亿  换手率: {realtime['换手率']:.2f}%")
        
        # 2. 资金流向
        money_flow = self.get_money_flow(stock_code)
        if money_flow:
            print(f"\n💰 资金流向:")
            print(f"  主力净流入: {money_flow['主力净流入']/10000:.2f}万 ({money_flow['主力净占比']:.2f}%)")
            print(f"  超大单净流入: {money_flow['超大单净流入']/10000:.2f}万 ({money_flow['超大单净占比']:.2f}%)")
            print(f"  大单净流入: {money_flow['大单净流入']/10000:.2f}万 ({money_flow['大单净占比']:.2f}%)")
            
            # 判断大单流向
            if money_flow['主力净流入'] > 0:
                print(f"  ✅ 主力资金净流入")
            else:
                print(f"  ❌ 主力资金净流出")
        
        # 3. 分时大单
        tick_data = self.get_tick_data(stock_code)
        if tick_data:
            print(f"\n🔍 分时大单 (>{self.big_order_threshold}万):")
            print(f"  大单笔数: {tick_data['大单笔数']}笔")
            print(f"  大单总额: {tick_data['大单总额']:.2f}万")
            
            if not tick_data['最新10笔'].empty:
                print(f"\n  最新10笔成交:")
                for idx, row in tick_data['最新10笔'].iterrows():
                    order_type = "🔴买" if row['性质'] == '买盘' else "🟢卖" if row['性质'] == '卖盘' else "⚪中"
                    amount = row['成交价'] * row['成交量'] / 10000
                    big_flag = "💎" if amount >= self.big_order_threshold else "  "
                    print(f"  {big_flag} {row['成交时间']} {order_type} {row['成交价']:.2f} × {row['成交量']} = {amount:.2f}万")
        
        return {
            'realtime': realtime,
            'money_flow': money_flow,
            'tick_data': tick_data
        }
    
    def monitor_loop(self, interval=10):
        """循环监测"""
        print(f"开始监测 {len(self.stock_codes)} 只股票...")
        print(f"大单阈值: {self.big_order_threshold}万元")
        print(f"刷新间隔: {interval}秒")
        
        try:
            while True:
                os.system('cls' if os.name == 'nt' else 'clear')
                print(f"\n{'#'*60}")
                print(f"盘口大单监测系统 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"{'#'*60}")
                
                for stock_code in self.stock_codes:
                    try:
                        self.analyze_big_order(stock_code)
                    except Exception as e:
                        print(f"监测 {stock_code} 出错: {e}")
                
                print(f"\n{'='*60}")
                print(f"等待 {interval} 秒后刷新... (Ctrl+C 退出)")
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n\n监测已停止")


def main():
    """主函数"""
    print("盘口大单监测工具")
    print("="*60)
    
    # 输入要监测的股票
    stock_input = input("请输入股票代码（多个用逗号分隔，如: 600519,000001）: ").strip()
    stock_codes = [code.strip() for code in stock_input.split(',')]
    
    # 输入大单阈值
    threshold_input = input("请输入大单阈值（万元，默认100）: ").strip()
    threshold = int(threshold_input) if threshold_input else 100
    
    # 输入刷新间隔
    interval_input = input("请输入刷新间隔（秒，默认10）: ").strip()
    interval = int(interval_input) if interval_input else 10
    
    # 创建监测器
    monitor = BigOrderMonitor(stock_codes, threshold)
    
    # 开始监测
    monitor.monitor_loop(interval)


if __name__ == "__main__":
    main()
