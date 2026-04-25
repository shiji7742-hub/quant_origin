"""
生成周一开盘机会分析Word文档
"""
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from datetime import datetime

def create_report():
    doc = Document()
    
    # 设置中文字体
    doc.styles['Normal'].font.name = '微软雅黑'
    doc.styles['Normal']._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    
    # 标题
    title = doc.add_heading('周一开盘机会分析报告', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # 日期
    date_para = doc.add_paragraph()
    date_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    date_run = date_para.add_run(f'扫描时间：{datetime.now().strftime("%Y年%m月%d日")}')
    date_run.font.size = Pt(12)
    date_run.font.color.rgb = RGBColor(128, 128, 128)
    
    doc.add_paragraph()
    
    # ==================== 一、策略概述 ====================
    doc.add_heading('一、策略概述', level=1)
    
    strategies = doc.add_paragraph()
    strategies.add_run('本报告综合以下三大策略进行扫描：\n\n').bold = True
    strategies.add_run('1. 分时托单策略\n')
    strategies.add_run('   - 5分钟K线横盘（波动<5%）\n')
    strategies.add_run('   - 多次下探收回（托单>=5次）\n')
    strategies.add_run('   - 量比>1.2（上涨量>下跌量）← 最关键\n')
    strategies.add_run('   - 收盘位置>80%\n\n')
    
    strategies.add_run('2. 板块异动策略\n')
    strategies.add_run('   - 2-4个月前有过爆发\n')
    strategies.add_run('   - 回撤8-25%后企稳\n')
    strategies.add_run('   - 近期止跌企稳\n\n')
    
    strategies.add_run('3. 涨停板破位洗盘策略\n')
    strategies.add_run('   - 近30天内有涨停\n')
    strategies.add_run('   - 涨停后回调-5%~-15%\n')
    strategies.add_run('   - 量能萎缩，近3日企稳\n')
    
    # ==================== 二、板块异动 ====================
    doc.add_heading('二、板块异动信号', level=1)
    
    sector_para = doc.add_paragraph()
    sector_para.add_run('以下板块触发"板块异动"信号，建议重点关注：\n\n').bold = True
    
    # 板块异动表格
    sector_table = doc.add_table(rows=4, cols=3)
    sector_table.style = 'Table Grid'
    
    # 表头
    hdr_cells = sector_table.rows[0].cells
    hdr_cells[0].text = '板块'
    hdr_cells[1].text = '回撤幅度'
    hdr_cells[2].text = '状态'
    for cell in hdr_cells:
        cell.paragraphs[0].runs[0].bold = True
    
    # 数据
    sectors = [
        ('消费电子', '11.3%', '企稳回升'),
        ('光伏', '17.0%', '企稳回升'),
        ('新能源车', '9.3%', '企稳回升'),
    ]
    for i, (name, drawdown, status) in enumerate(sectors, 1):
        row = sector_table.rows[i].cells
        row[0].text = name
        row[1].text = drawdown
        row[2].text = status
    
    doc.add_paragraph()
    
    # ==================== 三、重点机会 ====================
    doc.add_heading('三、★★★ 重点机会（策略共振）', level=1)
    
    combo_para = doc.add_paragraph()
    combo_para.add_run('以下个股同时满足"分时托单+板块异动"，胜率更高：\n\n').bold = True
    
    # 重点机会表格
    combo_table = doc.add_table(rows=7, cols=4)
    combo_table.style = 'Table Grid'
    
    hdr = combo_table.rows[0].cells
    hdr[0].text = '代码'
    hdr[1].text = '名称'
    hdr[2].text = '板块'
    hdr[3].text = '共振策略'
    for cell in hdr:
        cell.paragraphs[0].runs[0].bold = True
    
    combos = [
        ('002456', '欧菲光', '消费电子', '分时托单+板块异动'),
        ('002241', '歌尔股份', '消费电子', '分时托单+板块异动'),
        ('300750', '宁德时代', '新能源车', '分时托单+板块异动'),
        ('300207', '欣旺达', '新能源车', '分时托单+板块异动'),
        ('002466', '天齐锂业', '新能源车', '分时托单+板块异动'),
        ('300274', '阳光电源', '光伏', '分时托单+板块异动'),
    ]
    for i, (code, name, sector, strategy) in enumerate(combos, 1):
        row = combo_table.rows[i].cells
        row[0].text = code
        row[1].text = name
        row[2].text = sector
        row[3].text = strategy
    
    doc.add_paragraph()
    
    # ==================== 四、分时托单信号 ====================
    doc.add_heading('四、分时托单信号（高分）', level=1)
    
    intraday_table = doc.add_table(rows=6, cols=6)
    intraday_table.style = 'Table Grid'
    
    hdr = intraday_table.rows[0].cells
    headers = ['代码', '名称', '板块', '量比', '位置', '评分']
    for i, h in enumerate(headers):
        hdr[i].text = h
        hdr[i].paragraphs[0].runs[0].bold = True
    
    intradays = [
        ('300024', '机器人', '机器人', '1.74', '94%', '100'),
        ('002527', '新时达', '机器人', '1.51', '100%', '100'),
        ('300276', '三丰智能', '机器人', '1.43', '91%', '100'),
        ('002456', '欧菲光', '消费电子★', '1.43', '91%', '100'),
        ('300207', '欣旺达', '新能源车★', '1.54', '93%', '90'),
    ]
    for i, data in enumerate(intradays, 1):
        row = intraday_table.rows[i].cells
        for j, val in enumerate(data):
            row[j].text = val
    
    doc.add_paragraph()
    
    # ==================== 五、涨停洗盘信号 ====================
    doc.add_heading('五、涨停板破位洗盘信号', level=1)
    
    washout_table = doc.add_table(rows=3, cols=5)
    washout_table.style = 'Table Grid'
    
    hdr = washout_table.rows[0].cells
    headers = ['代码', '名称', '涨停后天数', '回调', '缩量']
    for i, h in enumerate(headers):
        hdr[i].text = h
        hdr[i].paragraphs[0].runs[0].bold = True
    
    washouts = [
        ('300496', '中科创达', '9天', '-5.0%', '0.49'),
        ('300624', '万兴科技', '9天', '-4.8%', '0.40'),
    ]
    for i, data in enumerate(washouts, 1):
        row = washout_table.rows[i].cells
        for j, val in enumerate(data):
            row[j].text = val
    
    doc.add_paragraph()
    
    # ==================== 六、操作建议 ====================
    doc.add_heading('六、周一操作建议', level=1)
    
    # 第一梯队
    doc.add_heading('第一梯队（板块共振，优先关注）', level=2)
    tier1 = doc.add_paragraph()
    tier1.add_run('002456 欧菲光\n').bold = True
    tier1.add_run('  理由：消费电子板块异动+分时托单\n')
    tier1.add_run('  操作：开盘不低开可买\n\n')
    
    tier1.add_run('300750 宁德时代\n').bold = True
    tier1.add_run('  理由：新能源车板块异动+分时托单+龙头\n')
    tier1.add_run('  操作：开盘不低开可买\n\n')
    
    tier1.add_run('300207 欣旺达\n').bold = True
    tier1.add_run('  理由：新能源车板块异动+分时托单+量比1.54高\n')
    tier1.add_run('  操作：开盘不低开可买\n')
    
    # 第二梯队
    doc.add_heading('第二梯队（分时托单强势）', level=2)
    tier2 = doc.add_paragraph()
    tier2.add_run('300024 机器人\n').bold = True
    tier2.add_run('  理由：量比1.74最高，分时托单信号强\n')
    tier2.add_run('  操作：开盘确认不低开买入\n\n')
    
    tier2.add_run('002527 新时达\n').bold = True
    tier2.add_run('  理由：收盘位置100%最强\n')
    tier2.add_run('  操作：开盘确认不低开买入\n')
    
    # 第三梯队
    doc.add_heading('第三梯队（涨停洗盘待突破）', level=2)
    tier3 = doc.add_paragraph()
    tier3.add_run('300496 中科创达\n').bold = True
    tier3.add_run('  理由：涨停后缩量回调5%，人工智能龙头\n')
    tier3.add_run('  操作：等待放量突破再进\n\n')
    
    tier3.add_run('300624 万兴科技\n').bold = True
    tier3.add_run('  理由：涨停后缩量回调4.8%\n')
    tier3.add_run('  操作：等待放量突破再进\n')
    
    # ==================== 七、风险提示 ====================
    doc.add_heading('七、风险提示', level=1)
    
    risk = doc.add_paragraph()
    risk.add_run('1. 大盘风险\n').bold = True
    risk.add_run('   - 大盘低开>1%：暂缓操作\n')
    risk.add_run('   - 大盘连续下跌：减少仓位\n\n')
    
    risk.add_run('2. 个股风险\n').bold = True
    risk.add_run('   - 个股低开>2%：放弃该信号\n')
    risk.add_run('   - 竞价成交量异常放大：谨慎\n\n')
    
    risk.add_run('3. 止损设置\n').bold = True
    risk.add_run('   - 分时托单：跌破周五分时低点-1%\n')
    risk.add_run('   - 涨停洗盘：跌破回调低点\n\n')
    
    risk.add_run('4. 仓位控制\n').bold = True
    risk.add_run('   - 单票不超过20%仓位\n')
    risk.add_run('   - 同板块不超过30%仓位\n')
    
    # ==================== 八、总结 ====================
    doc.add_heading('八、总结', level=1)
    
    summary = doc.add_paragraph()
    summary.add_run('本周关注要点：\n\n').bold = True
    summary.add_run('1. 板块层面：')
    summary.add_run('消费电子、新能源车、光伏').bold = True
    summary.add_run('三大板块触发"板块异动"信号，经过前期回调后企稳，有望迎来反弹。\n\n')
    
    summary.add_run('2. 个股层面：优先关注')
    summary.add_run('板块共振').bold = True
    summary.add_run('的标的（分时托单+板块异动），如欧菲光、宁德时代、欣旺达等。\n\n')
    
    summary.add_run('3. 操作策略：\n')
    summary.add_run('   - 开盘观察大盘走势，低开>1%暂缓\n')
    summary.add_run('   - 优先买入板块共振标的\n')
    summary.add_run('   - 设好止损，控制仓位\n')
    
    # 免责声明
    doc.add_paragraph()
    disclaimer = doc.add_paragraph()
    disclaimer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    disc_run = disclaimer.add_run('【免责声明】本报告仅供参考，不构成投资建议。投资有风险，入市需谨慎。')
    disc_run.font.size = Pt(9)
    disc_run.font.color.rgb = RGBColor(128, 128, 128)
    
    # 保存
    filename = f'周一开盘机会分析_{datetime.now().strftime("%Y%m%d")}.docx'
    doc.save(filename)
    print(f'已生成报告: {filename}')
    return filename

if __name__ == '__main__':
    create_report()
