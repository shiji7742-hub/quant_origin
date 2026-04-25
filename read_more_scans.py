"""Read more scan results"""
import pandas as pd
import os

os.chdir(r'D:\量化\quant_ai')

files_to_read = [
    ('优化版可买清单_20260121.xlsx', 'Latest Buy List'),
    ('策略组合扫描_20260122_145228.xlsx', 'Strategy Combo Scan'),
    ('年报扭亏进阶回测_20260124_110929.xlsx', 'Annual Report Turnaround')
]

for f, desc in files_to_read:
    if os.path.exists(f):
        print(f'\n{"="*60}')
        print(f'{desc}: {f}')
        print("="*60)
        try:
            xls = pd.ExcelFile(f)
            for sheet in xls.sheet_names[:3]:  # Max 3 sheets
                print(f'\n--- Sheet: {sheet} ---')
                df = pd.read_excel(f, sheet_name=sheet)
                if len(df) > 0:
                    print(df.head(15).to_string(index=False))
                    if len(df) > 15:
                        print(f'... total {len(df)} records')
        except Exception as e:
            print(f'Error: {e}')
    else:
        print(f'File not found: {f}')
