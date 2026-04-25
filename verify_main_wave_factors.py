"""验证主升浪两大关键要素：板块利好 + 游资引导"""
import pandas as pd
import akshare as ak
import ta
from datetime import datetime, timedelta
import time
from collections import Counter

def find_main_wave_stocks(days=60, min_gain=50):
    """找出近期主升浪股票（大涨股）"""
    print(f"正在寻找近{days}天涨幅超过{min_gain}%的主升浪股票...")
    
    df = ak.stock_zh_a_spot_em()
    df = df[df['代码'].str.match(r'^(60|00)')]
    df = df[~df['名称'].str.contains('ST')]
    
    main_wave_stocks = []
    total = len(df)
    
    for idx, row in df.iterrows():
        code = row['代码']
        name = row['名称']
        
        if idx % 100 == 0:
            print(f"  进度: {idx}/{total}")
        
        try:
            hist = ak.stock_zh_a_hist(symbol=code, period='daily', adjust='qfq')
            if hist is None or len(hist) < days:
                continue
            
            hist = hist.tail(days + 10)
            
            # 找最低点到最高点的主升浪
            min_idx = hist['收盘'].idxmin()
            max_idx = hist['收盘'].idxmax()
            
            # 确保最高点在最低点之后
            if max_idx <= min_idx:
                continue
            
            min_price = hist.loc[min_idx, '收盘']
            max_price = hist.loc[max_idx, '收盘']
            gain = (max_price - min_price) / min_price * 100
            
            if gain >= min_gain:
                min_date = hist.loc[min_idx, '日期']
                max_date = hist.loc[max_idx, '日期']
                
                main_wave_stocks.append({
                    'code': code,
                    'name': name,
                    'start_date': str(min_date)[:10],
                    'peak_date': str(max_date)[:10],
                    'start_price': min_price,
                    'peak_price': max_price,
                    'gain': gain
                })
                print(f"  ✓ {code} {name} 涨幅 {gain:.1f}%")
            
            time.sleep(0.05)
            
        except Exception as e:
            continue
    
    print(f"\n共找到 {len(main_wave_stocks)} 只主升浪股票")
    return main_wave_stocks

def check_sector_surge(code, start_date, days_before=5):
    """检查起涨前后板块是否有异动"""
    try:
        # 获取股票所属板块
        stock_board = ak.stock_board_industry_name_em()
        stock_info = stock_board[stock_board['代码'] == code]
        
        if len(stock_info) == 0:
            return None
        
        sector = stock_info.iloc[0]['板块']
        
        # 获取板块历史数据
        sector_hist = ak.stock_board_industry_hist_em(symbol=sector, period='daily', adjust='')
        if sector_hist is None or len(sector_hist) < 20:
            return None
        
        sector_hist['日期'] = pd.to_datetime(sector_hist['日期'])
        target_date = pd.to_datetime(start_date)
        
        # 获取起涨前后的板块数据
        before_data = sector_hist[sector_hist['日期'] <= target_date].tail(days_before + 5)
        
        if len(before_data) < days_before:
            return None
        
        # 计算板块在起涨前5天的涨幅
        sector_gain_5d = (before_data.iloc[-1]['收盘'] - before_data.iloc[-days_before]['收盘']) / before_data.iloc[-days_before]['收盘'] * 100
        
        # 计算板块成交量变化
        vol_recent = before_data.tail(3)['成交量'].mean()
        vol_before = before_data.head(5)['成交量'].mean()
        vol_ratio = vol_recent / vol_before if vol_before > 0 else 0
        
        return {
            'sector': sector,
            'sector_gain_5d': sector_gain_5d,
            'sector_vol_ratio': vol_ratio,
            'has_sector_surge': sector_gain_5d > 5 or vol_ratio > 1.5  # 板块涨超5%或量能放大1.5倍
        }
    except Exception as e:
        return None

def check_hot_money_activity(code, start_date, days_range=10):
    """检查起涨前后是否有游资活动（龙虎榜）"""
    try:
        # 计算日期范围
        target = datetime.strptime(start_date, '%Y-%m-%d')
        start = (target - timedelta(days=days_range)).strftime('%Y%m%d')
        end = (target + timedelta(days=days_range)).strftime('%Y%m%d')
        
        # 获取个股龙虎榜历史
        lhb = ak.stock_lhb_stock_detail_em(symbol=code)
        
        if lhb is None or len(lhb) == 0:
            return {
                'has_lhb': False,
                'lhb_count': 0,
                'hot_money_buy': 0,
                'hot_money_names': []
            }
        
        # 筛选起涨前后的龙虎榜
        lhb['上榜日'] = pd.to_datetime(lhb['上榜日'])
        target_lhb = lhb[(lhb['上榜日'] >= target - timedelta(days=days_range)) & 
                         (lhb['上榜日'] <= target + timedelta(days=days_range))]
        
        if len(target_lhb) == 0:
            return {
                'has_lhb': False,
                'lhb_count': 0,
                'hot_money_buy': 0,
                'hot_money_names': []
            }
        
        # 统计游资买入
        hot_money_names = []
        total_buy = 0
        
        for _, row in target_lhb.iterrows():
            # 解析营业部信息（通常在"解读"或"上榜原因"字段）
            if '营业部' in str(row.get('解读', '')):
                hot_money_names.append(str(row.get('解读', '')))
            total_buy += row.get('买入额', 0) if pd.notna(row.get('买入额', 0)) else 0
        
        return {
            'has_lhb': True,
            'lhb_count': len(target_lhb),
            'hot_money_buy': total_buy / 100000000,  # 转换为亿
            'hot_money_names': hot_money_names[:3]  # 只保留前3个
        }
        
    except Exception as e:
        return {
            'has_lhb': False,
            'lhb_count': 0,
            'hot_money_buy': 0,
            'hot_money_names': []
        }

def verify_two_factors(main_wave_stocks):
    """验证两大要素：板块利好 + 游资引导"""
    print(f"\n开始验证 {len(main_wave_stocks)} 只主升浪股票的两大要素...")
    print("="*80)
    
    results = []
    
    for idx, stock in enumerate(main_wave_stocks):
        print(f"\n[{idx+1}/{len(main_wave_stocks)}] 分析 {stock['code']} {stock['name']}")
        print(f"  主升浪: {stock['start_date']} → {stock['peak_date']}, 涨幅 {stock['gain']:.1f}%")
        
        # 检查板块因素
        print("  检查板块利好...")
        sector_info = check_sector_surge(stock['code'], stock['start_date'])
        
        # 检查游资因素
        print("  检查游资活动...")
        hot_money_info = check_hot_money_activity(stock['code'], stock['start_date'])
        
        if sector_info and hot_money_info:
            result = {
                **stock,
                **sector_info,
                **hot_money_info
            }
            results.append(result)
            
            print(f"  ✓ 板块: {sector_info['sector']}, 涨幅: {sector_info['sector_gain_5d']:.1f}%, 量比: {sector_info['sector_vol_ratio']:.2f}")
            print(f"  ✓ 龙虎榜: {hot_money_info['lhb_count']}次, 买入: {hot_money_info['hot_money_buy']:.2f}亿")
        
        time.sleep(0.3)  # 避免请求过快
    
    return pd.DataFrame(results)

def analyze_results(df):
    """分析验证结果"""
    if len(df) == 0:
        print("\n没有足够的数据进行分析")
        return
    
    print("\n" + "="*80)
    print("主升浪两大要素验证结果")
    print("="*80)
    
    total = len(df)
    
    # 统计各种情况
    both_factors = df[(df['has_sector_surge']) & (df['has_lhb'])].shape[0]
    only_sector = df[(df['has_sector_surge']) & (~df['has_lhb'])].shape[0]
    only_hot_money = df[(~df['has_sector_surge']) & (df['has_lhb'])].shape[0]
    neither = df[(~df['has_sector_surge']) & (~df['has_lhb'])].shape[0]
    
    print(f"\n【样本总数】{total} 只主升浪股票")
    print(f"\n【两大要素分布】")
    print(f"  ★ 板块利好 + 游资引导: {both_factors} 只 ({both_factors/total*100:.1f}%)")
    print(f"  ○ 仅板块利好: {only_sector} 只 ({only_sector/total*100:.1f}%)")
    print(f"  ○ 仅游资引导: {only_hot_money} 只 ({only_hot_money/total*100:.1f}%)")
    print(f"  ○ 两者都无: {neither} 只 ({neither/total*100:.1f}%)")
    
    # 涨幅对比
    print(f"\n【涨幅对比】")
    if both_factors > 0:
        avg_gain_both = df[(df['has_sector_surge']) & (df['has_lhb'])]['gain'].mean()
        print(f"  双要素股票平均涨幅: {avg_gain_both:.1f}%")
    
    if only_sector > 0:
        avg_gain_sector = df[(df['has_sector_surge']) & (~df['has_lhb'])]['gain'].mean()
        print(f"  仅板块利好平均涨幅: {avg_gain_sector:.1f}%")
    
    if only_hot_money > 0:
        avg_gain_hm = df[(~df['has_sector_surge']) & (df['has_lhb'])]['gain'].mean()
        print(f"  仅游资引导平均涨幅: {avg_gain_hm:.1f}%")
    
    if neither > 0:
        avg_gain_neither = df[(~df['has_sector_surge']) & (~df['has_lhb'])]['gain'].mean()
        print(f"  无明显要素平均涨幅: {avg_gain_neither:.1f}%")
    
    # 热门板块统计
    print(f"\n【热门板块TOP5】")
    sector_counts = df[df['has_sector_surge']]['sector'].value_counts().head(5)
    for sector, count in sector_counts.items():
        print(f"  {sector}: {count} 只")
    
    # 结论
    print(f"\n【验证结论】")
    if both_factors / total >= 0.6:
        print(f"  ✓✓✓ 强验证: {both_factors/total*100:.0f}%的主升浪同时具备板块利好和游资引导")
    elif both_factors / total >= 0.4:
        print(f"  ✓✓ 中等验证: {both_factors/total*100:.0f}%的主升浪同时具备两大要素")
    else:
        print(f"  ✓ 弱验证: 仅{both_factors/total*100:.0f}%的主升浪同时具备两大要素")
    
    if (both_factors + only_sector) / total >= 0.7:
        print(f"  ✓ 板块利好是重要因素: {(both_factors + only_sector)/total*100:.0f}%的主升浪有板块支撑")
    
    if (both_factors + only_hot_money) / total >= 0.7:
        print(f"  ✓ 游资引导是重要因素: {(both_factors + only_hot_money)/total*100:.0f}%的主升浪有游资参与")
    
    # 保存详细结果
    output_file = f"主升浪两要素验证_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    df.to_excel(output_file, index=False)
    print(f"\n详细数据已保存到: {output_file}")
    
    return df

def main():
    print("="*80)
    print("主升浪两大关键要素验证")
    print("假设: 主升浪 = 板块利好 + 游资引导")
    print("="*80)
    
    # 第一步：找出主升浪股票
    main_wave_stocks = find_main_wave_stocks(days=60, min_gain=50)
    
    if len(main_wave_stocks) == 0:
        print("未找到符合条件的主升浪股票，尝试降低涨幅要求")
        return
    
    # 限制样本数量，避免请求过多
    if len(main_wave_stocks) > 30:
        print(f"\n样本过多，随机抽取30只进行分析")
        import random
        main_wave_stocks = random.sample(main_wave_stocks, 30)
    
    # 第二步：验证两大要素
    df = verify_two_factors(main_wave_stocks)
    
    # 第三步：分析结果
    if len(df) > 0:
        analyze_results(df)

if __name__ == '__main__':
    main()
