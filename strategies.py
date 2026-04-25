"""战法模块 - 可自定义添加"""
import pandas as pd

def check_all_strategies(df: pd.DataFrame) -> dict:
    """检测所有战法，返回触发的战法"""
    results = {}
    
    # 确保数据足够
    if df is None or len(df) < 20:
        return results
    
    results['放量突破'] = strategy_volume_breakout(df)
    results['均线金叉'] = strategy_ma_golden_cross(df)
    results['MACD底背离'] = strategy_macd_divergence(df)
    results['缩量回踩'] = strategy_pullback_support(df)
    results['突破平台'] = strategy_platform_breakout(df)
    results['底部放量'] = strategy_bottom_volume(df)
    results['三连阳'] = strategy_three_red(df)
    results['涨停破位洗盘'] = strategy_limit_up_washout(df)
    
    return results

# ============ 战法定义 ============

def strategy_volume_breakout(df: pd.DataFrame) -> dict:
    """
    战法1：放量突破
    条件：
    - 今日收盘价突破20日最高价
    - 成交量大于5日均量的1.5倍
    """
    latest = df.iloc[-1]
    high_20 = df['最高'].iloc[-21:-1].max()
    vol_ma5 = df['成交量'].iloc[-6:-1].mean()
    
    triggered = (latest['收盘'] > high_20) and (latest['成交量'] > vol_ma5 * 1.5)
    
    return {
        "触发": triggered,
        "说明": "股价放量突破20日高点，可能开启新一轮上涨",
        "条件": f"收盘{latest['收盘']:.2f} > 20日高点{high_20:.2f}, 量比{latest['成交量']/vol_ma5:.2f}"
    }

def strategy_ma_golden_cross(df: pd.DataFrame) -> dict:
    """
    战法2：均线金叉
    条件：
    - MA5上穿MA10
    - MA10上穿MA20（或已在上方）
    """
    df = df.copy()
    df['MA5'] = df['收盘'].rolling(5).mean()
    df['MA10'] = df['收盘'].rolling(10).mean()
    df['MA20'] = df['收盘'].rolling(20).mean()
    
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    # MA5上穿MA10
    golden_cross = (latest['MA5'] > latest['MA10']) and (prev['MA5'] <= prev['MA10'])
    # MA10在MA20上方
    ma_bullish = latest['MA10'] > latest['MA20']
    
    triggered = golden_cross and ma_bullish
    
    return {
        "触发": triggered,
        "说明": "短期均线金叉，趋势转多",
        "条件": f"MA5({latest['MA5']:.2f})上穿MA10({latest['MA10']:.2f}), MA10>MA20:{ma_bullish}"
    }

def strategy_macd_divergence(df: pd.DataFrame) -> dict:
    """
    战法3：MACD底背离
    条件：
    - 股价创近期新低
    - MACD没有创新低（背离）
    """
    import ta
    df = df.copy()
    macd = ta.trend.MACD(df['收盘'])
    df['MACD'] = macd.macd()
    
    # 最近10天
    recent = df.tail(10)
    price_low_idx = recent['收盘'].idxmin()
    macd_low_idx = recent['MACD'].idxmin()
    
    # 价格新低但MACD没新低
    triggered = (price_low_idx == recent.index[-1]) and (macd_low_idx != recent.index[-1])
    
    return {
        "触发": triggered,
        "说明": "股价新低但MACD未新低，可能见底反弹",
        "条件": f"价格低点日期 vs MACD低点日期"
    }

def strategy_pullback_support(df: pd.DataFrame) -> dict:
    """
    战法4：缩量回踩支撑
    条件：
    - 股价回踩MA20附近（±3%）
    - 成交量小于5日均量的0.7倍
    - 均线多头排列
    """
    df = df.copy()
    df['MA5'] = df['收盘'].rolling(5).mean()
    df['MA10'] = df['收盘'].rolling(10).mean()
    df['MA20'] = df['收盘'].rolling(20).mean()
    
    latest = df.iloc[-1]
    vol_ma5 = df['成交量'].iloc[-6:-1].mean()
    
    near_ma20 = abs(latest['收盘'] - latest['MA20']) / latest['MA20'] < 0.03
    low_volume = latest['成交量'] < vol_ma5 * 0.7
    ma_bullish = latest['MA5'] > latest['MA10'] > latest['MA20']
    
    triggered = near_ma20 and low_volume and ma_bullish
    
    return {
        "触发": triggered,
        "说明": "缩量回踩20日均线支撑，可能是买点",
        "条件": f"距MA20:{abs(latest['收盘']-latest['MA20'])/latest['MA20']*100:.1f}%, 量比:{latest['成交量']/vol_ma5:.2f}"
    }

def strategy_platform_breakout(df: pd.DataFrame) -> dict:
    """
    战法5：突破平台
    条件：
    - 过去10天振幅小于10%（横盘整理）
    - 今日突破这10天的最高价
    """
    recent = df.tail(11)
    platform = recent.iloc[:-1]  # 前10天
    latest = recent.iloc[-1]
    
    high_10 = platform['最高'].max()
    low_10 = platform['最低'].min()
    range_pct = (high_10 - low_10) / low_10 * 100
    
    is_platform = range_pct < 10
    breakout = latest['收盘'] > high_10
    
    triggered = is_platform and breakout
    
    return {
        "触发": triggered,
        "说明": "横盘整理后突破，可能开启主升浪",
        "条件": f"10日振幅:{range_pct:.1f}%, 突破{high_10:.2f}"
    }

def strategy_bottom_volume(df: pd.DataFrame) -> dict:
    """
    战法6：底部放量
    条件：
    - 股价处于近20日低位（低于20日均价）
    - 今日放量（大于5日均量2倍）
    - 收阳线
    """
    df = df.copy()
    latest = df.iloc[-1]
    ma20 = df['收盘'].tail(20).mean()
    vol_ma5 = df['成交量'].iloc[-6:-1].mean()
    
    at_bottom = latest['收盘'] < ma20
    high_volume = latest['成交量'] > vol_ma5 * 2
    is_red = latest['收盘'] > latest['开盘']
    
    triggered = at_bottom and high_volume and is_red
    
    return {
        "触发": triggered,
        "说明": "低位放量收阳，可能有资金抄底",
        "条件": f"价格<MA20, 量比:{latest['成交量']/vol_ma5:.2f}, 收阳:{is_red}"
    }

def strategy_three_red(df: pd.DataFrame) -> dict:
    """
    战法7：三连阳
    条件：
    - 连续3天收阳线
    - 每天收盘价高于前一天
    """
    recent = df.tail(3)
    
    all_red = all(recent['收盘'] > recent['开盘'])
    rising = (recent['收盘'].iloc[2] > recent['收盘'].iloc[1] > recent['收盘'].iloc[0])
    
    triggered = all_red and rising
    
    return {
        "触发": triggered,
        "说明": "三连阳上涨，多头强势",
        "条件": f"连续3天收阳且逐日上涨"
    }


def strategy_limit_up_washout(df: pd.DataFrame, relaxed: bool = False) -> dict:
    """
    战法8：涨停破位洗盘（抄底信号）
    
    逻辑：
    1. 在过去20-30天内找到一个非一字涨停板（有换手的涨停，开盘价<涨停价）
    2. 后续回调跌破这个涨停板的最低价（破位洗盘）
    3. 今天拉出阳线反包
    
    参数：
    - relaxed: 是否放宽条件（默认False）
      放宽后：大阳线>2%，量比>1.2，搜索范围30天，允许涨幅<8%
    """
    if len(df) < 20:
        return {"触发": False, "说明": "数据不足", "条件": ""}
    
    df = df.copy().reset_index(drop=True)
    latest = df.iloc[-1]
    latest_idx = len(df) - 1
    
    # 放宽条件参数
    if relaxed:
        min_yang_gain = 2.0      # 大阳线标准：>2%（原3%）
        max_chase_gain = 8.0     # 追高上限：<8%（原6%）
        search_days = 30         # 搜索范围：30天（原20天）
        min_vol_ratio_5 = 1.2    # 5日放量倍数：>1.2（原1.5）
        min_vol_ratio_10 = 1.1   # 10日放量倍数：>1.1（原1.3）
        min_today_vol = 1.2      # 当日量比：>1.2（原1.5）
        pre_gain_limit = 30      # 涨停前涨幅上限：30%（原20%）
    else:
        min_yang_gain = 3.0
        max_chase_gain = 6.0
        search_days = 20
        min_vol_ratio_5 = 1.5
        min_vol_ratio_10 = 1.3
        min_today_vol = 1.5
        pre_gain_limit = 20
    
    # 今天是否大阳线
    today_gain = (latest['收盘'] - latest['开盘']) / latest['开盘'] * 100
    is_big_yang = today_gain > min_yang_gain
    
    if not is_big_yang:
        return {
            "触发": False,
            "说明": "涨停破位后大阳反包抄底",
            "条件": f"今日涨幅{today_gain:.2f}%，未达到大阳线标准(>{min_yang_gain}%)"
        }
    
    # 在过去3-N天内找非一字涨停板（从近到远搜索）
    limit_up_info = None
    for i in range(latest_idx - 3, max(latest_idx - search_days, 0), -1):
        row = df.iloc[i]
        prev_close = df.iloc[i-1]['收盘'] if i > 0 else row['开盘']
        
        # 涨停判断：涨幅>=9.5%（考虑四舍五入）
        gain = (row['收盘'] - prev_close) / prev_close * 100
        is_limit_up = gain >= 9.5
        
        # 非一字板：开盘价 < 收盘价（有换手空间）
        is_not_yizi = row['开盘'] < row['收盘'] * 0.99  # 开盘价低于涨停价1%以上
        
        if is_limit_up and is_not_yizi:
            limit_up_info = {
                'idx': i,
                'date': row.get('日期', f'第{i}天'),
                'low': row['最低'],
                'close': row['收盘'],
                'open': row['开盘']
            }
            break
    
    if not limit_up_info:
        return {
            "触发": False,
            "说明": "涨停破位后大阳反包抄底",
            "条件": f"近{search_days}天内未找到非一字涨停板"
        }
    
    # 检查涨停是否是低位启动
    limit_idx = limit_up_info['idx']
    if limit_idx >= 10:
        price_10d_ago = df.iloc[limit_idx - 10]['收盘']
        price_before_limit = df.iloc[limit_idx - 1]['收盘']
        pre_gain = (price_before_limit - price_10d_ago) / price_10d_ago * 100
        if pre_gain > pre_gain_limit:
            return {
                "触发": False,
                "说明": "涨停破位后大阳反包抄底",
                "条件": f"涨停前10日已涨{pre_gain:.1f}%，不是低位启动(>{pre_gain_limit}%)"
            }
    
    # 检查最近两月（40个交易日）涨幅是否小于40%
    if len(df) >= 40:
        price_40d_ago = df.iloc[-40]['收盘']
        price_now = latest['收盘']
        gain_2month = (price_now - price_40d_ago) / price_40d_ago * 100
        if gain_2month > 40:
            return {
                "触发": False,
                "说明": "涨停破位后大阳反包抄底",
                "条件": f"近两月涨幅{gain_2month:.1f}%，超过40%上限"
            }
    
    # 检查涨停后的走势
    limit_low = limit_up_info['low']
    limit_close = limit_up_info['close']
    broke_support = False
    broke_date = None
    made_new_high = False  # 是否先创新高再破位
    max_high_after = limit_close  # 涨停后最高价
    
    # 检查涨停后到今天的走势
    for i in range(limit_up_info['idx'] + 1, latest_idx + 1):
        row = df.iloc[i]
        # 记录是否创新高（超过涨停收盘价5%以上算新高）
        new_high_threshold = 1.08 if relaxed else 1.05  # 放宽时允许涨8%再回落
        if row['最高'] > limit_close * new_high_threshold:
            made_new_high = True
            max_high_after = max(max_high_after, row['最高'])
        # 检查是否破位
        if row['最低'] <= limit_low:
            broke_support = True
            if broke_date is None:
                broke_date = row.get('日期', f'第{i}天')
    
    # 关键：如果先涨了一波再破位，不符合战法
    if made_new_high:
        return {
            "触发": False,
            "说明": "涨停破位后大阳反包抄底",
            "条件": f"涨停后先创新高({max_high_after:.2f})再回落，不符合直接洗盘条件"
        }
    
    if not broke_support:
        return {
            "触发": False,
            "说明": "涨停破位后大阳反包抄底",
            "条件": f"涨停板({limit_up_info['date']})最低价{limit_low:.2f}未被跌破"
        }
    
    # 今天收盘是否反包回涨停板最低价之上（洗盘结束信号）
    recovered = latest['收盘'] > limit_low
    
    # 检查近5日均量是否相比前20日均量明显放大
    if len(df) >= 25:
        vol_recent_5 = df['成交量'].iloc[-5:].mean()  # 近5日均量
        vol_recent_10 = df['成交量'].iloc[-10:].mean()  # 近10日均量
        vol_prev_20 = df['成交量'].iloc[-25:-5].mean()  # 前20日均量
        vol_ratio_5 = vol_recent_5 / vol_prev_20 if vol_prev_20 > 0 else 0
        vol_ratio_10 = vol_recent_10 / vol_prev_20 if vol_prev_20 > 0 else 0
        volume_amplify_5 = vol_ratio_5 > min_vol_ratio_5
        volume_amplify_10 = vol_ratio_10 > min_vol_ratio_10
        volume_amplify = volume_amplify_5 or volume_amplify_10
    else:
        vol_ratio_5 = 0
        vol_ratio_10 = 0
        volume_amplify = False
        volume_amplify_5 = False
        volume_amplify_10 = False
    
    # 当日量比
    vol_ma5_today = df['成交量'].iloc[-6:-1].mean() if len(df) >= 6 else 0
    today_vol_ratio = latest['成交量'] / vol_ma5_today if vol_ma5_today > 0 else 0
    high_vol_ratio = today_vol_ratio > min_today_vol
    
    # 当日涨幅不追高
    not_chasing_high = today_gain < max_chase_gain
    
    triggered = is_big_yang and broke_support and recovered and volume_amplify and high_vol_ratio and not_chasing_high
    
    # 放量信息显示
    if volume_amplify_5:
        vol_info = f"近5日放量{vol_ratio_5:.2f}倍✓"
    elif volume_amplify_10:
        vol_info = f"近10日放量{vol_ratio_10:.2f}倍✓(5日{vol_ratio_5:.2f})"
    else:
        vol_info = f"5日量比{vol_ratio_5:.2f}/10日量比{vol_ratio_10:.2f}✗"
    today_vol_info = f"当日量比{today_vol_ratio:.2f}"
    
    # 详细条件说明
    mode_tag = "[宽松]" if relaxed else ""
    conditions = []
    conditions.append(f"涨停最低价{limit_low:.2f}")
    conditions.append("已破位" if broke_support else "未破位")
    conditions.append(f"今日涨幅{today_gain:.2f}%{'✓' if not_chasing_high else f'✗>{max_chase_gain}%追高'}")
    conditions.append(f"收盘{latest['收盘']:.2f}{'✓反包' if recovered else '✗未反包'}")
    conditions.append(f"{vol_info}{'✓' if volume_amplify else '✗'}")
    conditions.append(f"{today_vol_info}{'✓' if high_vol_ratio else f'✗<{min_today_vol}量能不足'}")
    
    return {
        "触发": triggered,
        "说明": f"{mode_tag}涨停破位洗盘后大阳反包！涨停日:{limit_up_info['date']}, 破位后今日收复",
        "条件": ", ".join(conditions)
    }
