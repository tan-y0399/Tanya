<template>
  <article class="audit-flow-card" :style="cardStyle" @click="$emit('open', record)">
    <div class="card-glow" aria-hidden="true"></div>

    <header class="card-header">
      <div class="type-badge">
        <AuditIcon :name="eventIconName" :tone="eventIconTone" size="sm" boxed />
        <div class="type-text">
          <strong>{{ eventLabel(record.eventType) }}</strong>
          <span v-if="intentText">{{ intentText }}</span>
          <span v-else-if="record.turnCount && record.turnCount > 1">{{ record.turnCount }} 轮对话</span>
        </div>
      </div>
      <div class="header-right">
        <span class="flow-status" :class="statusToneClass">{{ statusText }}</span>
        <span class="risk-tag" :class="riskClass(record.riskLevel)">{{ record.riskLevel || 'L1' }}</span>
        <time class="card-time">{{ formatTime(record.timestamp) }}</time>
      </div>
    </header>

    <p class="card-summary">{{ record.summary }}</p>
    <p v-if="record.eventType === 'blocked_injection' && blockReasonText" class="card-block-reason">
      {{ blockReasonText }}
    </p>

    <div v-if="showPipeline" class="card-pipeline">
      <div class="pipeline-track" aria-hidden="true">
        <svg class="track-svg" preserveAspectRatio="none">
          <defs>
            <linearGradient :id="`grad-${uid}`" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" :stop-color="accentColor" stop-opacity="0.15" />
              <stop offset="50%" :stop-color="accentColor" stop-opacity="0.55" />
              <stop offset="100%" :stop-color="accentColor" stop-opacity="0.15" />
            </linearGradient>
          </defs>
          <line
            x1="0" y1="50%" x2="100%" y2="50%"
            :stroke="`url(#grad-${uid})`"
            stroke-width="2"
            stroke-dasharray="6 4"
          />
        </svg>
      </div>

      <div class="node-row">
        <div v-for="(node, idx) in flowNodes" :key="node.id" class="node-wrap">
          <div
            class="flow-node"
            :class="[`tone-${nodeStatusTone(node.status)}`, { active: node.status === 'passed' || node.status === 'warning' }]"
            :title="node.detail"
          >
            <span class="node-index">{{ String(idx + 1).padStart(2, '0') }}</span>
            <div class="node-body">
              <span class="node-label">{{ node.label }}</span>
              <span class="node-sub">{{ node.sublabel }}</span>
              <span class="meta-chip status">{{ nodeStatusLabel(node.status) }}</span>
            </div>
          </div>
          <div v-if="idx < flowNodes.length - 1" class="node-connector" aria-hidden="true">
            <svg width="24" height="14" viewBox="0 0 24 14">
              <path
                d="M0 7 H14 L10 3 M14 7 L10 11"
                fill="none"
                :stroke="accentColor"
                stroke-width="1.5"
                stroke-linecap="round"
                stroke-linejoin="round"
                opacity="0.65"
              />
            </svg>
          </div>
        </div>
      </div>
    </div>

    <footer class="card-footer">
      <span class="meta-item" :title="record.userId">
        <AuditIcon name="meta-user" tone="muted" size="sm" />
        {{ displayUser }}
      </span>
      <span class="meta-item mono">
        <AuditIcon name="meta-trace" tone="muted" size="sm" />
        {{ shortTrace }}
      </span>
      <span v-if="record.totalMs != null" class="meta-item">
        <AuditIcon name="meta-time" tone="muted" size="sm" />
        {{ formatMs(record.totalMs) }}
      </span>
      <span v-if="record.toolCount" class="meta-item">
        <AuditIcon name="meta-tool" tone="muted" size="sm" />
        {{ record.toolCount }} 工具
      </span>
      <div class="card-actions" @click.stop>
        <button class="action-btn" @click="$emit('detail', record)">详情</button>
        <button class="action-btn primary" @click="$emit('replay', record.traceId)">
          <AuditIcon name="action-replay" tone="blue" size="sm" /> 回放
        </button>
        <button
          v-if="record.sessionId"
          class="action-btn"
          @click="$emit('goto-chat', { sessionId: record.sessionId!, traceId: record.traceId })"
        >对话</button>
      </div>
    </footer>
  </article>
</template>

<script setup lang="ts">
import { computed, withDefaults } from 'vue'
import AuditIcon from './AuditIcon.vue'
import {
  type AuditIconName,
  type AuditRecordItem,
  EVENT_META,
  eventLabel,
  formatMs,
  intentLabel,
  riskClass,
} from './auditEventMeta'
import {
  buildAuditFlowNodes,
  eventColor,
  flowStatusForRecord,
  type AuditFlowNode,
} from './auditTabMeta'
import { formatTime } from '@/utils'

const props = withDefaults(
  defineProps<{ record: AuditRecordItem; showPipeline?: boolean }>(),
  { showPipeline: true },
)

defineEmits<{
  open: [record: AuditRecordItem]
  detail: [record: AuditRecordItem]
  replay: [traceId: string]
  'goto-chat': [payload: { sessionId: string; traceId?: string }]
}>()

const uid = Math.random().toString(36).slice(2, 8)

const accentColor = computed(() => eventColor(props.record.eventType))
const cardStyle = computed(() => ({ '--accent-color': accentColor.value }))
const flowNodes = computed(() => buildAuditFlowNodes(props.record))

const statusMeta = computed(() => flowStatusForRecord(props.record))
const statusText = computed(() => statusMeta.value.text)
const statusToneClass = computed(() => statusMeta.value.tone)

const eventIconName = computed<AuditIconName>(
  () => EVENT_META[props.record.eventType]?.icon || 'module-all',
)
const eventIconTone = computed(() => {
  const t = props.record.eventType
  if (t === 'blocked_injection') return 'red'
  if (t === 'chat_resume') return 'blue'
  return 'blue'
})
const intentText = computed(() => intentLabel(props.record.intent))
const shortTrace = computed(() => {
  const id = props.record.traceId || ''
  return id.length > 16 ? `${id.slice(0, 16)}…` : id
})
const displayUser = computed(() => {
  const name = props.record.userDisplayName || props.record.username
  if (name && props.record.userRoleLabel) return `${name}（${props.record.userRoleLabel}）`
  return name || props.record.userId
})

const blockReasonText = computed(() => {
  if (props.record.eventType !== 'blocked_injection') return ''
  const reason = props.record.blockReason || props.record.summary || ''
  const stage = props.record.blockStage
  if (!reason) return ''
  return stage ? `[${stage}] ${reason}` : reason
})

function nodeStatusTone(s: AuditFlowNode['status']): string {
  if (s === 'passed') return 'ok'
  if (s === 'blocked') return 'danger'
  if (s === 'warning') return 'warn'
  if (s === 'pending') return 'warn'
  return 'muted'
}

function nodeStatusLabel(s: AuditFlowNode['status']): string {
  const m: Record<AuditFlowNode['status'], string> = {
    passed: '通过',
    blocked: '阻断',
    pending: '等待',
    idle: '—',
    warning: '注意',
  }
  return m[s] || s
}
</script>

<style scoped lang="scss">
.audit-flow-card {
  position: relative;
  border-radius: 16px;
  border: 1px solid color-mix(in srgb, var(--accent-color) 18%, #e2e8f0);
  background:
    radial-gradient(ellipse 80% 60% at 10% 0%, color-mix(in srgb, var(--accent-color) 6%, transparent), transparent 55%),
    #fff;
  padding: 18px 20px 16px;
  cursor: pointer;
  overflow: hidden;
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
  transition: border-color 0.2s, box-shadow 0.25s, transform 0.2s;

  &:hover {
    border-color: color-mix(in srgb, var(--accent-color) 35%, #cbd5e1);
    box-shadow: 0 10px 28px color-mix(in srgb, var(--accent-color) 10%, rgba(15, 23, 42, 0.06));
    transform: translateY(-1px);
  }
}

.card-glow {
  position: absolute;
  inset: -40% -20% auto;
  height: 120px;
  background: radial-gradient(ellipse, color-mix(in srgb, var(--accent-color) 8%, transparent), transparent 70%);
  pointer-events: none;
  opacity: 0.9;
}

.card-header {
  position: relative;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.type-badge {
  display: flex;
  align-items: center;
  gap: 10px;
}

.type-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  strong {
    font-size: 14px;
    font-weight: 700;
    color: #1e293b;
  }
  span {
    font-size: 11px;
    color: #64748b;
  }
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.flow-status {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  padding: 3px 8px;
  border-radius: 999px;
  &.ok { background: #ecfdf5; color: #059669; border: 1px solid #a7f3d0; }
  &.danger { background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; }
  &.warn { background: #fffbeb; color: #d97706; border: 1px solid #fde68a; }
  &.muted { background: #f1f5f9; color: #64748b; border: 1px solid #e2e8f0; }
}

.risk-tag {
  font-size: 10px;
  font-weight: 800;
  padding: 2px 6px;
  border-radius: 4px;
  &.l1 { color: #059669; background: #ecfdf5; }
  &.l2 { color: #0891b2; background: #ecfeff; }
  &.l3 { color: #d97706; background: #fffbeb; }
  &.l4 { color: #dc2626; background: #fef2f2; }
  &.l5 { color: #be123c; background: #fff1f2; }
}

.card-time {
  font-size: 11px;
  color: #64748b;
}

.card-summary {
  position: relative;
  margin: 0 0 14px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  font-size: 14px;
  font-weight: 500;
  color: #334155;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-block-reason {
  margin: -6px 0 14px;
  padding: 8px 12px;
  border-radius: 8px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  font-size: 13px;
  color: #b91c1c;
  line-height: 1.45;
}

.card-pipeline {
  position: relative;
  margin-bottom: 14px;
  padding: 12px 4px 8px;
  border-radius: 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  overflow-x: auto;
}

.pipeline-track {
  position: absolute;
  left: 16px;
  right: 16px;
  top: 50%;
  height: 2px;
  transform: translateY(-50%);
  pointer-events: none;
  opacity: 0.5;
}

.track-svg { width: 100%; height: 100%; }

.node-row {
  position: relative;
  display: flex;
  align-items: stretch;
  gap: 0;
  min-width: min-content;
  padding: 4px 8px;
}

.node-wrap {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.flow-node {
  width: 118px;
  min-height: 76px;
  padding: 8px 8px 8px 6px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #fff;
  display: flex;
  gap: 6px;
  transition: box-shadow 0.2s, border-color 0.2s;

  &.active {
    border-color: color-mix(in srgb, var(--accent-color) 40%, #cbd5e1);
    box-shadow: 0 4px 14px color-mix(in srgb, var(--accent-color) 12%, rgba(15, 23, 42, 0.05));
  }
  &.tone-ok .node-index { color: #059669; border-color: #a7f3d0; background: #ecfdf5; }
  &.tone-danger { border-color: #fecaca; .node-index { color: #dc2626; background: #fef2f2; } }
  &.tone-warn { border-color: #fde68a; .node-index { color: #d97706; background: #fffbeb; } }
  &.tone-muted { opacity: 0.85; background: #fafafa; }
}

.node-index {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 9px;
  font-weight: 800;
  color: #64748b;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #f8fafc;
}

.node-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.node-label {
  font-size: 11px;
  font-weight: 700;
  color: #1e293b;
  line-height: 1.25;
}

.node-sub {
  font-size: 9px;
  color: #64748b;
  line-height: 1.3;
}

.meta-chip {
  font-size: 8px;
  font-weight: 700;
  padding: 1px 4px;
  border-radius: 3px;
  background: #f1f5f9;
  color: #64748b;
  border: 1px solid #e2e8f0;
  margin-top: 4px;
  align-self: flex-start;
  &.status { color: #475569; }
}

.node-connector {
  display: flex;
  align-items: center;
  padding: 0 2px;
  flex-shrink: 0;
}

.card-footer {
  position: relative;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  font-size: 11px;
  color: #64748b;
  padding-top: 12px;
  border-top: 1px solid #f1f5f9;
}

.meta-item {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  &.mono { font-family: 'JetBrains Mono', Consolas, monospace; }
}

.card-actions {
  margin-left: auto;
  display: flex;
  gap: 8px;
}

.action-btn {
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #64748b;
  font-size: 11px;
  font-weight: 600;
  padding: 5px 10px;
  border-radius: 8px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  transition: color 0.15s, border-color 0.15s, background 0.15s;
  &:hover {
    color: #2563eb;
    border-color: #bfdbfe;
    background: #f8fafc;
  }
  &.primary {
    color: var(--accent-color);
    border-color: color-mix(in srgb, var(--accent-color) 35%, #e2e8f0);
    background: color-mix(in srgb, var(--accent-color) 8%, #fff);
  }
}

@media (max-width: 900px) {
  .node-row { flex-direction: column; align-items: stretch; padding: 8px; }
  .node-wrap { flex-direction: column; align-items: stretch; }
  .flow-node { width: 100%; min-height: 0; }
  .node-connector {
    justify-content: center;
    padding: 4px 0;
    svg { transform: rotate(90deg); }
  }
  .pipeline-track { display: none; }
}
</style>
