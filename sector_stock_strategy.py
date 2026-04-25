"""
潜力板块+潜力个股组合策略
流程：
1. 扫描潜力板块（早期爆发→回撤洗盘→企稳）
2. 在潜力板块中找潜力个股（类似形态）
3. 回测验证策略有效性
4. 扫描当前市场（匹配市场情绪）
"""
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import warnings
warnings.filterwarnings('ignore')

# ==================== 市场情绪检测 ====================
class MarketSentiment:
    """市场情绪检测器"""
    
    def __init__(self):
        self.sentiment_score = 0
        self.volatility = 0
        self.trend = ""
        self.is_bullish = False
        
    def check(self, date=None):
        """检查指定日期的市场情绪"""
        try:
            df = ak.stock_zh_index_daily(symbol="sh000001")
            df['date'] = pd.to_datetime(df['date'])
            
            if date:
                target_date = pd.to_datetime(date)
                df = df[df['date'] <= target_date]
            
            if len(df) < 20:
                return False
            
            df = df.tail(20).reset_index(drop=True)
            df['pct_change'] = df['close'].pct_change() * 100
            
            latest = df.iloc[-1]
            recent_5 = df.tail(5)
            
            # 计算情绪指标
            self.volatility = recent_5['pct_change'].std()
            ma5 = df['close'].tail(5).mean()
            ma20 = df['close'].tail(20).mean()
            self.trend = "上涨" if latest['close'] > ma20 else "下跌"
            
            # 情绪评分
            score = 0
            
            # 1. 波动率（0-3分）
            if self.volatility >= 1.5:
                score += 3
            elif self.volatility >= 1.0:
                score += 2
            elif self.volatility >= 0.8:
                score += 1
            
            # 2. 趋势（0-2分）
            if latest['close'] > ma5 > ma20:
                score += 2
            elif latest['close'] > ma20:
                score += 1
            
            # 3. 近期涨天数（0-2分）
            up_days = (recent_5['pct_change'] > 0).sum()
            if up_days >= 4:
                score += 2
            elif up_days >= 3:
                score += 1
            
            self.sentiment_score = score
            self.is_bullish = score >= 3  # 7分满分，3分及格（降低门槛）
            
            return self.is_bullish
            
        except Exception as e:
            print(f"情绪检测失败: {e}")
            return False
    
    def get_summary(self):
        """获取情绪摘要"""
        return {
            'score': self.sentiment_score,
            'volatility': round(self.volatility, 2),
            'trend': self.trend,
            'is_bullish': self.is_bullish
        }


# ==================== 板块分析 ====================
def get_sector_history(sector_name, start_date, end_date):
    """获取板块历史数据（通过成分股估算）"""
    try:
        df = ak.stock_board_concept_cons_em(symbol=sector_name)
        if df is None or len(df) == 0:
            return None
        
        top_stocks = df.head(5)['代码'].tolist()
        all_data = []
        
        for symbol in top_stocks:
            try:
                hist = ak.stock_zh_a_hist(
                    symbol=symbol,
                    period="daily",
                    start_date=start_date,
                    end_date=end_date,
                    adjust="qfq"
                )
                if hist is not None and len(hist) > 30:
                    hist['涨跌幅'] = hist['收盘'].pct_change() * 100
                    hist['日期'] = pd.to_datetime(hist['日期'])
                    all_data.append(hist[['日期', '涨跌幅']].set_index('日期'))
            except:
                continue
        
        if len(all_data) == 0:
            return None
        
        combined = pd.concat([d['涨跌幅'] for d in all_data], axis=1)
        return combined.mean(axis=1)
    except:
        return None


def detect_potential_sector(daily_returns, sentiment_required=3):
    """
    检测潜力板块信号
    
    条件：
    1. 过去60天内有过爆发（单日>3%）
    2. 爆发后回撤5-15%
    3. 近15日表现弱(<5%)但近5日企稳(>-5%)
    4. 市场情绪评分 >= sentiment_required（默认3分）
    """
    if daily_returns is None or len(daily_returns) < 60:
        return False, None
    
    daily_returns = daily_returns.dropna()
    if len(daily_returns) < 60:
        return False, None
    
    old_period = daily_returns.iloc[:-15]
    recent_15d = daily_returns.iloc[-15:]
    recent_5d = daily_returns.iloc[-5:]
    
    # 条件1：找爆发
    surge_days = old_period[old_period > 3.0]
    if len(surge_days) == 0:
        return False, None
    
    max_surge_value = surge_days.max()
    max_surge_idx = surge_days.idxmax()
    surge_count = len(surge_days)
    
    after_surge = daily_returns[daily_returns.index >= max_surge_idx]
    if len(after_surge) < 10:
        return False, None
    
    # 计算回撤
    cumsum = after_surge.cumsum()
    max_gain = cumsum.max()
    current_gain = cumsum.iloc[-1]
    drawdown = max_gain - current_gain
    
    # 条件2：回撤5-15%
    if drawdown < 5 or drawdown > 15:
        return False, None
    
    # 条件3：近期弱但企稳
    recent_15d_sum = recent_15d.sum()
    recent_5d_sum = recent_5d.sum()
    recent_weak = recent_15d_sum < 5
    not_crashing = recent_5d_sum > -5
    
    if not (recent_weak and not_crashing):
        return False, None
    
    return True, {
        'surge_date': max_surge_idx.strftime('%Y-%m-%d'),
        'surge_value': round(max_surge_value, 2),
        'surge_count': surge_count,
        'drawdown': round(drawdown, 2),
        'recent_15d': round(recent_15d_sum, 2),
        'recent_5d': round(recent_5d_sum, 2)
    }


# ==================== 个股分析 ====================
def detect_potential_stock(df, check_date=None):
    """
    检测个股是否有类似板块的潜力形态
    
    条件：
    1. 过去60天内有过大涨（单日>5%或3日累计>10%）
    2. 之后回撤8-20%
    3. 近10日横盘或企稳（振幅<12%）
    4. 当前价格接近横盘区间下沿
    """
    if len(df) < 60:
        return False, None
    
    df = df.copy().reset_index(drop=True)
    df['涨跌幅'] = df['收盘'].pct_change() * 100
    
    if check_date:
        df = df[df['日期'] <= check_date]
    
    if len(df) < 60:
        return False, None
    
    latest_idx = len(df) - 1
    latest = df.iloc[-1]
    
    # 找大涨日
    surge_found = False
    surge_info = None
    
    for i in range(latest_idx - 15, max(latest_idx - 60, 0), -1):
        # 单日大涨>5%
        if df.iloc[i]['涨跌幅'] > 5:
            surge_found = True
            surge_info = {
                'idx': i,
                'date': df.iloc[i]['日期'],
                'gain': df.iloc[i]['涨跌幅'],
                'price': df.iloc[i]['收盘']
            }
            break
        
        # 或3日累计>10%
        if i >= 2:
            gain_3d = ((df.iloc[i]['收盘'] / df.iloc[i-3]['收盘']) - 1) * 100
            if gain_3d > 10:
                surge_found = True
                surge_info = {
                    'idx': i,
                    'date': df.iloc[i]['日期'],
                    'gain': gain_3d,
                    'price': df.iloc[i]['收盘']
                }
                break
    
    if not surge_found:
        return False, None
    
    # 计算回撤
    surge_idx = surge_info['idx']
    after_surge = df.iloc[surge_idx:]
    high_after = after_surge['最高'].max()
    current_price = latest['收盘']
    drawdown = (current_price - high_after) / high_after * 100
    
    # 回撤8-20%
    if drawdown > -8 or drawdown < -20:
        return False, None
    
    # 近10日横盘
    recent_10 = df.tail(10)
    high_10 = recent_10['最高'].max()
    low_10 = recent_10['最低'].min()
    range_10 = (high_10 - low_10) / low_10 * 100
    
    if range_10 > 12:
        return False, None
    
    # 当前价格接近下沿
    dist_to_low = (current_price - low_10) / low_10 * 100
    if dist_to_low > 5:
        return False, None
    
    return True, {
        'surge_date': surge_info['date'],
        'surge_gain': round(surge_info['gain'], 2),
        'drawdown': round(drawdown, 2),
        'range_10d': round(range_10, 2),
        'dist_to_low': round(dist_to_low, 2),
        'low_10d': round(low_10, 2),
        'high_10d': round(high_10, 2)
    }


# ==================== 回测 ====================
def backtest_strategy(start_date='20250901', end_date='20251231'):
    """回测潜力板块+潜力个股策略"""
    print("=" * 70)
    print("潜力板块+潜力个股策略回测")
    print("=" * 70)
    print(f"回测期间: {start_date} - {end_date}")
    
    # 获取所有板块
    print("\n获取板块列表...")
    sectors_df = ak.stock_board_concept_name_em()
    sectors = sectors_df['板块名称'].tolist()[:100]  # 测试前100个
    
    # 按月回测
    test_dates = pd.date_range(start=start_date, end=end_date, freq='MS')
    all_signals = []
    
    sentiment_checker = MarketSentiment()
    
    for test_date in test_dates:
        date_str = test_date.strftime('%Y-%m-%d')
        month_str = test_date.strftime('%Y年%m月')
        print(f"\n{'='*60}")
        print(f"回测日期: {month_str}")
        print("=" * 60)
        
        # 检查市场情绪
        sentiment_ok = sentiment_checker.check(date_str)
        sentiment_info = sentiment_checker.get_summary()
        
        print(f"市场情绪: 评分{sentiment_info['score']}/7, "
              f"波动率{sentiment_info['volatility']}%, "
              f"趋势{sentiment_info['trend']}, "
              f"{'✓适合' if sentiment_ok else '✗不适合'}")
        
        if not sentiment_ok:
            print("  市场情绪不佳，跳过")
            continue
        
        # 找潜力板块
        print("\n扫描潜力板块...")
        potential_sectors = []
        
        for sector in sectors[:50]:  # 每月测试50个板块
            data = get_sector_history(
                sector,
                (test_date - timedelta(days=90)).strftime('%Y%m%d'),
                test_date.strftime('%Y%m%d')
            )
            
            is_potential, details = detect_potential_sector(data)
            if is_potential:
                potential_sectors.append({
                    'name': sector,
                    'details': details
                })
        
        print(f"  发现 {len(potential_sectors)} 个潜力板块")
        
        if len(potential_sectors) == 0:
            continue
        
        # 在潜力板块中找个股
        print("\n在潜力板块中扫描个股...")
        month_signals = []
        
        for sector_info in potential_sectors[:10]:  # 取前10个板块
            sector = sector_info['name']
            print(f"  扫描板块: {sector}")
            
            try:
                cons = ak.stock_board_concept_cons_em(symbol=sector)
                if cons is None:
                    continue
                
                stocks = cons[cons['代码'].str.match(r'^(60|00)')].head(20)
                
                for _, stock in stocks.iterrows():
                    code = stock['代码']
                    name = stock['名称']
                    
                    try:
                        hist = ak.stock_zh_a_hist(
                            symbol=code,
                            period="daily",
                            start_date=(test_date - timedelta(days=90)).strftime('%Y%m%d'),
                            end_date=test_date.strftime('%Y%m%d'),
                            adjust="qfq"
                        )
                        
                        if hist is None or len(hist) < 60:
                            continue
                        
                        hist['日期'] = pd.to_datetime(hist['日期'])
                        is_potential, stock_details = detect_potential_stock(hist, test_date)
                        
                        if is_potential:
                            month_signals.append({
                                '信号日期': date_str,
                                '月份': month_str,
                                '板块': sector,
                                '代码': code,
                                '名称': name,
                                '信号价': hist.iloc[-1]['收盘'],
                                '市场情绪评分': sentiment_info['score'],
                                '市场波动率': sentiment_info['volatility'],
                                **stock_details
                            })
                            print(f"    ✓ {code} {name}")
                    except:
                        continue
            except:
                continue
        
        print(f"\n本月发现 {len(month_signals)} 个信号")
        all_signals.extend(month_signals)
    
    if len(all_signals) == 0:
        print("\n回测期间未发现信号")
        return pd.DataFrame()
    
    # 计算收益
    print(f"\n{'='*60}")
    print("计算信号收益...")
    print("=" * 60)
    
    signals_df = pd.DataFrame(all_signals)
    
    for idx, row in signals_df.iterrows():
        code = row['代码']
        signal_date = pd.to_datetime(row['信号日期'])
        signal_price = row['信号价']
        
        try:
            # 获取后续数据
            future_data = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=signal_date.strftime('%Y%m%d'),
                end_date='20260115',
                adjust="qfq"
            )
            
            if future_data is None or len(future_data) < 2:
                continue
            
            future_data['日期'] = pd.to_datetime(future_data['日期'])
            future_data = future_data[future_data['日期'] > signal_date]
            
            # 计算不同周期收益
            for days, label in [(5, '5日'), (10, '10日'), (20, '20日'), (60, '60日')]:
                if len(future_data) >= days:
                    future_price = future_data.iloc[days-1]['收盘']
                    ret = (future_price - signal_price) / signal_price * 100
                    signals_df.at[idx, f'{label}收益'] = round(ret, 2)
                    
                    # 计算最大回撤
                    period_data = future_data.head(days)
                    max_dd = ((period_data['收盘'].min() - signal_price) / signal_price * 100)
                    signals_df.at[idx, f'{label}最大回撤'] = round(max_dd, 2)
        except:
            continue
    
    return signals_df


# ==================== 当前扫描 ====================
def scan_current_market():
    """扫描当前市场"""
    print("\n" + "=" * 70)
    print("当前市场扫描")
    print("=" * 70)
    
    # 检查当前市场情绪
    sentiment = MarketSentiment()
    sentiment_ok = sentiment.check()
    sentiment_info = sentiment.get_summary()
    
    print(f"\n当前市场情绪:")
    print(f"  评分: {sentiment_info['score']}/7")
    print(f"  波动率: {sentiment_info['volatility']}%")
    print(f"  趋势: {sentiment_info['trend']}")
    print(f"  结论: {'✓ 适合操作' if sentiment_ok else '✗ 不适合操作'}")
    
    if not sentiment_ok:
        print("\n⚠️ 当前市场情绪不佳，不建议操作")
        print("建议等待市场情绪改善后再扫描")
        return []
    
    # 扫描潜力板块
    print("\n扫描潜力板块...")
    sectors_df = ak.stock_board_concept_name_em()
    sectors = sectors_df['板块名称'].tolist()[:80]
    
    potential_sectors = []
    for sector in sectors:
        data = get_sector_history(sector, '20250901', '20260115')
        is_potential, details = detect_potential_sector(data)
        if is_potential:
            potential_sectors.append({'name': sector, 'details': details})
            print(f"  ✓ {sector}")
    
    print(f"\n发现 {len(potential_sectors)} 个潜力板块")
    
    if len(potential_sectors) == 0:
        print("未发现潜力板块")
        return []
    
    # 在潜力板块中找个股
    print("\n在潜力板块中扫描个股...")
    results = []
    lock = threading.Lock()
    
    def scan_sector(sector_info):
        sector = sector_info['name']
        sector_results = []
        
        try:
            cons = ak.stock_board_concept_cons_em(symbol=sector)
            if cons is None:
                return sector_results
            
            stocks = cons[cons['代码'].str.match(r'^(60|00)')].head(30)
            
            for _, stock in stocks.iterrows():
                code = stock['代码']
                name = stock['名称']
                
                try:
                    hist = ak.stock_zh_a_hist(
                        symbol=code,
                        period="daily",
                        start_date='20250901',
                        adjust="qfq"
                    )
                    
                    if hist is None or len(hist) < 60:
                        continue
                    
                    hist['日期'] = pd.to_datetime(hist['日期'])
                    is_potential, stock_details = detect_potential_stock(hist)
                    
                    if is_potential:
                        sector_results.append({
                            '板块': sector,
                            '代码': code,
                            '名称': name,
                            '现价': hist.iloc[-1]['收盘'],
                            '今日涨幅': stock.get('涨跌幅', 0),
                            '市场情绪评分': sentiment_info['score'],
                            **stock_details
                        })
                        
                        with lock:
                            print(f"  ✓ {sector} - {code} {name}")
                except:
                    pass
        except:
            pass
        
        return sector_results
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(scan_sector, s) for s in potential_sectors]
        for future in as_completed(futures):
            results.extend(future.result())
    
    return results


# ==================== 主函数 ====================
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='潜力板块+潜力个股策略')
    parser.add_argument('--backtest', action='store_true', help='运行回测')
    parser.add_argument('--scan', action='store_true', help='扫描当前市场')
    args = parser.parse_args()
    
    if args.backtest:
        # 回测
        signals_df = backtest_strategy()
        
        if len(signals_df) > 0:
            # 保存回测结果
            filename = f"板块个股策略回测_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                signals_df.to_excel(writer, index=False, sheet_name='信号明细')
                
                # 统计分析
                stats = []
                for period in ['5日', '10日', '20日', '60日']:
                    col = f'{period}收益'
                    if col in signals_df.columns:
                        valid = signals_df[col].dropna()
                        if len(valid) > 0:
                            stats.append({
                                '周期': period,
                                '信号数': len(valid),
                                '胜率': f"{(valid > 0).sum() / len(valid) * 100:.1f}%",
                                '平均收益': f"{valid.mean():.2f}%",
                                '中位数收益': f"{valid.median():.2f}%",
                                '最大收益': f"{valid.max():.2f}%",
                                '最大亏损': f"{valid.min():.2f}%"
                            })
                
                stats_df = pd.DataFrame(stats)
                stats_df.to_excel(writer, index=False, sheet_name='统计分析')
            
            print(f"\n✓ 回测结果已保存: {filename}")
            
            # 打印统计
            print("\n" + "=" * 70)
            print("回测统计")
            print("=" * 70)
            print(stats_df.to_string(index=False))
    
    elif args.scan:
        # 扫描当前市场
        results = scan_current_market()
        
        if len(results) > 0:
            results_df = pd.DataFrame(results)
            
            # 保存结果
            filename = f"板块个股扫描_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            results_df.to_excel(filename, index=False)
            
            print(f"\n✓ 扫描结果已保存: {filename}")
            print(f"\n发现 {len(results)} 只潜力个股")
            
            # 按板块分组显示
            print("\n" + "=" * 70)
            print("扫描结果")
            print("=" * 70)
            for sector in results_df['板块'].unique():
                sector_stocks = results_df[results_df['板块'] == sector]
                print(f"\n【{sector}】({len(sector_stocks)}只)")
                for _, stock in sector_stocks.iterrows():
                    print(f"  {stock['代码']} {stock['名称']} "
                          f"现价{stock['现价']:.2f} "
                          f"距低点{stock['dist_to_low']:.1f}%")
        else:
            print("\n未发现符合条件的个股")
    
    else:
        print("请指定操作: --backtest 或 --scan")
        print("示例:")
        print("  python sector_stock_strategy.py --backtest  # 运行回测")
        print("  python sector_stock_strategy.py --scan      # 扫描当前市场")


if __name__ == "__main__":
    main()
