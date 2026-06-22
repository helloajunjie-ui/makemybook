import tiktoken


# 💡【钛合金钢板-第三根】Token 截断阈值
MAX_PROMPT_TOKENS = 6000
# 各部分的保留优先级（从高到低）：custom_prompt > current_scene > pitch > outline > rag_facts
# 裁剪顺序：先砍 RAG facts 数量，再砍 outline 早期卷，最后砍 pitch


def _truncate_by_tokens(text: str, max_tokens: int, encoding) -> str:
    """将文本截断到指定 token 数以内（保留开头）"""
    tokens = encoding.encode(text)
    if len(tokens) <= max_tokens:
        return text
    return encoding.decode(tokens[:max_tokens])


def build_injection_prompt(
    chapter_marker: int,
    fetch_data,
    current_plot_context: str,
    pitch_context: str = "",
    outline_context: str = "",
    current_volume: int = 1  # 💡【阶段锁定】当前正在撰写的卷号
) -> str:
    found_entries = fetch_data.found_entries
    missing_entries = fetch_data.missing_entries

    # ── 1. 组装各部分原始内容 ──
    prompt_parts = {}

    # 固定头部（token 极少，不裁剪）
    header = f"""语言：中文。你必须使用中文回答。正文内容必须为中文。

<CRITICAL_DIRECTIVE>
【当前进度坐标】
你正在撰写的是：第 {current_volume} 卷 的 第 {chapter_marker} 章。

【视界锁定与节奏纪律】
1. 绝对边界：你目前的思考和剧情推演【仅限】于当前第 {current_volume} 卷的核心目标内！绝对禁止越界触发或暗示下一卷的事件。
2. 无限容量：本卷没有章节数量限制。不要急于完结本卷的目标。
3. 显微镜视角：放慢叙事节奏（Slow pacing），聚焦于当前的微观交互、动作细节、心理描写和环境渲染。一步一个脚印地推进。

你必须严格遵循以下【全书核心创意与大纲路线】以及【世界观设定字典】。
</CRITICAL_DIRECTIVE>
"""

    # Pitch（核心创意）
    pitch_section = ""
    if pitch_context:
        pitch_section = f"""
<CORE_CREATIVE_CONCEPT>
{pitch_context}
</CORE_CREATIVE_CONCEPT>
"""

    # Outline（大纲路线）
    outline_section = ""
    if outline_context:
        # 💡【阶段锁定】在当前卷旁边注入注意力锚点
        highlighted_outline = outline_context.replace(
            f"第{current_volume}卷:",
            f"第{current_volume}卷: [<<< 当前所在卷，绝对聚焦于此 >>>]"
        )
        outline_section = f"""
<OUTLINE_ROADMAP>
{highlighted_outline}
</OUTLINE_ROADMAP>
"""

    # RAG Facts（世界观设定字典）
    facts_section = "<ESTABLISHED_FACTS>\n"
    if found_entries:
        for entry in found_entries:
            facts = entry.facts
            facts_str = "；".join(f.content for f in facts)
            facts_section += f"- 【{entry.entry_name}】({entry.type}): {facts_str}\n"
    else:
        facts_section += "- 当前时间节点无须特别约束的旧有设定。\n"
    facts_section += "</ESTABLISHED_FACTS>\n\n"

    # Missing entries（新造物授权）
    missing_section = ""
    if missing_entries:
        missing_str = "、".join(missing_entries)
        missing_section = f"""<NEW_CREATION_AUTHORIZATION>
提示：大纲中提到了以下新词条 [{missing_str}]。
这些是本章首次出现的全新设定。请结合上下文，极其自然地为它们赋予合理的外观、属性或背景，并在生成正文时丰满这些细节。
</NEW_CREATION_AUTHORIZATION>

"""

    # Current Scene（当前场景 — 最高优先级保留）
    scene_section = f"""<CURRENT_SCENE>
{current_plot_context}
</CURRENT_SCENE>

请基于上述设定与场景，直接输出正文内容。
"""

    # ── 2. 组装完整 prompt ──
    prompt = header + pitch_section + outline_section + facts_section + missing_section + scene_section

    # ── 3. Token 计数与动态截断 ──
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        token_count = len(encoding.encode(prompt))

        if token_count > MAX_PROMPT_TOKENS:
            print(f"[Token 截断] 原始 prompt {token_count} tokens，超过阈值 {MAX_PROMPT_TOKENS}，启动裁剪...")

            # 裁剪策略：从低优先级到高优先级逐步裁剪
            # 第一刀：砍 RAG facts 数量（从 Top 15 减到 Top 5）
            if token_count > MAX_PROMPT_TOKENS and found_entries and len(found_entries) > 5:
                found_entries = found_entries[:5]
                facts_section = "<ESTABLISHED_FACTS>\n"
                for entry in found_entries:
                    facts = entry.facts
                    facts_str = "；".join(f.content for f in facts)
                    facts_section += f"- 【{entry.entry_name}】({entry.type}): {facts_str}\n"
                facts_section += "</ESTABLISHED_FACTS>\n\n"
                prompt = header + pitch_section + outline_section + facts_section + missing_section + scene_section
                token_count = len(encoding.encode(prompt))
                print(f"[Token 截断] 第一刀后: {token_count} tokens")

            # 第二刀：砍 outline 到 2000 tokens
            if token_count > MAX_PROMPT_TOKENS and outline_section:
                outline_section = _truncate_by_tokens(outline_section, 2000, encoding)
                prompt = header + pitch_section + outline_section + facts_section + missing_section + scene_section
                token_count = len(encoding.encode(prompt))
                print(f"[Token 截断] 第二刀后: {token_count} tokens")

            # 第三刀：砍 pitch 到 1000 tokens
            if token_count > MAX_PROMPT_TOKENS and pitch_section:
                pitch_section = _truncate_by_tokens(pitch_section, 1000, encoding)
                prompt = header + pitch_section + outline_section + facts_section + missing_section + scene_section
                token_count = len(encoding.encode(prompt))
                print(f"[Token 截断] 第三刀后: {token_count} tokens")

            # 第四刀：终极保底 — 砍 RAG facts 到 3 条
            if token_count > MAX_PROMPT_TOKENS and found_entries and len(found_entries) > 3:
                found_entries = found_entries[:3]
                facts_section = "<ESTABLISHED_FACTS>\n"
                for entry in found_entries:
                    facts = entry.facts
                    facts_str = "；".join(f.content for f in facts)
                    facts_section += f"- 【{entry.entry_name}】({entry.type}): {facts_str}\n"
                facts_section += "</ESTABLISHED_FACTS>\n\n"
                prompt = header + pitch_section + outline_section + facts_section + missing_section + scene_section
                token_count = len(encoding.encode(prompt))
                print(f"[Token 截断] 第四刀后: {token_count} tokens")

            print(f"[Token 截断] 最终 prompt: {token_count} tokens")

    except Exception as e:
        # tiktoken 失败时静默降级，不阻塞生成
        print(f"[Token 截断] tiktoken 初始化失败，跳过裁剪: {e}")

    return prompt
