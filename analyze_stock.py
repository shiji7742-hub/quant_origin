"""
个股深度分析 - 中山公用（000685）
结合三大策略进行综合评估
"""
import requests
import pandas as pd
import numpy as np
import os
from datetime import datetime
import json

def log(msg):
    print(msg, flush=True)

for key in list(os.environ.keys()):
    if 'proxy' in key.lower():
        del os.environ[key]

session = requests.Session()
session.trust_env = False
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
})


def get_stock_kline(code, days=250):
    """获取日K线"""
    code = str(code).zfill(6)
    kcode = f'sh{code}' if code.startswith('6') else f'sz{code}'
    url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={kcode},day,,,{days},qfq'
    try:
        r = session.get(url, timeout=10)
        data = r.json()
        if not data.get('data'):
            return None
        stock_data = data['data'].get(kcode) or data['data'].get(kcode.upper())
        if not stock_data or 'qfqday' not in stock_data:
            return None
        days_data = stock_data['qfqday']
        df = pd.DataFrame([d[:6] for d in days_data], 
                        columns=['日期','开盘','收盘','最高','最低','成交量'])
        for col in ['开盘','收盘','最高','最低','成交量']:
            df[col] = df[col].astype(float)
        df['日期'] = pd.to_datetime(df['日期'])
        df['涨跌幅'] = df['收盘'].pct_change() * 100
        return df
    except Exception as e:
        log(f"获取数据失败: {e}")
        return None


def get_5min_kline(code):
    """获取5分钟K线"""
    code = str(code).zfill(6)
    symbol = f'sh{code}' if code.startswith('6') else f'sz{code}'
    url = f'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData?symbol={symbol}&scale=5&ma=no&datalen=100'
    try:
        r = session.get(url, timeout=15)
        text = r.text
        if not text or text == 'null':
            return None
        data = json.loads(text)
        if not data or len(data) < 20:
            return None
        df = pd.DataFrame(data)
        df['day'] = pd.to_datetime(df['day'])
        df['date'] = df['day'].dt.strftime('%Y%m%d')
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
        df = df.rename(columns={
            'open': '开盘', 'high': '最高', 'low': '最低', 
            'close': '收盘', 'volume': '成交量', 'day': '时间'
        })
        return df
    except:
        return None


def get_stock_name(code):
    """获取股票名称"""
    code = str(code).zfill(6)
    kcode = f'sh{code}' if code.startswith('6') else f'sz{code}'
    try:
        url = f'https://qt.gtimg.cn/q={kcode}'
        r = session.get(url, timeout=5)
        parts = r.text.split('~')
        if len(parts) > 1:
            return parts[1]
    except:
        pass
    return code


def analyze_stock(code):
    log("="*70)
    log(f"个股深度分析 - {code}")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*70)
    
    # 获取数据
    name = get_stock_name(code)
    log(f"\n股票: {code} {name}")
    
    df = get_stock_kline(code, 250)
    if df is None or len(df) < 60:
        log("无法获取足够的历史数据")
        return
    
    df_5min = get_5min_kline(code)
    
    log(f"数据范围: {df.iloc[0]['日期'].strftime('%Y-%m-%d')} ~ {df.iloc[-1]['日期'].strftime('%Y-%m-%d')}")
    log(f"共 {len(df)} 个交易日")
    
    # ==================== 基本面数据 ====================
    log("\n" + "="*70)
    log("一、基本走势分析")
    log("="*70)
    
    current = df.iloc[-1]
    log(f"\n【最新价格】")
    log(f"  收盘价: {current['收盘']:.2f}")
    log(f"  今日涨跌: {current['涨跌幅']:+.2f}%")
    
    # 近期涨跌
    log(f"\n【近期涨跌】")
    for days in [5, 10, 20, 60]:
        if len(df) >= days:
            ret = (df.iloc[-1]['收盘'] - df.iloc[-days]['收盘']) / df.iloc[-days]['收盘'] * 100
            log(f"  近{days}日: {ret:+.2f}%")
    
    # 均线位置
    log(f"\n【均线分析】")
    ma5 = df['收盘'].iloc[-5:].mean()
    ma10 = df['收盘'].iloc[-10:].mean()
    ma20 = df['收盘'].iloc[-20:].mean()
    ma60 = df['收盘'].iloc[-60:].mean() if len(df) >= 60 else None
    
    log(f"  5日均线: {ma5:.2f} ({'上方' if current['收盘'] > ma5 else '下方'})")
    log(f"  10日均线: {ma10:.2f} ({'上方' if current['收盘'] > ma10 else '下方'})")
    log(f"  20日均线: {ma20:.2f} ({'上方' if current['收盘'] > ma20 else '下方'})")
    if ma60:
        log(f"  60日均线: {ma60:.2f} ({'上方' if current['收盘'] > ma60 else '下方'})")
    
    # 成交量分析
    log(f"\n【成交量分析】")
    vol_5d = df['成交量'].iloc[-5:].mean()
    vol_20d = df['成交量'].iloc[-20:].mean()
    vol_ratio = vol_5d / vol_20d if vol_20d > 0 else 1
    log(f"  5日平均量: {vol_5d/10000:.0f}万")
    log(f"  20日平均量: {vol_20d/10000:.0f}万")
    log(f"  量比: {vol_ratio:.2f} ({'放量' if vol_ratio > 1.2 else '缩量' if vol_ratio < 0.8 else '平量'})")
    
    # 波动率
    log(f"\n【波动率分析】")
    volatility_20d = df['涨跌幅'].iloc[-20:].std()
    log(f"  近20日波动率: {volatility_20d:.2f}%")
    log(f"  波动特征: {'高波动' if volatility_20d > 3 else '中等波动' if volatility_20d > 2 else '低波动'}")
    
    # ==================== 策略分析 ====================
    log("\n" + "="*70)
    log("二、策略信号分析")
    log("="*70)
    
    # 策略1：分时托单
    log("\n【策略1：分时托单】")
    if df_5min is not None:
        latest_date = df_5min['date'].max()
        day_bars = df_5min[df_5min['date'] == latest_date].copy()
        
        if len(day_bars) >= 20:
            high = day_bars['最高'].max()
            low = day_bars['最低'].min()
            avg_price = day_bars['收盘'].mean()
            current_5min = day_bars.iloc[-1]['收盘']
            open_price = day_bars.iloc[0]['开盘']
            
            volatility = (high - low) / avg_price * 100
            
            day_bars['下影线'] = day_bars.apply(
                lambda x: min(x['开盘'], x['收盘']) - x['最低'], axis=1)
            day_bars['实体'] = abs(day_bars['收盘'] - day_bars['开盘'])
            support_bars = day_bars[day_bars['下影线'] > day_bars['实体'] * 0.5]
            support_count = len(support_bars)
            
            day_bars['涨跌'] = day_bars['收盘'] - day_bars['开盘']
            down_bars = day_bars[day_bars['涨跌'] < 0]
            up_bars = day_bars[day_bars['涨跌'] > 0]
            
            if len(down_bars) > 0 and len(up_bars) > 0:
                avg_down_vol = down_bars['成交量'].mean()
                avg_up_vol = up_bars['成交量'].mean()
                vol_ratio_5min = avg_up_vol / avg_down_vol if avg_down_vol > 0 else 1
            else:
                vol_ratio_5min = 1
            
            position = (current_5min - low) / (high - low) * 100 if high > low else 50
            today_change = (current_5min - open_price) / open_price * 100
            
            log(f"  分时波动: {volatility:.2f}% ({'符合' if volatility < 5 else '不符合'}横盘)")
            log(f"  托单次数: {support_count}次 ({'符合' if support_count >= 5 else '不足'})")
            log(f"  量比: {vol_ratio_5min:.2f} ({'符合' if vol_ratio_5min >= 1.2 else '不足'})")
            log(f"  收盘位置: {position:.0f}% ({'符合' if position >= 80 else '不足'})")
            log(f"  今日涨跌: {today_change:+.2f}%")
            
            # 评分
            score = 0
            if volatility < 5: score += 20
            if support_count >= 5: score += 20
            if vol_ratio_5min >= 1.2: score += 40
            if position >= 80: score += 20
            
            log(f"\n  分时托单评分: {score}/100")
            if score >= 60:
                log(f"  ★ 符合分时托单条件")
            else:
                log(f"  ✗ 不符合分时托单条件")
        else:
            log("  分时数据不足")
    else:
        log("  无法获取分时数据")
    
    # 策略2：涨停板破位洗盘
    log("\n【策略2：涨停板破位洗盘】")
    
    # 找近60天内的涨停
    recent_60d = df.iloc[-60:]
    limit_up_days = recent_60d[recent_60d['涨跌幅'] > 9.5]
    
    if len(limit_up_days) > 0:
        log(f"  近60天涨停次数: {len(limit_up_days)}次")
        
        # 取最近的涨停
        limit_up_idx = df.index.get_loc(limit_up_days.index[-1])
        days_since = len(df) - 1 - limit_up_idx
        limit_high = df.iloc[limit_up_idx]['最高']
        limit_date = df.iloc[limit_up_idx]['日期'].strftime('%Y-%m-%d')
        
        log(f"  最近涨停: {limit_date}")
        log(f"  涨停后天数: {days_since}天")
        log(f"  涨停高点: {limit_high:.2f}")
        
        # 回调幅度
        pullback = (current['收盘'] - limit_high) / limit_high * 100
        log(f"  回调幅度: {pullback:.1f}%")
        
        # 量能萎缩
        vol_recent = df.iloc[-5:]['成交量'].mean()
        vol_before = df.iloc[limit_up_idx:limit_up_idx+5]['成交量'].mean() if limit_up_idx + 5 < len(df) else vol_recent
        vol_shrink = vol_recent / vol_before if vol_before > 0 else 1
        log(f"  量能变化: {vol_shrink:.2f} ({'缩量' if vol_shrink < 0.8 else '正常'})")
        
        if 3 <= days_since <= 20 and -15 <= pullback <= -3 and vol_shrink < 1.2:
            log(f"\n  ★ 符合涨停洗盘条件")
        else:
            log(f"\n  ✗ 不符合涨停洗盘条件")
            if days_since < 3:
                log(f"    原因: 涨停后时间太短")
            elif days_since > 20:
                log(f"    原因: 涨停后时间太长")
            elif pullback > -3:
                log(f"    原因: 回调不足")
            elif pullback < -15:
                log(f"    原因: 回调过深")
    else:
        log(f"  近60天无涨停")
        log(f"  ✗ 不符合涨停洗盘条件")
    
    # 策略3：趋势分析（替代板块异动，因为这是个股）
    log("\n【策略3：趋势形态分析】")
    
    # 近期走势
    high_60d = df['最高'].iloc[-60:].max()
    low_60d = df['最低'].iloc[-60:].min()
    current_pos = (current['收盘'] - low_60d) / (high_60d - low_60d) * 100
    
    log(f"  60日最高: {high_60d:.2f}")
    log(f"  60日最低: {low_60d:.2f}")
    log(f"  当前位置: {current_pos:.0f}%（相对60日区间）")
    
    # 趋势判断
    if current['收盘'] > ma5 > ma10 > ma20:
        trend = "多头排列"
    elif current['收盘'] < ma5 < ma10 < ma20:
        trend = "空头排列"
    else:
        trend = "震荡整理"
    log(f"  均线趋势: {trend}")
    
    # 支撑压力
    log(f"\n【支撑压力位】")
    
    # 简单支撑压力
    recent_highs = df['最高'].iloc[-20:].nlargest(3).mean()
    recent_lows = df['最低'].iloc[-20:].nsmallest(3).mean()
    
    log(f"  短期压力: {recent_highs:.2f}")
    log(f"  短期支撑: {recent_lows:.2f}")
    log(f"  距压力: {(recent_highs - current['收盘'])/current['收盘']*100:+.1f}%")
    log(f"  距支撑: {(recent_lows - current['收盘'])/current['收盘']*100:+.1f}%")
    
    # ==================== 历史回测 ====================
    log("\n" + "="*70)
    log("三、历史信号回测")
    log("="*70)
    
    # 找历史上类似的信号
    signals = []
    for idx in range(60, len(df) - 5):
        row = df.iloc[idx]
        
        # 条件：近3日横盘 + 下影线
        recent_3d = df.iloc[idx-3:idx]
        high_3d = recent_3d['最高'].max()
        low_3d = recent_3d['最低'].min()
        volatility_3d = (high_3d - low_3d) / recent_3d['收盘'].mean() * 100
        
        # 下影线
        body_low = min(row['开盘'], row['收盘'])
        lower_shadow = body_low - row['最低']
        amplitude = row['最高'] - row['最低']
        
        if amplitude > 0 and volatility_3d < 5:
            lower_shadow_ratio = lower_shadow / amplitude * 100
            
            if lower_shadow_ratio > 30:
                # 计算未来收益
                future_3d = (df.iloc[idx+3]['收盘'] - row['收盘']) / row['收盘'] * 100
                future_5d = (df.iloc[idx+5]['收盘'] - row['收盘']) / row['收盘'] * 100
                
                signals.append({
                    'date': row['日期'],
                    'close': row['收盘'],
                    'lower_shadow': lower_shadow_ratio,
                    'volatility': volatility_3d,
                    'future_3d': future_3d,
                    'future_5d': future_5d,
                })
    
    if signals:
        df_signals = pd.DataFrame(signals)
        log(f"\n历史类似信号: {len(df_signals)}个")
        
        win_rate_3d = (df_signals['future_3d'] > 0).sum() / len(df_signals) * 100
        win_rate_5d = (df_signals['future_5d'] > 0).sum() / len(df_signals) * 100
        avg_3d = df_signals['future_3d'].mean()
        avg_5d = df_signals['future_5d'].mean()
        
        log(f"\n【历史表现】")
        log(f"  3日胜率: {win_rate_3d:.1f}%")
        log(f"  3日均收: {avg_3d:+.2f}%")
        log(f"  5日胜率: {win_rate_5d:.1f}%")
        log(f"  5日均收: {avg_5d:+.2f}%")
        
        log(f"\n【近期信号案例】")
        for i, row in df_signals.tail(5).iterrows():
            log(f"  {row['date'].strftime('%Y-%m-%d')}: 3日{row['future_3d']:+.1f}%, 5日{row['future_5d']:+.1f}%")
    else:
        log("\n无历史类似信号")
    
    # ==================== 综合评估 ====================
    log("\n" + "="*70)
    log("四、综合评估")
    log("="*70)
    
    # 计算综合评分
    total_score = 0
    
    # 趋势评分
    if trend == "多头排列":
        total_score += 30
        trend_comment = "趋势向好"
    elif trend == "空头排列":
        total_score -= 10
        trend_comment = "趋势偏弱"
    else:
        total_score += 10
        trend_comment = "趋势中性"
    
    # 位置评分
    if 30 <= current_pos <= 70:
        total_score += 20
        pos_comment = "位置适中"
    elif current_pos < 30:
        total_score += 30
        pos_comment = "低位区域，反弹潜力"
    else:
        total_score += 5
        pos_comment = "高位区域，注意风险"
    
    # 量能评分
    if 0.8 <= vol_ratio <= 1.5:
        total_score += 15
        vol_comment = "量能健康"
    elif vol_ratio > 1.5:
        total_score += 20
        vol_comment = "放量活跃"
    else:
        total_score += 5
        vol_comment = "缩量低迷"
    
    # 波动评分
    if volatility_20d < 2:
        total_score += 15
        volatility_comment = "波动较小，适合稳健投资"
    elif volatility_20d < 3:
        total_score += 10
        volatility_comment = "波动适中"
    else:
        total_score += 5
        volatility_comment = "波动较大，注意控制仓位"
    
    log(f"\n【评分明细】")
    log(f"  趋势: {trend_comment}")
    log(f"  位置: {pos_comment}")
    log(f"  量能: {vol_comment}")
    log(f"  波动: {volatility_comment}")
    log(f"\n【综合评分】{total_score}/100")
    
    # 操作建议
    log(f"\n【操作建议】")
    if total_score >= 70:
        log(f"  评级: ★★★ 积极关注")
        log(f"  策略: 可以考虑分批建仓")
    elif total_score >= 50:
        log(f"  评级: ★★ 观望为主")
        log(f"  策略: 等待更好的买点")
    else:
        log(f"  评级: ★ 暂不推荐")
        log(f"  策略: 观察为主，等待趋势转好")
    
    log(f"\n【风险提示】")
    log(f"  - 该股属于公用事业板块，波动相对较小")
    log(f"  - 不符合分时托单策略的高胜率条件（科技股效果更好）")
    log(f"  - 建议配合大盘走势和板块轮动判断")


if __name__ == "__main__":
    analyze_stock("000685")
