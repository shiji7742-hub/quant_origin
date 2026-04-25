"""股票盯盘悬浮窗 - 翻牌动画效果"""
import requests
import time
import threading
import math
from datetime import datetime, time as dtime
import tkinter as tk
import winsound


# ── 颜色配置 ──
BG = '#1a1a2e'
BG_CARD = '#16213e'
RED = '#ff4757'
GREEN = '#2ed573'
WHITE = '#f1f2f6'
GRAY = '#747d8c'
YELLOW = '#ffa502'
BG_INPUT = '#0f3460'


class FlipDigit:
    """单个翻牌数字组件"""
    def __init__(self, parent, font_size=18, width=14, height=26):
        self.canvas = tk.Canvas(parent, width=width, height=height,
                                bg=BG_CARD, highlightthickness=0)
        self.font_size = font_size
        self.width = width
        self.height = height
        self.current = ''
        self.color = WHITE
        self._anim_id = None

    def pack(self, **kw):
        self.canvas.pack(**kw)

    def grid(self, **kw):
        self.canvas.grid(**kw)

    def set(self, char, color=None):
        if color:
            self.color = color
        if char == self.current:
            self._draw(char, 1.0)
            return
        self.current = char
        self._animate(char, 0)

    def _animate(self, char, step):
        if self._anim_id:
            self.canvas.after_cancel(self._anim_id)
        total = 6
        if step <= total:
            progress = step / total
            self._draw(char, progress)
            self._anim_id = self.canvas.after(25, self._animate, char, step + 1)
        else:
            self._draw(char, 1.0)

    def _draw(self, char, progress):
        c = self.canvas
        c.delete('all')
        w, h = self.width, self.height
        # 背景圆角矩形
        r = 3
        c.create_rectangle(1, 1, w-1, h-1, fill='#1e2a45', outline='#2a3a5c', width=1)
        # 中线
        c.create_line(1, h//2, w-1, h//2, fill='#2a3a5c', width=1)
        # 翻牌缩放效果
        scale_y = abs(math.cos(math.pi * (1 - progress)))
        if scale_y < 0.05:
            scale_y = 0.05
        font = ('Consolas', max(1, int(self.font_size * scale_y)), 'bold')
        c.create_text(w//2, h//2, text=char, fill=self.color, font=font)


class FlipNumber:
    """翻牌数字组 - 显示一个完整数字"""
    def __init__(self, parent, max_chars=8, font_size=18, digit_w=14, digit_h=26):
        self.frame = tk.Frame(parent, bg=BG_CARD)
        self.digits = []
        self.max_chars = max_chars
        for _ in range(max_chars):
            d = FlipDigit(self.frame, font_size=font_size, width=digit_w, height=digit_h)
            d.pack(side='left', padx=0)
            self.digits.append(d)

    def pack(self, **kw):
        self.frame.pack(**kw)

    def grid(self, **kw):
        self.frame.grid(**kw)

    def set(self, text, color=WHITE):
        text = str(text).rjust(self.max_chars)[-self.max_chars:]
        for i, ch in enumerate(text):
            self.digits[i].set(ch, color)


class StockCard:
    """单只股票卡片 - 支持多个提醒条件"""
    def __init__(self, parent, code, name, on_remove=None):
        self.code = code
        self.name = name
        self.alerts = []  # [{'type': '涨幅', 'threshold': 3.0, 'alerted': False, 'label': widget}, ...]
        self.last_price = 0
        self.last_pct = 0
        self._on_remove = on_remove

        self.frame = tk.Frame(parent, bg=BG_CARD, padx=8, pady=6,
                              highlightbackground='#2a3a5c', highlightthickness=1)

        # 顶部：名称 + 代码 + 删除按钮
        top = tk.Frame(self.frame, bg=BG_CARD)
        top.pack(fill='x')
        tk.Label(top, text=name, font=('Microsoft YaHei', 11, 'bold'),
                 fg=WHITE, bg=BG_CARD).pack(side='left')
        tk.Label(top, text=f' {code}', font=('Consolas', 9),
                 fg=GRAY, bg=BG_CARD).pack(side='left')

        btn = tk.Label(top, text='✕', font=('Arial', 10), fg=GRAY, bg=BG_CARD, cursor='hand2')
        btn.pack(side='right')
        if on_remove:
            btn.bind('<Button-1>', lambda e: on_remove(self))

        # 条件标签行
        self.tag_frame = tk.Frame(self.frame, bg=BG_CARD)
        self.tag_frame.pack(fill='x', pady=(2, 0))

        # 价格翻牌
        mid = tk.Frame(self.frame, bg=BG_CARD)
        mid.pack(fill='x', pady=(4, 0))

        self.price_flip = FlipNumber(mid, max_chars=8, font_size=20, digit_w=16, digit_h=28)
        self.price_flip.pack(side='left')

        self.pct_flip = FlipNumber(mid, max_chars=7, font_size=16, digit_w=13, digit_h=24)
        self.pct_flip.pack(side='right')

        # 状态
        self.status_label = tk.Label(self.frame, text='等待数据...', font=('Microsoft YaHei', 8),
                                     fg=GRAY, bg=BG_CARD, anchor='w')
        self.status_label.pack(fill='x', pady=(2, 0))

    def add_alert(self, alert_type, threshold):
        """添加一个提醒条件"""
        # 检查重复
        for a in self.alerts:
            if a['type'] == alert_type and a['threshold'] == threshold:
                return
        tag_text = f'{alert_type}≥{threshold}' if alert_type in ('涨幅', '跌幅') else f'{alert_type}{threshold}'
        lbl = tk.Label(self.tag_frame, text=tag_text, font=('Microsoft YaHei', 8),
                       fg=YELLOW, bg='#2a3a5c', padx=4, pady=1, cursor='hand2')
        lbl.pack(side='left', padx=(0, 4), pady=1)
        alert = {'type': alert_type, 'threshold': threshold, 'alerted': False, 'label': lbl}
        # 右键点击标签删除该条件
        lbl.bind('<Button-3>', lambda e, a=alert: self._remove_alert(a))
        self.alerts.append(alert)

    def _remove_alert(self, alert):
        """删除单个提醒条件，如果没有条件了就删除整张卡片"""
        alert['label'].destroy()
        self.alerts.remove(alert)
        if not self.alerts and self._on_remove:
            self._on_remove(self)

    def pack(self, **kw):
        self.frame.pack(**kw)

    def destroy(self):
        self.frame.destroy()

    def update(self, price, change_pct):
        """更新价格，触发翻牌动画"""
        color = RED if change_pct >= 0 else GREEN
        price_str = f'{price:.2f}'
        pct_str = f'{change_pct:+.2f}%'

        self.price_flip.set(price_str, color)
        self.pct_flip.set(pct_str, color)

        any_triggered = False
        for a in self.alerts:
            triggered = False
            if a['type'] == '涨幅' and change_pct >= a['threshold']:
                triggered = True
            elif a['type'] == '跌幅' and change_pct <= -a['threshold']:
                triggered = True
            elif a['type'] == '价格上' and price >= a['threshold']:
                triggered = True
            elif a['type'] == '价格下' and price <= a['threshold']:
                triggered = True

            if triggered and not a['alerted']:
                a['alerted'] = True
                a['label'].config(fg='#1a1a2e', bg=RED if a['type'] in ('跌幅','价格下') else YELLOW)
                try:
                    winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                except:
                    pass
            elif not triggered:
                # 回落重置
                reset = False
                if a['type'] == '涨幅' and change_pct < a['threshold'] - 0.5:
                    reset = True
                elif a['type'] == '跌幅' and change_pct > -a['threshold'] + 0.5:
                    reset = True
                elif a['type'] == '价格上' and price < a['threshold'] - 0.05:
                    reset = True
                elif a['type'] == '价格下' and price > a['threshold'] + 0.05:
                    reset = True
                if reset:
                    a['alerted'] = False
                    a['label'].config(fg=YELLOW, bg='#2a3a5c')

            if a['alerted']:
                any_triggered = True

        if any_triggered:
            self.status_label.config(text='⚠ 已触发提醒', fg=YELLOW)
            self.frame.config(highlightbackground=YELLOW)
        else:
            self.status_label.config(text=f'监控中  {datetime.now().strftime("%H:%M:%S")}', fg=GRAY)
            self.frame.config(highlightbackground='#2a3a5c')

        self.last_price = price
        self.last_pct = change_pct


class StockAlertGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title('盯盘')
        self.root.geometry('280x400+50+50')
        self.root.configure(bg=BG)
        self.root.attributes('-topmost', True)
        self.root.attributes('-alpha', 0.92)
        self.root.overrideredirect(True)  # 无边框

        self.cards = []  # StockCard list
        self.running = False
        self._drag_data = {'x': 0, 'y': 0}

        self._build_ui()
        self.start_monitor()

    def _build_ui(self):
        # 标题栏（可拖动）
        title_bar = tk.Frame(self.root, bg='#0f3460', height=32)
        title_bar.pack(fill='x')
        title_bar.pack_propagate(False)

        tk.Label(title_bar, text='📊 盯盘', font=('Microsoft YaHei', 10, 'bold'),
                 fg=WHITE, bg='#0f3460').pack(side='left', padx=8)

        # 置顶切换
        self._topmost = True
        self.pin_btn = tk.Label(title_bar, text='📌', font=('Arial', 10),
                                fg=YELLOW, bg='#0f3460', cursor='hand2')
        self.pin_btn.pack(side='right', padx=4)
        self.pin_btn.bind('<Button-1>', self._toggle_topmost)

        close_btn = tk.Label(title_bar, text='✕', font=('Arial', 12, 'bold'),
                             fg=GRAY, bg='#0f3460', cursor='hand2')
        close_btn.pack(side='right', padx=4)
        close_btn.bind('<Button-1>', lambda e: self.on_close())

        min_btn = tk.Label(title_bar, text='─', font=('Arial', 12),
                           fg=GRAY, bg='#0f3460', cursor='hand2')
        min_btn.pack(side='right', padx=4)
        min_btn.bind('<Button-1>', lambda e: self.root.iconify())

        # 拖动
        title_bar.bind('<Button-1>', self._start_drag)
        title_bar.bind('<B1-Motion>', self._do_drag)

        # 输入区
        input_frame = tk.Frame(self.root, bg=BG, padx=8, pady=4)
        input_frame.pack(fill='x')

        row1 = tk.Frame(input_frame, bg=BG)
        row1.pack(fill='x', pady=2)

        self.code_entry = tk.Entry(row1, width=8, font=('Consolas', 10),
                                   bg=BG_INPUT, fg=WHITE, insertbackground=WHITE,
                                   relief='flat', highlightthickness=1,
                                   highlightbackground='#2a3a5c')
        self.code_entry.pack(side='left', padx=(0, 4))
        self.code_entry.insert(0, '代码')
        self.code_entry.bind('<FocusIn>', lambda e: self.code_entry.delete(0, 'end') if self.code_entry.get() == '代码' else None)

        self.threshold_entry = tk.Entry(row1, width=5, font=('Consolas', 10),
                                        bg=BG_INPUT, fg=WHITE, insertbackground=WHITE,
                                        relief='flat', highlightthickness=1,
                                        highlightbackground='#2a3a5c')
        self.threshold_entry.pack(side='left', padx=(0, 4))
        self.threshold_entry.insert(0, '3')

        self.type_var = tk.StringVar(value='涨幅')
        type_menu = tk.OptionMenu(row1, self.type_var, '涨幅', '跌幅', '价格上', '价格下')
        type_menu.config(font=('Microsoft YaHei', 8), bg=BG_INPUT, fg=WHITE,
                         activebackground='#2a3a5c', highlightthickness=0, relief='flat', width=4)
        type_menu['menu'].config(bg=BG_INPUT, fg=WHITE)
        type_menu.pack(side='left', padx=(0, 4))

        add_btn = tk.Label(row1, text='＋', font=('Arial', 14, 'bold'),
                           fg=YELLOW, bg=BG, cursor='hand2')
        add_btn.pack(side='left', padx=4)
        add_btn.bind('<Button-1>', lambda e: self.add_monitor())

        self.code_entry.bind('<Return>', lambda e: self.threshold_entry.focus())
        self.threshold_entry.bind('<Return>', lambda e: self.add_monitor())

        # 卡片滚动区
        self.card_container = tk.Frame(self.root, bg=BG)
        self.card_container.pack(fill='both', expand=True, padx=4, pady=4)

        # 底部状态
        self.status_label = tk.Label(self.root, text='就绪', font=('Microsoft YaHei', 8),
                                     fg=GRAY, bg=BG, anchor='w')
        self.status_label.pack(fill='x', padx=8, pady=(0, 4))

        # 底部拉伸手柄
        grip = tk.Label(self.root, text='⋮⋮', font=('Arial', 8), fg=GRAY, bg=BG, cursor='size_nw_se')
        grip.pack(side='right', anchor='se')
        grip.bind('<Button-1>', self._start_resize)
        grip.bind('<B1-Motion>', self._do_resize)

    def _toggle_topmost(self, event=None):
        self._topmost = not self._topmost
        self.root.attributes('-topmost', self._topmost)
        self.pin_btn.config(fg=YELLOW if self._topmost else GRAY)

    def _start_drag(self, event):
        self._drag_data['x'] = event.x
        self._drag_data['y'] = event.y

    def _do_drag(self, event):
        x = self.root.winfo_x() + event.x - self._drag_data['x']
        y = self.root.winfo_y() + event.y - self._drag_data['y']
        self.root.geometry(f'+{x}+{y}')

    def _start_resize(self, event):
        self._drag_data['x'] = event.x_root
        self._drag_data['y'] = event.y_root
        self._drag_data['w'] = self.root.winfo_width()
        self._drag_data['h'] = self.root.winfo_height()

    def _do_resize(self, event):
        dw = event.x_root - self._drag_data['x']
        dh = event.y_root - self._drag_data['y']
        w = max(240, self._drag_data['w'] + dw)
        h = max(200, self._drag_data['h'] + dh)
        self.root.geometry(f'{w}x{h}')

    def is_trading_time(self):
        now = datetime.now()
        if now.weekday() >= 5:
            return False
        t = now.time()
        return (dtime(9, 30) <= t <= dtime(11, 30)) or (dtime(13, 0) <= t <= dtime(15, 0))

    def _market_prefix(self, code):
        """根据股票代码判断市场前缀"""
        return 'sh' if code.startswith(('6', '9')) else 'sz'

    def get_stock_name(self, code):
        prefix = self._market_prefix(code)
        # 腾讯接口
        try:
            url = f'http://qt.gtimg.cn/q={prefix}{code}'
            resp = requests.get(url, timeout=5)
            resp.encoding = 'gbk'
            if 'v_' in resp.text and '~' in resp.text:
                parts = resp.text.split('~')
                if len(parts) > 1 and parts[1]:
                    return parts[1]
        except:
            pass
        # 新浪备用
        try:
            url = f'http://hq.sinajs.cn/list={prefix}{code}'
            resp = requests.get(url, headers={'Referer': 'http://finance.sina.com.cn'}, timeout=5)
            resp.encoding = 'gbk'
            if '="' in resp.text:
                content = resp.text.split('="')[1].split('"')[0]
                parts = content.split(',')
                if parts and parts[0]:
                    return parts[0]
        except:
            pass
        return None

    def get_realtime_quotes(self):
        result = {}
        if not self.cards:
            return result
        # 腾讯接口支持批量查询
        symbols = ','.join(f'{self._market_prefix(c.code)}{c.code}' for c in self.cards)
        try:
            url = f'http://qt.gtimg.cn/q={symbols}'
            resp = requests.get(url, timeout=5)
            resp.encoding = 'gbk'
            for line in resp.text.strip().split(';'):
                if 'v_' not in line or '~' not in line:
                    continue
                parts = line.split('~')
                if len(parts) > 34:
                    code = parts[2] if len(parts) > 2 else ''
                    price = float(parts[3]) if parts[3] else 0
                    yesterday_close = float(parts[4]) if parts[4] else 0
                    if yesterday_close > 0 and price > 0:
                        change_pct = (price - yesterday_close) / yesterday_close * 100
                        result[code] = {'price': price, 'change_pct': change_pct}
        except Exception as e:
            print(f'腾讯接口失败: {e}')
            # 新浪备用逐个查
            for card in self.cards:
                try:
                    prefix = self._market_prefix(card.code)
                    url = f'http://hq.sinajs.cn/list={prefix}{card.code}'
                    resp = requests.get(url, headers={'Referer': 'http://finance.sina.com.cn'}, timeout=5)
                    resp.encoding = 'gbk'
                    if '="' in resp.text:
                        content = resp.text.split('="')[1].split('"')[0]
                        parts = content.split(',')
                        if len(parts) > 3:
                            yesterday_close = float(parts[2]) if parts[2] else 0
                            price = float(parts[3]) if parts[3] else 0
                            if yesterday_close > 0 and price > 0:
                                change_pct = (price - yesterday_close) / yesterday_close * 100
                                result[card.code] = {'price': price, 'change_pct': change_pct}
                except Exception as e2:
                    print(f'新浪接口也失败 {card.code}: {e2}')
        return result

    def add_monitor(self):
        code = self.code_entry.get().strip()
        if not code or code == '代码':
            return
        try:
            threshold = float(self.threshold_entry.get().strip())
        except ValueError:
            return

        alert_type = self.type_var.get()
        self.code_entry.delete(0, 'end')

        def fetch():
            name = self.get_stock_name(code)
            if not name:
                self.root.after(0, lambda: self.status_label.config(text=f'找不到 {code}', fg=RED))
                return
            self.root.after(0, lambda: self._add_card(code, name, threshold, alert_type))

        threading.Thread(target=fetch, daemon=True).start()
        self.status_label.config(text=f'正在查询 {code}...', fg=GRAY)

    def _add_card(self, code, name, threshold, alert_type):
        # 如果已有该股票的卡片，直接追加条件
        for card in self.cards:
            if card.code == code:
                card.add_alert(alert_type, threshold)
                self.status_label.config(text=f'已添加 {name} {alert_type}≥{threshold}', fg=WHITE)
                return
        card = StockCard(self.card_container, code, name, on_remove=self._remove_card)
        card.add_alert(alert_type, threshold)
        card.pack(fill='x', pady=2)
        self.cards.append(card)
        self.status_label.config(text=f'已添加 {name}', fg=WHITE)

    def _remove_card(self, card):
        self.cards.remove(card)
        card.destroy()

    def monitor_loop(self):
        while self.running:
            try:
                trading = self.is_trading_time()
                now_str = datetime.now().strftime('%H:%M:%S')
                status = f'{"交易中" if trading else "休市"} {now_str}'
                self.root.after(0, lambda s=status: self.status_label.config(text=s, fg=GRAY))

                if not self.cards or not trading:
                    time.sleep(10 if trading else 30)
                    continue

                quotes = self.get_realtime_quotes()
                for card in self.cards:
                    if card.code in quotes:
                        q = quotes[card.code]
                        self.root.after(0, lambda c=card, p=q['price'], pct=q['change_pct']:
                                        c.update(p, pct))
                time.sleep(3)
            except Exception as e:
                print(f'监控错误: {e}')
                time.sleep(10)

    def start_monitor(self):
        self.running = True
        threading.Thread(target=self.monitor_loop, daemon=True).start()

    def on_close(self):
        self.running = False
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == '__main__':
    app = StockAlertGUI()
    app.run()
