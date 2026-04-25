"""主程序入口"""
import json
from datetime import datetime
from screener import screen_stocks, analyze_stock
from ai_analyzer import analyze_with_ai

def run():
    """运行量化分析"""
    print("=" * 60)
    print(f"AI量化分析系统 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 1. 筛选股票
    print("\n[1] 正在筛选主板股票...")
    candidates = screen_stocks()
    print(f"    筛选出 {len(candidates)} 只候选股票: {candidates}")
    
    # 2. 技术分析
    print("\n[2] 正在进行技术分析...")
    results = []
    for symbol in candidates:
        print(f"    分析 {symbol}...", end=" ")
        data = analyze_stock(symbol)
        if data:
            print("✓")
            results.append(data)
        else:
            print("✗ 数据不足")
    
    # 3. AI分析
    print("\n[3] 正在进行AI分析...")
    final_results = []
    for stock in results:
        print(f"    AI分析 {stock['代码']}...", end=" ")
        ai_result = analyze_with_ai(stock)
        stock['AI分析'] = ai_result
        final_results.append(stock)
        print("✓")
    
    # 4. 输出结果
    print("\n" + "=" * 60)
    print("分析结果")
    print("=" * 60)
    
    for stock in final_results:
        print(f"\n【{stock['代码']}】最新价: {stock['最新价']}")
        print(f"  涨跌幅: {stock['涨跌幅']}%")
        print(f"  均线: MA5={stock['MA5']} MA10={stock['MA10']} MA20={stock['MA20']}")
        print(f"  MACD: {stock['MACD']} | RSI: {stock['RSI']}")
        print(f"  均线多头: {stock['均线多头']} | MACD金叉: {stock['MACD金叉']}")
        
        ai = stock.get('AI分析', {})
        if '操作' in ai:
            print(f"  ➤ AI建议: {ai['操作']} | 仓位: {ai.get('仓位', 'N/A')}%")
            print(f"  ➤ 理由: {ai.get('理由', 'N/A')}")
            print(f"  ➤ 风险: {ai.get('风险提示', 'N/A')}")
        else:
            print(f"  ➤ AI回复: {ai}")
    
    # 保存结果
    save_results(final_results)
    return final_results

def save_results(results):
    """保存分析结果"""
    filename = f"result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存到: {filename}")

if __name__ == "__main__":
    run()
