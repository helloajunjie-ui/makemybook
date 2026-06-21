<template>
  <div class="side-panel">
    <div class="panel-title">当前激活记忆</div>

    <!-- 骨架屏 -->
    <div v-if="loading" class="skeleton-list">
      <div v-for="n in 3" :key="n" class="skeleton-card">
        <div class="skeleton-line skeleton-name"></div>
        <div class="skeleton-line skeleton-type"></div>
        <div class="skeleton-line skeleton-fact"></div>
        <div class="skeleton-line skeleton-fact short"></div>
      </div>
    </div>

    <div v-else-if="entities.length === 0" class="empty-state">暂无记忆数据</div>
    <div v-for="e in entities" :key="e.entry_name" class="entity-card">
      <div class="entity-name">{{ e.entry_name }}</div>
      <div class="entity-type">{{ e.type }}</div>
      <div v-for="(f, fi) in e.facts" :key="fi" class="fact-item">
        <span>{{ f.content }}</span>
        <span class="fact-chapter">第{{ f.chapter_marker }}章</span>
      </div>
    </div>
    <div v-if="missing.length > 0" style="margin-top: 8px;">
      <div class="panel-title">未命中词条（新设定）</div>
      <div v-for="m in missing" :key="m" class="entity-card" style="border-left: 2px solid #ffaa44;">
        <div class="entity-name" style="color: #ffaa44;">{{ m }}</div>
        <div class="entity-type">待创建</div>
      </div>
    </div>
  </div>
</template>

<script setup>
defineProps({
  entities: { type: Array, default: () => [] },
  missing: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false }
})
</script>

<style scoped>
.skeleton-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.skeleton-card {
  background: #252540;
  border-radius: 8px;
  padding: 12px 16px;
}

.skeleton-line {
  background: linear-gradient(90deg, #2a2a3e 25%, #3a3a5e 50%, #2a2a3e 75%);
  background-size: 200% 100%;
  animation: skeleton-pulse 1.5s ease-in-out infinite;
  border-radius: 4px;
  margin-bottom: 8px;
}

.skeleton-name {
  width: 40%;
  height: 16px;
}

.skeleton-type {
  width: 20%;
  height: 12px;
}

.skeleton-fact {
  width: 90%;
  height: 12px;
}

.skeleton-fact.short {
  width: 60%;
}

@keyframes skeleton-pulse {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
