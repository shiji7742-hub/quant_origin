"""
生成周一开盘机会分析Word文档（完善版）
增加：仓位控制、大盘分析、具体买入操作
"""
from docx import Document
from docx.shared import Inches, Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from datetime import datetime

def create_report():
    doc = Document()
    
    # 设置中文字体
    doc.styles['Normal'].font.name = '微软雅黑'
    doc.styles['Normal']._element.rPr.rFonts.set(qn('w:eastAsia'), '微软雅黑')
    doc.styles['Normal'].font.size = Pt(11)
    
    # 标题
    title = doc.add_heading('周一开盘机会分析报告', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    # 日期
    date_para = doc.add_paragraph()
    date_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    date_run = date_para.add_run(f'扫描时间：{datetime.now().strftime("%Y年%m月%d日")} 周日')
    date_run.font.size = Pt(12)
    date_run.font.color.rgb = RGBColor(128, 128, 128)
    
    doc.add_paragraph()
    
    # ==================== 核心要点 ====================
    doc.add_heading('核心要点速览', level=1)
    
    keypoints = doc.add_paragraph()
    keypoints.add_run('【板块机会】').bold = True
    keypoints.add_run('消费电子、新能源车、光伏板块触发"板块异动"信号\n\n')
    
    keypoints.add_run('【重点标的】').bold = True
    keypoints.add_run('欧菲光、宁德时代、欣旺达（板块共振）\n\n')
    
    keypoints.add_run('【建议仓位】').bold = True
    keypoints.add_run('总仓位30-50%，单票不超过15%\n\n')
    
    keypoints.add_run('【操作策略】').bold = True
    keypoints.add_run('开盘观察5分钟，不低开即可买入\n')
    
    # ==================== 一、大盘环境分析 ====================
    doc.add_heading('一、大盘环境分析', level=1)
    
    market = doc.add_paragraph()
    market.add_run('1. 当前市场状态\n\n').bold = True
    market.add_run('   根据近期走势，大盘处于震荡整理阶段。需要关注：\n')
    market.add_run('   - 上证指数支撑位：3200点\n')
    market.add_run('   - 上证指数压力位：3350点\n')
    market.add_run('   - 成交量：近期成交萎缩，需放量确认方向\n\n')
    
    market.add_run('2. 周一开盘观察要点\n\n').bold = True
    
    # 大盘情况表格
    market_table = doc.add_table(rows=5, cols=3)
    market_table.style = 'Table Grid'
    
    hdr = market_table.rows[0].cells
    hdr[0].text = '大盘情况'
    hdr[1].text = '操作建议'
    hdr[2].text = '仓位建议'
    for cell in hdr:
        cell.paragraphs[0].runs[0].bold = True
    
    market_scenarios = [
        ('高开>0.5%', '正常买入信号股', '可满仓操作'),
        ('平开（-0.3%~+0.3%）', '观察5分钟后买入', '建议50%仓位'),
        ('低开-0.3%~-1%', '等待企稳后再买', '建议30%仓位'),
        ('低开>1%', '暂缓操作，观望为主', '空仓或10%试探'),
    ]
    for i, (situation, action, position) in enumerate(market_scenarios, 1):
        row = market_table.rows[i].cells
        row[0].text = situation
        row[1].text = action
        row[2].text = position
    
    doc.add_paragraph()
    
    # ==================== 二、仓位管理策略 ====================
    doc.add_heading('二、仓位管理策略', level=1)
    
    position_mgmt = doc.add_paragraph()
    position_mgmt.add_run('1. 总体仓位控制\n\n').bold = True
    
    # 仓位表格
    pos_table = doc.add_table(rows=4, cols=3)
    pos_table.style = 'Table Grid'
    
    hdr = pos_table.rows[0].cells
    hdr[0].text = '市场环境'
    hdr[1].text = '总仓位'
    hdr[2].text = '说明'
    for cell in hdr:
        cell.paragraphs[0].runs[0].bold = True
    
    positions = [
        ('强势（放量上涨）', '50-70%', '积极参与，但保留现金'),
        ('震荡（当前状态）', '30-50%', '精选个股，控制风险'),
        ('弱势（破位下跌）', '10-30%', '防守为主，少量试探'),
    ]
    for i, data in enumerate(positions, 1):
        row = pos_table.rows[i].cells
        for j, val in enumerate(data):
            row[j].text = val
    
    doc.add_paragraph()
    
    position_mgmt2 = doc.add_paragraph()
    position_mgmt2.add_run('2. 单票仓位控制\n\n').bold = True
    position_mgmt2.add_run('   - 单票最大仓位：15%（绝对上限20%）\n')
    position_mgmt2.add_run('   - 同板块总仓位：不超过30%\n')
    position_mgmt2.add_run('   - 建议持股数量：3-5只\n\n')
    
    position_mgmt2.add_run('3. 分批建仓策略\n\n').bold = True
    position_mgmt2.add_run('   对于重点标的，建议分批建仓：\n')
    position_mgmt2.add_run('   - 第一批：开盘买入50%计划仓位\n')
    position_mgmt2.add_run('   - 第二批：确认上涨后加仓30%\n')
    position_mgmt2.add_run('   - 第三批：突破关键位置加仓20%\n')
    
    # ==================== 三、板块异动信号 ====================
    doc.add_heading('三、板块异动信号', level=1)
    
    sector_para = doc.add_paragraph()
    sector_para.add_run('以下板块触发"板块异动"信号（爆发后回调企稳）：\n\n').bold = True
    
    sector_table = doc.add_table(rows=4, cols=4)
    sector_table.style = 'Table Grid'
    
    hdr = sector_table.rows[0].cells
    hdr[0].text = '板块'
    hdr[1].text = '回撤幅度'
    hdr[2].text = '当前状态'
    hdr[3].text = '关注度'
    for cell in hdr:
        cell.paragraphs[0].runs[0].bold = True
    
    sectors = [
        ('消费电子', '11.3%', '企稳回升', '★★★'),
        ('新能源车', '9.3%', '企稳回升', '★★★'),
        ('光伏', '17.0%', '企稳回升', '★★'),
    ]
    for i, data in enumerate(sectors, 1):
        row = sector_table.rows[i].cells
        for j, val in enumerate(data):
            row[j].text = val
    
    doc.add_paragraph()
    
    # ==================== 四、重点机会详解 ====================
    doc.add_heading('四、重点机会详解（策略共振）', level=1)
    
    # 欧菲光
    doc.add_heading('1. 002456 欧菲光（消费电子）★★★', level=2)
    
    stock1 = doc.add_paragraph()
    stock1.add_run('【信号分析】\n').bold = True
    stock1.add_run('  - 分时托单：量比1.43，位置91%，托单22次\n')
    stock1.add_run('  - 板块共振：消费电子板块异动，回撤11.3%后企稳\n')
    stock1.add_run('  - 技术形态：日线企稳，5日均线走平\n\n')
    
    stock1.add_run('【买入操作】\n').bold = True
    stock1.add_run('  - 买入时机：周一开盘后5分钟，确认不低开\n')
    stock1.add_run('  - 买入价位：开盘价附近（参考周五收盘价）\n')
    stock1.add_run('  - 建仓方式：首批50%，上涨后加仓\n')
    stock1.add_run('  - 建议仓位：10-15%\n\n')
    
    stock1.add_run('【止损止盈】\n').bold = True
    stock1.add_run('  - 止损位：跌破周五分时低点-1%（约-3%）\n')
    stock1.add_run('  - 第一止盈：+3%减仓1/3\n')
    stock1.add_run('  - 第二止盈：+5%减仓1/3\n')
    stock1.add_run('  - 剩余仓位：跟随趋势，跌破5日线离场\n')
    
    # 宁德时代
    doc.add_heading('2. 300750 宁德时代（新能源车）★★★', level=2)
    
    stock2 = doc.add_paragraph()
    stock2.add_run('【信号分析】\n').bold = True
    stock2.add_run('  - 分时托单：量比较高，收盘位置强势\n')
    stock2.add_run('  - 板块共振：新能源车板块异动，回撤9.3%后企稳\n')
    stock2.add_run('  - 龙头优势：板块绝对龙头，资金关注度高\n\n')
    
    stock2.add_run('【买入操作】\n').bold = True
    stock2.add_run('  - 买入时机：开盘后观察成交量，放量上涨时买入\n')
    stock2.add_run('  - 买入价位：开盘价附近，或回调5日线时\n')
    stock2.add_run('  - 建仓方式：龙头可一次性建仓\n')
    stock2.add_run('  - 建议仓位：10-15%（龙头可略高）\n\n')
    
    stock2.add_run('【止损止盈】\n').bold = True
    stock2.add_run('  - 止损位：跌破5日均线-1%\n')
    stock2.add_run('  - 第一止盈：+4%减仓1/3\n')
    stock2.add_run('  - 第二止盈：+7%减仓1/3\n')
    stock2.add_run('  - 剩余仓位：持有至趋势结束\n')
    
    # 欣旺达
    doc.add_heading('3. 300207 欣旺达（新能源车）★★★', level=2)
    
    stock3 = doc.add_paragraph()
    stock3.add_run('【信号分析】\n').bold = True
    stock3.add_run('  - 分时托单：量比1.54（较高），位置93%，托单25次\n')
    stock3.add_run('  - 板块共振：新能源车板块异动\n')
    stock3.add_run('  - 弹性优势：市值较小，弹性更好\n\n')
    
    stock3.add_run('【买入操作】\n').bold = True
    stock3.add_run('  - 买入时机：开盘后5分钟，确认不低开\n')
    stock3.add_run('  - 买入价位：开盘价附近\n')
    stock3.add_run('  - 建仓方式：首批50%，确认上涨后加仓\n')
    stock3.add_run('  - 建议仓位：8-12%\n\n')
    
    stock3.add_run('【止损止盈】\n').bold = True
    stock3.add_run('  - 止损位：跌破周五分时低点-1%\n')
    stock3.add_run('  - 第一止盈：+3%减仓1/3\n')
    stock3.add_run('  - 第二止盈：+5%减仓1/3\n')
    stock3.add_run('  - 剩余仓位：跟随趋势\n')
    
    # ==================== 五、分时托单信号 ====================
    doc.add_heading('五、分时托单信号（第二梯队）', level=1)
    
    # 机器人
    doc.add_heading('1. 300024 机器人 ★★', level=2)
    
    stock4 = doc.add_paragraph()
    stock4.add_run('【信号特点】量比1.74（最高），位置94%\n\n').bold = True
    stock4.add_run('【买入操作】\n')
    stock4.add_run('  - 时机：开盘确认不低开\n')
    stock4.add_run('  - 仓位：8-10%\n')
    stock4.add_run('  - 止损：跌破分时低点18.07元\n')
    stock4.add_run('  - 止盈：+3%~+5%\n')
    
    # 新时达
    doc.add_heading('2. 002527 新时达 ★★', level=2)
    
    stock5 = doc.add_paragraph()
    stock5.add_run('【信号特点】收盘位置100%（最强），量比1.51\n\n').bold = True
    stock5.add_run('【买入操作】\n')
    stock5.add_run('  - 时机：开盘确认不低开\n')
    stock5.add_run('  - 仓位：5-8%\n')
    stock5.add_run('  - 止损：跌破分时低点-1%\n')
    stock5.add_run('  - 止盈：+3%~+5%\n')
    
    # ==================== 六、涨停洗盘信号 ====================
    doc.add_heading('六、涨停洗盘信号（待突破）', level=1)
    
    washout_para = doc.add_paragraph()
    washout_para.add_run('以下个股需等待放量突破后再买入：\n\n')
    
    # 中科创达
    doc.add_heading('1. 300496 中科创达（人工智能）', level=2)
    
    stock6 = doc.add_paragraph()
    stock6.add_run('【信号特点】涨停后9天，回调-5.0%，缩量至0.49\n\n').bold = True
    stock6.add_run('【买入条件】\n')
    stock6.add_run('  - 等待放量突破涨停高点\n')
    stock6.add_run('  - 或者回调至涨停低点附近企稳\n\n')
    stock6.add_run('【操作建议】\n')
    stock6.add_run('  - 现在不急于买入，观察为主\n')
    stock6.add_run('  - 放量突破时追入，仓位5-8%\n')
    stock6.add_run('  - 止损：跌破回调低点\n')
    
    # ==================== 七、具体操作时间表 ====================
    doc.add_heading('七、周一操作时间表', level=1)
    
    # 时间表
    time_table = doc.add_table(rows=8, cols=3)
    time_table.style = 'Table Grid'
    
    hdr = time_table.rows[0].cells
    hdr[0].text = '时间'
    hdr[1].text = '操作'
    hdr[2].text = '说明'
    for cell in hdr:
        cell.paragraphs[0].runs[0].bold = True
    
    timeline = [
        ('9:15-9:25', '观察竞价', '关注信号股竞价情况，异常放量需谨慎'),
        ('9:25-9:30', '分析开盘', '判断大盘高开/低开，决定操作策略'),
        ('9:30-9:35', '第一波操作', '大盘正常则按计划买入第一批'),
        ('9:35-10:00', '观察确认', '观察买入标的走势，确认方向'),
        ('10:00-10:30', '加仓时机', '确认上涨后加仓第二批'),
        ('10:30-11:30', '持仓观察', '设好止损，观察盘面变化'),
        ('14:00-14:30', '尾盘决策', '根据走势决定是否调整仓位'),
    ]
    for i, data in enumerate(timeline, 1):
        row = time_table.rows[i].cells
        for j, val in enumerate(data):
            row[j].text = val
    
    doc.add_paragraph()
    
    # ==================== 八、风险控制 ====================
    doc.add_heading('八、风险控制', level=1)
    
    risk = doc.add_paragraph()
    risk.add_run('1. 止损纪律（必须严格执行）\n\n').bold = True
    
    # 止损表格
    sl_table = doc.add_table(rows=4, cols=3)
    sl_table.style = 'Table Grid'
    
    hdr = sl_table.rows[0].cells
    hdr[0].text = '策略类型'
    hdr[1].text = '止损位置'
    hdr[2].text = '止损幅度参考'
    for cell in hdr:
        cell.paragraphs[0].runs[0].bold = True
    
    sl_data = [
        ('分时托单', '跌破分时低点-1%', '约-3%'),
        ('板块共振', '跌破5日均线-1%', '约-3%~-5%'),
        ('涨停洗盘', '跌破回调低点', '约-3%~-5%'),
    ]
    for i, data in enumerate(sl_data, 1):
        row = sl_table.rows[i].cells
        for j, val in enumerate(data):
            row[j].text = val
    
    doc.add_paragraph()
    
    risk2 = doc.add_paragraph()
    risk2.add_run('2. 不操作的情况\n\n').bold = True
    risk2.add_run('  - 大盘低开超过1%\n')
    risk2.add_run('  - 个股低开超过2%\n')
    risk2.add_run('  - 竞价成交量异常放大（可能有利空）\n')
    risk2.add_run('  - 板块整体走弱\n')
    risk2.add_run('  - 有重大消息面利空\n\n')
    
    risk2.add_run('3. 减仓信号\n\n').bold = True
    risk2.add_run('  - 买入后冲高回落，收长上影线\n')
    risk2.add_run('  - 放量滞涨（量增价不增）\n')
    risk2.add_run('  - 跌破5日均线\n')
    risk2.add_run('  - 板块龙头转弱\n')
    
    # ==================== 九、资金分配方案 ====================
    doc.add_heading('九、资金分配方案', level=1)
    
    fund = doc.add_paragraph()
    fund.add_run('假设总资金100万，建议分配如下：\n\n').bold = True
    
    # 资金分配表格
    fund_table = doc.add_table(rows=6, cols=4)
    fund_table.style = 'Table Grid'
    
    hdr = fund_table.rows[0].cells
    hdr[0].text = '标的'
    hdr[1].text = '仓位比例'
    hdr[2].text = '资金（万）'
    hdr[3].text = '备注'
    for cell in hdr:
        cell.paragraphs[0].runs[0].bold = True
    
    fund_data = [
        ('欧菲光', '12%', '12', '板块共振首选'),
        ('宁德时代', '12%', '12', '龙头股'),
        ('欣旺达', '10%', '10', '板块共振'),
        ('机器人', '8%', '8', '分时托单强'),
        ('现金', '58%', '58', '保留灵活性'),
    ]
    for i, data in enumerate(fund_data, 1):
        row = fund_table.rows[i].cells
        for j, val in enumerate(data):
            row[j].text = val
    
    doc.add_paragraph()
    
    fund2 = doc.add_paragraph()
    fund2.add_run('说明：\n')
    fund2.add_run('  - 总持仓约42%，保持谨慎\n')
    fund2.add_run('  - 若大盘强势，可提高至60%\n')
    fund2.add_run('  - 若大盘弱势，降低至20%以下\n')
    
    # ==================== 十、总结 ====================
    doc.add_heading('十、总结', level=1)
    
    summary = doc.add_paragraph()
    summary.add_run('周一操作要点：\n\n').bold = True
    
    summary.add_run('1. 开盘前：').bold = True
    summary.add_run('关注外盘走势、消息面，做好心理准备\n\n')
    
    summary.add_run('2. 开盘时：').bold = True
    summary.add_run('观察大盘开盘情况，决定操作力度\n\n')
    
    summary.add_run('3. 开盘后5分钟：').bold = True
    summary.add_run('确认不低开，按计划买入第一批\n\n')
    
    summary.add_run('4. 盘中：').bold = True
    summary.add_run('设好止损，观察走势，确认后加仓\n\n')
    
    summary.add_run('5. 尾盘：').bold = True
    summary.add_run('根据持仓表现，决定次日策略\n\n')
    
    summary.add_run('核心原则：').bold = True
    summary.add_run('控制仓位、严格止损、顺势而为\n')
    
    # 免责声明
    doc.add_paragraph()
    doc.add_paragraph()
    disclaimer = doc.add_paragraph()
    disclaimer.alignment = WD_ALIGN_PARAGRAPH.CENTER
    disc_run = disclaimer.add_run('【免责声明】')
    disc_run.bold = True
    disc_run.font.size = Pt(10)
    
    disc2 = doc.add_paragraph()
    disc2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    disc2_run = disc2.add_run('本报告基于量化策略扫描生成，仅供参考学习，不构成投资建议。\n'
                              '股市有风险，投资需谨慎。盈亏自负，责任自担。')
    disc2_run.font.size = Pt(9)
    disc2_run.font.color.rgb = RGBColor(128, 128, 128)
    
    # 保存
    filename = f'周一开盘机会分析_{datetime.now().strftime("%Y%m%d")}.docx'
    doc.save(filename)
    print(f'已生成报告: {filename}')
    return filename

if __name__ == '__main__':
    create_report()
