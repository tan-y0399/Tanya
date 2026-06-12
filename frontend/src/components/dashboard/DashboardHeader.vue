<template>
  <div class="dash-header">
    <div class="header-main">
      <div class="title-bar">
        <span class="title-accent"></span>
        <div>
          <h2 class="page-title">运维仪表盘</h2>
          <p class="page-sub">[ TELEMETRY · REAL-TIME · SSH METRICS ]</p>
        </div>
      </div>
    </div>

    <div class="header-actions">
      <div class="sync-capsule" :class="syncState">
        <span class="capsule-dot"></span>
        <span class="capsule-text">{{ capsuleText }}</span>
      </div>

      <button
        type="button"
        class="sync-btn"
        :class="{ active: syncing, done: syncDone }"
        :disabled="syncing"
        @click="emit('sync')"
      >
        <span class="btn-sweep"></span>
        <svg class="sync-icon" width="18" height="18" viewBox="0 0 18 18" fill="none" :class="{ spinning: syncing }">
          <circle cx="9" cy="9" r="7" stroke="currentColor" stroke-width="1" stroke-opacity="0.2"/>
          <path d="M9 2.5a6.5 6.5 0 016.5 6.5" stroke="url(#syncGrad1)" stroke-width="1.5" stroke-linecap="round"/>
          <path d="M15.5 9V6M15.5 6H12" stroke="url(#syncGrad1)" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M9 15.5a6.5 6.5 0 01-6.5-6.5" stroke="url(#syncGrad2)" stroke-width="1.5" stroke-linecap="round" stroke-opacity="0.85"/>
          <path d="M2.5 9v3M2.5 12H5.5" stroke="url(#syncGrad2)" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round" stroke-opacity="0.85"/>
          <circle cx="9" cy="9" r="1.5" fill="#06b6d4"/>
          <line x1="9" y1="4" x2="9" y2="2.5" stroke="#67e8f9" stroke-width="0.8" stroke-linecap="round"/>
          <line x1="12.2" y1="5.8" x2="13.3" y2="4.7" stroke="#67e8f9" stroke-width="0.8" stroke-linecap="round"/>
          <line x1="5.8" y1="5.8" x2="4.7" y2="4.7" stroke="#67e8f9" stroke-width="0.8" stroke-linecap="round"/>
          <defs>
            <linearGradient id="syncGrad1" x1="9" y1="2" x2="16" y2="10" gradientUnits="userSpaceOnUse">
              <stop stop-color="#06b6d4"/><stop offset="1" stop-color="#3b82f6"/>
            </linearGradient>
            <linearGradient id="syncGrad2" x1="9" y1="16" x2="2" y2="8" gradientUnits="userSpaceOnUse">
              <stop stop-color="#6366f1"/><stop offset="1" stop-color="#93c5fd"/>
            </linearGradient>
          </defs>
        </svg>
        <span>{{ syncing ? '同步中…' : (syncDone ? '已同步' : '同步数据') }}</span>
      </button>

      <div class="node-pick glass-panel">
        <span class="node-tag">NODE</span>
        <select :value="serverId" @change="onServerChange">
          <option v-for="s in servers" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
        <span class="node-dot" :class="nodeOnline ? 'on' : 'off'"></span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ServerInfo } from '@/api/servers'

const props = defineProps<{
  servers: ServerInfo[]
  serverId: string
  lastUpdate: string
  syncing: boolean
  syncDone: boolean
  offline: boolean
}>()

const emit = defineEmits<{ sync: []; 'update:serverId': [id: string] }>()

const nodeOnline = computed(() =>
  props.servers.find(s => s.id === props.serverId)?.status === 'online',
)

const syncState = computed(() => {
  if (props.offline) return 'offline'
  if (props.syncing) return 'syncing'
  return 'live'
})

const capsuleText = computed(() => {
  if (props.offline) return 'SIGNAL LOST · SSH 不可达'
  if (props.syncing) return 'SYNC · 采集中…'
  if (props.syncDone && props.lastUpdate) return `SYNC OK · ${props.lastUpdate}`
  if (props.lastUpdate) return `LIVE · ${props.lastUpdate}`
  return 'LIVE · 等待同步'
})

function onServerChange(e: Event) {
  emit('update:serverId', (e.target as HTMLSelectElement).value)
}
</script>

<style lang="scss" scoped>
.dash-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.title-bar {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.title-accent {
  width: 3px;
  height: 36px;
  border-radius: 2px;
  background: linear-gradient(180deg, #06b6d4, #3b82f6);
  box-shadow: 0 0 12px rgba(6, 182, 212, 0.45);
  flex-shrink: 0;
  margin-top: 2px;
}

.page-title {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
}

.page-sub {
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: #06b6d4;
  margin: 4px 0 0;
  opacity: 0.9;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.sync-capsule {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.88);
  border: 1px solid rgba(186, 230, 253, 0.8);
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
  color: #047857;

  &.syncing { color: #0891b2; border-color: rgba(6, 182, 212, 0.5); }
  &.offline { color: #dc2626; border-color: rgba(239, 68, 68, 0.35); }
}

.capsule-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #10b981;
  box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.15);
  animation: live-pulse 2.5s ease-in-out infinite;
  .syncing & {
    background: #06b6d4;
    animation: fast-pulse 0.6s ease-in-out infinite;
  }
  .offline & { background: #ef4444; animation: none; }
}

.sync-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 9px 16px;
  border-radius: 10px;
  border: 1px solid rgba(6, 182, 212, 0.55);
  background: linear-gradient(135deg, rgba(236, 254, 255, 0.95), rgba(255, 255, 255, 0.92));
  color: #0891b2;
  font-size: 12px;
  font-weight: 600;
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  cursor: pointer;
  overflow: hidden;
  transition: all 0.2s;
  box-shadow: 0 2px 12px rgba(6, 182, 212, 0.12);

  &:hover:not(:disabled) {
    border-color: #06b6d4;
    box-shadow: 0 4px 18px rgba(6, 182, 212, 0.25);
    transform: translateY(-1px);
  }

  &.active, &:disabled { cursor: wait; }
  &.done { border-color: #10b981; color: #047857; }
}

.btn-sweep {
  position: absolute;
  inset: 0;
  background: linear-gradient(105deg, transparent 40%, rgba(6, 182, 212, 0.12) 50%, transparent 60%);
  transform: translateX(-100%);
  .active & { animation: btn-sweep 1s ease-in-out infinite; }
}

.sync-icon {
  flex-shrink: 0;
  filter: drop-shadow(0 0 4px rgba(6, 182, 212, 0.35));
  &.spinning { animation: spin 0.85s linear infinite; }
}

.node-pick {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 7px 12px 7px 10px;
  border-color: rgba(186, 230, 253, 0.75) !important;
  background: rgba(255, 255, 255, 0.88) !important;

  select {
    border: none;
    outline: none;
    background: none;
    font-size: 13px;
    color: #0f172a;
    cursor: pointer;
    font-family: inherit;
    min-width: 100px;
  }
}

.node-tag {
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: #6366f1;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid rgba(99, 102, 241, 0.2);
}

.node-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  &.on { background: #10b981; box-shadow: 0 0 6px rgba(16, 185, 129, 0.45); }
  &.off { background: #ef4444; }
}

@keyframes spin { to { transform: rotate(360deg); } }
@keyframes btn-sweep { to { transform: translateX(100%); } }
@keyframes live-pulse {
  0%, 100% { box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.15); }
  50% { box-shadow: 0 0 0 6px rgba(16, 185, 129, 0.06); }
}
@keyframes fast-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}
</style>
