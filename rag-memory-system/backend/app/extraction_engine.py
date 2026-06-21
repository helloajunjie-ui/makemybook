import json
import re


EXTRACTION_PROMPT_TEMPLATE = """你是一个精确的小说设定提取器。你的任务是从正文中提取出新产生的事实碎片。

【规则】
1. 只提取正文中明确提及的、与世界观设定相关的原子化事实
2. 每个事实必须是一个独立的短句
3. 忽略对话、心理描写、修辞性表达
4. 输出格式为 JSON 数组，每个元素包含: entry_name, type, triggers, content
5. type 只能是以下之一: 人物, 地点, 物品, 组织, 事件, 能力, 其他
6. triggers 是 entry_name 可能的别名/简称列表
7. 如果正文中没有新的事实产生，返回空数组 []

【正文】
{text}

【输出】
"""


def build_extraction_prompt(text: str) -> str:
    return EXTRACTION_PROMPT_TEMPLATE.format(text=text)


def parse_extraction_result(raw: str) -> list[dict]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        items = json.loads(cleaned)
        if not isinstance(items, list):
            return []
        return items
    except json.JSONDecodeError:
        return []
