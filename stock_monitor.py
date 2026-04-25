"""股票实时监控 - 涨幅/剧烈波动提醒"""
import akshare as ak
import time
import threading
from datetime import datetime, time as dtime
import tkinter as tk
from tkinter import messagebox
import winsound

# 监控配置
MONITOR_CONFIG = {
    "stock_code": "002279",  # 久其软件
    "stock_name": "久其软件",
    "cost_price": 10.86,     # 成本价（你的买入价）
    "shares": 1000,          # 持仓数量
    "price_alert": 9.01,     # 价格突破提醒阈值
    "gain_threshold": 3.0,   # 涨幅阈值 3%
    "gain_threshold_2": 6.0, # 第二档涨幅阈值 6%
    "limit_up_threshold": 9.8,  # 涨停阈值
    "surge_threshold": 1.5,  # 短时剧烈拉升阈值 1.5%
    "check_interval": 3,     # 检查间隔（秒）- 改为3秒，更快检测
    "surge_window": 60,      # 剧烈波动检测窗口（秒）
}

class StockMonitor:
    def __init__(self, config):
        self.config = config
        self.running = False
        self.last_price = None
        self.price_history = []  # 存储最近价格用于检测剧烈波动
        self.alerted_price = False   # 避免重复提醒价格突破
        self.alerted_gain = False  # 避免重复提醒涨幅
        self.alerted_gain_2 = False  # 避免重复提醒6%涨幅
        self.alerted_limit_up = False  # 避免重复提醒涨停
        self.alerted_surge = False  # 避免重复提醒剧烈波动
    
    def is_trading_time(self):
        """判断是否在交易时间内"""
        now = datetime.now()
        # 周末不交易
        if now.weekday() >= 5:
            return False
        current_time = now.time()
        # 上午 9:30-11:30，下午 13:00-15:00
        morning_start = dtime(9, 30)
        morning_end = dtime(11, 30)
        afternoon_start = dtime(13, 0)
        afternoon_end = dtime(15, 0)
        return (morning_start <= current_time <= morning_end) or \
               (afternoon_start <= current_time <= afternoon_end)
        
    def get_realtime_quote(self):
        """获取实时行情 - 使用腾讯/新浪单股票接口，速度快（<0.5秒）"""
        import requests
        code = self.config['stock_code']
        name = self.config['stock_name']
        
        # 判断市场
        if code.startswith('6'):
            symbol_tx = f"sh{code}"
            symbol_sina = f"sh{code}"
        else:
            symbol_tx = f"sz{code}"
            symbol_sina = f"sz{code}"
        
        # 方法1: 腾讯接口（最快）
        try:
            url = f"http://qt.gtimg.cn/q={symbol_tx}"
            response = requests.get(url, timeout=3)
            response.encoding = 'gbk'
            data = response.text
            
            if 'v_' in data and '~' in data:
                parts = data.split('~')
                if len(parts) > 34:
                    price = float(parts[3]) if parts[3] else 0
                    yesterday_close = float(parts[4]) if parts[4] else 0
                    open_price = float(parts[5]) if parts[5] else 0
                    volume = float(parts[6]) if parts[6] else 0
                    high = float(parts[33]) if parts[33] else 0
                    low = float(parts[34]) if parts[34] else 0
                    
                    if yesterday_close > 0 and price > 0:
                        change_pct = (price - yesterday_close) / yesterday_close * 100
                        return {
                            'code': code,
                            'name': name,
                            'price': price,
                            'change_pct': change_pct,
                            'open': open_price,
                            'high': high,
                            'low': low,
                            'volume': volume,
                            'yesterday_close': yesterday_close,
                        }
        except Exception as e:
            print(f"腾讯接口失败: {e}")
        
        # 方法2: 新浪接口（备用）
        try:
            url = f"http://hq.sinajs.cn/list={symbol_sina}"
            headers = {'Referer': 'http://finance.sina.com.cn'}
            response = requests.get(url, headers=headers, timeout=3)
            response.encoding = 'gbk'
            data = response.text
            
            if '="' in data:
                content = data.split('="')[1].split('"')[0]
                parts = content.split(',')
                if len(parts) > 8:
                    open_price = float(parts[1]) if parts[1] else 0
                    yesterday_close = float(parts[2]) if parts[2] else 0
                    price = float(parts[3]) if parts[3] else 0
                    high = float(parts[4]) if parts[4] else 0
                    low = float(parts[5]) if parts[5] else 0
                    volume = float(parts[8]) if parts[8] else 0
                    
                    if yesterday_close > 0 and price > 0:
                        change_pct = (price - yesterday_close) / yesterday_close * 100
                        return {
                            'code': code,
                            'name': name,
                            'price': price,
                            'change_pct': change_pct,
                            'open': open_price,
                            'high': high,
                            'low': low,
                            'volume': volume,
                            'yesterday_close': yesterday_close,
                        }
        except Exception as e:
            print(f"新浪接口也失败: {e}")
        
        return None
    
    def show_alert(self, title, message):
        """弹窗提醒"""
        def alert():
            # 播放提示音
            try:
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            except:
                pass
            
            # 创建弹窗
            root = tk.Tk()
            root.withdraw()
            root.attributes('-topmost', True)
            messagebox.showwarning(title, message)
            root.destroy()
        
        # 在新线程中显示弹窗，避免阻塞监控
        threading.Thread(target=alert, daemon=True).start()
    
    def check_surge(self, current_price):
        """检测剧烈波动"""
        now = time.time()
        self.price_history.append((now, current_price))
        
        # 清理过期数据
        window = self.config['surge_window']
        self.price_history = [(t, p) for t, p in self.price_history if now - t <= window]
        
        if len(self.price_history) >= 2:
            oldest_price = self.price_history[0][1]
            change_pct = (current_price - oldest_price) / oldest_price * 100
            return abs(change_pct) >= self.config['surge_threshold'], change_pct
        return False, 0
    
    def monitor_loop(self):
        """监控主循环"""
        print(f"\n{'='*50}")
        print(f"开始监控 {self.config['stock_name']}({self.config['stock_code']})")
        print(f"涨幅阈值: {self.config['gain_threshold']}%")
        print(f"剧烈波动阈值: {self.config['surge_threshold']}% / {self.config['surge_window']}秒")
        print(f"检查间隔: {self.config['check_interval']}秒")
        print(f"交易时间: 9:30-11:30, 13:00-15:00")
        print(f"{'='*50}\n")
        
        while self.running:
            # 检查是否在交易时间
            if not self.is_trading_time():
                now = datetime.now().strftime("%H:%M:%S")
                print(f"[{now}] 非交易时间，等待中...")
                time.sleep(60)  # 非交易时间每分钟检查一次
                continue
            
            quote = self.get_realtime_quote()
            if quote:
                now = datetime.now().strftime("%H:%M:%S")
                print(f"[{now}] {quote['name']} 现价:{quote['price']:.2f} 涨跌幅:{quote['change_pct']:+.2f}%")
                
                # 检查价格突破阈值
                if 'price_alert' in self.config and quote['price'] > self.config['price_alert'] and not self.alerted_price:
                    self.alerted_price = True
                    msg = f"{quote['name']} 价格突破 {self.config['price_alert']} 元!\n\n" \
                          f"现价: {quote['price']:.2f}\n" \
                          f"涨跌幅: {quote['change_pct']:+.2f}%\n" \
                          f"最高: {quote['high']:.2f}\n" \
                          f"最低: {quote['low']:.2f}"
                    print(f"\n*** 触发价格提醒: 现价 {quote['price']:.2f} > {self.config['price_alert']}")
                    self.show_alert("价格突破提醒", msg)
                # 价格回落则重置，下次再突破时继续提醒
                if 'price_alert' in self.config and quote['price'] <= self.config['price_alert'] - 0.05:
                    self.alerted_price = False

                # 检查涨幅阈值
                if quote['change_pct'] >= self.config['gain_threshold'] and not self.alerted_gain:
                    self.alerted_gain = True
                    msg = f"🚀 {quote['name']} 涨幅达到 {quote['change_pct']:.2f}%!\n\n" \
                          f"现价: {quote['price']:.2f}\n" \
                          f"最高: {quote['high']:.2f}\n" \
                          f"最低: {quote['low']:.2f}\n\n" \
                          f"请注意止盈!"
                    print(f"\n⚠️ 触发涨幅提醒: {quote['change_pct']:.2f}%")
                    self.show_alert("📈 止盈提醒 (3%)", msg)
                
                # 检查6%涨幅
                if quote['change_pct'] >= self.config['gain_threshold_2'] and not self.alerted_gain_2:
                    self.alerted_gain_2 = True
                    msg = f"🔥 {quote['name']} 涨幅达到 {quote['change_pct']:.2f}%!\n\n" \
                          f"现价: {quote['price']:.2f}\n" \
                          f"最高: {quote['high']:.2f}\n" \
                          f"最低: {quote['low']:.2f}\n\n" \
                          f"涨幅较大，注意风险!"
                    print(f"\n🔥 触发6%涨幅提醒: {quote['change_pct']:.2f}%")
                    self.show_alert("🔥 高涨幅提醒 (6%)", msg)
                
                # 检查涨停
                if quote['change_pct'] >= self.config['limit_up_threshold'] and not self.alerted_limit_up:
                    self.alerted_limit_up = True
                    msg = f"🎉 {quote['name']} 涨停了!\n\n" \
                          f"涨幅: {quote['change_pct']:.2f}%\n" \
                          f"现价: {quote['price']:.2f}\n\n" \
                          f"恭喜!"
                    print(f"\n🎉 触发涨停提醒: {quote['change_pct']:.2f}%")
                    self.show_alert("🎉 涨停提醒", msg)
                
                # 检查剧烈波动
                is_surge, surge_pct = self.check_surge(quote['price'])
                if is_surge and not self.alerted_surge:
                    self.alerted_surge = True
                    direction = "拉升" if surge_pct > 0 else "下跌"
                    msg = f"⚡ {quote['name']} 短时剧烈{direction}!\n\n" \
                          f"{self.config['surge_window']}秒内波动: {surge_pct:+.2f}%\n" \
                          f"现价: {quote['price']:.2f}\n" \
                          f"涨跌幅: {quote['change_pct']:+.2f}%\n\n" \
                          f"请注意风险!"
                    print(f"\n⚠️ 触发剧烈波动提醒: {surge_pct:+.2f}%")
                    self.show_alert("⚡ 剧烈波动提醒", msg)
                
                # 如果涨幅回落，重置提醒状态
                if quote['change_pct'] < self.config['gain_threshold'] - 0.5:
                    self.alerted_gain = False
                if not is_surge:
                    self.alerted_surge = False
                    
            time.sleep(self.config['check_interval'])
    
    def start(self):
        """启动监控"""
        self.running = True
        self.monitor_loop()
    
    def stop(self):
        """停止监控"""
        self.running = False


def main():
    print("=" * 50)
    print("       股票实时监控系统")
    print("=" * 50)
    print(f"\n监控目标: {MONITOR_CONFIG['stock_name']}({MONITOR_CONFIG['stock_code']})")
    print("按 Ctrl+C 停止监控\n")
    
    monitor = StockMonitor(MONITOR_CONFIG)
    try:
        monitor.start()
    except KeyboardInterrupt:
        print("\n\n监控已停止")
        monitor.stop()


if __name__ == "__main__":
    main()
