# -*- coding: utf-8 -*-
"""快速运行全市场扫描"""
import subprocess
import sys
import os

# 获取脚本目录
script_dir = os.path.dirname(os.path.abspath(__file__))
script_path = os.path.join(script_dir, 'scan_volume_stocks.py')

# 切换到脚本目录并运行
os.chdir(script_dir)
subprocess.run([sys.executable, 'scan_volume_stocks.py'])
