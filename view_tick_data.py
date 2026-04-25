#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
逐笔成交查看工具
实时查看股票的逐笔成交数据，分析大单、小单分布
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime
import time
import os
import sys


class TickDataViewer:
    """逐笔成交查看器"""
    
    def __init__(self):
        self.big_threshold_1 = 100  # 超大单：100万
        self.big_threshold_2 = 50   # 大单：50万
        self.big_threshold_3 = 20   # 中单：20万
        
    def get_stock_name(self, stock_code: str) -> str:
        """获取股票名称"""
        try:
            # 尝试从实时行情获取
            df = ak.stock_zh_a_spot_em()
            stock_info = df[df['代码'] == stock_code]
            if not stock_info.empty:
                return stock_info.iloc[0]['名称']
        except:
            pass
        return stock_code
    
    def format_symbol(self, stock_code: str) -> str:
        """格式化股票代码为akshare需要的格式"""
        if stock_code.startswith('6'):
            return f"sh{stock_code}"
        elif stock_code.startswith('0') or stock_code.startswith('3'):
            return f"sz{stock_code}"
        else:
            return stock_code
    
    def get_tick_data(self, stock_code: str) -> pd.DataFrame:
        """获取逐笔成交数据"""
        try:
            symbol = self.format_symbol(stock_code)
            print(f"正在获取 {stock_code} 的逐笔数据...")
            
            # 尝试使用腾讯接口
            df = ak.stock_zh_a_tick_tx_js(symbol=symbol)
            
            if df is None or len(df) == 0:
                # 如果失败，尝试另一个接口
                df = ak.stock_zh_a_tick_tx(symbol=symbol)
            
            if df is None or len(df) == 0:
                return pd.DataFrame()
            
            # 计算成交金额（万元）
            df['成交金额'] = df['成交价'] * df['成交量']
            df['成交额(万)'] = df['成交金额'] / 10000
            
            # 转换时间
            if '成交时间' in df.columns:
                df['时间'] = pd.to_datetime(df['成交时间'])
                df = df.sort_values('时间')
            
            # 分类订单大小
            df['订单类型'] = pd.cut(
                df['成交额(万)'],
                bins=[0, self.big_threshold_3, self.big_threshold_2, self.big_threshold_1, float('inf')],
                labels=['小单', '中单', '大单', '超大单']
            )
            
            return df
            
        except Exception as e:
            print(f"获取数据失败: {e}")
            return pd.DataFrame()
    
    def print_tick_data(self, df: pd.DataFrame, stock_code: str, stock_name: str = None, limit: int = 50):
        """打印逐笔成交数据"""
        if df.empty:
            print(f"❌ 无法获取 {stock_code} 的逐笔数据")
            return
        
        if stock_name is None:
            stock_name = self.get_stock_name(stock_code)
        
        # 清屏
        os.system('cls' if os.name == 'nt' else 'clear')
        
        # 打印标题
        print("=" * 100)
        print(f"📊 逐笔成交查看 - {stock_name} ({stock_code})")
        print(f"⏰ 更新时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 100)
        
        # 基本统计
        total_count = len(df)
        total_amount = df['成交额(万)'].sum()
        avg_price = df['成交价'].mean()
        current_price = df['成交价'].iloc[-1] if len(df) > 0 else 0
        
        print(f"\n📈 基本统计:")
        print(f"  总成交笔数: {total_count:,} 笔")
        print(f"  总成交额: {total_amount:,.2f} 万元")
        print(f"  平均成交价: {avg_price:.2f} 元")
        print(f"  最新成交价: {current_price:.2f} 元")
        
        # 按性质统计
        buy_df = df[df['性质'] == '买盘']
        sell_df = df[df['性质'] == '卖盘']
        neutral_df = df[df['性质'] == '中性盘']
        
        print(f"\n💰 买卖盘统计:")
        print(f"  买盘: {len(buy_df):,} 笔, {buy_df['成交额(万)'].sum():,.2f} 万元 ({buy_df['成交额(万)'].sum()/total_amount*100:.1f}%)")
        print(f"  卖盘: {len(sell_df):,} 笔, {sell_df['成交额(万)'].sum():,.2f} 万元 ({sell_df['成交额(万)'].sum()/total_amount*100:.1f}%)")
        if len(neutral_df) > 0:
            print(f"  中性盘: {len(neutral_df):,} 笔, {neutral_df['成交额(万)'].sum():,.2f} 万元")
        
        # 按订单大小统计
        print(f"\n📊 订单大小统计:")
        for order_type in ['小单', '中单', '大单', '超大单']:
            order_df = df[df['订单类型'] == order_type]
            if len(order_df) > 0:
                buy_amount = order_df[order_df['性质'] == '买盘']['成交额(万)'].sum()
                sell_amount = order_df[order_df['性质'] == '卖盘']['成交额(万)'].sum()
                print(f"  {order_type}: {len(order_df):,} 笔, {order_df['成交额(万)'].sum():,.2f} 万 (买:{buy_amount:,.2f}万 卖:{sell_amount:,.2f}万)")
        
        # 显示最近N笔成交
        print(f"\n📋 最近 {min(limit, len(df))} 笔成交:")
        print("-" * 100)
        print(f"{'时间':<12} {'方向':<4} {'价格':<8} {'数量':<10} {'金额(万)':<12} {'类型':<6}")
        print("-" * 100)
        
        recent_df = df.tail(limit).copy()
        for idx, row in recent_df.iterrows():
            # 方向标记
            if row['性质'] == '买盘':
                direction = "🔴买"
            elif row['性质'] == '卖盘':
                direction = "🟢卖"
            else:
                direction = "⚪中"
            
            # 大单标记
            amount = row['成交额(万)']
            if amount >= self.big_threshold_1:
                flag = "💎💎💎"
            elif amount >= self.big_threshold_2:
                flag = "💎💎"
            elif amount >= self.big_threshold_3:
                flag = "💎"
            else:
                flag = "   "
            
            # 时间格式化
            time_str = str(row.get('成交时间', row.get('时间', '')))[:12]
            
            print(f"{time_str:<12} {direction:<4} {row['成交价']:>7.2f} {row['成交量']:>9,} {amount:>11.2f} {flag} {row['订单类型']}")
        
        print("-" * 100)
        
        # 显示超大单详情
        super_big = df[df['成交额(万)'] >= self.big_threshold_1]
        if len(super_big) > 0:
            print(f"\n💎💎💎 超大单详情 (≥{self.big_threshold_1}万):")
            print("-" * 100)
            for idx, row in super_big.iterrows():
                direction = "🔴买" if row['性质'] == '买盘' else "🟢卖" if row['性质'] == '卖盘' else "⚪中"
                time_str = str(row.get('成交时间', row.get('时间', '')))[:12]
                print(f"  {time_str} {direction} {row['成交价']:.2f} × {row['成交量']:,} = {row['成交额(万)']:.2f}万")
            print("-" * 100)
    
    def view_single_stock(self, stock_code: str, refresh: bool = False, interval: int = 5):
        """查看单只股票的逐笔成交"""
        stock_name = self.get_stock_name(stock_code)
        
        if refresh:
            # 循环刷新模式
            print(f"开始实时监测 {stock_name} ({stock_code})，每 {interval} 秒刷新一次...")
            print("按 Ctrl+C 停止")
            try:
                while True:
                    df = self.get_tick_data(stock_code)
                    self.print_tick_data(df, stock_code, stock_name)
                    print(f"\n⏳ 等待 {interval} 秒后刷新...")
                    time.sleep(interval)
            except KeyboardInterrupt:
                print("\n\n已停止监测")
        else:
            # 单次查看
            df = self.get_tick_data(stock_code)
            self.print_tick_data(df, stock_code, stock_name)
    
    def view_multiple_stocks(self, stock_codes: list, limit: int = 20):
        """查看多只股票的逐笔成交"""
        print("=" * 100)
        print(f"📊 批量查看逐笔成交 - {len(stock_codes)} 只股票")
        print("=" * 100)
        
        for i, stock_code in enumerate(stock_codes, 1):
            print(f"\n\n[{i}/{len(stock_codes)}] 正在查看 {stock_code}...")
            df = self.get_tick_data(stock_code)
            if not df.empty:
                stock_name = self.get_stock_name(stock_code)
                self.print_tick_data(df, stock_code, stock_name, limit=limit)
            else:
                print(f"❌ 无法获取 {stock_code} 的数据")
            
            if i < len(stock_codes):
                print("\n" + "-" * 100)
                time.sleep(1)  # 避免请求过快


def main():
    """主函数"""
    viewer = TickDataViewer()
    
    print("=" * 100)
    print("📊 逐笔成交查看工具")
    print("=" * 100)
    print("\n使用方法:")
    print("  1. 查看单只股票: python view_tick_data.py <股票代码>")
    print("  2. 实时刷新模式: python view_tick_data.py <股票代码> --refresh")
    print("  3. 查看多只股票: python view_tick_data.py <代码1> <代码2> ...")
    print("\n示例:")
    print("  python view_tick_data.py 002279")
    print("  python view_tick_data.py 002279 --refresh")
    print("  python view_tick_data.py 002279 000001 600000")
    print("=" * 100)
    
    if len(sys.argv) < 2:
        # 如果没有参数，使用默认股票
        print("\n未提供股票代码，使用默认示例: 002279 (久其软件)")
        viewer.view_single_stock("002279")
    else:
        args = sys.argv[1:]
        
        # 检查是否有 --refresh 参数
        if '--refresh' in args:
            refresh = True
            args.remove('--refresh')
        else:
            refresh = False
        
        if len(args) == 1:
            # 单只股票
            viewer.view_single_stock(args[0], refresh=refresh)
        else:
            # 多只股票
            viewer.view_multiple_stocks(args)


if __name__ == '__main__':
    main()
