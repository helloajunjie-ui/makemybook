import { defineStore } from 'pinia'
import { useSettingsStore } from './settingsStore'

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

const fetchWithBYOK = async (url, bodyData) => {
  const settings = useSettingsStore()
  let res
  try {
    res = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-LLM-API-Key': settings.apiKey,
        'X-LLM-Base-URL': settings.baseUrl,
        'X-LLM-Model': settings.model
      },
      body: JSON.stringify(bodyData)
    })
  } catch (err) {
    throw new Error(friendlyFetchError(err))
  }
  if (!res.ok) {
    const errBody = await res.text()
    throw new Error(`HTTP ${res.status}: ${errBody}`)
  }
  return res.json()
}

export const useStoryStore = defineStore('story', {
  state: () => ({
    currentPhase: 'library',
    currentBookId: null,
    currentPitchId: null,
    bookshelf: [],
    promptSeed: '',
    pitches: [],
    selectedPitch: null,
    currentChapter: 1,
    currentVolume: 1,
    outlineNodes: [],
    chatHistory: [],
    plotSuggestions: [],
    isSuggesting: false,
    currentDraft: '',
    isGeneratingOutline: false,
    chapters: [],
    viewingChapter: null
  }),

  getters: {
    isLibraryPhase: (state) => state.currentPhase === 'library',
    isPitchPhase: (state) => state.currentPhase === 'pitch',
    isOutlinePhase: (state) => state.currentPhase === 'outline',
    isIdePhase: (state) => state.currentPhase === 'ide'
  },

  actions: {
    setPhase(phase) {
      this.currentPhase = phase
    },

    async loadBookshelf() {
      try {
        const res = await fetch('/api/books/')
        this.bookshelf = await res.json()
      } catch {
        this.bookshelf = []
      }
    },

    async deleteBook(bookId) {
      const res = await fetch(`/api/books/${bookId}`, { method: 'DELETE' })
      if (!res.ok) {
        const errBody = await res.text()
        throw new Error(`HTTP ${res.status}: ${errBody}`)
      }
      this.bookshelf = this.bookshelf.filter(b => b.id !== bookId)
    },

    async openBook(bookId, bookTitle) {
      this.currentBookId = bookId
      try {
        const pitchRes = await fetch('/api/pitch/list')
        if (pitchRes.ok) {
          const pitches = await pitchRes.json()
          const match = pitches.find(p => p.title === bookTitle)
          if (match) {
            this.currentPitchId = match.id
            this.selectedPitch = match
          }
        }
      } catch {
        // 静默
      }
      await this.loadOutlineFromDb()
      await this.loadChaptersFromDb()
      await this.loadChatHistoryFromDb()
      this.setPhase('ide')
    },

    async loadOutlineFromDb() {
      if (!this.currentPitchId) return
      try {
        const res = await fetch(`/api/outline/list/${this.currentPitchId}`)
        if (res.ok) {
          const nodes = await res.json()
          if (nodes && nodes.length > 0) {
            this.outlineNodes = nodes.map(n => ({
              id: n.id,
              volume: n.volume_number,
              title: n.title,
              desc: n.core_goal || '',
              core_goal: n.core_goal,
              emotion_curve: n.emotion_curve,
              location: n.location,
              estimated_chapters: n.estimated_chapters,
              status: n.status || 'pending',
              sort_order: n.sort_order,
            }))
          }
        }
      } catch {
        // 静默失败，outlineNodes 保持空数组
      }
    },

    async loadChaptersFromDb() {
      if (!this.currentBookId) return
      try {
        const res = await fetch(`/api/chapters/list/${this.currentBookId}`)
        if (res.ok) {
          const chapters = await res.json()
          if (chapters && chapters.length > 0) {
            this.chapters = chapters
            const last = chapters[chapters.length - 1]
            this.currentChapter = last.chapter_marker + 1
            this.currentVolume = last.volume_number
          }
        }
      } catch {
        // 静默
      }
    },

    async loadChatHistoryFromDb() {
      if (!this.currentBookId) return
      try {
        const res = await fetch(`/api/chat/list/${this.currentBookId}`)
        if (res.ok) {
          const msgs = await res.json()
          if (msgs && msgs.length > 0) {
            this.chatHistory = msgs
          }
        }
      } catch {
        // 静默
      }
    },

    async startNewBook() {
      this.currentBookId = null
      this.setPhase('pitch')
    },

    async generatePitches(seedText, isVariant = false, targetPitch = null) {
      if (!isVariant) this.promptSeed = seedText
      this.pitches = []
      try {
        const response = await fetchWithBYOK('/api/books/pitch', {
          seed_text: seedText,
          is_variant: isVariant,
          target_pitch: targetPitch
        })
        this.pitches = response.data || []
      } catch (error) {
        console.error("裂变失败", error)
        alert("裂变推演失败: " + error.message)
      }
    },

    async generateOutline(pitchId) {
      this.selectedPitch = this.pitches.find(p => p.id === pitchId)
      this.currentPitchId = pitchId
      this.isGeneratingOutline = true
      try {
        const response = await fetchWithBYOK('/api/books/outline', {
          pitch: this.selectedPitch
        })
        this.outlineNodes = (response.data.outline_nodes || []).map(n => ({
          id: n.id,
          volume: n.volume_number,
          title: n.title,
          desc: n.core_goal || '',
          core_goal: n.core_goal,
          emotion_curve: n.emotion_curve,
          location: n.location,
          estimated_chapters: n.estimated_chapters,
          status: n.status || 'pending',
          sort_order: n.sort_order,
        }))
        this.setPhase('outline')
      } catch (error) {
        console.error("大纲生成失败", error)
        alert("大纲生成失败: " + error.message)
      } finally {
        this.isGeneratingOutline = false
      }
    },

    advanceChapter() {
      this.currentChapter++
      const currentVolumeNode = this.outlineNodes.find(n => Number(n.volume) === Number(this.currentVolume))
      if (currentVolumeNode) {
        currentVolumeNode.status = 'completed'
        this._syncOutlineStatus(currentVolumeNode.id, 'completed')
      }
      const nextNode = this.outlineNodes.find(n => n.status === 'pending')
      if (nextNode) {
        nextNode.status = 'active'
        this.currentVolume = Number(nextNode.volume)
        this._syncOutlineStatus(nextNode.id, 'active')
      }
    },

    async fetchPlotSuggestions() {
      this.isSuggesting = true
      this.plotSuggestions = []
      try {
        const recentChats = this.chatHistory.slice(-3).map(c => c.text || c.content || '').join('\n')
        const { fetchSuggestions } = await import('../api/stream')
        const json = await fetchSuggestions(recentChats || '故事刚刚开始...')
        this.plotSuggestions = json.data || []
      } catch (error) {
        console.error('推演失败', error)
        alert('获取剧情建议失败: ' + error.message)
      } finally {
        this.isSuggesting = false
      }
    },

    useSuggestion(suggestionText) {
      this.currentDraft = suggestionText
    },

    advanceVolume() {
      const currentIndex = this.outlineNodes.findIndex(n => Number(n.volume) === Number(this.currentVolume))
      if (currentIndex !== -1 && currentIndex < this.outlineNodes.length - 1) {
        this.outlineNodes[currentIndex].status = 'completed'
        this._syncOutlineStatus(this.outlineNodes[currentIndex].id, 'completed')
        const nextNode = this.outlineNodes[currentIndex + 1]
        this.currentVolume = Number(nextNode.volume)
        this.currentChapter = 1
        nextNode.status = 'active'
        this._syncOutlineStatus(nextNode.id, 'active')
        const divider = {
          id: Date.now(),
          role: 'system',
          type: 'volume_divider',
          volume: nextNode.volume,
          title: nextNode.title,
          desc: nextNode.desc || '全新的命运齿轮开始转动...'
        }
        this.chatHistory.push(divider)
        fetch('/api/chat/save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            book_id: this.currentBookId,
            role: 'system',
            type: 'volume_divider',
            volume: nextNode.volume,
            title: nextNode.title,
            desc: nextNode.desc || '全新的命运齿轮开始转动...',
          })
        }).catch(() => {})
      }
    },

    _syncOutlineStatus(nodeId, status) {
      fetch(`/api/outline/update/${nodeId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status })
      }).catch(() => {})
    },

    appendChat(text) {
      const msg = {
        id: Date.now(),
        role: 'assistant',
        type: 'text',
        content: text,
        chapter: this.currentChapter,
        timestamp: Date.now()
      }
      this.chatHistory.push(msg)
      fetch('/api/chat/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          book_id: this.currentBookId,
          role: 'assistant',
          type: 'text',
          chapter: this.currentChapter,
          content: text,
        })
      }).catch(() => {})
    },

    async saveChapter(volume, chapterMarker, content) {
      const match = content.match(/第[一二三四五六七八九十百零0-9]+章[ \t:：]*([^\n]+)/)
      const title = match ? `第 ${chapterMarker} 章：${match[1].trim()}` : `第 ${chapterMarker} 章`
      const chapter = { id: Date.now(), volume, chapter: chapterMarker, title, content }
      this.chapters.push(chapter)
      this.currentChapter += 1
      // 异步写入数据库
      try {
        await fetch('/api/chapters/save', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            book_id: this.currentBookId,
            volume_number: volume,
            chapter_marker: chapterMarker,
            title,
            content,
          })
        })
      } catch {
        // 静默失败，本地已保存
      }
    },

    openChapterModal(chapter) {
      this.viewingChapter = chapter
    },

    closeChapterModal() {
      this.viewingChapter = null
    }
  }
})
