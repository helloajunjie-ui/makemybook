<template>
  <Transition name="fade" mode="out-in">
    <TheLibrary v-if="storyStore.currentPhase === 'library'" />
    <PitchRoom v-else-if="storyStore.currentPhase === 'pitch'" />
    <OutlineForge v-else-if="storyStore.currentPhase === 'outline'" />
    <IDEWorkspace v-else-if="storyStore.currentPhase === 'ide'" />
  </Transition>
  <SettingsModal />
</template>

<script setup>
import { onMounted } from 'vue'
import { useStoryStore } from './stores/storyStore'
import { useSettingsStore } from './stores/settingsStore'
import TheLibrary from './views/TheLibrary.vue'
import PitchRoom from './views/PitchRoom.vue'
import OutlineForge from './views/OutlineForge.vue'
import IDEWorkspace from './views/IDEWorkspace.vue'
import SettingsModal from './components/SettingsModal.vue'

const storyStore = useStoryStore()
const settingsStore = useSettingsStore()

onMounted(() => {
  settingsStore.loadFromDb()
})
</script>

<style>
.fade-enter-active, .fade-leave-active {
  transition: opacity 0.4s ease, transform 0.4s ease;
}
.fade-enter-from, .fade-leave-to {
  opacity: 0;
  transform: translateY(10px);
}
</style>
