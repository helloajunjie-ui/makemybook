<template>
  <div class="h-screen w-screen bg-[#0a0c10] text-gray-100 overflow-y-auto selection:bg-blue-500/30 relative">

    <!-- 背景氛围光晕 -->
    <div class="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-blue-600/10 rounded-full blur-[120px] pointer-events-none"></div>

    <div class="max-w-6xl mx-auto px-8 pt-16 pb-24 relative z-10">

      <!-- 顶部控制台 -->
      <header class="flex justify-between items-end mb-16 border-b border-white/10 pb-6">
        <div>
          <h1 class="text-5xl font-black tracking-widest text-transparent bg-clip-text bg-gradient-to-r from-gray-100 to-gray-400 drop-shadow-lg mb-2">
            青羽·织梦宇宙
          </h1>
          <p class="text-gray-500 tracking-wide">选择一个世界，或创造新的历史。</p>
        </div>

        <div class="flex items-center space-x-4">
          <!-- AI 连接状态 -->
          <div @click="settingsStore.checkConnection()"
               :title="statusTooltip"
               class="flex items-center px-3 py-2.5 bg-[#161925] border border-white/10 rounded-xl text-xs cursor-pointer hover:border-blue-500/50 transition-all shadow-lg">
            <span :class="statusDotClass" class="w-2 h-2 rounded-full mr-2 shadow-[0_0_8px_var(--tw-shadow-color)]"></span>
            <span class="text-gray-400">{{ statusLabel }}</span>
          </div>

          <button @click="settingsStore.openPanel()"
                  class="flex items-center px-4 py-2.5 bg-[#161925] border border-white/10 hover:border-blue-500 hover:text-blue-400 text-gray-400 rounded-xl transition-all shadow-lg">
            <span class="mr-2">⚙️</span> 引擎配置
          </button>

          <button @click="storyStore.startNewBook()"
                  class="flex items-center px-6 py-2.5 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white rounded-xl font-bold transition-all shadow-[0_0_20px_rgba(37,99,235,0.4)] hover:shadow-[0_0_30px_rgba(37,99,235,0.6)] transform hover:-translate-y-0.5">
            <span class="mr-2 text-lg">+</span> 开辟新世界
          </button>
        </div>
      </header>

      <!-- 书架网格 -->
      <div v-if="storyStore.bookshelf && storyStore.bookshelf.length > 0" class="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-8">
        <div v-for="book in storyStore.bookshelf" :key="book.id"
             class="group relative h-80 rounded-2xl overflow-hidden cursor-pointer border border-white/5 hover:border-blue-500/50 transition-all shadow-xl hover:shadow-[0_10px_40px_rgba(37,99,235,0.15)] transform hover:-translate-y-1">
          <div @click="storyStore.openBook(book.id, book.title)" class="absolute inset-0 bg-gradient-to-br from-[#161925] to-[#0f111a] group-hover:scale-105 transition-transform duration-700"></div>
          <div @click="storyStore.openBook(book.id, book.title)" class="absolute inset-0 p-6 flex flex-col justify-end bg-gradient-to-t from-[#0a0c10] via-[#0a0c10]/80 to-transparent">
            <h3 class="text-2xl font-bold mb-3 text-gray-200 group-hover:text-blue-400 transition-colors">{{ book.title }}</h3>
            <p class="text-sm text-gray-400 line-clamp-3 leading-relaxed mb-4">{{ book.summary }}</p>
            <div class="flex items-center text-xs text-gray-500 font-mono">
              <span class="w-2 h-2 rounded-full bg-emerald-500 mr-2 shadow-[0_0_8px_rgba(16,185,129,0.6)] animate-pulse"></span>
              ID: {{ book.id.substring(0, 8) }}
            </div>
          </div>
          <button @click.stop="deleteBook(book)"
                  class="absolute top-3 right-3 w-8 h-8 rounded-full bg-red-900/60 border border-red-700/50 text-red-300 hover:bg-red-700 hover:text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-all text-sm"
                  title="删除此书">✕</button>
        </div>
      </div>

      <!-- 空状态展示 -->
      <div v-else class="w-full py-32 flex flex-col items-center justify-center border-2 border-dashed border-white/5 rounded-3xl bg-[#161925]/30">
        <div class="text-6xl mb-6 opacity-50">🌌</div>
        <h3 class="text-xl font-bold text-gray-400 mb-2">宇宙尚处在混沌之中</h3>
        <p class="text-gray-500 text-sm mb-6">点击右上角配置引擎，然后开辟你的第一个世界。</p>
      </div>

      <!-- 技术支持 -->
      <footer class="mt-16 pt-6 border-t border-white/5 text-center">
        <p class="text-xs text-gray-600">技术支持 QQ 群：<a href="https://qm.qq.com/q/1051068329" target="_blank" class="text-blue-500 hover:text-blue-400 transition">1051068329</a> | 作者：尼可</p>
      </footer>

    </div>
  </div>
</template>

<script setup>
import { onMounted, computed } from 'vue'
import { useStoryStore } from '../stores/storyStore'
import { useSettingsStore } from '../stores/settingsStore'

const storyStore = useStoryStore()
const settingsStore = useSettingsStore()

const statusDotClass = computed(() => {
  const bk = settingsStore.backendStatus
  const ai = settingsStore.connectionStatus
  if (bk === 'disconnected') return 'bg-red-500 shadow-red-500/60'
  if (ai === 'connected') return 'bg-emerald-500 shadow-emerald-500/60 animate-pulse'
  if (ai === 'disconnected') return 'bg-red-500 shadow-red-500/60'
  return 'bg-gray-500 shadow-gray-500/60'
})

const statusLabel = computed(() => {
  const bk = settingsStore.backendStatus
  const ai = settingsStore.connectionStatus
  if (bk === 'disconnected') return '后端未连接'
  if (ai === 'connected') return `${settingsStore.activePreset === 'deepseek' ? 'DS' : '中转'} · ${settingsStore.model}`
  if (ai === 'disconnected') return 'AI 未连接'
  return '检测中...'
})

const statusTooltip = computed(() => {
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

onMounted(() => {
  if (storyStore.loadBookshelf) {
    storyStore.loadBookshelf()
  }
  // 页面加载后自动检测连接
  setTimeout(() => settingsStore.checkConnection(), 500)
})

async function deleteBook(book) {
  if (!confirm(`确定要删除《${book.title}》吗？\n此操作不可恢复，所有相关记忆数据将被永久清除。`)) return
  try {
    await storyStore.deleteBook(book.id)
  } catch (err) {
    alert('删除失败: ' + err.message)
  }
}
</script>
