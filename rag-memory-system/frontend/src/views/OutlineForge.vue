<template>
  <div class="h-screen w-screen bg-[#111] flex flex-col text-gray-200 overflow-hidden">
    <header class="h-16 flex items-center justify-between px-8 bg-gray-900 border-b border-gray-800 shrink-0">
      <div class="flex items-center space-x-4">
        <button @click="storyStore.setPhase('pitch')" class="text-gray-500 hover:text-white transition">← 返回重选</button>
        <span class="text-gray-600">|</span>
        <h2 class="font-bold text-lg">世界大纲铸造：<span class="text-blue-400">{{ storyStore.selectedPitch?.title }}</span></h2>
      </div>
      <button @click="enterIDE" :disabled="storyStore.outlineNodes.length === 0" class="px-6 py-2 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-lg font-bold shadow-[0_0_15px_rgba(37,99,235,0.4)] transition-all">
        进入共创 IDE 🚀
      </button>
    </header>

    <main class="flex-1 overflow-y-auto p-12 flex justify-center">
      <div class="w-full max-w-3xl relative">
        <div class="absolute left-[27px] top-4 bottom-4 w-1 bg-gray-800 rounded-full"></div>

        <div v-for="(node, index) in storyStore.outlineNodes" :key="node.id" class="relative pl-20 mb-10 group">
          <div class="absolute left-4 top-2 w-8 h-8 rounded-full border-4 border-gray-900 flex items-center justify-center font-bold text-xs transition-colors"
               :class="node.status === 'active' ? 'bg-blue-500 text-white' : 'bg-gray-700 text-gray-400 group-hover:bg-gray-600'">
            {{ index + 1 }}
          </div>

          <div class="bg-gray-800/50 border border-gray-700/60 rounded-xl p-5 hover:border-gray-500 transition-colors">
            <div class="flex items-center justify-between mb-2">
              <input v-model="node.title" class="bg-transparent text-xl font-bold text-blue-300 focus:outline-none focus:border-b border-blue-500 w-2/3 pb-1" />
              <span class="text-xs font-mono text-gray-500 bg-gray-900 px-2 py-1 rounded">第 {{ node.volume }} 卷</span>
            </div>
            <textarea v-model="node.desc" placeholder="卷宗核心目标与剧情走向..." class="w-full h-16 bg-transparent text-sm text-gray-400 focus:outline-none focus:text-gray-200 resize-none mt-2"></textarea>
          </div>
        </div>

        <button class="relative pl-20 text-gray-500 hover:text-blue-400 flex items-center transition-colors font-medium">
          <div class="absolute left-[18px] w-6 h-6 rounded-full bg-gray-800 border border-dashed border-gray-500 flex items-center justify-center">+</div>
          衍生新篇章 (Add Volume)
        </button>
      </div>
    </main>
  </div>
</template>

<script setup>
import { useStoryStore } from '../stores/storyStore'

const storyStore = useStoryStore()

async function enterIDE() {
  if (storyStore.outlineNodes.length === 0) return

  // 如果还没有 book_id，先创建 Book
  if (!storyStore.currentBookId) {
    try {
      const res = await fetch('/api/books/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: storyStore.selectedPitch?.title || '未命名世界',
          summary: storyStore.selectedPitch?.desc || ''
        })
      })
      if (!res.ok) {
        const errBody = await res.text()
        alert('创建 Book 失败: ' + errBody)
        return
      }
      const book = await res.json()
      storyStore.currentBookId = book.id
    } catch (error) {
      console.error('创建 Book 失败', error)
      alert('创建 Book 失败: ' + error.message)
      return
    }
  }

  storyStore.setPhase('ide')
}
</script>
