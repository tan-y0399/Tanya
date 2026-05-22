<template>
  <header class="topbar">
    <div class="topbar-left">
      <span class="breadcrumb-item">{{ pageTitle }}</span>
      <span class="breadcrumb-sep">/</span>
      <span class="breadcrumb-current">{{ subtitle }}</span>
    </div>
    <div class="topbar-right">
      <div class="clock">{{ currentTime }}</div>
      <div class="trace-info" v-if="latestTraceId" title="最新 TraceId">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <path d="M7 4v3l2 2M2.5 3.5l-2-2M11.5 3.5l2-2" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
          <circle cx="7" cy="7" r="5.5" stroke="currentColor" stroke-width="1.2"/>
        </svg>
        <span class="trace-id">{{ shortTraceId }}</span>
      </div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useChatStore } from '@/stores/chat'

const route = useRoute()
const chatStore = useChatStore()
const currentTime = ref('')

let timer: number
onMounted(() => {
  timer = window.setInterval(() => {
    currentTime.value = new Date().toLocaleString('zh-CN', {
      year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    })
  }, 1000)
})
onUnmounted(() => clearInterval(timer))

const pageTitle = computed(() => (route.meta.title as string) || '智能运维')
const subtitle = computed(() => {
  if (route.path.startsWith('/chat') && route.params.id) return route.params.id as string
  return 'KylinOS'
})

const latestTraceId = computed(() => chatStore.currentTraceId)
const shortTraceId = computed(() => {
  const id = latestTraceId.value
  return id ? id.slice(0, 28) + '...' : ''
})
</script>

<style lang="scss" scoped>
.topbar {
  height: 56px;
  min-height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  border-bottom: 1px solid #e2e8f0;
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(12px);
  z-index: 50;
}

.breadcrumb-item { color: #94a3b8; font-size: 14px; }
.breadcrumb-sep { color: #e2e8f0; margin: 0 8px; }
.breadcrumb-current { color: #2563eb; font-weight: 500; font-size: 14px; }

.topbar-right {
  display: flex;
  align-items: center;
  gap: 20px;
}

.clock {
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 13px;
  color: #94a3b8;
}

.trace-info {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #94a3b8;
  .trace-id {
    font-family: 'JetBrains Mono', Consolas, monospace;
  }
}
</style>
