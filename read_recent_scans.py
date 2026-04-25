"""读取最近的扫描结果"""
import pandas as pd
import os

os.chdir(r'D:\量化\quant_ai')

# 列出最近的xlsx文件
files = [f for f in os.listdir('.') if f.endswith('.xlsx')]
files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
print('最近的Excel文件:')
for f in files[:10]:
    print(f'  - {f}')

print()

# 读取最近的扫描结果
for f in files[:5]:
    print(f'\n=== {f} ===')
    try:
        df = pd.read_excel(f)
        if len(df) > 0:
            print(df.head(20).to_string(index=False))
            if len(df) > 20:
                print(f'... total {len(df)} records')
        else:
            print('No data')
    except Exception as e:
        print(f'Read error: {e}')
