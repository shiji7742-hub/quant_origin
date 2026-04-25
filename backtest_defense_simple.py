"""
横盘托单策略回测（简化版）
基于日线数据识别横盘+反弹模式
"""
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import warnings
import time
import os
warnings.filterwarnings('ignore')

# 禁用代理，避免网络问题
os.environ['NO_PROXY'] = '*'
if 'HTTP_PROXY' in os.environ:
    del os.environ['HTTP_PROXY']
if 'HTTPS_PROXY' in os.environ:
    del os.environ['HTTPS_PROXY']


class SimpleDefenseBacktest:
    """简化版横盘托单回测"""
    
    def __init__(self):
        # 横盘识别参数
        self.sideways_days = 3  # 横盘天数
        self.sideways_range = 5.0  # 横盘波动范围（%）- 放宽到5%
        
        # 支撑测试参数
        self.support_test_range = 3.0  # 测试支撑的范围（%）- 放宽到3%
        
        # 反弹确认参数
        self.bounce_threshold = 0.5  # 反弹幅度（%）- 降低到0.5%
        
    def get_stock_list(self):
        """获取股票列表"""
        print("📊 使用预设股票列表...")
        return [
            ('600519', '贵州茅台'), ('000858', '五粮液'), ('600036', '招商银行'),
            ('601318', '中国平安'), ('000001', '平安银行'), ('600000', '浦发银行'),
            ('600276', '恒瑞医药'), ('000333', '美的集团'), ('000651', '格力电器'),
            ('002475', '立讯精密'), ('002594', '比亚迪'),
            ('600887', '伊利股份'), ('000568', '泸州老窖'), ('600809', '山西汾酒'),
            ('002415', '海康威视'), ('000063', '中兴通讯'), ('002230', '科大讯飞'),
            ('600031', '三一重工'), ('000002', '万科A'), ('600030', '中信证券'),
            ('601166', '兴业银行'), ('601288', '农业银行'), ('601398', '工商银行'),
            ('600016', '民生银行'), ('000725', '京东方A'), ('002352', '顺丰控股'),
            ('600009', '上海机场'), ('600585', '海螺水泥'), ('601888', '中国中免'),
            ('000876', '新希望'), ('002714', '牧原股份'), ('600690', '海尔智家'),
            ('000338', '潍柴动力'), ('600104', '上汽集团'), ('601012', '隆基绿能'),
            ('002156', '通富微电'), ('002049', '紫光国微'), ('600745', '闻泰科技'),
            ('002371', '北方华创'), ('603259', '药明康德'),
            ('300015', '爱尔眼科'), ('300760', '迈瑞医疗'), ('603288', '海天味业'),
            ('002027', '分众传媒'), ('300059', '东方财富'), ('000100', 'TCL科技'),
            ('600588', '用友网络'), ('002410', '广联达'), ('300124', '汇川技术'),
            ('002008', '大族激光'), ('300142', '沃森生物')
        ]
    
    def check_sideways_pattern(self, df, idx):
        """
        检查横盘模式
        
        模式：
        1. 前N天横盘（波动小）
        2. 某天测试支撑位（下探但不破）
        3. 后续反弹（托单成功）
        """
        # 需要足够的数据
        if idx < self.sideways_days + 1 or idx >= len(df) - 3:
            return None
        
        # 1. 检查横盘期
        sideways_period = df.iloc[idx-self.sideways_days:idx]
        high = sideways_period['最高'].max()
        low = sideways_period['最低'].min()
        avg = sideways_period['收盘'].mean()
        
        # 横盘波动
        sideways_volatility = (high - low) / avg * 100
        
        if sideways_volatility > self.sideways_range:
            return None  # 波动太大，不是横盘
        
        # 支撑位 = 横盘期最低点
        support = low
        
        # 2. 检查当天是否测试支撑
        today = df.iloc[idx]
        today_low = today['最低']
        today_close = today['收盘']
        
        # 当天最低价接近支撑位
        distance_to_support = (today_low - support) / support * 100
        
        if not (-self.support_test_range <= distance_to_support <= 0.5):
            return None  # 没有测试支撑
        
        # 3. 检查是否守住支撑并反弹
        # 守住支撑：最低价不破支撑位太多
        support_held = today_low >= support * 0.98
        
        # 收盘价回到支撑位上方
        close_above_support = today_close > support * 1.001
        
        if not (support_held and close_above_support):
            return None
        
        # 4. 检查后续反弹
        future_data = df.iloc[idx+1:idx+4]  # 后3天
        
        if len(future_data) == 0:
            return None
        
        # 计算反弹幅度
        max_price = future_data['最高'].max()
        bounce = (max_price - today_close) / today_close * 100
        
        if bounce < self.bounce_threshold:
            return None  # 反弹不够
        
        # 信号成立
        return {
            'signal_date': today['日期'],
            'signal_price': today_close,
            'support': support,
            'distance': distance_to_support,
            'sideways_volatility': sideways_volatility,
            'sideways_high': high,
            'sideways_low': low,
            'today_low': today_low,
            'bounce': bounce
        }
    
    def backtest_stock(self, stock_code, stock_name, start_date, end_date):
        """回测单只股票"""
        trades = []
        
        # 重试机制
        max_retries = 3
        for retry in range(max_retries):
            try:
                # 获取历史数据
                df = ak.stock_zh_a_hist(
                    symbol=stock_code,
                    period='daily',
                    start_date=start_date.strftime('%Y%m%d'),
                    end_date=end_date.strftime('%Y%m%d'),
                    adjust='qfq'
                )
                
                if df.empty or len(df) < 20:
                    return trades
                
                df['日期'] = pd.to_datetime(df['日期'])
                df = df.reset_index(drop=True)
                
                # 遍历每一天，寻找信号
                for i in range(self.sideways_days + 1, len(df) - 5):
                    signal = self.check_sideways_pattern(df, i)
                    
                    if signal:
                        # 买入价格：信号日收盘价
                        buy_price = signal['signal_price']
                        buy_date = signal['signal_date']
                        
                        # 计算后续收益
                        future_data = df.iloc[i+1:i+6]
                        
                        if len(future_data) == 0:
                            continue
                        
                        # 持有期收益
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
                            '横盘波动': f"{signal['sideways_volatility']:.2f}%",
                            '横盘区间': f"{signal['sideways_low']:.2f}-{signal['sideways_high']:.2f}",
                            '当日最低': signal['today_low'],
                            '预期反弹': f"{signal['bounce']:.2f}%",
                            '1日收益': returns.get('1日', 0),
                            '3日收益': returns.get('3日', 0),
                            '5日收益': returns.get('5日', 0),
                            '最高收益': max_return,
                            '最大回撤': max_drawdown
                        })
                
                return trades
                
            except Exception as e:
                if retry < max_retries - 1:
                    time.sleep(2)  # 等待2秒后重试
                    continue
                else:
                    # print(f"   {stock_name} 出错: {e}")
                    return trades
        
        return trades
    
    def run_backtest(self, sample_size=30, days=90):
        """运行回测"""
        print(f"\n{'='*80}")
        print(f"横盘托单策略回测（简化版）")
        print(f"{'='*80}\n")
        
        print(f"📅 回测周期: 最近 {days} 天")
        print(f"📊 样本数量: {sample_size} 只股票")
        print(f"⚙️  策略参数:")
        print(f"   - 横盘天数: {self.sideways_days} 天")
        print(f"   - 横盘波动: < {self.sideways_range}%")
        print(f"   - 支撑测试: {self.support_test_range}%")
        print(f"   - 反弹阈值: > {self.bounce_threshold}%")
        
        # 日期范围
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # 获取股票列表
        stock_list = self.get_stock_list()
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
            
            if trades:
                print(f"   ✅ {stock_name}: 发现 {len(trades)} 个信号")
            
            # 添加延迟，避免请求过快
            time.sleep(0.5)
        
        # 统计结果
        if not all_trades:
            print("\n❌ 未发现符合条件的交易信号")
            print("\n💡 建议：")
            print("   1. 增加回测天数")
            print("   2. 放宽横盘波动阈值")
            print("   3. 增加样本股票数量")
            return
        
        df = pd.DataFrame(all_trades)
        
        print(f"\n{'='*80}")
        print(f"回测结果统计")
        print(f"{'='*80}\n")
        
        print(f"📊 交易统计:")
        print(f"   总信号数: {len(df)}")
        print(f"   涉及股票: {df['股票代码'].nunique()} 只")
        print(f"   平均每只: {len(df) / df['股票代码'].nunique():.1f} 个信号")
        
        print(f"\n💰 收益统计:")
        for period in ['1日收益', '3日收益', '5日收益']:
            avg_return = df[period].mean()
            median_return = df[period].median()
            win_rate = (df[period] > 0).sum() / len(df) * 100
            max_return = df[period].max()
            min_return = df[period].min()
            
            print(f"\n   {period}:")
            print(f"      平均收益: {avg_return:+.2f}%")
            print(f"      中位收益: {median_return:+.2f}%")
            print(f"      胜率: {win_rate:.1f}%")
            print(f"      最大收益: {max_return:+.2f}%")
            print(f"      最大亏损: {min_return:+.2f}%")
        
        print(f"\n📈 极值统计:")
        print(f"   平均最高收益: {df['最高收益'].mean():+.2f}%")
        print(f"   平均最大回撤: {df['最大回撤'].mean():+.2f}%")
        
        # 保存详细结果
        filename = f"横盘托单回测_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        # 格式化数值列
        df_export = df.copy()
        for col in ['1日收益', '3日收益', '5日收益', '最高收益', '最大回撤']:
            df_export[col] = df_export[col].apply(lambda x: f"{x:+.2f}%")
        df_export['买入价格'] = df_export['买入价格'].apply(lambda x: f"{x:.2f}")
        df_export['支撑位'] = df_export['支撑位'].apply(lambda x: f"{x:.2f}")
        df_export['当日最低'] = df_export['当日最低'].apply(lambda x: f"{x:.2f}")
        
        df_export.to_excel(filename, index=False)
        print(f"\n✅ 详细结果已保存到: {filename}")
        
        # 显示最佳案例
        print(f"\n{'='*80}")
        print(f"最佳案例（按5日收益排序）")
        print(f"{'='*80}\n")
        
        top_trades = df.nlargest(min(10, len(df)), '5日收益')
        for idx, (i, row) in enumerate(top_trades.iterrows(), 1):
            print(f"{idx}. {row['股票名称']}({row['股票代码']}) - {row['信号日期']}")
            print(f"   买入: {row['买入价格']:.2f}  支撑: {row['支撑位']:.2f}  距离: {row['距支撑']}")
            print(f"   横盘: {row['横盘区间']}  波动: {row['横盘波动']}")
            print(f"   收益: 1日{row['1日收益']:+.2f}% | 3日{row['3日收益']:+.2f}% | 5日{row['5日收益']:+.2f}%")
            print()


def main():
    """主函数"""
    backtest = SimpleDefenseBacktest()
    
    print("横盘托单策略回测工具（简化版）")
    print("="*80)
    print("基于日线数据识别：横盘 → 测试支撑 → 反弹")
    print()
    
    try:
        backtest.run_backtest(sample_size=20, days=120)  # 增加到120天，减少样本到20只
        
    except KeyboardInterrupt:
        print("\n\n用户中断")
    except Exception as e:
        print(f"\n回测出错: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
