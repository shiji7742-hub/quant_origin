"""
生成明日买入报告
包含Word报告和Excel可买清单
"""
import pandas as pd
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from datetime import datetime, timedelta
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

# 读取扫描结果
df = pd.read_excel('策略组合扫描_20260119_220003.xlsx')
df_triple = df[df['策略组合']=='深度回调+箱体突破+均线粘合'].copy()

# 推荐股票数据
recommendations = [
    {
        '代码': '000685',
        '名称': '中山公用',
        '现价': 12.49,
        '今日涨幅': 5.94,
        '优先级': 1,
        '建议仓位': '8%',
        '买入价': '12.50附近',
        '止损价': 11.87,
        '目标价1': 13.74,
        '目标价2': 14.36,
        '持有周期': '10-20天',
        '买入时机': '开盘后10分钟内，价格在12.30-12.70区间',
        '优势': '三重信号共振，涨幅适中，成交额充足',
        '风险': '市场情绪较弱，需严格止损'
    },
    {
        '代码': '000823',
        '名称': '超声电子',
        '现价': 14.85,
        '今日涨幅': 3.48,
        '优先级': 2,
        '建议仓位': '5%',
        '买入价': '14.80附近',
        '止损价': 14.11,
        '目标价1': 16.34,
        '目标价2': 17.08,
        '持有周期': '10-20天',
        '买入时机': '如首选高开超3%，转向此股',
        '优势': '三重信号，涨幅温和',
        '风险': '需观察首选表现'
    },
    {
        '代码': '001211',
        '名称': '双枪科技',
        '现价': 28.73,
        '今日涨幅': 3.09,
        '优先级': 3,
        '建议仓位': '5%',
        '买入价': '28.50-29.00',
        '止损价': 27.29,
        '目标价1': 31.60,
        '目标价2': 33.04,
        '持有周期': '10-20天',
        '买入时机': '备选，前两只不合适时考虑',
        '优势': '三重信号，价格稳定',
        '风险': '价格较高，波动可能大'
    },
    {
        '代码': '002893',
        '名称': '京能热力',
        '现价': 12.25,
        '今日涨幅': 2.94,
        '优先级': 4,
        '建议仓位': '3%',
        '买入价': '12.20附近',
        '止损价': 11.64,
        '目标价1': 13.48,
        '目标价2': 14.09,
        '持有周期': '10-20天',
        '买入时机': '补充仓位用',
        '优势': '三重信号，涨幅小',
        '风险': '流动性一般'
    },
    {
        '代码': '605033',
        '名称': '美邦股份',
        '现价': 20.79,
        '今日涨幅': 2.77,
        '优先级': 5,
        '建议仓位': '3%',
        '买入价': '20.50-21.00',
        '止损价': 19.75,
        '目标价1': 22.87,
        '目标价2': 23.91,
        '持有周期': '10-20天',
        '买入时机': '补充仓位用',
        '优势': '三重信号',
        '风险': '关注度低'
    }
]

# ==================== 生成Word报告 ====================
print("正在生成Word报告...")

doc = Document()

# 标题
title = doc.add_heading('股票买入操作报告', 0)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER

# 副标题
subtitle = doc.add_paragraph()
subtitle.add_run(f'报告日期：{datetime.now().strftime("%Y年%m月%d日")}\n').bold = True
subtitle.add_run(f'操作日期：{(datetime.now() + timedelta(days=1)).strftime("%Y年%m月%d日")}（明日）').bold = True
subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER

doc.add_paragraph()

# 一、市场环境分析
doc.add_heading('一、市场环境分析', 1)
p = doc.add_paragraph()
p.add_run('当前市场状态：').bold = True
p.add_run('情绪较弱\n')
p.add_run('市场情绪评分：').bold = True
p.add_run('1/7（低）\n')
p.add_run('5日波动率：').bold = True
p.add_run('0.34%（过低）\n')
p.add_run('大盘状态：').bold = True
p.add_run('跌破5日均线\n\n')

p.add_run('⚠️ 风险提示：').bold = True
p.add_run('当前市场环境不佳，建议控制总仓位≤15%，严格止损。')

doc.add_paragraph()

# 二、策略说明
doc.add_heading('二、策略说明', 1)
p = doc.add_paragraph()
p.add_run('策略名称：').bold = True
p.add_run('深度回调+箱体突破+均线粘合（三重信号共振）\n')
p.add_run('历史胜率：').bold = True
p.add_run('60.0%\n')
p.add_run('平均收益：').bold = True
p.add_run('3.23%\n')
p.add_run('建议持有周期：').bold = True
p.add_run('10-20天\n\n')

p.add_run('策略逻辑：\n').bold = True
p.add_run('1. 深度回调：股价从高点回调8%以上，接近支撑位\n')
p.add_run('2. 箱体突破：突破前期箱体震荡区间\n')
p.add_run('3. 均线粘合：多条均线粘合后发散，蓄势待发\n')

doc.add_paragraph()

# 三、推荐股票清单
doc.add_heading('三、推荐股票清单', 1)

for stock in recommendations:
    doc.add_heading(f'{stock["优先级"]}. {stock["代码"]} {stock["名称"]}（{stock["建议仓位"]}仓位）', 2)
    
    # 基本信息
    p = doc.add_paragraph()
    p.add_run('【基本信息】\n').bold = True
    p.add_run(f'现价：{stock["现价"]:.2f}元\n')
    p.add_run(f'今日涨幅：{stock["今日涨幅"]:+.2f}%\n')
    p.add_run(f'优先级：{"★" * stock["优先级"]}\n\n')
    
    # 操作计划
    p.add_run('【操作计划】\n').bold = True
    p.add_run(f'建议仓位：').bold = True
    p.add_run(f'{stock["建议仓位"]}\n')
    p.add_run(f'买入价格：').bold = True
    p.add_run(f'{stock["买入价"]}\n')
    p.add_run(f'买入时机：').bold = True
    p.add_run(f'{stock["买入时机"]}\n')
    p.add_run(f'持有周期：').bold = True
    p.add_run(f'{stock["持有周期"]}\n\n')
    
    # 风控设置
    p.add_run('【风控设置】\n').bold = True
    p.add_run(f'止损价：').bold = True
    run = p.add_run(f'{stock["止损价"]:.2f}元（-5%）\n')
    run.font.color.rgb = RGBColor(255, 0, 0)
    p.add_run(f'目标价1：').bold = True
    run = p.add_run(f'{stock["目标价1"]:.2f}元（+10%，减半仓）\n')
    run.font.color.rgb = RGBColor(0, 128, 0)
    p.add_run(f'目标价2：').bold = True
    run = p.add_run(f'{stock["目标价2"]:.2f}元（+15%，清仓）\n\n')
    run.font.color.rgb = RGBColor(0, 128, 0)
    
    # 优势与风险
    p.add_run('【优势】\n').bold = True
    p.add_run(f'{stock["优势"]}\n\n')
    p.add_run('【风险】\n').bold = True
    p.add_run(f'{stock["风险"]}\n')
    
    doc.add_paragraph()

# 四、操作流程
doc.add_heading('四、明日操作流程', 1)

p = doc.add_paragraph()
p.add_run('⏰ 9:15-9:25 集合竞价阶段\n').bold = True
p.add_run('• 观察首选股票000685中山公用的竞价情况\n')
p.add_run('• 如果竞价涨幅<3%，准备买入\n')
p.add_run('• 如果竞价涨幅>5%，放弃，转向备选\n\n')

p.add_run('⏰ 9:30-9:40 开盘10分钟\n').bold = True
p.add_run('• 首选：000685中山公用，价格12.30-12.70区间买入8%仓位\n')
p.add_run('• 如首选不合适，转向000823超声电子或001211双枪科技\n')
p.add_run('• 买入后立即设置止损单（-5%）\n\n')

p.add_run('⏰ 10:00-11:00 观察期\n').bold = True
p.add_run('• 观察买入股票的走势\n')
p.add_run('• 如果快速拉升>3%，可考虑加仓2-3%\n')
p.add_run('• 如果快速下跌接近止损，准备离场\n\n')

p.add_run('⏰ 下午盘\n').bold = True
p.add_run('• 如果上午未买入，下午可补充仓位\n')
p.add_run('• 选择002893京能热力或605033美邦股份\n')
p.add_run('• 总仓位控制在15%以内\n')

doc.add_paragraph()

# 五、风险控制
doc.add_heading('五、风险控制要点', 1)

p = doc.add_paragraph()
p.add_run('🔴 必须严格执行的规则：\n\n').bold = True

p.add_run('1. 仓位控制\n').bold = True
p.add_run('   • 单只股票≤8%\n')
p.add_run('   • 总仓位≤15%\n')
p.add_run('   • 不要满仓操作\n\n')

p.add_run('2. 止损纪律\n').bold = True
p.add_run('   • 跌破买入价-5%立即止损\n')
p.add_run('   • 不要心存侥幸\n')
p.add_run('   • 不要补仓摊平\n\n')

p.add_run('3. 止盈策略\n').bold = True
p.add_run('   • 盈利+10%：减半仓，锁定利润\n')
p.add_run('   • 盈利+15%：清仓离场\n')
p.add_run('   • 不要贪心追求更高收益\n\n')

p.add_run('4. 持有周期\n').bold = True
p.add_run('   • 建议持有10-20天\n')
p.add_run('   • 不要短线频繁交易\n')
p.add_run('   • 如果10天内未达目标，可继续持有\n\n')

p.add_run('5. 市场环境\n').bold = True
p.add_run('   • 如果大盘连续大跌，提前止损\n')
p.add_run('   • 如果个股出现重大利空，立即离场\n')
p.add_run('   • 保持灵活，不要死守\n')

doc.add_paragraph()

# 六、注意事项
doc.add_heading('六、特别注意事项', 1)

p = doc.add_paragraph()
p.add_run('⚠️ 当前市场环境较弱，以下情况建议放弃操作：\n\n').bold = True
p.add_run('1. 首选股票高开超过5%\n')
p.add_run('2. 大盘低开超过1%\n')
p.add_run('3. 个股出现异常波动\n')
p.add_run('4. 成交量异常萎缩\n\n')

p.add_run('✅ 操作成功的关键：\n\n').bold = True
p.add_run('1. 严格按照计划执行\n')
p.add_run('2. 不要情绪化交易\n')
p.add_run('3. 控制仓位和风险\n')
p.add_run('4. 保持耐心，不要频繁操作\n')

doc.add_paragraph()

# 七、免责声明
doc.add_heading('七、免责声明', 1)
p = doc.add_paragraph()
p.add_run('本报告仅供参考，不构成投资建议。股市有风险，投资需谨慎。\n')
p.add_run('投资者应根据自身风险承受能力做出独立判断。\n')
p.add_run('历史业绩不代表未来表现。\n')

# 保存Word
word_filename = f'买入操作报告_{datetime.now().strftime("%Y%m%d")}.docx'
doc.save(word_filename)
print(f"✓ Word报告已生成: {word_filename}")

# ==================== 生成Excel可买清单 ====================
print("\n正在生成Excel可买清单...")

wb = openpyxl.Workbook()
ws = wb.active
ws.title = "可买清单"

# 样式定义
header_font = Font(bold=True, color="FFFFFF", size=11)
header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
red_font = Font(color="FF0000", bold=True)
green_font = Font(color="008000", bold=True)
border = Border(
    left=Side(style='thin'),
    right=Side(style='thin'),
    top=Side(style='thin'),
    bottom=Side(style='thin')
)

# 标题
ws.merge_cells('A1:M1')
title_cell = ws['A1']
title_cell.value = f'股票买入清单 - {(datetime.now() + timedelta(days=1)).strftime("%Y年%m月%d日")}'
title_cell.font = Font(bold=True, size=14)
title_cell.alignment = Alignment(horizontal='center', vertical='center')

# 表头
headers = ['优先级', '代码', '名称', '现价', '建议仓位', '买入价', '买入时机', 
           '止损价', '目标价1', '目标价2', '持有周期', '优势', '风险']

for col, header in enumerate(headers, 1):
    cell = ws.cell(row=2, column=col, value=header)
    cell.font = header_font
    cell.fill = header_fill
    cell.border = border
    cell.alignment = Alignment(horizontal='center', vertical='center')

# 数据
for row_idx, stock in enumerate(recommendations, 3):
    ws.cell(row=row_idx, column=1, value=stock['优先级']).border = border
    ws.cell(row=row_idx, column=2, value=stock['代码']).border = border
    ws.cell(row=row_idx, column=3, value=stock['名称']).border = border
    ws.cell(row=row_idx, column=4, value=stock['现价']).border = border
    ws.cell(row=row_idx, column=5, value=stock['建议仓位']).border = border
    ws.cell(row=row_idx, column=6, value=stock['买入价']).border = border
    ws.cell(row=row_idx, column=7, value=stock['买入时机']).border = border
    
    # 止损价（红色）
    cell = ws.cell(row=row_idx, column=8, value=stock['止损价'])
    cell.font = red_font
    cell.border = border
    
    # 目标价（绿色）
    cell = ws.cell(row=row_idx, column=9, value=stock['目标价1'])
    cell.font = green_font
    cell.border = border
    
    cell = ws.cell(row=row_idx, column=10, value=stock['目标价2'])
    cell.font = green_font
    cell.border = border
    
    ws.cell(row=row_idx, column=11, value=stock['持有周期']).border = border
    ws.cell(row=row_idx, column=12, value=stock['优势']).border = border
    ws.cell(row=row_idx, column=13, value=stock['风险']).border = border

# 调整列宽
ws.column_dimensions['A'].width = 8
ws.column_dimensions['B'].width = 10
ws.column_dimensions['C'].width = 12
ws.column_dimensions['D'].width = 10
ws.column_dimensions['E'].width = 12
ws.column_dimensions['F'].width = 15
ws.column_dimensions['G'].width = 30
ws.column_dimensions['H'].width = 10
ws.column_dimensions['I'].width = 10
ws.column_dimensions['J'].width = 10
ws.column_dimensions['K'].width = 12
ws.column_dimensions['L'].width = 30
ws.column_dimensions['M'].width = 20

# 添加操作提示sheet
ws2 = wb.create_sheet("操作提示")
ws2.column_dimensions['A'].width = 80

tips = [
    ['⏰ 操作时间表', ''],
    ['9:15-9:25', '观察集合竞价，首选000685中山公用'],
    ['9:30-9:40', '开盘10分钟内买入，价格12.30-12.70'],
    ['10:00-11:00', '观察走势，设置止损'],
    ['下午盘', '如未买入，可补充仓位'],
    ['', ''],
    ['🔴 风控要点', ''],
    ['总仓位', '≤15%'],
    ['单只仓位', '≤8%'],
    ['止损', '-5%立即执行'],
    ['止盈', '+10%减半，+15%清仓'],
    ['持有周期', '10-20天'],
    ['', ''],
    ['⚠️ 放弃操作的情况', ''],
    ['1', '首选股票高开超5%'],
    ['2', '大盘低开超1%'],
    ['3', '个股异常波动'],
    ['4', '成交量异常萎缩'],
]

for row_idx, tip in enumerate(tips, 1):
    ws2.cell(row=row_idx, column=1, value=tip[0]).font = Font(bold=True)
    if len(tip) > 1:
        ws2.cell(row=row_idx, column=2, value=tip[1])

# 保存Excel
excel_filename = f'可买清单_{datetime.now().strftime("%Y%m%d")}.xlsx'
wb.save(excel_filename)
print(f"✓ Excel清单已生成: {excel_filename}")

print("\n" + "="*70)
print("报告生成完成！")
print("="*70)
print(f"\n文件清单：")
print(f"1. {word_filename} - 详细操作报告")
print(f"2. {excel_filename} - 可买清单")
print("\n请仔细阅读报告，严格按照计划执行！")
print("="*70)
