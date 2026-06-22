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


async def compute_embedding(text: str, api_key: str = None, base_url: str = None) -> list[float]:
    """💡 RAG v2：调用 Embedding API 将文本转为向量

    复用 LLM 的 base_url/api_key（DeepSeek / 中转站均兼容 OpenAI Embeddings）。
    返回 1536 维向量（text-embedding-3-small 默认维度）。
    """
    try:
        client = get_dynamic_client(api_key, base_url)
        response = await client.embeddings.create(
            model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"[Embedding API] 调用失败: {e}，返回空向量")
        return []



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


async def consolidate_entity_profile(old_profile: str, new_insights: str, api_key: str = None, base_url: str = None, model_name: str = None) -> str:
    """💡【记忆融合引擎】将旧设定卡与新情报融合为一份精炼词条

    状态机核心：One Entity = One Active Profile。
    将 old_profile（当前 is_active=1 的词条）与 new_insights（本章新情报）
    融合为一份全新的、精炼的、结构化的角色词条。
    """
    prompt = f"""你是一个世界观档案管理员。这里有该角色【原有的设定卡】和【本章发生的新情报】。
请你将新情报无缝【融合】到原设定卡中，输出一份【全新、精炼、结构化】的角色词条。

规则：
1. 剔除过时/矛盾的早期状态（例如：如果她现在已经开朗，就不要用大篇幅描写她曾经的自闭，只需一笔带过"曾有创伤但已走出"）。
2. 保持字数精简，提炼核心性格、人际关系、重要道具，剔除琐碎的日常流水账。
3. 必须输出一份完整的、可以直接作为百科词条阅读的文本。

【原有的设定卡】：
{old_profile}

【本章发生的新情报】：
{new_insights}

请直接输出融合后的完整词条文本，不要额外解释。"""
    client = get_dynamic_client(api_key, base_url)
    model = get_dynamic_model(model_name)
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是一个世界观档案管理员。只输出融合后的词条文本，不要额外解释。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=800
        )
        merged = response.choices[0].message.content.strip()
        print(f"[记忆融合] 融合完成: {len(old_profile)} chars + {len(new_insights)} chars → {len(merged)} chars")
        return merged
    except Exception as e:
        print(f"[记忆融合] LLM 调用失败，返回原始新情报作为降级: {e}")
        return new_insights


async def extract_new_facts(text: str, api_key: str = None, base_url: str = None, model_name: str = None) -> list:
    extraction_prompt = """
语言：中文。你必须使用中文回答。所有输出内容必须为中文。

请从最新章节正文中，提取并编撰世界书词条。

【🚨 绝对禁止 — 代词封杀】
严禁将以下任何词作为 entry_name 提取：
- 第一人称代词："我"、"自己"、"本人"
- 第二人称代词："你"、"您"、"汝"
- 第三人称代词："他"、"她"、"它"、"他们"、"她们"、"它们"
- 指示代词："这"、"那"、"这个"、"那个"
- 如果文中出现上述代词，必须通过上下文推断其指代的【真实人物/实体全名】，将该事实归入该真实实体名下。

【🚨 强制实体消歧 — 别名合并】
如果文中出现了同一个人的不同称呼（如"哥哥"、"林哥哥"、"小林"、"林兄"），你必须：
1. 识别出这些称呼指向的是同一个【真实全名】角色
2. 只以该角色的【真实全名】作为 entry_name 创建一条实体
3. 将所有别名/昵称/称呼放入该实体的 triggers 数组中
4. 绝对禁止为同一个角色的不同称呼创建多个独立实体！

【世界书编撰法则】：
1. "entry_name"（词条）：必须是该实体的【真实专有名词/全名】（如"林墨"、"青云宗"、"斩天剑"），1-8字。禁止使用代词或昵称作为 entry_name。
2. "triggers"（触发关键词）：全词匹配，包含所有别名、外号、简称、称呼（如"哥哥"、"我"——如果主角是第一人称叙述，将"我"作为主角的 trigger）。禁用通用虚词。
3. "type"（类型）：人物、地点、物品、组织、事件、能力、其他。
4. "relations"（关联词条）：与该词条强相关的其他专有名词列表。
5. "content"（世界书内容）：用 50-200 字的精炼文本描述该词条的核心特征。

【强制输出规范】：
必须输出包含 "entities" 键的 JSON：
```json
{
  "entities": [
    {
      "entry_name": "林墨",
      "triggers": ["林墨", "哥哥", "林哥哥", "小林", "我"],
      "type": "人物",
      "relations": ["青云宗", "斩天剑"],
      "content": "本书主角，青云宗外门弟子，性格坚毅，擅长剑术。"
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

请整理【实体：{entity_name}（{entity_type}）】在过往多个章节中积累的零散情报，将它们整合为一份完整的词条。

【整合要求】：
1. 包含所有重要信息。
2. 内容组织成具有可读性的段落。
3. 如果信息有更新，以最新状态为准。

原始事实：
{json.dumps(facts_list, ensure_ascii=False, indent=2)}

【强制输出规范】：
1. 必须使用中文回答！必须使用中文回答！
2. 请严格输出以下 JSON 结构，【不要】输出任何多余的解释、问候或 Markdown 之外的文字。
3. 必须使用 ```json 包裹。

```json
["整合后的完整文本"]
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
        details_str = target_pitch.get('details', '')
        details_block = f"\n原方向详细设定：{details_str}" if details_str else ""
        context_instruction = f"用户希望基于以下特定方向进行微调或重做：\n原方向：{target_pitch.get('title')} - {target_pitch.get('summary')}{details_block}\n用户的修改建议/新灵感为：{seed_text}"

    system_prompt = f"""
语言：中文。你必须使用中文回答。所有输出内容必须为中文，包括 title、tone、summary 等所有字段的值。

你是一位专业的创作灵感衍生工具。请基于用户输入的灵感，提供 3 个差异化的创作方向。

【执行标准】：
1. 基于用户输入，衍生出完整的创作框架。
2. 提供 3 个差异化的创作方向。
3. 绝不抛出问题清单！不准反问用户！
4. 每个方向必须附带核心差异说明。

【强制输出规范】：
1. 必须使用中文回答！必须使用中文回答！
2. 请严格输出以下 JSON 结构，【不要】输出任何多余的解释、问候或 Markdown 之外的文字。
3. 必须使用 ```json 包裹。

```json
{{
  "pitches": [
    {{
      "id": 1,
      "title": "书名或方向名",
      "tone": "基调标签，如：温馨/治愈/日常",
      "summary": "一句话核心差异说明与剧情亮点，必须写满20个字以上",
      "details": "详细设定：包含核心世界观、主要人物关系、故事主线脉络、独特设定等。必须写满100字以上，为后续大纲生成提供完整素材"
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

你是一位专业的故事大纲生成工具。请基于以下选定的创作方向，生成大纲骨架。

【执行标准】：
1. 基于以下选定的创作方向，生成 10-15 个核心剧情卷（Volume）。
2. 每个卷必须包含：卷标题、核心目标、情感曲线、主要地点、预估章节数。
3. 卷之间必须有清晰的剧情递进逻辑。
4. 所有内容必须使用中文。


选定的创作方向：
标题：{pitch.get('title')}
基调：{pitch.get('tone')}
核心差异：{pitch.get('summary')}
详细设定：{pitch.get('details', '')}

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
