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
        this.groupAndStoreEntries(data.data.found_entries || [])
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

    addNewFact(fact) {
      const type = fact.type || '其他'
      if (!this.entities[type]) this.entities[type] = []
      this.entities[type].unshift(fact)
      this.newlyAddedIds.push(fact.id)
      setTimeout(() => {
        this.newlyAddedIds = this.newlyAddedIds.filter(id => id !== fact.id)
      }, 2000)
    }
  }
})
