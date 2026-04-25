# AI自主交易系统使用指南

## 系统简介

这是一个完全自动化的AI交易系统，能够：
- 🤖 **自主选股**：每日扫描市场，评分筛选机会
- 💰 **自动交易**：根据策略自动买入卖出
- 📊 **持仓管理**：动态管理仓位，止盈止损
- 📈 **每日复盘**：分析交易表现，总结经验
- 🧠 **自我学习**：记录洞察，优化策略

## 快速开始

### 1. 首次运行（初始化账户）

```bash
# 运行一次完整流程
python auto_trading_system.py
```

这会：
- 创建虚拟账户（初始资金10万）
- 扫描市场并做出交易决策
- 执行买入/卖出操作
- 进行复盘分析
- 保存所有数据到 `virtual_trading_data/` 目录

### 2. 查看账户状态

```bash
python view_portfolio.py
```

显示：
- 当前资金和持仓
- 总资产和收益率
- 最近交易记录
- 收益曲线

### 3. 单独运行复盘

```bash
python ai_review.py
```

查看：
- 交易统计（胜率、盈亏）
- 整体表现（收益、回撤）
- 交易模式分析
- AI洞察和建议

### 4. 设置自动定时运行

```bash
python schedule_trading.py
```

每个交易日15:30自动运行（收盘后）

## 系统架构

```
virtual_portfolio.py      # 虚拟账户（资金、持仓、交易记录）
    ↓
ai_trader.py             # AI交易员（选股、决策、执行）
    ↓
ai_review.py             # AI复盘师（分析、学习、优化）
    ↓
auto_trading_system.py   # 完整流程（交易+复盘）
```

## 交易策略

### 选股标准（评分系统）
- ✓ 均线多头排列（3分）
- ✓ 价格站上MA20（2分）
- ✓ 成交量放大（2分）
- ✓ 今日上涨（1分）
- ✓ 箱体突破（2分）
- ✓ 换手率适中（1分）

**最低入选分数：5分**

### 仓位管理
- 最多持仓：5只股票
- 单只仓位：总资产的15%
- 买入单位：100股整数倍

### 风控规则
- 止损：-8%
- 止盈：+20%
- 时间止盈：持有15天
- 技术止损：跌破MA5且盈利<5%

## 数据文件说明

所有数据保存在 `virtual_trading_data/` 目录：

```
virtual_trading_data/
├── portfolio.json        # 账户状态（资金、持仓）
├── trades.json          # 所有交易记录
├── daily_records.json   # 每日账户快照
└── learning_log.json    # AI学习日志
```

## 复盘指标

### 交易统计
- 胜率：盈利交易占比
- 平均盈亏：每笔交易平均收益
- 盈亏比：平均盈利/平均亏损
- 平均持仓天数

### 整体表现
- 累计收益率
- 最大回撤
- 夏普比率
- 收益曲线

### AI洞察
- 策略有效性评估
- 风险控制评价
- 操作风格分析

### 优化建议
- 选股标准调整
- 止盈止损优化
- 仓位管理改进
- 持仓时间建议

## 使用场景

### 场景1：每日自动运行
```bash
# 方式1：手动运行
python auto_trading_system.py

# 方式2：定时自动
python schedule_trading.py
```

### 场景2：只看不动
```bash
# 只查看账户，不交易
python view_portfolio.py
```

### 场景3：深度复盘
```bash
# 详细分析交易表现
python ai_review.py
```

### 场景4：手动交易
```python
from virtual_portfolio import VirtualPortfolio

portfolio = VirtualPortfolio()

# 买入
portfolio.buy('600519', '贵州茅台', 1650.0, 100, '手动买入')

# 卖出
portfolio.sell('600519', 100, 1700.0, '手动止盈')

# 查看
portfolio.print_status()
```

## 自定义配置

修改 `ai_trader.py` 中的参数：

```python
class AITrader:
    def __init__(self):
        self.max_positions = 5        # 最多持仓数
        self.position_size = 0.15     # 单只仓位比例
        self.stop_loss = -0.08        # 止损比例
        self.take_profit = 0.20       # 止盈比例
        self.max_hold_days = 15       # 最长持有天数
```

## 学习机制

AI系统会自动：

1. **记录每笔交易**
   - 买入原因和信号
   - 卖出原因和结果
   - 持仓时间和盈亏

2. **分析交易模式**
   - 哪些信号更有效
   - 哪些原因导致亏损
   - 最佳持仓时间

3. **生成优化建议**
   - 基于胜率调整选股
   - 基于盈亏比优化止盈止损
   - 基于回撤改进风控

4. **持续迭代**
   - 每日复盘总结
   - 积累经验数据
   - 逐步优化策略

## 注意事项

⚠️ **这是模拟交易系统**
- 使用虚拟资金，不涉及真实交易
- 数据来自AKShare，有延迟
- 仅供学习和策略验证

⚠️ **风险提示**
- 历史表现不代表未来
- 市场有风险，投资需谨慎
- 实盘前请充分测试

⚠️ **数据依赖**
- 需要网络连接获取行情
- 非交易日无法获取数据
- 建议交易日收盘后运行

## 进阶功能

### 导出交易报告
```python
from ai_review import AIReviewer
import pandas as pd

reviewer = AIReviewer()
trades = pd.DataFrame(reviewer.portfolio.trades)
trades.to_excel('交易明细.xlsx', index=False)
```

### 回测历史策略
```python
# 可以修改历史交易记录，测试不同参数
# 然后运行复盘查看效果
```

### 对比多个策略
```python
# 创建多个账户，使用不同参数
portfolio1 = VirtualPortfolio(initial_capital=100000)
portfolio2 = VirtualPortfolio(initial_capital=100000)
# 分别运行，对比表现
```

## 常见问题

**Q: 如何重置账户？**
A: 删除 `virtual_trading_data/` 目录，重新运行即可

**Q: 可以修改初始资金吗？**
A: 可以，修改 `VirtualPortfolio(initial_capital=100000)` 参数

**Q: 如何调整交易频率？**
A: 修改 `schedule_trading.py` 中的定时时间

**Q: 数据保存在哪里？**
A: `virtual_trading_data/` 目录下的JSON文件

**Q: 如何查看历史学习日志？**
A: 查看 `virtual_trading_data/learning_log.json` 文件

## 下一步计划

- [ ] 增加更多技术指标
- [ ] 支持多种交易策略
- [ ] 机器学习优化参数
- [ ] 可视化交易报告
- [ ] 实时监控和提醒
- [ ] 策略回测框架

## 联系方式

有问题或建议？欢迎反馈！
