"""单只股票分析工具"""
import sys
from screener import analyze_stock
from ai_analyzer import analyze_with_ai
from data_fetcher import get_stock_info, get_stock_history
from strategies import check_all_strategies

def analyze_single(symbol: str):
    """分析单只股票"""
    # 检查是否为主板
    if not symbol.startswith(('60', '00')):
        print(f"错误: {symbol} 不是主板股票，只支持60/00开头的股票")
        return
    
    print(f"\n正在分析 {symbol}...")
    
    # 获取基本信息
    info = get_stock_info(symbol)
    if info:
        print(f"股票名称: {info.get('股票简称', 'N/A')}")
        print(f"所属行业: {info.get('行业', 'N/A')}")
    
    # 技术分析
    data = analyze_stock(symbol)
    if not data:
        print("获取数据失败")
        return
    
    print(f"\n--- 技术面 ---")
    print(f"最新价: {data['最新价']}")
    print(f"涨跌幅: {data['涨跌幅']}%")
    print(f"MA5/10/20: {data['MA5']} / {data['MA10']} / {data['MA20']}")
    print(f"MACD: {data['MACD']}")
    print(f"RSI: {data['RSI']}")
    print(f"成交量比: {data['成交量比']}")
    print(f"均线多头: {data['均线多头']}")
    print(f"MACD金叉: {data['MACD金叉']}")
    
    # 战法检测
    print(f"\n--- 战法检测 ---")
    df = get_stock_history(symbol, days=60)
    strategies = check_all_strategies(df)
    triggered_count = 0
    for name, result in strategies.items():
        status = "✓ 触发" if result['触发'] else "✗"
        if result['触发']:
            triggered_count += 1
            print(f"{status} 【{name}】{result['说明']}")
            print(f"      {result['条件']}")
        else:
            print(f"{status} {name}")
    
    print(f"\n共触发 {triggered_count} 个战法")
    
    # 把战法信息加入AI分析
    data['触发战法'] = [name for name, r in strategies.items() if r['触发']]
    
    # AI分析
    print(f"\n--- AI分析 ---")
    ai_result = analyze_with_ai(data)
    
    if '操作' in ai_result:
        print(f"操作建议: {ai_result['操作']}")
        print(f"建议仓位: {ai_result.get('仓位', 'N/A')}%")
        print(f"理由: {ai_result.get('理由', 'N/A')}")
        print(f"风险提示: {ai_result.get('风险提示', 'N/A')}")
    else:
        print(ai_result)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python single_stock.py <股票代码>")
        print("示例: python single_stock.py 600519")
    else:
        analyze_single(sys.argv[1])
