<template>
  <article class="approval-flow-card" :style="cardStyle" @click="$emit('open', item)">
    <div class="card-glow" aria-hidden="true"></div>

    <header class="card-header">
      <div class="type-badge">
        <span class="type-code">{{ mode === 'pending' ? 'PENDING' : 'HISTORY' }}</span>
        <div class="type-text">
          <strong>{{ item.eventSummary || item.detail || item.toolName }}</strong>
          <span>{{ item.sourceType || 'Agent 对话' }} · <code>{{ item.toolName }}</code></span>
        </div>
      </div>
      <div class="header-right">
        <span class="flow-status" :class="resultClass">{{ resultText }}</span>
        <span class="risk-tag" :class="riskClass(item.riskLevel)">{{ item.riskLevel }}</span>
        <time class="card-time">{{ formatTime(item.resolvedAt || item.requestedAt) }}</time>
      </div>
    </header>

    <p v-if="item.commandPreview" class="card-cmd">{{ item.commandPreview }}</p>

    <div class="card-pipeline">
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
            :class="[`tone-${nodeStatusTone(node.status)}`, { active: node.status === 'passed' || node.status === 'pending' }]"
            :title="node.detail"
          >
            <span class="node-index">{{ String(idx + 1).padStart(2, '0') }}</span>
            <div class="node-body">
              <span class="node-label">{{ node.label }}</span>
              <span class="node-sub">{{ node.sublabel }}</span>
              <span v-if="node.detail" class="node-detail">{{ node.detail }}</span>
              <span class="meta-chip">{{ nodeStatusLabel(node.status) }}</span>
            </div>
          </div>
          <div v-if="idx < flowNodes.length - 1" class="node-connector" aria-hidden="true">
            <svg width="28" height="14" viewBox="0 0 28 14">
              <path
                d="M0 7 H16 L12 3 M16 7 L12 11"
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
      <span class="meta-item">{{ formatUser(item) }}</span>
      <span v-if="item.remainingSeconds != null && mode === 'pending'" class="meta-item countdown">
        {{ item.remainingSeconds }}s 后超时
      </span>
      <div class="card-actions" @click.stop>
        <template v-if="mode === 'pending' && isAdmin">
          <button class="action-btn approve" :disabled="approving" @click="$emit('approve', item.id)">
            <span v-if="approving" class="btn-spinner"></span>
            {{ approving ? '处理中…' : '通过' }}
          </button>
          <button class="action-btn reject" :disabled="approving" @click="$emit('reject', item.id)">拒绝</button>
        </template>
        <button class="action-btn" @click="$emit('detail', item)">详情</button>
        <button v-if="item.sessionId" class="action-btn primary" @click="$emit('goto-chat', item)">对话</button>
        <el-dropdown v-if="mode === 'history' && isAdmin" trigger="click" @command="(cmd: string) => $emit('action', cmd, item)">
          <button type="button" class="action-btn more">
            <el-icon><MoreFilled /></el-icon>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="edit">修改</el-dropdown-item>
              <el-dropdown-item command="delete" divided>
                <span class="danger-text">删除</span>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </footer>
  </article>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { MoreFilled } from '@element-plus/icons-vue'
import {
  approvalResultClass,
  approvalResultLabel,
  buildApprovalFlowNodes,
  nodeStatusLabel,
  nodeStatusTone,
  riskAccentColor,
  riskClass,
} from './approvalMeta'
import { formatTime } from '@/utils'

const props = defineProps<{
  item: any
  mode: 'pending' | 'history'
  isAdmin?: boolean
  approving?: boolean
}>()

defineEmits<{
  open: [item: any]
  detail: [item: any]
  approve: [id: string]
  reject: [id: string]
  'goto-chat': [item: any]
  action: [cmd: string, item: any]
}>()

const uid = Math.random().toString(36).slice(2, 8)

const accentColor = computed(() => riskAccentColor(props.item.riskLevel))
const cardStyle = computed(() => ({ '--accent-color': accentColor.value }))

const status = computed(() => (props.mode === 'pending' ? 'pending' : props.item.status))
const flowNodes = computed(() =>
  buildApprovalFlowNodes(status.value, props.item.remainingSeconds),
)

const resultText = computed(() =>
  props.mode === 'pending' ? '待审批' : approvalResultLabel(props.item.status),
)
const resultClass = computed(() =>
  props.mode === 'pending' ? 'pending' : approvalResultClass(props.item.status),
)

function formatUser(row: any) {
  const name = row.requestedBy || row.requestedByUsername
  if (name && row.requestedByRole) return `${name}（${row.requestedByRole}）`
  return name || '—'
}
</script>

<style scoped lang="scss">
.approval-flow-card {
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

.type-badge { display: flex; align-items: flex-start; gap: 10px; min-width: 0; }

.type-code {
  flex-shrink: 0;
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.06em;
  color: var(--accent-color);
  padding: 5px 7px;
  border-radius: 6px;
  border: 1px solid color-mix(in srgb, var(--accent-color) 30%, #e2e8f0);
  background: color-mix(in srgb, var(--accent-color) 8%, #fff);
}

.type-text {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
  strong {
    font-size: 14px;
    font-weight: 700;
    color: #1e293b;
    line-height: 1.35;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  span {
    font-size: 11px;
    color: #64748b;
    code {
      font-family: 'JetBrains Mono', Consolas, monospace;
      font-size: 10px;
      color: #2563eb;
      background: #f1f5f9;
      padding: 1px 5px;
      border-radius: 4px;
    }
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
  padding: 3px 8px;
  border-radius: 999px;
  &.ok { background: #ecfdf5; color: #059669; border: 1px solid #a7f3d0; }
  &.fail { background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; }
  &.warn { background: #fffbeb; color: #d97706; border: 1px solid #fde68a; }
  &.pending { background: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe; }
}

.risk-tag {
  font-size: 10px;
  font-weight: 800;
  padding: 2px 6px;
  border-radius: 4px;
  &.l3 { color: #d97706; background: #fffbeb; }
  &.l4, &.l5 { color: #dc2626; background: #fef2f2; }
}

.card-time { font-size: 11px; color: #64748b; }

.card-cmd {
  position: relative;
  margin: 0 0 14px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  font-size: 12px;
  font-family: 'JetBrains Mono', Consolas, monospace;
  color: #475569;
  line-height: 1.5;
  word-break: break-all;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
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
  display: flex;
  align-items: stretch;
  min-width: min-content;
  padding: 4px 8px;
}

.node-wrap { display: flex; align-items: center; flex-shrink: 0; }

.flow-node {
  width: 140px;
  min-height: 84px;
  padding: 8px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #fff;
  display: flex;
  gap: 6px;
  &.active {
    border-color: color-mix(in srgb, var(--accent-color) 40%, #cbd5e1);
    box-shadow: 0 4px 14px color-mix(in srgb, var(--accent-color) 12%, rgba(15, 23, 42, 0.05));
  }
  &.tone-ok .node-index { color: #059669; background: #ecfdf5; border-color: #a7f3d0; }
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
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #f8fafc;
  color: #64748b;
}

.node-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.node-label { font-size: 11px; font-weight: 700; color: #1e293b; }
.node-sub { font-size: 9px; color: #64748b; }
.node-detail { font-size: 8px; color: #d97706; font-weight: 600; margin-top: 2px; }

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
}

.node-connector { padding: 0 2px; flex-shrink: 0; }

.card-footer {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px;
  font-size: 11px;
  color: #64748b;
  padding-top: 12px;
  border-top: 1px solid #f1f5f9;
}

.meta-item.countdown {
  color: #d97706;
  font-weight: 600;
  animation: pulse 1.5s ease infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.65; }
}

.card-actions {
  margin-left: auto;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
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
  &:hover:not(:disabled) {
    color: #2563eb;
    border-color: #bfdbfe;
    background: #f8fafc;
  }
  &.primary {
    color: var(--accent-color);
    border-color: color-mix(in srgb, var(--accent-color) 35%, #e2e8f0);
    background: color-mix(in srgb, var(--accent-color) 8%, #fff);
  }
  &.approve {
    color: #059669;
    border-color: #a7f3d0;
    &:hover:not(:disabled) { background: #ecfdf5; }
  }
  &.reject {
    color: #dc2626;
    border-color: #fecaca;
    &:hover:not(:disabled) { background: #fef2f2; }
  }
  &.more { padding: 5px 8px; }
  &:disabled { opacity: 0.6; cursor: not-allowed; }
}

.btn-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid #a7f3d0;
  border-top-color: #059669;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.danger-text { color: #dc2626; }

@media (max-width: 900px) {
  .node-row { flex-direction: column; align-items: stretch; }
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
