"""
生成AI交易报告
导出Excel格式的详细报告
"""
import pandas as pd
from datetime import datetime
from virtual_portfolio import VirtualPortfolio
from ai_review import AIReviewer
from pathlib import Path

def generate_report():
    """生成交易报告"""
    print("正在生成交易报告...")
    
    portfolio = VirtualPortfolio()
    reviewer = AIReviewer()
    
    # 创建Excel写入器
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"AI交易报告_{timestamp}.xlsx"
    
    with pd.ExcelWriter(filename, engine='openpyxl') as writer:
        
        # 1. 账户概览
        total_value = portfolio.get_total_value()
        total_profit = total_value - portfolio.initial_capital
        total_return = total_profit / portfolio.initial_capital * 100
        
        overview = pd.DataFrame([{
            '报告日期': datetime.now().strftime('%Y-%m-%d %H:%M'),
            '初始资金': portfolio.initial_capital,
            '当前现金': portfolio.cash,
            '持仓市值': total_value - portfolio.cash,
            '总资产': total_value,
            '累计盈亏': total_profit,
            '收益率': f"{total_return:.2f}%"
        }])
        overview.to_excel(writer, sheet_name='账户概览', index=False)
        
        # 2. 当前持仓
        positions = portfolio.get_position_status()
        if positions:
            df_pos = pd.DataFrame(positions)
            df_pos = df_pos[['code', 'name', 'shares', 'cost', 'current_price', 
                            'market_value', 'profit', 'profit_rate', 'hold_days', 'buy_date']]
            df_pos.columns = ['代码', '名称', '持股数', '成本价', '现价', 
                             '市值', '盈亏', '收益率%', '持有天数', '买入日期']
            df_pos.to_excel(writer, sheet_name='当前持仓', index=False)
        
        # 3. 交易明细
        if portfolio.trades:
            df_trades = pd.DataFrame(portfolio.trades)
            df_trades = df_trades.sort_values('date', ascending=False)
            
            # 重命名列
            column_map = {
                'date': '日期',
                'type': '类型',
                'code': '代码',
                'name': '名称',
                'price': '价格',
                'shares': '数量',
                'amount': '金额',
                'reason': '原因'
            }
            
            # 添加盈亏列（仅卖出）
            if 'profit' in df_trades.columns:
                column_map['profit'] = '盈亏'
                column_map['profit_rate'] = '收益率%'
            
            df_trades = df_trades.rename(columns=column_map)
            df_trades['类型'] = df_trades['类型'].map({'buy': '买入', 'sell': '卖出'})
            
            df_trades.to_excel(writer, sheet_name='交易明细', index=False)
        
        # 4. 每日资产
        if portfolio.daily_records:
            df_daily = pd.DataFrame(portfolio.daily_records)
            df_daily.columns = ['日期', '总资产', '现金', '持仓数', '收益率%']
            df_daily.to_excel(writer, sheet_name='每日资产', index=False)
        
        # 5. 交易统计
        trade_stats = reviewer.analyze_trades(days=30)
        if trade_stats and trade_stats.get('sell_count', 0) > 0:
            stats = pd.DataFrame([{
                '统计周期': trade_stats['period'],
                '总交易次数': trade_stats['total_trades'],
                '买入次数': trade_stats['buy_count'],
                '卖出次数': trade_stats['sell_count'],
                '盈利次数': trade_stats['win_count'],
                '亏损次数': trade_stats['loss_count'],
                '胜率%': f"{trade_stats['win_rate']:.2f}",
                '总盈亏': trade_stats['total_profit'],
                '平均盈亏': trade_stats['avg_profit'],
                '平均收益率%': f"{trade_stats['avg_profit_rate']:.2f}",
                '最大盈利': trade_stats['max_win'],
                '最大亏损': trade_stats['max_loss'],
                '平均持仓天数': f"{trade_stats['avg_hold_days']:.1f}"
            }])
            stats.to_excel(writer, sheet_name='交易统计', index=False)
        
        # 6. 整体表现
        perf = reviewer.analyze_performance()
        if perf:
            performance = pd.DataFrame([{
                '交易天数': perf['trading_days'],
                '开始日期': perf['start_date'],
                '结束日期': perf['end_date'],
                '当前收益率%': f"{perf['current_return']:.2f}",
                '最高收益率%': f"{perf['max_return']:.2f}",
                '最低收益率%': f"{perf['min_return']:.2f}",
                '最大回撤%': f"{perf['max_drawdown']:.2f}",
                '夏普比率': f"{perf['sharpe_ratio']:.2f}"
            }])
            performance.to_excel(writer, sheet_name='整体表现', index=False)
        
        # 7. AI洞察
        insights = reviewer.generate_insights()
        if insights:
            df_insights = pd.DataFrame(insights)
            df_insights.columns = ['类型', '洞察']
            df_insights['类型'] = df_insights['类型'].map({
                'positive': '✓ 优势',
                'warning': '⚠ 警告',
                'info': 'ℹ 信息'
            })
            df_insights.to_excel(writer, sheet_name='AI洞察', index=False)
        
        # 8. 优化建议
        suggestions = reviewer.generate_suggestions()
        if suggestions:
            df_sug = pd.DataFrame({'建议': suggestions})
            df_sug.to_excel(writer, sheet_name='优化建议', index=False)
    
    print(f"✓ 报告已生成: {filename}")
    return filename

if __name__ == "__main__":
    generate_report()
