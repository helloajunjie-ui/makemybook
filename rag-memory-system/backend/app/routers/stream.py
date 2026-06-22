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
from app.llm_client import stream_generate, extract_new_facts, suggest_plot_directions, _translate_llm_error, compute_embedding
from app.models.entity import MemoryEntity
from app.models.fact import MemoryFact
from app.models.pitch import StoryPitch
from app.models.outline import StoryOutlineNode
from app.models.book import Book
from app.memory_compactor import run_compaction_task

router = APIRouter()


# ═══════════════════════════════════════════════════════════════
# 公共函数：获取全书全局上下文（Pitch + Outline）
# DRY 原则：stream_generation / stream_revision / get_plot_suggestions 统一调用
# ═══════════════════════════════════════════════════════════════
async def get_book_global_context(book_id: str, db: AsyncSession) -> dict:
    """查询 Pitch（核心创意）+ Outline（大纲路线），返回格式化文本字典。"""
    result = {
        "pitch_context": "",
        "outline_context": "",
        "pitch_block": "",
        "outline_block": "",
    }
    try:
        pitch_row = await db.execute(
            select(StoryPitch).where(
                StoryPitch.book_id == uuid.UUID(book_id)
            ).order_by(StoryPitch.created_at.desc()).limit(1)
        )
        pitch = pitch_row.scalar_one_or_none()
        if not pitch:
            print(f"[全局上下文] [WARN] 书 {book_id} 下无 Pitch")
            return result

        # 组装 pitch_context
        pc = f"书名/标题: {pitch.title}\n核心创意: {pitch.summary}"
        if pitch.tone:
            pc += f"\n文风基调: {pitch.tone}"
        if pitch.details:
            pc += f"\n详细设定:\n{pitch.details}"
        result["pitch_context"] = pc
        result["pitch_block"] = f"\n【全书核心创意】\n{pc}\n"
        print(f"[全局上下文] [OK] 命中 Pitch: {pitch.title} (id={pitch.id})")

        # 组装 outline_context
        outline_rows = await db.execute(
            select(StoryOutlineNode).where(
                StoryOutlineNode.pitch_id == pitch.id
            ).order_by(StoryOutlineNode.sort_order)
        )
        nodes = outline_rows.scalars().all()
        if nodes:
            lines = []
            for n in nodes:
                line = f"第{n.volume_number}卷: {n.title}"
                if n.core_goal:
                    line += f" —— {n.core_goal}"
                if n.emotion_curve:
                    line += f" [情绪曲线: {n.emotion_curve}]"
                lines.append(line)
            oc = "\n".join(lines)
            result["outline_context"] = oc
            result["outline_block"] = f"\n【大纲路线】\n{oc}\n"
            print(f"[全局上下文] [OK] 命中 Outline: {len(nodes)} 卷")
        else:
            print(f"[全局上下文] [WARN] Pitch {pitch.id} 下无 Outline 节点")
    except Exception as e:
        import traceback
        print(f"[全局上下文] [ERROR] 查询失败: {e}")
        print(f"[全局上下文] [ERROR] 调用栈:\n{traceback.format_exc()}")

    return result


class StreamGenRequest(BaseModel):
    book_id: str
    chapter_marker: int
    plot_context: str
    extracted_triggers: List[str] = []  # 兼容旧版（不再使用）
    query_text: str = ""  # 💡 RAG v2：原始文本，后端做向量检索
    custom_prompt: str = ""  # 💡 接收用户的自定义文风规则
    current_volume: int = 1  # 💡【阶段锁定】当前正在撰写的卷号


@router.post("/generate")
async def stream_generation(req: StreamGenRequest, request: Request, db: AsyncSession = Depends(get_db)):

    api_key = request.headers.get("X-LLM-API-Key")
    base_url = request.headers.get("X-LLM-Base-URL")
    model_name = request.headers.get("X-LLM-Model")

    async def event_generator():
        full_text = ""
        try:
            # Phase 1 & 2: Fetch 提取与召回
            yield f"data: {json.dumps({'type': 'status', 'msg': '[检索] 正在检索世界线记忆...', 'step': 'fetch'})}\n\n"
            await asyncio.sleep(0.5)

            fetch_req = FetchRequest(book_id=req.book_id, current_chapter=req.chapter_marker, extracted_triggers=req.extracted_triggers)
            fetch_res = await predict_fetch_memory(fetch_req, db)

            found = [e.entry_name for e in fetch_res.data.found_entries]
            missing = fetch_res.data.missing_entries

            yield f"data: {json.dumps({'type': 'status', 'msg': f'命中设定: {len(found)}个 | 允许新造物: {len(missing)}个', 'found': found, 'missing': missing})}\n\n"

            # Phase 3: Inject 组装法则 — 熔接全书创意 + 大纲路线
            yield f"data: {json.dumps({'type': 'status', 'msg': '[熔接] 正在熔接全书创意与大纲路线...', 'step': 'inject'})}\n\n"

            # 💡 公共函数：熔接全书创意 + 大纲路线（DRY）
            print(f"[吐真剂] book_id={req.book_id}, type={type(req.book_id).__name__}")
            ctx = await get_book_global_context(req.book_id, db)
            pitch_context = ctx["pitch_context"]
            outline_context = ctx["outline_context"]
            print(f"[吐真剂] pitch_context ({len(pitch_context)} chars): {pitch_context[:200] if pitch_context else '(空)'}")
            print(f"[吐真剂] outline_context ({len(outline_context)} chars): {outline_context[:300] if outline_context else '(空)'}")

            system_prompt = build_injection_prompt(
                req.chapter_marker,
                fetch_res.data,
                req.plot_context,
                pitch_context=pitch_context,
                outline_context=outline_context,
                current_volume=req.current_volume
            )

            # 💡 作者自定义文风约束熔接（最高优先级，必须严格遵守）
            if req.custom_prompt and req.custom_prompt.strip():
                system_prompt += f"\n\n【作者自定义文风与全局约束（最高优先级，必须严格遵守）】：\n{req.custom_prompt.strip()}"

            # Phase 4: Generate (LLM 核心流式推演)
            yield f"data: {json.dumps({'type': 'status', 'msg': '[推演] 引擎推演中...', 'step': 'generate'})}\n\n"

            # ===== 吐真剂：打印最终 SYSTEM PROMPT =====
            print("========== FINAL SYSTEM PROMPT =========")
            print(system_prompt)
            print("========================================")

            async for chunk in stream_generate(system_prompt, api_key, base_url, model_name):
                if await request.is_disconnected():
                    print("客户端连接断开，终止生成")
                    break

                full_text += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"

            # Phase 5: Commit (写后提取与沉淀) — 💡【记忆融合引擎】状态机覆盖更新
            yield f"data: {json.dumps({'type': 'status', 'msg': '[沉淀] 正在炼化并沉淀新事实...', 'step': 'commit'})}\n\n"

            extracted_entities = await extract_new_facts(full_text, api_key, base_url, model_name)

            committed_results = []
            try:
                for item in extracted_entities:
                    entry_name = item.get("entry_name", "")
                    entity_type = item.get("type", "其他")
                    new_content = item.get("content", "")

                    # 💡 世界书特有：关联词条熔接 — 不改表结构，拼入 content
                    relations = item.get("relations", [])
                    if isinstance(relations, list) and len(relations) > 0:
                        relations_str = " | ".join(relations)
                        new_content = f"{new_content}\n\n[关联]: {relations_str}"

                    if not entry_name or not new_content:
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

                    # ── 查 Entity ──
                    result = await db.execute(
                        select(MemoryEntity).where(
                            MemoryEntity.book_id == req.book_id,
                            MemoryEntity.entry_name == entry_name
                        )
                    )
                    entity = result.scalar_one_or_none()

                    if entity is None:
                        # ── 新实体：直接创建 + 插入 is_active=1 词条 ──
                        entity = MemoryEntity(
                            book_id=req.book_id,
                            entry_name=entry_name,
                            type=entity_type,
                            triggers=triggers
                        )
                        db.add(entity)
                        await db.flush()

                        fact_embedding = await compute_embedding(new_content, api_key, base_url)
                        fact = MemoryFact(
                            entity_id=entity.id,
                            book_id=uuid.UUID(req.book_id),
                            chapter_marker=req.chapter_marker,
                            content=new_content,
                            embedding=fact_embedding if fact_embedding else None,
                            is_active=1  # 新词条直接活跃
                        )
                        db.add(fact)
                        await db.flush()

                        print(f"[记忆融合] 新实体「{entry_name}」: 直接创建 is_active=1 词条")
                    else:
                        # ── 已有实体：融合模式 ──
                        # 合并 triggers（去重）
                        existing_triggers = set(entity.triggers or [])
                        new_triggers = existing_triggers.union(set(triggers))
                        entity.triggers = list(new_triggers)

                        # 查找当前活跃的 is_active=1 词条
                        old_fact_result = await db.execute(
                            select(MemoryFact).where(
                                MemoryFact.entity_id == entity.id,
                                MemoryFact.is_active == 1
                            ).limit(1)
                        )
                        old_fact = old_fact_result.scalar_one_or_none()

                        if old_fact:
                            # 有旧词条 → 融合
                            merged_content = await consolidate_entity_profile(
                                old_fact.content, new_content, api_key, base_url, model_name
                            )
                            # 旧词条归档
                            old_fact.is_active = 0
                            print(f"[记忆融合] 实体「{entry_name}」: 旧词条(id={old_fact.id}) 已归档(is_active=0)")
                        else:
                            # 无旧词条（异常状态，如被压缩清空）→ 直接用新内容
                            merged_content = new_content
                            print(f"[记忆融合] 实体「{entry_name}」: 无活跃旧词条，直接使用新内容")

                        # 创建融合后的新词条（is_active=1）
                        fact_embedding = await compute_embedding(merged_content, api_key, base_url)
                        fact = MemoryFact(
                            entity_id=entity.id,
                            book_id=uuid.UUID(req.book_id),
                            chapter_marker=req.chapter_marker,
                            content=merged_content,
                            embedding=fact_embedding if fact_embedding else None,
                            is_active=1  # 新词条成为活跃词条
                        )
                        db.add(fact)
                        await db.flush()

                    committed_results.append({
                        "entry_name": entry_name,
                        "type": entity_type,
                        "content": new_content,
                        "triggers": triggers
                    })

                # 唯一一次 commit，保证原子性
                await db.commit()

            except Exception as e:
                await db.rollback()
                print(f"数据持久化失败: {e}")

            yield f"data: {json.dumps({'type': 'commit_done', 'new_entities': committed_results})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"

        except Exception as e:
            import traceback
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'msg': _translate_llm_error(e)})}\n\n"

        finally:
            # 💡【钛合金钢板-第二根】SSE 断连抢救：即使客户端断开，半成品正文落库为草稿
            if full_text and len(full_text) > 50:
                try:
                    # 检查是否已有该章节（避免重复覆盖）
                    existing = await db.execute(
                        select(StoryChapter).where(
                            StoryChapter.book_id == uuid.UUID(req.book_id),
                            StoryChapter.chapter_marker == req.chapter_marker
                        ).limit(1)
                    )
                    if existing.scalar_one_or_none() is None:
                        draft_chapter = StoryChapter(
                            book_id=uuid.UUID(req.book_id),
                            volume_number=0,  # volume=0 标记为草稿
                            chapter_marker=req.chapter_marker,
                            title=f"第{req.chapter_marker}章（断线草稿）",
                            content=full_text
                        )
                        db.add(draft_chapter)
                        await db.commit()
                        print(f"[断连抢救] 第{req.chapter_marker}章半成品已落库为草稿 ({len(full_text)} chars)")
                except Exception as salvage_err:
                    await db.rollback()
                    print(f"[断连抢救] 草稿落库失败: {salvage_err}")

    return StreamingResponse(event_generator(), media_type="text/event-stream")


class SuggestRequest(BaseModel):
    book_id: str = ""
    recent_context: str


@router.post("/suggest")
async def get_plot_suggestions(req: SuggestRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """前端主动索要剧情建议的 API"""
    api_key = request.headers.get("X-LLM-API-Key")
    base_url = request.headers.get("X-LLM-Base-URL")
    model_name = request.headers.get("X-LLM-Model")

    # 💡 公共函数：熔接全书创意 + 大纲路线（DRY）
    enriched_context = req.recent_context
    if req.book_id:
        ctx = await get_book_global_context(req.book_id, db)
        if ctx["pitch_block"] or ctx["outline_block"]:
            enriched_context = f"{ctx['pitch_block']}{ctx['outline_block']}【最近剧情】\n{req.recent_context}"

    suggestions = await suggest_plot_directions(enriched_context, api_key, base_url, model_name)
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

    # 💡 公共函数：熔接全书创意 + 大纲路线（DRY）
    ctx = await get_book_global_context(req.book_id, db)
    pitch_block = ctx["pitch_block"]
    outline_block = ctx["outline_block"]

    system_prompt = f"""
语言：中文。你必须使用中文回答。正文内容必须为中文。

你是一个客观的文本修订引擎。用户要求对【第 {req.chapter_marker} 章】进行重写或润色。
【修稿指令】：{req.instruction}
{pitch_block}{outline_block}
【上下文约束锚点】：
前一章结尾：{req.prev_context[-800:] if req.prev_context else '无（这是开局）'}
当前章原稿：{req.current_content}
后一章开头：{req.next_context[:800] if req.next_context else '无（这是最新章）'}

【执行法则】：
1. 严格执行用户的修稿指令。如果是局部润色，请保留未提及修改的精彩原文；如果是重写，请放开手脚。
2. 必须保证与【前一章结尾】和【后一章开头】的剧情、情绪衔接天衣无缝。
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
                        book_id=uuid.UUID(req.book_id),
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
