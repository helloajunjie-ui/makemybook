<template>
  <div class="h-screen w-screen flex flex-col overflow-hidden bg-[#0F111A] text-[#94A3B8]">
    <!-- 顶栏：极简无边框，极弱的下划线 -->
    <header class="h-14 flex items-center justify-between px-6 bg-[#0f111a] border-b border-white/[0.02] shrink-0 z-20">

      <!-- 左侧全局导航与面包屑 -->
      <div class="flex items-center space-x-4">
        <!-- 返回大厅的逃生舱 -->
        <button @click="storyStore.setPhase('library')"
                class="flex items-center text-sm font-medium text-[#64748B] hover:text-blue-400/70 transition-colors group">
          <span class="mr-1.5 transform group-hover:-translate-x-1 transition-transform">←</span>
          宇宙大厅
        </button>

        <span class="text-gray-800 text-lg">|</span>

        <!-- 当前世界指示器 -->
        <div class="flex items-center space-x-2">
          <div class="w-2 h-2 rounded-full bg-blue-500 animate-pulse shadow-[0_0_10px_rgba(59,130,246,0.6)]"></div>
          <div class="font-bold text-sm tracking-widest text-transparent bg-clip-text bg-gradient-to-r from-[#94A3B8] to-[#64748B]">
            {{ storyStore.selectedPitch?.title || '青羽·织梦引擎' }}
          </div>
        </div>
      </div>

      <!-- 右侧控制台 -->
      <div class="flex items-center space-x-5 text-sm">
        <!-- AI 连接状态 -->
        <div @click="settingsStore.checkConnection()"
             :title="aiStatusTooltip"
             class="flex items-center text-[#64748B] text-xs cursor-pointer hover:text-[#94A3B8] transition">
          <span :class="aiStatusDot" class="w-1.5 h-1.5 rounded-full mr-2 shadow-[0_0_8px_var(--tw-shadow-color)]"></span>
          {{ aiStatusLabel }}
        </div>
        <button @click="settingsStore.openPanel()" class="text-[#64748B] hover:text-[#94A3B8] transition flex items-center">
          <span class="mr-1">⚙️</span> 偏好设定
        </button>
        <button class="px-4 py-1.5 bg-[#2E3C56]/30 text-[#94A3B8] border border-white/5 rounded-lg hover:bg-[#2E3C56] hover:text-[#D1D5DB] transition shadow-sm font-medium">
          导出全卷
        </button>
      </div>
    </header>

    <!-- 错误提示条 -->
    <div v-if="errorMessage" class="px-6 py-2 bg-red-900/60 border-b border-red-700/50 text-red-200 text-sm flex items-center justify-between shrink-0">
      <span>⚠️ {{ errorMessage }}</span>
      <button @click="errorMessage = ''" class="text-red-300 hover:text-white ml-4">✕</button>
    </div>

    <!-- 主工作区：Flexbox 三栏布局 -->
    <main class="flex-1 flex overflow-hidden">

      <!-- 左栏：设定字典 (w-[280px], Z轴阴影) -->
      <aside class="w-[280px] shrink-0 flex flex-col bg-[#0B0D14] shadow-[inset_-10px_0_20px_rgba(0,0,0,0.2)] z-10 border-r border-white/[0.02]">
        <div class="p-4 border-b border-white/[0.02] font-semibold text-[#94A3B8]">
          📚 设定字典 (第 {{ storyStore.currentChapter }} 章)
        </div>
        <div class="flex-1 overflow-y-auto p-3 space-y-4 custom-scrollbar">
          <div v-for="(entries, type) in memoryStore.entities" :key="type" class="mb-6">
            <!-- 分类标题 -->
            <h4 class="text-[10px] font-bold text-[#64748B] mb-3 px-2 uppercase tracking-widest">{{ type }}</h4>

            <!-- 💡 Flex 标签云布局 -->
            <div class="flex flex-wrap gap-2 px-2">

              <div v-for="entry in entries" :key="entry.id"
                   class="relative cursor-help"
                   @mouseenter="showTooltip($event, entry)"
                   @mouseleave="hideTooltip">

                <!-- 词条小胶囊 -->
                <div class="px-2.5 py-1.5 bg-[#131620] border border-white/[0.03] rounded-md hover:border-blue-500/30 hover:bg-[#1a1f2e] transition-all flex items-center shadow-sm group">
                  <span class="w-1.5 h-1.5 bg-blue-500/30 rounded-full mr-1.5 opacity-50 group-hover:opacity-100 group-hover:shadow-[0_0_8px_rgba(59,130,246,0.4)] transition-all"></span>
                  <span class="text-xs text-[#64748B] group-hover:text-[#94A3B8] font-medium transition-colors">
                    {{ entry.entry_name || '未知' }}
                  </span>
                </div>

              </div>
            </div>
          </div>
        </div>

        <!-- 🚀 Teleport 到 body：气泡在顶层渲染，永不遮挡 -->
        <!-- 外层 pb-2 做隐形桥填补空隙，内层 pointer-events-auto 允许滚动/点击 -->
        <Teleport to="body">
          <div v-if="tooltipEntry"
               :style="tooltipStyle"
               class="fixed z-[9999]"
               @mouseenter="keepTooltipAlive"
               @mouseleave="hideTooltip">

            <!-- 隐形桥：填补胶囊到气泡之间的空隙 -->
            <div class="pb-2">
              <!-- 实体气泡 -->
              <div class="w-72 p-4 bg-[#0F111A]/95 backdrop-blur-xl border border-white/[0.05] rounded-lg shadow-[0_10px_40px_rgba(0,0,0,0.9)] pointer-events-auto">

                <!-- 指向胶囊的箭头 -->
                <div :style="arrowStyle"
                     class="absolute w-3 h-3 bg-[#0F111A] border-l border-t border-white/[0.05]"></div>

                <!-- 阶段印记 -->
                <div class="absolute top-4 right-4 text-[9px] font-mono text-[#64748B] border border-white/5 px-1.5 py-0.5 rounded">
                  初见于 第 {{ tooltipEntry.facts?.length > 0 ? (tooltipEntry.facts[0]?.chapter_marker ?? tooltipEntry.facts[0]?.chapter ?? '?') : '?' }} 章
                </div>

                <!-- 标题 -->
                <h5 class="text-base font-bold text-[#94A3B8] mb-1">{{ tooltipEntry.entry_name || '未知' }}</h5>

                <!-- 类型标签 -->
                <div class="text-[10px] text-blue-400/70 mb-3 font-mono">CLASS: {{ tooltipEntry.type }}</div>

                <!-- 内容区：现在可以滚动 -->
                <div class="max-h-48 overflow-y-auto custom-scrollbar pr-2 mb-3">
                  <div v-if="!tooltipEntry.facts || tooltipEntry.facts.length === 0" class="text-xs text-[#64748B] italic">
                    暂无详细记录...
                  </div>
                  <div v-for="(fact, index) in tooltipEntry.facts" :key="fact.id || index"
                       class="mb-3 relative pl-3 border-l border-white/[0.05] last:mb-0">
                    <div class="absolute -left-[3px] top-1.5 w-1.5 h-1.5 bg-blue-500/50 rounded-full"></div>
                    <div class="text-[9px] text-blue-400/80 font-mono mb-1">
                      [更新于 第 {{ fact.chapter_marker || fact.chapter || '?' }} 章]
                    </div>
                    <div class="text-xs text-[#8B9EB0] leading-relaxed whitespace-pre-wrap">{{ fact.content }}</div>
                  </div>
                </div>

                <!-- 触发词 -->
                <div class="flex flex-wrap gap-1.5 pt-2 border-t border-white/[0.02]" v-if="tooltipEntry.triggers && tooltipEntry.triggers.length > 0">
                  <span class="text-[10px] text-[#64748B] mr-1 mt-0.5">触发词:</span>
                  <span v-for="t in tooltipEntry.triggers.filter(x => x !== tooltipEntry.entry_name)" :key="t"
                        class="px-1.5 py-0.5 bg-[#131620] border border-white/[0.03] rounded text-[9px] text-[#8B9EB0]">{{ t }}</span>
                </div>

              </div>
            </div>
          </div>
        </Teleport>
      </aside>

      <!-- 中栏：剧本渲染与共创区 (最深色背景, flex-1) -->
      <section class="flex-1 flex flex-col bg-[#0F111A] relative">

        <!-- 💡 顶部遥测仪表盘 (Telemetry HUD) — 水印级存在感 -->
        <div class="absolute top-0 right-0 left-0 h-12 bg-gradient-to-b from-[#0B0D14]/80 to-transparent z-10 flex justify-end items-start pt-3 px-6 pointer-events-none select-none">
          <div class="flex items-center gap-4 text-[11px] font-mono text-[#475569]/70 tracking-widest uppercase">
            <div class="flex items-center gap-1.5">
              <span class="w-1 h-1 bg-[#475569]/50 rounded-full"></span>
              CH.{{ storyStore.currentChapter }} <span class="text-[#64748B]">{{ storyStore.currentChapterWordCount }}</span> W
            </div>
            <div class="flex items-center gap-1.5">
              <span class="w-1 h-1 bg-[#475569]/50 rounded-full"></span>
              TOTAL <span class="text-[#64748B]">{{ storyStore.totalWordCount }}</span> W
            </div>
          </div>
        </div>

        <!-- 黄金阅读容器 (pt-12 为 HUD 让位) -->
        <div class="flex-1 overflow-y-auto custom-scrollbar pt-12" ref="chatContainer">
          <div class="max-w-3xl mx-auto px-8 pb-8">

            <!-- 状态机骨架屏 -->
            <div v-if="generating" class="mb-6 space-y-2">
              <div v-for="step in statusSteps" :key="step.key"
                   class="flex items-center gap-3 text-sm px-4 py-2 rounded"
                   :class="step.status === 'active' ? 'bg-blue-900/20 text-blue-400/80 border border-blue-900/30' : step.status === 'done' ? 'text-green-400/80' : 'text-[#475569]'">
                <span v-if="step.status === 'active'" class="w-4 h-4 rounded-full border-2 border-blue-400 animate-spin border-t-transparent"></span>
                <span v-else-if="step.status === 'done'" class="text-green-400">✓</span>
                <span v-else class="w-4 h-4 rounded-full border border-gray-600"></span>
                {{ step.label }}
              </div>
            </div>

            <!-- 卷宗分隔线 + 普通消息 -->
            <div v-for="msg in storyStore.chatHistory" :key="msg.id" class="mb-8 group">

              <!-- 正常的文本消息 -->
              <div v-if="!msg.type || msg.type === 'text'" class="text-[#8B9EB0] leading-[2.2] text-lg font-serif tracking-wide whitespace-pre-wrap">
                {{ msg.content }}
              </div>

              <!-- 🌟 史诗级卷宗分割线 -->
              <div v-else-if="msg.type === 'volume_divider'" class="my-16 relative flex py-8 items-center opacity-0 animate-[fade-in-up_0.8s_ease-out_forwards]">
                <div class="flex-grow border-t border-white/[0.05]"></div>
                <div class="flex flex-col items-center mx-8 text-center">
                  <span class="text-xs font-mono tracking-widest text-emerald-500/80 mb-2 uppercase border border-emerald-900/50 bg-emerald-900/20 px-3 py-1 rounded-full shadow-[0_0_10px_rgba(16,185,129,0.1)]">
                    VOLUME {{ msg.volume }}
                  </span>
                  <h2 class="text-3xl font-black text-transparent bg-clip-text bg-gradient-to-r from-[#94A3B8] to-[#64748B] tracking-widest drop-shadow-lg">
                    {{ msg.title }}
                  </h2>
                  <p v-if="msg.desc" class="text-sm text-[#64748B] mt-3 max-w-md italic">
                    " {{ msg.desc }} "
                  </p>
                </div>
                <div class="flex-grow border-t border-white/[0.05]"></div>
              </div>

            </div>

            <!-- 正在生成的打字机文本 (serif 字体) -->
            <div v-if="streamingText" class="mb-6 p-6 rounded-lg bg-white/[0.03] border border-blue-800/30">
              <div class="text-[#94A3B8] leading-[2.2] text-lg font-serif tracking-wide whitespace-pre-wrap">{{ streamingText }}</div>
              <span class="inline-block w-2 h-4 bg-blue-400 animate-pulse ml-1"></span>
            </div>

            <!-- 空状态 -->
            <div v-if="!storyStore.chatHistory.length && !generating" class="text-[#475569] text-center mt-32">
              <p class="text-lg">✨ 输入指令开始创作</p>
              <p class="text-sm mt-2">在下方输入推演指令，按 Ctrl+Enter 生成正文</p>
            </div>

          </div>
        </div>

        <!-- 全息悬浮控制台 (glassmorphism + 渐变遮罩) -->
        <div class="absolute bottom-0 left-0 w-full pt-20 pb-8 px-8 bg-gradient-to-t from-[#0F111A] via-[#0F111A]/95 to-transparent pointer-events-none">
          <div class="max-w-3xl mx-auto pointer-events-auto">
            <!-- 🔮 剧情预演幽灵卡片区 -->
            <div class="flex space-x-3 mb-3 overflow-x-auto pb-1 scrollbar-hide">
              <button @click="storyStore.fetchPlotSuggestions()"
                      class="flex-shrink-0 flex items-center justify-center w-8 h-8 rounded-full bg-[#131620]/80 backdrop-blur-md border border-white/[0.03] hover:border-blue-500/40 text-[#64748B] hover:text-blue-400/70 transition"
                      :class="storyStore.isSuggesting ? 'animate-spin' : ''"
                      title="换一批灵感">
                ✨
              </button>
              <div v-if="storyStore.isSuggesting" class="flex space-x-3">
                <div v-for="i in 3" :key="i" class="h-8 w-48 bg-[#131620]/80 rounded-lg animate-pulse border border-white/[0.02]"></div>
              </div>
              <template v-else>
                <button v-for="(suggestion, idx) in storyStore.plotSuggestions" :key="idx"
                        @click="applySuggestion(suggestion)"
                        class="flex-shrink-0 max-w-[250px] text-left px-4 py-1.5 text-xs text-[#64748B] bg-[#131620]/80 backdrop-blur-md border border-white/[0.03] hover:border-blue-500/40 hover:bg-blue-900/10 hover:text-[#94A3B8] rounded-lg transition-all truncate shadow-sm"
                        :title="typeof suggestion === 'object' ? (suggestion.desc || suggestion.conflict || '') : suggestion">
                  <span class="text-blue-500/60 font-bold mr-1">#{{ idx + 1 }}</span>
                  {{ typeof suggestion === 'object' ? (suggestion.title || '剧情分支') : suggestion }}
                </button>
              </template>
            </div>

            <!-- 💡 全息状态呼吸灯 -->
            <div v-if="sysStatus" class="flex items-center gap-2 mb-3 px-1">
              <span class="w-2 h-2 bg-blue-500 rounded-full animate-pulse shadow-[0_0_8px_rgba(59,130,246,0.8)]"></span>
              <span class="text-xs font-mono text-blue-400/80 tracking-wider">{{ sysStatus }}</span>
            </div>

            <!-- 💡 文风约束弹窗（毛玻璃，绝对定位在输入框上方） -->
            <div v-if="showStyleModal"
                 class="relative mb-3">
              <div class="w-full p-4 bg-[#0F111A]/95 backdrop-blur-2xl border border-blue-500/20 rounded-xl shadow-[0_20px_60px_rgba(0,0,0,0.8)]">
                <div class="flex justify-between items-center mb-3">
                  <h3 class="text-xs font-bold text-[#94A3B8] flex items-center">
                    <span class="w-1 h-3 bg-blue-500/50 rounded-full mr-2"></span>
                    全局文风与规则约束（最高优先级）
                  </h3>
                  <button @click="showStyleModal = false" class="text-gray-500 hover:text-white transition-colors text-xs">✕</button>
                </div>
                <textarea
                  v-model="storyStore.customPrompt"
                  class="w-full h-24 bg-[#131620] border border-white/[0.05] rounded-lg p-3 text-xs text-[#8B9EB0] placeholder-[#475569] focus:border-blue-500/30 focus:ring-1 focus:ring-blue-500/20 outline-none resize-none custom-scrollbar"
                  placeholder="例如：&#10;1. 语言风格要求冷峻、克制，不要用华丽堆砌的辞藻。&#10;2. 战斗场面要拳拳到肉，多写动作细节。&#10;3. 每段尽量不要超过3行，节奏要快。"></textarea>
                <div class="mt-2 flex justify-end">
                  <button @click="storyStore.saveCustomPrompt(storyStore.customPrompt); showStyleModal = false"
                          class="px-3 py-1 bg-[#2E3C56] hover:bg-[#3B4D6B] rounded text-[10px] font-bold text-[#D1D5DB] transition-colors shadow-lg">
                    保存并应用
                  </button>
                </div>
              </div>
            </div>

            <!-- glassmorphism 输入框 -->
            <div class="flex gap-2">
              <div class="relative flex-1">
                <!-- 💡 文风约束呼出按钮（输入框左上角） -->
                <div class="absolute -top-6 left-0 flex items-center gap-2 z-10">
                  <button @click="showStyleModal = !showStyleModal"
                          class="text-[10px] flex items-center px-2 py-0.5 bg-[#131620]/50 hover:bg-blue-900/30 border border-white/[0.03] hover:border-blue-500/30 rounded text-[#64748B] hover:text-[#94A3B8] transition-all">
                    ⚙️ 文风约束{{ storyStore.customPrompt ? ' ✓' : '' }}
                  </button>
                </div>
                <textarea
                  v-model="storyStore.currentDraft"
                  class="w-full h-24 bg-[#131620] backdrop-blur-xl border border-white/[0.05] rounded-2xl p-3 pl-4 text-sm text-[#8B9EB0] focus:outline-none focus:border-blue-500/30 focus:ring-1 focus:ring-blue-500/20 resize-none transition-all shadow-[inset_0_2px_4px_rgba(0,0,0,0.4),0_8px_30px_rgba(0,0,0,0.4)]"
                  placeholder="选择上方预演方向，或自己输入剧情推演指令 (Enter 发送)..."
                  @keydown.enter.prevent="submitGeneration"
                  :disabled="generating"
                ></textarea>
                <button @click="submitGeneration"
                        class="absolute bottom-3 right-3 p-2 bg-[#2E3C56] hover:bg-[#3B4D6B] text-[#D1D5DB] rounded-lg shadow-[0_0_10px_rgba(0,0,0,0.3)] transition">
                  <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"></path></svg>
                </button>
              </div>
              <div class="flex flex-col gap-2 shrink-0">
                <button class="px-4 py-2 bg-[#2E3C56] border border-white/5 rounded hover:bg-[#3B4D6B] transition text-sm text-[#D1D5DB] disabled:opacity-50"
                        @click="submitGeneration" :disabled="generating || !String(storyStore.currentDraft || '').trim()">生成</button>
                <button v-if="generating" class="px-4 py-2 bg-red-800/60 rounded hover:bg-red-700/80 transition text-sm text-red-200"
                        @click="stopGeneration">停止</button>
                <button class="px-4 py-2 bg-gradient-to-r from-[#2E3C56] to-[#3B4D6B] rounded hover:from-[#3B4D6B] hover:to-[#4A5C7A] transition text-sm whitespace-nowrap text-[#D1D5DB]"
                        @click="storyStore.advanceVolume()"
                        :disabled="generating">📖 推进卷宗</button>
              </div>
            </div>
          </div>
        </div>

      </section>

      <!-- 右栏：世界大纲 (w-[320px], Z轴阴影) -->
      <aside class="w-[320px] shrink-0 flex flex-col bg-[#0B0D14] shadow-[inset_10px_0_20px_rgba(0,0,0,0.2)] z-10 border-l border-white/[0.02]">
        <div class="p-4 border-b border-white/[0.02] font-semibold text-[#94A3B8] flex items-center justify-between">
          <span>🗺️ 世界大纲</span>
          <button class="text-xs px-3 py-1 bg-gradient-to-r from-[#2E3C56] to-[#3B4D6B] rounded hover:from-[#3B4D6B] hover:to-[#4A5C7A] transition text-[#D1D5DB]"
                  @click="storyStore.advanceVolume()"
                  :disabled="generating">推进卷宗 📖</button>
        </div>
        <div class="flex-1 overflow-y-auto p-4 custom-scrollbar">
          <div v-for="node in storyStore.outlineNodes" :key="node.id"
               class="mb-6 relative pl-6 transition-all duration-500 ease-out"
               :class="(node.status === 'active' || Number(node.volume) === storyStore.currentVolume)
                 ? 'border-l-2 border-blue-500/50 shadow-[inset_0_0_12px_rgba(59,130,246,0.1)] rounded-r-lg'
                 : node.status === 'completed'
                   ? 'border-l-2 border-gray-600 opacity-70'
                   : 'border-l-2 border-gray-800 opacity-30'">
            <div class="absolute -left-[11px] top-0 w-5 h-5 rounded-full border-4 transition-all duration-500"
                 :class="(node.status === 'active' || Number(node.volume) === storyStore.currentVolume)
                   ? 'bg-blue-500/60 border-blue-900 shadow-[0_0_10px_rgba(59,130,246,0.3)] animate-pulse'
                   : node.status === 'completed'
                     ? 'bg-gray-600 border-gray-800'
                     : 'bg-gray-800 border-gray-800'">
            </div>
            <h4 class="font-bold text-sm transition-colors duration-500"
                :class="(node.status === 'active' || Number(node.volume) === storyStore.currentVolume) ? 'text-blue-400/80' : 'text-[#64748B]'">
              第 {{ node.volume }} 卷：{{ node.title }}
            </h4>
            <p v-if="node.status === 'active' || Number(node.volume) === storyStore.currentVolume" class="text-xs text-[#64748B] mt-2 line-clamp-2">
              {{ node.desc }}
            </p>
            <div v-if="node.status === 'active' || node.status === 'completed' || Number(node.volume) === storyStore.currentVolume" class="mt-3 pl-2 space-y-2 border-l border-white/[0.02]">
              <div v-for="chapter in storyStore.chapters.filter(c => Number(c.volume) === Number(node.volume))" :key="chapter.id"
                   @click="storyStore.openChapterModal(chapter)"
                   class="text-xs text-[#64748B] hover:text-blue-400/70 cursor-pointer flex items-center group transition-colors">
                <span class="w-1.5 h-1.5 bg-gray-600 group-hover:bg-blue-500/50 rounded-sm mr-2 transition-colors"></span>
                <span class="truncate">{{ chapter.title }}</span>
              </div>
            </div>
          </div>
        </div>
      </aside>

    </main>

    <!-- 全息时光机弹窗（含溯源控制台） -->
    <div v-if="storyStore.viewingChapter" class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm animate-[fade-in_0.2s_ease-out]">
      <div class="w-full max-w-3xl max-h-[85vh] bg-[#0F111A] border border-white/[0.05] rounded-2xl shadow-[0_20px_60px_rgba(0,0,0,0.7)] flex flex-col overflow-hidden transform transition-all">
        <div class="px-8 py-5 border-b border-white/[0.02] flex justify-between items-center bg-[#0B0D14]/80 shrink-0">
          <div class="flex items-center space-x-3">
            <span class="text-xs font-mono text-blue-400/70 bg-blue-900/20 border border-blue-500/20 px-2 py-1 rounded">
              VOLUME {{ storyStore.viewingChapter?.volume ?? '?' }}
            </span>
            <h3 class="text-xl font-bold text-[#94A3B8] tracking-wider">
              {{ storyStore.viewingChapter?.title ?? '未知章节' }}
            </h3>
          </div>
          <button @click="storyStore.closeChapterModal()" class="text-[#64748B] hover:text-[#94A3B8] transition w-8 h-8 rounded-full hover:bg-white/5 flex items-center justify-center">✕</button>
        </div>

        <!-- 正文阅读区 / 修稿预览区 -->
        <div class="p-10 overflow-y-auto custom-scrollbar flex-1 bg-gradient-to-b from-[#0F111A] to-[#0B0D14] relative">
          <div class="text-[#8B9EB0] leading-[2.2] text-lg font-serif tracking-wide whitespace-pre-wrap max-w-2xl mx-auto selection:bg-blue-500/20 transition-all"
               :class="reviseDraft ? 'opacity-50' : 'opacity-100'">
            {{ storyStore.viewingChapter?.content ?? '' }}
          </div>
          <div v-if="reviseDraft || isRevising" class="absolute inset-0 p-10 bg-[#0F111A]/80 backdrop-blur-sm overflow-y-auto custom-scrollbar">
            <div class="max-w-2xl mx-auto">
              <div class="text-blue-400/80 leading-[2.2] text-lg font-serif tracking-wide whitespace-pre-wrap">
                {{ reviseDraft }}
                <span v-if="isRevising" class="inline-block w-2 h-5 bg-blue-500 animate-pulse ml-1 align-middle"></span>
              </div>
            </div>
          </div>
        </div>

        <!-- 底栏操作区 -->
        <div class="px-8 py-4 border-t border-white/[0.02] bg-[#0B0D14]/80 shrink-0">
          <div class="flex flex-col mb-4 space-y-3">
            <div class="flex items-center space-x-3">
              <input v-model="reviseInstruction"
                     type="text"
                     placeholder="输入修稿指令 (例如：把这里的对话改得更激烈一些，增加雨天的环境描写)..."
                     class="flex-1 bg-[#131620] border border-white/[0.05] rounded-lg px-4 py-2.5 text-sm text-[#8B9EB0] focus:outline-none focus:border-purple-500/50 transition-colors"
                     :disabled="isRevising"
                     @keydown.enter="triggerRevision">
              <button @click="triggerRevision"
                      :disabled="isRevising || !(reviseInstruction || '').trim()"
                      class="px-5 py-2.5 bg-[#2E3C56] hover:bg-[#3B4D6B] disabled:opacity-50 disabled:bg-gray-700 text-[#D1D5DB] rounded-lg font-bold transition-all shadow-lg flex items-center">
                <span class="mr-1">🪄</span> {{ isRevising ? '溯源重塑中...' : '织补推演' }}
              </button>
            </div>
          </div>
          <div class="flex justify-between items-center border-t border-white/[0.02] pt-4">
            <div v-if="reviseDraft && !isRevising" class="space-x-3">
              <button @click="reviseDraft = ''" class="px-4 py-2 text-sm text-[#64748B] hover:text-red-400/70 transition border border-white/10 rounded-lg">
                放弃修改
              </button>
              <button @click="acceptRevision" class="px-4 py-2 text-sm bg-[#2E3C56] hover:bg-[#3B4D6B] text-[#D1D5DB] font-bold transition rounded-lg shadow-lg">
                覆盖并应用新记忆 ✓
              </button>
            </div>
            <div v-else></div>
            <button @click="storyStore.closeChapterModal()" class="px-6 py-2 bg-[#2E3C56]/30 text-[#94A3B8] border border-white/5 rounded-lg hover:bg-[#2E3C56] hover:text-[#D1D5DB] transition font-medium">
              关闭面板
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { ref, nextTick, reactive, onMounted } from 'vue'
import { useStoryStore } from '../stores/storyStore'
import { useMemoryStore } from '../stores/memoryStore'
import { useSettingsStore } from '../stores/settingsStore'
import { startGeneration, startRevision } from '../api/stream'

const storyStore = useStoryStore()
const memoryStore = useMemoryStore()
const settingsStore = useSettingsStore()

const chatContainer = ref(null)
const generating = ref(false)
const streamingText = ref('')
const errorMessage = ref('')
const isRevising = ref(false)
const reviseInstruction = ref('')
const reviseDraft = ref('')
let abortController = null

// 全息状态呼吸灯
const sysStatus = ref('')

// 💡 文风约束弹窗
const showStyleModal = ref(false)

// 词条气泡状态 — Teleport 到 body，fixed 定位，永不遮挡
const tooltipEntry = ref(null)
const tooltipPos = ref({ top: 0, left: 0, arrowTop: 0, arrowLeft: 0, arrowRotation: '-45deg' })
const tooltipStyle = computed(() => ({
  top: tooltipPos.value.top + 'px',
  left: tooltipPos.value.left + 'px'
}))
const arrowStyle = computed(() => ({
  top: tooltipPos.value.arrowTop + 'px',
  left: tooltipPos.value.arrowLeft + 'px',
  transform: `rotate(${tooltipPos.value.arrowRotation || '-45deg'})`
}))

// 💡 150ms 滞空定时器：解决胶囊→气泡的悬浮断层
let tooltipHideTimer = null

function showTooltip(event, entry) {
  // 取消任何待销毁任务
  if (tooltipHideTimer) {
    clearTimeout(tooltipHideTimer)
    tooltipHideTimer = null
  }

  const el = event.currentTarget
  if (!el) return
  tooltipEntry.value = entry

  const rect = el.getBoundingClientRect()
  const tooltipW = 288
  const tooltipH = 320
  const gap = 12

  // 默认右侧
  let left = rect.right + gap
  let arrowLeft = -5
  let arrowRotation = '-45deg'

  // 右侧不够 → 翻到左侧
  if (left + tooltipW > window.innerWidth - 16) {
    left = rect.left - tooltipW - gap
    arrowLeft = tooltipW - 8
    arrowRotation = '135deg'
  }

  // 垂直居中，不超出视口
  let top = rect.top + rect.height / 2 - tooltipH / 2
  if (top < 8) top = 8
  if (top + tooltipH > window.innerHeight - 8) {
    top = window.innerHeight - tooltipH - 8
  }

  const arrowTop = (rect.top + rect.height / 2) - top

  tooltipPos.value = { top, left, arrowTop, arrowLeft, arrowRotation }
}

function hideTooltip() {
  // 💡 150ms 后销毁，给鼠标留出滑过缝隙的时间
  tooltipHideTimer = setTimeout(() => {
    tooltipEntry.value = null
    tooltipHideTimer = null
  }, 150)
}

function keepTooltipAlive() {
  // 💡 鼠标进入气泡，取消销毁定时器
  if (tooltipHideTimer) {
    clearTimeout(tooltipHideTimer)
    tooltipHideTimer = null
  }
}

// AI 连接状态指示器
const aiStatusDot = computed(() => {
  const bk = settingsStore.backendStatus
  const ai = settingsStore.connectionStatus
  if (bk === 'disconnected') return 'bg-red-500 shadow-red-500/60'
  if (ai === 'connected') return 'bg-emerald-500 shadow-emerald-500/60 animate-pulse'
  if (ai === 'disconnected') return 'bg-red-500 shadow-red-500/60'
  return 'bg-gray-500 shadow-gray-500/60'
})
const aiStatusLabel = computed(() => {
  const bk = settingsStore.backendStatus
  const ai = settingsStore.connectionStatus
  if (bk === 'disconnected') return '后端未连接'
  if (ai === 'connected') return `${settingsStore.activePreset === 'deepseek' ? 'DS' : '中转'} · ${settingsStore.model}`
  if (ai === 'disconnected') return 'AI 未连接'
  return '检测中...'
})
const aiStatusTooltip = computed(() => {
  const bk = settingsStore.backendStatus
  const ai = settingsStore.connectionStatus
  const name = settingsStore.activePreset === 'deepseek' ? 'DeepSeek 官方' : 'AI 中转站'
  let tip = ''
  if (bk === 'connected') {
    tip = `后端 ✓ 正常`
    if (ai === 'connected') tip += `\n${name} · ${settingsStore.model}`
    else if (ai === 'disconnected') tip += `\nAI ✗ ${settingsStore.aiError || '未连接'}`
    else tip += `\nAI 检测中...`
  } else {
    tip = `后端 ✗ ${settingsStore.backendError || '断开'}`
  }
  tip += '\n点击重新检测'
  return tip
})

// 🚀 入场即开局：进入 IDE 时自动砸出第一卷分割线并触发第一章生成
onMounted(() => {
  // 💡 读档流程由 openBook() 统一管理（大纲→章节→聊天→词条→setPhase）
  // 此处不再调用 resetMemory()，避免清空 openBook 已加载好的数据
  // 仅在新书（chatHistory 为空）时触发自动生成

  // 自动检测 AI 连接状态
  setTimeout(() => settingsStore.checkConnection(), 500)

  if (storyStore.chatHistory.length === 0 && storyStore.outlineNodes.length > 0) {
    const firstVolume = storyStore.outlineNodes[0]

    // 1. 压入第一卷的史诗分割线
    storyStore.chatHistory.push({
      id: Date.now(),
      role: 'system',
      type: 'volume_divider',
      volume: 1,
      title: firstVolume.title || '初入江湖',
      desc: firstVolume.desc || '命运的齿轮开始转动...'
    })

    // 2. 将开局指令填入输入框
    storyStore.currentDraft = `【系统指令】：请严格根据已锁定的世界观与第一卷大纲，开始撰写《${firstVolume.title || '第一章'}》的正文。要求：代入感强，遵循黄金三章原则，迅速交代主角初始状态并引出核心困境。`

    // 3. 延迟 500ms（等待分割线动画渲染），自动触发生成
    setTimeout(() => {
      submitGeneration()
    }, 500)
  }
})

const statusSteps = reactive([
  { key: 'fetch', label: '🔍 检索世界线记忆', status: 'pending' },
  { key: 'inject', label: '🧱 组装上帝视角法则', status: 'pending' },
  { key: 'generate', label: '✍️ 引擎推演中', status: 'pending' },
  { key: 'commit', label: '💾 沉淀新事实', status: 'pending' }
])

function resetSteps() {
  statusSteps.forEach(s => s.status = 'pending')
}

function setStepActive(key) {
  const step = statusSteps.find(s => s.key === key)
  if (step) step.status = 'active'
}

function setStepDone(key) {
  const step = statusSteps.find(s => s.key === key)
  if (step) step.status = 'done'
}

async function scrollToBottom() {
  await nextTick()
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}

function submitGeneration() {
  if (!String(storyStore.currentDraft || '').trim() || generating.value) return

  generating.value = true
  streamingText.value = ''
  resetSteps()

  const draftText = String(storyStore.currentDraft || '').trim()
  const triggers = draftText.match(/[\u4e00-\u9fa5]{2,}/g) || []

  const params = {
    book_id: storyStore.currentBookId,
    chapter_marker: storyStore.currentChapter,
    plot_context: storyStore.currentDraft,
    extracted_triggers: triggers,
    custom_prompt: storyStore.customPrompt  // 💡 随身携带"尚方宝剑"
  }

  abortController = startGeneration(params, {
    onMessage: (data) => {
      if (data.type === 'status') {
        sysStatus.value = data.msg || ''
        setStepDone(data.step)
        if (data.step === 'fetch') {
          memoryStore.isLoading = true
        }
        if (data.step === 'commit') {
          memoryStore.isLoading = false
        }
        scrollToBottom()
      }
      if (data.type === 'chunk') {
        streamingText.value += data.text
        scrollToBottom()
      }
      if (data.type === 'commit_done') {
        for (const entity of (data.new_entities || [])) {
          memoryStore.addNewFact({
            id: Date.now() + Math.random(),
            entity_name: entity.entry_name,
            type: entity.type,
            content: entity.content
          })
        }
        setStepDone('commit')
      }
      if (data.type === 'done') {
        sysStatus.value = ''
        const content = streamingText.value
        storyStore.appendChat(content)
        if ((content || '').trim()) {
          storyStore.saveChapter(storyStore.currentVolume, storyStore.currentChapter, content)
        }
        streamingText.value = ''
        generating.value = false
        memoryStore.isLoading = false
        storyStore.currentDraft = `【系统指令】：请紧接上文，继续撰写《第${storyStore.currentChapter}章》的剧情。要求：剧情推进紧凑，注意细节描写。`
        resetSteps()
        scrollToBottom()
        // 💡 神经反射弧：延迟 2 秒后强制刷新左侧设定字典
        // 传空字符串而非 currentDraft，避免"系统指令"等虚假触发词污染 RAG 检索
        setTimeout(() => {
          memoryStore.loadMemoryForChapter(
            storyStore.currentBookId,
            storyStore.currentChapter,
            ''
          )
        }, 2000)
      }
      if (data.type === 'error') {
        console.error('SSE error:', data.msg)
        errorMessage.value = '生成错误: ' + (data.msg || '未知错误')
        generating.value = false
        memoryStore.isLoading = false
        resetSteps()
      }
    },
    onError: (err) => {
      console.error('SSE connection error:', err)
      errorMessage.value = '生成失败: ' + err.message
      generating.value = false
      memoryStore.isLoading = false
      resetSteps()
    }
  })
}

function stopGeneration() {
  if (abortController) {
    abortController.abort()
    abortController = null
  }
  generating.value = false
  memoryStore.isLoading = false
  resetSteps()
}

const triggerRevision = async () => {
  if (!(reviseInstruction.value || '').trim()) return
  isRevising.value = true
  reviseDraft.value = ''

  const targetChapter = storyStore.viewingChapter
  const allChapters = storyStore.chapters
  const currentIndex = allChapters.findIndex(c => c.id === targetChapter.id)
  if (currentIndex === -1) {
    errorMessage.value = '章节索引异常，无法定位上下文'
    isRevising.value = false
    return
  }
  const prevContext = currentIndex > 0 ? allChapters[currentIndex - 1].content : ''
  const nextContext = currentIndex < allChapters.length - 1 ? allChapters[currentIndex + 1].content : ''

  await startRevision({
    book_id: storyStore.currentBookId,
    chapter_marker: targetChapter.chapter,
    instruction: reviseInstruction.value,
    prev_context: prevContext,
    current_content: targetChapter.content,
    next_context: nextContext
  }, {
    onChunk: (text) => {
      reviseDraft.value += text
    },
    onDone: () => {
      isRevising.value = false
    },
    onError: (err) => {
      console.error(err)
      errorMessage.value = '织补推演失败: ' + err
      isRevising.value = false
    }
  })
}

const acceptRevision = () => {
  if (reviseDraft.value) {
    storyStore.viewingChapter.content = reviseDraft.value
  }
  reviseInstruction.value = ''
  reviseDraft.value = ''
}

// 点击剧情建议卡片：智能拆包，拼接为优质指令
const applySuggestion = (suggestion) => {
  storyStore.useSuggestion(suggestion)
}
</script>
