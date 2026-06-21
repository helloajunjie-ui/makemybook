import { useSettingsStore } from '../stores/settingsStore'

const BASE = '/api'

function llmHeaders() {
  const s = useSettingsStore()
  return {
    'X-LLM-API-Key': s.apiKey,
    'X-LLM-Base-URL': s.baseUrl,
    'X-LLM-Model': s.model
  }
}

export async function fetchMemory(bookId, currentChapter, triggers) {
  const res = await fetch(`${BASE}/memory/fetch`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...llmHeaders() },
    body: JSON.stringify({ book_id: bookId, current_chapter: currentChapter, extracted_triggers: triggers })
  })
  const json = await res.json()
  return json.data
}

export async function commitMemory(data) {
  const res = await fetch(`${BASE}/memory/commit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...llmHeaders() },
    body: JSON.stringify(data)
  })
  return res.json()
}

export async function overrideFact(bookId, factId, content, isActive) {
  const res = await fetch(`${BASE}/memory/override`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...llmHeaders() },
    body: JSON.stringify({ book_id: bookId, fact_id: factId, content, is_active: isActive })
  })
  return res.json()
}

export async function listEntities(bookId) {
  const res = await fetch(`${BASE}/ui/entities?book_id=${bookId}`)
  return res.json()
}

export async function listFacts(bookId, entityId, chapter) {
  const params = new URLSearchParams()
  params.set('book_id', bookId)
  if (entityId) params.set('entity_id', entityId)
  if (chapter !== undefined) params.set('chapter', chapter)
  const res = await fetch(`${BASE}/ui/facts?${params}`)
  return res.json()
}

export async function getChapters(bookId) {
  const res = await fetch(`${BASE}/ui/chapters?book_id=${bookId}`)
  return res.json()
}
