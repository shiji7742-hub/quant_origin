# -*- coding: utf-8 -*-
"""
散户情绪策略库 V1.0
=====================================
核心理念：理解散户情绪，反向操作

这个文件会长期更新，不断积累新的情绪场景
"""

# =====================================================================
# 情绪状态定义
# =====================================================================

EMOTIONS = {
    'panic': {
        'name': '恐慌',
        'description': '极度害怕，想不计代价卖出',
        'typical_action': '割肉',
        'correct_action': '考虑买入',
    },
    'fear': {
        'name': '恐惧',
        'description': '担心继续下跌，犹豫是否卖出',
        'typical_action': '观望或小仓位割肉',
        'correct_action': '持有，观察是否企稳',
    },
    'anxiety': {
        'name': '焦虑',
        'description': '持仓亏损，坐立不安，频繁看盘',
        'typical_action': '反复纠结，随机操作',
        'correct_action': '设好止损，不要频繁看盘',
    },
    'numb': {
        'name': '麻木',
        'description': '亏太多已无感，躺平不动',
        'typical_action': '死扛',
        'correct_action': '该割的还是要割，解放资金',
    },
    'regret': {
        'name': '后悔',
        'description': '卖早了/买早了，自责',
        'typical_action': '追高买回/恐慌卖出',
        'correct_action': '接受结果，不追涨杀跌',
    },
    'fomo': {
        'name': 'FOMO(错过恐惧)',
        'description': '看到别人赚钱，着急入场',
        'typical_action': '追高买入',
        'correct_action': '等回调，不追涨',
    },
    'greed': {
        'name': '贪婪',
        'description': '赚了想赚更多，不愿止盈',
        'typical_action': '加仓或不卖',
        'correct_action': '分批止盈，落袋为安',
    },
    'euphoria': {
        'name': '狂热',
        'description': '觉得自己是股神，满仓加杠杆',
        'typical_action': '重仓单一标的',
        'correct_action': '减仓，控制风险',
    },
    'hope': {
        'name': '侥幸',
        'description': '亏了但相信会涨回来',
        'typical_action': '不止损，继续等',
        'correct_action': '执行止损纪律',
    },
    'revenge': {
        'name': '报复心理',
        'description': '亏了想立刻赚回来',
        'typical_action': '频繁交易，加大仓位',
        'correct_action': '休息一天，冷静下来',
    },
}


# =====================================================================
# 市场情景 -> 情绪映射
# =====================================================================

SCENARIOS = [
    # ================== 下跌场景 ==================
    {
        'id': 'S001',
        'name': '平开下杀',
        'market_condition': '开盘平开，然后持续下跌不反弹',
        'typical_emotion': 'anxiety',
        'emotion_process': [
            '刚开盘：还好，平开问题不大',
            '下跌1%：有点慌，要不要卖？',
            '下跌2%：纠结，再等等看',
            '下跌3%：完了，该卖了，但舍不得',
            '尾盘：算了，明天再说',
        ],
        'wrong_action': '全程纠结，错过止损时机',
        'correct_action': '开盘30分钟内如果持续下跌不反弹，立即止损',
        'lesson': '不要等，该止损就止损',
    },
    {
        'id': 'S002',
        'name': '高开低走',
        'market_condition': '开盘高开1%以上，然后一路下跌',
        'typical_emotion': 'regret',
        'emotion_process': [
            '开盘前：太好了，高开！',
            '追高买入：终于上车了',
            '开始下跌：正常回调，没事',
            '跌破开盘价：怎么回事？',
            '收盘：亏钱了，早上不该追',
        ],
        'wrong_action': '高开追买',
        'correct_action': '高开超过0.5%不追，等回调',
        'lesson': '高开不追，这是铁律',
    },
    {
        'id': 'S003',
        'name': '连续阴跌',
        'market_condition': '股票连续3-5天小幅下跌，每天跌1-2%',
        'typical_emotion': 'numb',
        'emotion_process': [
            '第1天：正常波动',
            '第2天：有点担心',
            '第3天：怎么还跌？',
            '第4天：算了，不看了',
            '第5天：已经麻木，随它去吧',
        ],
        'wrong_action': '一直扛着，期待反弹',
        'correct_action': '第3天就应该考虑减仓',
        'lesson': '阴跌比暴跌更可怕，温水煮青蛙',
    },
    {
        'id': 'S004',
        'name': '暴跌恐慌',
        'market_condition': '单日跌幅超过5%或跌停',
        'typical_emotion': 'panic',
        'emotion_process': [
            '看到暴跌：完了！',
            '看到跌停：天塌了！',
            '手抖想卖：不管了，先跑再说',
            '卖出后：心终于落地了',
            '第二天反弹：又亏在最低点...',
        ],
        'wrong_action': '恐慌时卖在最低点',
        'correct_action': '暴跌当天不操作，等第二天观察',
        'lesson': '恐慌时做的决定往往是错的',
    },
    {
        'id': 'S005',
        'name': '反弹后又跌',
        'market_condition': '下跌途中反弹1-2天，然后继续跌',
        'typical_emotion': 'hope',
        'emotion_process': [
            '反弹第1天：终于涨了！',
            '反弹第2天：果然要涨回来了',
            '又开始跌：应该只是回调',
            '继续跌：怎么又跌了？',
            '新低：完蛋，反弹是诱多',
        ],
        'wrong_action': '反弹不卖，期待更多',
        'correct_action': '反弹到关键位置（如5日线）减仓',
        'lesson': '下跌趋势中的反弹是减仓机会，不是加仓机会',
    },
    
    # ================== 上涨场景 ==================
    {
        'id': 'S101',
        'name': '踏空焦虑',
        'market_condition': '看好的股票一直涨，自己没买',
        'typical_emotion': 'fomo',
        'emotion_process': [
            '涨5%：还好没买，会回调的',
            '涨10%：怎么还涨？要不要追？',
            '涨15%：后悔了，当时应该买',
            '涨20%：不管了，追！',
            '追高后开始跌：套住了...',
        ],
        'wrong_action': '涨了很多才追买',
        'correct_action': '错过就错过，等下一个机会',
        'lesson': '踏空不亏钱，追高才亏钱',
    },
    {
        'id': 'S102',
        'name': '赚钱不走',
        'market_condition': '持仓盈利10%以上',
        'typical_emotion': 'greed',
        'emotion_process': [
            '盈利5%：再等等，还能涨',
            '盈利10%：卖了怕踏空，不卖',
            '回落到5%：等涨回10%再卖',
            '回落到0%：怎么没了？',
            '开始亏损：从盈利变亏损...',
        ],
        'wrong_action': '不止盈，利润回吐',
        'correct_action': '盈利5%减1/3，盈利10%再减1/3',
        'lesson': '会买的是徒弟，会卖的才是师傅',
    },
    {
        'id': 'S103',
        'name': '卖飞后悔',
        'market_condition': '卖出后股票继续大涨',
        'typical_emotion': 'regret',
        'emotion_process': [
            '卖出：落袋为安',
            '涨5%：还好卖了也不亏',
            '涨10%：有点后悔',
            '涨20%：太后悔了，买回来！',
            '买回后开始跌：又套住了...',
        ],
        'wrong_action': '高位追回',
        'correct_action': '接受卖飞，不追回',
        'lesson': '卖飞比套牢好一万倍',
    },
    {
        'id': 'S104',
        'name': '涨停幻想',
        'market_condition': '买的股票涨停了',
        'typical_emotion': 'euphoria',
        'emotion_process': [
            '涨停：我是股神！',
            '幻想：明天继续涨停！',
            '第二天高开：果然！',
            '高开后回落：正常回调',
            '收盘大跌：利润全没了...',
        ],
        'wrong_action': '涨停后期待更多，不减仓',
        'correct_action': '涨停次日高开5%以上减仓',
        'lesson': '涨停后的高开往往是出货机会',
    },
    
    # ================== 震荡场景 ==================
    {
        'id': 'S201',
        'name': '横盘磨人',
        'market_condition': '股票横盘震荡一个月以上',
        'typical_emotion': 'anxiety',
        'emotion_process': [
            '第1周：在整理，等突破',
            '第2周：怎么还不涨？',
            '第3周：要不要换股？',
            '第4周：受不了了，卖！',
            '卖后大涨：典型的卖飞...',
        ],
        'wrong_action': '横盘末期失去耐心卖出',
        'correct_action': '设置价格提醒，不频繁看盘',
        'lesson': '横盘是蓄势，往往突破后大涨',
    },
    {
        'id': 'S202',
        'name': '假突破陷阱',
        'market_condition': '突破压力位后快速回落',
        'typical_emotion': 'regret',
        'emotion_process': [
            '突破：终于突破了！',
            '追买：上车！',
            '回落：正常回踩',
            '跌破突破位：假突破？',
            '大跌：被骗了...',
        ],
        'wrong_action': '突破立刻追买',
        'correct_action': '等突破后回踩确认再买',
        'lesson': '真正的突破会回踩确认',
    },
    
    # ================== 特殊场景 ==================
    {
        'id': 'S301',
        'name': '周一效应',
        'market_condition': '周五涨，周一跌（或反过来）',
        'typical_emotion': 'anxiety',
        'emotion_process': [
            '周五收盘涨：周末心情好',
            '周一开盘跌：怎么回事？',
            '周一收盘：亏了',
            '周二继续跌：周末不该持股',
        ],
        'wrong_action': '周五尾盘追涨',
        'correct_action': '周五尾盘谨慎，周一早盘观望',
        'lesson': '周末持股风险大',
    },
    {
        'id': 'S302',
        'name': '尾盘诱惑',
        'market_condition': '尾盘突然拉升',
        'typical_emotion': 'fomo',
        'emotion_process': [
            '14:30前：今天一般',
            '14:45拉升：有资金进场！',
            '14:55追买：不能错过！',
            '第二天低开：被套了',
        ],
        'wrong_action': '尾盘追涨',
        'correct_action': '尾盘拉升不追，可能是诱多',
        'lesson': '尾盘拉升往往是主力诱多',
    },
    {
        'id': 'S303',
        'name': '消息刺激',
        'market_condition': '突发利好/利空消息',
        'typical_emotion': 'panic',  # 或 fomo
        'emotion_process': [
            '看到消息：这个消息很重要！',
            '立刻行动：赶紧买/卖！',
            '成交后：做了决定心里踏实',
            '后来：消息已经被消化了',
            '反思：冲动做的决定是错的',
        ],
        'wrong_action': '看到消息立刻操作',
        'correct_action': '消息出来后等30分钟再决定',
        'lesson': '消息刺激下的决定往往是错的',
    },
    {
        'id': 'S304',
        'name': '亏损加仓',
        'market_condition': '持仓亏损，想摊低成本',
        'typical_emotion': 'hope',
        'emotion_process': [
            '亏5%：加仓摊低成本',
            '继续跌：再加一点',
            '亏15%：仓位太重了',
            '亏20%：动弹不得',
            '反思：越亏越买，仓位失控',
        ],
        'wrong_action': '亏损时补仓',
        'correct_action': '只在止损位之上补仓，下跌趋势不补',
        'lesson': '下跌趋势中加仓只会加大亏损',
    },
    
    # ================== 评论区情绪指标 ==================
    {
        'id': 'S401',
        'name': '评论区情绪周期',
        'market_condition': '通过股吧评论数量和情绪判断位置',
        'typical_emotion': 'panic',
        'emotion_process': [
            '买入期：评论多，内容看好，"加油"、"冲"',
            '下跌初期：评论中等，"正常回调"、"加仓机会"',
            '继续跌：评论增多，开始骂，给负面评论点赞',
            '大跌：评论很多，骂得很凶，"垃圾股"、"庄家坑人"',
            '再下杀：评论骤减，沉默，偶尔哀叹 → 底部信号',
            '企稳：评论少，"烂股不看了" → 筹码清洗完毕',
            '开涨：评论逐渐增加，"后悔卖了" → 新周期开始',
        ],
        'wrong_action': '在骂声最大时恐慌卖出',
        'correct_action': '骂声大时观望，评论骤减+下杀后关注企稳信号',
        'lesson': '骂得凶=还在扛，沉默了=走了=底部',
    },
    {
        'id': 'S402',
        'name': '沉默底',
        'market_condition': '股价下跌+评论数骤减',
        'typical_emotion': 'numb',
        'emotion_process': [
            '前期：评论很多，骂声一片',
            '下杀：股价创新低',
            '之后：评论数明显减少（不到之前一半）',
            '解读：该割的都割了，浮筹清洗完毕',
        ],
        'wrong_action': '看到沉默以为没人关注就不关注',
        'correct_action': '沉默底是最佳买点，配合技术面企稳信号',
        'lesson': '最危险的是骂人时（对卖方），最安全的是沉默时（对买方）',
    },
    {
        'id': 'S403',
        'name': '狂热顶',
        'market_condition': '股价上涨+评论区一片叫好',
        'typical_emotion': 'euphoria',
        'emotion_process': [
            '上涨期：评论逐渐增多',
            '加速涨：评论很多，全是看好',
            '高潮：有人喊目标价，新手问能不能买',
            '见顶：大V开始推荐，媒体报道',
        ],
        'wrong_action': '在狂热时追买',
        'correct_action': '评论区一片叫好时考虑减仓',
        'lesson': '当出租车司机都在谈股票时，就该卖了',
    },
    {
        'id': 'S404',
        'name': '踏空追涨心理演变',
        'market_condition': '股票持续上涨，自己一直没买',
        'typical_emotion': 'fomo',
        'emotion_process': [
            '刚开始涨：太高了，等回调再买',
            '继续涨5%：还是等，肯定会调的',
            '又涨10%：后悔没买，但觉得虚高不敢追',
            '涨15%+媒体报道：好像真的要涨，要不要买？',
            '涨20%+朋友赚钱：他们都赚到了，我也要上',
            '终于追了：上车了！',
            '然后开始跌：套住了...',
        ],
        'wrong_action': '在媒体唱多、朋友都在讨论时追买',
        'correct_action': '错过就错过，产生"忍不住想追"的冲动时反而要警惕',
        'lesson': '当你从"不敢买"变成"必须买"时，往往就是顶部',
    },
    {
        'id': 'S405',
        'name': '追涨信号等级',
        'market_condition': '判断是否接近顶部的散户行为信号',
        'typical_emotion': 'euphoria',
        'emotion_process': [
            '自己犹豫观望：弱信号（还没到顶）',
            '财经媒体报道：中信号（接近顶部）',
            '朋友开始讨论赚钱：强信号（顶部区域）',
            '不炒股的人问能不能买：极强信号（已见顶）',
            '自己终于忍不住追了：你就是最后一批',
        ],
        'wrong_action': '看到别人赚钱就追',
        'correct_action': '用"周围人关注度"判断位置，关注度越高越危险',
        'lesson': '散户追涨的信号 = 顶部信号',
    },
    {
        'id': 'S406',
        'name': '自我情绪反向指标',
        'market_condition': '用自己的情绪判断买卖点',
        'typical_emotion': 'fomo',
        'emotion_process': [
            '当你觉得"太高了不敢买"：可能还能涨',
            '当你觉得"忍不住必须买"：大概率是顶',
            '当你觉得"不想看了随它去"：可能是底',
            '当你觉得"必须割肉"：可能不该割',
        ],
        'wrong_action': '跟着自己的情绪操作',
        'correct_action': '把自己的强烈情绪当作反向指标',
        'lesson': '当情绪最强烈时，往往是最不应该行动的时候',
    },
    {
        'id': 'S407',
        'name': '做T踏空陷阱',
        'market_condition': '持有好股但被反复震荡磨人，想做T结果踏空',
        'typical_emotion': 'regret',
        'emotion_process': [
            '持有好股：知道它应该会涨，逻辑没问题',
            '反复震荡：拉高回落，拉高回落，太磨人了',
            '看到别的涨：大盘涨/别的板块涨/短线情绪好，就我这个不动',
            '手痒出货：高点出去，想做个T',
            '确实回落：果然回调了，我判断对了！',
            '等更低：既然出了，就做个大T，等更低接回',
            '继续等：还没到我的目标价，再等等',
            '突然爆发：卧槽怎么涨了？！',
            '踏空：再也追不回来了...',
        ],
        'wrong_action': '因为磨人就卖出好股，想做T结果踏空',
        'correct_action': '好股拿住不动，不要因为短期磨人就放弃',
        'lesson': '做T的成功率很低，往往卖飞才是结局',
    },
    {
        'id': 'S408',
        'name': '外面的更香陷阱',
        'market_condition': '持仓不涨，别的在涨',
        'typical_emotion': 'anxiety',
        'emotion_process': [
            '持仓：没怎么动，横盘或小跌',
            '看别的：大盘涨/热点板块涨/朋友的票涨',
            '心态：我这个怎么不涨？要不要换？',
            '换股：卖了追热点',
            '结果1：追的高位套住',
            '结果2：卖的开始涨了',
            '心态崩：两边都没吃到',
        ],
        'wrong_action': '因为别的涨就换股追热点',
        'correct_action': '坚守自己的逻辑，不被短期热点带偏',
        'lesson': '外面的机会永远有，但追来追去往往两边都错过',
    },
    {
        'id': 'S409',
        'name': '做T自信陷阱',
        'market_condition': '卖出后确实回调了，觉得自己判断对',
        'typical_emotion': 'greed',
        'emotion_process': [
            '卖出：觉得会回调',
            '确实回调：我判断对了！',
            '自信增强：我能判断高低点',
            '等更低：既然能判断，就等最低点接',
            '继续等：还没到呢，再等等',
            '突然拉升：怎么回事？',
            '踏空：完了，接不回来了',
        ],
        'wrong_action': '因为一次判断对就觉得能做T',
        'correct_action': '即使回调了，也按计划接回，不要贪更低',
        'lesson': '"确实回调了"是让你踏空的陷阱，会诱惑你等更低',
    },
    {
        'id': 'S410',
        'name': '突然爆发',
        'market_condition': '横盘震荡后突然放量大涨',
        'typical_emotion': 'regret',
        'emotion_process': [
            '之前：长期横盘，磨人，很多人受不了卖了',
            '突然：放量突破，一根大阳线',
            '持仓的：终于涨了！但仓位不够',
            '卖了的：卧槽！踏空了！',
            '场外的：要不要追？',
            '追的：往往追在高点',
        ],
        'wrong_action': '横盘磨人时卖出，爆发后追高',
        'correct_action': '横盘时拿住，爆发后第一时间不追，等回踩',
        'lesson': '横盘是蓄势，越磨人越要拿住',
    },
    
    # ================== 主力行为识别 ==================
    {
        'id': 'S501A',
        'name': '尾盘对敲洗盘（积极信号）',
        'market_condition': '尾盘大单频繁+高换手率+下跌收盘',
        'typical_emotion': 'panic',
        'emotion_process': [
            '看到尾盘放量：主力在干什么？',
            '看到下跌：完了，要出货了？',
            '散户恐慌：赶紧跑！',
            '实际情况：主力对敲洗盘，清洗浮筹',
            '后续：洗完后拉升',
        ],
        'judgment_criteria': [
            '1. 量能刚放出来（不是放量尾声）',
            '2. 有强题材支撑（如AI应用）',
            '3. 基本面有拐点（如扭亏为盈）',
            '4. 技术面处于冲击高点阶段',
            '5. 换手率高但价格波动不大（对敲特征）',
        ],
        'wrong_action': '看到下跌+高换手就恐慌卖出',
        'correct_action': '综合分析题材+基本面+量价，判断是洗盘还是出货',
        'lesson': '对敲+下跌不一定是出货，放量初期+强题材+业绩拐点=洗盘拿住',
    },
    {
        'id': 'S502A',
        'name': '放量初期 vs 放量末期',
        'market_condition': '高换手率',
        'typical_emotion': 'anxiety',
        'emotion_process': [
            '放量初期：筹码刚开始换手，主力建仓',
            '放量中期：拉升+震荡洗盘交替',
            '放量末期：高位放量滞涨，出货信号',
        ],
        'judgment_criteria': [
            '初期特征：前期缩量横盘，突然放量，价格刚启动',
            '末期特征：连续放量多日，价格冲高回落，量价背离',
        ],
        'wrong_action': '不区分放量阶段，一律看空或一律看多',
        'correct_action': '判断放量位置：初期可持有，末期要减仓',
        'lesson': '放量位置决定含义，低位放量是机会，高位放量是风险',
    },
    {
        'id': 'S503A',
        'name': '主力对敲识别',
        'market_condition': '成交活跃但价格波动小',
        'typical_emotion': 'fomo',
        'emotion_process': [
            '表象：成交量大，买卖活跃',
            '实质：自买自卖，左手倒右手',
            '目的：制造成交量吸引眼球 / 洗盘 / 拉高出货',
        ],
        'judgment_criteria': [
            '对敲特征：',
            '1. 大单买卖金额接近',
            '2. 价格窄幅波动但量很大',
            '3. 盘口买卖挂单对称',
            '4. 尾盘大单密集',
        ],
        'context_matters': {
            '低位对敲+洗盘': '吸筹完毕，清洗浮筹，准备拉升',
            '拉升中对敲': '边拉边洗，控制节奏',
            '高位对敲+滞涨': '出货，赶紧跑',
        },
        'wrong_action': '看到对敲就恐慌',
        'correct_action': '结合位置判断对敲目的',
        'lesson': '对敲本身是中性的，位置决定含义',
    },
    
    # ================== 仓位管理陷阱 ==================
    {
        'id': 'S501',
        'name': '连涨All-in陷阱',
        'market_condition': '股票或持仓连续上涨3-5天',
        'typical_emotion': 'greed',
        'emotion_process': [
            '第1天涨：不错，涨了',
            '第2天涨：果然看对了',
            '第3天涨：这票太牛了，为什么当初不多买点？',
            '第4天涨：后悔仓位太轻，要不要加仓？',
            '第5天涨：忍不住了，All-in！把其他票都卖了来加仓',
            '第6天开始跌：完了，满仓套在最高点...',
        ],
        'wrong_action': '连涨后All-in加仓',
        'correct_action': '连涨后应该减仓而不是加仓，越涨越卖',
        'lesson': '连涨=风险积累，不是加仓信号；满仓往往套在最高点',
    },
    {
        'id': 'S502',
        'name': '赚钱后过度自信',
        'market_condition': '最近几笔交易都赚钱了',
        'typical_emotion': 'euphoria',
        'emotion_process': [
            '第1笔赚钱：运气不错',
            '第2笔赚钱：我有点厉害',
            '第3笔赚钱：我是不是有天赋？',
            '连续赚：我悟了！我能预测市场！',
            '加大仓位：既然这么准，干脆重仓一把',
            '突然亏大：一把亏掉前面赚的好几倍...',
        ],
        'wrong_action': '连续盈利后加大仓位',
        'correct_action': '连续盈利后更要保守，提取部分利润',
        'lesson': '连续盈利往往是大亏的前兆，市场会惩罚过度自信',
    },
    {
        'id': 'S503',
        'name': '回本仓位陷阱',
        'market_condition': '亏损后想快速回本',
        'typical_emotion': 'revenge',
        'emotion_process': [
            '亏损10%：得快点赚回来',
            '想法：如果重仓一把涨5%就能回本',
            '重仓买入：这次一定行',
            '又亏：更亏了，现在要涨更多才能回本',
            '继续加仓：不能认输，再搏一把',
            '结果：越亏越多，仓位越来越重',
        ],
        'wrong_action': '亏损后加仓想回本',
        'correct_action': '亏损后减仓，降低风险敞口',
        'lesson': '回本心态是最危险的，往往导致亏损扩大',
    },
    {
        'id': 'S504',
        'name': '分散变集中',
        'market_condition': '分散持仓，但某只涨得好',
        'typical_emotion': 'fomo',
        'emotion_process': [
            '初始：分散持有5只股票',
            'A涨B跌：A果然好，B真差',
            '卖B买A：把差的换成好的',
            'A继续涨：对了！再换点',
            '逐渐集中：从5只变成重仓1只',
            'A开始跌：全部亏损，无处可逃',
        ],
        'wrong_action': '把涨的加仓、跌的卖掉，导致仓位过于集中',
        'correct_action': '定期再平衡，涨多了减仓，跌多了考虑补仓',
        'lesson': '不要把所有鸡蛋放一个篮子，分散是为了活下去',
    },
    {
        'id': 'S505',
        'name': '牛市满仓幻觉',
        'market_condition': '大盘连续上涨，身边都在赚钱',
        'typical_emotion': 'euphoria',
        'emotion_process': [
            '大盘涨：行情来了',
            '周围人赚钱：别人都赚了，我仓位太轻',
            '加仓：把现金都买进去',
            '继续涨：后悔没满仓，借钱也要买',
            '满仓+杠杆：这次一定是大牛市',
            '大盘回调：爆仓了...',
        ],
        'wrong_action': '牛市氛围中满仓甚至加杠杆',
        'correct_action': '越热闹越要保留现金，留有余地',
        'lesson': '满仓是最危险的状态，永远不要All-in',
    },
    {
        'id': 'S506',
        'name': '底部轻仓陷阱',
        'market_condition': '大盘连续下跌，恐慌氛围',
        'typical_emotion': 'panic',
        'emotion_process': [
            '跌10%：先卖一点避险',
            '跌20%：再卖一点，太可怕了',
            '跌30%：清仓！不玩了',
            '企稳：不敢买，可能还会跌',
            '反弹10%：果然是诱多，不买',
            '反弹30%：踏空了...当初为什么清仓',
        ],
        'wrong_action': '下跌中越跌越卖，底部清仓',
        'correct_action': '下跌中分批买入，越跌越买（前提是好公司）',
        'lesson': '恐慌清仓往往是最差时机，应该反着来',
    },
]


# ================== 抄底陷阱 ==================
BOTTOM_FISHING_TRAPS = [
    {
        'id': 'B001',
        'name': '大跌抄底冲动',
        'market_condition': '股票单日大跌5%以上',
        'typical_emotion': 'greed',
        'emotion_process': [
            '看到大跌：哇，跌这么多！',
            '心理活动：这是机会，便宜了',
            '查历史：之前高点比现在高多少',
            '计算：如果涨回去能赚多少',
            '冲动买入：抄底！',
            '继续跌：怎么还跌？',
            '深套：抄在半山腰...',
        ],
        'wrong_action': '看到大跌就想抄底',
        'correct_action': '大跌当天不操作，等止跌企稳再考虑',
        'lesson': '大跌只是开始，抄底容易抄在半山腰',
    },
    {
        'id': 'B002',
        'name': '连续下跌接飞刀',
        'market_condition': '股票连续3-5天下跌',
        'typical_emotion': 'greed',
        'emotion_process': [
            '跌第1天：正常调整',
            '跌第2天：跌得够多了吧',
            '跌第3天：太便宜了，可以买了',
            '买入抄底：这个价格很划算',
            '跌第4天：再补一点摊成本',
            '跌第5天：完了，越补越亏',
            '继续跌：深套，动弹不得',
        ],
        'wrong_action': '连跌时抄底补仓',
        'correct_action': '永远不接飞刀，等刀落地再捡',
        'lesson': '连跌说明有问题，不要急着抄底',
    },
    {
        'id': 'B003',
        'name': '腰斩抄底',
        'market_condition': '股票从高点跌了50%',
        'typical_emotion': 'greed',
        'emotion_process': [
            '看到腰斩：跌了一半了，够低了吧',
            '计算：涨回去就是翻倍！',
            '心理：风险收益比太好了',
            '买入：这个价格肯定安全',
            '继续跌：腰斩后再腰斩...',
            '亏70%：当初以为是底',
        ],
        'wrong_action': '因为跌了很多就认为便宜',
        'correct_action': '跌多少不重要，趋势才重要',
        'lesson': '腰斩可以再腰斩，没有所谓的底',
    },
    {
        'id': 'B004',
        'name': '均线抄底',
        'market_condition': '跌到某个均线（如20日、60日）',
        'typical_emotion': 'hope',
        'emotion_process': [
            '看到跌到均线：到支撑位了',
            '心理：均线应该有支撑',
            '买入：在均线抄底',
            '跌破均线：支撑失效',
            '继续跌：一路向下',
        ],
        'wrong_action': '机械地在均线抄底',
        'correct_action': '均线只是参考，要结合量能和趋势',
        'lesson': '下跌趋势中，均线会被反复跌破',
    },
    {
        'id': 'B005',
        'name': '越跌越买陷阱',
        'market_condition': '持仓下跌中',
        'typical_emotion': 'hope',
        'emotion_process': [
            '第一次跌：正常波动',
            '第二次跌：补一点摊成本',
            '第三次跌：再补一点',
            '第N次跌：仓位越来越重',
            '反弹一点：解套了一点',
            '又跌：仓位太重，止损不了',
        ],
        'wrong_action': '下跌中越买越多',
        'correct_action': '只在上涨趋势中加仓',
        'lesson': '越跌越买=越套越深',
    },
    {
        'id': 'B006',
        'name': '抄底正确姿势',
        'market_condition': '想抄底时',
        'typical_emotion': 'calm',
        'emotion_process': [
            '第一步：等止跌（连续2-3天不创新低）',
            '第二步：等企稳（缩量横盘）',
            '第三步：等信号（放量阳线）',
            '第四步：小仓位试探（10-20%仓位）',
            '第五步：确认有效后加仓',
        ],
        'wrong_action': '看到跌就买',
        'correct_action': '等止跌→企稳→信号→分批买',
        'lesson': '宁可买贵一点，不要买在下跌途中',
    },
]


# ================== 交易频率陷阱 ==================
TRADING_FREQUENCY_TRAPS = [
    {
        'id': 'T001',
        'name': '管不住手综合征',
        'market_condition': '每天都想操作',
        'typical_emotion': 'anxiety',
        'emotion_process': [
            '早盘：看看今天有什么机会',
            '看到涨的：这个不错，要不要买点？',
            '买入：上车了，心里踏实',
            '震荡：要不要先出来？',
            '卖出：先落袋为安',
            '又涨了：靠，卖早了，再买回来',
            '循环往复：一天操作好几次',
        ],
        'wrong_action': '每天频繁交易',
        'correct_action': '制定计划，不到条件不操作',
        'lesson': '高手三年不出手，出手吃三年；散户天天操作，天天亏手续费',
    },
    {
        'id': 'T002',
        'name': '手痒症',
        'market_condition': '空仓或轻仓时',
        'typical_emotion': 'fomo',
        'emotion_process': [
            '空仓中：好无聊',
            '看到涨的：别人都在赚钱',
            '手痒：随便买点吧',
            '随便买入：总比空着好',
            '结果亏了：不该手痒',
        ],
        'wrong_action': '因为手痒而随便买入',
        'correct_action': '没有机会就空仓等待',
        'lesson': '空仓也是一种仓位，等待也是一种操作',
    },
    {
        'id': 'T003',
        'name': '做T上瘾',
        'market_condition': '持有股票时',
        'typical_emotion': 'greed',
        'emotion_process': [
            '持股：每天都想做个T',
            '高点卖：先出来',
            '等低点：准备接回',
            '没接到：涨了，踏空了',
            '追回来：成本更高了',
            '又想做T：弥补损失',
            '恶性循环：越做越亏',
        ],
        'wrong_action': '每天做T',
        'correct_action': '好股票拿着不动，不做T',
        'lesson': '做T的胜率很低，手续费+滑点会吃掉利润',
    },
    {
        'id': 'T004',
        'name': '看盘强迫症',
        'market_condition': '持仓时',
        'typical_emotion': 'anxiety',
        'emotion_process': [
            '开盘：看一眼',
            '10分钟后：再看一眼',
            '涨了：开心，继续看',
            '跌了：焦虑，更频繁看',
            '一天看几十次：什么都没干',
            '冲动操作：看多了容易手痒',
        ],
        'wrong_action': '频繁看盘',
        'correct_action': '设置提醒，每天最多看2-3次',
        'lesson': '看盘次数和收益成反比',
    },
    {
        'id': 'T005',
        'name': '换股频繁',
        'market_condition': '持仓不涨，别的涨',
        'typical_emotion': 'fomo',
        'emotion_process': [
            '持仓：横盘不动',
            '看别的涨：眼红',
            '换股：卖了买别的',
            '刚换的跌：刚才那个开始涨了',
            '再换回去：两边都没吃到',
            '频繁换股：手续费+踏空双重损失',
        ],
        'wrong_action': '频繁换股追热点',
        'correct_action': '持股守息，不随便换',
        'lesson': '频繁换股的成本远比想象的高',
    },
    {
        'id': 'T006',
        'name': '高手心态',
        'market_condition': '任何时候',
        'typical_emotion': 'calm',
        'emotion_process': [
            '大部分时间：观察，等待',
            '没机会时：空仓，学习，复盘',
            '机会来了：果断出手，重仓',
            '持有期间：不看盘，该干嘛干嘛',
            '目标到了：止盈离场',
            '然后：继续等待下一个机会',
        ],
        'wrong_action': '天天操作',
        'correct_action': '三年不出手，出手吃三年',
        'lesson': '耐心是交易中最稀缺的品质',
    },
]


# ================== 仓位管理原则 ==================
POSITION_RULES = {
    'rule_1': {
        'name': '连涨减仓原则',
        'condition': '持仓连涨3天以上',
        'action': '减仓1/3',
        'reason': '连涨积累风险，落袋为安',
    },
    'rule_2': {
        'name': '连跌不加原则',
        'condition': '持仓连跌且亏损超过5%',
        'action': '不加仓，考虑止损',
        'reason': '下跌趋势中加仓会扩大亏损',
    },
    'rule_3': {
        'name': '单只上限原则',
        'condition': '任何时候',
        'action': '单只股票仓位不超过30%',
        'reason': '避免集中风险',
    },
    'rule_4': {
        'name': '盈利减仓原则',
        'condition': '单只盈利超过20%',
        'action': '至少减仓1/2',
        'reason': '利润要落袋',
    },
    'rule_5': {
        'name': '现金底线原则',
        'condition': '任何时候',
        'action': '保留至少20%现金',
        'reason': '留有加仓余地',
    },
}


# =====================================================================
# 情绪识别函数
# =====================================================================

def identify_emotion(market_data):
    """
    根据市场数据识别当前可能的散户情绪
    
    参数:
        market_data: dict，包含
            - today_change: 今日涨跌幅
            - open_change: 开盘涨跌幅
            - position: 收盘位置(0-100)
            - trend_5d: 5日趋势（'up', 'down', 'flat'）
            - holding_pnl: 持仓盈亏比例
    
    返回:
        list of dict: 可能的情绪和场景
    """
    emotions = []
    
    today_change = market_data.get('today_change', 0)
    open_change = market_data.get('open_change', 0)
    position = market_data.get('position', 50)
    holding_pnl = market_data.get('holding_pnl', 0)
    
    # 平开下杀
    if abs(open_change) < 0.3 and today_change < -1:
        emotions.append({
            'scenario': 'S001',
            'emotion': 'anxiety',
            'intensity': min(abs(today_change) / 3 * 100, 100),
        })
    
    # 高开低走
    if open_change > 0.5 and today_change < open_change - 1:
        emotions.append({
            'scenario': 'S002',
            'emotion': 'regret',
            'intensity': min((open_change - today_change) / 2 * 100, 100),
        })
    
    # 暴跌恐慌
    if today_change < -5:
        emotions.append({
            'scenario': 'S004',
            'emotion': 'panic',
            'intensity': min(abs(today_change) / 10 * 100, 100),
        })
    
    # 持仓亏损
    if holding_pnl < -5:
        emotions.append({
            'scenario': 'S304',
            'emotion': 'hope',
            'intensity': min(abs(holding_pnl) / 20 * 100, 100),
        })
    
    # 持仓盈利
    if holding_pnl > 5:
        emotions.append({
            'scenario': 'S102',
            'emotion': 'greed',
            'intensity': min(holding_pnl / 20 * 100, 100),
        })
    
    return emotions


def get_advice(scenario_id):
    """获取特定场景的建议"""
    for s in SCENARIOS:
        if s['id'] == scenario_id:
            return {
                'name': s['name'],
                'wrong_action': s['wrong_action'],
                'correct_action': s['correct_action'],
                'lesson': s['lesson'],
            }
    return None


def print_all_scenarios():
    """打印所有场景"""
    print("=" * 70)
    print("散户情绪场景库")
    print("=" * 70)
    
    for s in SCENARIOS:
        print(f"\n【{s['id']}】{s['name']}")
        print(f"  市场条件: {s['market_condition']}")
        print(f"  典型情绪: {EMOTIONS[s['typical_emotion']]['name']}")
        print(f"  错误做法: {s['wrong_action']}")
        print(f"  正确做法: {s['correct_action']}")
        print(f"  教训: {s['lesson']}")


def get_todays_emotion_check():
    """今日情绪自检"""
    questions = [
        {
            'question': '今天看盘次数',
            'options': ['1-2次', '3-5次', '5-10次', '10次以上'],
            'emotion_map': ['calm', 'normal', 'anxiety', 'panic'],
        },
        {
            'question': '看到下跌时的反应',
            'options': ['没感觉', '有点担心', '很焦虑', '想立刻卖'],
            'emotion_map': ['calm', 'fear', 'anxiety', 'panic'],
        },
        {
            'question': '看到别人赚钱时',
            'options': ['无所谓', '有点羡慕', '很后悔没买', '想追进去'],
            'emotion_map': ['calm', 'regret', 'fomo', 'fomo'],
        },
        {
            'question': '对持仓的态度',
            'options': ['理性持有', '想加仓', '想减仓', '想全卖'],
            'emotion_map': ['calm', 'greed', 'fear', 'panic'],
        },
    ]
    return questions


# =====================================================================
# 情绪日记
# =====================================================================

def create_emotion_diary_template():
    """创建情绪日记模板"""
    template = """
# 交易情绪日记
日期: ____年__月__日

## 今日市场
- 大盘涨跌: ___%
- 持仓涨跌: ___%
- 当前盈亏: ___%

## 情绪自检
- 看盘次数: ___次
- 焦虑程度: 1-10分 ___分
- 是否想冲动操作: 是/否

## 今日操作
- 买入: 
- 卖出:
- 操作原因:

## 情绪分析
- 操作时的情绪: 
- 是否按计划执行: 是/否
- 如果违反计划，原因是:

## 反思
- 今天做对了什么:
- 今天做错了什么:
- 下次遇到类似情况应该:

## 明日计划
- 关注:
- 计划操作:
- 止损位:
- 止盈位:
"""
    return template


if __name__ == "__main__":
    print_all_scenarios()
