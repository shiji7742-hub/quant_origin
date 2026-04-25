"""
扫描潜力板块 - 寻找类似商业航天启动前特征的板块
特征：早期有爆发 -> 回撤洗盘 -> 近期企稳
"""
import akshare as ak
import pandas as pd
import numpy as np
import requests
from io import StringIO
from datetime import datetime, timedelta
from backtest_sector_surge import get_market_data, is_market_bullish
from data_fetcher import get_stock_history

SECTOR_LIST_CACHE = None
SECTOR_CONSTITUENTS_CACHE = {}

def get_all_sectors():
    """获取所有概念板块"""
    global SECTOR_LIST_CACHE

    if SECTOR_LIST_CACHE is not None and not SECTOR_LIST_CACHE.empty:
        return SECTOR_LIST_CACHE

    try:
        df = ak.stock_board_concept_name_em()
        if df is None or df.empty:
            raise ValueError("东方财富板块列表为空")
        SECTOR_LIST_CACHE = df
        return df
    except Exception as e:
        print(f"获取板块列表失败，切换同花顺备用源: {e}")
        try:
            ths_df = ak.stock_board_concept_name_ths()
            if ths_df is None or ths_df.empty:
                return pd.DataFrame()
            SECTOR_LIST_CACHE = ths_df.rename(columns={
                'name': '板块名称',
                'code': '板块代码'
            })
            return SECTOR_LIST_CACHE
        except Exception as fallback_error:
            print(f"同花顺板块列表也失败: {fallback_error}")
            return pd.DataFrame()


def get_scan_window(lookback_days=220):
    """获取滚动扫描窗口。"""
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=lookback_days)
    return start_date.strftime('%Y%m%d'), end_date.strftime('%Y%m%d')


def get_sector_code_by_name(sector_name):
    """根据板块名称查找板块代码。"""
    df = get_all_sectors()
    if df is None or df.empty:
        return ''

    matched = df[df['板块名称'] == sector_name]
    if matched.empty:
        return ''
    return str(matched.iloc[0]['板块代码'])


def normalize_sector_constituents(df: pd.DataFrame) -> pd.DataFrame:
    """统一板块成分股字段。"""
    if df is None or df.empty:
        return pd.DataFrame(columns=['代码', '名称'])

    rename_map = {
        'code': '代码',
        'name': '名称',
    }
    normalized = df.rename(columns=rename_map).copy()
    if '代码' not in normalized.columns or '名称' not in normalized.columns:
        return pd.DataFrame(columns=['代码', '名称'])

    normalized['代码'] = normalized['代码'].astype(str).str.extract(r'(\d+)', expand=False).fillna('')
    normalized['代码'] = normalized['代码'].str.zfill(6)
    normalized['名称'] = normalized['名称'].astype(str).str.strip()
    normalized = normalized[(normalized['代码'] != '') & (normalized['名称'] != '')]
    return normalized


def fetch_sector_constituents_from_ths(sector_code: str) -> pd.DataFrame:
    """从同花顺板块详情页抓取成分股。"""
    if not sector_code:
        return pd.DataFrame(columns=['代码', '名称'])

    response = requests.get(
        f'https://q.10jqka.com.cn/gn/detail/code/{sector_code}/',
        timeout=20,
        headers={'User-Agent': 'Mozilla/5.0'}
    )
    response.raise_for_status()

    tables = pd.read_html(StringIO(response.text))
    if not tables:
        return pd.DataFrame(columns=['代码', '名称'])

    return normalize_sector_constituents(tables[0])


def get_sector_constituents(sector_name: str, sector_code: str = '') -> pd.DataFrame:
    """获取板块成分股，优先东方财富，失败后回退同花顺页面抓取。"""
    cache_key = sector_code or sector_name
    cached = SECTOR_CONSTITUENTS_CACHE.get(cache_key)
    if cached is not None and not cached.empty:
        return cached.copy()

    try:
        df = ak.stock_board_concept_cons_em(symbol=sector_name)
        normalized = normalize_sector_constituents(df)
        if not normalized.empty:
            SECTOR_CONSTITUENTS_CACHE[cache_key] = normalized
            return normalized.copy()
    except Exception as exc:
        print(f"获取板块成分股失败，切换同花顺备用源 {sector_name}: {exc}")

    resolved_code = str(sector_code or get_sector_code_by_name(sector_name))
    if not resolved_code:
        return pd.DataFrame(columns=['代码', '名称'])

    try:
        normalized = fetch_sector_constituents_from_ths(resolved_code)
        if not normalized.empty:
            SECTOR_CONSTITUENTS_CACHE[cache_key] = normalized
            return normalized.copy()
    except Exception as fallback_exc:
        print(f"同花顺板块成分股也失败 {sector_name}: {fallback_exc}")

    return pd.DataFrame(columns=['代码', '名称'])


def get_sector_history(sector_name, sector_code='', lookback_days=220):
    """获取板块历史数据（通过龙头股估算）"""
    try:
        df = get_sector_constituents(sector_name, sector_code=sector_code)
        if df is None or len(df) == 0:
            return None
        
        # 取前3只股票作为代表
        top_stocks = df.head(3)['代码'].tolist()
        
        all_data = []
        for symbol in top_stocks:
            try:
                hist = get_stock_history(symbol, days=lookback_days)
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

def detect_potential_signal(daily_returns, market_data=None):
    """
    检测潜力信号 - 类似商业航天11月的特征
    
    条件：
    1. 过去60天内有过爆发（单日>3%）
    2. 爆发后有明显回撤（5-15%）
    3. 近期表现弱但企稳（近15日累计<5%，近5日不大跌）
    4. 大盘在20日均线上方
    """
    if daily_returns is None or len(daily_returns) < 60:
        return False, None
    
    daily_returns = daily_returns.dropna()
    
    if len(daily_returns) < 60:
        return False, None
    
    # 检查大盘
    check_date = daily_returns.index[-1]
    if market_data is not None and not is_market_bullish(check_date, market_data):
        return False, None
    
    # 分段
    old_period = daily_returns.iloc[:-15]  # 15天前的数据
    recent_15d = daily_returns.iloc[-15:]  # 最近15天
    recent_5d = daily_returns.iloc[-5:]    # 最近5天
    
    # 条件1：找爆发（单日>3%）
    surge_days = old_period[old_period > 3.0]
    
    if len(surge_days) == 0:
        return False, None
    
    max_surge_value = surge_days.max()
    max_surge_idx = surge_days.idxmax()
    surge_count = len(surge_days)
    
    # 爆发后数据
    after_surge = daily_returns[daily_returns.index >= max_surge_idx]
    
    if len(after_surge) < 10:
        return False, None
    
    # 计算指标
    cumulative_after = after_surge.sum()
    recent_15d_sum = recent_15d.sum()
    recent_5d_sum = recent_5d.sum()
    
    # 计算回撤
    cumsum = after_surge.cumsum()
    max_gain = cumsum.max()
    current_gain = cumsum.iloc[-1]
    drawdown = max_gain - current_gain
    
    # 条件2：回撤在5-15%之间
    if drawdown < 5 or drawdown > 15:
        return False, None
    
    # 条件3：近期弱但企稳
    recent_weak = recent_15d_sum < 5
    not_crashing = recent_5d_sum > -5  # 近5日不能大跌
    
    # 条件4：没有走出主升
    no_main_rise = cumulative_after < max_surge_value * 3
    
    if no_main_rise and recent_weak and not_crashing:
        # 计算各月涨幅
        monthly_returns = {}
        for month in ['2025-09', '2025-10', '2025-11', '2025-12', '2026-01']:
            month_data = daily_returns[daily_returns.index.strftime('%Y-%m') == month]
            if len(month_data) > 0:
                monthly_returns[month] = month_data.sum()
        
        return True, {
            'surge_date': max_surge_idx.strftime('%Y-%m-%d'),
            'surge_value': round(max_surge_value, 2),
            'surge_count': surge_count,
            'drawdown': round(drawdown, 2),
            'recent_15d': round(recent_15d_sum, 2),
            'recent_5d': round(recent_5d_sum, 2),
            'cumulative_after': round(cumulative_after, 2),
            'monthly_returns': monthly_returns
        }
    
    return False, None

def scan_potential_sectors(num_sectors=100):
    """扫描潜力板块"""
    print("=" * 70)
    print("潜力板块扫描 - 寻找类似商业航天启动前特征的板块")
    print("=" * 70)
    print("\n扫描条件：")
    print("  1. 过去60天内有过爆发（单日>3%）")
    print("  2. 爆发后回撤5-15%（洗盘）")
    print("  3. 近15日表现弱(<5%)但近5日企稳(>-5%)")
    print("  4. 大盘在20日均线上方")
    
    start_date, end_date = get_scan_window()

    print("\n获取大盘数据...")
    market_data = get_market_data(start_date, end_date)
    
    print("获取板块列表...")
    df = get_all_sectors()
    
    if df.empty:
        print("获取板块列表失败")
        return []
    
    print(f"共 {len(df)} 个板块，将扫描 {min(num_sectors, len(df))} 个")
    
    # 随机打乱
    import random
    sectors = df.to_dict('records')
    random.shuffle(sectors)
    sectors = sectors[:num_sectors]
    
    results = []
    
    for i, sector in enumerate(sectors):
        name = sector['板块名称']
        today_change = float(sector.get('涨跌幅', 0) or 0)
        
        print(f"[{i+1}/{len(sectors)}] 分析 {name}...", end=" ")
        
        data = get_sector_history(name, sector.get('板块代码', ''))
        
        if data is None:
            print("数据获取失败")
            continue
        
        is_potential, details = detect_potential_signal(data, market_data)
        
        if is_potential:
            print(f"✓ 符合条件！")
            results.append({
                '板块名称': name,
                '板块代码': sector['板块代码'],
                '当日涨幅': today_change,
                '上涨家数': int(sector.get('上涨家数', 0) or 0),
                '下跌家数': int(sector.get('下跌家数', 0) or 0),
                **details
            })
        else:
            print("×")
    
    # 按回撤排序（回撤越大，洗盘越充分）
    results = sorted(results, key=lambda x: x['drawdown'], reverse=True)
    
    return results

def print_results(results):
    """打印结果"""
    if not results:
        print("\n未发现符合条件的板块")
        return
    
    print("\n" + "=" * 70)
    print(f"发现 {len(results)} 个潜力板块")
    print("=" * 70)
    
    for i, r in enumerate(results, 1):
        print(f"\n【{i}. {r['板块名称']}】")
        print(f"  爆发日期: {r['surge_date']} | 爆发涨幅: +{r['surge_value']}%")
        print(f"  爆发次数: {r['surge_count']}次")
        print(f"  高点回撤: {r['drawdown']}%（洗盘程度）")
        print(f"  近15日: {r['recent_15d']}% | 近5日: {r['recent_5d']}%")
        print(f"  今日: {r['当日涨幅']:.2f}% | 上涨{r['上涨家数']}家 下跌{r['下跌家数']}家")
        
        # 打印月度走势
        if 'monthly_returns' in r:
            monthly = r['monthly_returns']
            print(f"  月度走势: ", end="")
            for month, ret in monthly.items():
                month_name = month.split('-')[1] + '月'
                print(f"{month_name}:{ret:+.1f}% ", end="")
            print()
    
    # 总结
    print("\n" + "=" * 70)
    print("【分析总结】")
    print("=" * 70)
    print("\n这些板块具有类似商业航天启动前的特征：")
    print("1. 早期有过爆发（说明有资金关注）")
    print("2. 之后回撤洗盘（清洗浮筹）")
    print("3. 近期企稳（可能在酝酿新一轮上涨）")
    print("\n建议关注回撤较大（8-12%）且近期企稳的板块")
    print("这类板块洗盘更充分，启动后空间可能更大")

if __name__ == "__main__":
    results = scan_potential_sectors(num_sectors=80)
    print_results(results)
