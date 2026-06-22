# 青羽·织梦宇宙 — 架构文档

> 最后更新：2026-06-22（v4 — 记忆融合引擎 + 阶段锁定 + 实体消歧）

---

## 一、系统分层

```
┌─────────────────────────────────────────────────────────────┐
│  前端层 (Frontend)                                           │
│  Vue 3 + Vite + Pinia + Tailwind CSS                        │
│  views/       — 页面级组件（TheLibrary, PitchRoom, ...）      │
│  components/  — 可复用组件（EditorPanel, MemoryPanel, ...）   │
│  stores/      — Pinia 状态管理（storyStore, settingsStore）   │
│  api/         — API 调用封装（stream.js, memory.js）          │
├─────────────────────────────────────────────────────────────┤
│  HTTP / SSE                                                  │
├─────────────────────────────────────────────────────────────┤
│  后端层 (Backend)                                            │
│  FastAPI + SQLAlchemy async + Pydantic                      │
│  routers/     — API 路由（books, stream, memory, chat, ...）  │
│  models/      — SQLAlchemy ORM 模型                          │
│  schemas/     — Pydantic 请求/响应模型                        │
│  app/ 根目录  — 核心逻辑（llm_client, prompt_engine, ...）    │
├─────────────────────────────────────────────────────────────┤
│  AI 引擎层 (LLM)                                             │
│  OpenAI-compatible API（DeepSeek / 中转站）                   │
│  llm_client.py — 统一 LLM 调用入口（含 Embedding API）        │
│  prompt_engine.py — Prompt 模板组装 + Token 截断             │
├─────────────────────────────────────────────────────────────┤
│  数据层 (Database)                                           │
│  PostgreSQL 16 + pgvector                                    │
│  7 张业务表 + 向量检索（全部物理 FK CASCADE）                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、目录结构

```
rag-memory-system/
├── docker-compose.yml          # PostgreSQL + pgvector 容器
├── ARCHITECTURE.md             # 本文档
├── backend/
│   ├── requirements.txt        # 依赖（含 tiktoken）
│   ├── alembic/                # 数据库迁移（001~004）
│   │   └── versions/
│   └── app/
│       ├── __init__.py
│       ├── main.py             # FastAPI 入口 + CORS + lifespan
│       ├── config.py           # 配置（Settings）
│       ├── database.py         # 异步引擎 + session 工厂
│       ├── llm_client.py       # LLM 调用（流式/非流式 + Embedding API + 记忆融合引擎）
│       ├── prompt_engine.py    # Prompt 模板 + Token 截断（tiktoken）
│       ├── memory_compactor.py # 记忆压缩（后台任务，阈值 30 条）
│       ├── orchestrator.py     # 编排逻辑（旧，部分废弃）
│       ├── models/             # SQLAlchemy ORM（全部物理 FK CASCADE）
│       │   ├── __init__.py
│       │   ├── book.py         # books 表
│       │   ├── pitch.py        # story_pitches 表
│       │   ├── outline.py      # story_outline_nodes 表
│       │   ├── chapter.py      # story_chapters 表
│       │   ├── chat.py         # story_chat_messages 表
│       │   ├── entity.py       # memory_entities 表
│       │   ├── fact.py         # memory_facts 表（含 embedding 向量列）
│       │   └── apiconfig.py    # API 配置持久化
│       ├── schemas/            # Pydantic 模型
│       │   ├── __init__.py
│       │   ├── pitch.py
│       │   ├── outline.py
│       │   ├── fetch.py        # FetchRequest（含 query_text）
│       │   ├── commit.py
│       │   └── override.py
│       └── routers/            # API 路由
│           ├── __init__.py
│           ├── books.py        # 书籍 CRUD + 灵感 + 大纲
│           ├── stream.py       # SSE 生成 + 修订（含断连抢救）
│           ├── pitch.py        # Pitch 独立 CRUD
│           ├── outline.py      # Outline 独立 CRUD
│           ├── chapters.py     # 章节持久化
│           ├── chat.py         # 聊天记录
│           ├── memory.py       # 记忆检索/提交/重塑（RAG v2 混合检索）
│           ├── ui.py           # UI 数据查询
│           └── settings.py     # API 配置
└── frontend/
    ├── index.html
    ├── vite.config.js
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── package.json
    └── src/
        ├── main.js
        ├── App.vue
        ├── style.css
        ├── api/
        │   ├── stream.js       # SSE 流式请求
        │   └── memory.js       # 记忆 API
        ├── stores/
        │   ├── storyStore.js   # 核心状态（书/灵感/大纲/章节）
        │   ├── settingsStore.js# 引擎配置
        │   ├── memoryStore.js  # 记忆面板状态
        │   ├── memory.js       # ⚠️ 废弃，待清理
        │   ├── editor.js       # ⚠️ 废弃，待清理
        │   └── storyFlow.js    # ⚠️ 废弃，待清理
        ├── views/
        │   ├── TheLibrary.vue      # 书架大厅
        │   ├── PitchRoom.vue       # 灵感裂变室
        │   ├── OutlineForge.vue    # 大纲锻造
        │   └── IDEWorkspace.vue    # 共创 IDE（主工作区）
        └── components/
            ├── SettingsModal.vue    # 引擎配置弹窗
            ├── EditorPanel.vue     # ⚠️ 编辑器面板（旧，部分废弃）
            ├── MemoryPanel.vue     # 记忆面板
            ├── MemoryExplorer.vue  # 记忆资源管理器
            ├── OutlineNavigator.vue# 大纲导航
            ├── FactTooltip.vue     # 事实气泡
            └── TimeSlider.vue      # 时间轴滑块
```

---

## 三、数据模型

### 3.1 ER 关系

```
books (1) ─────< story_pitches (N)      # 一本书有多个灵感（FK CASCADE）
books (1) ─────< memory_entities (N)    # 一本书有多个记忆实体（FK CASCADE）
books (1) ─────< memory_facts (N)       # 一本书有多个记忆事实（FK CASCADE）
books (1) ─────< story_chapters (N)     # 一本书有多个章节（FK CASCADE）
books (1) ─────< story_chat_messages (N)# 一本书有多个聊天记录（FK CASCADE）

story_pitches (1) ─────< story_outline_nodes (N)  # 一个灵感有多个大纲节点（FK CASCADE）
```

### 3.2 核心表结构

| 表 | 关键字段 | 用途 |
|----|---------|------|
| [`books`](rag-memory-system/backend/app/models/book.py) | `id`, `title`, `summary`, `custom_prompt`, `created_at` | 书籍元数据 + 文风约束 |
| [`story_pitches`](rag-memory-system/backend/app/models/pitch.py) | `id`, `book_id`(nullable), `seed_text`, `variant_of`, `title`, `summary`, `tone`, `created_at` | 灵感卡片 |
| [`story_outline_nodes`](rag-memory-system/backend/app/models/outline.py) | `id`, `pitch_id`, `volume_number`, `title`, `core_goal`, `emotion_curve`, `location`, `estimated_chapters`, `sort_order`, `status` | 大纲卷节点 |
| [`story_chapters`](rag-memory-system/backend/app/models/chapter.py) | `id`, `book_id`, `volume_number`, `chapter_marker`, `title`, `content`, `created_at` | 已生成的章节正文 |
| [`story_chat_messages`](rag-memory-system/backend/app/models/chat.py) | `id`, `book_id`, `role`, `type`, `volume_number`, `content`, `created_at` | 聊天记录（含分割线） |
| [`memory_entities`](rag-memory-system/backend/app/models/entity.py) | `id`, `book_id`, `entry_name`, `type`, `triggers`(ARRAY) | 记忆实体（人物/地点/物品等） |
| [`memory_facts`](rag-memory-system/backend/app/models/fact.py) | `id`, `entity_id`, `book_id`, `chapter_marker`, `content`, `embedding`(vector), `is_active`(Integer: 0/1) | 记忆事实（带向量用于 RAG） |

---

## 四、API 路由

### 4.1 书籍管理 — [`routers/books.py`](rag-memory-system/backend/app/routers/books.py)

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/books/` | 列出所有书籍 |
| GET | `/api/books/{book_id}` | 获取单本书详情（含文风约束） |
| POST | `/api/books/` | 创建书籍（回写 pitch.book_id） |
| PUT | `/api/books/{book_id}/custom_prompt` | 更新文风约束 |
| DELETE | `/api/books/{book_id}` | 删除书籍（FK CASCADE 自动清理子表） |
| DELETE | `/api/books/clean/all` | 清空全部数据（调试用） |

### 4.2 灵感 & 大纲 — [`routers/books.py`](rag-memory-system/backend/app/routers/books.py)

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/api/books/pitch` | LLM 生成灵感（始终持久化） |
| POST | `/api/books/outline` | LLM 生成大纲（需 pitch_id） |

### 4.3 独立 CRUD — [`routers/pitch.py`](rag-memory-system/backend/app/routers/pitch.py) / [`routers/outline.py`](rag-memory-system/backend/app/routers/outline.py)

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/api/pitch/create` | 创建 Pitch |
| GET | `/api/pitch/list` | 列出所有 Pitch |
| PUT | `/api/pitch/select` | 选中 Pitch |
| POST | `/api/outline/create` | 创建大纲节点 |
| GET | `/api/outline/list/{pitch_id}` | 按 Pitch 列出大纲 |
| GET | `/api/outline/by-book/{book_id}` | 按 Book 列出大纲 |
| PUT | `/api/outline/update/{node_id}` | 更新大纲节点 |

### 4.4 流式生成 — [`routers/stream.py`](rag-memory-system/backend/app/routers/stream.py)

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/api/stream/generate` | SSE 流式生成章节正文 |
| POST | `/api/stream/revise` | SSE 流式修订章节 |
| POST | `/api/stream/suggest` | 获取剧情建议 |

### 4.5 记忆系统 — [`routers/memory.py`](rag-memory-system/backend/app/routers/memory.py)

| 方法 | 路径 | 用途 |
|------|------|------|
| POST | `/api/memory/fetch` | RAG 检索记忆 |
| POST | `/api/memory/commit` | 提交新记忆 |
| PUT | `/api/memory/override` | 覆写事实 |
| POST | `/api/memory/{book_id}/rebuild/{chapter_number}` | 章节重写后重塑记忆 |

### 4.6 其他

| 方法 | 路径 | 文件 | 用途 |
|------|------|------|------|
| POST | `/api/chapters/save` | [`chapters.py`](rag-memory-system/backend/app/routers/chapters.py) | 保存章节 |
| POST | `/api/chat/save` | [`chat.py`](rag-memory-system/backend/app/routers/chat.py) | 保存聊天记录 |
| GET | `/api/ui/entities` | [`ui.py`](rag-memory-system/backend/app/routers/ui.py) | 查询实体列表 |
| GET | `/api/ui/facts` | [`ui.py`](rag-memory-system/backend/app/routers/ui.py) | 查询事实列表 |
| GET | `/api/ui/chapters` | [`ui.py`](rag-memory-system/backend/app/routers/ui.py) | 查询章节列表 |
| GET/PUT | `/api/settings/` | [`settings.py`](rag-memory-system/backend/app/routers/settings.py) | API 配置管理 |

---

## 五、核心流程

### 5.1 灵感 → 大纲 → 写作（三阶段）

```
PitchRoom          OutlineForge          IDEWorkspace
─────────          ────────────          ───────────
输入种子文本
  → POST /pitch
  → LLM 返回 3 个灵感
  → 展示卡片列表
       ── 用户选择一个 ──→
                          生成大纲
                            → POST /outline
                            → LLM 返回多卷大纲
                            → 展示卷列表
                                 ── 用户点"进入IDE" ──→
                                                       创建 Book（回写 pitch_id）
                                                       加载大纲 + 章节 + 聊天记录
                                                       自动生成第一章
```

### 5.2 SSE 生成流程

```
POST /api/stream/generate
  │
  ├─ [fetch]    RAG v2 混合检索（3 路径）
  │   ├─ Path A: query_text → Embedding API → cosine_distance（Top 15）
  │   ├─ Path B: extracted_triggers → triggers && 数组重叠（legacy 回退）
  │   └─ Path C: 空查询 → 全量返回（graceful degradation）
  │
  ├─ [inject]   组装 system_prompt
  │   ├─ header（固定指令 + 🔒 阶段锁定：进度坐标 + 视界锁定 + 节奏纪律）
  │   ├─ pitch_section（核心创意）
  │   ├─ outline_section（大纲路线 + [<<< 当前所在卷，绝对聚焦于此 >>>] 注意力锚点）
  │   ├─ facts_section（RAG 记忆事实）
  │   ├─ missing_section（新造物授权）
  │   ├─ scene_section（当前场景 — 最高优先级）
  │   └─ Token 截断：tiktoken 计数 → 4 阶段裁剪（阈值 6000）
  │       ├─ 第一刀：RAG facts Top 15 → Top 5
  │       ├─ 第二刀：Outline 截断到 2000 tokens
  │       ├─ 第三刀：Pitch 截断到 1000 tokens
  │       └─ 第四刀：RAG facts 终极砍到 Top 3
  │       （custom_prompt + current_scene 永不裁剪）
  │
  ├─ [generate] LLM 流式返回文本 chunks → SSE 推送到前端
  │
  ├─ [commit]   💡 记忆融合引擎 — 提取新实体/事实 → 状态机覆盖更新
  │   ├─ LLM 提取新实体列表（entry_name + type + triggers + content）
  │   ├─ 对每个实体：
  │   │   ├─ 新实体 → 创建 MemoryEntity + MemoryFact(is_active=1)
  │   │   └─ 已有实体 → 查询当前 is_active=1 事实
  │   │       ├─ 存在 → 调用 consolidate_entity_profile() 融合旧设定+新情报
  │   │       │   ├─ 旧事实 is_active=0（归档）
  │   │       │   └─ 创建新事实 is_active=1 + embedding
  │   │       └─ 不存在 → 直接创建新事实 is_active=1
  │   ├─ 别名合并：新 triggers 去重合并到 entity.triggers
  │   ├─ 12 字符幻觉防护：content < 12 字符则跳过
  │   └─ 为每个新 MemoryFact 调用 Embedding API 生成向量
  │
  ├─ [done]     前端保存章节 → 2s 后刷新记忆面板
  │
  └─ [断连抢救] 客户端断开时 finally 块自动保存半成品为草稿（volume=0）
```

### 5.3 修订流程

```
POST /api/stream/revise
  │
  ├─ 获取目标章节 + 前后文
  ├─ LLM 重写章节内容 → SSE 推送
  ├─ 用户预览修订结果
  └─ 用户确认 → 覆盖章节 + POST /api/memory/{id}/rebuild 重塑记忆
```

---

## 六、技术选型与关键决策

| 维度 | 选型 | 理由 |
|------|------|------|
| 前端框架 | Vue 3 + Vite | 轻量、响应式、组合式 API |
| 状态管理 | Pinia | 官方推荐，TypeScript 友好 |
| 样式 | Tailwind CSS | 原子化 CSS，快速迭代 UI |
| 后端框架 | FastAPI | 异步原生、自动 OpenAPI、Pydantic 校验 |
| ORM | SQLAlchemy async | 异步数据库操作，避免阻塞事件循环 |
| 数据库 | PostgreSQL 16 + pgvector | 向量检索（RAG 记忆召回） |
| LLM 协议 | OpenAI-compatible API | 兼容 DeepSeek / 中转站 / 任意 OpenAI 代理 |
| 流式传输 | Server-Sent Events | 单向实时推送，比 WebSocket 轻量 |
| 容器化 | Docker Compose | 仅数据库容器化，后端/前端本地运行 |

### 关键架构决策

1. **Pitch 先于 Book**：灵感可以在没有 Book 时独立存在（`book_id` 可为 NULL），创建 Book 后回写。这允许用户在确定书名之前先探索创意方向。

2. **SSE 而非 WebSocket**：生成是单向流（服务器→客户端），不需要双向通信。SSE 基于 HTTP，无需额外协议握手，与 FastAPI 的 `StreamingResponse` 天然契合。

3. **记忆 RAG v2（混合检索）**：废除旧版正则提取触发词 + 数组重叠匹配。新版流程：
   - 前端直接传入用户输入的原始文本 `query_text`
   - 后端调用 Embedding API 将其转为向量
   - 使用 pgvector `cosine_distance` 进行语义相似度搜索（Top 15）
   - 写入新记忆时同步生成 embedding 存入数据库
   - Embedding API 失败时自动降级为全量返回（graceful degradation）

4. **文风约束随身带**：`custom_prompt` 存储在 `books` 表，每次生成请求都透传给 LLM，确保整本书风格一致。

5. **记忆压缩阈值 30 条**：`memory_compactor.py` 中 `COMPACTION_THRESHOLD = 30`，长篇小说重要角色 30 条设定以内不触发压缩，避免过早丢失细节。

6. **🧠 记忆融合引擎（Memory Consolidation）**：废除 Append-Only 逐章追加模式，改为 **One Entity = One Active Profile** 状态机。每个实体在任何时刻只有 1 条 `is_active=1` 的事实。新章节产生新情报时：
   - 查询该实体当前 `is_active=1` 的旧设定卡
   - 调用 LLM `consolidate_entity_profile()` 将旧设定 + 新情报融合为一份精炼词条
   - 旧事实 `is_active=0`（归档），新事实 `is_active=1` + embedding
   - 这避免了角色词条随章节数线性膨胀，将每个实体的活跃记忆控制在 LLM 可消化的范围内。

7. **🚫 实体消歧（Entity Fragmentation Fix）**：LLM 提取新实体时，System Prompt 中加入：
   - **代词封杀**：禁止将"我/你/他/她/它/自己/这/那"作为 `entry_name`
   - **强制别名合并**：同一实体的不同称呼（如"林墨/哥哥/林哥哥"）必须合并为同一条记录，triggers 数组收集所有别名
   - 这解决了 LLM 将同一角色的不同称呼识别为多个独立实体的"实体分裂"问题。

8. **🔒 阶段锁定架构（Stage-Lock）**：防止 LLM 跨越当前卷宗边界提前撰写后续剧情。实现方式：
   - `StreamGenRequest` 携带 `current_volume` 字段
   - Prompt header 注入【当前进度坐标】和【视界锁定与节奏纪律】3 条铁律
   - Outline 章节中当前卷标题后追加 `[<<< 当前所在卷，绝对聚焦于此 >>>]` 注意力锚点
   - 这解决了 LLM"剧情早泄"（Plot Rushing）问题，确保叙事节奏可控。

### 钛合金钢板（层间契约修复）

> 以下三项修复于 2026-06-22 统一实施，解决架构师评审中发现的 3 根"软肋"。

#### 第一根：物理外键 ON DELETE CASCADE

**问题**：ORM 模型定义了 `ForeignKey("books.id", ondelete="CASCADE")`，但 Alembic 迁移 `002_add_foreign_key_cascades.py` 从未执行，数据库中 3 张子表无物理 FK 约束。删除 Book 时，关联的 `story_chapters`、`story_chat_messages`、`story_outline_nodes` 成为孤儿数据。

**修复**：通过 `004_enforce_physical_fk_cascades.py` 迁移脚本（直接 SQL 执行）为以下 3 表添加物理 FK：

```sql
ALTER TABLE story_chapters ADD CONSTRAINT fk_chapter_book FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE;
ALTER TABLE story_chat_messages ADD CONSTRAINT fk_chat_book FOREIGN KEY (book_id) REFERENCES books(id) ON DELETE CASCADE;
ALTER TABLE story_outline_nodes ADD CONSTRAINT fk_outline_pitch FOREIGN KEY (pitch_id) REFERENCES story_pitches(id) ON DELETE CASCADE;
```

**效果**：删除 Book 时，PostgreSQL 自动级联删除所有关联章节、聊天记录；删除 Pitch 时自动级联删除所有大纲节点。应用层不再需要手动逐表清理。

#### 第二根：SSE 断连抢救

**问题**：客户端在网络抖动或用户关闭页面时断开 SSE 连接，`event_generator()` 协程被取消，已生成但尚未保存的半成品正文直接蒸发。

**修复**：在 [`stream.py`](rag-memory-system/backend/app/routers/stream.py) 的 `event_generator()` 中添加 `finally` 块：

```python
finally:
    if full_text and len(full_text) > 50:
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
```

**设计要点**：
- `volume_number=0` 作为草稿标记，前端可据此区分正式章节与断线草稿
- 先查重再写入，避免重复保存
- 落库失败仅 rollback 不抛异常，不影响主流程

#### 第三根：Token 截断

**问题**：当 Pitch 较长 + 完整多卷 Outline + Top 15 RAG 事实同时注入 Prompt 时，总 token 数可能超过 LLM 上下文窗口（如 DeepSeek 的 8K/32K 限制），导致 HTTP 400 错误。

**修复**：在 [`prompt_engine.py`](rag-memory-system/backend/app/prompt_engine.py) 中引入 `tiktoken` 计数 + 4 阶段动态裁剪：

```python
MAX_PROMPT_TOKENS = 6000  # 安全阈值，低于常见 LLM 上下文窗口
# 优先级：custom_prompt > current_scene > pitch > outline > rag_facts
```

**裁剪策略**：
| 阶段 | 操作 | 条件 |
|------|------|------|
| 第一刀 | RAG facts 从 Top 15 砍到 Top 5 | token_count > 6000 |
| 第二刀 | Outline 截断到 2000 tokens | 仍超阈值 |
| 第三刀 | Pitch 截断到 1000 tokens | 仍超阈值 |
| 第四刀 | RAG facts 终极砍到 Top 3 | 仍超阈值 |

**设计要点**：
- `tiktoken` 初始化失败时静默降级（try/except），不阻塞生成
- 裁剪顺序按优先级从低到高：先砍 RAG facts 数量（信息密度最低），再砍 outline 早期卷，最后砍 pitch
- `current_scene` 和 `custom_prompt` 永不裁剪（最高优先级）

---

## 七、数据库外键约束现状

| 父表 | 子表 | 外键约束 | 级联删除 |
|------|------|---------|---------|
| `books` | `story_pitches` | ✅ `book_id` → `books.id` | ✅ CASCADE |
| `books` | `memory_entities` | ✅ `book_id` → `books.id` | ✅ CASCADE |
| `books` | `memory_facts` | ✅ `book_id` → `books.id` | ✅ CASCADE |
| `books` | `story_chapters` | ✅ `fk_chapter_book`（v3 新增） | ✅ CASCADE |
| `books` | `story_chat_messages` | ✅ `fk_chat_book`（v3 新增） | ✅ CASCADE |
| `story_pitches` | `story_outline_nodes` | ✅ `fk_outline_pitch`（v3 新增） | ✅ CASCADE |

---

## 八、修复记录

> 见 [`CHANGELOG.md`](rag-memory-system/CHANGELOG.md)（如存在）或 Git 提交历史。
