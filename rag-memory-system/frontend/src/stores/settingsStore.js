import { defineStore } from 'pinia'

const DEEPSEEK_KEY = 'llm_deepseek'
const RELAY_KEY = 'llm_relay'

function loadPreset(key) {
  try {
    return JSON.parse(localStorage.getItem(key)) || {}
  } catch {
    return {}
  }
}

function savePreset(key, data) {
  localStorage.setItem(key, JSON.stringify(data))
}

export const useSettingsStore = defineStore('settings', {
  state: () => {
    const active = localStorage.getItem('llm_active') || 'deepseek'
    const ds = loadPreset(DEEPSEEK_KEY)
    const relay = loadPreset(RELAY_KEY)
    const cfg = active === 'relay' ? relay : ds
    return {
      isOpen: false,
      activePreset: active,
      dsApiKey: ds.apiKey || '',
      dsBaseUrl: ds.baseUrl || 'https://api.deepseek.com',
      dsModel: ds.model || 'deepseek-chat',
      relayApiKey: relay.apiKey || '',
      relayBaseUrl: relay.baseUrl || '',
      relayModel: relay.model || '',
      apiKey: cfg.apiKey || '',
      baseUrl: cfg.baseUrl || (active === 'deepseek' ? 'https://api.deepseek.com' : ''),
      model: cfg.model || (active === 'deepseek' ? 'deepseek-chat' : ''),
      backendStatus: 'unknown',
      connectionStatus: 'unknown',
      backendError: '',
      aiError: '',
    }
  },
  actions: {
    openPanel() { this.isOpen = true },
    closePanel() { this.isOpen = false },
    switchPreset(name) {
      this.activePreset = name
      localStorage.setItem('llm_active', name)
      const cfg = loadPreset(name === 'deepseek' ? DEEPSEEK_KEY : RELAY_KEY)
      this.apiKey = cfg.apiKey || ''
      this.baseUrl = cfg.baseUrl || (name === 'deepseek' ? 'https://api.deepseek.com' : '')
      this.model = cfg.model || (name === 'deepseek' ? 'deepseek-chat' : '')
    },
    async loadFromDb() {
      try {
        const res = await fetch('/api/settings/load')
        if (!res.ok) return
        const data = await res.json()
        if (!data.presets || data.presets.length === 0) return
        for (const p of data.presets) {
          const lsKey = p.preset_name === 'deepseek' ? DEEPSEEK_KEY : RELAY_KEY
          savePreset(lsKey, { apiKey: p.api_key, baseUrl: p.base_url, model: p.model })
          if (p.preset_name === 'deepseek') {
            this.dsApiKey = p.api_key
            this.dsBaseUrl = p.base_url
            this.dsModel = p.model
          } else {
            this.relayApiKey = p.api_key
            this.relayBaseUrl = p.base_url
            this.relayModel = p.model
          }
        }
        this.activePreset = data.active_preset
        localStorage.setItem('llm_active', data.active_preset)
        const activeCfg = data.presets.find(p => p.preset_name === data.active_preset)
        if (activeCfg) {
          this.apiKey = activeCfg.api_key
          this.baseUrl = activeCfg.base_url
          this.model = activeCfg.model
        }
      } catch {
        // fallback to localStorage
      }
    },
    async saveToDb() {
      const presets = [
        { preset_name: 'deepseek', api_key: this.dsApiKey, base_url: this.dsBaseUrl, model: this.dsModel },
        { preset_name: 'relay', api_key: this.relayApiKey, base_url: this.relayBaseUrl, model: this.relayModel },
      ]
      try {
        await fetch('/api/settings/save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ active_preset: this.activePreset, presets }),
        })
      } catch {
        // silent
      }
    },
    async checkConnection() {
      this.backendError = ''
      this.aiError = ''
      try {
        const healthRes = await fetch('/health', { signal: AbortSignal.timeout(3000) })
        this.backendStatus = healthRes.ok ? 'connected' : 'disconnected'
        if (!healthRes.ok) this.backendError = '程序异常，请重启软件'
      } catch {
        this.backendStatus = 'disconnected'
        this.backendError = '程序未启动，请重启软件'
      }
      if (!this.apiKey) {
        this.connectionStatus = 'disconnected'
        this.aiError = '未配置 AI，请打开⚙️设置'
        return
      }
      try {
        const res = await fetch(`${this.baseUrl.replace(/\/+$/, '')}/models`, {
          headers: { 'Authorization': `Bearer ${this.apiKey}` },
          signal: AbortSignal.timeout(5000)
        })
        this.connectionStatus = res.ok ? 'connected' : 'disconnected'
        if (!res.ok) this.aiError = 'AI 连接失败，请检查 API Key 或地址'
      } catch {
        this.connectionStatus = 'disconnected'
        this.aiError = 'AI 连接失败，请检查网络或 API 地址'
      }
    }
  }
})
