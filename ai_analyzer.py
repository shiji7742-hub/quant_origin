"""DeepSeek AI分析模块"""
import requests
import json
from config import DEEPSEEK_API_KEY, DEEPSEEK_API_URL, DEEPSEEK_MODEL

SYSTEM_PROMPT = """你是一个专业的A股量化分析师。
规则：
1. 只分析主板股票（60开头沪市、00开头深市）
2. 不分析创业板（30开头）
3. 基于技术面数据给出客观分析
4. 给出明确的操作建议：买入/卖出/观望
5. 给出建议仓位（0-100%）
6. 说明主要理由（简洁）

输出格式（JSON）：
{
    "操作": "买入/卖出/观望",
    "仓位": 30,
    "理由": "xxx",
    "风险提示": "xxx"
}"""

def analyze_with_ai(stock_data: dict) -> dict:
    """使用DeepSeek分析股票"""
    # 战法信息
    triggered = stock_data.get('触发战法', [])
    strategy_info = f"触发战法：{', '.join(triggered) if triggered else '无'}"
    
    prompt = f"""请分析以下股票数据并给出操作建议：

股票代码：{stock_data['代码']}
最新价：{stock_data['最新价']}
涨跌幅：{stock_data['涨跌幅']}%
MA5：{stock_data['MA5']}
MA10：{stock_data['MA10']}
MA20：{stock_data['MA20']}
MACD：{stock_data['MACD']}
RSI：{stock_data['RSI']}
成交量比（相对5日均量）：{stock_data['成交量比']}
均线多头排列：{stock_data['均线多头']}
MACD金叉：{stock_data['MACD金叉']}
{strategy_info}

请结合技术指标和触发的战法，给出分析和操作建议。"""

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3
    }
    
    try:
        response = requests.post(DEEPSEEK_API_URL, headers=headers, json=data, timeout=60)
        result = response.json()
        content = result["choices"][0]["message"]["content"]
        
        # 尝试解析JSON
        try:
            # 提取JSON部分
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            return json.loads(content.strip())
        except:
            return {"原始回复": content}
    except Exception as e:
        return {"错误": str(e)}
