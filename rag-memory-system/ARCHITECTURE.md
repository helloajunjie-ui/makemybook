# 核心架构蓝图：基于事件溯源的小说创作记忆外挂系统

**版本**: 3.4 | **架构师**: 青羽 | **定位**: 独立外挂认知中间件

---

## 1. 核心产品定义与哲学

### 认知解耦（Cognitive Decoupling）
彻底分离"逻辑推演（主AI）"与"事实存储（记忆外挂）"。主AI作为CPU负责渲染剧情，记忆系统作为内存+硬盘提供绝对精准的世界观状态。

### 时间序列状态机（Time-Series State Machine）
小说的本质是随时间流逝的世界状态变更。系统抛弃传统的 CRUD 修改逻辑，采用**事件溯源（Event Sourcing）**思想。每一次设定的变更都是一次带有 `chapter_marker`（章节时间戳）的事实追加（Append-only）。

### 防穿透原则
严格基于时间轴隔离数据，确保第 N 章的推演绝对无法获取 N+1 章的设定，彻底杜绝"预知未来"的逻辑崩塌。

### 多租户物理隔离（Tenant Isolation）
以 `Book`（书籍/项目）作为最高层级容器。所有实体、事实、大纲数据通过 `book_id` 外键实现物理级隔离，杜绝跨书串库幻觉。

### 漏斗收敛（Funnel Convergence）
创作流程从发散到收敛：**书架大厅（TheLibrary）→ 灵感裂变（PitchRoom）→ 大纲锻造（OutlineForge）→ 三栏IDE（IDEWorkspace）**。四个阶段由 `storyStore.currentPhase` 单一状态源驱动，`<Transition>` 动画平滑切换。

---

## 2. Agentic RAG 工作流：五步闭环（ReAct 模式）

```
Phase 1: 前置思考与提取 (Planning)
  └─ 主AI阅读前文，输出JSON格式的"剧情推演思路"及"即将用到的词条清单(Triggers)"

Phase 2: 预测性记忆召回 (Fetch)
  └─ 系统拦截AI的词条清单，携带当前 chapter_marker + book_id，调用记忆外挂的 /fetch 接口
  └─ 返回匹配词条的原子化事实 + 明确标注"库中未有的新设定"

Phase 3: 上下文动态注入 (Context Injection)
  └─ 系统将召回的设定事实，组装为强约束性的 System Prompt（上帝视角的设定字典）

Phase 4: 剧情渲染生成 (Generation)
  └─ 主AI带着注入的设定约束，通过 AsyncOpenAI 流式生成（temperature=0.8），逐 chunk 推送给前端打字机渲染

Phase 5: 记忆沉淀归档 (Commit)
  └─ 利用 JSON Mode（temperature=0.1）扫描新生成的正文，提取出新产生的事实碎片
  └─ 调用外挂的 /commit 接口，打上时间戳存入数据库
  └─ 后台触发 Memory GC：若实体事实超过 10 条，异步调用 LLM 炼化压缩
```

---

## 3. 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 数据库 | PostgreSQL 15+ + pgvector | 单库解决实体关联 + JSONB + 时间轴截断 + GIN倒排 + 向量索引 |
| 服务端 | Python 3.11+ / FastAPI | 异步高并发，SQLAlchemy 2.0 async + Pydantic v2 |
| LLM 客户端 | AsyncOpenAI (openai 1.6.1+) | 支持 DeepSeek / 任意兼容 OpenAI SDK 的 relay 中转站 |
| 客户端 | Vue 3 (Composition API) + Vite + Pinia + Tailwind CSS v4 | 四阶段漏斗布局，零第三方UI库 |
| 样式引擎 | Tailwind CSS v4 + PostCSS + Autoprefixer | 原子化 CSS，`@import "tailwindcss"` 入口 |
| 流式传输 | SSE (Server-Sent Events) | 基于原生 HTTP 的单向高频文本流，轻量无心跳 |
| 容器化 | Docker Compose | ankane/pgvector 一键拉起 |

---

## 4. 数据模型

### 书籍表（Book）— 多租户容器

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| title | VARCHAR(100) | 书名，带索引 |
| summary | TEXT | 大纲概要 |
| created_at | TIMESTAMPTZ | 创建时间 |

### 实体表（MemoryEntity）— 世界观词条字典

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| book_id | UUID FK | **物理隔离墙**，关联 books.id CASCADE |
| entry_name | VARCHAR(255) | 词条名（如：张三） |
| type | VARCHAR(50) | 类型（人物/地点/物品等），带索引 |
| triggers | ARRAY[VARCHAR] | 触发词数组（如：["张三","三哥"]），GIN 索引 |
| created_at | TIMESTAMPTZ | 创建时间 |
| updated_at | TIMESTAMPTZ | 更新时间 |

**唯一约束**：`(book_id, entry_name)` 联合唯一，同一本书内词条名不重复。

### 事实表（MemoryFact）— 时间序列化的原子记忆

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| entity_id | UUID FK | 关联实体，CASCADE 删除 |
| chapter_marker | INTEGER | **核心**：所属章节时间戳，带索引 |
| content | TEXT | 原子化短句（如："右腿被打断"） |
| embedding | VECTOR(1536) | 向量表示，用于消歧义和语义兜底 |
| is_active | INTEGER | 软删除标记（1=活跃，0=失效） |
| created_at | TIMESTAMPTZ | 创建时间 |

---

## 5. 核心 API 契约

### 5.1 预测性召回 `POST /api/memory/fetch`

**用途**：写前获取设定字典

**Request**:
```json
{
  "book_id": "uuid-xxx",
  "current_chapter": 5,
  "extracted_triggers": ["张三", "三哥", "青云城"]
}
```

**Response**:
```json
{
  "status": "success",
  "data": {
    "found_entries": [
      {
        "entry_name": "张三",
        "type": "人物",
        "facts": [
          { "content": "右腿被打断", "chapter_marker": 3 },
          { "content": "拜入青云宗门", "chapter_marker": 4 }
        ]
      }
    ],
    "missing_entries": ["青云城"]
  }
}
```

**查询逻辑**（[`memory.py`](backend/app/routers/memory.py:16)）：
- 单次 SQL 连表查询：`text()` 原生 SQL + `JOIN`
- `me.book_id = CAST(:book_id AS uuid)` — **物理隔离锁死**
- `me.triggers && :triggers` — PostgreSQL 原生 `&&` 数组重叠运算符，GIN 倒排索引极速命中
- `mf.chapter_marker <= :chapter` — SQL 层面硬性切断未来记忆
- `mf.is_active = true` — 屏蔽已失效事实
- `set(extracted) - found_triggers_set` — 集合运算计算 missing_entries

### 5.2 记忆沉淀 `POST /api/memory/commit`

**用途**：写后追加新事实

**Request**:
```json
{
  "book_id": "uuid-xxx",
  "chapter_marker": 6,
  "entry_name": "青云城",
  "triggers": ["青云城", "青云"],
  "content": "位于大陆东部的修仙者聚集地",
  "type": "地点"
}
```

**行为**：幂等且追加。通过 `book_id + entry_name` 联合查询，不存在则自动创建实体。实体创建 + 事实追加在同一个 `db.commit()` 事务中完成。

### 5.3 上帝之手 `PUT /api/memory/override`

**用途**：作者人工纠偏

**Request**:
```json
{
  "book_id": "uuid-xxx",
  "fact_id": "uuid-xxx",
  "content": "修正后的事实内容",
  "is_active": 0
}
```

**行为**：直接修改指定 fact 的 content 或标记 is_active=0 软删除。

### 5.4 SSE 流式生成 `POST /api/stream/generate`

**用途**：五步闭环的流式推演接口，基于 SSE 协议，后端使用真实 AsyncOpenAI 客户端

**Request**:
```json
{
  "book_id": "uuid-xxx",
  "chapter_marker": 1,
  "plot_context": "张三冷笑一声，拔出了那把断剑...",
  "extracted_triggers": ["张三", "血魔剑"]
}
```

**Response**（`text/event-stream`）:

```
data: {"type": "status", "msg": "🔍 正在检索世界线记忆...", "step": "fetch"}
data: {"type": "status", "msg": "命中设定: 2个 | 允许新造物: 1个", "found": [...], "missing": [...]}
data: {"type": "status", "msg": "🧱 组装上帝视角法则...", "step": "inject"}
data: {"type": "status", "msg": "✍️ 引擎推演中...", "step": "generate"}
data: {"type": "chunk", "text": "张三"}
data: {"type": "chunk", "text": "冷笑一声..."}
data: {"type": "commit_done", "new_entities": [{"entry_name": "血魔剑", "type": "道具", "content": "..."}]}
data: {"type": "done"}
```

**事件类型**：

| type | 说明 |
|------|------|
| `status` | 状态机流转，驱动前端骨架屏 |
| `chunk` | 打字机文本块，逐块上屏 |
| `commit_done` | 写后提取结果，触发左栏新词条闪烁 |
| `done` | 生成完成，归档到对话历史 |
| `error` | 异常穿透，前端停止 Loading |

**后端执行流程**（[`stream.py`](backend/app/routers/stream.py:28)）：

```
Phase 1&2 (Fetch): predict_fetch_memory(book_id=req.book_id, ...) — 真实数据库查询（物理隔离）
Phase 3 (Inject):  build_injection_prompt() — 组装 System Prompt
Phase 4 (Generate): stream_generate(system_prompt) — 真实 AsyncOpenAI 流式调用（temperature=0.8）
Phase 5 (Commit):  extract_new_facts(full_text) — JSON Mode 提取（temperature=0.1）
                   → find-or-create MemoryEntity(book_id=req.book_id) → append MemoryFact → db.commit()
                   → background_tasks: run_compaction_task() — 异步 Memory GC
```

**防御性设计**：
- `request.is_disconnected()` — 客户端断开立即终止生成，节省 Token
- 强类型 Event 区分 — 前端精确控制骨架屏状态
- 异常穿透 — 后端崩溃包装为 `{"type": "error"}` 吐给前端

### 5.5 命运幽灵卡片 `POST /api/stream/suggest`

**用途**：极速推演接口，根据近期上下文给出 3 个差异化剧情走向建议

**Request**:
```json
{
  "recent_context": "张三冷笑一声，拔出了那把断剑..."
}
```

**Response**:
```json
{
  "status": "success",
  "data": ["遭遇血魔宗突袭", "发现剑中的神秘剑灵", "李四突然叛变"]
}
```

**后端逻辑**（[`llm_client.py`](backend/app/llm_client.py:122)）：
- `suggest_plot_directions(recent_context)` — temperature=0.8，JSON Mode
- 每个方向不超过 30 字，必须差异化（遇袭 / 发现线索 / 情感爆发）

**前端交互**（[`IDEWorkspace.vue`](frontend/src/views/IDEWorkspace.vue)）：
- 输入框上方悬浮 ✨ 按钮 + 3 张幽灵卡片
- 点击 ✨ 触发 `fetchPlotSuggestions()` → 骨架屏加载 → 卡片渲染
- 点击卡片自动填入输入框（`useSuggestion()`），作者可微调后发送

### 5.6 书架管理 `GET/POST/DELETE /api/books/`

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/api/books/` | 获取书架列表（按创建时间倒序） |
| POST | `/api/books/` | 创建新书（title, summary） |
| DELETE | `/api/books/{book_id}` | 删除书籍及所有关联记忆数据（级联：MemoryFact → MemoryEntity → Book） |

**删除行为**（[`books.py`](backend/app/routers/books.py:89)）：
- 先查询 Book 是否存在，不存在返回 404
- 查询该 book_id 下所有 MemoryEntity.id
- 逐条删除关联的 MemoryFact
- 删除所有 MemoryEntity
- 最后删除 Book
- 单事务 `db.commit()` 原子提交

**前端交互**（[`TheLibrary.vue`](frontend/src/views/TheLibrary.vue:44)）：
- 每张书籍卡片 hover 时右上角显示 ✕ 删除按钮
- 点击弹出 `confirm()` 对话框确认删除
- 删除成功后 `storyStore.deleteBook()` 从 `bookshelf` 数组中移除该卡片

### 5.7 灵感裂变 `POST /api/books/pitch`

**用途**：根据种子文本裂变 3 个差异化灵感变体

**Request**:
```json
{
  "seed_text": "一个少年修仙的故事",
  "is_variant": false,
  "target_pitch": null
}
```

**Response**:
```json
{
  "status": "success",
  "data": [
    { "id": 1, "title": "...", "logline": "...", "showDetails": false },
    { "id": 2, "title": "...", "logline": "...", "showDetails": false },
    { "id": 3, "title": "...", "logline": "...", "showDetails": false }
  ]
}
```

**后端逻辑**（[`books.py`](backend/app/routers/books.py:53)）：
- 提取 `X-LLM-*` 头部透传 BYOK 配置
- 调用 `generate_pitches_from_llm()`（temperature=0.8）
- 若返回空列表，抛出 `HTTPException(502)` 携带中文错误描述

### 5.8 大纲生成 `POST /api/books/outline`

**用途**：根据选定的灵感裂变结果生成完整大纲骨架

**Request**:
```json
{
  "pitch": { "title": "...", "logline": "...", ... }
}
```

**Response**:
```json
{
  "status": "success",
  "data": {
    "outline_nodes": [
      { "volume": 1, "title": "觉醒篇", "desc": "...", "status": "active" },
      { "volume": 2, "title": "试炼篇", "desc": "...", "status": "pending" }
    ],
    "confirmed_settings": { "worldview": "...", "power_system": "..." }
  }
}
```

**后端逻辑**（[`books.py`](backend/app/routers/books.py:77)）：
- 提取 `X-LLM-*` 头部透传 BYOK 配置
- 调用 `generate_outline_from_llm()`（temperature=0.8）
- 若返回空 `outline_nodes`，抛出 `HTTPException(502)` 携带中文错误描述

### 5.9 时光溯源重塑 `POST /api/stream/revise`

**用途**：带上下文的章节重写与记忆重塑，支持指定改写范围

**Request**:
```json
{
  "book_id": "uuid-xxx",
  "chapter_marker": 5,
  "original_text": "原章节全文...",
  "revision_prompt": "让张三在结尾觉醒血脉之力",
  "extracted_triggers": ["张三", "血脉"]
}
```

**Response**（`text/event-stream`）:
```
data: {"type": "status", "msg": "🔍 正在检索世界线记忆...", "step": "fetch"}
data: {"type": "status", "msg": "🧱 组装上帝视角法则...", "step": "inject"}
data: {"type": "status", "msg": "✍️ 时光溯源重塑中...", "step": "revise"}
data: {"type": "chunk", "text": "改写后的文本..."}
data: {"type": "done"}
```

**后端逻辑**（[`stream.py`](backend/app/routers/stream.py:160)）：
- 调用 `predict_fetch_memory()` 获取当前章节前的所有设定
- 组装 System Prompt（原文 + 改写指令 + 设定字典）
- 调用 `stream_generate()` 流式输出改写结果
- 改写完成后自动执行记忆提取与归档（Phase 5 Commit）

---

## 6. 数据库索引策略

```sql
-- 书籍表
CREATE INDEX idx_book_title ON books (title);

-- 实体表
CREATE UNIQUE INDEX uix_book_entry ON memory_entities (book_id, entry_name);
CREATE INDEX idx_entity_book_id ON memory_entities (book_id);
CREATE INDEX idx_entity_type ON memory_entities (type);
CREATE INDEX idx_entity_triggers_gin ON memory_entities USING GIN (triggers);

-- 事实表
CREATE INDEX idx_fact_entity_id ON memory_facts (entity_id);
CREATE INDEX idx_fact_chapter ON memory_facts (chapter_marker);
CREATE INDEX idx_fact_entity_chapter ON memory_facts (entity_id, chapter_marker);
CREATE INDEX idx_fact_embedding ON memory_facts USING ivfflat (embedding vector_cosine_ops);
```

---

## 7. UI/UX 设计

### 四阶段漏斗收敛（Funnel Convergence）

创作流程从发散到收敛，四个阶段由 [`storyStore.currentPhase`](frontend/src/stores/storyStore.js:5) 驱动：

```
┌─────────────────────────────────────────────────────────────┐
│                   书架大厅 (TheLibrary)                       │
│  展示所有书籍卡片 → 点击进入 IDE / 新建进入 Pitch             │
│  右上角 "⚙️ 引擎配置" 按钮（BYOK 配置入口）                   │
├─────────────────────────────────────────────────────────────┤
│                   灵感裂变室 (PitchRoom)                      │
│  输入种子 → 裂变 3 个变体 → 选择骨架 → 进入大纲              │
├─────────────────────────────────────────────────────────────┤
│                   大纲锻造炉 (OutlineForge)                   │
│  编辑卷/章节点 → 衍生新篇章 → 进入 IDE                      │
├─────────────────────────────────────────────────────────────┤
│                   三栏创作 IDE (IDEWorkspace)                 │
│  左栏: 设定字典  │  中栏: 剧本渲染  │  右栏: 世界大纲        │
│  顶栏: "⚙️ 偏好设定" 按钮（BYOK 配置入口）                   │
└─────────────────────────────────────────────────────────────┘
```

### 三栏式 IDE 布局（[`IDEWorkspace.vue`](frontend/src/views/IDEWorkspace.vue)）

```
┌─────────────────────────────────────────────────────────────┐
│ 顶栏：青羽·织梦引擎 IDE  | 状态指示灯 | ⚙️ 偏好设定 | 导出剧本 │
├──────────┬──────────────────────────────────┬──────────────┤
│ 左栏     │ 中栏                             │ 右栏         │
│ 设定字典  │ 剧本渲染与共创区                   │ 世界大纲      │
│ (280px)  │ (1fr)                            │ (280px)      │
│          │                                   │              │
│ 人物     │ [状态机骨架屏]                      │ 第1卷：觉醒篇 │
│ 张三     │  🔍 检索世界线记忆 ✓               │ 第2卷：试炼篇 │
│ 李四     │  🧱 组装上帝视角法则 ✓              │ 第3卷：血魔乱 │
│          │  ✍️ 引擎推演中...                  │              │
│ 地点     │ [打字机流式文本]                    │              │
│ 青云城   │ 张三冷笑一声，拔出了那把断剑...      │              │
│          │                                   │              │
│          │ [对话历史]                         │              │
│          │                                   │              │
│          ├──────────────────────────────────┤              │
│          │ 输入框 [Ctrl+Enter 生成] [停止]    │              │
└──────────┴──────────────────────────────────┴──────────────┘
```

### 全局状态神经中枢（Pinia Stores）

| Store | 职责 | 关键状态 |
|-------|------|----------|
| [`memoryStore`](frontend/src/stores/memoryStore.js) | 左栏灵魂 — 记忆数据管理 | `entities`（按人物/地点/道具/事件分组）、`newlyAddedIds`（闪烁驱动）、`isLoading` |
| [`storyStore`](frontend/src/stores/storyStore.js) | 全流程灵魂 — 阶段路由 + 多书管理 + 剧情流转 | `currentPhase`（library/pitch/outline/ide）、`currentBookId`、`bookshelf[]`、`promptSeed`、`pitches[]`、`selectedPitch`、`currentChapter`、`currentVolume`、`outlineNodes[]`（active/pending/completed）、`chatHistory[]` |
| [`editor`](frontend/src/stores/editor.js) | 编辑器辅助状态 | `conversationHistory[]`、`appendGenerated()` |
| [`settingsStore`](frontend/src/stores/settingsStore.js) | BYOK 配置 — LLM 密钥/地址/模型 | `isOpen`（面板开关）、`apiKey`、`baseUrl`、`model`（localStorage 持久化） |

### 数据流架构

```
书架选择 (TheLibrary)
    ↓ openBook(bookId) / startNewBook()
storyStore.currentBookId = bookId

用户输入 (中栏底部)
    ↓ Ctrl+Enter
startGeneration({book_id, chapter_marker, plot_context, extracted_triggers}, handlers)
    ↓ POST /api/stream/generate（携带 X-LLM-* 头部）
后端 SSE Event Generator
    ↓
onMessage({type:'status', step:'fetch'})  ←──  Phase 1&2: Fetch (predict_fetch_memory, book_id 隔离)
    ↓ memoryStore.isLoading = true
onMessage({type:'status', step:'inject'}) ←──  Phase 3: Inject (build_injection_prompt)
onMessage({type:'status', step:'generate'}) ←  Phase 4: Generate (stream_generate, real LLM)
onMessage({type:'chunk', text})  ←── 打字机逐字上屏  Phase 4 (流式)
onMessage({type:'commit_done'})  ←── memoryStore.addNewFact() → 左栏闪烁  Phase 5: Commit + Memory GC
onMessage({type:'done'})         ←── storyStore.appendChat() → 对话历史归档
```

---

## 8. 项目结构

```
rag-memory-system/
├── docker-compose.yml           # pgvector 容器化一键启动
├── README.md                    # 快速启动指南
├── ARCHITECTURE.md              # 本文件：核心架构蓝图
├── backend/
│   ├── .env                     # LLM 密钥/地址/模型配置（后备，优先使用前端 BYOK）
│   ├── requirements.txt
│   ├── alembic/
│   │   └── env.py               # 迁移配置（已引入 pgvector.sqlalchemy）
│   └── app/
│       ├── main.py              # FastAPI 入口，挂载路由 + CORS
│       ├── config.py            # 配置（数据库连接、embedding 维度等）
│       ├── database.py          # SQLAlchemy async 引擎 & Session
│       ├── llm_client.py        # AsyncOpenAI 动态客户端：get_dynamic_client() + stream_generate() + extract_new_facts() + compact_old_facts() + suggest_plot_directions() + generate_pitches_from_llm() + generate_outline_from_llm() + _translate_llm_error()
│       ├── memory_compactor.py  # 后台 Memory GC：阈值触发 → LLM 炼化 → 软删除旧事实 + 插入压缩事实
│       ├── prompt_engine.py     # 上下文注入 Prompt 组装
│       ├── extraction_engine.py # 写后提取 Prompt 组装 + 结果解析（备用）
│       ├── orchestrator.py      # 编排层（预留）
│       ├── models/
│       │   ├── book.py          # Book 表模型（多租户容器）
│       │   ├── entity.py        # MemoryEntity 表模型（含 book_id FK + 联合唯一约束）
│       │   ├── fact.py          # MemoryFact 表模型（含 VECTOR 列）
│       │   ├── pitch.py         # StoryPitch 表模型（灵感裂变持久化）
│       │   ├── outline.py       # StoryOutlineNode 表模型（大纲节点持久化）
│       │   ├── chapter.py       # StoryChapter 表模型（章节内容持久化）
│       │   ├── chat.py          # StoryChatMessage 表模型（对话历史持久化）
│       │   └── apiconfig.py     # ApiConfig 表模型（设置持久化）
│       ├── schemas/
│       │   ├── fetch.py         # POST /fetch 请求/响应 Pydantic 模型（含 book_id）
│       │   ├── commit.py        # POST /commit 请求模型（含 book_id）
│       │   ├── override.py      # PUT /override 请求模型（含 book_id）
│       │   ├── pitch.py         # 灵感裂变请求/响应模型
│       │   └── outline.py       # 大纲请求/响应模型
│       └── routers/
│           ├── books.py         # 书架管理：GET/POST/DELETE /api/books/ + POST /pitch + POST /outline
│           ├── memory.py        # 核心 API：fetch / commit / override（book_id 物理隔离）
│           ├── stream.py        # SSE 流式生成路由（五步闭环 + BackgroundTasks GC）+ POST /suggest 幽灵卡片 + POST /revise 时光溯源重塑（提取 X-LLM-* 头部，错误中文翻译）
│           ├── ui.py            # UI 数据接口：entities / facts / chapters（book_id 过滤）
│           ├── pitch.py         # 灵感裂变接口
│           ├── outline.py       # 大纲生成接口
│           ├── chapters.py      # 章节内容持久化：POST /api/chapters/save + GET /api/chapters/list
│           ├── chat.py          # 对话历史持久化：POST /api/chat/save + GET /api/chat/list
│           └── settings.py      # 设置持久化：POST /api/settings/save + GET /api/settings/load
└── frontend/
    ├── index.html
    ├── vite.config.js           # Vite + Vue3 + API 代理
    ├── package.json             # Vue3 + Pinia + Tailwind CSS v4 依赖
    ├── tailwind.config.js       # Tailwind CSS v4 配置（content 扫描路径）
    ├── postcss.config.js        # PostCSS 插件配置（@tailwindcss/postcss + autoprefixer）
    └── src/
        ├── main.js              # 入口，createPinia() 注入
        ├── App.vue              # 四阶段 Transition 路由：TheLibrary → PitchRoom → OutlineForge → IDEWorkspace（挂载 SettingsModal）
        ├── style.css            # Tailwind v4 入口 @import "tailwindcss" + 自定义滚动条 + 动画
        ├── api/
        │   ├── memory.js        # 封装 /fetch /commit /override /entities /facts /chapters（全部携带 book_id + X-LLM-* 头部）
        │   └── stream.js        # SSE 客户端（fetch + ReadableStream + AbortController）+ fetchSuggestions()（携带 X-LLM-* 头部）
        ├── stores/
        │   ├── memoryStore.js   # 左栏灵魂：entities 分组 + newlyAddedIds 闪烁
        │   ├── storyStore.js    # 全流程灵魂：书架管理 + 阶段路由 + 剧情流转 + 对话历史
        │   ├── settingsStore.js # BYOK 配置：apiKey/baseUrl/model（localStorage 持久化）
        │   └── editor.js        # 编辑器辅助状态
        ├── views/
        │   ├── TheLibrary.vue   # Phase 0：书架大厅（网格卡片 + 新建/选书 + ⚙️ 引擎配置）
        │   ├── PitchRoom.vue    # Phase 1：灵感裂变室（Midjourney 风格 U/V 网格）
        │   ├── OutlineForge.vue # Phase 2：大纲锻造炉（可编辑时间线）
        │   └── IDEWorkspace.vue # Phase 3：三栏式 IDE 骨架 + SSE 流式接入 + ⚙️ 偏好设定
        └── components/
            ├── MemoryExplorer.vue   # 记忆资源管理器
            ├── EditorPanel.vue      # 编辑器面板
            ├── OutlineNavigator.vue # 大纲导航
            ├── MemoryPanel.vue      # 右侧"当前激活记忆"面板（含骨架屏）
            ├── TimeSlider.vue       # 时空穿梭滑块（300ms 防抖）
            ├── FactTooltip.vue      # 悬停弹出事实气泡（Teleport + 动效）
            └── SettingsModal.vue    # BYOK 配置模态框（玻璃拟态，三个输入框 + 连接引擎按钮）
```

---

## 9. BYOK 架构：动态 LLM 注入器（Bring Your Own Key）

### 设计动机

传统方案将 API Key 硬编码在后端 `.env`，存在致命缺陷：
- 用户首次打开前端看到黑屏，必须手动编辑后端文件才能使用
- 多用户场景下密钥无法隔离
- 切换模型/提供商需要重启后端

BYOK 架构将 LLM 配置权交还给用户，通过前端面板配置，经 HTTP 头部透传，后端动态实例化客户端。

### 数据流

```
用户打开 TheLibrary / IDEWorkspace
    ↓ 点击 "⚙️ 引擎配置" / "⚙️ 偏好设定"
SettingsModal.vue 弹出（玻璃拟态面板）
    ↓ 填入 Base URL / Model / API Key → 点击 "连接引擎"
settingsStore.saveSettings(key, url, mod)
    ↓ localStorage.setItem('llm_*') 持久化
    ↓ settingsStore.isOpen = false 关闭面板

后续所有 API 请求：
    ↓ llmHeaders() 从 settingsStore 读取配置
    ↓ 注入 HTTP 头部：X-LLM-API-Key / X-LLM-Base-URL / X-LLM-Model
    ↓ POST /api/stream/generate（携带头部）

后端 stream.py 路由：
    ↓ request.headers.get("X-LLM-API-Key") 提取
    ↓ get_dynamic_client(api_key, base_url) 创建 per-request AsyncOpenAI 实例
    ↓ 调用 stream_generate(system_prompt, api_key, base_url, model_name)
```

### 前端配置面板

[`SettingsModal.vue`](frontend/src/components/SettingsModal.vue) — 玻璃拟态模态框：
- **Base URL**：默认 `https://api.deepseek.com`
- **Model**：默认 `deepseek-chat`
- **API Key**：password 模式输入，不可见
- **连接引擎**按钮：调用 `settingsStore.saveSettings()`

### 前端 Store

[`settingsStore.js`](frontend/src/stores/settingsStore.js) — Pinia + localStorage 持久化：

```javascript
state: () => ({
  isOpen: false,
  apiKey: localStorage.getItem('llm_api_key') || '',
  baseUrl: localStorage.getItem('llm_base_url') || 'https://api.deepseek.com',
  model: localStorage.getItem('llm_model') || 'deepseek-chat',
})
```

### HTTP 头部透传

所有前端 API 调用（[`stream.js`](frontend/src/api/stream.js)、[`memory.js`](frontend/src/api/memory.js)）通过 `llmHeaders()` 注入三个自定义头部：

```
X-LLM-API-Key: sk-xxxxx
X-LLM-Base-URL: https://api.deepseek.com
X-LLM-Model: deepseek-chat
```

### 后端动态客户端

[`llm_client.py`](backend/app/llm_client.py) 移除全局 `AsyncOpenAI()` 实例，改为 `get_dynamic_client()`：

```python
def get_dynamic_client(api_key: str = None, base_url: str = None):
    final_key = api_key or os.getenv("LLM_API_KEY")
    final_url = base_url or os.getenv("LLM_BASE_URL")
    if not final_key:
        raise ValueError("未配置 API Key。请在前端面板设置，或在后端 .env 中配置。")
    return AsyncOpenAI(api_key=final_key, base_url=final_url)
```

所有六个 LLM 函数（`stream_generate`、`extract_new_facts`、`compact_old_facts`、`suggest_plot_directions`、`generate_pitches_from_llm`、`generate_outline_from_llm`）均接受 `api_key`、`base_url`、`model_name` 可选参数。若未传入，回退到 `.env` 环境变量。

### 入口点

- **TheLibrary.vue**：右上角 "⚙️ 引擎配置" 按钮（用户首次打开即见）；hover 显示 ✕ 删除按钮
- **IDEWorkspace.vue**：顶栏 "⚙️ 偏好设定" 按钮（IDE 内快速切换）
- **App.vue**：全局挂载 `<SettingsModal />`，所有阶段均可弹出

---

## 10. LLM 配置

### 方式一：前端 BYOK 面板（推荐）

打开浏览器 → 点击 "⚙️ 引擎配置" → 填入 Base URL / Model / API Key → 点击 "连接引擎"。配置自动保存到浏览器 localStorage，无需重启。

### 方式二：后端环境变量（后备）

系统通过环境变量解耦 LLM 提供商，支持 DeepSeek 官方 API 或任意兼容 OpenAI SDK 的 relay 中转站。

#### 环境变量（[`.env`](backend/.env)）

```ini
LLM_API_KEY="sk-你的deepseek密钥"
LLM_BASE_URL="https://api.deepseek.com"
LLM_MODEL="deepseek-chat"
```

### 四模式调用（[`llm_client.py`](backend/app/llm_client.py)）

| 模式 | 函数 | temperature | 用途 |
|------|------|-------------|------|
| 流式生成 | `stream_generate(system_prompt)` | 0.8 | Phase 4 剧情渲染，逐 chunk 推送 SSE |
| JSON 提取 | `extract_new_facts(text)` | 0.1 | Phase 5 记忆沉淀，`response_format={"type":"json_object"}` |
| 记忆炼化 | `compact_old_facts(entity_name, entity_type, facts_list)` | 0.1 | Memory GC 后台压缩，`response_format={"type":"json_object"}` |
| 极速推演 | `suggest_plot_directions(recent_context)` | 0.8 | 幽灵卡片，3 个差异化剧情走向建议 |
| 灵感裂变 | `generate_pitches_from_llm(seed_text, ...)` | 0.8 | PitchRoom 灵感发散，3 个变体 |
| 大纲锻造 | `generate_outline_from_llm(pitch, ...)` | 0.8 | OutlineForge 大纲骨架生成 |

---

### 错误分类与中文翻译

系统所有 LLM API 错误和网络错误均翻译为中文，帮助用户快速区分"软件问题"与"AI/配置问题"。

#### 后端 LLM 错误翻译（[`llm_client.py`](backend/app/llm_client.py:20)）

```python
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
```

网络连接失败翻译为：`"无法连接到 LLM API，请检查网络连接或 API 地址配置"`
API Key 未配置翻译为：`"API Key 未配置。请在前端面板设置，或在后端 .env 中配置 LLM_API_KEY"`

#### 前端网络错误翻译（[`stream.js`](frontend/src/api/stream.js:14)、[`storyStore.js`](frontend/src/stores/storyStore.js:4)）

```javascript
function friendlyFetchError(err) {
  // "Failed to fetch" / "NetworkError" → "无法连接到服务器，请检查后端服务是否启动或网络连接是否正常"
  // "AbortError" / "timeout" → "请求超时或被中断，请重试"
}
```

#### 后端 502 兜底（[`books.py`](backend/app/routers/books.py:63)）

当 LLM 返回空结果（静默失败）时，抛出 `HTTPException(502)`，前端 `fetchWithBYOK` 的 `res.ok` 检查捕获并显示：
- `"LLM API 调用失败，请检查 API 配置、余额或网络连接"`（裂变/大纲）
- `"HTTP 502: ..."`（通用）

#### 责任划分速查表

| 错误表现 | 根因 | 责任方 |
|----------|------|--------|
| `API Key 无效或已过期` | 密钥配置错误 | 用户配置 |
| `API 账户余额不足` | 账户欠费 | 用户账户 |
| `无法连接到 LLM API` | 网络不通或地址错误 | 用户网络/配置 |
| `无法连接到服务器` | 后端未启动或端口错误 | 软件部署 |
| `HTTP 502: LLM API 调用失败` | LLM 返回空结果 | LLM 服务 |
| `HTTP 4xx/5xx` 原始错误 | 后端代码异常 | 软件 Bug |

## 11. 样式架构

### Tailwind CSS v4

系统使用 Tailwind CSS v4 作为样式引擎，通过 PostCSS 插件 `@tailwindcss/postcss` 编译。

#### 配置文件

[`tailwind.config.js`](frontend/tailwind.config.js)：
```javascript
export default {
  content: ["./index.html", "./src/**/*.{vue,js,ts,jsx,tsx}"],
  theme: { extend: {} },
  plugins: [],
}
```

[`postcss.config.js`](frontend/postcss.config.js)：
```javascript
export default {
  plugins: { '@tailwindcss/postcss': {}, autoprefixer: {} }
}
```

#### 样式入口

[`style.css`](frontend/src/style.css) 仅包含 Tailwind v4 入口 + 自定义工具类：

```css
@import "tailwindcss";

.custom-scrollbar::-webkit-scrollbar { width: 6px; height: 6px; }
.custom-scrollbar::-webkit-scrollbar-track { background: transparent; }
.custom-scrollbar::-webkit-scrollbar-thumb { background-color: rgba(255,255,255,0.08); border-radius: 10px; }
.custom-scrollbar::-webkit-scrollbar-thumb:hover { background-color: rgba(255,255,255,0.15); }
.scrollbar-hide { -ms-overflow-style: none; scrollbar-width: none; }
.scrollbar-hide::-webkit-scrollbar { display: none; }
@keyframes fade-in-up { 0% { opacity: 0; transform: translateY(20px); } 100% { opacity: 1; transform: translateY(0); } }
```

所有 Vite 默认样式（`#app { max-width: 1280px; margin: 0 auto; text-align: center; }`）已删除，避免与 Tailwind 全屏布局冲突。

---

## 12. 启动指南

### 前置条件
- Docker & Docker Compose
- Python 3.11+
- Node.js 18+

### 步骤

```bash
# 1. 启动 PostgreSQL + pgvector
docker compose up -d

# 2. 启动后端
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 3. 启动前端
cd frontend
npm install
npm run dev
```

### 首次使用

1. 打开浏览器访问 `http://localhost:5173`
2. 点击书架大厅右上角 **"⚙️ 引擎配置"**
3. 填入你的 LLM Base URL、Model、API Key
4. 点击 **"连接引擎"** — 配置自动保存
5. 点击 **"+ 开辟新世界"** 开始创作

### 验证

```bash
# 健康检查
curl http://localhost:8000/health

# 创建一本书
curl -X POST http://localhost:8000/api/books/ \
  -H "Content-Type: application/json" \
  -d '{"title":"修仙传","summary":"一个少年的修仙之路"}'

# 提交一条记忆（需替换 book_id）
curl -X POST http://localhost:8000/api/memory/commit \
  -H "Content-Type: application/json" \
  -d '{"book_id":"<上一步返回的id>","chapter_marker":1,"entry_name":"张三","triggers":["张三","三哥"],"content":"青云宗外门弟子","type":"人物"}'

# 召回记忆
curl -X POST http://localhost:8000/api/memory/fetch \
  -H "Content-Type: application/json" \
  -d '{"book_id":"<book_id>","current_chapter":1,"extracted_triggers":["张三","青云城"]}'

# SSE 流式生成（需保持连接查看流式输出）
curl -N -X POST http://localhost:8000/api/stream/generate \
  -H "Content-Type: application/json" \
  -d '{"book_id":"<book_id>","chapter_marker":1,"plot_context":"张三拔剑","extracted_triggers":["张三"]}'
```
