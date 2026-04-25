"""
AI复盘分析系统
每日自动分析交易表现，总结经验教训，优化策略
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from virtual_portfolio import VirtualPortfolio
import json
from pathlib import Path

class AIReviewer:
    """AI复盘分析师"""
    
    def __init__(self):
        self.portfolio = VirtualPortfolio()
    
    def analyze_trades(self, days=30):
        """分析近期交易"""
        if not self.portfolio.trades:
            return None
        
        df = pd.DataFrame(self.portfolio.trades)
        df['date'] = pd.to_datetime(df['date'])
        
        # 筛选时间范围
        cutoff = datetime.now() - timedelta(days=days)
        df = df[df['date'] >= cutoff]
        
        if len(df) == 0:
            return None
        
        # 分析卖出交易
        sells = df[df['type'] == 'sell'].copy()
        if len(sells) == 0:
            return {
                'total_trades': len(df),
                'buy_count': len(df[df['type'] == 'buy']),
                'sell_count': 0,
                'message': '暂无卖出交易，无法分析'
            }
        
        # 胜率统计
        wins = sells[sells['profit'] > 0]
        losses = sells[sells['profit'] <= 0]
        win_rate = len(wins) / len(sells) * 100 if len(sells) > 0 else 0
        
        # 盈亏统计
        total_profit = sells['profit'].sum()
        avg_profit = sells['profit'].mean()
        avg_profit_rate = sells['profit_rate'].mean()
        
        max_win = sells['profit'].max() if len(sells) > 0 else 0
        max_loss = sells['profit'].min() if len(sells) > 0 else 0
        
        # 持仓时间分析
        avg_hold_days = self._calculate_avg_hold_days(sells)
        
        return {
            'period': f'近{days}天',
            'total_trades': len(df),
            'buy_count': len(df[df['type'] == 'buy']),
            'sell_count': len(sells),
            'win_count': len(wins),
            'loss_count': len(losses),
            'win_rate': win_rate,
            'total_profit': total_profit,
            'avg_profit': avg_profit,
            'avg_profit_rate': avg_profit_rate,
            'max_win': max_win,
            'max_loss': max_loss,
            'avg_hold_days': avg_hold_days
        }
    
    def _calculate_avg_hold_days(self, sells):
        """计算平均持仓天数"""
        hold_days = []
        for _, sell in sells.iterrows():
            # 找到对应的买入记录
            buys = pd.DataFrame(self.portfolio.trades)
            buys = buys[(buys['type'] == 'buy') & (buys['code'] == sell['code'])]
            buys = buys[buys['date'] < sell['date']]
            if len(buys) > 0:
                buy_date = pd.to_datetime(buys.iloc[-1]['date'])
                sell_date = pd.to_datetime(sell['date'])
                days = (sell_date - buy_date).days
                hold_days.append(days)
        
        return np.mean(hold_days) if hold_days else 0
    
    def analyze_performance(self):
        """分析整体表现"""
        if not self.portfolio.daily_records:
            return None
        
        df = pd.DataFrame(self.portfolio.daily_records)
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date')
        
        # 收益曲线
        returns = df['total_return'].values
        
        # 最大回撤
        max_drawdown = self._calculate_max_drawdown(df['total_value'].values)
        
        # 夏普比率（简化版）
        if len(returns) > 1:
            daily_returns = np.diff(returns)
            sharpe = np.mean(daily_returns) / np.std(daily_returns) * np.sqrt(252) if np.std(daily_returns) > 0 else 0
        else:
            sharpe = 0
        
        return {
            'trading_days': len(df),
            'current_return': returns[-1] if len(returns) > 0 else 0,
            'max_return': returns.max() if len(returns) > 0 else 0,
            'min_return': returns.min() if len(returns) > 0 else 0,
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe,
            'start_date': df['date'].min().strftime('%Y-%m-%d'),
            'end_date': df['date'].max().strftime('%Y-%m-%d')
        }
    
    def _calculate_max_drawdown(self, values):
        """计算最大回撤"""
        peak = values[0]
        max_dd = 0
        for value in values:
            if value > peak:
                peak = value
            dd = (peak - value) / peak * 100
            if dd > max_dd:
                max_dd = dd
        return max_dd
    
    def find_patterns(self):
        """发现交易模式"""
        if not self.portfolio.trades:
            return []
        
        df = pd.DataFrame(self.portfolio.trades)
        sells = df[df['type'] == 'sell'].copy()
        
        if len(sells) == 0:
            return []
        
        patterns = []
        
        # 分析止损/止盈原因
        reasons = sells['reason'].value_counts()
        for reason, count in reasons.items():
            patterns.append({
                'pattern': '卖出原因',
                'detail': reason,
                'count': int(count),
                'percentage': count / len(sells) * 100
            })
        
        # 分析盈利vs亏损的特征
        wins = sells[sells['profit'] > 0]
        losses = sells[sells['profit'] <= 0]
        
        if len(wins) > 0 and len(losses) > 0:
            # 对比买入理由
            win_reasons = pd.DataFrame(self.portfolio.trades)
            win_reasons = win_reasons[win_reasons['code'].isin(wins['code'])]
            win_reasons = win_reasons[win_reasons['type'] == 'buy']
            
            patterns.append({
                'pattern': '盈利交易特征',
                'detail': f'平均盈利{wins["profit"].mean():.2f}元 ({wins["profit_rate"].mean():.2f}%)',
                'count': len(wins)
            })
            
            patterns.append({
                'pattern': '亏损交易特征',
                'detail': f'平均亏损{losses["profit"].mean():.2f}元 ({losses["profit_rate"].mean():.2f}%)',
                'count': len(losses)
            })
        
        return patterns
    
    def generate_insights(self):
        """生成交易洞察"""
        insights = []
        
        # 分析交易数据
        trade_stats = self.analyze_trades(days=30)
        if trade_stats and trade_stats.get('sell_count', 0) > 0:
            # 胜率分析
            if trade_stats['win_rate'] >= 60:
                insights.append({
                    'type': 'positive',
                    'message': f"胜率{trade_stats['win_rate']:.1f}%，策略有效性较好"
                })
            elif trade_stats['win_rate'] < 40:
                insights.append({
                    'type': 'warning',
                    'message': f"胜率仅{trade_stats['win_rate']:.1f}%，需要优化选股策略"
                })
            
            # 盈亏比分析
            if trade_stats['avg_profit_rate'] > 5:
                insights.append({
                    'type': 'positive',
                    'message': f"平均收益率{trade_stats['avg_profit_rate']:.2f}%，盈利能力良好"
                })
            elif trade_stats['avg_profit_rate'] < 0:
                insights.append({
                    'type': 'warning',
                    'message': f"平均收益率{trade_stats['avg_profit_rate']:.2f}%，整体亏损，需调整策略"
                })
            
            # 持仓时间分析
            if trade_stats['avg_hold_days'] > 10:
                insights.append({
                    'type': 'info',
                    'message': f"平均持仓{trade_stats['avg_hold_days']:.1f}天，偏向中线操作"
                })
            elif trade_stats['avg_hold_days'] < 3:
                insights.append({
                    'type': 'info',
                    'message': f"平均持仓{trade_stats['avg_hold_days']:.1f}天，偏向短线操作"
                })
        
        # 分析整体表现
        perf = self.analyze_performance()
        if perf:
            if perf['max_drawdown'] > 15:
                insights.append({
                    'type': 'warning',
                    'message': f"最大回撤{perf['max_drawdown']:.2f}%，风险控制需加强"
                })
            
            if perf['current_return'] > 10:
                insights.append({
                    'type': 'positive',
                    'message': f"累计收益{perf['current_return']:.2f}%，表现优秀"
                })
        
        return insights
    
    def generate_suggestions(self):
        """生成优化建议"""
        suggestions = []
        
        trade_stats = self.analyze_trades(days=30)
        if not trade_stats or trade_stats.get('sell_count', 0) == 0:
            return ['继续积累交易数据，暂无足够样本分析']
        
        # 基于胜率的建议
        if trade_stats['win_rate'] < 40:
            suggestions.append("建议提高选股标准，增加技术指标权重")
            suggestions.append("考虑增加基本面筛选条件")
        
        # 基于盈亏比的建议
        if trade_stats['avg_profit_rate'] < 3:
            suggestions.append("建议调整止盈止损比例，让利润奔跑")
            suggestions.append("考虑延长持仓时间，给股票更多上涨空间")
        
        # 基于最大亏损的建议
        if trade_stats['max_loss'] < -1000:
            suggestions.append("单笔最大亏损过大，建议严格执行止损")
            suggestions.append("考虑降低单只股票仓位")
        
        # 基于持仓时间的建议
        if trade_stats['avg_hold_days'] < 2:
            suggestions.append("持仓时间过短，可能频繁交易，建议耐心持股")
        
        if not suggestions:
            suggestions.append("当前策略运行良好，保持现有节奏")
        
        return suggestions
    
    def daily_review(self):
        """每日复盘"""
        print("\n" + "="*70)
        print(f"AI复盘分析 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("="*70)
        
        # 1. 交易统计
        print("\n【交易统计】")
        trade_stats = self.analyze_trades(days=30)
        if trade_stats and trade_stats.get('sell_count', 0) > 0:
            print(f"统计周期: {trade_stats['period']}")
            print(f"总交易次数: {trade_stats['total_trades']} (买{trade_stats['buy_count']}/卖{trade_stats['sell_count']})")
            print(f"胜率: {trade_stats['win_rate']:.1f}% ({trade_stats['win_count']}胜/{trade_stats['loss_count']}负)")
            print(f"总盈亏: {trade_stats['total_profit']:+,.2f}元")
            print(f"平均盈亏: {trade_stats['avg_profit']:+,.2f}元 ({trade_stats['avg_profit_rate']:+.2f}%)")
            print(f"最大盈利: {trade_stats['max_win']:,.2f}元")
            print(f"最大亏损: {trade_stats['max_loss']:,.2f}元")
            print(f"平均持仓: {trade_stats['avg_hold_days']:.1f}天")
        else:
            print("暂无足够交易数据")
        
        # 2. 整体表现
        print("\n【整体表现】")
        perf = self.analyze_performance()
        if perf:
            print(f"交易天数: {perf['trading_days']}天 ({perf['start_date']} ~ {perf['end_date']})")
            print(f"当前收益率: {perf['current_return']:+.2f}%")
            print(f"最高收益率: {perf['max_return']:+.2f}%")
            print(f"最大回撤: {perf['max_drawdown']:.2f}%")
            print(f"夏普比率: {perf['sharpe_ratio']:.2f}")
        else:
            print("暂无历史数据")
        
        # 3. 交易模式
        print("\n【交易模式】")
        patterns = self.find_patterns()
        if patterns:
            for p in patterns[:5]:
                print(f"• {p['pattern']}: {p['detail']}")
                if 'percentage' in p:
                    print(f"  占比: {p['percentage']:.1f}%")
        else:
            print("暂无模式分析")
        
        # 4. 交易洞察
        print("\n【交易洞察】")
        insights = self.generate_insights()
        if insights:
            for insight in insights:
                icon = "✓" if insight['type'] == 'positive' else "⚠" if insight['type'] == 'warning' else "ℹ"
                print(f"{icon} {insight['message']}")
        else:
            print("继续积累数据中...")
        
        # 5. 优化建议
        print("\n【优化建议】")
        suggestions = self.generate_suggestions()
        for i, sug in enumerate(suggestions, 1):
            print(f"{i}. {sug}")
        
        # 6. 保存学习日志
        self._save_learning_log(trade_stats, perf, insights, suggestions)
        
        print("\n" + "="*70)
        print("复盘完成！")
        print("="*70)
    
    def _save_learning_log(self, trade_stats, perf, insights, suggestions):
        """保存学习日志"""
        log_entry = {
            'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'trade_stats': trade_stats,
            'performance': perf,
            'insights': insights,
            'suggestions': suggestions
        }
        
        self.portfolio.learning_log.append(log_entry)
        self.portfolio.save_portfolio()

if __name__ == "__main__":
    reviewer = AIReviewer()
    reviewer.daily_review()
