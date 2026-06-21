<template>
  <Teleport to="body">
    <div v-if="visible" class="tooltip-overlay" :style="{ top: y + 'px', left: x + 'px' }">
      <div class="tooltip-name">{{ entity?.entry_name }}</div>
      <div class="entity-type">{{ entity?.type }}</div>
      <div v-for="f in facts" :key="f.fact_id" class="tooltip-fact">
        [第{{ f.chapter_marker }}章] {{ f.content }}
      </div>
      <div v-if="facts.length === 0" class="tooltip-fact" style="color:#666;">暂无事实记录</div>
    </div>
  </Teleport>
</template>

<script setup>
defineProps({
  visible: { type: Boolean, default: false },
  x: { type: Number, default: 0 },
  y: { type: Number, default: 0 },
  entity: { type: Object, default: null },
  facts: { type: Array, default: () => [] }
})
</script>

<style scoped>
.tooltip-overlay {
  position: fixed;
  background: #1e1e38;
  border: 1px solid #3a3a5e;
  border-radius: 8px;
  padding: 12px 16px;
  max-width: 320px;
  z-index: 1000;
  box-shadow: 0 8px 24px rgba(0,0,0,0.4);
  animation: tooltip-fade-in 150ms ease-out forwards;
}

@keyframes tooltip-fade-in {
  from {
    opacity: 0;
    transform: translateY(30px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.tooltip-name {
  font-size: 15px;
  font-weight: 600;
  color: #7ecfff;
  margin-bottom: 6px;
}

.tooltip-fact {
  font-size: 13px;
  color: #c0c0d0;
  padding: 2px 0;
}
</style>
