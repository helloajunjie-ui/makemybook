<template>
  <div class="editor-panel">
    <div class="editor-toolbar">
      <div class="toolbar-left">
        <span class="toolbar-title">剧本渲染区</span>
        <span class="chapter-badge">第 {{ editorStore.currentChapter }} 章</span>
      </div>
      <div class="toolbar-right">
        <button class="toolbar-btn" @click="showTriggerInput = !showTriggerInput">触发词</button>
        <button class="toolbar-btn primary" @click="doGenerate" :disabled="generating">
          {{ generating ? '生成中...' : '生成正文' }}
        </button>
      </div>
    </div>

    <div v-if="showTriggerInput" class="trigger-bar">
      <input v-model="editorStore.triggerInput" placeholder="输入触发词，逗号分隔，如：张三, 青云城" class="trigger-input" />
    </div>

    <div class="editor-content" ref="contentRef">
      <div v-if="!editorStore.generatedText" class="editor-placeholder">
        <div class="placeholder-icon">✍</div>
        <div class="placeholder-text">输入触发词，点击"生成正文"开始创作</div>
        <div class="placeholder-hint">系统将自动召回记忆并注入设定约束</div>
      </div>
      <div v-else class="editor-text" v-html="renderedText"></div>
    </div>

    <div class="editor-footer">
      <div class="footer-info">
        <span>已生成 {{ editorStore.conversationHistory.length }} 段</span>
      </div>
      <div class="footer-actions">
        <button class="toolbar-btn" @click="clearText">清空</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useMemoryStore } from '../stores/memory.js'

const memoryStore = useMemoryStore()

const showTriggerInput = ref(true)
const generating = ref(false)
const contentRef = ref(null)

const renderedText = computed(() => {
  const text = editorStore.generatedText
  const triggers = memoryStore.foundEntries.map(e => e.entry_name)
  if (!triggers.length) return text.replace(/\n/g, '<br>')

  let result = text
  for (const t of triggers) {
    const re = new RegExp(`(${t})`, 'g')
    result = result.replace(re, '<span class="highlight-trigger">$1</span>')
  }
  return result.replace(/\n/g, '<br>')
})

async function doGenerate() {
  generating.value = true
  const triggers = editorStore.triggerInput
    .split(',')
    .map(s => s.trim())
    .filter(Boolean)

  if (triggers.length) {
    await memoryStore.doFetch(editorStore.currentChapter, triggers)
  }

  generating.value = false
}

function clearText() {
  editorStore.generatedText = ''
  editorStore.conversationHistory.value = []
}
</script>

<style scoped>
.editor-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #0f0f1a;
}

.editor-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 20px;
  border-bottom: 1px solid #2a2a3e;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.toolbar-title {
  font-size: 14px;
  font-weight: 600;
  color: #8888aa;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.chapter-badge {
  font-size: 12px;
  background: #252540;
  color: #7ecfff;
  padding: 2px 10px;
  border-radius: 12px;
}

.toolbar-right {
  display: flex;
  gap: 8px;
}

.toolbar-btn {
  background: #252540;
  color: #c0c0d0;
  border: 1px solid #3a3a5e;
  padding: 6px 16px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}

.toolbar-btn:hover {
  background: #2e2e4e;
}

.toolbar-btn.primary {
  background: #3a6ea5;
  color: #fff;
  border: none;
}

.toolbar-btn.primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.trigger-bar {
  padding: 8px 20px;
  border-bottom: 1px solid #2a2a3e;
}

.trigger-input {
  width: 100%;
  background: #1a1a2e;
  border: 1px solid #3a3a5e;
  color: #e0e0e0;
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 13px;
}

.editor-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px 20px;
}

.editor-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #555577;
}

.placeholder-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.placeholder-text {
  font-size: 16px;
  margin-bottom: 8px;
}

.placeholder-hint {
  font-size: 13px;
}

.editor-text {
  font-size: 15px;
  line-height: 1.9;
  color: #e0e0e0;
}

.editor-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 20px;
  border-top: 1px solid #2a2a3e;
}

.footer-info {
  font-size: 12px;
  color: #555577;
}

.footer-actions {
  display: flex;
  gap: 8px;
}
</style>
