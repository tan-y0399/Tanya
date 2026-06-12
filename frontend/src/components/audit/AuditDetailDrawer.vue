<template>
  <el-drawer
    :model-value="visible"
    size="560px"
    direction="rtl"
    :append-to-body="true"
    :z-index="2100"
    class="audit-detail-drawer"
    @update:model-value="$emit('update:visible', $event)"
  >
    <template #header>
      <div class="drawer-head">
        <div class="drawer-head-main">
          <div class="drawer-title-row">
            <AuditIcon name="module-chat" tone="blue" size="sm" boxed />
            <span class="drawer-title">审计详情</span>
          </div>
          <div v-if="detail?.traceId" class="drawer-sub mono">{{ detail.traceId }}</div>
        </div>
        <span v-if="detail?.riskLevel" class="risk-pill" :class="riskClass(detail.riskLevel)">
          {{ detail.riskLevel }}
        </span>
      </div>
    </template>

    <div class="drawer-shell">
      <div v-if="loading" class="loading-box">
        <span class="loading-ring"></span>
        <span>加载审计详情…</span>
      </div>

      <template v-else-if="detail">
        <div class="drawer-content">
          <div class="hero-stats">
            <div v-for="stat in heroStats" :key="stat.label" class="hero-stat" :class="stat.tone">
              <AuditIcon :name="stat.icon" tone="blue" size="sm" />
              <div class="hero-stat-body">
                <span class="hero-stat-label">{{ stat.label }}</span>
                <strong class="hero-stat-value">{{ stat.value }}</strong>
              </div>
            </div>
          </div>

          <div class="tabs-area">
            <el-tabs v-model="activeTab" class="detail-tabs">
              <el-tab-pane label="概览" name="overview">
                <div class="tab-panel-scroll">
                  <div class="overview-panel">
                    <div class="info-grid">
                      <div v-for="item in overviewItems" :key="item.label" class="info-card">
                        <span class="info-label">{{ item.label }}</span>
                        <strong class="info-value">{{ item.value }}</strong>
                      </div>
                    </div>
                    <div v-if="detail.summary" class="summary-card">
                      <div class="block-title">
                        <AuditIcon name="module-all" tone="muted" size="sm" />
                        <span>摘要</span>
                      </div>
                      <p class="summary-text">{{ detail.summary }}</p>
                    </div>
                  </div>
                </div>
              </el-tab-pane>

              <el-tab-pane label="对话内容" name="chat">
                <div class="tab-panel-scroll">
                  <div class="chat-panel">
                    <template v-if="detail.turns && detail.turns.length > 1">
                      <div v-for="turn in detail.turns" :key="turn.traceId" class="turn-block">
                        <div class="turn-head">
                          <span class="turn-badge">第 {{ turn.sequence }} 轮</span>
                          <span class="turn-time">{{ formatTime(turn.timestamp) }}</span>
                        </div>
                        <div v-if="turn.question" class="bubble user-bubble">
                          <span class="bubble-label">用户</span>
                          <p>{{ turn.question }}</p>
                        </div>
                        <div v-if="turn.answer" class="bubble agent-bubble">
                          <span class="bubble-label">Agent</span>
                          <pre>{{ turn.answer }}</pre>
                        </div>
                      </div>
                    </template>
                    <template v-else>
                      <div v-if="detail.question" class="bubble user-bubble">
                        <span class="bubble-label">用户</span>
                        <p>{{ detail.question }}</p>
                      </div>
                      <div v-if="detail.answer" class="bubble agent-bubble">
                        <span class="bubble-label">Agent</span>
                        <pre>{{ cleanAnswer(detail.answer) }}</pre>
                      </div>
                    </template>
                    <div v-if="!detail.question && !detail.answer && !(detail.turns?.length)" class="empty-inline">
                      暂无对话内容
                    </div>
                  </div>
                </div>
              </el-tab-pane>

              <el-tab-pane label="工具调用" name="tools">
                <div class="tab-panel-scroll">
                  <div v-if="detail.tools?.length" class="tool-list">
                    <div v-for="(tool, idx) in detail.tools" :key="`${tool.name}-${idx}`" class="tool-card">
                      <div class="tool-card-head">
                        <span class="tool-name">{{ tool.name }}</span>
                        <span class="risk-tag" :class="riskClass(tool.risk)">{{ tool.risk || 'L1' }}</span>
                      </div>
                      <span class="tool-status" :class="toolStatusClass(tool.status)">{{ tool.status || 'completed' }}</span>
                    </div>
                  </div>
                  <div v-else class="empty-inline">本轮未调用工具</div>
                </div>
              </el-tab-pane>

              <el-tab-pane label="性能追踪" name="telemetry">
                <div class="tab-panel-scroll">
                  <div v-if="telemetrySteps.length" class="telemetry-wrap">
                    <div class="telemetry-summary">
                      总耗时 <strong>{{ totalDurationText }}</strong>
                      <span v-if="detail.telemetry?.slowest_step">
                        · 最慢 {{ detail.telemetry.slowest_step }} ({{ formatMs(detail.telemetry.slowest_ms) }})
                      </span>
                    </div>
                    <div v-for="(step, idx) in telemetrySteps" :key="idx" class="telemetry-row">
                      <div class="telemetry-name">{{ step.step }}</div>
                      <div class="telemetry-bar-wrap">
                        <div
                          class="telemetry-bar"
                          :class="step.status"
                          :style="{ width: barWidth(step.duration_ms) }"
                        ></div>
                      </div>
                      <div class="telemetry-ms">{{ formatMs(step.duration_ms) }}</div>
                    </div>
                  </div>
                  <div v-else class="empty-inline">暂无性能数据</div>
                </div>
              </el-tab-pane>

              <el-tab-pane label="原始 JSON" name="raw">
                <div class="tab-panel-raw">
                  <pre class="raw-json">{{ rawJson }}</pre>
                </div>
              </el-tab-pane>
            </el-tabs>
          </div>

          <div class="drawer-actions">
            <button type="button" class="action-btn ghost" @click="handleReplay">
              <AuditIcon name="action-replay" tone="blue" size="sm" />
              执行回放
            </button>
            <button
              v-if="detail.sessionId"
              type="button"
              class="action-btn primary"
              @click="emitGotoChat"
            >
              跳转对话
            </button>
          </div>
        </div>
      </template>

      <AuditReplayPipeline
        v-model:visible="replayVisible"
        embedded
        :loading="replayLoading"
        :data="replayData"
        @goto-chat="$emit('goto-chat', $event)"
      />
    </div>
  </el-drawer>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import AuditIcon from './AuditIcon.vue'
import AuditReplayPipeline from './AuditReplayPipeline.vue'
import type { AuditDetail, AuditReplayData } from './auditEventMeta'
import { eventLabel, formatMs, intentLabel, riskClass } from './auditEventMeta'
import { formatTime } from '@/utils'
import { getAuditReplay } from '@/api/audit'

const props = defineProps<{
  visible: boolean
  detail: AuditDetail | null
  loading?: boolean
}>()

const emit = defineEmits<{
  'update:visible': [v: boolean]
  'goto-chat': [payload: { sessionId: string; traceId?: string }]
}>()

const activeTab = ref('overview')
const replayVisible = ref(false)
const replayLoading = ref(false)
const replayData = ref<AuditReplayData | null>(null)
const replayTotalMs = ref<number | undefined>(undefined)

watch(() => props.visible, (v) => {
  if (v) {
    activeTab.value = 'overview'
  } else {
    replayVisible.value = false
    replayData.value = null
    replayTotalMs.value = undefined
  }
})

watch(
  () => props.detail?.traceId,
  async (traceId) => {
    replayTotalMs.value = undefined
    if (!traceId || !props.detail) return
    const hasMs = props.detail.totalMs != null || props.detail.telemetry?.total_ms != null
    if (hasMs) return
    try {
      const replay = await getAuditReplay(traceId)
      if (replay.totalMs != null) replayTotalMs.value = replay.totalMs
    } catch {
      /* ignore */
    }
  },
  { immediate: true },
)

const telemetrySteps = computed(() => props.detail?.telemetry?.steps || [])
const maxMs = computed(() => Math.max(...telemetrySteps.value.map((s) => s.duration_ms || 0), 1))
const rawJson = computed(() => JSON.stringify(props.detail, null, 2))

const totalDurationText = computed(() => {
  const d = props.detail
  if (!d) return '—'
  let ms = replayTotalMs.value ?? d.totalMs ?? d.telemetry?.total_ms
  if (ms == null && d.startedAt && d.timestamp) {
    const start = new Date(d.startedAt).getTime()
    const end = new Date(d.timestamp).getTime()
    if (!Number.isNaN(start) && !Number.isNaN(end) && end > start) {
      ms = end - start
    }
  }
  return formatMs(ms)
})

const userDisplay = computed(() => {
  const d = props.detail
  if (!d) return '—'
  const name = d.userDisplayName || d.username
  if (name && d.userRoleLabel) return `${name}（${d.userRoleLabel}）`
  return name || d.userId || '—'
})

const heroStats = computed(() => {
  const d = props.detail
  if (!d) return []
  return [
    { label: '意图', value: intentLabel(d.intent) || '—', icon: 'module-chat' as const, tone: 'tone-blue' },
    { label: '总耗时', value: totalDurationText.value, icon: 'module-all' as const, tone: 'tone-emerald' },
    { label: '工具', value: String(d.tools?.length || 0), icon: 'module-workflow' as const, tone: 'tone-violet' },
    { label: '轮次', value: `${d.turnCount || 1} 轮`, icon: 'module-resume' as const, tone: 'tone-amber' },
  ]
})

const overviewItems = computed(() => {
  const d = props.detail
  if (!d) return []
  return [
    { label: '事件类型', value: eventLabel(d.eventType || '') },
    { label: '用户', value: userDisplay.value },
    { label: '时间', value: formatTime(d.timestamp || '') },
    { label: '总耗时', value: totalDurationText.value },
    { label: '会话 ID', value: d.sessionId ? d.sessionId.slice(0, 12) + '…' : '—' },
  ]
})

function cleanAnswer(text: string) {
  return text.replace(/<!--KYLIN_TOOLS-->/g, '').trim()
}

function barWidth(ms?: number) {
  const pct = Math.max(8, Math.round(((ms || 0) / maxMs.value) * 100))
  return `${pct}%`
}

function toolStatusClass(status?: string) {
  if (status === 'rejected' || status === 'failed') return 'is-error'
  if (status === 'pending_approval' || status === 'pending_confirm') return 'is-warn'
  return 'is-ok'
}

function emitGotoChat() {
  if (!props.detail?.sessionId) return
  emit('goto-chat', {
    sessionId: props.detail.sessionId,
    traceId: props.detail.traceId,
  })
}

async function handleReplay() {
  if (!props.detail?.traceId) return
  await openReplay(props.detail.traceId)
}

async function openReplay(traceId: string) {
  replayVisible.value = true
  replayLoading.value = true
  replayData.value = null
  try {
    replayData.value = await getAuditReplay(traceId)
  } catch {
    replayData.value = { traceId, steps: [] }
  } finally {
    replayLoading.value = false
  }
}

defineExpose({ openReplay })
</script>

<style scoped lang="scss">
.drawer-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
}

.drawer-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.drawer-title {
  font-size: 17px;
  font-weight: 700;
  color: #1e293b;
}

.drawer-sub {
  font-size: 11px;
  color: #94a3b8;
  margin-top: 6px;
}

.mono { font-family: 'JetBrains Mono', Consolas, monospace; }

.risk-pill {
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
  &.l1 { background: #ecfdf5; color: #059669; }
  &.l2 { background: #eff6ff; color: #2563eb; }
  &.l3 { background: #fff7ed; color: #ea580c; }
  &.l4, &.l5 { background: #fef2f2; color: #dc2626; }
}

.drawer-shell {
  position: relative;
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.drawer-content {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.loading-box, .empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 48px 24px;
  color: #94a3b8;
  font-size: 13px;
}

.loading-ring {
  width: 28px;
  height: 28px;
  border: 3px solid #e2e8f0;
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: spin 0.75s linear infinite;
}

.hero-stats {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  margin-bottom: 12px;
  flex-shrink: 0;
}

.hero-stat {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 12px;
  background: linear-gradient(135deg, #f8fafc, #fff);
  border: 1px solid #eef2f7;
  transition: transform 0.18s ease, box-shadow 0.18s ease;
  &:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 20px rgba(15, 23, 42, 0.06);
  }
}

.hero-stat-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.hero-stat-label {
  font-size: 10px;
  color: #94a3b8;
  letter-spacing: 0.3px;
}

.hero-stat-value {
  font-size: 14px;
  font-weight: 700;
  color: #1e293b;
}

.tone-blue .hero-stat-value { color: #2563eb; }
.tone-emerald .hero-stat-value { color: #059669; }
.tone-violet .hero-stat-value { color: #7c3aed; }
.tone-amber .hero-stat-value { color: #d97706; }

.tabs-area {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.tab-panel-scroll {
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 14px 4px 10px 0;
  box-sizing: border-box;
}

.tab-panel-raw {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding-top: 14px;
  box-sizing: border-box;
}

.empty-inline {
  text-align: center;
  padding: 32px 16px;
  color: #94a3b8;
  font-size: 13px;
}

.detail-tabs {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;

  :deep(.el-tabs__header) {
    margin-bottom: 0;
    flex-shrink: 0;
  }
  :deep(.el-tabs__content) {
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }
  :deep(.el-tab-pane) {
    height: 100%;
    overflow: hidden;
  }
  :deep(.el-tabs__item) {
    font-size: 13px;
    font-weight: 600;
    padding: 0 14px;
    transition: color 0.15s;
  }
  :deep(.el-tabs__active-bar) {
    height: 3px;
    border-radius: 999px;
  }
}

.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-bottom: 14px;
}

.info-card {
  padding: 12px 14px;
  border-radius: 10px;
  background: #f8fafc;
  border: 1px solid transparent;
  transition: border-color 0.15s, background 0.15s;
  &:hover {
    background: #fff;
    border-color: #e2e8f0;
  }
}

.info-label {
  display: block;
  font-size: 11px;
  color: #94a3b8;
  margin-bottom: 4px;
}

.info-value {
  font-size: 13px;
  color: #1e293b;
  word-break: break-all;
}

.summary-card {
  padding: 14px 16px;
  border-radius: 12px;
  background: linear-gradient(180deg, #fffbeb, #fff);
  border: 1px solid #fef3c7;
}

.block-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  font-weight: 700;
  color: #92400e;
  margin-bottom: 8px;
}

.summary-text {
  margin: 0;
  font-size: 13px;
  line-height: 1.65;
  color: #475569;
}

.turn-block {
  margin-bottom: 18px;
  padding-bottom: 16px;
  border-bottom: 1px dashed #e2e8f0;
  &:last-child { border-bottom: none; }
}

.turn-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.turn-badge {
  font-size: 11px;
  font-weight: 700;
  color: #4338ca;
  background: #eef2ff;
  padding: 3px 10px;
  border-radius: 999px;
}

.turn-time {
  font-size: 11px;
  color: #94a3b8;
}

.bubble {
  margin-bottom: 10px;
  padding: 12px 14px;
  border-radius: 12px;
  animation: bubble-in 0.3s ease;
  .bubble-label {
    display: block;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.4px;
    margin-bottom: 6px;
    opacity: 0.75;
  }
  p, pre {
    margin: 0;
    font-size: 13px;
    line-height: 1.6;
    white-space: pre-wrap;
    word-break: break-word;
    font-family: inherit;
  }
}

.user-bubble {
  background: linear-gradient(135deg, #eff6ff, #dbeafe);
  border: 1px solid #bfdbfe;
  color: #1e3a8a;
}

.agent-bubble {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  color: #334155;
}

.tool-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.tool-card {
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid #eef2f7;
  background: #fff;
  transition: transform 0.15s, box-shadow 0.15s;
  &:hover {
    transform: translateX(2px);
    box-shadow: 0 6px 16px rgba(15, 23, 42, 0.05);
  }
}

.tool-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}

.tool-name {
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
  font-family: 'JetBrains Mono', Consolas, monospace;
}

.tool-status {
  font-size: 12px;
  font-weight: 600;
  &.is-ok { color: #059669; }
  &.is-warn { color: #d97706; }
  &.is-error { color: #dc2626; }
}

.telemetry-summary {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 14px;
  padding: 10px 12px;
  background: #f8fafc;
  border-radius: 8px;
  strong { color: #1e293b; }
}

.telemetry-row {
  display: grid;
  grid-template-columns: 120px 1fr 56px;
  gap: 8px;
  align-items: center;
  margin-bottom: 10px;
}

.telemetry-name {
  font-size: 11px;
  color: #475569;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.telemetry-bar-wrap {
  height: 8px;
  background: #f1f5f9;
  border-radius: 999px;
  overflow: hidden;
}

.telemetry-bar {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #60a5fa, #3b82f6);
  transition: width 0.4s ease;
  &.error { background: linear-gradient(90deg, #f87171, #ef4444); }
  &.warn, &.warning { background: linear-gradient(90deg, #fbbf24, #f59e0b); }
}

.telemetry-ms {
  font-size: 11px;
  font-family: 'JetBrains Mono', Consolas, monospace;
  color: #64748b;
  text-align: right;
}

.raw-json {
  flex: 1;
  min-height: 0;
  height: 100%;
  max-height: none;
  margin: 0;
  padding: 14px;
  background: #0f172a;
  color: #e2e8f0;
  border-radius: 10px;
  font-size: 11px;
  line-height: 1.5;
  overflow: auto;
  box-sizing: border-box;
}

.drawer-actions {
  display: flex;
  gap: 10px;
  flex-shrink: 0;
  padding-top: 14px;
  margin-top: 0;
  border-top: 1px solid #f1f5f9;
  background: #fff;
}

.action-btn {
  flex: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 40px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s, background 0.15s;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #475569;
  &:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 16px rgba(15, 23, 42, 0.08);
  }
  &.primary {
    background: linear-gradient(135deg, #2563eb, #1d4ed8);
    border-color: transparent;
    color: #fff;
    &:hover { box-shadow: 0 8px 20px rgba(37, 99, 235, 0.35); }
  }
  &.ghost:hover {
    border-color: #bfdbfe;
    color: #2563eb;
  }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

@keyframes bubble-in {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>

<style lang="scss">
.audit-detail-drawer.el-drawer {
  .el-drawer__body {
    padding: 0 20px 16px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    height: calc(100% - 72px);
    box-sizing: border-box;
  }
  .el-drawer__header {
    margin-bottom: 8px;
    padding-bottom: 12px;
    border-bottom: 1px solid #f1f5f9;
    flex-shrink: 0;
  }
}
</style>
