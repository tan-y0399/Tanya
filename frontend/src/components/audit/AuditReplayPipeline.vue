<template>
  <Transition name="replay-slide">
    <div
      v-if="visible"
      class="replay-overlay"
      :class="{ embedded }"
      @click.self="embedded ? $emit('update:visible', false) : $emit('update:visible', false)"
    >
      <div class="replay-panel" @click.stop>
        <header class="replay-header">
          <div class="replay-header-text">
            <div class="replay-badge">
              <AuditIcon name="action-replay" tone="blue" size="sm" />
              <span>执行回放</span>
            </div>
            <p class="replay-sub mono">{{ data?.traceId }}</p>
          </div>
          <button type="button" class="modal-close" aria-label="关闭" @click="$emit('update:visible', false)">
            &times;
          </button>
        </header>

        <div v-if="summaryItems.length" class="summary-bar">
          <div v-for="item in summaryItems" :key="item.label" class="sum-item" :class="item.tone">
            <span class="sum-label">{{ item.label }}</span>
            <span class="sum-value">{{ item.value }}</span>
          </div>
        </div>

        <div class="pipeline-body">
          <div v-if="loading" class="loading">
            <span class="loading-ring"></span>
            <span>加载回放数据…</span>
          </div>
          <div v-else class="flow-track">
            <div
              v-for="(s, idx) in steps"
              :key="`${s.step}-${idx}`"
              class="flow-step"
              :class="[mapStatus(s.status), { 'is-last': idx === steps.length - 1 }]"
              :style="{ animationDelay: `${idx * 45}ms` }"
            >
              <div class="step-rail">
                <span class="step-num">{{ s.step }}</span>
                <span v-if="idx < steps.length - 1" class="step-line" :class="mapStatus(s.status)"></span>
              </div>
              <div class="step-card">
                <div class="step-card-head">
                  <span class="step-status-icon" :class="mapStatus(s.status)">
                    <template v-if="mapStatus(s.status) === 'done'">✓</template>
                    <template v-else-if="mapStatus(s.status) === 'error'">!</template>
                    <template v-else>•</template>
                  </span>
                  <span class="step-type">{{ s.eventType }}</span>
                  <span v-if="s.riskLevel" class="risk-tag" :class="riskClass(s.riskLevel)">{{ s.riskLevel }}</span>
                  <span v-if="s.duration != null" class="step-duration">{{ formatMs(s.duration) }}</span>
                </div>
                <div class="step-title">{{ s.title }}</div>
                <p v-if="s.detail" class="step-detail">{{ s.detail }}</p>
              </div>
            </div>
          </div>
        </div>

        <footer class="replay-footer">
          <button
            v-if="data?.sessionId"
            type="button"
            class="tech-btn primary"
            @click="$emit('goto-chat', { sessionId: data!.sessionId!, traceId: data?.traceId })"
          >
            跳转对话
          </button>
          <button type="button" class="tech-btn" @click="$emit('update:visible', false)">关闭</button>
        </footer>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AuditIcon from './AuditIcon.vue'
import type { AuditReplayData, AuditReplayStep } from './auditEventMeta'
import { formatMs, intentLabel, riskClass } from './auditEventMeta'

const props = defineProps<{
  visible: boolean
  loading?: boolean
  data: AuditReplayData | null
  /** 嵌入审计详情抽屉内，覆盖在详情内容之上 */
  embedded?: boolean
}>()

defineEmits<{
  'update:visible': [v: boolean]
  'goto-chat': [payload: { sessionId: string; traceId?: string }]
}>()

const steps = computed(() => props.data?.steps || [])

const summaryItems = computed(() => {
  const d = props.data
  if (!d) return []
  return [
    { label: '意图', value: d.intentLabel || intentLabel(d.intent) || '—', tone: 'tone-blue' },
    { label: '风险', value: d.riskLevel || 'L1', tone: 'tone-amber' },
    { label: '工具', value: String(d.toolCallCount ?? 0), tone: 'tone-violet' },
    { label: '总耗时', value: formatMs(d.totalMs), tone: 'tone-emerald' },
  ]
})

function mapStatus(status: AuditReplayStep['status']) {
  if (status === 'success' || status === 'info') return 'done'
  if (status === 'error') return 'error'
  return 'running'
}
</script>

<style scoped lang="scss">
.replay-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  backdrop-filter: blur(6px);
  z-index: 2500;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;

  &.embedded {
    position: absolute;
    inset: 0;
    z-index: 20;
    border-radius: 0;
    padding: 0;
    background: rgba(248, 250, 252, 0.72);
    backdrop-filter: blur(10px);
    align-items: stretch;
    justify-content: stretch;

    .replay-panel {
      width: 100%;
      max-height: none;
      height: 100%;
      border-radius: 0;
      box-shadow: none;
      animation: replay-in-drawer 0.28s cubic-bezier(0.22, 1, 0.36, 1);
    }
  }
}

.replay-panel {
  width: min(720px, 100%);
  max-height: 88vh;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 24px 64px rgba(15, 23, 42, 0.18);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: replay-pop 0.26s cubic-bezier(0.22, 1, 0.36, 1);
}

.replay-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 18px 20px 14px;
  border-bottom: 1px solid #f1f5f9;
  background: linear-gradient(135deg, #eff6ff 0%, #fff 55%);
}

.replay-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 17px;
  font-weight: 700;
  color: #1e293b;
}

.replay-sub { margin: 6px 0 0; font-size: 11px; color: #94a3b8; }
.mono { font-family: 'JetBrains Mono', Consolas, monospace; }

.modal-close {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.85);
  color: #64748b;
  font-size: 22px;
  cursor: pointer;
  transition: background 0.15s, color 0.15s, transform 0.15s;
  &:hover { background: #fff; color: #1e293b; transform: scale(1.05); }
}

.summary-bar {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  padding: 14px 20px;
  background: #fafbfc;
  border-bottom: 1px solid #f1f5f9;
}

.sum-item {
  padding: 10px 12px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid #eef2f7;
  transition: transform 0.15s, box-shadow 0.15s;
  &:hover { transform: translateY(-1px); box-shadow: 0 6px 16px rgba(15, 23, 42, 0.06); }
  .sum-label { display: block; font-size: 10px; color: #94a3b8; letter-spacing: 0.4px; margin-bottom: 4px; }
  .sum-value { font-size: 13px; font-weight: 700; color: #1e293b; }
  &.tone-blue .sum-value { color: #2563eb; }
  &.tone-amber .sum-value { color: #d97706; }
  &.tone-violet .sum-value { color: #7c3aed; }
  &.tone-emerald .sum-value { color: #059669; }
}

.pipeline-body {
  flex: 1;
  overflow-y: auto;
  padding: 18px 20px;
}

.loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  color: #94a3b8;
  padding: 40px;
}

.loading-ring {
  width: 28px;
  height: 28px;
  border: 3px solid #e2e8f0;
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: spin 0.75s linear infinite;
}

.flow-track { display: flex; flex-direction: column; }
.flow-step {
  display: flex;
  gap: 12px;
  animation: step-in 0.35s ease both;
}

.step-rail {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 28px;
  flex-shrink: 0;
}

.step-num {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #e2e8f0;
  color: #64748b;
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s, color 0.2s;
}

.flow-step.done .step-num { background: #d1fae5; color: #059669; }
.flow-step.error .step-num { background: #fee2e2; color: #dc2626; }

.step-line {
  flex: 1;
  width: 2px;
  min-height: 20px;
  margin: 4px 0;
  background: #e2e8f0;
  transition: background 0.2s;
  &.done { background: linear-gradient(180deg, #a7f3d0, #6ee7b7); }
  &.error { background: #fecaca; }
}

.step-card {
  flex: 1;
  border: 1px solid #eef2f7;
  border-radius: 12px;
  padding: 12px 14px;
  margin-bottom: 10px;
  background: #fff;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.03);
  transition: border-color 0.15s, box-shadow 0.15s;
  &:hover { border-color: #dbeafe; box-shadow: 0 6px 18px rgba(37, 99, 235, 0.08); }
}

.step-card-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 4px;
}

.step-status-icon {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
  &.done { background: #d1fae5; color: #059669; }
  &.error { background: #fee2e2; color: #dc2626; }
  &.running { background: #dbeafe; color: #2563eb; }
}

.step-type {
  font-size: 10px;
  font-weight: 700;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.4px;
}

.step-duration {
  margin-left: auto;
  font-size: 11px;
  font-family: 'JetBrains Mono', Consolas, monospace;
  color: #64748b;
}

.step-title { font-size: 14px; font-weight: 600; color: #1e293b; }
.step-detail { margin: 6px 0 0; font-size: 12px; color: #64748b; line-height: 1.55; }

.replay-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 20px;
  border-top: 1px solid #f1f5f9;
  background: rgba(255, 255, 255, 0.92);
}

.replay-slide-enter-active,
.replay-slide-leave-active {
  transition: opacity 0.22s ease;
}
.replay-slide-enter-from,
.replay-slide-leave-to {
  opacity: 0;
}

@keyframes replay-pop {
  from { opacity: 0; transform: scale(0.96) translateY(8px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

@keyframes replay-in-drawer {
  from { opacity: 0; transform: translateX(12px); }
  to { opacity: 1; transform: translateX(0); }
}

@keyframes step-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
