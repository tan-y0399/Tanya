<template>
  <div class="app-layout">
    <!-- 故障转移提示栏 -->
    <div v-if="showFailover" class="failover-bar">
      <span class="failover-icon">&#9888;</span>
      <span>当前服务器连接失败，请切换至备用入口：</span>
      <a v-for="s in failoverServers" :key="s.url" :href="s.url" class="failover-link">{{ s.label }}</a>
      <button class="failover-close" @click="showFailover = false">&times;</button>
    </div>
    <Sidebar />
    <div class="main-area">
      <TopBar />
      <div class="page-content">
        <router-view />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import Sidebar from './Sidebar.vue'
import TopBar from './TopBar.vue'

interface FailoverServer { label: string; url: string }

const showFailover = ref(false)
const failoverServers = ref<FailoverServer[]>([])

function onDisconnected(e: Event) {
  const detail = (e as CustomEvent).detail
  failoverServers.value = detail.servers || []
  showFailover.value = true
}

function onConnected() { showFailover.value = false }

onMounted(() => {
  document.addEventListener('api:disconnected', onDisconnected)
  document.addEventListener('api:connected', onConnected)
})

onUnmounted(() => {
  document.removeEventListener('api:disconnected', onDisconnected)
  document.removeEventListener('api:connected', onConnected)
})
</script>

<style lang="scss" scoped>
.app-layout { display: flex; flex-direction: row; width: 100%; height: 100vh; overflow: hidden; }

.failover-bar {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 20px; background: #fff3cd; border-bottom: 1px solid #ffc107;
  color: #856404; font-size: 14px; flex-shrink: 0; z-index: 100;
  .failover-icon { font-size: 18px; }
  .failover-link {
    color: #0d6efd; font-weight: 600; text-decoration: none;
    padding: 3px 10px; border: 1px solid #0d6efd; border-radius: 4px;
    &:hover { background: #0d6efd; color: #fff; }
  }
  .failover-close {
    margin-left: auto; border: none; background: none;
    font-size: 20px; cursor: pointer; color: #856404;
    &:hover { color: #333; }
  }
}

.main-area { flex: 1; min-width: 0; display: flex; flex-direction: column; overflow: hidden; background: #f5f6f8; }
.page-content { flex: 1; min-width: 0; overflow: auto; padding: 24px; }
</style>
