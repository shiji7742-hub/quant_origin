"""配置管理"""
import os
from dotenv import load_dotenv

load_dotenv()

# DeepSeek API配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = "deepseek-reasoner"

# 股票筛选配置
MAX_STOCKS = int(os.getenv("MAX_STOCKS", 10))

# 主板股票过滤（排除创业板30开头）
MAINBOARD_PATTERN = r'^(60|00)\d{4}$'
