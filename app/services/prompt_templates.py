# 新变量名：ASSISTANT_SYSTEM_PROMPT，用于替换内部所有 "coach" 命名
ASSISTANT_SYSTEM_PROMPT = """
你是一名严格但鼓励式的复习助手。你只能依据给定知识源进行提问和纠错。
输出应短句、可执行、便于学生立刻修改答案。
""".strip()

# 兼容旧名，短期内保留以避免大面积改动引发运行时错误。
COACH_SYSTEM_PROMPT = ASSISTANT_SYSTEM_PROMPT

FLASHCARD_PROMPT = """
请根据课程资料生成最多 {count} 张知识卡片。严格只输出 JSON，格式如下：
{{"cards":[{{"concept":"概念","explanation":"一句话解释（优先基于证据）","example":"一个简短例子，若无则空字符串"}}]}}

要求：
1) 返回的输出必须是可解析的 JSON，不要输出任何额外的文字。
2) 输出语言规则：默认使用中文输出（术语可保留英文原名）。
3) 每个 concept 要简短（2-6 字或词组），便于记忆与考查。
4) explanation 必须优先基于课程资料中的句子或段落，尽量不引入外部信息或推断。
5) example 可为空；若给出，应贴合资料中的场景。
6) 避免使用泛化占位符（如“核心概念”），优先输出具体术语。

示例（仅示范结构，不作为唯一答案）：
{{"cards":[{{"concept":"边际效应递减","explanation":"在其他条件不变时，连续增加某一投入，其边际产出最终会下降。","example":"例如连续施肥下，单位产量增长率下降。"}}]}}

课程资料:
{material}
""".strip()

TERM_EXTRACTION_PROMPT = """
从以下课程资料提取最关键术语。要求：
1) 优先选择可被考查、可解释、可举例的概念。
2) 输出 JSON: {{"terms": ["术语1", "术语2", ...]}}。
3) 术语去重，最多 {count} 个。
课程资料:
{material}
""".strip()

QUESTION_PROMPT = """
根据课程资料生成1个引导性问题，不要直接给答案。
- 输出语言: {language}
- 学生水平: {level}
- 核心概念: {concept}
- 证据片段: {evidence}
要求：
1) 只输出1个问题，必须以问号结尾。
2) 问题要具体，围绕定义、条件、机制、比较、应用或例子中的一个点发问。
3) 不要使用“请解释该概念”“请说明一下”这类空泛问法，不要直接复述证据。
4) 难度要匹配学生水平：初级问定义，中级问条件/机制，高级问边界/应用/比较。
5) 默认使用中文输出问题；若术语是英文，可在中文句子中保留英文术语。
只输出问题文本，不要额外说明。
""".strip()

EVALUATION_PROMPT = """
请评估学生答案与知识源的一致性，输出 JSON。
字段:
- score: 0-100
- feedback: 一句话指出主要问题
- correction: 给出更准确答案（不超过120字）
- missing_points: 关键遗漏点列表
 - basis_points: 用于评分的关键依据点列表
输入:
概念: {concept}
问题: {question}
学生答案: {answer}
知识源证据: {evidence}
评分依据点: {basis_points}
""".strip()
