"""
自动交易系统 - 完整流程
每日自动运行：交易 -> 复盘 -> 学习
"""
from ai_trader import AITrader
from ai_review import AIReviewer
from datetime import datetime
import time

def run_daily_system():
    """运行每日自动交易系统"""
    print("\n" + "="*70)
    print("自动交易系统启动")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    try:
        # 第一步：AI交易
        print("\n" + "▶"*35)
        print("第一步：AI自主交易")
        print("▶"*35)
        trader = AITrader()
        trader.daily_routine()
        
        time.sleep(2)
        
        # 第二步：AI复盘
        print("\n" + "▶"*35)
        print("第二步：AI复盘分析")
        print("▶"*35)
        reviewer = AIReviewer()
        reviewer.daily_review()
        
        print("\n" + "="*70)
        print("✓ 今日系统运行完成！")
        print("="*70)
        
        # 显示下次运行提示
        print("\n提示：")
        print("• 每日运行一次即可")
        print("• 建议在交易日收盘后运行")
        print("• 数据保存在 virtual_trading_data/ 目录")
        print("• 可随时运行 python ai_review.py 查看复盘")
        
    except Exception as e:
        print(f"\n系统运行出错: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_daily_system()
