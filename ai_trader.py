"""
AI自主交易员
每日自动选股、交易决策、执行操作
"""
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from virtual_portfolio import VirtualPortfolio
import json

class AITrader:
    """AI交易员 - 自主学习和交易"""
    
    def __init__(self):
        self.portfolio = VirtualPortfolio()
        self.max_positions = 5  # 最多持仓5只
        self.position_size = 0.15  # 每只股票占总资产15%
        self.stop_loss = -0.08  # 止损-8%
        self.take_profit = 0.20  # 止盈+20%
        self.max_hold_days = 15  # 最长持有15天
    
    def scan_opportunities(self):
        """扫描交易机会"""
        print("\n正在扫描市场机会...")
        
        try:
            df = ak.stock_zh_a_spot_em()
            df = df[df['代码'].str.match(r'^(60|00)')]
            df = df[~df['名称'].str.contains('ST|退')]
            df = df[df['成交额'] > 5e7]
            df = df[df['涨跌幅'] > -5]
            df = df[df['涨跌幅'] < 9.5]
            
            # 综合评分
            df['综合得分'] = df['成交额'] / 1e8 + df['涨跌幅'] * 10
            candidates = df.nlargest(30, '综合得分')
            
            opportunities = []
            for _, row in candidates.iterrows():
                code = row['代码']
                name = row['名称']
                
                try:
                    hist = ak.stock_zh_a_hist(symbol=code, period='daily', 
                                              start_date='20241001', adjust='qfq')
                    if hist is None or len(hist) < 30:
                        continue
                    
                    hist = hist.tail(60)
                    close = hist['收盘'].values
                    volume = hist['成交量'].values
                    
                    # 计算指标
                    ma5 = pd.Series(close).rolling(5).mean().values
                    ma10 = pd.Series(close).rolling(10).mean().values
                    ma20 = pd.Series(close).rolling(20).mean().values
                    
                    current_price = close[-1]
                    
                    # 评分
                    score = 0
                    signals = []
                    
                    if ma5[-1] > ma10[-1] > ma20[-1]:
                        score += 3
                        signals.append('均线多头')
                    
                    if current_price > ma20[-1]:
                        score += 2
                        signals.append('站上MA20')
                    
                    vol_ma5 = pd.Series(volume).rolling(5).mean().values[-2]
                    if volume[-1] > vol_ma5 * 1.5:
                        score += 2
                        signals.append('放量')
                    
                    if row['涨跌幅'] > 0:
                        score += 1
                    
                    if score >= 5:
                        opportunities.append({
                            'code': code,
                            'name': name,
                            'price': current_price,
                            'change': row['涨跌幅'],
                            'score': score,
                            'signals': signals
                        })
                except:
                    continue
            
            opportunities.sort(key=lambda x: x['score'], reverse=True)
            return opportunities[:10]
        
        except Exception as e:
            print(f"扫描失败: {e}")
            return []
    
    def make_buy_decisions(self, opportunities):
        """做出买入决策"""
        decisions = []
        
        # 检查可用仓位
        current_positions = len(self.portfolio.positions)
        available_slots = self.max_positions - current_positions
        
        if available_slots <= 0:
            print("仓位已满，不再买入")
            return decisions
        
        # 计算可用资金
        total_value = self.portfolio.get_total_value()
        target_amount = total_value * self.position_size
        
        for opp in opportunities[:available_slots]:
            if self.portfolio.cash < target_amount:
                break
            
            shares = int(target_amount / opp['price'] / 100) * 100  # 100股整数倍
            if shares >= 100:
                decisions.append({
                    'action': 'buy',
                    'code': opp['code'],
                    'name': opp['name'],
                    'price': opp['price'],
                    'shares': shares,
                    'reason': f"评分{opp['score']}分: {', '.join(opp['signals'])}"
                })
        
        return decisions
    
    def make_sell_decisions(self):
        """做出卖出决策"""
        decisions = []
        positions = self.portfolio.get_position_status()
        
        for pos in positions:
            should_sell = False
            reason = ""
            
            # 止损
            if pos['profit_rate'] <= self.stop_loss * 100:
                should_sell = True
                reason = f"止损 ({pos['profit_rate']:.2f}%)"
            
            # 止盈
            elif pos['profit_rate'] >= self.take_profit * 100:
                should_sell = True
                reason = f"止盈 ({pos['profit_rate']:.2f}%)"
            
            # 持有时间过长
            elif pos['hold_days'] >= self.max_hold_days:
                should_sell = True
                reason = f"持有{pos['hold_days']}天，时间止盈"
            
            # 技术面恶化
            else:
                try:
                    hist = ak.stock_zh_a_hist(symbol=pos['code'], period='daily', 
                                              start_date='20241201', adjust='qfq')
                    if hist is not None and len(hist) >= 5:
                        close = hist['收盘'].values
                        ma5 = pd.Series(close).rolling(5).mean().values[-1]
                        
                        # 跌破5日线且盈利<5%
                        if pos['current_price'] < ma5 and pos['profit_rate'] < 5:
                            should_sell = True
                            reason = "跌破MA5，技术面恶化"
                except:
                    pass
            
            if should_sell:
                decisions.append({
                    'action': 'sell',
                    'code': pos['code'],
                    'name': pos['name'],
                    'price': pos['current_price'],
                    'shares': pos['shares'],
                    'reason': reason
                })
        
        return decisions
    
    def execute_trades(self, decisions):
        """执行交易决策"""
        results = []
        
        for decision in decisions:
            if decision['action'] == 'buy':
                success, msg = self.portfolio.buy(
                    decision['code'],
                    decision['name'],
                    decision['price'],
                    decision['shares'],
                    decision['reason']
                )
                results.append({
                    'action': 'buy',
                    'code': decision['code'],
                    'name': decision['name'],
                    'success': success,
                    'message': msg
                })
                print(f"  买入 {decision['code']} {decision['name']}: {msg}")
            
            elif decision['action'] == 'sell':
                success, msg = self.portfolio.sell(
                    decision['code'],
                    decision['shares'],
                    decision['price'],
                    decision['reason']
                )
                results.append({
                    'action': 'sell',
                    'code': decision['code'],
                    'name': decision['name'],
                    'success': success,
                    'message': msg
                })
                print(f"  卖出 {decision['code']} {decision['name']}: {msg}")
        
        return results
    
    def daily_routine(self):
        """每日交易流程"""
        print("\n" + "="*70)
        print(f"AI交易员开始工作 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("="*70)
        
        # 1. 检查持仓，决定是否卖出
        print("\n【步骤1】检查持仓...")
        sell_decisions = self.make_sell_decisions()
        if sell_decisions:
            print(f"发现 {len(sell_decisions)} 个卖出信号")
            sell_results = self.execute_trades(sell_decisions)
        else:
            print("暂无卖出信号")
        
        # 2. 扫描机会，决定是否买入
        print("\n【步骤2】扫描买入机会...")
        opportunities = self.scan_opportunities()
        if opportunities:
            print(f"发现 {len(opportunities)} 个潜在机会")
            buy_decisions = self.make_buy_decisions(opportunities)
            if buy_decisions:
                print(f"决定买入 {len(buy_decisions)} 只股票")
                buy_results = self.execute_trades(buy_decisions)
            else:
                print("暂不买入")
        else:
            print("未发现合适机会")
        
        # 3. 记录每日状态
        self.record_daily_status()
        
        # 4. 显示账户状态
        self.portfolio.print_status()
        
        print("\n今日交易完成！")
    
    def record_daily_status(self):
        """记录每日账户状态"""
        total_value = self.portfolio.get_total_value()
        positions = self.portfolio.get_position_status()
        
        record = {
            'date': datetime.now().strftime('%Y-%m-%d'),
            'total_value': total_value,
            'cash': self.portfolio.cash,
            'position_count': len(positions),
            'total_return': (total_value - self.portfolio.initial_capital) / self.portfolio.initial_capital * 100
        }
        
        self.portfolio.daily_records.append(record)
        self.portfolio.save_portfolio()

if __name__ == "__main__":
    trader = AITrader()
    trader.daily_routine()
