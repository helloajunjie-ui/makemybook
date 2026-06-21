<template>
  <div v-if="settingsStore.isOpen" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-[fade-in_0.2s_ease-out]">
    <div class="w-full max-w-md bg-[#161925] border border-white/10 rounded-2xl shadow-[0_20px_60px_rgba(0,0,0,0.5)] overflow-hidden transform transition-all">
      <div class="px-6 py-4 border-b border-white/5 flex justify-between items-center bg-[#0a0c10]/50">
        <h3 class="text-lg font-bold text-gray-200 tracking-wider flex items-center">
          <span class="text-blue-500 mr-2">⚙️</span> 引擎核心配置
        </h3>
        <button @click="settingsStore.closePanel" class="text-gray-500 hover:text-white transition">✕</button>
      </div>

      <div class="p-6 space-y-5">
        <!-- 接入方式选择 -->
        <div>
          <label class="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-3">接入方式</label>
          <div class="flex space-x-2">
            <button @click="selectPreset('deepseek')"
                    :class="preset === 'deepseek' ? 'bg-blue-600 border-blue-500 text-white' : 'bg-[#0a0c10] border-white/10 text-gray-400 hover:border-blue-500 hover:text-blue-400'"
                    class="flex-1 px-3 py-2.5 border rounded-lg text-sm font-bold transition text-center">
              DeepSeek 官方
            </button>
            <button @click="selectPreset('relay')"
                    :class="preset === 'relay' ? 'bg-blue-600 border-blue-500 text-white' : 'bg-[#0a0c10] border-white/10 text-gray-400 hover:border-blue-500 hover:text-blue-400'"
                    class="flex-1 px-3 py-2.5 border rounded-lg text-sm font-bold transition text-center">
              AI 中转站
            </button>
          </div>
        </div>

        <div>
          <label class="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">API 基础地址 (Base URL)</label>
          <input v-model="tempUrl" type="text" class="w-full bg-[#0a0c10] border border-white/10 rounded-lg p-2.5 text-sm text-gray-200 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition" :placeholder="preset === 'deepseek' ? 'https://api.deepseek.com' : 'https://your-relay.com/v1'" />
        </div>

        <!-- DeepSeek 模式：手动输入模型 -->
        <div v-if="preset === 'deepseek'">
          <label class="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">模型名称 (Model)</label>
          <input v-model="tempModel" type="text" class="w-full bg-[#0a0c10] border border-white/10 rounded-lg p-2.5 text-sm text-gray-200 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition" placeholder="deepseek-chat" />
        </div>

        <!-- 中转站模式：下拉选择模型 -->
        <div v-if="preset === 'relay'">
          <label class="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">模型名称 (Model)</label>
          <div class="flex space-x-2">
            <select v-model="tempModel"
                    class="flex-1 bg-[#0a0c10] border border-white/10 rounded-lg p-2.5 text-sm text-gray-200 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition appearance-none">
              <option value="" disabled>-- 请先获取模型列表 --</option>
              <option v-for="m in modelList" :key="m" :value="m">{{ m }}</option>
            </select>
            <button @click="fetchModels"
                    :disabled="isFetching"
                    class="px-3 py-2.5 bg-[#0a0c10] border border-white/10 rounded-lg text-sm text-gray-400 hover:text-blue-400 hover:border-blue-500 transition whitespace-nowrap disabled:opacity-40">
              {{ isFetching ? '获取中...' : '获取模型' }}
            </button>
          </div>
          <p v-if="fetchError" class="text-xs text-red-400 mt-2">{{ fetchError }}</p>
        </div>

        <div>
          <label class="block text-xs font-bold text-gray-500 uppercase tracking-wider mb-2">API 密钥 (API Key)</label>
          <input v-model="tempKey" type="password" class="w-full bg-[#0a0c10] border border-white/10 rounded-lg p-2.5 text-sm text-gray-200 focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition font-mono" placeholder="sk-..." />
          <p class="text-xs text-gray-500 mt-2">密钥仅保存在您的浏览器本地，绝不上传至服务器。</p>
        </div>
      </div>

      <div class="px-6 py-4 border-t border-white/5 bg-[#0a0c10]/50 flex justify-between items-center">
        <p class="text-xs text-gray-600">技术支持 QQ 群：<span class="text-blue-500">1051068329</span> | 作者：尼可</p>
        <div class="flex space-x-3">
          <button @click="settingsStore.closePanel" class="px-4 py-2 text-sm text-gray-400 hover:text-white transition">取消</button>
          <button @click="save" class="px-6 py-2 text-sm bg-blue-600 hover:bg-blue-500 text-white rounded-lg shadow-lg shadow-blue-600/20 transition font-bold">
            连接引擎
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useSettingsStore } from '../stores/settingsStore'

const settingsStore = useSettingsStore()
const tempUrl = ref('')
const tempModel = ref('')
const tempKey = ref('')
const preset = ref('deepseek')
const modelList = ref([])
const isFetching = ref(false)
const fetchError = ref('')

function loadFromLS(name) {
  const key = name === 'deepseek' ? 'llm_deepseek' : 'llm_relay'
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return {}
    return JSON.parse(raw)
  } catch {
    return {}
  }
}

function applyPresetToUI(name) {
  preset.value = name
  const cfg = loadFromLS(name)
  tempKey.value = cfg.apiKey || ''
  tempUrl.value = cfg.baseUrl || (name === 'deepseek' ? 'https://api.deepseek.com' : '')
  tempModel.value = cfg.model || (name === 'deepseek' ? 'deepseek-chat' : '')
}

function selectPreset(name) {
  settingsStore.switchPreset(name)
  applyPresetToUI(name)
}

async function fetchModels() {
  if (!tempUrl.value || !tempKey.value) {
    fetchError.value = '请先填写 API 地址和密钥'
    return
  }
  isFetching.value = true
  fetchError.value = ''
  modelList.value = []
  try {
    const res = await fetch(`${tempUrl.value.replace(/\/+$/, '')}/models`, {
      headers: { 'Authorization': `Bearer ${tempKey.value}` }
    })
    if (!res.ok) {
      const text = await res.text()
      throw new Error(`HTTP ${res.status}: ${text.slice(0, 80)}`)
    }
    const json = await res.json()
    const models = (json.data || []).map(m => m.id || m)
    modelList.value = models.filter(id => {
      const lower = id.toLowerCase()
      return !lower.includes('whisper') && !lower.includes('tts') && !lower.includes('embedding')
    })
    if (modelList.value.length > 0) {
      tempModel.value = modelList.value[0]
    } else {
      fetchError.value = '未找到可用的文本模型'
    }
  } catch (err) {
    fetchError.value = '获取模型列表失败: ' + (err.message || '未知错误')
  } finally {
    isFetching.value = false
  }
}

watch(() => settingsStore.isOpen, (newVal) => {
  if (newVal) {
    const active = localStorage.getItem('llm_active') || 'deepseek'
    applyPresetToUI(active)
    modelList.value = []
    fetchError.value = ''
  }
})

const save = () => {
  const name = preset.value
  const lsKey = name === 'deepseek' ? 'llm_deepseek' : 'llm_relay'
  const data = { apiKey: tempKey.value, baseUrl: tempUrl.value, model: tempModel.value }
  localStorage.setItem(lsKey, JSON.stringify(data))
  localStorage.setItem('llm_active', name)
  settingsStore.activePreset = name
  settingsStore.apiKey = tempKey.value
  settingsStore.baseUrl = tempUrl.value
  settingsStore.model = tempModel.value
  if (name === 'deepseek') {
    settingsStore.dsApiKey = tempKey.value
    settingsStore.dsBaseUrl = tempUrl.value
    settingsStore.dsModel = tempModel.value
  } else {
    settingsStore.relayApiKey = tempKey.value
    settingsStore.relayBaseUrl = tempUrl.value
    settingsStore.relayModel = tempModel.value
  }
  settingsStore.saveToDb()
  settingsStore.isOpen = false
  settingsStore.checkConnection()
}
</script>
