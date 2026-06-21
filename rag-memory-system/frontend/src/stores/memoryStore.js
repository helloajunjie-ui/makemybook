import { defineStore } from 'pinia'
import { fetchMemory } from '../api/memory'

const ENTITY_TYPES = ['人物', '地点', '道具', '事件', '组织', '能力', '其他']

function emptyEntities() {
  const e = {}
  ENTITY_TYPES.forEach(t => { e[t] = [] })
  return e
}

export const useMemoryStore = defineStore('memory', {
  state: () => ({
    entities: emptyEntities(),
    newlyAddedIds: [],
    isLoading: false
  }),

  actions: {
    async loadMemoryForChapter(bookId, currentChapter, draftText = '') {
      this.isLoading = true
      try {
        const triggers = draftText.match(/[\u4e00-\u9fa5]{2,}/g) || []
        const data = await fetchMemory(bookId, currentChapter, triggers)
        // 💡 fetchMemory 返回 json.data，即 { found_entries, missing_entries }
        // 所以直接取 data.found_entries，不是 data.data.found_entries
        this.groupAndStoreEntries(data.found_entries || [])
      } catch (error) {
        console.error('记忆加载崩溃', error)
      } finally {
        this.isLoading = false
      }
    },

    groupAndStoreEntries(entries) {
      const grouped = emptyEntities()
      for (const entry of entries) {
        const type = entry.type || '其他'
        if (!grouped[type]) grouped[type] = []
        grouped[type].push(entry)
      }
      this.entities = grouped
    },

    resetMemory() {
      this.entities = emptyEntities()
      this.newlyAddedIds = []
      this.isLoading = false
    },

    addNewFact(fact) {
      const type = fact.type || '其他'
      if (!this.entities[type]) this.entities[type] = []
      // 💡 统一字段名：后端返回 entry_name，前端手动构造也用 entry_name
      this.entities[type].unshift({
        id: fact.id,
        entry_name: fact.entry_name || fact.entity_name || '未知',
        type: fact.type,
        content: fact.content,
        triggers: fact.triggers || [],
        facts: fact.content ? [{ fact_id: fact.id || '', content: fact.content, chapter_marker: fact.chapter_marker || 0 }] : []
      })
      this.newlyAddedIds.push(fact.id)
      setTimeout(() => {
        this.newlyAddedIds = this.newlyAddedIds.filter(id => id !== fact.id)
      }, 2000)
    }
  }
})
