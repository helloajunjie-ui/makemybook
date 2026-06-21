# 青羽·织梦宇宙 — AI 小说创作助手

> 一套带记忆功能的 AI 小说创作工具，帮你管理复杂的世界观和人物关系。
>
> 技术架构文档见 [`ARCHITECTURE.md`](ARCHITECTURE.md) | **版本**: 4.0

---

## 快速开始

### 首次使用

1. **打开软件**，进入书架大厅
2. 点击右上角 **"⚙️ 引擎配置"**
3. 选择接入方式（DeepSeek 官方 或 AI 中转站）
4. 填写 API Key 和地址，点击 **"连接引擎"**
5. 看到信号灯变绿 🟢，即可开始创作

> 配置只需设置一次，下次打开自动加载。

### 界面说明

| 区域 | 说明 |
|------|------|
| 📚 书架大厅 | 创建/选择小说 |
| 💡 灵感裂变室 | 输入想法，AI 帮你扩展创意 |
| 📋 大纲锻造炉 | 规划章节结构 |
| ✍️ 创作 IDE | 写正文，AI 辅助生成 |

### 创作 IDE 三栏布局

```
┌─────────────────────────────────────────────────────────────┐
│ 顶栏：书名 | 状态指示灯 🟢 | ⚙️ 偏好设定 | 导出全卷          │
├──────────┬──────────────────────────────────┬──────────────┤
│ 左栏     │ 中栏                             │ 右栏         │
│ 设定字典  │ 剧本渲染与共创区                   │ 世界大纲      │
│          │                                   │              │
│ 人物     │ [打字机流式文本]                    │ 第1卷：觉醒篇 │
│ 张三 🟦  │ 张三冷笑一声，拔出了那把断剑...      │ 第2卷：试炼篇 │
│ 李四 🟦  │                                   │              │
│          │ [对话历史]                         │              │
│ 地点     ├──────────────────────────────────┤              │
│ 青云城   │ 输入框 [✨ 灵感] [Ctrl+Enter 生成]  │              │
└──────────┴──────────────────────────────────┴──────────────┘
```

> 🟦 **词条胶囊**：鼠标悬停显示该词条的所有设定事实（气泡自动定位，右侧优先，空间不足翻左侧）。
> ✨ **灵感按钮**：点击生成 3 个剧情走向建议，点击卡片自动填入输入框。

---

## 新功能亮点

### 🕰️ 时间线覆写引擎（Timeline Retcon）

修改已写章节后，AI 记忆自动同步更新，杜绝"祖父悖论"——不会在后续章节复活已死的角色。

- **自动触发**：在时光机面板接受改写后，静默重建该章记忆
- **精准抹除**：只删除被修改章节的记忆，不影响其他章节
- **幽灵清理**：自动删除不再有任何事实关联的孤立词条

### 📊 遥测仪表盘（Telemetry HUD）

右下角水印级字数统计，不打扰创作沉浸感。

- 当前章节字数 / 全书总字数 / 章节数
- 40% 透明度，鼠标穿透，不阻挡交互
- 随内容变化自动更新

### 🎨 Zen Mode 降噪柔化

长时间创作不疲劳的视觉设计。

- 降低对比度天花板（纯白→柔灰，纯黑→深墨）
- 视觉层级后退（z-index 优化 + 透明度梯度）
- 控制台侵略性降低（状态文字加透明度，去色块化）

### 信号灯说明

页面右上角的圆点指示灯显示当前软件状态：

| 信号灯 | 含义 | 怎么办 |
|--------|------|--------|
| 🟢 绿色（闪烁） | 一切正常，可以开始创作 | — |
| 🔴 红色（显示"程序未启动"） | 软件启动异常 | **重启软件** |
| 🔴 红色（显示"AI 连接失败"） | AI 配置有问题 | 打开⚙️检查 API Key 和地址 |
| 🔴 红色（显示"未配置 AI"） | 还没设置 AI | 打开⚙️配置 AI |
| ⚪ 灰色 | 正在检测中 | 稍等片刻 |

> 点击信号灯可以手动重新检测。

---

## 常见问题

### Q: 信号灯红了怎么办？
- 显示"程序未启动，请重启软件" → **关掉软件重新打开**
- 显示"未配置 AI" → 点击⚙️填写 API Key
- 显示"AI 连接失败" → 检查 API Key 是否正确，网络是否通畅

### Q: 如何获取 API Key？
- **DeepSeek 官方**：访问 platform.deepseek.com 注册获取
- **AI 中转站**：联系你的中转服务商获取

### Q: 配置保存后下次打开没了？
- 检查是否使用了浏览器的**隐私/无痕模式**，隐私模式下不会保存配置
- 确认点击了"连接引擎"按钮（不是直接关掉窗口）

### Q: 鼠标移到词条上，气泡一闪就没了？
- 这是正常设计！气泡和词条之间有物理缝隙，系统给了 **150ms 的"滞空时间"**。只要鼠标在 150ms 内滑进气泡，气泡就不会消失。如果还是消失，说明鼠标移动太慢，再试一次快速滑过去即可。

### Q: 灵感按钮点了没反应？
- 检查右上角信号灯是否为 🟢 绿色。如果是 🔴 红色，说明 AI 未连接，请点击 ⚙️ 配置 API Key。
- 如果信号灯正常但仍无反应，检查浏览器控制台是否有网络错误。

### Q: 输入框显示 `[object Object]`？
- 这是旧版本的 Bug，当前版本已修复。如果遇到，刷新页面即可。

### Q: 遇到其他问题？
加入技术支持群反馈，携带截图和错误信息。

---

## 项目结构

```
rag-memory-system/
├── docker-compose.yml
├── ARCHITECTURE.md          # 核心架构蓝图（必读）
├── README.md                # 本文件
├── backend/
│   ├── .env                 # LLM 密钥/地址/模型配置（后备，优先使用前端 BYOK）
│   ├── requirements.txt
│   ├── alembic/env.py
│   └── app/
│       ├── main.py          # FastAPI 入口
│       ├── config.py        # 配置
│       ├── database.py      # SQLAlchemy async 引擎
│       ├── llm_client.py    # AsyncOpenAI 动态客户端（extract_json_from_markdown + get_dynamic_client + 流式生成 + 事实抽取 + 记忆炼化 + 灵感裂变 + 大纲锻造）
│       ├── memory_compactor.py # 后台 Memory GC
│       ├── prompt_engine.py # 上下文注入 Prompt 组装
│       ├── models/          # Book, MemoryEntity, MemoryFact, StoryPitch, StoryOutlineNode, StoryChapter, StoryChatMessage, ApiConfig
│       ├── schemas/         # fetch, commit, override, pitch, outline（全部含 book_id）
│       └── routers/         # books, memory(物理隔离), stream(SSE+GC+X-LLM-*头部), ui, pitch, outline, chapters, chat, settings
└── frontend/
    ├── index.html
    ├── vite.config.js
    ├── package.json         # Vue3 + Pinia + Tailwind CSS v4
    ├── tailwind.config.js   # Tailwind v4 配置
    ├── postcss.config.js    # PostCSS 插件（@tailwindcss/postcss）
    └── src/
        ├── main.js          # 入口，createPinia()
        ├── App.vue          # 四阶段 Transition 路由 + SettingsModal 全局挂载
        ├── style.css        # Tailwind v4 入口 @import "tailwindcss"
        ├── api/
        │   ├── memory.js    # REST API 客户端（全部携带 book_id + X-LLM-* 头部）
        │   └── stream.js    # SSE 客户端 + fetchSuggestions()（携带 X-LLM-* 头部）
        ├── stores/
        │   ├── memoryStore.js   # 左栏记忆状态
        │   ├── storyStore.js    # 全流程状态（书架 + 阶段路由 + 剧情流转）
        │   ├── settingsStore.js # BYOK 配置（localStorage 持久化）
        │   └── editor.js        # 编辑器辅助状态
        ├── views/
        │   ├── TheLibrary.vue    # 书架大厅（含 ⚙️ 引擎配置入口）
        │   ├── PitchRoom.vue     # 灵感裂变室
        │   ├── OutlineForge.vue  # 大纲锻造炉
        │   └── IDEWorkspace.vue  # 三栏创作 IDE（含 ⚙️ 偏好设定入口）
        └── components/
            ├── SettingsModal.vue # BYOK 配置模态框
            ├── MemoryPanel.vue
            ├── TimeSlider.vue
            ├── FactTooltip.vue
            └── ...
```

---

## 技术支持

**QQ 群**: `1051068329` | **作者**: 尼可
