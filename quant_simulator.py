# -*- coding: utf-8 -*-
"""
量化模拟交易系统
=====================================
模拟机构量化操作
- 本金：10万
- 规则：T+1
- 策略：基于之前回测验证的散户心理反向策略
"""
import requests
import pandas as pd
import numpy as np
import os
import json
from datetime import datetime, timedelta
import time

for key in list(os.environ.keys()):
    if 'proxy' in key.lower():
        del os.environ[key]

session = requests.Session()
session.trust_env = False
session.headers.update({'User-Agent': 'Mozilla/5.0'})

# ================== 配置 ==================
INITIAL_CAPITAL = 100000  # 初始资金10万
DATA_FILE = 'd:/量化/quant_ai/portfolio.json'

# 交易成本
COMMISSION = 0.0003  # 佣金万三
STAMP_TAX = 0.001    # 印花税千一（卖出）


def get_realtime_quote(code):
    """获取实时行情"""
    code = str(code).zfill(6)
    kcode = f'sh{code}' if code.startswith('6') else f'sz{code}'
    url = f'http://qt.gtimg.cn/q={kcode}'
    try:
        r = session.get(url, timeout=10)
        text = r.text
        if '~' not in text:
            return None
        parts = text.split('~')
        return {
            'code': code,
            'name': parts[1],
            'price': float(parts[3]),
            'yesterday_close': float(parts[4]),
            'open': float(parts[5]),
            'high': float(parts[33]) if len(parts) > 33 and parts[33] else float(parts[3]),
            'low': float(parts[34]) if len(parts) > 34 and parts[34] else float(parts[3]),
            'volume': float(parts[6]) if parts[6] else 0,
            'amount': float(parts[37]) if len(parts) > 37 and parts[37] else 0,
            'change': float(parts[32]) if len(parts) > 32 and parts[32] else 0,
            'change_pct': float(parts[32]) if len(parts) > 32 and parts[32] else 0,
            'time': parts[30] if len(parts) > 30 else '',
        }
    except Exception as e:
        return None


def get_stock_kline(code, days=60):
    """获取日K线数据"""
    code = str(code).zfill(6)
    kcode = f'sh{code}' if code.startswith('6') else f'sz{code}'
    url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={kcode},day,,,{days},qfq'
    try:
        r = session.get(url, timeout=15)
        data = r.json()
        if not data.get('data'):
            return None
        stock_data = data['data'].get(kcode) or data['data'].get(kcode.upper())
        if not stock_data or 'qfqday' not in stock_data:
            return None
        days_data = stock_data['qfqday']
        df = pd.DataFrame([d[:6] for d in days_data], 
                        columns=['date','open','close','high','low','volume'])
        for col in ['open','close','high','low','volume']:
            df[col] = df[col].astype(float)
        df['change'] = df['close'].pct_change() * 100
        return df
    except:
        return None


def load_portfolio():
    """加载投资组合"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {
        'cash': INITIAL_CAPITAL,
        'positions': {},  # {code: {'shares': x, 'cost': y, 'buy_date': 'YYYY-MM-DD', 'name': 'xxx'}}
        'history': [],    # 交易历史
        'daily_value': [],  # 每日净值
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }


def save_portfolio(portfolio):
    """保存投资组合"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(portfolio, f, ensure_ascii=False, indent=2)


def calculate_portfolio_value(portfolio):
    """计算投资组合总价值"""
    total = portfolio['cash']
    positions_value = 0
    
    for code, pos in portfolio['positions'].items():
        quote = get_realtime_quote(code)
        if quote:
            value = pos['shares'] * quote['price']
            positions_value += value
            pos['current_price'] = quote['price']
            pos['current_value'] = value
            pos['pnl'] = value - pos['shares'] * pos['cost']
            pos['pnl_pct'] = (quote['price'] - pos['cost']) / pos['cost'] * 100
    
    total += positions_value
    return total, positions_value


def analyze_stock(code):
    """分析股票，给出评分和信号"""
    df = get_stock_kline(code, 60)
    if df is None or len(df) < 30:
        return None
    
    quote = get_realtime_quote(code)
    if not quote:
        return None
    
    score = 50  # 基础分
    signals = []
    
    # ================== 基于散户心理的反向策略 ==================
    
    # 1. 检查是否连续下跌（散户恐慌，可能是机会）
    recent_3d = df.tail(3)
    if all(recent_3d['change'] < 0):
        total_drop = recent_3d['change'].sum()
        if total_drop < -8:
            # 连跌太多，等企稳再买
            score -= 20
            signals.append(f'连跌3天累计{total_drop:.1f}%，不接飞刀')
        elif total_drop > -5:
            # 小幅连跌，观察
            score += 5
            signals.append(f'小幅调整{total_drop:.1f}%')
    
    # 2. 检查是否企稳（之前跌，现在止跌）
    if len(df) >= 10:
        prev_5d = df.iloc[-10:-5]
        recent_5d = df.tail(5)
        prev_change = (prev_5d.iloc[-1]['close'] - prev_5d.iloc[0]['close']) / prev_5d.iloc[0]['close'] * 100
        recent_change = (recent_5d.iloc[-1]['close'] - recent_5d.iloc[0]['close']) / recent_5d.iloc[0]['close'] * 100
        
        if prev_change < -5 and recent_change > -2:
            score += 15
            signals.append('之前下跌，近期企稳')
    
    # 3. 检查20日位置（避免追高）
    if len(df) >= 20:
        high_20d = df.tail(20)['high'].max()
        low_20d = df.tail(20)['low'].min()
        pos_20d = (quote['price'] - low_20d) / (high_20d - low_20d) * 100 if high_20d != low_20d else 50
        
        if pos_20d > 80:
            score -= 25
            signals.append(f'20日位置{pos_20d:.0f}%，偏高不追')
        elif pos_20d < 30:
            score += 15
            signals.append(f'20日位置{pos_20d:.0f}%，相对低位')
    
    # 4. 检查成交量（缩量企稳好于放量下跌）
    if len(df) >= 10:
        vol_5d = df.tail(5)['volume'].mean()
        vol_10d = df.tail(10)['volume'].mean()
        vol_ratio = vol_5d / vol_10d
        
        if vol_ratio < 0.7 and recent_change > -3:
            score += 10
            signals.append('缩量整理')
        elif vol_ratio > 1.5 and quote['change'] < -3:
            score -= 15
            signals.append('放量下跌，观望')
    
    # 5. 今日涨跌（避免追涨）
    if quote['change'] > 5:
        score -= 20
        signals.append(f'今日涨{quote["change"]:.1f}%，不追')
    elif quote['change'] < -5:
        score -= 10
        signals.append(f'今日跌{quote["change"]:.1f}%，等企稳')
    elif -1 < quote['change'] < 1:
        score += 5
        signals.append('今日平稳')
    
    # 6. 开盘情况（避免高开追买）
    open_change = (quote['open'] - quote['yesterday_close']) / quote['yesterday_close'] * 100
    if open_change > 2:
        score -= 10
        signals.append(f'高开{open_change:.1f}%')
    elif open_change < -2 and quote['change'] > open_change:
        score += 10
        signals.append('低开高走')
    
    # 7. 股价过滤（只买入股价<20元的中小市值）
    if quote['price'] > 20:
        score -= 30
        signals.append(f'股价{quote["price"]:.0f}元，超过20元不买')
    
    return {
        'code': code,
        'name': quote['name'],
        'price': quote['price'],
        'change': quote['change'],
        'score': min(max(score, 0), 100),
        'signals': signals,
        'recommend': 'buy' if score >= 65 else ('hold' if score >= 45 else 'avoid'),
    }


def scan_stocks():
    """扫描股票池"""
    # 股票池（主板中小市值，股价<20元，约100亿市值以内）
    stock_pool = [
        # 科技/电子（确认低价<20元）
        ('002456', '欧菲光'),      # ~10元
        ('000727', '冠捷科技'),    # ~3元
        ('002106', '莱宝高科'),    # ~11元
        ('000100', 'TCL科技'),     # ~5元
        ('000725', '京东方A'),     # ~4元
        ('002217', '合力泰'),      # ~5元
        ('002036', '联创电子'),    # ~8元
        # 新能源/汽车（确认低价<20元）
        ('000625', '长安汽车'),    # ~11元
        ('002013', '中航机电'),    # ~10元
        ('601127', '赛力斯'),      # ~15元（需确认）
        ('002048', '宁波华翔'),    # ~15元
        # 军工/制造（确认低价<20元）
        ('002414', '高德红外'),    # ~17元
        ('600765', '中航重机'),    # ~15元（需确认）
        ('600677', '航天通信'),    # ~8元
        ('600501', '航天晨光'),    # ~10元
        # 医药/消费（确认低价<20元）
        ('600998', '九州通'),      # ~5元
        ('002038', '双鹭药业'),    # ~12元
        ('000028', '国药一致'),    # ~18元（需确认）
        # 其他活跃低价股
        ('601108', '财通证券'),    # ~10元
        ('000623', '吉林敖东'),    # ~18元
        ('002027', '分众传媒'),    # ~6元
        ('600030', '中信证券'),    # ~18元（需确认）
    ]
    
    results = []
    print("\n扫描股票...")
    
    for code, name in stock_pool:
        analysis = analyze_stock(code)
        if analysis:
            results.append(analysis)
            status = '买入' if analysis['recommend'] == 'buy' else ('持有' if analysis['recommend'] == 'hold' else '回避')
            print(f"  {code} {analysis['name']}: {analysis['price']:.2f} ({analysis['change']:+.1f}%) 评分:{analysis['score']} [{status}]")
        time.sleep(0.1)
    
    results.sort(key=lambda x: x['score'], reverse=True)
    return results


def execute_buy(portfolio, code, amount):
    """执行买入"""
    quote = get_realtime_quote(code)
    if not quote:
        print(f"无法获取{code}行情")
        return False
    
    price = quote['price']
    shares = int(amount / price / 100) * 100  # 整手
    
    if shares < 100:
        print("资金不足一手")
        return False
    
    cost = shares * price
    commission = max(cost * COMMISSION, 5)  # 最低5元
    total_cost = cost + commission
    
    if total_cost > portfolio['cash']:
        print(f"资金不足: 需要{total_cost:.2f}, 可用{portfolio['cash']:.2f}")
        return False
    
    # 更新持仓
    if code in portfolio['positions']:
        old_pos = portfolio['positions'][code]
        new_shares = old_pos['shares'] + shares
        new_cost = (old_pos['shares'] * old_pos['cost'] + cost) / new_shares
        portfolio['positions'][code] = {
            'shares': new_shares,
            'cost': new_cost,
            'buy_date': datetime.now().strftime('%Y-%m-%d'),
            'name': quote['name'],
        }
    else:
        portfolio['positions'][code] = {
            'shares': shares,
            'cost': price,
            'buy_date': datetime.now().strftime('%Y-%m-%d'),
            'name': quote['name'],
        }
    
    portfolio['cash'] -= total_cost
    
    # 记录交易
    portfolio['history'].append({
        'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'type': 'buy',
        'code': code,
        'name': quote['name'],
        'price': price,
        'shares': shares,
        'amount': cost,
        'commission': commission,
    })
    
    print(f"买入成功: {code} {quote['name']} {shares}股 @ {price:.2f}, 花费{total_cost:.2f}")
    return True


def execute_sell(portfolio, code, shares=None):
    """执行卖出"""
    if code not in portfolio['positions']:
        print(f"没有持仓{code}")
        return False
    
    pos = portfolio['positions'][code]
    if shares is None:
        shares = pos['shares']
    
    # 检查T+1
    buy_date = datetime.strptime(pos['buy_date'], '%Y-%m-%d').date()
    today = datetime.now().date()
    if buy_date >= today:
        print(f"T+1限制: {code}是今天买入的，明天才能卖")
        return False
    
    quote = get_realtime_quote(code)
    if not quote:
        print(f"无法获取{code}行情")
        return False
    
    price = quote['price']
    amount = shares * price
    commission = max(amount * COMMISSION, 5)
    stamp_tax = amount * STAMP_TAX
    net_amount = amount - commission - stamp_tax
    
    # 更新持仓
    if shares >= pos['shares']:
        del portfolio['positions'][code]
    else:
        portfolio['positions'][code]['shares'] -= shares
    
    portfolio['cash'] += net_amount
    
    # 计算盈亏
    pnl = (price - pos['cost']) * shares - commission - stamp_tax
    pnl_pct = (price - pos['cost']) / pos['cost'] * 100
    
    # 记录交易
    portfolio['history'].append({
        'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'type': 'sell',
        'code': code,
        'name': quote['name'],
        'price': price,
        'shares': shares,
        'amount': amount,
        'commission': commission,
        'stamp_tax': stamp_tax,
        'pnl': pnl,
        'pnl_pct': pnl_pct,
    })
    
    pnl_str = f"+{pnl:.2f}" if pnl > 0 else f"{pnl:.2f}"
    print(f"卖出成功: {code} {quote['name']} {shares}股 @ {price:.2f}, 收入{net_amount:.2f}, 盈亏{pnl_str}")
    return True


def show_portfolio(portfolio):
    """显示投资组合"""
    print("\n" + "="*70)
    print("投资组合")
    print("="*70)
    
    total_value, positions_value = calculate_portfolio_value(portfolio)
    
    print(f"\n现金: {portfolio['cash']:.2f}")
    print(f"持仓市值: {positions_value:.2f}")
    print(f"总资产: {total_value:.2f}")
    print(f"总收益: {total_value - INITIAL_CAPITAL:+.2f} ({(total_value/INITIAL_CAPITAL - 1)*100:+.2f}%)")
    
    if portfolio['positions']:
        print("\n持仓明细:")
        print("-"*70)
        for code, pos in portfolio['positions'].items():
            quote = get_realtime_quote(code)
            if quote:
                current_value = pos['shares'] * quote['price']
                pnl = current_value - pos['shares'] * pos['cost']
                pnl_pct = (quote['price'] - pos['cost']) / pos['cost'] * 100
                print(f"  {code} {pos['name']}")
                print(f"    持仓: {pos['shares']}股, 成本: {pos['cost']:.2f}")
                print(f"    现价: {quote['price']:.2f} ({quote['change']:+.1f}%)")
                print(f"    市值: {current_value:.2f}, 盈亏: {pnl:+.2f} ({pnl_pct:+.1f}%)")
                print(f"    买入日: {pos['buy_date']}")


def auto_trade(portfolio, auto_execute=False):
    """自动交易逻辑
    
    auto_execute: False=只分析不交易(默认), True=自动执行交易
    """
    print("\n" + "="*70)
    print("市场分析 (观察模式)" if not auto_execute else "自动交易")
    print("="*70)
    
    # 1. 先检查持仓状态
    if portfolio['positions']:
        print("\n【持仓监控】")
        for code in list(portfolio['positions'].keys()):
            pos = portfolio['positions'][code]
            quote = get_realtime_quote(code)
            if not quote:
                continue
            
            pnl_pct = (quote['price'] - pos['cost']) / pos['cost'] * 100
            buy_date = datetime.strptime(pos['buy_date'], '%Y-%m-%d').date()
            can_sell = buy_date < datetime.now().date()
            
            if pnl_pct < -5:
                print(f"  [止损警告] {code} {pos['name']} 亏损{pnl_pct:.1f}%")
                if can_sell and auto_execute:
                    execute_sell(portfolio, code)
                elif can_sell:
                    print(f"    -> 建议止损，输入 sell {code} 执行")
                else:
                    print(f"    -> T+1限制，明天可卖")
            elif pnl_pct > 8:
                print(f"  [止盈信号] {code} {pos['name']} 盈利{pnl_pct:.1f}%")
                if can_sell and auto_execute:
                    sell_shares = int(pos['shares'] / 2 / 100) * 100
                    if sell_shares >= 100:
                        execute_sell(portfolio, code, sell_shares)
                elif can_sell:
                    print(f"    -> 建议止盈一半，输入 sell {code} 执行")
            else:
                status = "盈利" if pnl_pct > 0 else "亏损"
                print(f"  {code} {pos['name']}: {status}{abs(pnl_pct):.1f}%, 继续持有")
    
    # 2. 扫描股票池
    results = scan_stocks()
    
    # 3. 分析买入机会（不自动执行）
    buy_candidates = [r for r in results if r['recommend'] == 'buy']
    hold_candidates = [r for r in results if r['recommend'] == 'hold' and r['score'] >= 55]
    
    print("\n" + "="*70)
    print("【买入候选】")
    print("="*70)
    
    if buy_candidates:
        print(f"\n发现{len(buy_candidates)}个买入信号（需进一步观察）:\n")
        for i, c in enumerate(buy_candidates[:5], 1):
            print(f"  {i}. {c['code']} {c['name']}")
            print(f"     价格: {c['price']:.2f} ({c['change']:+.1f}%)")
            print(f"     评分: {c['score']}")
            print(f"     信号: {', '.join(c['signals'][:3])}")
            print()
        
        # 给出建议，但不自动买入
        best = buy_candidates[0]
        total_value, _ = calculate_portfolio_value(portfolio)
        position_count = len(portfolio['positions'])
        
        print("-"*70)
        print("【决策分析】")
        if position_count >= 3:
            print("  仓位已满(3只)，暂不买入")
        elif best['score'] >= 75:
            print(f"\n  分析: {best['code']} {best['name']}")
            print(f"  - 评分: {best['score']} (>=75，达到买入标准)")
            print(f"  - 价格: {best['price']:.2f}元 (<20元，符合中小市值)")
            print(f"  - 信号: {', '.join(best['signals'])}")
            print(f"  - 仓位: {min(total_value * 0.3, 30000):.0f}元 (30%)")
            print(f"\n  结论: 符合买入条件，执行买入")
            print("-"*70)
            
            # 执行买入
            invest_amount = min(portfolio['cash'] * 0.5, total_value * 0.3, 30000)
            if invest_amount > 10000:
                execute_buy(portfolio, best['code'], invest_amount)
        elif best['score'] >= 65:
            print(f"\n  分析: {best['code']} {best['name']}")
            print(f"  - 评分: {best['score']} (65-74，接近但未达标)")
            print(f"  - 信号: {', '.join(best['signals'])}")
            print(f"\n  结论: 继续观察，暂不买入")
    else:
        print("\n  暂无符合条件的买入信号")
        print("  建议继续观望，等待更好的机会")
    
    # 显示可关注的股票
    if hold_candidates:
        print("\n【观察池】(评分55-64，接近买入条件)")
        for c in hold_candidates[:3]:
            print(f"  - {c['code']} {c['name']}: {c['price']:.2f} 评分{c['score']}")
    
    save_portfolio(portfolio)


def run_simulator():
    """运行模拟器"""
    print("="*70)
    print("量化模拟交易系统")
    print("="*70)
    print(f"初始资金: {INITIAL_CAPITAL:,}")
    print(f"规则: T+1")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 加载投资组合
    portfolio = load_portfolio()
    
    # 显示当前状态
    show_portfolio(portfolio)
    
    # 执行自动交易
    auto_trade(portfolio)
    
    # 再次显示状态
    show_portfolio(portfolio)
    
    # 记录每日净值
    total_value, _ = calculate_portfolio_value(portfolio)
    portfolio['daily_value'].append({
        'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'value': total_value,
        'return': (total_value / INITIAL_CAPITAL - 1) * 100,
    })
    save_portfolio(portfolio)
    
    print("\n" + "="*70)
    print("交易完成")
    print("="*70)


if __name__ == "__main__":
    run_simulator()
