import json
import asyncio
import uuid
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel
from typing import List, Optional

from app.database import get_db
from app.routers.memory import predict_fetch_memory
from app.schemas.fetch import FetchRequest
from app.prompt_engine import build_injection_prompt
from app.llm_client import stream_generate, extract_new_facts, suggest_plot_directions, _translate_llm_error
from app.models.entity import MemoryEntity
from app.models.fact import MemoryFact
from app.models.pitch import StoryPitch
from app.models.outline import StoryOutlineNode
from app.models.book import Book
from app.memory_compactor import run_compaction_task

router = APIRouter()


class StreamGenRequest(BaseModel):
    book_id: str
    chapter_marker: int
    plot_context: str
    extracted_triggers: List[str]
    custom_prompt: str = ""  # 💡 接收用户的自定义文风规则


@router.post("/generate")
async def stream_generation(req: StreamGenRequest, request: Request, db: AsyncSession = Depends(get_db)):

    api_key = request.headers.get("X-LLM-API-Key")
    base_url = request.headers.get("X-LLM-Base-URL")
    model_name = request.headers.get("X-LLM-Model")

    async def event_generator():
        try:
            # Phase 1 & 2: Fetch 提取与召回
            yield f"data: {json.dumps({'type': 'status', 'msg': '🔍 正在检索世界线记忆...', 'step': 'fetch'})}\n\n"
            await asyncio.sleep(0.5)

            fetch_req = FetchRequest(book_id=req.book_id, current_chapter=req.chapter_marker, extracted_triggers=req.extracted_triggers)
            fetch_res = await predict_fetch_memory(fetch_req, db)

            found = [e.entry_name for e in fetch_res.data.found_entries]
            missing = fetch_res.data.missing_entries

            yield f"data: {json.dumps({'type': 'status', 'msg': f'命中设定: {len(found)}个 | 允许新造物: {len(missing)}个', 'found': found, 'missing': missing})}\n\n"

            # Phase 3: Inject 组装法则 — 熔接全书创意 + 大纲路线
            yield f"data: {json.dumps({'type': 'status', 'msg': '🧱 正在熔接全书创意与大纲路线...', 'step': 'inject'})}\n\n"

            # 💡 从数据库查询 Pitch（全书核心创意）
            # 注意：不依赖 is_selected（前端可能未更新），按 created_at 倒序取最新一条
            pitch_context = ""
            selected_pitch = None
            try:
                pitch_result = await db.execute(
                    select(StoryPitch).order_by(StoryPitch.created_at.desc()).limit(1)
                )
                selected_pitch = pitch_result.scalar_one_or_none()
                if selected_pitch:
                    pitch_context = f"书名/标题: {selected_pitch.title}\n核心创意: {selected_pitch.summary}"
                    if selected_pitch.tone:
                        pitch_context += f"\n文风基调: {selected_pitch.tone}"
                    print(f"[大纲熔接] ✅ 命中 Pitch: {selected_pitch.title} (id={selected_pitch.id})")
                else:
                    print("[大纲熔接] ⚠️ 数据库中没有 Pitch 数据")
            except Exception as e:
                print(f"[大纲熔接] ❌ 查询 Pitch 失败: {e}")

            # 💡 从数据库查询全书大纲路线（通过 pitch_id 关联）
            outline_context = ""
            try:
                if selected_pitch:
                    outline_result = await db.execute(
                        select(StoryOutlineNode).where(
                            StoryOutlineNode.pitch_id == selected_pitch.id
                        ).order_by(StoryOutlineNode.sort_order)
                    )
                    outline_nodes = outline_result.scalars().all()
                    if outline_nodes:
                        lines = []
                        for node in outline_nodes:
                            line = f"第{node.volume_number}卷: {node.title}"
                            if node.core_goal:
                                line += f" —— {node.core_goal}"
                            if node.emotion_curve:
                                line += f" [情绪曲线: {node.emotion_curve}]"
                            lines.append(line)
                        outline_context = "\n".join(lines)
                        print(f"[大纲熔接] ✅ 命中 Outline: {len(outline_nodes)} 卷")
                    else:
                        print(f"[大纲熔接] ⚠️ Pitch {selected_pitch.id} 下没有 Outline 节点")
                else:
                    print("[大纲熔接] ⚠️ 无 Pitch，跳过 Outline 查询")
            except Exception as e:
                print(f"[大纲熔接] ❌ 查询 Outline 失败: {e}")

            # 日志验证：打印最终熔接内容
            print(f"[大纲熔接] pitch_context ({len(pitch_context)} chars): {pitch_context[:200]}")
            print(f"[大纲熔接] outline_context ({len(outline_context)} chars): {outline_context[:300]}")

            system_prompt = build_injection_prompt(
                req.chapter_marker,
                fetch_res.data,
                req.plot_context,
                pitch_context=pitch_context,
                outline_context=outline_context
            )

            # 💡 作者自定义文风约束熔接（最高优先级，必须严格遵守）
            if req.custom_prompt and req.custom_prompt.strip():
                system_prompt += f"\n\n【⚠️ 作者自定义文风与全局约束（最高优先级，必须严格遵守）】：\n{req.custom_prompt.strip()}"

            # Phase 4: Generate (LLM 核心流式推演)
            yield f"data: {json.dumps({'type': 'status', 'msg': '✍️ 引擎推演中...', 'step': 'generate'})}\n\n"

            full_text = ""
            async for chunk in stream_generate(system_prompt, api_key, base_url, model_name):
                if await request.is_disconnected():
                    print("客户端连接断开，终止生成")
                    break

                full_text += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"

            # Phase 5: Commit (写后提取与沉淀) — ACID 原子事务
            yield f"data: {json.dumps({'type': 'status', 'msg': '💾 正在炼化并沉淀新事实...', 'step': 'commit'})}\n\n"

            extracted_entities = await extract_new_facts(full_text, api_key, base_url, model_name)

            committed_results = []
            affected_entity_ids = set()
            try:
                for item in extracted_entities:
                    entry_name = item.get("entry_name", "")
                    entity_type = item.get("type", "其他")
                    content = item.get("content", "")

                    # 💡 世界书特有：关联词条熔接 — 不改表结构，拼入 content
                    relations = item.get("relations", [])
                    if isinstance(relations, list) and len(relations) > 0:
                        relations_str = " | ".join(relations)
                        content = f"{content}\n\n[关联]: {relations_str}"

                    if not entry_name or not content:
                        continue
                    # 💡 【核心防御闸门】：词条名超过 12 字 → AI 幻觉，丢弃
                    if len(entry_name) > 12:
                        print(f"[风控拦截] AI生成了恶意的超长词条名，已丢弃: {entry_name}")
                        continue

                    # 💡 获取大模型提炼的激活词，并进行安全兜底
                    triggers = item.get("triggers", [])
                    if not isinstance(triggers, list):
                        triggers = []
                    # 确保主词条名永远在激活词列表中，保证 100% 召回
                    if entry_name and entry_name not in triggers:
                        triggers.append(entry_name)

                    result = await db.execute(
                        select(MemoryEntity).where(
                            MemoryEntity.book_id == req.book_id,
                            MemoryEntity.entry_name == entry_name
                        )
                    )
                    entity = result.scalar_one_or_none()

                    if entity is None:
                        entity = MemoryEntity(
                            book_id=req.book_id,
                            entry_name=entry_name,
                            type=entity_type,
                            triggers=triggers
                        )
                        db.add(entity)
                        await db.flush()
                    else:
                        # 💡 实体已存在，追加新的激活词（去重合并）
                        existing_triggers = set(entity.triggers or [])
                        new_triggers = existing_triggers.union(set(triggers))
                        entity.triggers = list(new_triggers)

                    fact = MemoryFact(
                        entity_id=entity.id,
                        chapter_marker=req.chapter_marker,
                        content=content
                    )
                    db.add(fact)
                    await db.flush()

                    affected_entity_ids.add(str(entity.id))

                    committed_results.append({
                        "entry_name": entry_name,
                        "type": entity_type,
                        "content": content,
                        "triggers": triggers
                    })

                # 唯一一次 commit，保证原子性
                await db.commit()

                # 事务成功后，用 asyncio.create_task 调度后台压缩
                for eid in affected_entity_ids:
                    asyncio.create_task(run_compaction_task(eid, req.chapter_marker))

            except Exception as e:
                await db.rollback()
                print(f"数据持久化失败: {e}")

            yield f"data: {json.dumps({'type': 'commit_done', 'new_entities': committed_results})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'msg': _translate_llm_error(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


class SuggestRequest(BaseModel):
    recent_context: str


@router.post("/suggest")
async def get_plot_suggestions(req: SuggestRequest, request: Request):
    """前端主动索要剧情建议的 API"""
    api_key = request.headers.get("X-LLM-API-Key")
    base_url = request.headers.get("X-LLM-Base-URL")
    model_name = request.headers.get("X-LLM-Model")
    suggestions = await suggest_plot_directions(req.recent_context, api_key, base_url, model_name)
    return {"status": "success", "data": suggestions}


class ReviseRequest(BaseModel):
    book_id: str
    chapter_marker: int
    instruction: str
    prev_context: str = ""
    current_content: str
    next_context: str = ""


@router.post("/revise")
async def stream_revision(
    req: ReviseRequest,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """时光溯源：带上下文的章节重写与记忆重塑"""
    api_key = request.headers.get("X-LLM-API-Key")
    base_url = request.headers.get("X-LLM-Base-URL")
    model_name = request.headers.get("X-LLM-Model")

    system_prompt = f"""
语言：中文。你必须使用中文回答。正文内容必须为中文。

你是一位网文大神级修稿师。用户要求对【第 {req.chapter_marker} 章】进行重写或润色。
【修稿指令】：{req.instruction}

【上下文约束锚点】：
前一章结尾：{req.prev_context[-800:] if req.prev_context else '无（这是开局）'}
当前章原稿：{req.current_content}
后一章开头：{req.next_context[:800] if req.next_context else '无（这是最新章）'}

【执行法则】：
1. 严格执行用户的修稿指令。如果是局部润色，请保留未提及修改的精彩原文；如果是重写，请放开手脚。
2. 必须保证与【前一章结尾】和【后一章开头】的剧情、情绪衔接天衣无缝！
3. 绝不输出多余的解释、确认语，直接输出修改后的【完整章节正文】。
"""

    async def event_generator():
        try:
            full_new_text = ""
            async for chunk in stream_generate(system_prompt, api_key, base_url, model_name):
                full_new_text += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"

            # 记忆重塑
            try:
                stmt = update(MemoryFact).where(
                    MemoryFact.entity_id.in_(
                        select(MemoryEntity.id).where(MemoryEntity.book_id == req.book_id)
                    ),
                    MemoryFact.chapter_marker == req.chapter_marker
                ).values(is_active=0)
                await db.execute(stmt)

                extracted_entities = await extract_new_facts(full_new_text, api_key, base_url, model_name)

                affected_entity_ids = set()
                for item in extracted_entities:
                    entry_name = item.get("entry_name", "")
                    content = item.get("content", "")
                    if not entry_name or not content:
                        continue
                    # 💡 【核心防御闸门】：词条名超过 12 字 → AI 幻觉，丢弃
                    if len(entry_name) > 12:
                        print(f"[风控拦截] AI生成了恶意的超长词条名，已丢弃: {entry_name}")
                        continue

                    # 💡 获取大模型提炼的激活词，并进行安全兜底
                    triggers = item.get("triggers", [])
                    if not isinstance(triggers, list):
                        triggers = []
                    if entry_name and entry_name not in triggers:
                        triggers.append(entry_name)

                    result = await db.execute(
                        select(MemoryEntity).where(
                            MemoryEntity.book_id == req.book_id,
                            MemoryEntity.entry_name == entry_name
                        )
                    )
                    entity = result.scalar_one_or_none()

                    if not entity:
                        entity = MemoryEntity(
                            book_id=req.book_id,
                            entry_name=entry_name,
                            type=item.get("type", "其他"),
                            triggers=triggers
                        )
                        db.add(entity)
                        await db.flush()
                    else:
                        existing_triggers = set(entity.triggers or [])
                        new_triggers = existing_triggers.union(set(triggers))
                        entity.triggers = list(new_triggers)

                    new_fact = MemoryFact(
                        entity_id=entity.id,
                        chapter_marker=req.chapter_marker,
                        content=content,
                        is_active=1
                    )
                    db.add(new_fact)
                    affected_entity_ids.add(str(entity.id))

                await db.commit()

                for eid in affected_entity_ids:
                    asyncio.create_task(run_compaction_task(eid, req.chapter_marker))

            except Exception as e:
                await db.rollback()
                print(f"[Revision] 记忆重塑失败: {e}")

            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': _translate_llm_error(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
