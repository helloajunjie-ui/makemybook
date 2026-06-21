<template>
  <div class="outline-panel">
    <div class="panel-title">大纲导航器</div>

    <div class="stepper">
      <div v-for="(node, idx) in nodes" :key="node.id" class="step-item" :class="stepClass(node)">
        <div class="step-connector" v-if="idx > 0"></div>
        <div class="step-dot" @click="jumpTo(node)">
          <span class="step-number">{{ node.volume_number }}</span>
        </div>
        <div class="step-content">
          <div class="step-title">{{ node.title }}</div>
          <div class="step-meta">
            <span class="step-status">{{ statusLabel(node.status) }}</span>
            <span class="step-chapters">{{ node.estimated_chapters }}章</span>
          </div>
          <div v-if="node.core_goal" class="step-goal">{{ node.core_goal }}</div>
        </div>
      </div>
    </div>

    <div v-if="nodes.length === 0" class="empty-state">暂无大纲数据</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useStoryFlowStore } from '../stores/storyFlow.js'

const flowStore = useStoryFlowStore()

const nodes = computed(() => flowStore.outlineNodes)

function stepClass(node) {
  return {
    'step-active': node.status === 'active',
    'step-completed': node.status === 'completed',
    'step-pending': node.status === 'pending'
  }
}

function statusLabel(status) {
  const map = { pending: '未开始', active: '进行中', completed: '已完成' }
  return map[status] || status
}

function jumpTo(node) {
  if (node.status === 'completed') return
  editorStore.setChapter(node.volume_number)
}
</script>

<style scoped>
.outline-panel {
  height: 100%;
  background: #16162a;
  border-left: 1px solid #2a2a3e;
  padding: 16px;
  overflow-y: auto;
}

.stepper {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.step-item {
  display: flex;
  gap: 12px;
  padding: 8px 0;
  cursor: pointer;
  position: relative;
}

.step-connector {
  position: absolute;
  left: 15px;
  top: -8px;
  width: 2px;
  height: 16px;
  background: #2a2a3e;
}

.step-dot {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 600;
  flex-shrink: 0;
  z-index: 1;
}

.step-pending .step-dot {
  background: #252540;
  color: #555577;
  border: 2px solid #2a2a3e;
}

.step-active .step-dot {
  background: #3a6ea5;
  color: #fff;
  box-shadow: 0 0 8px rgba(58, 110, 165, 0.5);
}

.step-completed .step-dot {
  background: #2a6a3e;
  color: #fff;
}

.step-content {
  flex: 1;
  padding-top: 4px;
}

.step-title {
  font-size: 14px;
  font-weight: 600;
  color: #e0e0e0;
}

.step-meta {
  display: flex;
  gap: 8px;
  margin-top: 2px;
}

.step-status {
  font-size: 11px;
  color: #8888aa;
}

.step-chapters {
  font-size: 11px;
  color: #555577;
}

.step-goal {
  font-size: 12px;
  color: #666688;
  margin-top: 4px;
  line-height: 1.4;
}

.step-completed .step-title {
  color: #6a8a6a;
}
</style>
