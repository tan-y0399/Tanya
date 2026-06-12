<template>
  <div class="nav-panel glass-panel" :class="{ scanning: scanning }">
    <div class="panel-head">
      <div class="head-left">
        <span class="panel-tag">NAV</span>
        <h4>快捷操作</h4>
      </div>
      <span class="head-status">{{ headStatus }}</span>
    </div>

    <div class="nav-grid">
      <QuickNavTile
        v-for="(item, i) in navItems"
        :key="item.path"
        :item="item"
        :index="i"
        :lit="litIndex === i"
      />
    </div>

    <div class="scan-bar">
      <div class="scan-track">
        <div class="scan-dot"></div>
        <div class="scan-beam" :class="{ fast: scanning }"></div>
      </div>
      <span class="scan-label">{{ scanLabel }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted } from 'vue'
import type { ServerInfo } from '@/api/servers'
import QuickNavTile, { type NavTileItem } from './QuickNavTile.vue'

const props = defineProps<{
  pulseTick?: number
  scanning?: boolean
  servers?: ServerInfo[]
}>()

const litIndex = ref(-1)
const localScanning = ref(false)
let litTimer = 0
let scanEndTimer = 0

const CHANNEL = {
  chat: { color: '#06b6d4', channel: 'chat' as const },
  srv:  { color: '#2563eb', channel: 'srv' as const },
  aud:  { color: '#6366f1', channel: 'aud' as const },
  alt:  { color: '#f59e0b', channel: 'alt' as const },
}

const onlineCount = computed(() =>
  (props.servers || []).filter(s => s.status === 'online').length,
)

const totalServers = computed(() => (props.servers || []).length)

const navItems = computed<NavTileItem[]>(() => [
  {
    path: '/chat',
    label: '对话',
    code: 'CHAT',
    ...CHANNEL.chat,
    status: 'ready',
    statusText: 'READY',
    hint: 'AI AGENT · SSH OPS',
  },
  {
    path: '/servers',
    label: '服务器',
    code: 'SRV',
    ...CHANNEL.srv,
    status: totalServers.value > 0 && onlineCount.value === totalServers.value ? 'online' : 'idle',
    statusText: totalServers.value > 0
      ? `${onlineCount.value}/${totalServers.value} ONLINE`
      : 'LINK OK',
    hint: totalServers.value > 0
      ? `${onlineCount.value} NODES · SSH`
      : 'NODE MGMT',
  },
  {
    path: '/audit',
    label: '审计',
    code: 'AUD',
    ...CHANNEL.aud,
    status: 'idle',
    statusText: 'TRACE OK',
    hint: 'LOG · AUDIT TRAIL',
  },
  {
    path: '/alerts',
    label: '告警',
    code: 'ALT',
    ...CHANNEL.alt,
    status: 'ready',
    statusText: 'MONITOR',
    hint: 'ALERT · NOTIFY',
  },
])

const scanning = computed(() => localScanning.value || !!props.scanning)

const headStatus = computed(() =>
  scanning.value ? 'SCANNING…' : `LINK · ${navItems.value.length} MODULES`,
)

const scanLabel = computed(() =>
  scanning.value ? 'MODULE SCAN' : 'SCAN OK',
)

function runScanSequence() {
  window.clearTimeout(litTimer)
  window.clearTimeout(scanEndTimer)
  localScanning.value = true
  litIndex.value = -1

  let step = 0
  const stagger = () => {
    if (step < 4) {
      litIndex.value = step
      step += 1
      litTimer = window.setTimeout(stagger, 80)
    }
  }
  stagger()

  scanEndTimer = window.setTimeout(() => {
    localScanning.value = false
    litIndex.value = -1
  }, 900)
}

watch(
  () => props.pulseTick,
  (v) => { if (v) runScanSequence() },
)

watch(
  () => props.scanning,
  (v) => { if (v) runScanSequence() },
)

onMounted(() => {
  window.setTimeout(runScanSequence, 500)
})
</script>

<style lang="scss" scoped>
.nav-panel {
  padding: 18px 18px 14px;
  border-color: rgba(186, 230, 253, 0.65) !important;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.head-left {
  display: flex;
  align-items: center;
  gap: 8px;
  h4 { margin: 0; font-size: 14px; font-weight: 600; color: #334155; }
}

.panel-tag {
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

.head-status {
  font-family: 'Inter', 'PingFang SC', sans-serif;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #94a3b8;
  transition: color 0.25s;
}

.scanning .head-status {
  color: #06b6d4;
  animation: status-pulse 0.8s ease infinite;
}

@keyframes status-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.45; }
}

.nav-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.scan-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 2px;
}

.scan-track {
  flex: 1;
  position: relative;
  height: 2px;
  background: linear-gradient(90deg, transparent, #e2e8f0 15%, #e2e8f0 85%, transparent);
  border-radius: 1px;
  overflow: hidden;
}

.scan-dot {
  position: absolute;
  left: 0;
  top: 50%;
  width: 4px;
  height: 4px;
  margin-top: -2px;
  border-radius: 50%;
  background: #06b6d4;
  opacity: 0.5;
}

.scan-beam {
  position: absolute;
  top: 0;
  left: -30%;
  width: 30%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(6, 182, 212, 0.5), transparent);
  animation: scan-sweep 8s linear infinite;

  &.fast {
    animation: scan-sweep 0.75s ease-out;
  }
}

@keyframes scan-sweep {
  from { left: -30%; }
  to { left: 100%; }
}

.scan-label {
  font-family: 'Inter', 'PingFang SC', sans-serif;
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #94a3b8;
  white-space: nowrap;
  min-width: 72px;
  text-align: right;
  transition: color 0.25s;
}

.scanning .scan-label {
  color: #06b6d4;
}
</style>
