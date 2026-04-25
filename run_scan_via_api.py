# -*- coding: utf-8 -*-
"""通过API调用全市场扫描"""
import requests
import json
import time
import subprocess
import sys
import os
from datetime import datetime
try:
    import pandas as pd
    HAS_PANDAS = True
except:
    HAS_PANDAS = False

def log(msg):
    print(msg, flush=True)

log("="*60)
log("全市场扫描 - 通过API调用")
log(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
log("="*60)

# 启动web服务器
log("\n[1] 启动Web服务器...")
server_process = None
try:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    server_script = os.path.join(script_dir, 'web_server.py')
    
    # 启动服务器（后台运行）
    server_process = subprocess.Popen(
        [sys.executable, server_script],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
    )
    
    log("  服务器启动中，等待5秒...")
    time.sleep(5)
    
    # 检查服务器是否启动
    try:
        test_resp = requests.get('http://localhost:5000/api/status', timeout=2)
        log("  ✓ 服务器已启动")
    except:
        log("  ⚠ 服务器可能还在启动中，继续尝试...")
        time.sleep(3)
        
except Exception as e:
    log(f"  ✗ 启动服务器失败: {str(e)}")
    log("  尝试直接调用API（如果服务器已在运行）...")

# 调用扫描API
log("\n[2] 调用全市场扫描API...")
log("  筛选条件: 最近3天，量比≥2.0倍，要求上涨")
log("  扫描范围: 全市场（约4000只股票）")
log("  请耐心等待，预计需要5-10分钟...")

try:
    url = 'http://localhost:5000/api/scan_volume'
    payload = {
        'days': 3,
        'vol_ratio': 2.0,
        'price_change': 1,  # 要求上涨
        'max_pages': 50  # 全市场扫描
    }
    
    response = requests.post(url, json=payload, timeout=600)  # 10分钟超时
    
    if response.status_code == 200:
        data = response.json()
        if data.get('success'):
            results = data.get('results', [])
            count = data.get('count', len(results))
            
            log(f"\n[3] 扫描完成！找到 {count} 只放量股票\n")
            log("="*100)
            log(f"{'代码':<8} {'名称':<12} {'现价':<8} {'量比':<8} {'涨跌幅':<10} {'近期量':<12} {'基准量':<12}")
            log("="*100)
            
            display_count = min(50, len(results))
            for r in results[:display_count]:
                vol_tag = "🔥" if r['vol_ratio'] >= 3 else "📈"
                price_color = "+" if r['price_change'] >= 0 else ""
                log(f"{r['code']:<8} {r['name']:<12} {r['price']:<8.2f} {vol_tag}{r['vol_ratio']:<7.2f}x "
                    f"{price_color}{r['price_change']:<9.2f}% {r['recent_vol']/10000:<11.0f}万 {r['base_vol']/10000:<11.0f}万")
            
            log("="*100)
            log(f"\n共找到 {count} 只符合条件的股票")
            log(f"显示前{display_count}只，按量比从高到低排序")
            
            # 保存结果
            output_dir = script_dir
            output_file = os.path.join(output_dir, f'放量股票_{datetime.now().strftime("%Y%m%d")}.txt')
            
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"筛选时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"筛选条件: 最近3天，量比≥2.0倍，要求上涨\n")
                f.write("="*100 + "\n")
                f.write(f"{'代码':<8} {'名称':<12} {'现价':<8} {'量比':<8} {'涨跌幅':<10} {'近期量':<12} {'基准量':<12}\n")
                f.write("="*100 + "\n")
                for r in results:
                    price_color = "+" if r['price_change'] >= 0 else ""
                    f.write(f"{r['code']:<8} {r['name']:<12} {r['price']:<8.2f} {r['vol_ratio']:<8.2f}x "
                            f"{price_color}{r['price_change']:<9.2f}% {r['recent_vol']/10000:<11.0f}万 {r['base_vol']/10000:<11.0f}万\n")
            
            log(f"\n结果已保存到: {output_file}")
            
            # 保存Excel
            if HAS_PANDAS and len(results) > 0:
                try:
                    df = pd.DataFrame(results)
                    excel_file = os.path.join(output_dir, f'放量股票_{datetime.now().strftime("%Y%m%d")}.xlsx')
                    df.to_excel(excel_file, index=False, engine='openpyxl')
                    log(f"Excel文件已保存到: {excel_file}")
                except Exception as e:
                    log(f"Excel导出失败: {str(e)}")
            
            # 保存为.sel格式（通达信自选股格式）
            if len(results) > 0:
                try:
                    sel_file = os.path.join(output_dir, f'放量股票_{datetime.now().strftime("%Y%m%d")}.sel')
                    with open(sel_file, 'w', encoding='gbk') as f:
                        for r in results:
                            code = r['code']
                            # 通达信格式：上海1+代码，深圳0+代码
                            if code.startswith('6'):
                                f.write(f"1{code}\n")
                            else:  # 0开头或3开头的深圳股票
                                f.write(f"0{code}\n")
                    log(f"通达信自选股文件已保存到: {sel_file}")
                except Exception as e:
                    log(f"SEL格式导出失败: {str(e)}")
        else:
            log(f"✗ 扫描失败: {data.get('error', '未知错误')}")
    else:
        log(f"✗ API调用失败: HTTP {response.status_code}")
        log(f"  响应: {response.text[:200]}")
        
except requests.exceptions.ConnectionError:
    log("\n✗ 无法连接到服务器")
    log("  请确保web_server.py正在运行，或者手动启动:")
    log("  python web_server.py")
except Exception as e:
    log(f"\n✗ 调用API失败: {str(e)}")

# 清理
if server_process:
    try:
        log("\n[4] 关闭服务器...")
        server_process.terminate()
        server_process.wait(timeout=5)
        log("  ✓ 服务器已关闭")
    except:
        log("  ⚠ 服务器关闭超时，可能需要手动关闭")

log("\n扫描完成！")
