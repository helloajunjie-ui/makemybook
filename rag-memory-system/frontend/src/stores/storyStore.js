import { defineStore } from 'pinia'
import { useMemoryStore } from './memoryStore'
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
    viewingChapter: null,
    // 💡 从本地存储读取文风约束，实现跨会话记忆
    customPrompt: localStorage.getItem('qingyu_custom_prompt') || ''
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
      // 💡 核心修复：一旦返回大厅，彻底清空工作台残影，防止数据串库
      if (phase === 'library') {
        this.currentBookId = null
        this.currentPitchId = null
        this.chapters = []
        this.chatHistory = []
        this.outlineNodes = []
        this.currentChapter = 1
        this.currentVolume = 1
        this.currentDraft = ''
        this.plotSuggestions = []
        this.isSuggesting = false
        this.viewingChapter = null
        // 同步清空记忆皮层
        const memoryStore = useMemoryStore()
        memoryStore.resetMemory()
        this.loadBookshelf()
      }
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
      // 打开新书前重置记忆，避免旧数据残留
      const memoryStore = useMemoryStore()
      memoryStore.resetMemory()
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
      // 💡 核心修复：打开存档时同步加载世界书词条（全量）
      // 传入空 draftText 使后端返回本书所有实体
      // 必须 await，确保在 setPhase 触发组件挂载前数据已就绪
      await memoryStore.loadMemoryForChapter(bookId, this.currentChapter, '')
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
            // 标准化字段：API 返回 volume_number，前端用 volume
            this.chapters = chapters.map(c => ({
              id: c.id,
              volume: c.volume_number,
              chapter: c.chapter_marker,
              title: c.title,
              content: c.content,
              created_at: c.created_at
            }))
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
      // 完全重置所有状态，避免数据库清空后前端内存残留
      const memoryStore = useMemoryStore()
      memoryStore.resetMemory()
      this.currentBookId = null
      this.currentPitchId = null
      this.promptSeed = ''
      this.pitches = []
      this.selectedPitch = null
      this.currentChapter = 1
      this.currentVolume = 1
      this.outlineNodes = []
      this.chatHistory = []
      this.plotSuggestions = []
      this.isSuggesting = false
      this.currentDraft = ''
      this.isGeneratingOutline = false
      this.chapters = []
      this.viewingChapter = null
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

        // 💡 大纲生成成功后，自动创建 Book 记录，确保 currentBookId 是真实的 book_id
        // 而不是 pitch_id（pitch_id 在 story_pitches 表，book_id 在 books 表，外键约束不同）
        try {
          const bookRes = await fetch('/api/books/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              title: this.selectedPitch?.title || '未命名世界',
              summary: this.selectedPitch?.summary || ''
            })
          })
          if (bookRes.ok) {
            const book = await bookRes.json()
            this.currentBookId = book.id
          } else {
            console.warn('创建 Book 失败，currentBookId 将保持 null')
          }
        } catch (bookErr) {
          console.warn('创建 Book 网络异常:', bookErr)
        }
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

    useSuggestion(suggestion) {
      // 智能拆包：对象 → 拼接成优质指令；字符串 → 直接使用
      if (typeof suggestion === 'object' && suggestion !== null) {
        const title = suggestion.title || ''
        const desc = suggestion.desc || suggestion.conflict || ''
        this.currentDraft = `【剧情分支】${title}：${desc}`.trim()
      } else {
        this.currentDraft = String(suggestion)
      }
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
    },

    // 💡 更新并持久化作者自定义文风约束
    updateCustomPrompt(text) {
      this.customPrompt = text
      try {
        localStorage.setItem('qingyu_custom_prompt', text)
      } catch {
        // 隐私模式等场景静默失败
      }
    }
  }
})
