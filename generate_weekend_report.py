# -*- coding: utf-8 -*-
"""
周末报告V4 - 专门针对周一开盘的改进版
改进点：
1. 加入周末效应分析
2. 开盘预判
3. 高开不追的具体规则
4. 排除高位股
5. 更保守的推荐策略
"""
import requests
import pandas as pd
import numpy as np
import os
from datetime import datetime
import time
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

def log(msg):
    print(msg, flush=True)

for key in list(os.environ.keys()):
    if 'proxy' in key.lower():
        del os.environ[key]

session = requests.Session()
session.trust_env = False
session.headers.update({'User-Agent': 'Mozilla/5.0'})


def get_stock_kline(code, days=60):
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
                        columns=['date','open','close','high','low','volume'])
        for col in ['open','close','high','low','volume']:
            df[col] = df[col].astype(float)
        df['date'] = pd.to_datetime(df['date'])
        df['change'] = df['close'].pct_change() * 100
        return df
    except:
        return None


def get_index_kline(code='000001', days=60):
    kcode = f'sh{code}'
    url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={kcode},day,,,{days},qfq'
    try:
        r = session.get(url, timeout=10)
        data = r.json()
        stock_data = data['data'].get(kcode) or data['data'].get(kcode.upper())
        days_data = stock_data.get('qfqday') or stock_data.get('day')
        df = pd.DataFrame([d[:6] for d in days_data], 
                        columns=['date','open','close','high','low','volume'])
        for col in ['open','close','high','low','volume']:
            df[col] = df[col].astype(float)
        df['date'] = pd.to_datetime(df['date'])
        df['change'] = df['close'].pct_change() * 100
        return df
    except:
        return None


def get_stock_name(code):
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


def analyze_weekend_effect(df):
    """分析周末效应 - 周五收涨周一容易被砸"""
    if df is None or len(df) < 20:
        return 0, {}
    
    current = df.iloc[-1]  # 周五
    
    # 周五涨幅
    friday_change = current['change']
    
    # 周五收盘位置
    high = current['high']
    low = current['low']
    close = current['close']
    position = (close - low) / (high - low) * 100 if high > low else 50
    
    # 风险评估
    risk_score = 0
    risks = []
    
    # 1. 周五大涨风险
    if friday_change > 3:
        risk_score += 30
        risks.append('周五大涨，周一易回调')
    elif friday_change > 1.5:
        risk_score += 15
        risks.append('周五涨幅较大')
    
    # 2. 周五冲高回落
    if position < 50 and (high - close) / close * 100 > 1.5:
        risk_score += 20
        risks.append('周五冲高回落')
    
    # 3. 周五高位收盘
    if position > 90:
        risk_score += 15
        risks.append('周五收盘位置过高')
    
    # 近5日累计涨幅
    ret_5d = (current['close'] - df.iloc[-6]['close']) / df.iloc[-6]['close'] * 100
    if ret_5d > 10:
        risk_score += 25
        risks.append('近5日涨幅过大')
    elif ret_5d > 5:
        risk_score += 10
    
    return risk_score, {
        'friday_change': friday_change,
        'friday_position': position,
        'ret_5d': ret_5d,
        'risks': risks,
    }


def analyze_stock_conservative(code):
    """保守分析 - 更严格的筛选"""
    df = get_stock_kline(code, 60)
    if df is None or len(df) < 30:
        return None
    
    name = get_stock_name(code)
    if 'ST' in name or 'st' in name:
        return None
    
    current = df.iloc[-1]
    
    # 均线
    ma5 = df['close'].iloc[-5:].mean()
    ma10 = df['close'].iloc[-10:].mean()
    ma20 = df['close'].iloc[-20:].mean()
    
    # 20日位置 - 关键指标
    high_20d = df['high'].iloc[-20:].max()
    low_20d = df['low'].iloc[-20:].min()
    pos_20d = (current['close'] - low_20d) / (high_20d - low_20d) * 100 if high_20d > low_20d else 50
    
    # 近期涨幅
    ret_5d = (current['close'] - df.iloc[-6]['close']) / df.iloc[-6]['close'] * 100
    ret_10d = (current['close'] - df.iloc[-11]['close']) / df.iloc[-11]['close'] * 100
    
    # 量能
    vol_5d = df['volume'].iloc[-5:].mean()
    vol_20d = df['volume'].iloc[-20:].mean()
    vol_ratio = vol_5d / vol_20d if vol_20d > 0 else 1
    
    # 周末效应分析
    weekend_risk, weekend_info = analyze_weekend_effect(df)
    
    # 评分 - 保守版本
    score = 0
    risks = []
    
    # 1. 均线 (+25)
    if current['close'] > ma5 > ma10 > ma20:
        score += 25
    elif current['close'] > ma5 > ma10:
        score += 15
    elif current['close'] < ma5 < ma10:
        score -= 25
        risks.append('均线空头')
    
    # 2. 位置 - 更严格 (+25)
    if pos_20d > 80:
        score -= 35  # 高位直接大扣分
        risks.append('高位风险大')
    elif pos_20d > 65:
        score -= 15
        risks.append('位置偏高')
    elif 35 <= pos_20d <= 65:
        score += 25  # 中间位置最佳
    elif pos_20d < 35:
        score += 15
    
    # 3. 近期涨幅 - 更严格 (+20)
    if ret_5d > 6:
        score -= 30
        risks.append('短期涨太多')
    elif ret_5d > 3:
        score -= 10
    elif -2 <= ret_5d <= 3:
        score += 20
    elif ret_5d < -4:
        score -= 15
        risks.append('下跌趋势')
    
    # 4. 量能 (+15)
    if 0.9 <= vol_ratio <= 1.3:
        score += 15
    elif vol_ratio > 1.8:
        score -= 10
        risks.append('量能偏大')
    
    # 5. 周末风险扣分
    score -= weekend_risk
    if weekend_info.get('risks'):
        risks.extend(weekend_info['risks'])
    
    # 综合评级 - 更严格
    if score >= 45 and len(risks) == 0:
        rating = 'A'
        recommend = '可考虑'
    elif score >= 25 and len(risks) <= 1:
        rating = 'B'
        recommend = '观望'
    else:
        rating = 'C'
        recommend = '不推荐'
    
    return {
        'code': code,
        'name': name,
        'score': score,
        'rating': rating,
        'recommend': recommend,
        'pos_20d': pos_20d,
        'ret_5d': ret_5d,
        'ret_10d': ret_10d,
        'vol_ratio': vol_ratio,
        'price': current['close'],
        'friday_change': current['change'],
        'risks': risks,
        'weekend_risk': weekend_risk,
    }


def generate_weekend_report():
    """生成周末报告"""
    log("="*70)
    log("周末报告V4 - 周一开盘机会分析（保守版）")
    log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log("="*70)
    
    # 1. 分析大盘
    log("\n分析大盘...")
    df_index = get_index_kline('000001', 60)
    
    if df_index is not None:
        current = df_index.iloc[-1]
        friday_change = current['change']
        ret_5d = (current['close'] - df_index.iloc[-6]['close']) / df_index.iloc[-6]['close'] * 100
        
        ma5 = df_index['close'].iloc[-5:].mean()
        ma10 = df_index['close'].iloc[-10:].mean()
        ma20 = df_index['close'].iloc[-20:].mean()
        
        if current['close'] > ma5 > ma10 > ma20:
            market_trend = '多头'
        elif current['close'] < ma5 < ma10:
            market_trend = '空头'
        else:
            market_trend = '震荡'
        
        log(f"  周五涨跌: {friday_change:+.2f}%")
        log(f"  5日累计: {ret_5d:+.2f}%")
        log(f"  趋势: {market_trend}")
    else:
        friday_change = 0
        ret_5d = 0
        market_trend = '未知'
    
    # 2. 扫描个股
    log("\n扫描个股（保守筛选）...")
    
    # 股票池 - 主板中小盘
    stocks = {
        'AI': ['002230', '603019', '002410', '000977'],
        '半导体': ['002371', '603986', '002049', '002185'],
        '机器人': ['002747', '002527', '002472', '002008'],
        '新能源车': ['002074', '000625', '002129'],
        '光伏': ['601012', '002459', '600438', '002506'],
        '消费电子': ['002241', '002475', '002938'],
        '医药': ['000538', '002821', '000963'],
        '新材料': ['002080', '603799', '002340'],
    }
    
    all_stocks = []
    for sector, codes in stocks.items():
        for code in codes:
            result = analyze_stock_conservative(code)
            if result:
                result['sector'] = sector
                all_stocks.append(result)
            time.sleep(0.1)
    
    all_stocks.sort(key=lambda x: x['score'], reverse=True)
    
    a_stocks = [s for s in all_stocks if s['rating'] == 'A']
    b_stocks = [s for s in all_stocks if s['rating'] == 'B']
    
    log(f"\n  A级: {len(a_stocks)}只")
    log(f"  B级: {len(b_stocks)}只")
    
    # 3. 生成Word报告
    log("\n生成Word报告...")
    
    doc = Document()
    
    # 字体设置
    doc.styles['Normal'].font.name = 'Microsoft YaHei'
    doc.styles['Normal']._element.rPr.rFonts.set(qn('w:eastAsia'), 'Microsoft YaHei')
    doc.styles['Normal'].font.size = Pt(11)
    
    # 标题
    title = doc.add_heading('', 0)
    title.add_run('周一开盘机会分析')
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    date_para = doc.add_paragraph()
    date_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    date_run = date_para.add_run(f'分析时间：{datetime.now().strftime("%Y年%m月%d日")}（周日）')
    date_run.font.color.rgb = RGBColor(128, 128, 128)
    
    # ==================== 核心警告 ====================
    doc.add_heading('【重要提醒】', level=1)
    
    warning = doc.add_paragraph()
    warning.add_run('周一开盘风险提示：\n\n').bold = True
    warning.add_run('1. 高开不追：开盘涨幅>0.5%的股票，不要追买\n')
    warning.add_run('2. 观察30分钟：开盘后先看30分钟走势再决定\n')
    warning.add_run('3. 平开下杀放弃：平开后持续下跌不反弹，当日不做\n')
    warning.add_run('4. 控制仓位：周一第一时间最多买入计划仓位的1/3\n\n')
    
    # 周末效应提示
    if friday_change > 1:
        warning.add_run('【周末效应警告】').bold = True
        warning.add_run(f'\n周五大盘涨{friday_change:.2f}%，周一高开低走概率较大，建议观望为主！\n')
    
    # ==================== 开盘操作指南 ====================
    doc.add_heading('开盘操作指南', level=1)
    
    guide = doc.add_paragraph()
    guide.add_run('9:25 集合竞价\n').bold = True
    guide.add_run('- 观察竞价价格和成交量\n')
    guide.add_run('- 竞价高开>1%：放弃今日操作\n')
    guide.add_run('- 竞价低开>0.5%：放弃今日操作\n\n')
    
    guide.add_run('9:30-10:00 观察期\n').bold = True
    guide.add_run('- 不要急于下单，先观察30分钟\n')
    guide.add_run('- 如果持续下跌无反弹：放弃\n')
    guide.add_run('- 如果下探后能收回开盘价：可考虑\n\n')
    
    guide.add_run('10:00以后 决策\n').bold = True
    guide.add_run('- 股价站稳分时均线上方：可以轻仓介入\n')
    guide.add_run('- 股价在分时均线下方：继续观望\n')
    guide.add_run('- 大盘走弱：不操作\n')
    
    # ==================== 推荐股票 ====================
    doc.add_heading('本周关注（非即时买入）', level=1)
    
    note = doc.add_paragraph()
    note.add_run('注意：以下股票仅供本周关注，不是让你周一开盘就买！\n').bold = True
    note.add_run('必须等到符合买入条件时才能操作。\n\n')
    
    if len(a_stocks) == 0:
        no_rec = doc.add_paragraph()
        no_rec.add_run('本周无A级推荐股票。\n').bold = True
        no_rec.add_run('建议本周以观望为主，等待更好的机会。')
    else:
        for i, s in enumerate(a_stocks[:3], 1):
            doc.add_heading(f'关注{i}：{s["code"]} {s["name"]}', level=2)
            
            stock_info = doc.add_paragraph()
            stock_info.add_run(f'板块：{s["sector"]}\n')
            stock_info.add_run(f'周五收盘：{s["price"]:.2f}元\n')
            stock_info.add_run(f'周五涨跌：{s["friday_change"]:+.1f}%\n')
            stock_info.add_run(f'20日位置：{s["pos_20d"]:.0f}%\n')
            stock_info.add_run(f'5日涨幅：{s["ret_5d"]:+.1f}%\n')
            stock_info.add_run(f'综合评分：{s["score"]}分\n\n')
            
            # 买入条件
            stock_info.add_run('买入条件（必须同时满足）：\n').bold = True
            stock_info.add_run(f'1. 开盘涨幅 < 0.5%\n')
            stock_info.add_run(f'2. 开盘30分钟内股价能收回开盘价\n')
            stock_info.add_run(f'3. 大盘开盘后没有明显下跌\n')
            stock_info.add_run(f'4. 成交量没有异常放大\n\n')
            
            # 不买条件
            stock_info.add_run('以下情况不买：\n').bold = True
            stock_info.add_run('- 高开超过1%\n')
            stock_info.add_run('- 开盘后持续下跌不反弹\n')
            stock_info.add_run('- 成交量异常放大（可能有利空）\n')
            stock_info.add_run('- 大盘明显走弱\n')
    
    # ==================== B级观察 ====================
    if len(b_stocks) > 0:
        doc.add_heading('B级观察池', level=1)
        
        b_table = doc.add_table(rows=min(6, len(b_stocks)+1), cols=5)
        b_table.style = 'Table Grid'
        
        hdr = b_table.rows[0].cells
        hdr[0].text = '代码'
        hdr[1].text = '名称'
        hdr[2].text = '20日位置'
        hdr[3].text = '5日涨幅'
        hdr[4].text = '风险提示'
        
        for i, s in enumerate(b_stocks[:5], 1):
            row = b_table.rows[i].cells
            row[0].text = s['code']
            row[1].text = s['name']
            row[2].text = f"{s['pos_20d']:.0f}%"
            row[3].text = f"{s['ret_5d']:+.1f}%"
            row[4].text = ', '.join(s['risks'][:2]) if s['risks'] else '-'
    
    # ==================== 纪律 ====================
    doc.add_heading('操作纪律', level=1)
    
    rules = doc.add_paragraph()
    rules.add_run('【必须遵守】\n\n').bold = True
    rules.add_run('1. 止损纪律：买入后跌3%立即止损，没有例外\n')
    rules.add_run('2. 不追高：涨起来的股票不追\n')
    rules.add_run('3. 仓位控制：单票最多10%，总仓位不超过50%\n')
    rules.add_run('4. 观察优先：开盘30分钟内只看不动\n')
    rules.add_run('5. 宁可错过：没把握就不做\n\n')
    
    rules.add_run('【周一特别提醒】\n\n').bold = True
    rules.add_run('- 周一容易出现"高开低走"或"平开下杀"\n')
    rules.add_run('- 如果今天多数股票低开，说明市场情绪不好，不要操作\n')
    rules.add_run('- 如果买入后被套，按照止损纪律执行，不要补仓\n')
    
    # 免责声明
    doc.add_paragraph()
    disclaimer = doc.add_paragraph()
    disclaimer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    disc_run = disclaimer.add_run('【免责声明】本报告仅供参考学习，不构成投资建议。股市有风险，投资需谨慎。')
    disc_run.font.size = Pt(9)
    disc_run.font.color.rgb = RGBColor(128, 128, 128)
    
    # 保存
    filename = f'周一开盘分析_{datetime.now().strftime("%Y%m%d")}.docx'
    doc.save(filename)
    log(f"\n报告已生成: {filename}")
    
    return filename


if __name__ == "__main__":
    generate_weekend_report()
