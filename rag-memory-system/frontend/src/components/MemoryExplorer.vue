<template>
  <div class="explorer-panel">
    <div class="panel-header">
      <span class="panel-title">记忆资源管理器</span>
      <input v-model="searchQuery" placeholder="搜索词条..." class="search-input" />
    </div>

    <div class="group-list">
      <div v-for="group in groupedEntities" :key="group.type" class="group-section">
        <div class="group-title" @click="toggleGroup(group.type)">
          <span>{{ group.type }} ({{ group.items.length }})</span>
          <span class="toggle-icon">{{ expandedGroups[group.type] ? '▾' : '▸' }}</span>
        </div>
        <div v-if="expandedGroups[group.type]" class="group-items">
          <div v-for="e in group.items" :key="e.id" class="entity-row" @click="selectEntity(e)">
            <span v-if="isNew(e)" class="new-badge">NEW</span>
            <span class="entity-row-name">{{ e.entry_name }}</span>
            <span class="entity-row-count">{{ getFactsCount(e.id) }}条</span>
          </div>
        </div>
      </div>
      <div v-if="groupedEntities.length === 0" class="empty-state">暂无记忆数据</div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useMemoryStore } from '../stores/memory.js'

const store = useMemoryStore()
const searchQuery = ref('')
const expandedGroups = ref({})
const newEntityIds = ref(new Set())

const groupedEntities = computed(() => {
  let list = store.entities
  if (searchQuery.value.trim()) {
    const q = searchQuery.value.toLowerCase()
    list = list.filter(e => e.entry_name.toLowerCase().includes(q))
  }
  const groups = {}
  for (const e of list) {
    const type = e.type || '其他'
    if (!groups[type]) groups[type] = []
    groups[type].push(e)
  }
  return Object.entries(groups).map(([type, items]) => ({ type, items }))
})

function toggleGroup(type) {
  expandedGroups.value[type] = !expandedGroups.value[type]
}

function isNew(entity) {
  return newEntityIds.value.has(entity.id)
}

function getFactsCount(entityId) {
  return store.getFactsByEntityId(entityId).length
}

function selectEntity(entity) {
  newEntityIds.value.delete(entity.id)
}

onMounted(() => {
  for (const g of ['人物', '地点', '物品', '组织', '事件', '能力', '其他']) {
    expandedGroups.value[g] = true
  }
})
</script>

<style scoped>
.explorer-panel {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #16162a;
  border-right: 1px solid #2a2a3e;
}

.panel-header {
  padding: 16px;
  border-bottom: 1px solid #2a2a3e;
}

.search-input {
  width: 100%;
  margin-top: 8px;
  background: #1e1e38;
  border: 1px solid #3a3a5e;
  color: #e0e0e0;
  padding: 6px 10px;
  border-radius: 4px;
  font-size: 13px;
}

.group-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.group-section {
  margin-bottom: 4px;
}

.group-title {
  display: flex;
  justify-content: space-between;
  padding: 8px 16px;
  font-size: 12px;
  color: #8888aa;
  cursor: pointer;
  user-select: none;
}

.group-title:hover {
  background: #1e1e38;
}

.toggle-icon {
  font-size: 10px;
}

.group-items {
  padding: 0 8px;
}

.entity-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}

.entity-row:hover {
  background: #252540;
}

.entity-row-name {
  flex: 1;
  color: #7ecfff;
}

.entity-row-count {
  font-size: 11px;
  color: #555577;
}

.new-badge {
  font-size: 10px;
  background: #ffaa44;
  color: #0f0f1a;
  padding: 1px 5px;
  border-radius: 3px;
  font-weight: 600;
  animation: new-blink 1s ease-in-out infinite;
}

@keyframes new-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}
</style>
