<template>
  <teleport to="body">
    <div v-if="alert" class="modal-overlay" @click.self="emit('close')">
      <div class="modal-shell" role="dialog" aria-modal="true" @click.stop>
        <div class="modal-brackets">
          <span class="corner tl"></span>
          <span class="corner tr"></span>
          <span class="corner bl"></span>
          <span class="corner br"></span>
        </div>

        <button type="button" class="modal-close" aria-label="关闭" @click="emit('close')">&times;</button>

        <header class="modal-head">
          <div class="head-tags">
            <span class="sev-tag" :class="alert.severity">{{ severityLabel(alert.severity) }}</span>
            <span class="type-tag">{{ alert.type }}</span>
            <span class="status-tag" :class="alert.status">{{ statusLabel(alert.status) }}</span>
          </div>
          <h3 class="modal-title">{{ alert.title }}</h3>
          <div class="modal-meta">
            <span><b>ID</b> {{ alert.id }}</span>
            <span><b>HOST</b> {{ alert.host }}</span>
            <span><b>TIME</b> {{ formatFullTime(alert.time) }}</span>
            <span><b>SRC</b> {{ alert.source }}</span>
          </div>
        </header>

        <section class="info-section">
          <div class="sec-head"><span class="sec-code">DET-01</span><h4>告警详情</h4></div>
          <p>{{ alert.detail }}</p>
        </section>

        <section class="info-section rca">
          <div class="sec-head"><span class="sec-code">RCA-02</span><h4>根因分析</h4></div>
          <p>{{ alert.rootCause }}</p>
        </section>

        <section class="info-section suggest">
          <div class="sec-head"><span class="sec-code">ACT-03</span><h4>处理建议</h4></div>
          <p>{{ alert.suggestion }}</p>
        </section>

        <section v-if="metricEntries.length" class="info-section metrics">
          <div class="sec-head"><span class="sec-code">MET-04</span><h4>关联指标</h4></div>
          <div class="metrics-grid">
            <div v-for="m in metricEntries" :key="m.key" class="metric-cell">
              <span class="m-key">{{ m.key }}</span>
              <span class="m-val">{{ m.val }}</span>
            </div>
          </div>
        </section>

        <footer class="modal-actions">
          <button
            v-if="alert.status === 'active'"
            type="button"
            class="action-btn primary"
            @click="emit('acknowledge')"
          >
            确认告警
          </button>
          <button
            v-if="alert.status !== 'resolved'"
            type="button"
            class="action-btn success"
            @click="emit('resolve')"
          >
            标记已解决
          </button>
          <button type="button" class="action-btn ghost" @click="emit('close')">关闭</button>
        </footer>
      </div>
    </div>
  </teleport>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ alert: any | null }>()
const emit = defineEmits<{ close: []; acknowledge: []; resolve: [] }>()

const metricEntries = computed(() => {
  const metrics = props.alert?.relatedMetrics || {}
  return Object.entries(metrics).map(([key, val]) => ({ key, val }))
})

function severityLabel(s: string) {
  return ({ critical: '紧急', warning: '警告', info: '提示' } as Record<string, string>)[s] || s
}

function statusLabel(s: string) {
  return ({ active: '进行中', acknowledged: '已确认', resolved: '已解决' } as Record<string, string>)[s] || s
}

function formatFullTime(raw: string) {
  if (!raw) return '—'
  const d = new Date(raw)
  if (Number.isNaN(d.getTime())) return raw
  return d.toLocaleString('zh-CN', { hour12: false })
}
</script>

<style lang="scss" scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  backdrop-filter: blur(6px);
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.modal-shell {
  position: relative;
  width: min(680px, 100%);
  max-height: 85vh;
  overflow-y: auto;
  padding: 28px 28px 24px;
  border-radius: 16px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid rgba(148, 163, 184, 0.25);
  box-shadow: 0 24px 64px rgba(15, 23, 42, 0.18);
}

.modal-brackets .corner {
  position: absolute;
  width: 14px;
  height: 14px;
  border-color: rgba(239, 68, 68, 0.45);
  border-style: solid;

  &.tl { top: 10px; left: 10px; border-width: 2px 0 0 2px; }
  &.tr { top: 10px; right: 10px; border-width: 2px 2px 0 0; }
  &.bl { bottom: 10px; left: 10px; border-width: 0 0 2px 2px; }
  &.br { bottom: 10px; right: 10px; border-width: 0 2px 2px 0; }
}

.modal-close {
  position: absolute;
  top: 12px;
  right: 14px;
  border: none;
  background: none;
  font-size: 24px;
  color: #94a3b8;
  cursor: pointer;
  line-height: 1;
}

.modal-head {
  margin-bottom: 18px;
  padding-right: 24px;
}

.head-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.sev-tag, .type-tag, .status-tag {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.05em;
  padding: 3px 8px;
  border-radius: 4px;
}

.sev-tag {
  &.critical { color: #dc2626; background: rgba(239, 68, 68, 0.1); }
  &.warning { color: #b45309; background: rgba(245, 158, 11, 0.12); }
  &.info { color: #2563eb; background: rgba(59, 130, 246, 0.1); }
}

.type-tag {
  color: #64748b;
  background: #f1f5f9;
}

.status-tag {
  &.active { color: #dc2626; background: rgba(239, 68, 68, 0.08); }
  &.acknowledged { color: #b45309; background: rgba(245, 158, 11, 0.1); }
  &.resolved { color: #059669; background: rgba(16, 185, 129, 0.1); }
}

.modal-title {
  margin: 0 0 8px;
  font-size: 20px;
  font-weight: 800;
  color: #0f172a;
}

.modal-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 16px;
  font-size: 11px;
  color: #64748b;

  b {
    margin-right: 4px;
    font-size: 9px;
    letter-spacing: 0.06em;
    color: #94a3b8;
  }
}

.info-section {
  margin-bottom: 14px;
  padding: 12px 14px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid #e2e8f0;

  p {
    margin: 0;
    font-size: 14px;
    line-height: 1.7;
    color: #334155;
    white-space: pre-line;
  }

  &.rca {
    background: rgba(245, 158, 11, 0.06);
    border-color: rgba(245, 158, 11, 0.2);
    p { color: #78350f; }
  }

  &.suggest {
    background: rgba(59, 130, 246, 0.06);
    border-color: rgba(59, 130, 246, 0.2);
    p { color: #1e3a8a; }
  }
}

.sec-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;

  h4 {
    margin: 0;
    font-size: 13px;
    font-weight: 700;
    color: #475569;
  }
}

.sec-code {
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.06em;
  color: #94a3b8;
  padding: 2px 6px;
  border-radius: 4px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.metric-cell {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 10px;
  border-radius: 8px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.m-key {
  font-size: 11px;
  color: #94a3b8;
}

.m-val {
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  font-variant-numeric: tabular-nums;
}

.modal-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 8px;
  padding-top: 16px;
  border-top: 1px solid #e2e8f0;
}

.action-btn {
  padding: 8px 18px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;

  &.primary {
    background: #2563eb;
    border-color: #2563eb;
    color: #fff;
    &:hover { background: #3b82f6; }
  }

  &.success {
    background: #059669;
    border-color: #059669;
    color: #fff;
    &:hover { background: #10b981; }
  }

  &.ghost {
    color: #64748b;
    &:hover { border-color: #94a3b8; }
  }
}
</style>
