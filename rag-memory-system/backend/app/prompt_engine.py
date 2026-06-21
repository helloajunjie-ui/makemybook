def build_injection_prompt(chapter_marker: int, fetch_response_data: dict, current_plot_context: str) -> str:
    found_entries = fetch_response_data.get("found_entries", [])
    missing_entries = fetch_response_data.get("missing_entries", [])

    prompt = f"""语言：中文。你必须使用中文回答。正文内容必须为中文。

你是业界顶级的剧情推演与文本生成AI。你正在撰写小说的第 {chapter_marker} 章。

<CRITICAL_DIRECTIVE>
你必须绝对服从以下【世界观设定字典】。这是本世界的物理与逻辑法则，任何情况下绝不可违背、篡改或遗漏！
</CRITICAL_DIRECTIVE>

<ESTABLISHED_FACTS>
"""

    if found_entries:
        for entry in found_entries:
            facts = entry.get('facts', [])
            facts_str = "；".join(f.get('content', '') for f in facts)
            prompt += f"- 【{entry['entry_name']}】({entry['type']}): {facts_str}\n"
    else:
        prompt += "- 当前时间节点无须特别约束的旧有设定。\n"

    prompt += "</ESTABLISHED_FACTS>\n\n"

    if missing_entries:
        missing_str = "、".join(missing_entries)
        prompt += f"""<NEW_CREATION_AUTHORIZATION>
提示：大纲中提到了以下新词条 [{missing_str}]。
这些是本章首次出现的全新设定。请结合上下文，极其自然地为它们赋予合理的外观、属性或背景，并在生成正文时丰满这些细节。
</NEW_CREATION_AUTHORIZATION>

"""

    prompt += f"""<CURRENT_SCENE>
{current_plot_context}
</CURRENT_SCENE>

请基于上述设定与场景，以沉浸式的网文笔法，直接输出正文内容。不写废话，拒绝说教。
"""
    return prompt
