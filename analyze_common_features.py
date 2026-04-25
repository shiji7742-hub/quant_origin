"""多股票共同特征分析 - GUI版（交互式添加）"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from tkcalendar import DateEntry
import pandas as pd
import akshare as ak
import ta
import threading
from datetime import datetime

class StockAnalyzerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("多股票共同特征分析")
        self.root.geometry("1000x750")
        
        self.stock_list = []  # 存储添加的股票
        self.all_stocks = None  # 缓存股票列表
        
        self.create_widgets()
        self.load_stock_list()
    
    def load_stock_list(self):
        """后台加载股票列表"""
        def load():
            try:
                self.status_var.set("正在加载股票列表...")
                self.root.update()
                self.all_stocks = ak.stock_zh_a_spot_em()
                self.status_var.set(f"就绪 (已加载{len(self.all_stocks)}只股票)")
            except Exception as e:
                self.status_var.set(f"加载失败，可直接输入6位代码")
                self.all_stocks = pd.DataFrame({'代码': [], '名称': []})  # 空表，允许直接输入代码
        threading.Thread(target=load, daemon=True).start()
    
    def create_widgets(self):
        # ===== 输入区 =====
        input_frame = ttk.LabelFrame(self.root, text="添加股票", padding=10)
        input_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 第一行：股票输入
        row1 = ttk.Frame(input_frame)
        row1.pack(fill=tk.X, pady=2)
        
        ttk.Label(row1, text="股票代码/名称:").pack(side=tk.LEFT)
        self.stock_entry = ttk.Entry(row1, width=15)
        self.stock_entry.pack(side=tk.LEFT, padx=5)
        self.stock_entry.bind('<Return>', lambda e: self.add_stock())
        
        ttk.Label(row1, text="周期:").pack(side=tk.LEFT, padx=(10, 0))
        self.period_var = tk.StringVar(value="日线")
        period_combo = ttk.Combobox(row1, textvariable=self.period_var, width=8, state='readonly')
        period_combo['values'] = ('日线', '60分钟', '30分钟', '15分钟', '5分钟', '1分钟')
        period_combo.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(row1, text="开始日期:").pack(side=tk.LEFT, padx=(10, 0))
        self.start_date_entry = DateEntry(row1, width=12, date_pattern='yyyy-mm-dd')
        self.start_date_entry.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(row1, text="结束日期:").pack(side=tk.LEFT, padx=(10, 0))
        self.end_date_entry = DateEntry(row1, width=12, date_pattern='yyyy-mm-dd')
        self.end_date_entry.pack(side=tk.LEFT, padx=5)
        
        self.use_latest_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(row1, text="最新", variable=self.use_latest_var, 
                       command=self.toggle_date).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(row1, text="添加", command=self.add_stock).pack(side=tk.LEFT, padx=5)
        
        # ===== 股票列表 =====
        list_frame = ttk.LabelFrame(self.root, text="已添加的股票", padding=10)
        list_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 列表
        columns = ('代码', '名称', '周期', '时间段')
        self.stock_tree = ttk.Treeview(list_frame, columns=columns, show='headings', height=5)
        self.stock_tree.heading('代码', text='代码')
        self.stock_tree.heading('名称', text='名称')
        self.stock_tree.heading('周期', text='周期')
        self.stock_tree.heading('时间段', text='分析时间段')
        self.stock_tree.column('代码', width=80)
        self.stock_tree.column('名称', width=100)
        self.stock_tree.column('周期', width=60)
        self.stock_tree.column('时间段', width=180)
        self.stock_tree.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 列表按钮
        list_btn_frame = ttk.Frame(list_frame)
        list_btn_frame.pack(side=tk.LEFT, padx=10)
        ttk.Button(list_btn_frame, text="删除选中", command=self.remove_stock).pack(pady=2)
        ttk.Button(list_btn_frame, text="清空列表", command=self.clear_list).pack(pady=2)
        
        # ===== 操作按钮 =====
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.analyze_btn = ttk.Button(btn_frame, text="分析共同特征", command=self.start_analyze)
        self.analyze_btn.pack(side=tk.LEFT, padx=5)
        
        self.verify_btn = ttk.Button(btn_frame, text="验证特征(留一法)", command=self.start_verify)
        self.verify_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(btn_frame, text="清空结果", command=self.clear_result).pack(side=tk.LEFT, padx=5)
        
        self.status_var = tk.StringVar(value="正在加载...")
        ttk.Label(btn_frame, textvariable=self.status_var).pack(side=tk.RIGHT, padx=5)
        
        # ===== 结果区 =====
        result_frame = ttk.LabelFrame(self.root, text="分析结果", padding=10)
        result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.result_text = scrolledtext.ScrolledText(result_frame, height=25, width=110, font=("Consolas", 10))
        self.result_text.pack(fill=tk.BOTH, expand=True)
    
    def toggle_date(self):
        """切换日期选择器状态"""
        if self.use_latest_var.get():
            self.start_date_entry.config(state='disabled')
            self.end_date_entry.config(state='disabled')
        else:
            self.start_date_entry.config(state='normal')
            self.end_date_entry.config(state='normal')
    
    def add_stock(self):
        """添加股票到列表"""
        input_str = self.stock_entry.get().strip()
        if not input_str:
            return
        
        # 查找股票
        code = None
        name = input_str
        
        if self.all_stocks is not None and len(self.all_stocks) > 0:
            code = self.find_stock_code(input_str)
            if code:
                match = self.all_stocks[self.all_stocks['代码'] == code]
                if len(match) > 0:
                    name = match['名称'].values[0]
        
        # 如果没找到但输入是6位数字，直接用
        if not code and input_str.isdigit() and len(input_str) == 6:
            code = input_str
            name = input_str
        
        if not code:
            messagebox.showwarning("提示", f"未找到股票: {input_str}\n可直接输入6位代码")
            return
        
        period = self.period_var.get()
        
        # 分钟数据只能用最新
        if period != '日线':
            date_str = "最新数据"
            start_date = None
            end_date = None
        elif self.use_latest_var.get():
            date_str = "最新数据"
            start_date = None
            end_date = None
        else:
            start_date = self.start_date_entry.get_date().strftime('%Y-%m-%d')
            end_date = self.end_date_entry.get_date().strftime('%Y-%m-%d')
            date_str = f"{start_date} ~ {end_date}"
        
        # 添加到列表
        self.stock_list.append({'code': code, 'name': name, 'period': period, 'start_date': start_date, 'end_date': end_date})
        self.stock_tree.insert('', tk.END, values=(code, name, period, date_str))
        
        # 清空输入
        self.stock_entry.delete(0, tk.END)
        self.stock_entry.focus()
    
    def find_stock_code(self, input_str):
        """根据输入找股票代码"""
        input_str = input_str.strip()
        if input_str.isdigit() and len(input_str) == 6:
            if input_str in self.all_stocks['代码'].values:
                return input_str
        match = self.all_stocks[self.all_stocks['名称'].str.contains(input_str, na=False)]
        if len(match) > 0:
            return match.iloc[0]['代码']
        return None
    
    def remove_stock(self):
        """删除选中的股票"""
        selected = self.stock_tree.selection()
        if not selected:
            return
        for item in selected:
            idx = self.stock_tree.index(item)
            self.stock_tree.delete(item)
            if idx < len(self.stock_list):
                self.stock_list.pop(idx)
    
    def clear_list(self):
        """清空股票列表"""
        self.stock_tree.delete(*self.stock_tree.get_children())
        self.stock_list.clear()
    
    def clear_result(self):
        self.result_text.delete(1.0, tk.END)
    
    def log(self, msg):
        self.result_text.insert(tk.END, msg + "\n")
        self.result_text.see(tk.END)
        self.root.update()
    
    def start_analyze(self):
        if len(self.stock_list) < 1:
            messagebox.showwarning("提示", "请先添加股票")
            return
        self.analyze_btn.config(state=tk.DISABLED)
        self.verify_btn.config(state=tk.DISABLED)
        self.result_text.delete(1.0, tk.END)
        threading.Thread(target=self.do_analyze, daemon=True).start()
    
    def start_verify(self):
        """验证模式：留一法验证特征有效性"""
        if len(self.stock_list) < 2:
            messagebox.showwarning("提示", "验证模式需要至少2只股票")
            return
        self.analyze_btn.config(state=tk.DISABLED)
        self.verify_btn.config(state=tk.DISABLED)
        self.result_text.delete(1.0, tk.END)
        threading.Thread(target=self.do_verify, daemon=True).start()
    
    def do_analyze(self):
        try:
            self.log(f"开始分析 {len(self.stock_list)} 只股票...\n")
            self.log('='*60)
            
            features_list = []
            for i, stock in enumerate(self.stock_list):
                self.status_var.set(f"分析 {stock['name']} ({i+1}/{len(self.stock_list)})")
                features = self.analyze_stock(stock['code'], stock['name'], stock['period'], stock['start_date'], stock['end_date'])
                if features:
                    features_list.append(features)
            
            if not features_list:
                self.log("\n没有足够数据进行分析")
                return
            
            self.summarize_features(features_list)
            
        except Exception as e:
            self.log(f"\n错误: {e}")
        finally:
            self.status_var.set("完成")
            self.analyze_btn.config(state=tk.NORMAL)
            self.verify_btn.config(state=tk.NORMAL)
    
    def do_verify(self):
        """留一法验证：用N-1只股票提取特征，验证能否找到第N只"""
        try:
            n = len(self.stock_list)
            self.log(f"开始验证模式（留一法）：{n}只股票\n")
            self.log("原理：每次留出1只作为验证，用其余股票提取共同特征，")
            self.log("然后用这些特征去全市场扫描，看能否找到留出的那只。\n")
            self.log('='*60)
            
            # 先分析所有股票的特征
            all_features = []
            for i, stock in enumerate(self.stock_list):
                self.status_var.set(f"分析 {stock['name']} ({i+1}/{n})")
                features = self.analyze_stock(stock['code'], stock['name'], stock['period'], 
                                            stock['start_date'], stock['end_date'])
                if features:
                    all_features.append(features)
            
            if len(all_features) < 2:
                self.log("\n有效数据不足，无法验证")
                return
            
            self.log(f"\n{'='*60}")
            self.log("开始留一法验证...")
            self.log('='*60)
            
            # 对每只股票进行留一验证
            success_count = 0
            for i in range(len(all_features)):
                target = all_features[i]
                train_set = [f for j, f in enumerate(all_features) if j != i]
                
                self.log(f"\n【验证 {i+1}/{len(all_features)}】目标: {target['name']}({target['code']})")
                self.log(f"  训练集: {', '.join([f['name'] for f in train_set])}")
                
                # 提取训练集的共同特征
                conditions = self.extract_common_conditions(train_set)
                self.log(f"  提取的条件: {conditions}")
                
                # 检查目标是否满足这些条件
                match, details = self.check_conditions(target, conditions)
                
                if match:
                    self.log(f"  ✓ 验证通过！目标股票满足所有条件")
                    success_count += 1
                else:
                    self.log(f"  ✗ 验证失败！不满足的条件: {details}")
            
            # 总结
            self.log(f"\n{'='*60}")
            self.log(f"验证结果: {success_count}/{len(all_features)} 通过 ({success_count/len(all_features)*100:.0f}%)")
            self.log('='*60)
            
            if success_count == len(all_features):
                self.log("\n★ 所有验证通过！提取的特征具有较好的泛化能力。")
                # 显示最终的共同特征
                final_conditions = self.extract_common_conditions(all_features)
                self.log(f"\n最终共同特征条件:")
                for cond, val in final_conditions.items():
                    self.log(f"  - {cond}: {val}")
            else:
                self.log(f"\n部分验证失败，特征可能需要调整。")
                self.log("建议：放宽条件阈值，或增加更多样本。")
            
        except Exception as e:
            self.log(f"\n错误: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.status_var.set("完成")
            self.analyze_btn.config(state=tk.NORMAL)
            self.verify_btn.config(state=tk.NORMAL)
    
    def extract_common_conditions(self, features_list):
        """从特征列表中提取共同条件（宽松版）"""
        df = pd.DataFrame(features_list)
        conditions = {}
        
        # 布尔特征：只有100%满足才作为必要条件
        bool_features = ['ma_bullish', 'ma_bearish', 'price_above_ma5', 'price_above_ma10', 
                        'price_above_ma20', 'macd_golden', 'macd_positive', 'macd_hist_positive',
                        'vol_amplify', 'vol_shrink']
        
        for feat in bool_features:
            if feat in df.columns:
                pct = df[feat].mean()
                # 只有100%满足才作为条件
                if pct == 1.0:
                    conditions[feat] = True
                elif pct == 0.0:
                    conditions[feat] = False
        
        # 数值特征：取范围（放宽50%）
        if 'rsi' in df.columns:
            rsi_min = df['rsi'].min()
            rsi_max = df['rsi'].max()
            margin = (rsi_max - rsi_min) * 0.5 + 10  # 放宽50%+10
            conditions['rsi_range'] = (max(0, rsi_min - margin), min(100, rsi_max + margin))
        
        if 'k' in df.columns:
            k_min = df['k'].min()
            k_max = df['k'].max()
            margin = (k_max - k_min) * 0.5 + 10
            conditions['k_range'] = (max(0, k_min - margin), min(100, k_max + margin))
        
        if 'price_vs_ma20' in df.columns:
            ma20_min = df['price_vs_ma20'].min()
            ma20_max = df['price_vs_ma20'].max()
            margin = (ma20_max - ma20_min) * 0.5 + 5
            conditions['price_vs_ma20_range'] = (ma20_min - margin, ma20_max + margin)
        
        return conditions
    
    def check_conditions(self, features, conditions):
        """检查单只股票是否满足条件"""
        failed = []
        
        for cond, val in conditions.items():
            if cond.endswith('_range'):
                # 范围条件
                feat_name = cond.replace('_range', '')
                if feat_name in features:
                    feat_val = features[feat_name]
                    if not (val[0] <= feat_val <= val[1]):
                        failed.append(f"{feat_name}={feat_val:.1f}不在[{val[0]:.1f},{val[1]:.1f}]")
            else:
                # 布尔条件
                if cond in features:
                    if features[cond] != val:
                        failed.append(f"{cond}={features[cond]}≠{val}")
        
        return len(failed) == 0, failed
    
    def get_stock_data(self, code, period):
        """获取股票数据，支持不同周期"""
        period_map = {
            '日线': 'daily',
            '60分钟': '60',
            '30分钟': '30',
            '15分钟': '15',
            '5分钟': '5',
            '1分钟': '1',
        }
        ak_period = period_map.get(period, 'daily')
        
        if ak_period == 'daily':
            df = ak.stock_zh_a_hist(symbol=code, period='daily', adjust='qfq')
            df['时间'] = pd.to_datetime(df['日期'])
        else:
            # 分钟数据
            df = ak.stock_zh_a_hist_min_em(symbol=code, period=ak_period, adjust='qfq')
            df['时间'] = pd.to_datetime(df['时间'])
            # 重命名列以统一
            df = df.rename(columns={'开盘': '开盘', '收盘': '收盘', '最高': '最高', '最低': '最低', '成交量': '成交量'})
        
        return df
    
    def analyze_stock(self, code, name, period='日线', start_date=None, end_date=None):
        """分析单只股票在指定时间段的技术指标"""
        try:
            df = self.get_stock_data(code, period)
            if df is None or len(df) < 5:
                self.log(f"  {code} 数据不足")
                return None
            
            # 筛选时间段
            if start_date and end_date:
                start = pd.to_datetime(start_date)
                end = pd.to_datetime(end_date) + pd.Timedelta(days=1)  # 包含结束日期
                df_before = df[df['时间'] < start].tail(30)
                df_period = df[(df['时间'] >= start) & (df['时间'] < end)]
                if len(df_period) < 1:
                    self.log(f"  {code} 在 {start_date}~{end_date} 无数据")
                    return None
                df = pd.concat([df_before, df_period])
                period_str = f"{start_date} ~ {end_date}"
                period_len = len(df_period)
            else:
                df = df.tail(100)
                period_str = "最新"
                period_len = min(60, len(df))
                df_period = df.tail(period_len)
            
            close = df['收盘']
            
            # 计算指标
            df['MA5'] = close.rolling(5, min_periods=1).mean()
            df['MA10'] = close.rolling(10, min_periods=1).mean()
            df['MA20'] = close.rolling(20, min_periods=1).mean()
            
            macd = ta.trend.MACD(close)
            df['MACD'] = macd.macd()
            df['MACD_signal'] = macd.macd_signal()
            df['MACD_hist'] = macd.macd_diff()
            
            df['RSI'] = ta.momentum.RSIIndicator(close, window=min(14, len(df)-1) if len(df) > 1 else 14).rsi()
            df['VOL_MA5'] = df['成交量'].rolling(5, min_periods=1).mean()
            
            # KDJ
            window = min(9, len(df))
            low_9 = df['最低'].rolling(window, min_periods=1).min()
            high_9 = df['最高'].rolling(window, min_periods=1).max()
            rsv = (close - low_9) / (high_9 - low_9 + 0.0001) * 100
            df['K'] = rsv.ewm(com=2, min_periods=1).mean()
            df['D'] = df['K'].ewm(com=2, min_periods=1).mean()
            df['J'] = 3 * df['K'] - 2 * df['D']
            
            latest = df.iloc[-1]
            prev = df.iloc[-2] if len(df) >= 2 else latest
            
            # 涨幅计算
            first_price = df_period.iloc[0]['收盘']
            last_price = df_period.iloc[-1]['收盘']
            max_price = df_period['最高'].max()
            
            period_gain = (last_price - first_price) / first_price * 100
            max_gain = (max_price - first_price) / first_price * 100
            
            features = {
                'code': code, 'name': name, 'period': period, 'time_range': period_str,
                'start_price': first_price,
                'end_price': last_price,
                'period_gain': period_gain,
                'max_gain': max_gain,
                'bars': period_len,
                'ma_bullish': latest['MA5'] > latest['MA10'] > latest['MA20'] if pd.notna(latest['MA20']) else False,
                'ma_bearish': latest['MA5'] < latest['MA10'] < latest['MA20'] if pd.notna(latest['MA20']) else False,
                'price_above_ma5': latest['收盘'] > latest['MA5'] if pd.notna(latest['MA5']) else False,
                'price_above_ma10': latest['收盘'] > latest['MA10'] if pd.notna(latest['MA10']) else False,
                'price_above_ma20': latest['收盘'] > latest['MA20'] if pd.notna(latest['MA20']) else False,
                'price_vs_ma20': (latest['收盘'] - latest['MA20']) / latest['MA20'] * 100 if pd.notna(latest['MA20']) and latest['MA20'] > 0 else 0,
                'macd': latest['MACD'] if pd.notna(latest['MACD']) else 0,
                'macd_golden': latest['MACD'] > latest['MACD_signal'] if pd.notna(latest['MACD']) else False,
                'macd_positive': latest['MACD'] > 0 if pd.notna(latest['MACD']) else False,
                'macd_hist_positive': latest['MACD_hist'] > 0 if pd.notna(latest['MACD_hist']) else False,
                'rsi': latest['RSI'] if pd.notna(latest['RSI']) else 50,
                'rsi_oversold': latest['RSI'] < 30 if pd.notna(latest['RSI']) else False,
                'rsi_overbought': latest['RSI'] > 70 if pd.notna(latest['RSI']) else False,
                'k': latest['K'] if pd.notna(latest['K']) else 50,
                'd': latest['D'] if pd.notna(latest['D']) else 50,
                'j': latest['J'] if pd.notna(latest['J']) else 50,
                'kdj_golden': (latest['K'] > latest['D'] and prev['K'] <= prev['D']) if pd.notna(latest['K']) else False,
                'kdj_oversold': (latest['K'] < 20 and latest['D'] < 20) if pd.notna(latest['K']) else False,
                'vol_ratio_5': latest['成交量'] / latest['VOL_MA5'] if pd.notna(latest['VOL_MA5']) and latest['VOL_MA5'] > 0 else 0,
                'vol_amplify': latest['成交量'] > latest['VOL_MA5'] * 1.5 if pd.notna(latest['VOL_MA5']) else False,
                'vol_shrink': latest['成交量'] < latest['VOL_MA5'] * 0.7 if pd.notna(latest['VOL_MA5']) else False,
            }
            
            self.log(f"\n【{name}({code})】{period} {period_str} ({period_len}根K线)")
            self.log(f"  价格: {first_price:.2f} → {last_price:.2f} (涨幅{period_gain:.1f}%, 最大{max_gain:.1f}%)")
            if pd.notna(latest['MA5']):
                self.log(f"  均线: MA5={latest['MA5']:.2f} MA10={latest['MA10']:.2f} MA20={latest['MA20']:.2f}")
            if pd.notna(latest['MACD']):
                self.log(f"  MACD:{latest['MACD']:.3f} RSI:{latest['RSI']:.1f} KDJ:{latest['K']:.1f}/{latest['D']:.1f}/{latest['J']:.1f}")
            
            return features
        except Exception as e:
            self.log(f"  {code} 分析失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def summarize_features(self, features_list):
        df = pd.DataFrame(features_list)
        n = len(df)
        
        self.log(f"\n{'='*60}")
        self.log(f"共同特征分析（{n}只股票/时间段）")
        self.log('='*60)
        
        # 显示涨幅统计
        self.log("\n【涨幅统计】")
        self.log(f"  时间段涨幅: 均值{df['period_gain'].mean():.1f}%, 范围[{df['period_gain'].min():.1f}%~{df['period_gain'].max():.1f}%]")
        self.log(f"  最大涨幅: 均值{df['max_gain'].mean():.1f}%, 范围[{df['max_gain'].min():.1f}%~{df['max_gain'].max():.1f}%]")
        self.log(f"  K线数量: 均值{df['bars'].mean():.0f}根")
        
        bool_features = {
            'ma_bullish': '均线多头排列(MA5>MA10>MA20)',
            'ma_bearish': '均线空头排列',
            'price_above_ma5': '价格在MA5上方',
            'price_above_ma10': '价格在MA10上方',
            'price_above_ma20': '价格在MA20上方',
            'macd_golden': 'MACD金叉(DIF>DEA)',
            'macd_positive': 'MACD在零轴上方',
            'macd_hist_positive': 'MACD柱为正',
            'rsi_oversold': 'RSI超卖(<30)',
            'rsi_overbought': 'RSI超买(>70)',
            'kdj_golden': 'KDJ金叉',
            'kdj_oversold': 'KDJ超卖区',
            'vol_amplify': '放量(>1.5倍)',
            'vol_shrink': '缩量(<0.7倍)',
        }
        
        self.log("\n【形态特征占比】")
        common = []
        for col, desc in bool_features.items():
            if col in df.columns:
                pct = df[col].mean() * 100
                bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
                self.log(f"  {desc}: {bar} {pct:.0f}%")
                if pct >= 70:
                    common.append((desc, pct))
        
        self.log("\n【数值指标】")
        self.log(f"  RSI: 均值{df['rsi'].mean():.1f} [{df['rsi'].min():.0f}-{df['rsi'].max():.0f}]")
        self.log(f"  KDJ-K: 均值{df['k'].mean():.1f} [{df['k'].min():.0f}-{df['k'].max():.0f}]")
        self.log(f"  距MA20: 均值{df['price_vs_ma20'].mean():.1f}%")
        
        if common:
            self.log("\n【★ 共同特征（>70%满足）】")
            for desc, pct in common:
                self.log(f"  ★ {pct:.0f}%: {desc}")

def main():
    root = tk.Tk()
    app = StockAnalyzerGUI(root)
    root.mainloop()

if __name__ == '__main__':
    main()
