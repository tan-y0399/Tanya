<template>
  <div class="sys-status">
    <div class="sys-overview">
      <div class="overview-left">
        <span class="sys-badge" :class="badgeClass">{{ badgeLabel }}</span>
        <span class="sys-score">{{ onlineCount }}/{{ components.length }} 在线</span>
      </div>
      <svg class="score-ring" viewBox="0 0 44 44" aria-hidden="true">
        <circle cx="22" cy="22" r="18" fill="none" stroke="#e2e8f0" stroke-width="3" />
        <circle
          cx="22" cy="22" r="18"
          fill="none"
          :stroke="ringColor"
          stroke-width="3"
          stroke-linecap="round"
          :stroke-dasharray="ringCirc"
          :stroke-dashoffset="ringOffset"
          transform="rotate(-90 22 22)"
        />
        <text x="22" y="24" text-anchor="middle" class="ring-text">{{ healthPct }}%</text>
      </svg>
    </div>

    <div class="sys-metrics">
      <div class="metric-cell">
        <span class="m-label">MODEL</span>
        <span class="m-val">{{ llmModel || '—' }}</span>
      </div>
      <div class="metric-cell">
        <span class="m-label">TOOLS</span>
        <span class="m-val">{{ enabledTools }}/{{ totalTools }}</span>
      </div>
      <div class="metric-cell">
        <span class="m-label">AVG RT</span>
        <span class="m-val">{{ avgLatency != null ? `${avgLatency}ms` : '—' }}</span>
      </div>
    </div>

    <div class="comp-list">
      <div v-for="comp in components" :key="comp.code" class="comp-row">
        <span class="status-dot" :class="comp.status"></span>
        <div class="comp-main">
          <div class="comp-top">
            <span class="comp-code">{{ comp.code }}</span>
            <span class="comp-name">{{ comp.name }}</span>
            <span class="comp-latency" v-if="comp.latency != null">{{ comp.latency }}ms</span>
            <span class="comp-latency na" v-else>—</span>
          </div>
          <div class="latency-bar">
            <div
              class="latency-fill"
              :class="comp.status"
              :style="{ width: latencyWidth(comp.latency) }"
            ></div>
          </div>
          <span v-if="comp.detail" class="comp-detail">{{ comp.detail }}</span>
        </div>
      </div>
    </div>

    <div v-if="vmAgent" class="vm-panel">
      <div class="vm-head">
        <span class="vm-tag">NODE</span>
        <span class="vm-host">{{ vmAgent.detail }}</span>
        <span class="status-pill" :class="vmAgent.status">{{ statusLabel(vmAgent.status) }}</span>
      </div>
      <p v-if="vmAgent.description" class="vm-desc">{{ vmAgent.description }}</p>
    </div>

    <div class="sys-footer">
      <div class="footer-left">
        <span>版本 {{ version }}</span>
        <span v-if="lastRefresh" class="refresh-time">· {{ lastRefresh }}</span>
      </div>
      <button type="button" class="refresh-btn" :disabled="refreshing || disabled" @click="emit('refresh')">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" :class="{ spinning: refreshing }">
          <path d="M1 7a6 6 0 0111.3-3M13 7a6 6 0 01-11.3 3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
          <path d="M1 1v3h3M13 13v-3h-3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
        </svg>
        {{ refreshing ? '刷新中...' : '刷新' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

export interface HealthComponent {
  name: string
  code: string
  status: 'online' | 'offline' | 'warning'
  latency: number | null
  detail?: string
  description?: string
}

const props = defineProps<{
  components: HealthComponent[]
  systemStatus?: string
  version?: string
  lastRefresh?: string
  llmModel?: string
  enabledTools?: number
  totalTools?: number
  refreshing?: boolean
  disabled?: boolean
}>()

const emit = defineEmits<{ refresh: [] }>()

const ringCirc = 2 * Math.PI * 18

const onlineCount = computed(() =>
  props.components.filter(c => c.status === 'online').length,
)

const healthPct = computed(() => {
  if (!props.components.length) return 0
  return Math.round((onlineCount.value / props.components.length) * 100)
})

const ringOffset = computed(() =>
  ringCirc - (healthPct.value / 100) * ringCirc,
)

const ringColor = computed(() => {
  if (healthPct.value >= 100) return '#10b981'
  if (healthPct.value >= 50) return '#f59e0b'
  return '#ef4444'
})

const badgeClass = computed(() => {
  const s = props.systemStatus
  if (s === 'healthy' && healthPct.value === 100) return 'ok'
  if (s === 'degraded' || healthPct.value < 100) return 'warn'
  return 'idle'
})

const badgeLabel = computed(() => {
  if (badgeClass.value === 'ok') return 'HEALTHY'
  if (badgeClass.value === 'warn') return 'DEGRADED'
  return 'CHECKING'
})

const avgLatency = computed(() => {
  const vals = props.components.map(c => c.latency).filter((v): v is number => v != null)
  if (!vals.length) return null
  return Math.round(vals.reduce((a, b) => a + b, 0) / vals.length)
})

const vmAgent = computed(() =>
  props.components.find(c => c.code === 'SSH'),
)

function latencyWidth(ms: number | null) {
  if (ms == null) return '0%'
  const pct = Math.min(100, (ms / 500) * 100)
  return `${Math.max(8, pct)}%`
}

function statusLabel(status: string) {
  if (status === 'online') return 'ONLINE'
  if (status === 'offline') return 'OFFLINE'
  return 'WARN'
}
</script>

<style lang="scss" scoped>
.sys-status {
  display: flex;
  flex-direction: column;
  gap: 10px;
  height: 100%;
}

.sys-overview {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(16, 185, 129, 0.05);
  border: 1px solid rgba(16, 185, 129, 0.12);
}

.overview-left {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.sys-badge {
  font-family: 'Inter', 'PingFang SC', sans-serif;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.08em;
  padding: 2px 7px;
  border-radius: 4px;
  width: fit-content;

  &.ok { color: #047857; background: rgba(16, 185, 129, 0.15); }
  &.warn { color: #b45309; background: rgba(245, 158, 11, 0.15); }
  &.idle { color: #64748b; background: rgba(148, 163, 184, 0.15); }
}

.sys-score {
  font-size: 11px;
  font-weight: 600;
  color: #64748b;
}

.score-ring {
  width: 44px;
  height: 44px;
  flex-shrink: 0;
}

.ring-text {
  font-family: 'Inter', 'PingFang SC', sans-serif;
  font-size: 9px;
  font-weight: 800;
  fill: #334155;
}

.sys-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
}

.metric-cell {
  padding: 6px 8px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid rgba(16, 185, 129, 0.1);
  text-align: center;

  .m-label {
    display: block;
    font-family: 'Inter', 'PingFang SC', sans-serif;
    font-size: 7px;
    font-weight: 700;
    letter-spacing: 0.06em;
    color: #94a3b8;
    margin-bottom: 2px;
  }

  .m-val {
    display: block;
    font-size: 10px;
    font-weight: 700;
    color: #1e293b;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
}

.comp-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  flex: 1;
  min-height: 0;
  max-height: 148px;
  overflow-y: auto;
  padding-right: 2px;
}

.comp-row {
  display: flex;
  gap: 8px;
  padding: 7px 8px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.65);
  border: 1px solid rgba(16, 185, 129, 0.08);
}

.comp-main {
  flex: 1;
  min-width: 0;
}

.comp-top {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.comp-code {
  font-family: 'Inter', 'PingFang SC', sans-serif;
  font-size: 7px;
  font-weight: 800;
  letter-spacing: 0.05em;
  color: #10b981;
  padding: 1px 4px;
  border-radius: 3px;
  background: rgba(16, 185, 129, 0.1);
  flex-shrink: 0;
}

.comp-name {
  flex: 1;
  font-size: 11px;
  font-weight: 600;
  color: #1e293b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.comp-latency {
  font-family: 'Inter', 'PingFang SC', sans-serif;
  font-size: 10px;
  font-weight: 700;
  color: #059669;
  flex-shrink: 0;

  &.na { color: #cbd5e1; font-weight: 500; }
}

.latency-bar {
  height: 3px;
  border-radius: 2px;
  background: #f1f5f9;
  overflow: hidden;
  margin-bottom: 3px;
}

.latency-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.4s ease;

  &.online { background: linear-gradient(90deg, #34d399, #10b981); }
  &.warning { background: linear-gradient(90deg, #fbbf24, #f59e0b); }
  &.offline { background: #ef4444; }
}

.comp-detail {
  font-size: 9px;
  color: #94a3b8;
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.vm-panel {
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(37, 99, 235, 0.04);
  border: 1px solid rgba(37, 99, 235, 0.1);
}

.vm-head {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.vm-tag {
  font-size: 7px;
  font-weight: 800;
  letter-spacing: 0.06em;
  color: #2563eb;
  padding: 1px 4px;
  border-radius: 3px;
  background: rgba(37, 99, 235, 0.1);
}

.vm-host {
  font-family: 'Inter', 'PingFang SC', sans-serif;
  font-size: 10px;
  font-weight: 600;
  color: #334155;
  flex: 1;
}

.status-pill {
  font-size: 7px;
  font-weight: 800;
  letter-spacing: 0.05em;
  padding: 2px 6px;
  border-radius: 999px;

  &.online { color: #047857; background: rgba(16, 185, 129, 0.12); }
  &.offline { color: #dc2626; background: rgba(239, 68, 68, 0.1); }
  &.warning { color: #b45309; background: rgba(245, 158, 11, 0.12); }
}

.vm-desc {
  margin: 4px 0 0;
  font-size: 9px;
  color: #94a3b8;
  line-height: 1.4;
}

.sys-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-top: 8px;
  margin-top: auto;
  border-top: 1px solid rgba(16, 185, 129, 0.12);
  font-size: 10px;
  color: #94a3b8;
}

.footer-left {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.refresh-time {
  font-family: 'Inter', 'PingFang SC', sans-serif;
  font-size: 9px;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 4px;

  &.online { background: #10b981; box-shadow: 0 0 4px rgba(16, 185, 129, 0.5); }
  &.warning { background: #f59e0b; }
  &.offline { background: #ef4444; }
}

.refresh-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 12px;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #64748b;
  font-size: 11px;
  cursor: pointer;

  &:hover:not(:disabled) {
    border-color: #10b981;
    color: #059669;
    background: rgba(16, 185, 129, 0.06);
  }

  &:disabled {
    opacity: 0.55;
    cursor: not-allowed;
  }
}

.spinning {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
