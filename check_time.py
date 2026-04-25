"""检查系统时间"""
from datetime import datetime
import calendar

print("="*50)
print("系统时间检查")
print("="*50)

now = datetime.now()
print(f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"今天是: {calendar.day_name[now.weekday()]} (星期{['一','二','三','四','五','六','日'][now.weekday()]})")

print()
print("最近日期星期对照:")
for i in range(5):
    d = datetime(2026, 1, 23 + i)
    weekday_cn = ['一','二','三','四','五','六','日'][d.weekday()]
    print(f"  2026-01-{23+i}: {calendar.day_name[d.weekday()]} (星期{weekday_cn})")

print()
print("结论:")
print("  1月23日(周五) = 正常交易日")
print("  1月24日(周六) = 休市")
print("  1月25日(周日) = 休市")
print("  1月26日(周一) = 正常交易日")
