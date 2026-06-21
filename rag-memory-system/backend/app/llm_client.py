import os
import json
import re
from openai import AsyncOpenAI


def extract_json_from_markdown(text: str) -> dict:
    """
    工业级 JSON 剥离器：无视模型前后胡说八道，精准抠出 JSON。
    """
    try:
        match = re.search(r"```(?:json)?(.*?)```", text, re.DOTALL)
        if match:
            json_str = match.group(1).strip()
        else:
            json_str = text.strip()
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        print(f"[JSON Parse Error] 无法解析大模型输出: {text[:100]}...")
        return {}


def _translate_llm_error(e: Exception) -> str:
    msg = str(e)
    if "401" in msg or "Unauthorized" in msg or "auth" in msg.lower() or "API key" in msg or "api_key" in msg:
        return "API Key 无效或未设置，请在设置中检查 API Key"
    if "insufficient_quota" in msg or "quota" in msg.lower() or "429" in msg:
        return "API 额度不足（429），请检查账户余额"
    if "timeout" in msg.lower() or "timed out" in msg.lower():
        return "请求超时，请检查网络连接或代理设置"
    if "connection" in msg.lower() or "refused" in msg.lower() or "resolve" in msg.lower():
        return "无法连接到 API 服务器，请检查基础地址或网络"
    if "model" in msg.lower() and "not found" in msg.lower():
        return "模型不存在或无权访问，请检查模型名称"
    return f"LLM 调用异常: {msg}"


def get_dynamic_client(api_key: str = None, base_url: str = None):
    return AsyncOpenAI(
        api_key=api_key or os.getenv("LLM_API_KEY", "sk-your-key"),
        base_url=base_url or os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
    )


def get_dynamic_model(model_name: str = None):
    return model_name or os.getenv("LLM_MODEL", "deepseek-chat")


async def stream_generate(system_prompt: str, api_key: str = None, base_url: str = None, model_name: str = None):
    # 🚨 探针：如果终端看不到这行，说明代码没被重新加载！
    print(">>> [探针] stream_generate 已加载新代码，无 async with")
    client = get_dynamic_client(api_key, base_url)
    model = get_dynamic_model(model_name)
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "请根据上述设定开始创作"}
        ],
        stream=True,
        temperature=0.85
    )
    async for chunk in response:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


async def extract_new_facts(text: str, api_key: str = None, base_url: str = None, model_name: str = None) -> list:
    extraction_prompt = """
语言：中文。你必须使用中文回答。所有输出内容必须为中文。

你是一位顶级的游戏"世界书（Lorebook）"架构师。请从最新章节正文中，提取并编撰世界书词条。

【世界书编撰法则】：
1. "entry_name"（词条）：严谨的专有名词（如角色名、地名、功法名），1-8字。
2. "triggers"（触发关键词）：全词匹配，包含别名、外号、简称。禁用通用虚词。
3. "type"（类型）：人物、地点、道具、事件、组织、能力、次要设定。
4. "relations"（关联词条）：与该词条强相关的其他专有名词列表。
5. "content"（世界书内容）：不要只写一句话！请用 50-200 字的精炼文本，写出它的人物性格、外貌特征、核心动机、或地点的历史背景。

【强制输出规范】：
必须输出包含 "entities" 键的 JSON：
```json
{
  "entities": [
    {
      "entry_name": "林晚晴",
      "triggers": ["晚晴", "新娘", "林家大小姐"],
      "type": "人物",
      "relations": ["林建国", "陆夏川"],
      "content": "林建国的女儿，与陆夏川结婚。外表身穿白色婚纱，性格隐忍且内心藏着复仇的决心。在婚礼之夜将带有N字母的项链扔进垃圾桶，标志着她斩断过去的决绝。"
    }
  ]
}
```
"""
    client = get_dynamic_client(api_key, base_url)
    model = get_dynamic_model(model_name)
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": extraction_prompt},
                {"role": "user", "content": f"请抽取以下文本中的剧情事实：\n\n{text}"}
            ],
            temperature=0.3
        )
        raw = response.choices[0].message.content.strip()
        data = extract_json_from_markdown(raw)

        # 💡 健壮解析：兼容两种输出格式
        if isinstance(data, list):
            # 模型直接输出数组（旧格式兼容）
            return data
        elif isinstance(data, dict):
            # 模型输出 {"entities": [...]} 包裹格式（新格式）
            entities = data.get("entities", [])
            if isinstance(entities, list):
                return entities
            print(f"[实体提取] 警告：entities 字段不是数组，实际类型: {type(entities)}")
            return []
        else:
            print(f"[实体提取] 警告：无法识别的返回类型: {type(data)}，原始内容前100字符: {raw[:100]}")
            return []
    except Exception as e:
        print(f"[实体提取失败] 发生了不可预知的错误: {e}")
        return []


async def compact_old_facts(entity_name: str, entity_type: str, facts_list: list, api_key: str = None, base_url: str = None, model_name: str = None) -> list:
    prompt = f"""
语言：中文。你必须使用中文回答。所有输出内容必须为中文。

你是一位顶级的世界书（Lorebook）档案管理员。
你要整理【实体：{entity_name}（{entity_type}）】在过往多个章节中积累的零散情报，将它们炼化为一份最新的、完整的、结构化的【世界书词条】。

【炼化法则】：
1. 绝不遗漏：必须包含所有重要的历史事件（如从"被甩"到"断腿"再到"觉醒"的过程）。
2. 结构清晰：请将内容组织成具有可读性的段落。
3. 状态更新：如果人物的身份、立场发生了反转，请以【最新状态】为基调，将旧身份作为【背景经历】描述。

原始事实：
{json.dumps(facts_list, ensure_ascii=False, indent=2)}

【格式示范】：
张三，原为普通上班族（悦米的男友）。在第3章被女友抛弃后流落街头，随后在小巷被恶霸打断双腿。这一致命打击使他意外触碰"黑皮盒子"并觉醒异能。目前他对过去充满仇恨，性格变得冷酷偏激，正在暗中积蓄力量。

【强制输出规范】：
1. 必须使用中文回答！必须使用中文回答！
2. 请严格输出以下 JSON 结构，【不要】输出任何多余的解释、问候或 Markdown 之外的文字。
3. 必须使用 ```json 包裹。

```json
["炼化后的完整传记文本"]
```
"""
    client = get_dynamic_client(api_key, base_url)
    model = get_dynamic_model(model_name)
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个专业的事实压缩器。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        raw = response.choices[0].message.content.strip()
        data = extract_json_from_markdown(raw)
        if isinstance(data, list):
            return data
        return facts_list
    except Exception as e:
        print(f"事实压缩失败: {e}")
        return facts_list


async def suggest_plot_directions(recent_context: str, api_key: str = None, base_url: str = None, model_name: str = None) -> list:
    prompt = f"""
语言：中文。你必须使用中文回答。所有输出内容必须为中文。

你是一个网文/游戏剧情推进顾问。请根据以下最近的剧情上下文，提供 3 个可能的剧情发展方向。

【要求】：
1. 每个方向必须包含：方向标题、一句话描述、核心冲突或看点
2. 方向之间必须有明显差异
3. 输出 JSON 数组

最近的剧情上下文：
{recent_context}

【强制输出规范】：
1. 必须使用中文回答！必须使用中文回答！
2. 请严格输出以下 JSON 结构，【不要】输出任何多余的解释、问候或 Markdown 之外的文字。
3. 必须使用 ```json 包裹。

```json
[
  {{
    "title": "方向标题",
    "desc": "一句话描述",
    "conflict": "核心冲突或看点"
  }}
]
```
"""
    client = get_dynamic_client(api_key, base_url)
    model = get_dynamic_model(model_name)
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个专业的剧情推进顾问。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.8
        )
        raw = response.choices[0].message.content.strip()
        data = extract_json_from_markdown(raw)
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        print(f"剧情方向建议失败: {e}")
        return []


async def generate_pitches_from_llm(seed_text: str, is_variant: bool, target_pitch: dict, api_key: str = None, base_url: str = None, model_name: str = None) -> list:
    """第一阶段：灵感接收与差异化裂变"""
    client = get_dynamic_client(api_key, base_url)
    model = get_dynamic_model(model_name)

    context_instruction = f"用户输入的初始灵感为：{seed_text}"
    if is_variant and target_pitch:
        context_instruction = f"用户希望基于以下特定方向进行微调或重做：\n原方向：{target_pitch.get('title')} - {target_pitch.get('summary')}\n用户的修改建议/新灵感为：{seed_text}"

    system_prompt = """
语言：中文。你必须使用中文回答。所有输出内容必须为中文，包括 title、tone、summary 等所有字段的值。

你是一位顶级的网文/游戏剧情主编。请严格执行【第一阶段：灵感接收】标准。

【执行标准】：
1. 精准拆解用户输入，主动将零散灵感拓展为完整框架（必须包含：主角雏形+核心冲突雏形+世界观基调）。
2. 基于框架，提供 3 个极具差异化的创作方向（差异必须体现在：剧情走向、玩法/看点侧重、世界观细节）。
3. 绝不抛出问题清单！不准反问用户！
4. 每个方向必须附带1-2句核心差异说明。

【强制输出规范】：
1. 必须使用中文回答！必须使用中文回答！
2. 请严格输出以下 JSON 结构，【不要】输出任何多余的解释、问候或 Markdown 之外的文字。
3. 必须使用 ```json 包裹。

```json
{
  "pitches": [
    {
      "id": 1,
      "title": "书名或方向名",
      "tone": "基调标签，如：黑暗/废土/悬疑",
      "summary": "一句话核心差异说明与剧情亮点，必须写满20个字以上"
    }
  ]
}
```
"""

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context_instruction + "\n\n请严格按照上述格式输出，必须使用 ```json 代码块包裹。"}
            ],
            temperature=0.9
        )
        raw = response.choices[0].message.content.strip()
        data = extract_json_from_markdown(raw)
        return data.get("pitches", [])
    except Exception as e:
        print(f"灵感裂变失败: {e}")
        return []


async def generate_outline_from_llm(pitch: dict, api_key: str = None, base_url: str = None, model_name: str = None) -> dict:
    """第二阶段：故事确认与大纲骨架锻造"""
    client = get_dynamic_client(api_key, base_url)
    model = get_dynamic_model(model_name)

    system_prompt = f"""
语言：中文。你必须使用中文回答。所有输出内容必须为中文，包括 title、core_goal、emotion_curve、location 等所有字段的值。

你是一位顶级的网文/游戏剧情主编。请严格执行【第二阶段：故事确认与大纲骨架锻造】标准。

【执行标准】：
1. 基于以下选定的创作方向，生成 10-15 个核心剧情卷（Volume）。
2. 每个卷必须包含：卷标题、核心目标、情感曲线、主要地点、预估章节数。
3. 卷之间必须有清晰的剧情递进逻辑，确保剧情节奏张弛有度。
4. 所有内容必须使用中文。

选定的创作方向：
标题：{pitch.get('title')}
基调：{pitch.get('tone')}
核心差异：{pitch.get('summary')}

【强制输出规范】：
1. 必须使用中文回答！必须使用中文回答！
2. 请严格输出以下 JSON 结构，【不要】输出任何多余的解释、问候或 Markdown 之外的文字。
3. 必须使用 ```json 包裹。

```json
{{
  "outline_nodes": [
    {{
      "volume_number": 1,
      "title": "卷标题",
      "core_goal": "本卷的核心剧情目标",
      "emotion_curve": "情感曲线描述",
      "location": "主要地点",
      "estimated_chapters": 5
    }}
  ]
}}
```
"""

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "请根据以上选定的创作方向，生成完整的大纲骨架。必须严格按照上述格式输出，必须使用 ```json 代码块包裹。"}
            ],
            temperature=0.85
        )
        raw = response.choices[0].message.content.strip()
        data = extract_json_from_markdown(raw)
        return data
    except Exception as e:
        print(f"大纲生成失败: {e}")
        return {"outline_nodes": []}
