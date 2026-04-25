"""
诊断板块异动检测问题 - 修复代理问题
"""
import os
import sys

# 彻底清除代理
for key in list(os.environ.keys()):
    if 'proxy' in key.lower():
        del os.environ[key]

# 在导入akshare之前，先patch requests
import requests
_original_get = requests.get
_original_post = requests.post

def patched_get(*args, **kwargs):
    kwargs['proxies'] = {'http': None, 'https': None}
    kwargs.pop('proxy', None)
    return _original_get(*args, **kwargs)

def patched_post(*args, **kwargs):
    kwargs['proxies'] = {'http': None, 'https': None}
    kwargs.pop('proxy', None)
    return _original_post(*args, **kwargs)

requests.get = patched_get
requests.post = patched_post

def log(msg):
    print(msg, flush=True)

log("="*60)
log("板块异动检测诊断 V2 (已禁用代理)")
log("="*60)

# 1. 检查akshare
log("\n[1] 检查Akshare...")
try:
    import akshare as ak
    log(f"  Akshare版本: {ak.__version__}")
    HAS_AKSHARE = True
except Exception as e:
    log(f"  导入失败: {e}")
    HAS_AKSHARE = False

if not HAS_AKSHARE:
    log("\n无法继续，请先安装akshare: pip install akshare")
    exit()

# 2. 获取板块列表
log("\n[2] 获取板块列表...")
try:
    df = ak.stock_board_concept_name_em()
    log(f"  成功获取 {len(df)} 个板块")
    log(f"\n  前5个板块:")
    for i, row in df.head(5).iterrows():
        log(f"    {row['板块名称']} 涨跌幅:{row['涨跌幅']}%")
except Exception as e:
    log(f"  获取失败: {e}")
    import traceback
    traceback.print_exc()
    exit()

# 3. 获取单个板块成分股
log("\n[3] 获取板块成分股...")
test_sector = df.iloc[0]['板块名称']
log(f"  测试板块: {test_sector}")
try:
    cons = ak.stock_board_concept_cons_em(symbol=test_sector)
    log(f"  成功获取 {len(cons)} 只成分股")
    if len(cons) > 0:
        log(f"  前3只: {cons.head(3)['代码'].tolist()}")
except Exception as e:
    log(f"  获取失败: {e}")
    import traceback
    traceback.print_exc()
    cons = None

# 4. 获取个股历史数据
log("\n[4] 获取个股历史...")
if cons is not None and len(cons) > 0:
    test_code = cons.iloc[0]['代码']
    log(f"  测试股票: {test_code}")
    try:
        hist = ak.stock_zh_a_hist(symbol=test_code, period="daily", 
                                   start_date='20251001', adjust="qfq")
        log(f"  成功获取 {len(hist)} 天数据")
        log(f"  日期范围: {hist['日期'].iloc[0]} ~ {hist['日期'].iloc[-1]}")
    except Exception as e:
        log(f"  获取失败: {e}")

# 5. 完整测试板块异动检测
log("\n[5] 测试板块异动检测...")
import pandas as pd

def get_sector_history(sector_name):
    """获取板块历史走势"""
    try:
        cons = ak.stock_board_concept_cons_em(symbol=sector_name)
        if cons is None or len(cons) == 0:
            return None
        
        top_stocks = cons.head(3)['代码'].tolist()
        all_data = []
        
        for symbol in top_stocks:
            try:
                hist = ak.stock_zh_a_hist(symbol=symbol, period="daily", 
                                          start_date='20251001', adjust="qfq")
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


def detect_potential_sector(daily_returns):
    """检测板块是否有异动特征"""
    if daily_returns is None:
        return False, None, "无数据"
    
    if len(daily_returns) < 45:
        return False, None, f"数据不足({len(daily_returns)}天<45天)"
    
    daily_returns = daily_returns.dropna()
    if len(daily_returns) < 45:
        return False, None, f"有效数据不足"
    
    old_period = daily_returns.iloc[:-15]
    recent_15d = daily_returns.iloc[-15:]
    recent_5d = daily_returns.iloc[-5:]
    
    surge_days = old_period[old_period > 3.0]
    if len(surge_days) == 0:
        return False, None, "无早期爆发(>3%)"
    
    max_surge_value = surge_days.max()
    max_surge_idx = surge_days.idxmax()
    
    after_surge = daily_returns[daily_returns.index >= max_surge_idx]
    if len(after_surge) < 10:
        return False, None, "爆发后数据不足"
    
    cumsum = after_surge.cumsum()
    max_gain = cumsum.max()
    current_gain = cumsum.iloc[-1]
    drawdown = max_gain - current_gain
    
    recent_15d_sum = recent_15d.sum()
    recent_5d_sum = recent_5d.sum()
    
    if drawdown < 5:
        return False, None, f"回撤不足({drawdown:.1f}%<5%)"
    if drawdown > 15:
        return False, None, f"回撤过大({drawdown:.1f}%>15%)"
    if recent_15d_sum > 5:
        return False, None, f"近15日涨太多({recent_15d_sum:.1f}%)"
    if recent_5d_sum < -5:
        return False, None, f"近5日跌太多({recent_5d_sum:.1f}%)"
    
    return True, {
        'surge_date': max_surge_idx.strftime('%Y-%m-%d'),
        'surge_value': round(max_surge_value, 2),
        'drawdown': round(drawdown, 2),
        'recent_15d': round(recent_15d_sum, 2),
        'recent_5d': round(recent_5d_sum, 2)
    }, "符合条件"


# 测试前15个板块
log("\n  检测前15个板块:")
results = []
for i, row in df.head(15).iterrows():
    name = row['板块名称']
    log(f"\n  [{i+1}] {name}")
    
    data = get_sector_history(name)
    if data is None:
        log(f"      -> 无法获取历史数据")
        continue
    
    log(f"      数据: {len(data)}天")
    
    is_potential, details, reason = detect_potential_sector(data)
    
    if is_potential:
        log(f"      -> ✓ 符合条件!")
        log(f"         爆发{details['surge_date']} +{details['surge_value']}%")
        log(f"         回撤{details['drawdown']}% 近5日{details['recent_5d']:+.1f}%")
        results.append({'name': name, **details})
    else:
        log(f"      -> ✗ {reason}")

log("\n" + "="*60)
log(f"诊断完成: 发现 {len(results)} 个符合条件的板块")
if results:
    for r in results:
        log(f"  {r['name']}: 爆发{r['surge_date']} 回撤{r['drawdown']}%")
log("="*60)
