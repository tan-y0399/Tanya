<template>
  <article
    class="alert-item glass-panel"
    :class="[alert.severity, alert.status, { pulsing: alert.severity === 'critical' && alert.status === 'active' }]"
    @click="emit('select', alert)"
  >
    <div class="rail" :class="alert.severity"></div>

    <div class="item-body">
      <div class="row-top">
        <div class="badges">
          <span class="sev-badge" :class="alert.severity">{{ severityLabel(alert.severity) }}</span>
          <span class="type-badge">{{ alert.type }}</span>
          <span class="status-badge" :class="alert.status">{{ statusLabel(alert.status) }}</span>
        </div>
        <span class="item-id">{{ alert.id }}</span>
      </div>

      <h3 class="item-title">{{ alert.title }}</h3>
      <p class="item-detail">{{ alert.detail }}</p>

      <div class="row-meta">
        <span class="meta-cell">
          <span class="meta-key">HOST</span>
          <span class="meta-val">{{ alert.host }}</span>
        </span>
        <span class="meta-sep"></span>
        <span class="meta-cell">
          <span class="meta-key">SRC</span>
          <span class="meta-val">{{ alert.source }}</span>
        </span>
        <span class="meta-sep"></span>
        <span class="meta-cell">
          <span class="meta-key">TIME</span>
          <span class="meta-val">{{ formatTime(alert.time) }}</span>
        </span>
      </div>

      <div v-if="metricPreview.length" class="metric-preview">
        <span class="preview-label">METRICS</span>
        <span v-for="m in metricPreview" :key="m.key" class="metric-chip">{{ m.key }} {{ m.val }}</span>
      </div>
    </div>

    <div class="item-action" aria-hidden="true">
      <span class="action-label">DETAIL</span>
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path d="M6 4l4 4-4 4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
      </svg>
    </div>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ alert: any }>()
const emit = defineEmits<{ select: [alert: any] }>()

const metricPreview = computed(() => {
  const metrics = props.alert.relatedMetrics || {}
  return Object.entries(metrics).slice(0, 3).map(([key, val]) => ({
    key,
    val: typeof val === 'number' ? val : String(val),
  }))
})

function severityLabel(s: string) {
  return ({ critical: '紧急', warning: '警告', info: '提示' } as Record<string, string>)[s] || s
}

function statusLabel(s: string) {
  return ({ active: '进行中', acknowledged: '已确认', resolved: '已解决' } as Record<string, string>)[s] || s
}

function formatTime(raw: string) {
  if (!raw) return '—'
  const d = new Date(raw)
  if (Number.isNaN(d.getTime())) return raw
  const now = Date.now()
  const diff = Math.floor((now - d.getTime()) / 1000)
  if (diff < 60) return `${diff} 秒前`
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  return d.toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
  })
}
</script>

<style lang="scss" scoped>
.alert-item {
  position: relative;
  display: flex;
  align-items: stretch;
  padding: 0;
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.2s, border-color 0.2s;
  border-color: rgba(226, 232, 240, 0.9) !important;

  &:hover {
    transform: translateY(-1px);
    box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
    border-color: rgba(99, 102, 241, 0.25) !important;
  }

  &.pulsing {
    animation: pulse-border 2.5s ease-in-out infinite;
  }
}

.rail {
  width: 4px;
  flex-shrink: 0;

  &.critical { background: linear-gradient(180deg, #ef4444, #dc2626); }
  &.warning { background: linear-gradient(180deg, #fbbf24, #f59e0b); }
  &.info { background: linear-gradient(180deg, #60a5fa, #3b82f6); }
}

.item-body {
  flex: 1;
  min-width: 0;
  padding: 14px 16px;
}

.row-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}

.badges {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.sev-badge,
.type-badge,
.status-badge {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  padding: 2px 7px;
  border-radius: 4px;
}

.sev-badge {
  &.critical { color: #dc2626; background: rgba(239, 68, 68, 0.1); }
  &.warning { color: #b45309; background: rgba(245, 158, 11, 0.12); }
  &.info { color: #2563eb; background: rgba(59, 130, 246, 0.1); }
}

.type-badge {
  color: #64748b;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
}

.status-badge {
  &.active { color: #dc2626; background: rgba(239, 68, 68, 0.08); }
  &.acknowledged { color: #b45309; background: rgba(245, 158, 11, 0.1); }
  &.resolved { color: #059669; background: rgba(16, 185, 129, 0.1); }
}

.item-id {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: #cbd5e1;
  font-variant-numeric: tabular-nums;
}

.item-title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.35;
}

.item-detail {
  margin: 6px 0 0;
  font-size: 13px;
  color: #64748b;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.row-meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
}

.meta-cell {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.meta-key {
  font-size: 8px;
  font-weight: 800;
  letter-spacing: 0.06em;
  color: #94a3b8;
}

.meta-val {
  font-size: 11px;
  font-weight: 600;
  color: #475569;
  font-variant-numeric: tabular-nums;
}

.meta-sep {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: #cbd5e1;
}

.metric-preview {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed rgba(148, 163, 184, 0.25);
}

.preview-label {
  font-size: 8px;
  font-weight: 800;
  letter-spacing: 0.06em;
  color: #94a3b8;
}

.metric-chip {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(99, 102, 241, 0.08);
  color: #4338ca;
  font-variant-numeric: tabular-nums;
}

.item-action {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 0 14px;
  color: #94a3b8;
  border-left: 1px solid #f1f5f9;
}

.action-label {
  font-size: 8px;
  font-weight: 800;
  letter-spacing: 0.08em;
}

@keyframes pulse-border {
  0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
  50% { box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.15); }
}
</style>
