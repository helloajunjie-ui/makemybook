import os
import json
from dotenv import load_dotenv
from openai import AsyncOpenAI, APIError

load_dotenv()

_LLM_ERROR_MAP = {
    401: "API Key 无效或已过期，请检查前端面板或 .env 中的配置",
    402: "API 账户余额不足，请充值后重试",
    403: "API 访问被拒绝，请检查密钥权限",
    404: "请求的模型不存在或端点错误",
    429: "API 请求频率过高，请稍后重试",
    500: "LLM 服务端内部错误，请稍后重试",
    502: "LLM 网关错误，请稍后重试",
    503: "LLM 服务暂时不可用，请稍后重试",
}


def _translate_llm_error(e: Exception) -> str:
    """将 LLM SDK 异常翻译为中文用户提示"""
    if isinstance(e, APIError):
        code = e.status_code
        hint = _LLM_ERROR_MAP.get(code)
        if hint:
            return f"LLM API 错误 (HTTP {code}): {hint}"
        return f"LLM API 错误 (HTTP {code}): {e.message}"
    msg = str(e)
    if "connect" in msg.lower() or "connection" in msg.lower() or "timeout" in msg.lower():
        return "无法连接到 LLM API，请检查网络连接或 API 地址配置"
    if "api_key" in msg.lower() or "apikey" in msg.lower():
        return "API Key 未配置。请在前端面板设置，或在后端 .env 中配置 LLM_API_KEY"
    return f"LLM 调用异常: {msg}"


def get_dynamic_client(api_key: str = None, base_url: str = None):
    """动态获取大模型客户端，优先使用前端传来的配置，否则降级使用 .env"""
    final_key = api_key or os.getenv("LLM_API_KEY")
    final_url = base_url or os.getenv("LLM_BASE_URL")

    if not final_key:
        raise ValueError("API Key 未配置。请在前端面板设置，或在后端 .env 中配置 LLM_API_KEY")

    return AsyncOpenAI(api_key=final_key, base_url=final_url)


def get_dynamic_model(model_name: str = None):
    return model_name or os.getenv("LLM_MODEL") or "deepseek-chat"


async def stream_generate(system_prompt: str, api_key: str = None, base_url: str = None, model_name: str = None):
    client = get_dynamic_client(api_key, base_url)
    model = get_dynamic_model(model_name)

    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "请基于以上设定，紧接前文继续生成正文。"}
        ],
        temperature=0.8,
        stream=True
    )

    async for chunk in response:
        content = chunk.choices[0].delta.content
        if content is not None:
            yield content


async def extract_new_facts(text: str, api_key: str = None, base_url: str = None, model_name: str = None) -> list:
    extraction_prompt = """
语言：中文。你必须使用中文回答。所有输出内容必须为中文，包括 entry_name、type、content 等所有字段的值。

你是一个无情的实体提取器。请阅读以下小说正文，提取出所有【全新的】或【发生重大状态改变】的设定。
如果是过渡性废话请忽略，只保留会影响后续剧情的永久性设定（如：张三断了右腿、获得了一把轩辕剑）。

必须且只能返回合法的 JSON 对象，格式严格如下：
{
  "entities": [
    {
      "entry_name": "实体标准名",
      "type": "人物",
      "content": "一句话原子化的事实描述"
    }
  ]
}
type 字段必须是以下枚举值之一：人物、地点、道具、事件、世界观

【重要】你必须使用中文回答。所有输出内容必须为中文，包括 entry_name、type、content 等所有字段的值。
"""
    client = get_dynamic_client(api_key, base_url)
    model = get_dynamic_model(model_name)

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": extraction_prompt},
                {"role": "user", "content": f"提取以下正文中的设定：\n\n{text}"}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )

        raw_json = response.choices[0].message.content
        data = json.loads(raw_json)
        return data.get("entities", [])
    except Exception as e:
        print(f"提取新事实失败: {e}")
        return []


async def compact_old_facts(entity_name: str, entity_type: str, facts_list: list, api_key: str = None, base_url: str = None, model_name: str = None) -> list:
    """
    后台炼化：将十几条琐碎的事实压缩为 2-3 条核心设定
    """
    facts_str = "\n".join([f"- {f}" for f in facts_list])
    compaction_prompt = f"""
语言：中文。你必须使用中文回答。所有输出内容必须为中文，包括 compacted_facts 数组中的每个字符串。

你是一个无情的记忆炼化引擎。
以下是关于【{entity_name}】({entity_type}) 在长篇小说中积累的近期时间线事实：

{facts_str}

【炼化规则】：
1. 剔除所有过渡性、临时性的废话（例如：他今天吃了顿饭、他走向了城门）。
2. 提炼并保留永久性、影响剧情的核心设定（例如：断了右腿、获得了某神器、性格从善良转为腹黑）。
3. 将信息极致压缩为 1 到 3 句话的原子事实。

必须严格返回 JSON 格式：
{{
  "compacted_facts": ["核心事实1", "核心事实2"]
}}

【重要】你必须使用中文回答。所有输出内容必须为中文，包括 compacted_facts 数组中的每个字符串。
"""
    client = get_dynamic_client(api_key, base_url)
    model = get_dynamic_model(model_name)

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": compaction_prompt}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        return data.get("compacted_facts", [])
    except Exception as e:
        print(f"记忆炼化失败: {e}")
        return []


async def suggest_plot_directions(recent_context: str, api_key: str = None, base_url: str = None, model_name: str = None) -> list:
    """
    极速推演：根据近期上下文，给出 3 个剧情走向建议
    """
    prompt = f"""
语言：中文。你必须使用中文回答。所有输出内容必须为中文，包括 suggestions 数组中的每个字符串。

你是一个顶级网文军师。请阅读以下最近的剧情讨论：
{recent_context}

请基于以上讨论，推演出接下来最可能发生的 3 个截然不同的剧情走向。
要求：
1. 必须差异化（例如：一个是遇袭，一个是发现线索，一个是人物情感爆发）。
2. 极其精炼，每个方向不超过 30 个字。
3. 严格返回 JSON 格式：
{{
  "suggestions": ["方向1", "方向2", "方向3"]
}}

【重要】你必须使用中文回答。所有输出内容必须为中文，包括 suggestions 数组中的每个字符串。
"""
    client = get_dynamic_client(api_key, base_url)
    model = get_dynamic_model(model_name)

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": prompt}],
            temperature=0.8,
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        return data.get("suggestions", [])
    except Exception as e:
        print(f"推演方向失败: {e}")
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

【强制 JSON 输出格式】：
{
  "pitches": [
    {
      "id": 1,
      "title": "书名或方向名",
      "tone": "基调标签，如：黑暗/废土/悬疑",
      "summary": "一句话核心差异说明与剧情亮点"
    }
  ]
}
"""

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": context_instruction}
            ],
            temperature=0.9,
            response_format={"type": "json_object"}
        )
        data = json.loads(response.choices[0].message.content)
        return data.get("pitches", [])
    except Exception as e:
        print(f"灵感裂变失败: {e}")
        return []


async def generate_outline_from_llm(pitch: dict, api_key: str = None, base_url: str = None, model_name: str = None) -> dict:
    """第二阶段：故事确认与大纲骨架锻造"""
    client = get_dynamic_client(api_key, base_url)
    model = get_dynamic_model(model_name)

    system_prompt = f"""
    语言：中文。你必须使用中文回答。所有输出内容必须为中文，包括 confirmed_settings、title、core_goal、emotion_curve、location 等所有字段的值。

    你是一位顶级的网文/游戏世界观架构师。用户已明确敲定了以下故事框架：
    书名：{pitch.get('title')}
    基调：{pitch.get('tone')}
    简介：{pitch.get('summary') or pitch.get('desc')}

    请严格执行【第二阶段：故事确认】标准，不要有任何模糊表述。

    【执行标准】：
    1. 彻底锁定并丰满核心信息：主角设定、核心冲突、关键NPC、世界观基调、核心看点/玩法倾向。
    2. 这是一部预计几十万字甚至百万字的长篇巨著。请将该故事推演为【至少 10 个核心大阶段】（对应 10 卷以上大纲）。
    3. 每一卷的划分标志必须是：【大地图的转移】、【重大生命阶段的蜕变】或【终极目标的质变】。切忌把几十个字的小章节当成卷！

    【强制 JSON 输出格式】：
    {{
      "confirmed_settings": "将主角、冲突、NPC、世界观、看点等所有锁定信息的详细设定，合并成一段约500字的全局世界观摘要...",
      "outline_nodes": [
        {{
          "volume_number": 1,
          "title": "第一卷：卷名（需具史诗感）",
          "core_goal": "本卷的核心目标、冲突触发点及剧情走向概述（约50字）",
          "emotion_curve": "本卷的情感曲线描述",
          "location": "本卷的主要发生地点",
          "estimated_chapters": 5,
          "status": "active"
        }},
        // ... 至少输出 10 卷以上，第二卷起 status 为 "pending"
      ]
    }}
    """

    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "请确认上述设定，并输出完整的大纲 JSON。"}
            ],
            temperature=0.4,
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"大纲生成失败: {e}")
        return {"confirmed_settings": pitch.get('summary') or pitch.get('desc', ''), "outline_nodes": []}
