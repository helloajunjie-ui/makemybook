<template>
  <div class="h-screen w-screen bg-[#0a0c10] text-gray-100 flex flex-col relative overflow-hidden selection:bg-blue-500/30">

    <!-- 背景氛围光 -->
    <div class="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-blue-600/10 rounded-full blur-[120px] pointer-events-none"></div>

    <!-- 顶栏 -->
    <header class="relative z-10 flex items-center justify-between px-8 py-6">
      <h1 class="text-2xl font-black tracking-widest text-transparent bg-clip-text bg-gradient-to-r from-gray-100 to-gray-400">
        青羽·灵感裂变室
      </h1>
      <button @click="storyStore.setPhase('library')" class="text-gray-500 hover:text-gray-300 text-sm transition">
        返回宇宙大厅 ✕
      </button>
    </header>

    <!-- 主体区域 -->
    <main class="flex-1 flex flex-col items-center relative z-10 overflow-y-auto custom-scrollbar px-8 pb-40">

      <!-- 状态 1：初始输入状态 -->
      <div v-if="storyStore.pitches.length === 0" class="w-full max-w-3xl mt-32 flex flex-col items-center animate-[fade-in_0.4s_ease-out]">
        <h2 class="text-3xl font-bold mb-8 text-gray-200">定义这个世界的起点</h2>
        <div class="w-full relative group">
          <textarea
            v-model="seedInput"
            placeholder="输入你的灵感，例如：背景设定在繁华却暗流涌动的现代东京。我表面上是个普通大学生，实际上是专门解决超自然都市传说事件的灵探..."
            class="w-full h-40 bg-[#161925]/80 backdrop-blur border border-white/10 rounded-2xl p-6 text-lg text-gray-200 focus:outline-none focus:border-blue-500/50 focus:ring-4 focus:ring-blue-500/10 resize-none transition-all shadow-xl"
          ></textarea>
          <button @click="crackIdeas" :disabled="isCracking"
            class="absolute bottom-6 right-6 px-6 py-2 bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-500 hover:to-blue-400 text-white rounded-xl font-bold transition-all shadow-[0_0_15px_rgba(37,99,235,0.4)] disabled:opacity-50 disabled:cursor-not-allowed">
            {{ isCracking ? '🧠 裂变推演中...' : '✦ 启动世界裂变' }}
          </button>
        </div>
      </div>

      <!-- 状态 2：变体卡片展示区 -->
      <div v-else class="w-full max-w-6xl mt-8">
        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 animate-[fade-in-up_0.5s_ease-out]">
          <div v-for="(pitch, index) in storyStore.pitches" :key="pitch.id"
               class="group bg-[#161925]/60 backdrop-blur-md border border-white/5 hover:border-blue-500/40 rounded-2xl flex flex-col transition-all shadow-lg hover:shadow-[0_10px_30px_rgba(37,99,235,0.1)]">

            <!-- 卡片头部信息 -->
            <div class="p-6 pb-4">
              <div class="text-xs font-mono text-emerald-400 mb-3 border border-emerald-900 bg-emerald-900/20 inline-block px-2 py-0.5 rounded uppercase tracking-wider">
                {{ pitch.tone }}
              </div>
              <h3 class="text-2xl font-bold text-gray-100 mb-3">{{ pitch.title }}</h3>
              <p class="text-sm text-gray-400 leading-relaxed">{{ pitch.summary }}</p>
            </div>

            <!-- 底部操作栏 -->
            <div class="mt-auto p-4 border-t border-white/5 flex gap-2 bg-[#0a0c10]/30 rounded-b-2xl">
              <button @click="storyStore.generateOutline(pitch.id)"
                      class="flex-1 bg-blue-600/20 hover:bg-blue-600 border border-blue-600/50 text-blue-300 hover:text-white rounded-lg py-2 text-sm font-bold transition-colors">
                U{{ index + 1 }} 敲定骨架
              </button>
              <button @click="setVariantTarget(pitch)"
                      class="px-4 bg-[#161925] hover:bg-[#1a2035] border border-white/10 text-gray-300 hover:text-white rounded-lg text-sm transition-colors shadow-inner"
                      title="对这个方向不满意？点击基于它提出修改建议">
                V{{ index + 1 }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </main>

    <!-- 底部的反馈迭代悬浮舱 (Iteration Dock) -->
    <div v-if="storyStore.pitches.length > 0"
         class="absolute bottom-0 left-0 w-full pt-12 pb-6 px-8 bg-gradient-to-t from-[#0a0c10] via-[#0a0c10]/95 to-transparent z-20 pointer-events-none">
      <div class="max-w-4xl mx-auto w-full pointer-events-auto bg-[#161925]/90 backdrop-blur-xl border border-white/10 rounded-2xl p-4 shadow-[0_-10px_40px_rgba(0,0,0,0.3)]">

        <!-- 目标指示器 -->
        <div v-if="variantTarget" class="mb-3 flex items-center justify-between bg-blue-900/20 border border-blue-500/30 px-3 py-1.5 rounded-lg text-xs text-blue-300">
          <span>✨ 正在基于 <strong>{{ variantTarget.title }}</strong> 推演变体方向</span>
          <button @click="variantTarget = null" class="hover:text-white">✕ 取消</button>
        </div>

        <div class="relative flex items-center">
          <textarea
            v-model="feedbackInput"
            id="feedback-input"
            :placeholder="variantTarget ? '输入微调建议（例如：金手指太强了，削弱一点）...' : '对这三个都不满意？输入修改建议，重新裂变...'"
            class="w-full h-12 bg-[#0a0c10]/50 border border-white/5 rounded-xl p-3 pr-32 text-sm text-gray-200 focus:outline-none focus:border-blue-500/50 resize-none transition-all"
            @keydown.enter.prevent="submitFeedback"
          ></textarea>

          <button @click="submitFeedback" :disabled="isCracking"
                  class="absolute right-2 top-2 bottom-2 px-4 bg-gray-800 hover:bg-gray-700 text-gray-200 rounded-lg text-sm font-bold transition-all flex items-center disabled:opacity-50">
            {{ isCracking ? '推演中...' : (variantTarget ? '生成变体' : '全部重做') }} 🔄
          </button>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, nextTick } from 'vue'
import { useStoryStore } from '../stores/storyStore'

const storyStore = useStoryStore()
const seedInput = ref('')
const feedbackInput = ref('')
const isCracking = ref(false)
const variantTarget = ref(null)

const crackIdeas = async () => {
  if (!seedInput.value.trim()) return
  isCracking.value = true
  await storyStore.generatePitches(seedInput.value)
  isCracking.value = false
}

const setVariantTarget = (pitch) => {
  variantTarget.value = pitch
  feedbackInput.value = ''
  nextTick(() => {
    document.getElementById('feedback-input').focus()
  })
}

const submitFeedback = async () => {
  isCracking.value = true
  const contextText = feedbackInput.value.trim() || (variantTarget.value ? '请生成其他变体' : '请重新生成完全不同的方向')
  await storyStore.generatePitches(contextText, !!variantTarget.value, variantTarget.value)
  isCracking.value = false
  feedbackInput.value = ''
  variantTarget.value = null
}
</script>

<style scoped>
@keyframes fade-in-up {
  0% { opacity: 0; transform: translateY(20px); }
  100% { opacity: 1; transform: translateY(0); }
}
</style>
