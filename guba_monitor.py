# -*- coding: utf-8 -*-
"""
股吧评论监控
=====================================
监控东方财富股吧评论，分析散户情绪

数据来源：东方财富股吧
指标：
1. 评论数量变化
2. 负面情绪占比
3. 情绪周期判断
"""
import requests
import re
import os
import json
from datetime import datetime, timedelta
import time

for key in list(os.environ.keys()):
    if 'proxy' in key.lower():
        del os.environ[key]

session = requests.Session()
session.trust_env = False
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://guba.eastmoney.com/',
})


def get_guba_posts(stock_code, page=1):
    """
    获取东方财富股吧帖子列表
    
    参数:
        stock_code: 股票代码（6位）
        page: 页码
    
    返回:
        list: 帖子列表
    """
    code = str(stock_code).zfill(6)
    
    # 东方财富股吧API
    url = f'https://guba.eastmoney.com/list,{code},f_{page}.html'
    
    try:
        r = session.get(url, timeout=15)
        r.encoding = 'utf-8'
        html = r.text
        
        posts = []
        
        # 简单解析帖子
        # 匹配阅读数、评论数、标题
        pattern = r'<span class="l1 a1">(\d+)</span>.*?<span class="l2 a2">(\d+)</span>.*?<span class="l3 a3">.*?title="(.*?)"'
        matches = re.findall(pattern, html, re.DOTALL)
        
        for read_count, comment_count, title in matches:
            posts.append({
                'read': int(read_count),
                'comment': int(comment_count),
                'title': title.strip(),
            })
        
        return posts
        
    except Exception as e:
        print(f"获取股吧数据失败: {e}")
        return []


def analyze_sentiment(title):
    """
    分析标题情绪
    
    返回: 'positive', 'negative', 'neutral'
    """
    # 负面关键词
    negative_words = [
        '垃圾', '坑', '骗', '亏', '跌', '绿', '完了', '崩', '割肉',
        '套', '死', '烂', '差', '坏', '骂', '黑', '假', '骗子',
        '庄家', '割韭菜', '出货', '跑路', '暴跌', '闪崩',
    ]
    
    # 正面关键词
    positive_words = [
        '涨', '红', '冲', '牛', '好', '买', '加仓', '看好',
        '突破', '起飞', '翻倍', '目标', '利好', '机会',
        '低吸', '抄底', '金坑',
    ]
    
    title_lower = title.lower()
    
    neg_count = sum(1 for w in negative_words if w in title_lower)
    pos_count = sum(1 for w in positive_words if w in title_lower)
    
    if neg_count > pos_count:
        return 'negative'
    elif pos_count > neg_count:
        return 'positive'
    else:
        return 'neutral'


def get_guba_stats(stock_code, pages=3):
    """
    获取股吧统计数据
    
    返回:
        dict: 统计数据
    """
    all_posts = []
    
    for page in range(1, pages + 1):
        posts = get_guba_posts(stock_code, page)
        all_posts.extend(posts)
        time.sleep(0.5)
    
    if not all_posts:
        return None
    
    # 统计
    total_posts = len(all_posts)
    total_reads = sum(p['read'] for p in all_posts)
    total_comments = sum(p['comment'] for p in all_posts)
    
    # 情绪分析
    sentiments = [analyze_sentiment(p['title']) for p in all_posts]
    negative_count = sentiments.count('negative')
    positive_count = sentiments.count('positive')
    
    negative_ratio = negative_count / total_posts * 100 if total_posts > 0 else 0
    positive_ratio = positive_count / total_posts * 100 if total_posts > 0 else 0
    
    # 找出点赞/阅读最多的帖子
    top_posts = sorted(all_posts, key=lambda x: x['read'], reverse=True)[:5]
    
    return {
        'total_posts': total_posts,
        'total_reads': total_reads,
        'total_comments': total_comments,
        'avg_reads': total_reads / total_posts if total_posts > 0 else 0,
        'avg_comments': total_comments / total_posts if total_posts > 0 else 0,
        'negative_ratio': negative_ratio,
        'positive_ratio': positive_ratio,
        'top_posts': top_posts,
        'all_posts': all_posts,
    }


def judge_emotion_stage(stats, history=None):
    """
    判断当前情绪阶段
    
    参数:
        stats: 当前统计数据
        history: 历史数据（可选）
    
    返回:
        dict: 情绪阶段判断
    """
    if stats is None:
        return {'stage': '未知', 'signal': '无数据'}
    
    neg_ratio = stats['negative_ratio']
    pos_ratio = stats['positive_ratio']
    
    # 基于负面比例判断
    if neg_ratio >= 70:
        stage = '极度恐慌'
        signal = '可能接近底部，但需等评论减少'
        action = '观望，等沉默底'
    elif neg_ratio >= 50:
        stage = '恐慌'
        signal = '下跌中，散户开始骂'
        action = '继续观望'
    elif neg_ratio >= 30:
        stage = '焦虑'
        signal = '有分歧，还在扛'
        action = '不操作'
    elif pos_ratio >= 60:
        stage = '乐观'
        signal = '注意风险，可能接近顶部'
        action = '考虑减仓'
    elif pos_ratio >= 40:
        stage = '偏乐观'
        signal = '正常上涨期'
        action = '持有'
    else:
        stage = '中性'
        signal = '情绪平稳'
        action = '按计划操作'
    
    # 如果有历史数据，判断变化趋势
    trend = None
    if history:
        prev_posts = history.get('total_posts', 0)
        curr_posts = stats['total_posts']
        
        if prev_posts > 0:
            change_ratio = (curr_posts - prev_posts) / prev_posts
            
            if change_ratio < -0.5 and neg_ratio > 50:
                trend = '沉默底信号！评论骤减，可能见底'
                action = '关注技术面企稳，考虑轻仓试探'
            elif change_ratio < -0.3:
                trend = '评论减少，关注度下降'
            elif change_ratio > 0.5:
                trend = '评论激增，情绪激动'
    
    return {
        'stage': stage,
        'signal': signal,
        'action': action,
        'trend': trend,
        'negative_ratio': neg_ratio,
        'positive_ratio': pos_ratio,
    }


def monitor_stock(stock_code, stock_name=None):
    """
    监控单只股票的股吧情绪
    """
    print(f"\n{'='*60}")
    print(f"股吧情绪监控: {stock_code} {stock_name or ''}")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    # 获取数据
    stats = get_guba_stats(stock_code, pages=3)
    
    if stats is None:
        print("获取数据失败")
        return None
    
    # 基础统计
    print(f"\n【基础统计】")
    print(f"  帖子数: {stats['total_posts']}")
    print(f"  总阅读: {stats['total_reads']}")
    print(f"  总评论: {stats['total_comments']}")
    print(f"  平均阅读: {stats['avg_reads']:.0f}")
    print(f"  平均评论: {stats['avg_comments']:.1f}")
    
    # 情绪统计
    print(f"\n【情绪统计】")
    print(f"  负面帖子: {stats['negative_ratio']:.1f}%")
    print(f"  正面帖子: {stats['positive_ratio']:.1f}%")
    print(f"  中性帖子: {100 - stats['negative_ratio'] - stats['positive_ratio']:.1f}%")
    
    # 情绪判断
    judgment = judge_emotion_stage(stats)
    print(f"\n【情绪判断】")
    print(f"  阶段: {judgment['stage']}")
    print(f"  信号: {judgment['signal']}")
    print(f"  建议: {judgment['action']}")
    
    # 热门帖子
    print(f"\n【热门帖子】")
    for i, post in enumerate(stats['top_posts'][:5], 1):
        sentiment = analyze_sentiment(post['title'])
        emoji = '😡' if sentiment == 'negative' else ('😊' if sentiment == 'positive' else '😐')
        title_short = post['title'][:30] + '...' if len(post['title']) > 30 else post['title']
        print(f"  {i}. {emoji} [{post['read']}阅读] {title_short}")
    
    return {
        'code': stock_code,
        'name': stock_name,
        'stats': stats,
        'judgment': judgment,
        'time': datetime.now().isoformat(),
    }


def save_history(data, filename='guba_history.json'):
    """保存历史数据"""
    history = []
    
    # 读取现有历史
    if os.path.exists(filename):
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except:
            history = []
    
    # 添加新数据
    history.append(data)
    
    # 只保留最近30条
    history = history[-30:]
    
    # 保存
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def load_history(stock_code, filename='guba_history.json'):
    """加载历史数据"""
    if not os.path.exists(filename):
        return None
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            history = json.load(f)
        
        # 找到该股票的上一条记录
        for item in reversed(history):
            if item.get('code') == stock_code:
                return item.get('stats')
        
        return None
    except:
        return None


def main():
    """主函数"""
    # 示例：监控几只股票
    stocks = [
        ('000685', '中山公用'),
        ('002456', '欧菲光'),
        ('300750', '宁德时代'),
    ]
    
    print("="*60)
    print("股吧情绪监控系统")
    print("="*60)
    print("\n数据来源: 东方财富股吧")
    print("监控指标: 帖子数量、情绪比例、热门话题")
    print("\n情绪周期理论:")
    print("  骂得凶+评论多 = 还在扛")
    print("  下杀后+评论骤减 = 底部信号")
    print("  一片叫好+评论多 = 顶部信号")
    
    for code, name in stocks:
        result = monitor_stock(code, name)
        if result:
            # 检查历史对比
            history = load_history(code)
            if history:
                judgment = judge_emotion_stage(result['stats'], history)
                if judgment.get('trend'):
                    print(f"\n  【趋势变化】{judgment['trend']}")
            
            # 保存历史
            save_history(result)
        
        time.sleep(1)
    
    print("\n" + "="*60)
    print("监控完成")
    print("="*60)


if __name__ == "__main__":
    main()
