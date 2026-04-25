"""实时更新Excel持仓数据"""
import akshare as ak
from openpyxl import load_workbook
from datetime import datetime
import time

# Excel文件路径
EXCEL_PATH = r'C:\Users\shiji\Desktop\股票统计.xlsx'

# 列号定义（根据实际Excel结构）
COL_CODE = 1          # A列：代码
COL_COST = 10         # J列：成本价格
COL_CURRENT = 11      # K列：今日收盘价格
COL_CHANGE = 12       # L列：当日该股涨幅
COL_PROFIT_RATE = 13  # M列：当日盈亏率
COL_BUY_AMOUNT = 14   # N列：买入金额
COL_PROFIT = 15       # O列：盈亏金额

def get_realtime_prices():
    """获取A股实时行情"""
    df = ak.stock_zh_a_spot_em()
    df['代码'] = df['代码'].astype(str)
    return df.set_index('代码')

def update_excel():
    """更新Excel中的实时数据"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 获取实时行情...")
    realtime = get_realtime_prices()
    
    wb = load_workbook(EXCEL_PATH)
    ws = wb.active
    
    updated_count = 0
    
    # 从第3行开始遍历（跳过标题行和表头行）
    for row in range(3, ws.max_row + 1):
        code_cell = ws.cell(row=row, column=COL_CODE).value
        cost_cell = ws.cell(row=row, column=COL_COST).value
        buy_amount_cell = ws.cell(row=row, column=COL_BUY_AMOUNT).value
        
        # 跳过空行或无效行
        if not code_cell or code_cell in ['批次一', '批次二', '代码']:
            continue
        
        # 格式化股票代码
        code = str(int(code_cell)).zfill(6) if isinstance(code_cell, (int, float)) else str(code_cell).zfill(6)
        
        if code not in realtime.index:
            continue
        
        # 获取实时数据
        current_price = float(realtime.loc[code, '最新价'])
        change_pct = float(realtime.loc[code, '涨跌幅'])
        
        # 更新今日收盘价格
        ws.cell(row=row, column=COL_CURRENT, value=current_price)
        
        # 更新当日该股涨幅（转为小数）
        ws.cell(row=row, column=COL_CHANGE, value=change_pct / 100)
        
        # 如果有成本价和买入金额，计算盈亏
        if cost_cell and cost_cell != '/' and buy_amount_cell:
            try:
                cost = float(cost_cell)
                buy_amount = float(buy_amount_cell)
                
                # 计算盈亏率
                profit_rate = (current_price - cost) / cost
                ws.cell(row=row, column=COL_PROFIT_RATE, value=profit_rate)
                
                # 计算盈亏金额
                shares = buy_amount / cost
                profit = (current_price - cost) * shares
                ws.cell(row=row, column=COL_PROFIT, value=profit)
            except:
                pass
        
        stock_name = realtime.loc[code, '名称'] if '名称' in realtime.columns else code
        print(f"  {code} {stock_name}: {current_price} ({change_pct:+.2f}%)")
        updated_count += 1
    
    wb.save(EXCEL_PATH)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 已更新 {updated_count} 只股票\n")
    return updated_count

def run_realtime(interval=30):
    """实时更新模式"""
    print("="*50)
    print("Excel实时更新已启动")
    print(f"文件: {EXCEL_PATH}")
    print(f"刷新间隔: {interval}秒")
    print("按 Ctrl+C 停止")
    print("="*50 + "\n")
    
    while True:
        try:
            update_excel()
            time.sleep(interval)
        except KeyboardInterrupt:
            print("\n已停止更新")
            break
        except Exception as e:
            print(f"错误: {e}")
            time.sleep(5)

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--once':
        update_excel()
    else:
        run_realtime(interval=30)
