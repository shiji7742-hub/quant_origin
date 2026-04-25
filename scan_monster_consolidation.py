"""妖股震荡低吸策略
扫描条件：
1. 短期内有过连板或大幅拉升（妖股特征）
2. 回调后进入震荡区间
3. 当前价格接近震荡区间低点（买入信号）
4. 【新增】短线情绪过滤：只在市场情绪好的时候才扫描
"""
import akshare as ak
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import threading
import time
import sys
import warnings
warnings.filterwarnings('ignore')


# ==================== 短线情绪过滤器 ====================
class SentimentFilter:
    """短线情绪过滤器
    
    根据回测分析，妖股低吸策略与短线情绪高度相关：
    - 高波动(>=1.5%): 策略平均收益 +12.82%
    - 低波动(<0.8%): 策略平均收益 -0.48%
    
    过滤条件：
    1. 近5日波动率 > 0.8%
    2. 或近5日有1天大盘涨幅 > 1%
    3. 大盘站上5日均线
    """
    
    def __init__(self):
        self.sentiment_data = None
        self.is_good = False
        self.reason = ""
    
    def check(self):
        """检查当前短线情绪"""
        print("\n" + "="*60)
        print("【短线情绪检测】")
        print("="*60)
        
        try:
            # 获取上证指数近期数据
            df = ak.stock_zh_index_daily(symbol="sh000001")
            df['date'] = pd.to_datetime(df['date'])
            df = df.tail(20).reset_index(drop=True)
            
            # 计算每日涨跌幅
            df['pct_change'] = df['close'].pct_change() * 100
            
            # 近5日数据
            recent_5 = df.tail(5)
            latest = df.iloc[-1]
            
            # 指标1: 近5日波动率
            volatility_5d = recent_5['pct_change'].std()
            
            # 指标2: 近5日是否有大涨日(>1%)
            big_up_days = (recent_5['pct_change'] > 1).sum()
            
            # 指标3: 是否站上5日均线
            ma5 = df['close'].tail(5).mean()
            above_ma5 = latest['close'] > ma5
            
            # 指标4: 近5日涨天比例
            up_days = (recent_5['pct_change'] > 0).sum()
            up_ratio = up_days / 5 * 100
            
            # 指标5: 近10日波动率
            recent_10 = df.tail(10)
            volatility_10d = recent_10['pct_change'].std()
            
            # 打印情绪指标
            print(f"  上证指数: {latest['close']:.2f}")
            print(f"  5日均线:  {ma5:.2f} ({'站上' if above_ma5 else '跌破'})")
            print(f"  5日波动率: {volatility_5d:.2f}%")
            print(f"  10日波动率: {volatility_10d:.2f}%")
            print(f"  近5日大涨天数(>1%): {big_up_days}天")
            print(f"  近5日涨天比例: {up_ratio:.0f}%")
            
            # 判断情绪
            conditions_met = []
            conditions_failed = []
            
            # 条件1: 波动率
            if volatility_5d >= 0.8:
                conditions_met.append(f"5日波动率{volatility_5d:.2f}%>=0.8%")
            else:
                conditions_failed.append(f"5日波动率{volatility_5d:.2f}%<0.8%")
            
            # 条件2: 大涨日
            if big_up_days >= 1:
                conditions_met.append(f"有{big_up_days}天大涨")
            else:
                conditions_failed.append("近5日无大涨日")
            
            # 条件3: 站上均线
            if above_ma5:
                conditions_met.append("站上5日均线")
            else:
                conditions_failed.append("跌破5日均线")
            
            # 条件4: 涨天比例
            if up_ratio >= 50:
                conditions_met.append(f"涨天比例{up_ratio:.0f}%>=50%")
            else:
                conditions_failed.append(f"涨天比例{up_ratio:.0f}%<50%")
            
            # 综合判断：满足2个以上条件即可
            self.is_good = len(conditions_met) >= 2
            
            print("-"*60)
            if self.is_good:
                print(f"✅ 短线情绪: 良好 (满足{len(conditions_met)}个条件)")
                print(f"   {', '.join(conditions_met)}")
                self.reason = f"情绪良好: {', '.join(conditions_met)}"
            else:
                print(f"⚠️ 短线情绪: 较差 (仅满足{len(conditions_met)}个条件)")
                print(f"   不满足: {', '.join(conditions_failed)}")
                self.reason = f"情绪较差: {', '.join(conditions_failed)}"
            
            # 保存数据供后续使用
            self.sentiment_data = {
                'volatility_5d': volatility_5d,
                'volatility_10d': volatility_10d,
                'big_up_days': big_up_days,
                'above_ma5': above_ma5,
                'up_ratio': up_ratio,
                'conditions_met': len(conditions_met)
            }
            
            return self.is_good
            
        except Exception as e:
            print(f"❌ 情绪检测失败: {e}")
            print("   将继续扫描，但请注意市场风险")
            self.is_good = True  # 失败时默认允许扫描
            self.reason = "情绪检测失败"
            return True
    
    def get_summary(self):
        """获取情绪摘要"""
        if self.sentiment_data:
            return (f"5日波动率{self.sentiment_data['volatility_5d']:.2f}%, "
                    f"大涨天{self.sentiment_data['big_up_days']}天, "
                    f"{'站上' if self.sentiment_data['above_ma5'] else '跌破'}5日线")
        return "未检测"


# 全局情绪过滤器实例
sentiment_filter = SentimentFilter()


def get_all_stocks():
    """获取所有A股主板股票"""
    print("获取A股列表...")
    df = ak.stock_zh_a_spot_em()
    # 主板股票
    df = df[df['代码'].str.match(r'^(60|00)')]
    # 排除ST
    df = df[~df['名称'].str.contains('ST')]
    # 有效数据
    df = df[df['最新价'].notna() & (df['最新价'] > 0)]
    df = df[df['成交量'].notna() & (df['成交量'] > 0)]
    print(f"共 {len(df)} 只有效主板股票")
    return df[['代码', '名称', '最新价']].to_dict('records')


def find_monster_consolidation(symbol, name):
    """
    查找妖股震荡低吸机会
    
    妖股定义：
    - 60天内有过连板（至少2连板）
    - 或者30天内涨幅超过50%
    
    震荡区间定义：
    - 从高点回调后，近10-20天在某个价格区间内震荡
    - 震荡区间振幅 < 15%
    
    买入信号：
    - 当前价格接近震荡区间下沿（距离下沿 < 3%）
    - 缩量（成交量低于均量）
    """
    
    try:
        # 获取90天数据
        df = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="qfq")
        if df is None or len(df) < 60:
            return None
        
        df = df.tail(90).reset_index(drop=True)
        df['日期'] = pd.to_datetime(df['日期'])
        
        # ========== 第一步：判断是否是妖股 ==========
        is_monster = False
        monster_info = {}
        
        # 检查连板
        consecutive_limits = find_consecutive_limit_up(df)
        if consecutive_limits:
            is_monster = True
            monster_info = consecutive_limits
        
        # 检查30天涨幅
        if not is_monster and len(df) >= 30:
            price_30d_ago = df.iloc[-30]['收盘']
            price_high = df.tail(30)['最高'].max()
            gain_30d = (price_high - price_30d_ago) / price_30d_ago * 100
            if gain_30d >= 50:
                is_monster = True
                monster_info = {
                    'type': '短期暴涨',
                    'gain': round(gain_30d, 1),
                    'desc': f"30天内最高涨幅{gain_30d:.1f}%"
                }
        
        if not is_monster:
            return None
        
        # ========== 第二步：检查是否在震荡区间 ==========
        consolidation = find_consolidation_zone(df)
        if not consolidation:
            return None
        
        # ========== 第三步：检查是否接近区间低点 ==========
        latest = df.iloc[-1]
        zone_low = consolidation['zone_low']
        zone_high = consolidation['zone_high']
        current_price = latest['收盘']
        
        # 距离下沿的百分比
        dist_to_low = (current_price - zone_low) / zone_low * 100
        
        # 买入条件：距离下沿 < 5%
        if dist_to_low > 5:
            return None
        
        # 缩量条件
        vol_ma10 = df['成交量'].tail(10).mean()
        is_shrink = latest['成交量'] < vol_ma10 * 0.8
        
        # 计算潜在收益（到区间上沿）
        potential_gain = (zone_high - current_price) / current_price * 100
        
        return {
            '代码': symbol,
            '名称': name,
            '妖股类型': monster_info.get('type', '连板'),
            '妖股说明': monster_info.get('desc', ''),
            '最高涨幅': monster_info.get('gain', 0),
            '震荡天数': consolidation['days'],
            '区间下沿': round(zone_low, 2),
            '区间上沿': round(zone_high, 2),
            '当前价格': round(current_price, 2),
            '距下沿%': round(dist_to_low, 2),
            '潜在收益%': round(potential_gain, 2),
            '是否缩量': '是' if is_shrink else '否',
            '信号强度': '强' if dist_to_low < 2 and is_shrink else '中'
        }
        
    except Exception as e:
        return None


def find_consecutive_limit_up(df):
    """查找连板记录"""
    if len(df) < 60:
        return None
    
    # 在最近60天内查找连板
    for i in range(len(df) - 60, len(df) - 2):
        if i < 1:
            continue
            
        # 检查是否涨停
        prev_close = df.iloc[i-1]['收盘']
        curr_close = df.iloc[i]['收盘']
        gain = (curr_close - prev_close) / prev_close * 100
        
        if gain < 9.5:
            continue
        
        # 找到涨停，检查是否连板
        consecutive = 1
        for j in range(i + 1, min(i + 10, len(df))):
            prev = df.iloc[j-1]['收盘']
            curr = df.iloc[j]['收盘']
            g = (curr - prev) / prev * 100
            if g >= 9.5:
                consecutive += 1
            else:
                break
        
        if consecutive >= 2:
            limit_date = df.iloc[i]['日期']
            # 计算从连板起点到最高点的涨幅
            start_price = df.iloc[i-1]['收盘']
            max_price = df.iloc[i:i+consecutive+10]['最高'].max() if i+consecutive+10 < len(df) else df.iloc[i:]['最高'].max()
            total_gain = (max_price - start_price) / start_price * 100
            
            return {
                'type': f'{consecutive}连板',
                'date': limit_date.strftime('%Y-%m-%d'),
                'gain': round(total_gain, 1),
                'desc': f"{consecutive}连板，最高涨{total_gain:.1f}%"
            }
    
    return None


def find_consolidation_zone(df):
    """查找震荡区间"""
    if len(df) < 20:
        return None
    
    # 找到近期高点
    recent_60 = df.tail(60)
    high_idx = recent_60['最高'].idxmax()
    high_price = recent_60.loc[high_idx, '最高']
    
    # 高点之后的数据
    after_high = df.loc[high_idx:]
    if len(after_high) < 10:
        return None
    
    # 检查最近10-20天是否形成震荡区间
    for days in [10, 15, 20]:
        if len(df) < days:
            continue
            
        recent = df.tail(days)
        zone_high = recent['最高'].max()
        zone_low = recent['最低'].min()
        zone_range = (zone_high - zone_low) / zone_low * 100
        
        # 震荡区间振幅 < 15%
        if zone_range < 15:
            # 确认是从高点回调下来的
            pullback = (high_price - zone_high) / high_price * 100
            if pullback > 10:  # 至少回调10%
                return {
                    'days': days,
                    'zone_high': zone_high,
                    'zone_low': zone_low,
                    'zone_range': zone_range,
                    'pullback': pullback
                }
    
    return None


def scan_all_stocks(max_workers=15):
    """多线程扫描全市场"""
    stocks = get_all_stocks()
    total = len(stocks)
    
    print(f"\n开始扫描，使用 {max_workers} 个线程...")
    print("=" * 60)
    
    start_time = time.time()
    results = []
    completed = 0
    lock = threading.Lock()
    
    def worker(stock):
        nonlocal completed
        result = find_monster_consolidation(stock['代码'], stock['名称'])
        
        with lock:
            completed += 1
            if result:
                results.append(result)
                print(f"[{completed}/{total}] ✓ {result['名称']}({result['代码']}) {result['妖股类型']} 距下沿{result['距下沿%']}%")
                sys.stdout.flush()
            elif completed % 300 == 0:
                elapsed = time.time() - start_time
                speed = completed / elapsed if elapsed > 0 else 0
                eta = (total - completed) / speed if speed > 0 else 0
                print(f"[{completed}/{total}] 进度 {completed/total*100:.1f}%, 速度 {speed:.1f}只/秒, 剩余 {eta:.0f}秒")
                sys.stdout.flush()
        
        return result
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(worker, stock) for stock in stocks]
        for future in as_completed(futures):
            pass
    
    elapsed = time.time() - start_time
    print("=" * 60)
    print(f"扫描完成! 耗时 {elapsed:.1f}秒, 发现 {len(results)} 只符合条件")
    
    return results


def save_to_excel(results):
    """保存结果到Excel"""
    if not results:
        print("没有找到符合条件的股票")
        return None
    
    df = pd.DataFrame(results)
    # 按信号强度和距下沿排序
    df['排序权重'] = df.apply(lambda x: 0 if x['信号强度'] == '强' else 1, axis=1)
    df = df.sort_values(['排序权重', '距下沿%'])
    df = df.drop('排序权重', axis=1)
    
    filename = f"妖股震荡低吸_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='扫描结果')
        
        worksheet = writer.sheets['扫描结果']
        for col in worksheet.columns:
            worksheet.column_dimensions[col[0].column_letter].width = 12
    
    print(f"\n结果已保存到: {filename}")
    return filename


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='妖股震荡低吸扫描')
    parser.add_argument('--force', action='store_true', help='强制扫描，忽略情绪过滤')
    parser.add_argument('--workers', type=int, default=15, help='线程数')
    args = parser.parse_args()
    
    # 检查短线情绪
    sentiment_ok = sentiment_filter.check()
    
    if not sentiment_ok and not args.force:
        print("\n" + "="*60)
        print("⚠️ 当前短线情绪较差，不建议做妖股低吸")
        print("="*60)
        print("""
根据历史回测分析：
- 高波动市场(>=1.5%): 策略平均收益 +12.82%
- 低波动市场(<0.8%):  策略平均收益 -0.48%

当前市场特征：
""")
        data = sentiment_filter.sentiment_data
        if data:
            print(f"  • 5日波动率: {data['volatility_5d']:.2f}% (建议>=0.8%)")
            print(f"  • 大涨天数: {data['big_up_days']}天 (建议>=1天)")
            print(f"  • 5日均线: {'站上' if data['above_ma5'] else '跌破'} (建议站上)")
            print(f"  • 涨天比例: {data['up_ratio']:.0f}% (建议>=50%)")
        
        print("""
建议：
  1. 等待市场情绪回暖再操作
  2. 关注大盘是否站上5日均线
  3. 如需强制扫描，使用: python scan_monster_consolidation.py --force
""")
        print("="*60)
    else:
        if not sentiment_ok:
            print("\n⚠️ 警告：当前情绪较差，强制扫描中...")
            print("   请注意控制仓位，设置好止损！\n")
        
        results = scan_all_stocks(max_workers=args.workers)
        
        # 在结果中加入情绪信息
        if results:
            for r in results:
                r['市场情绪'] = sentiment_filter.get_summary()
        
        save_to_excel(results)
