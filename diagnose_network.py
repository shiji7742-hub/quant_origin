#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网络诊断工具 - 检查网络连接问题
"""

import requests
import os
import sys


def check_proxy_settings():
    """检查代理设置"""
    print("=" * 70)
    print("1. 检查代理设置")
    print("=" * 70)
    
    # 检查环境变量
    http_proxy = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
    https_proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')
    
    if http_proxy:
        print(f"  HTTP代理: {http_proxy}")
    else:
        print(f"  HTTP代理: 未设置")
    
    if https_proxy:
        print(f"  HTTPS代理: {https_proxy}")
    else:
        print(f"  HTTPS代理: 未设置")
    
    # 检查requests的代理
    session = requests.Session()
    print(f"  requests代理: {session.proxies}")
    
    return http_proxy, https_proxy


def test_basic_connection():
    """测试基本网络连接"""
    print("\n" + "=" * 70)
    print("2. 测试基本网络连接")
    print("=" * 70)
    
    test_urls = [
        ("百度", "https://www.baidu.com"),
        ("淘宝", "https://www.taobao.com"),
        ("新浪", "https://www.sina.com.cn"),
    ]
    
    for name, url in test_urls:
        try:
            response = requests.get(url, timeout=5)
            print(f"  ✓ {name} ({url}): 成功 (状态码: {response.status_code})")
        except Exception as e:
            print(f"  ✗ {name} ({url}): 失败 - {e}")


def test_financial_apis():
    """测试金融数据API"""
    print("\n" + "=" * 70)
    print("3. 测试金融数据API")
    print("=" * 70)
    
    # 测试东方财富
    print("\n[东方财富API]")
    try:
        url = "http://80.push2.eastmoney.com/api/qt/clist/get"
        params = {
            'pn': '1',
            'pz': '10',
            'po': '1',
            'np': '1',
            'fltt': '2',
            'invt': '2',
            'fid': 'f3',
            'fs': 'm:0+t:6,m:0+t:80',
            'fields': 'f12,f14'
        }
        response = requests.get(url, params=params, timeout=10)
        print(f"  ✓ 连接成功 (状态码: {response.status_code})")
        data = response.json()
        if 'data' in data and 'diff' in data['data']:
            print(f"  ✓ 数据解析成功，获取到 {len(data['data']['diff'])} 条数据")
        else:
            print(f"  ✗ 数据格式异常")
    except Exception as e:
        print(f"  ✗ 连接失败: {e}")
    
    # 测试akshare
    print("\n[akshare]")
    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        print(f"  ✓ 连接成功，获取到 {len(df)} 只股票")
    except Exception as e:
        print(f"  ✗ 连接失败: {e}")


def test_with_no_proxy():
    """测试禁用代理后的连接"""
    print("\n" + "=" * 70)
    print("4. 测试禁用代理后的连接")
    print("=" * 70)
    
    # 临时禁用代理
    session = requests.Session()
    session.trust_env = False  # 不使用环境变量的代理
    
    try:
        url = "http://80.push2.eastmoney.com/api/qt/clist/get"
        params = {
            'pn': '1',
            'pz': '10',
            'po': '1',
            'np': '1',
            'fltt': '2',
            'invt': '2',
            'fid': 'f3',
            'fs': 'm:0+t:6,m:0+t:80',
            'fields': 'f12,f14'
        }
        response = session.get(url, params=params, timeout=10)
        print(f"  ✓ 禁用代理后连接成功 (状态码: {response.status_code})")
        return True
    except Exception as e:
        print(f"  ✗ 禁用代理后仍然失败: {e}")
        return False


def provide_solutions(http_proxy, https_proxy, no_proxy_works):
    """提供解决方案"""
    print("\n" + "=" * 70)
    print("5. 解决方案建议")
    print("=" * 70)
    
    if no_proxy_works:
        print("\n✓ 禁用代理后可以连接！")
        print("\n解决方案：在代码中添加以下内容禁用代理")
        print("""
import os
os.environ['NO_PROXY'] = '*'

# 或者在requests中禁用
import requests
session = requests.Session()
session.trust_env = False
""")
    
    elif http_proxy or https_proxy:
        print("\n⚠ 检测到系统代理设置")
        print("\n可能的解决方案：")
        print("1. 临时关闭VPN/代理软件")
        print("2. 在代码中禁用代理：")
        print("""
import os
os.environ['NO_PROXY'] = '*'
del os.environ['HTTP_PROXY']
del os.environ['HTTPS_PROXY']
""")
    
    else:
        print("\n可能的原因：")
        print("1. 防火墙/安全软件拦截")
        print("   - 检查Windows防火墙设置")
        print("   - 检查杀毒软件（360、火绒等）")
        print("   - 临时关闭防火墙测试")
        print("\n2. ISP网络问题")
        print("   - 尝试切换网络（手机热点）")
        print("   - 联系网络管理员")
        print("\n3. 服务器限流")
        print("   - 增加请求延迟")
        print("   - 错峰使用（晚上或周末）")
        print("\n4. DNS问题")
        print("   - 尝试更换DNS（8.8.8.8或114.114.114.114）")


def main():
    print("网络诊断工具")
    print("=" * 70)
    
    # 1. 检查代理
    http_proxy, https_proxy = check_proxy_settings()
    
    # 2. 测试基本连接
    test_basic_connection()
    
    # 3. 测试金融API
    test_financial_apis()
    
    # 4. 测试禁用代理
    no_proxy_works = test_with_no_proxy()
    
    # 5. 提供解决方案
    provide_solutions(http_proxy, https_proxy, no_proxy_works)
    
    print("\n" + "=" * 70)
    print("诊断完成")
    print("=" * 70)


if __name__ == '__main__':
    main()
