import akshare as ak

df = ak.stock_zh_a_spot_em()
bbg = df[df['代码'] == '002251']

print("步步高(002251)实时数据:")
print(bbg[['代码','名称','最新价','涨跌幅','昨收']].to_string(index=False))

# Excel中的成本
cost = 5.952
buy_amount = 20000
current = float(bbg['最新价'].values[0])
shares = buy_amount / cost
profit = (current - cost) * shares
profit_rate = (current - cost) / cost * 100

print(f"\n根据Excel成本计算:")
print(f"  成本价: {cost}")
print(f"  买入金额: {buy_amount}")
print(f"  持股数: {shares:.0f}")
print(f"  现价: {current}")
print(f"  盈亏金额: {profit:.2f}")
print(f"  盈亏率: {profit_rate:.2f}%")
