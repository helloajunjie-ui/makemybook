import { useSettingsStore } from '../stores/settingsStore'

const BASE = '/api/stream'

function llmHeaders() {
  const s = useSettingsStore()
  return {
    'X-LLM-API-Key': s.apiKey,
    'X-LLM-Base-URL': s.baseUrl,
    'X-LLM-Model': s.model
  }
}

function friendlyFetchError(err) {
  const msg = (err.message || '').toLowerCase()
  if (msg.includes('failed to fetch') || msg.includes('networkerror') || msg.includes('network error') || msg.includes('load failed')) {
    return '无法连接到服务器，请检查后端服务是否启动或网络连接是否正常'
  }
  if (msg.includes('abort') || msg.includes('timeout')) {
    return '请求超时或被中断，请重试'
  }
  return err.message || '未知网络错误'
}

export function startGeneration(params, handlers) {
  const controller = new AbortController()

  fetch(`${BASE}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...llmHeaders() },
    body: JSON.stringify(params),
    signal: controller.signal
  }).then(async (response) => {
    if (!response.ok) {
      const errBody = await response.text()
      throw new Error(`HTTP ${response.status}: ${errBody}`)
    }
    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const dataStr = line.slice(6)
        try {
          const data = JSON.parse(dataStr)
          handlers.onMessage?.(data)
        } catch {
          // skip malformed
        }
      }
    }
  }).catch((err) => {
    if (err.name !== 'AbortError') {
      err.message = friendlyFetchError(err)
      handlers.onError?.(err)
    }
  })

  return controller
}

export async function fetchSuggestions(recentContext) {
  const res = await fetch(`${BASE}/suggest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...llmHeaders() },
    body: JSON.stringify({ recent_context: recentContext })
  })
  return res.json()
}

export async function startRevision(params, handlers) {
  try {
    const response = await fetch(`${BASE}/revise`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...llmHeaders() },
      body: JSON.stringify(params)
    })

    if (!response.ok) throw new Error('网络响应异常')

    const reader = response.body.getReader()
    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop()

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const jsonStr = line.substring(6).trim()
          if (!jsonStr) continue
          const data = JSON.parse(jsonStr)

          if (data.type === 'chunk' && handlers.onChunk) {
            handlers.onChunk(data.text)
          } else if (data.type === 'done' && handlers.onDone) {
            handlers.onDone()
          } else if (data.type === 'error' && handlers.onError) {
            handlers.onError(data.message)
          }
        }
      }
    }
  } catch (error) {
    if (handlers.onError) handlers.onError(friendlyFetchError(error))
  }
}
