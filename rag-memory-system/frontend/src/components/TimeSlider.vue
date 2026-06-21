<template>
  <div class="slider-container">
    <div class="panel-title">时空穿梭</div>
    <input type="range" :min="1" :max="maxChapter" :value="modelValue" @input="onInput" @change="onChange" />
    <div class="slider-label">
      <span>第 1 章</span>
      <span>当前：第 {{ modelValue }} 章</span>
      <span>第 {{ maxChapter }} 章</span>
    </div>
  </div>
</template>

<script setup>
const props = defineProps({
  modelValue: { type: Number, default: 1 },
  maxChapter: { type: Number, default: 1 }
})
const emit = defineEmits(['update:modelValue', 'change'])

let debounceTimer = null

function onInput(e) {
  const val = Number(e.target.value)
  emit('update:modelValue', val)
}

function onChange(e) {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    emit('change', Number(e.target.value))
  }, 300)
}
</script>
