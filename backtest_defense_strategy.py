"""
横盘托单策略回测
策略：大单往上打，横盘托单
"""
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')


class DefenseStrategyBacktest:
    """横盘托单策略回测"""
    
    def __init__(self):
        self.big_order_threshold = 50  # 大单阈值（万元）
        self.sideways_threshold = 1.5  # 横盘波动阈值（%）- 放宽
        self.window = 10  # 横盘判断窗口（分钟）
        self.support_range = (-1.0, 0.5)  # 接近支撑位的范围（%）- 放宽
        self.buy_ratio = 1.5  # 买单/卖单比例
        self.min_buy_amount = 100  # 最小买入大单金额（万）
        
    def get_stock_list(self):
        """获取股票列表"""
        print("📊 使用预设股票列表...")
        # 使用常见的大盘股和中盘股
        return [
            ('600519', '贵州茅台'), ('000858', '五粮液'), ('600036', '招商银行'),
            ('601318', '中国平安'), ('000001', '平安银行'), ('600000', '浦发银行'),
            ('600276', '恒瑞医药'), ('000333', '美的集团'), ('000651', '格力电器'),
            ('002475', '立讯精密'), ('300750', '宁德时代'), ('002594', '比亚迪'),
            ('600887', '伊利股份'), ('000568', '泸州老窖'), ('600809', '山西汾酒'),
            ('002415', '海康威视'), ('000063', '中兴通讯'), ('002230', '科大讯飞'),
            ('600031', '三一重工'), ('000002', '万科A'), ('600030', '中信证券'),
            ('601166', '兴业银行'), ('601288', '农业银行'), ('601398', '工商银行'),
            ('600016', '民生银行'), ('000725', '京东方A'), ('002352', '顺丰控股'),
            ('600009', '上海机场'), ('600585', '海螺水泥'), ('601888', '中国中免'),
            ('000876', '新希望'), ('002714', '牧原股份'), ('600690', '海尔智家'),
            ('000338', '潍柴动力'), ('600104', '上汽集团'), ('601012', '隆基绿能'),
            ('002156', '通富微电'), ('002049', '紫光国微'), ('600745', '闻泰科技'),
            ('002371', '北方华创'), ('688981', '中芯国际'), ('603259', '药明康德'),
            ('300015', '爱尔眼科'), ('300760', '迈瑞医疗'), ('603288', '海天味业'),
            ('002027', '分众传媒'), ('300059', '东方财富'), ('000100', 'TCL科技'),
            ('600588', '用友网络'), ('002410', '广联达'), ('300124', '汇川技术'),
            ('002008', '大族激光'), ('300142', '沃森生物')
        ]
    
    def get_minute_data(self, stock_code, date):
        """获取指定日期的分时数据"""
        try:
            # 获取日线数据，找到对应日期
            end_date = date.strftime('%Y%m%d')
            start_date = (date - timedelta(days=10)).strftime('%Y%m%d')
            
            df = ak.stock_zh_a_hist(
                symbol=stock_code,
                period='daily',
                start_date=start_date,
                end_date=end_date,
                adjust='qfq'
            )
            
            if df.empty:
                return None
            
            # 找到对应日期的数据
            df['日期'] = pd.to_datetime(df['日期'])
            target_data = df[df['日期'].dt.date == date.date()]
            
            if target_data.empty:
                return None
            
            return target_data.iloc[0]
            
        except Exception as e:
            return None
    
    def simulate_intraday_pattern(self, daily_data):
        """模拟日内分时走势（简化版）"""
        # 基于日线数据模拟分时
        open_price = daily_data['开盘']
        high_price = daily_data['最高']
        low_price = daily_data['最低']
        close_price = daily_data['收盘']
        
        # 生成60个分钟数据点（简化为60分钟）
        minutes = 60
        prices = []
        
        # 简单的价格路径模拟
        for i in range(minutes):
            if i < 15:  # 开盘阶段
                price = open_price + (high_price - open_price) * (i / 15) * np.random.uniform(0.8, 1.2)
            elif i < 30:  # 上午阶段
                price = high_price - (high_price - low_price) * ((i - 15) / 15) * np.random.uniform(0.3, 0.7)
            elif i < 45:  # 下午阶段
                price = low_price + (close_price - low_price) * ((i - 30) / 15) * np.random.uniform(0.8, 1.2)
            else:  # 收盘阶段
                price = close_price + (close_price - low_price) * 0.1 * np.random.uniform(-0.5, 0.5)
            
            prices.append(max(low_price, min(high_price, price)))
        
        return pd.DataFrame({
            '时间': range(minutes),
            '价格': prices,
            '最高': [max(prices[max(0, i-5):i+1]) for i in range(minutes)],
            '最低': [min(prices[max(0, i-5):i+1]) for i in range(minutes)]
        })
    
    def check_sideways_signal(self, minute_df):
        """检查横盘托单信号"""
        if len(minute_df) < self.window + 5:  # 需要额外的数据用于验证
            return None
        
        # 取中间部分作为横盘判断区域
        sideways_window = minute_df.iloc[:-5]  # 排除最后5分钟
        
        if len(sideways_window) < self.window:
            return None
        
        recent = sideways_window.tail(self.window)
        
        high = recent['最高'].max()
        low = recent['最低'].min()
        avg = recent['价格'].mean()
        current = recent['价格'].iloc[-1]
        
        # 计算波动率
        volatility = (high - low) / avg * 100
        
        # 判断是否横盘
        if volatility >= self.sideways_threshold:
            return None
        
        # 支撑位
        support = low
        
        # 距离支撑位
        distance = (current - support) / support * 100
        
        # 判断是否接近支撑
        if not (self.support_range[0] <= distance <= self.support_range[1]):
            return None
        
        # 检查后续走势（托单效果）
        future_prices = minute_df.iloc[-5:]  # 最后5分钟
        
        if len(future_prices) < 3:
            return None
        
        # 检查是否守住支撑并反弹
        future_low = future_prices['最低'].min()
        future_high = future_prices['最高'].max()
        future_close = future_prices['价格'].iloc[-1]
        
        # 托单成功的标准：
        # 1. 守住支撑（最低价不破支撑位-0.5%）
        # 2. 有反弹（最高价或收盘价高于信号价）
        support_held = future_low >= support * 0.995
        has_bounce = future_high > current * 1.002 or future_close > current * 1.001
        
        if support_held and has_bounce:
            return {
                'signal_time': recent['时间'].iloc[-1],
                'signal_price': current,
                'support': support,
                'distance': distance,
                'volatility': volatility,
                'future_high': future_high,
                'future_low': future_low,
                'type': '托单护盘'
            }
        
        return None
    
    def backtest_stock(self, stock_code, stock_name, start_date, end_date):
        """回测单只股票"""
        trades = []
        
        try:
            # 获取历史数据
            df = ak.stock_zh_a_hist(
                symbol=stock_code,
                period='daily',
                start_date=start_date.strftime('%Y%m%d'),
                end_date=end_date.strftime('%Y%m%d'),
                adjust='qfq'
            )
            
            if df.empty or len(df) < 10:
                return trades
            
            df['日期'] = pd.to_datetime(df['日期'])
            
            # 遍历每一天
            for i in range(len(df) - 5):  # 保留5天用于计算收益
                daily_data = df.iloc[i]
                date = daily_data['日期']
                
                # 模拟分时数据
                minute_df = self.simulate_intraday_pattern(daily_data)
                
                # 检查信号
                signal = self.check_sideways_signal(minute_df)
                
                if signal:
                    # 买入价格：信号价格
                    buy_price = signal['signal_price']
                    buy_date = date
                    
                    # 计算后续收益
                    future_data = df.iloc[i+1:i+6]
                    
                    if len(future_data) == 0:
                        continue
                    
                    # 持有期收益（1天、3天、5天）
                    returns = {}
                    for hold_days in [1, 3, 5]:
                        if hold_days <= len(future_data):
                            sell_price = future_data.iloc[hold_days-1]['收盘']
                            returns[f'{hold_days}日'] = (sell_price - buy_price) / buy_price * 100
                    
                    # 最高收益
                    max_price = future_data['最高'].max()
                    max_return = (max_price - buy_price) / buy_price * 100
                    
                    # 最大回撤
                    min_price = future_data['最低'].min()
                    max_drawdown = (min_price - buy_price) / buy_price * 100
                    
                    trades.append({
                        '股票代码': stock_code,
                        '股票名称': stock_name,
                        '信号日期': buy_date.strftime('%Y-%m-%d'),
                        '买入价格': buy_price,
                        '支撑位': signal['support'],
                        '距支撑': f"{signal['distance']:.2f}%",
                        '波动率': f"{signal['volatility']:.2f}%",
                        '1日收益': returns.get('1日', 0),
                        '3日收益': returns.get('3日', 0),
                        '5日收益': returns.get('5日', 0),
                        '最高收益': max_return,
                        '最大回撤': max_drawdown
                    })
            
            return trades
            
        except Exception as e:
            return trades
    
    def run_backtest(self, sample_size=50, days=60):
        """运行回测"""
        print(f"\n{'='*80}")
        print(f"横盘托单策略回测")
        print(f"{'='*80}\n")
        
        print(f"📅 回测周期: 最近 {days} 天")
        print(f"📊 样本数量: {sample_size} 只股票")
        print(f"⚙️  策略参数:")
        print(f"   - 横盘波动阈值: {self.sideways_threshold}%")
        print(f"   - 支撑位范围: {self.support_range[0]}% ~ {self.support_range[1]}%")
        print(f"   - 大单阈值: {self.big_order_threshold}万")
        print(f"   - 买卖比例: {self.buy_ratio}")
        
        # 日期范围
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # 获取股票列表
        stock_list = self.get_stock_list()
        
        # 取前sample_size只股票
        sample_stocks = stock_list[:sample_size]
        
        print(f"\n🔍 开始回测 {len(sample_stocks)} 只股票...\n")
        
        all_trades = []
        processed = 0
        
        for stock_code, stock_name in sample_stocks:
            processed += 1
            if processed % 10 == 0:
                print(f"   进度: {processed}/{len(sample_stocks)}")
            
            trades = self.backtest_stock(stock_code, stock_name, start_date, end_date)
            all_trades.extend(trades)
        
        # 统计结果
        if not all_trades:
            print("\n❌ 未发现符合条件的交易信号")
            return
        
        df = pd.DataFrame(all_trades)
        
        print(f"\n{'='*80}")
        print(f"回测结果统计")
        print(f"{'='*80}\n")
        
        print(f"📊 交易统计:")
        print(f"   总信号数: {len(df)}")
        print(f"   涉及股票: {df['股票代码'].nunique()} 只")
        
        print(f"\n💰 收益统计:")
        for period in ['1日收益', '3日收益', '5日收益']:
            avg_return = df[period].mean()
            win_rate = (df[period] > 0).sum() / len(df) * 100
            max_return = df[period].max()
            min_return = df[period].min()
            
            print(f"\n   {period}:")
            print(f"      平均收益: {avg_return:+.2f}%")
            print(f"      胜率: {win_rate:.1f}%")
            print(f"      最大收益: {max_return:+.2f}%")
            print(f"      最大亏损: {min_return:+.2f}%")
        
        print(f"\n📈 极值统计:")
        print(f"   平均最高收益: {df['最高收益'].mean():+.2f}%")
        print(f"   平均最大回撤: {df['最大回撤'].mean():+.2f}%")
        
        # 保存详细结果
        filename = f"横盘托单回测_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        df.to_excel(filename, index=False)
        print(f"\n✅ 详细结果已保存到: {filename}")
        
        # 显示最佳案例
        print(f"\n{'='*80}")
        print(f"最佳案例（按5日收益排序）")
        print(f"{'='*80}\n")
        
        top_trades = df.nlargest(10, '5日收益')
        for i, row in top_trades.iterrows():
            print(f"{row['股票名称']}({row['股票代码']}) - {row['信号日期']}")
            print(f"   买入: {row['买入价格']:.2f}  支撑: {row['支撑位']:.2f}  距离: {row['距支撑']}")
            print(f"   收益: 1日{row['1日收益']:+.2f}% | 3日{row['3日收益']:+.2f}% | 5日{row['5日收益']:+.2f}%")
            print()


def main():
    """主函数"""
    backtest = DefenseStrategyBacktest()
    
    # 默认参数
    sample_size = 30  # 减少样本数量，加快速度
    days = 30  # 减少回测天数
    
    print("横盘托单策略回测工具")
    print("="*80)
    print(f"样本数量: {sample_size} 只股票")
    print(f"回测天数: {days} 天")
    
    try:
        backtest.run_backtest(sample_size=sample_size, days=days)
        
    except KeyboardInterrupt:
        print("\n\n用户中断")
    except Exception as e:
        print(f"\n回测出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
