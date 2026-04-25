"""
虚拟交易账户 - AI自主交易和学习系统
每日自动：选股 -> 交易 -> 持仓管理 -> 复盘分析 -> 策略优化
"""
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
from pathlib import Path

class VirtualPortfolio:
    """虚拟交易账户"""
    
    def __init__(self, initial_capital=100000):
        self.data_dir = Path("virtual_trading_data")
        self.data_dir.mkdir(exist_ok=True)
        
        # 账户文件
        self.portfolio_file = self.data_dir / "portfolio.json"
        self.trades_file = self.data_dir / "trades.json"
        self.daily_records_file = self.data_dir / "daily_records.json"
        self.learning_file = self.data_dir / "learning_log.json"
        
        # 初始化或加载账户
        if self.portfolio_file.exists():
            self.load_portfolio()
        else:
            self.initial_capital = initial_capital
            self.cash = initial_capital
            self.positions = {}  # {code: {name, shares, cost, buy_date}}
            self.trades = []
            self.daily_records = []
            self.learning_log = []
            self.save_portfolio()
    
    def load_portfolio(self):
        """加载账户数据"""
        with open(self.portfolio_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self.initial_capital = data['initial_capital']
            self.cash = data['cash']
            self.positions = data['positions']
        
        if self.trades_file.exists():
            with open(self.trades_file, 'r', encoding='utf-8') as f:
                self.trades = json.load(f)
        else:
            self.trades = []
        
        if self.daily_records_file.exists():
            with open(self.daily_records_file, 'r', encoding='utf-8') as f:
                self.daily_records = json.load(f)
        else:
            self.daily_records = []
        
        if self.learning_file.exists():
            with open(self.learning_file, 'r', encoding='utf-8') as f:
                self.learning_log = json.load(f)
        else:
            self.learning_log = []
    
    def save_portfolio(self):
        """保存账户数据"""
        data = {
            'initial_capital': self.initial_capital,
            'cash': self.cash,
            'positions': self.positions,
            'last_update': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        with open(self.portfolio_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        with open(self.trades_file, 'w', encoding='utf-8') as f:
            json.dump(self.trades, f, ensure_ascii=False, indent=2)
        
        with open(self.daily_records_file, 'w', encoding='utf-8') as f:
            json.dump(self.daily_records, f, ensure_ascii=False, indent=2)
        
        with open(self.learning_file, 'w', encoding='utf-8') as f:
            json.dump(self.learning_log, f, ensure_ascii=False, indent=2)
    
    def get_current_price(self, code):
        """获取实时价格"""
        try:
            df = ak.stock_zh_a_spot_em()
            stock = df[df['代码'] == code]
            if len(stock) > 0:
                return float(stock.iloc[0]['最新价'])
        except:
            pass
        return None
    
    def get_total_value(self):
        """计算总资产"""
        position_value = 0
        for code, pos in self.positions.items():
            price = self.get_current_price(code)
            if price:
                position_value += price * pos['shares']
        return self.cash + position_value
    
    def buy(self, code, name, price, shares, reason=""):
        """买入股票"""
        cost = price * shares * 1.0003  # 含手续费
        if cost > self.cash:
            return False, "资金不足"
        
        self.cash -= cost
        if code in self.positions:
            # 加仓
            old_pos = self.positions[code]
            total_shares = old_pos['shares'] + shares
            total_cost = old_pos['cost'] * old_pos['shares'] + cost
            self.positions[code] = {
                'name': name,
                'shares': total_shares,
                'cost': total_cost / total_shares,
                'buy_date': old_pos['buy_date']
            }
        else:
            # 新建仓位
            self.positions[code] = {
                'name': name,
                'shares': shares,
                'cost': cost / shares,
                'buy_date': datetime.now().strftime('%Y-%m-%d')
            }
        
        # 记录交易
        trade = {
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'type': 'buy',
            'code': code,
            'name': name,
            'price': price,
            'shares': shares,
            'amount': cost,
            'reason': reason
        }
        self.trades.append(trade)
        self.save_portfolio()
        return True, "买入成功"
    
    def sell(self, code, shares, price, reason=""):
        """卖出股票"""
        if code not in self.positions:
            return False, "无持仓"
        
        pos = self.positions[code]
        if shares > pos['shares']:
            return False, "持仓不足"
        
        amount = price * shares * 0.9987  # 扣除手续费和印花税
        self.cash += amount
        
        # 计算盈亏
        profit = (price - pos['cost']) * shares
        profit_rate = profit / (pos['cost'] * shares) * 100
        
        # 更新持仓
        if shares == pos['shares']:
            del self.positions[code]
        else:
            self.positions[code]['shares'] -= shares
        
        # 记录交易
        trade = {
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'type': 'sell',
            'code': code,
            'name': pos['name'],
            'price': price,
            'shares': shares,
            'amount': amount,
            'profit': profit,
            'profit_rate': profit_rate,
            'reason': reason
        }
        self.trades.append(trade)
        self.save_portfolio()
        return True, f"卖出成功，盈亏: {profit:.2f} ({profit_rate:+.2f}%)"
    
    def get_position_status(self):
        """获取持仓状态"""
        positions = []
        for code, pos in self.positions.items():
            current_price = self.get_current_price(code)
            if current_price:
                market_value = current_price * pos['shares']
                profit = (current_price - pos['cost']) * pos['shares']
                profit_rate = profit / (pos['cost'] * pos['shares']) * 100
                hold_days = (datetime.now() - datetime.strptime(pos['buy_date'], '%Y-%m-%d')).days
                
                positions.append({
                    'code': code,
                    'name': pos['name'],
                    'shares': pos['shares'],
                    'cost': pos['cost'],
                    'current_price': current_price,
                    'market_value': market_value,
                    'profit': profit,
                    'profit_rate': profit_rate,
                    'hold_days': hold_days,
                    'buy_date': pos['buy_date']
                })
        return positions
    
    def print_status(self):
        """打印账户状态"""
        total_value = self.get_total_value()
        total_profit = total_value - self.initial_capital
        total_return = total_profit / self.initial_capital * 100
        
        print("\n" + "="*70)
        print(f"虚拟账户状态 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("="*70)
        print(f"初始资金: {self.initial_capital:,.2f}")
        print(f"当前现金: {self.cash:,.2f}")
        print(f"持仓市值: {total_value - self.cash:,.2f}")
        print(f"总资产:   {total_value:,.2f}")
        print(f"总盈亏:   {total_profit:+,.2f} ({total_return:+.2f}%)")
        
        positions = self.get_position_status()
        if positions:
            print(f"\n持仓明细 ({len(positions)}只):")
            for i, pos in enumerate(positions, 1):
                print(f"\n{i}. {pos['code']} {pos['name']}")
                print(f"   持仓: {pos['shares']}股  成本: {pos['cost']:.2f}  现价: {pos['current_price']:.2f}")
                print(f"   市值: {pos['market_value']:,.2f}  盈亏: {pos['profit']:+,.2f} ({pos['profit_rate']:+.2f}%)")
                print(f"   持有: {pos['hold_days']}天  买入日期: {pos['buy_date']}")
        else:
            print("\n当前无持仓")
        
        print("="*70)
