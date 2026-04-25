"""
定时自动交易
每个交易日自动运行
"""
import schedule
import time
from datetime import datetime
from auto_trading_system import run_daily_system
from trading_calendar import is_trading_day

def job():
    """定时任务"""
    # 检查是否交易日
    if not is_trading_day():
        print(f"{datetime.now().strftime('%Y-%m-%d')} 非交易日，跳过")
        return
    
    print(f"\n{'='*70}")
    print(f"定时任务触发 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}")
    
    try:
        run_daily_system()
    except Exception as e:
        print(f"任务执行失败: {e}")
        import traceback
        traceback.print_exc()

def start_scheduler():
    """启动定时器"""
    print("="*70)
    print("自动交易定时器启动")
    print("="*70)
    print("运行时间: 每个交易日 15:30 (收盘后)")
    print("按 Ctrl+C 停止")
    print("="*70)
    
    # 每天15:30运行（收盘后）
    schedule.every().day.at("15:30").do(job)
    
    # 也可以立即运行一次测试
    print("\n是否立即运行一次测试？(y/n): ", end='')
    choice = input().strip().lower()
    if choice == 'y':
        job()
    
    # 循环检查
    while True:
        schedule.run_pending()
        time.sleep(60)  # 每分钟检查一次

if __name__ == "__main__":
    start_scheduler()
