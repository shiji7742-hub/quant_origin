"""股票涨幅提醒 - 交互式版本"""
import akshare as ak
import time
import threading
from datetime import datetime, time as dtime
import tkinter as tk
from tkinter import messagebox
import winsound


class StockAlert:
    def __init__(self):
        self.monitors = []  # 存储监控配置 [{code, name, threshold, alerted}, ...]
        self.running = False
        
    def is_trading_time(self):
        """判断是否在交易时间内"""
        now = datetime.now()
        if now.weekday() >= 5:
            return False
        current_time = now.time()
        morning_start = dtime(9, 30)
        morning_end = dtime(11, 30)
        afternoon_start = dtime(13, 0)
        afternoon_end = dtime(15, 0)
        return (morning_start <= current_time <= morning_end) or \
               (afternoon_start <= current_time <= afternoon_end)
    
    def get_stock_name(self, code):
        """根据代码获取股票名称"""
        try:
            df = ak.stock_zh_a_spot_em()
            stock = df[df['代码'] == code]
            if len(stock) > 0:
                return stock.iloc[0]['名称']
        except:
            pass
        return None
    
    def get_realtime_quotes(self):
        """获取所有监控股票的实时行情"""
        try:
            df = ak.stock_zh_a_spot_em()
            codes = [m['code'] for m in self.monitors]
            stocks = df[df['代码'].isin(codes)]
            result = {}
            for _, row in stocks.iterrows():
                result[row['代码']] = {
                    'name': row['名称'],
                    'price': float(row['最新价']),
                    'change_pct': float(row['涨跌幅']),
                }
            return result
        except Exception as e:
            print(f"获取行情失败: {e}")
            return {}
    
    def show_alert(self, title, message):
        """弹窗提醒"""
        def alert():
            try:
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            except:
                pass
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            messagebox.showwarning(title, message)
            root.destroy()
        threading.Thread(target=alert, daemon=True).start()
    
    def add_monitor(self, code, threshold):
        """添加监控"""
        name = self.get_stock_name(code)
        if name is None:
            print(f"❌ 找不到股票代码: {code}")
            return False
        
        # 检查是否已存在
        for m in self.monitors:
            if m['code'] == code and m['threshold'] == threshold:
                print(f"⚠️ 已存在相同监控: {name}({code}) {threshold}%")
                return False
        
        self.monitors.append({
            'code': code,
            'name': name,
            'threshold': threshold,
            'alerted': False
        })
        print(f"✅ 已添加: {name}({code}) 涨幅 ≥ {threshold}% 时提醒")
        return True
    
    def list_monitors(self):
        """列出所有监控"""
        if not self.monitors:
            print("当前没有监控任务")
            return
        print("\n当前监控列表:")
        print("-" * 40)
        for i, m in enumerate(self.monitors, 1):
            status = "已触发" if m['alerted'] else "监控中"
            print(f"{i}. {m['name']}({m['code']}) 阈值:{m['threshold']}% [{status}]")
        print("-" * 40)
    
    def remove_monitor(self, index):
        """删除监控"""
        if 1 <= index <= len(self.monitors):
            m = self.monitors.pop(index - 1)
            print(f"✅ 已删除: {m['name']}({m['code']}) {m['threshold']}%")
        else:
            print("❌ 无效的序号")
    
    def monitor_loop(self):
        """监控循环"""
        while self.running:
            if not self.monitors:
                time.sleep(5)
                continue
                
            if not self.is_trading_time():
                time.sleep(60)
                continue
            
            quotes = self.get_realtime_quotes()
            now = datetime.now().strftime("%H:%M:%S")
            
            for m in self.monitors:
                if m['code'] in quotes and not m['alerted']:
                    q = quotes[m['code']]
                    if q['change_pct'] >= m['threshold']:
                        m['alerted'] = True
                        msg = f"🚀 {q['name']} 涨幅达到 {q['change_pct']:.2f}%!\n\n" \
                              f"设定阈值: {m['threshold']}%\n" \
                              f"现价: {q['price']:.2f}\n\n" \
                              f"请注意操作!"
                        print(f"\n[{now}] ⚠️ 触发提醒: {q['name']} {q['change_pct']:.2f}% ≥ {m['threshold']}%")
                        self.show_alert(f"📈 {q['name']} 涨幅提醒", msg)
                    else:
                        # 如果涨幅回落，重置状态
                        if q['change_pct'] < m['threshold'] - 0.5:
                            m['alerted'] = False
            
            time.sleep(10)
    
    def start_monitor(self):
        """启动后台监控"""
        if not self.running:
            self.running = True
            threading.Thread(target=self.monitor_loop, daemon=True).start()
            print("✅ 监控已启动 (后台运行)")
    
    def stop_monitor(self):
        """停止监控"""
        self.running = False
        print("⏹️ 监控已停止")


def main():
    print("=" * 50)
    print("       股票涨幅提醒系统 (交互式)")
    print("=" * 50)
    print("\n命令说明:")
    print("  add 代码 涨幅  - 添加监控 (如: add 002083 3)")
    print("  list          - 查看监控列表")
    print("  del 序号      - 删除监控")
    print("  start         - 启动监控")
    print("  stop          - 停止监控")
    print("  quit          - 退出程序")
    print("=" * 50)
    
    alert = StockAlert()
    
    while True:
        try:
            cmd = input("\n> ").strip().lower()
            
            if not cmd:
                continue
            
            parts = cmd.split()
            action = parts[0]
            
            if action == 'add' and len(parts) >= 3:
                code = parts[1]
                try:
                    threshold = float(parts[2])
                    alert.add_monitor(code, threshold)
                except ValueError:
                    print("❌ 涨幅必须是数字")
            
            elif action == 'list':
                alert.list_monitors()
            
            elif action == 'del' and len(parts) >= 2:
                try:
                    index = int(parts[1])
                    alert.remove_monitor(index)
                except ValueError:
                    print("❌ 序号必须是数字")
            
            elif action == 'start':
                alert.start_monitor()
            
            elif action == 'stop':
                alert.stop_monitor()
            
            elif action in ['quit', 'exit', 'q']:
                alert.stop_monitor()
                print("再见!")
                break
            
            else:
                print("❌ 未知命令，输入 help 查看帮助")
                
        except KeyboardInterrupt:
            alert.stop_monitor()
            print("\n再见!")
            break
        except Exception as e:
            print(f"错误: {e}")


if __name__ == "__main__":
    main()
