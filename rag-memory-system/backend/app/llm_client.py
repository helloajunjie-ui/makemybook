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
    client = get_dynamic_client(api_key, base_url)
    model = get_dynamic_model(model_name)
    async with client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "请根据上述设定开始创作"}
        ],
        stream=True,
        temperature=0.85
    ) as stream:
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


async def extract_new_facts(text: str, api_key: str = None, base_url: str = None, model_name: str = None) -> list:
    extraction_prompt = """
语言：中文。你必须使用中文回答。所有输出内容必须为中文。

你是一个网文/游戏剧情的事实抽取器。请从以下文本中抽取所有可验证的剧情事实。

【抽取标准】：
1. 只抽取明确陈述的事实（角色设定、事件、关系、世界观规则等）
2. 不抽取模糊感受、修辞、对话中的假设
3. 每个事实是一句完整的中文陈述
4. 输出 JSON 数组

【强制输出规范】：
1. 必须使用中文回答！必须使用中文回答！
2. 请严格输出以下 JSON 结构，【不要】输出任何多余的解释、问候或 Markdown 之外的文字。
3. 必须使用 ```json 包裹。

```json
["事实1", "事实2", "事实3"]
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
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        print(f"事实抽取失败: {e}")
        return []


async def compact_old_facts(entity_name: str, entity_type: str, facts_list: list, api_key: str = None, base_url: str = None, model_name: str = None) -> list:
    prompt = f"""
语言：中文。你必须使用中文回答。所有输出内容必须为中文。

你是一个网文/游戏剧情的事实压缩器。请将以下关于「{entity_name}（{entity_type}）」的事实列表进行压缩合并。

【压缩标准】：
1. 合并语义重复的事实
2. 删除过时或被覆盖的细节
3. 保留所有不重复的关键信息
4. 输出为 JSON 字符串数组

原始事实：
{json.dumps(facts_list, ensure_ascii=False, indent=2)}

【强制输出规范】：
1. 必须使用中文回答！必须使用中文回答！
2. 请严格输出以下 JSON 结构，【不要】输出任何多余的解释、问候或 Markdown 之外的文字。
3. 必须使用 ```json 包裹。

```json
["压缩后的事实1", "压缩后的事实2"]
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
1. 基于以下选定的创作方向，生成 3-6 个核心剧情卷（Volume）。
2. 每个卷必须包含：卷标题、核心目标、情感曲线、主要地点、预估章节数。
3. 卷之间必须有清晰的剧情递进逻辑。
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
