<template>
  <div class="plan-progress-card" v-if="progress">
    <div class="progress-head">
      <span class="progress-icon" aria-hidden="true">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
        </svg>
      </span>
      <div class="progress-titles">
        <span class="progress-title">方案执行进度</span>
        <span class="progress-sub">{{ progress.phenomenon || '运维诊断方案' }}</span>
      </div>
      <span class="progress-badge" :class="statusClass">{{ statusLabel }}</span>
    </div>

    <div class="progress-bar-wrap">
      <div class="progress-bar">
        <div class="progress-fill" :style="{ width: percent + '%' }" />
      </div>
      <span class="progress-count">{{ progress.completedSteps }}/{{ progress.totalSteps }}</span>
    </div>

    <p v-if="progress.brief" class="progress-brief">{{ progress.brief }}</p>

    <div v-if="stuck" class="progress-actions">
      <button
        type="button"
        class="continue-btn"
        :disabled="continuing"
        @click="$emit('continue')"
      >
        {{ continuing ? '正在续跑…' : '继续执行方案' }}
      </button>
      <span class="continue-hint">方案暂停于中间步骤，点击后将自动推进下一步</span>
    </div>

    <ol v-if="progress.steps?.length" class="step-status-list">
      <li
        v-for="s in progress.steps"
        :key="s.order"
        class="step-status-item"
        :class="[stepClass(s.status), s.core ? 'core-step' : '']"
      >
        <span class="step-dot" />
        <span class="step-order">{{ s.order }}</span>
        <span class="step-action">{{ s.action }}</span>
        <span class="step-state">{{ stepLabel(s.status) }}</span>
      </li>
    </ol>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

export interface PlanProgressPayload {
  phenomenon?: string
  totalSteps?: number
  completedSteps?: number
  currentStepOrder?: number | null
  currentStepAction?: string | null
  currentStatus?: string
  brief?: string
  steps?: { order: number; action: string; status: string }[]
}

const props = defineProps<{
  progress: PlanProgressPayload | null
  stuck?: boolean
  continuing?: boolean
}>()

defineEmits<{ continue: [] }>()

const percent = computed(() => {
  const t = props.progress?.totalSteps || 0
  const d = props.progress?.completedSteps || 0
  if (!t) return 0
  return Math.min(100, Math.round((d / t) * 100))
})

const statusLabel = computed(() => {
  const s = props.progress?.currentStatus || ''
  const total = props.progress?.totalSteps || 0
  const done = props.progress?.completedSteps || 0
  const hasFailed = props.progress?.steps?.some(st => st.status === 'failed')
  if (s === 'completed' || (total > 0 && done >= total)) {
    return hasFailed ? '已结束' : '已完成'
  }
  if (s === 'pending_confirm') return '待确认'
  if (s === 'pending_approval') return '待审批'
  return '执行中'
})

const statusClass = computed(() => {
  const s = props.progress?.currentStatus || ''
  if (s === 'completed') return 'is-done'
  if (s === 'pending_confirm' || s === 'pending_approval') return 'is-wait'
  return 'is-run'
})

function stepLabel(status: string) {
  const m: Record<string, string> = {
    completed: '已完成',
    failed: '未成功',
    blocked: '已阻止',
    rejected: '已跳过',
    skipped: '已跳过',
    pending_confirm: '待确认',
    pending_approval: '待审批',
    executing: '执行中',
    pending: '待执行',
  }
  return m[status] || '待执行'
}

function stepClass(status: string) {
  if (status === 'completed') return 'done'
  if (['failed', 'blocked'].includes(status)) return 'err'
  if (['pending_confirm', 'pending_approval'].includes(status)) return 'wait'
  return ''
}
</script>

<style scoped lang="scss">
.plan-progress-card {
  margin: 0 0 12px;
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid #c7d2fe;
  background: linear-gradient(160deg, #eef2ff 0%, #ffffff 60%);
  box-shadow: 0 2px 10px rgba(99, 102, 241, 0.08);
}

.progress-head {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 12px;
}
.progress-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: #6366f1;
  color: #fff;
  flex-shrink: 0;
}
.progress-titles { flex: 1; min-width: 0; }
.progress-title {
  display: block;
  font-size: 14px;
  font-weight: 700;
  color: #312e81;
}
.progress-sub {
  display: block;
  font-size: 12px;
  color: #64748b;
  margin-top: 2px;
}
.progress-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 20px;
  flex-shrink: 0;
  &.is-done { background: #dcfce7; color: #166534; }
  &.is-wait { background: #fef9c3; color: #854d0e; }
  &.is-run { background: #dbeafe; color: #1d4ed8; }
}

.progress-bar-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.progress-bar {
  flex: 1;
  height: 6px;
  border-radius: 3px;
  background: #e2e8f0;
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  border-radius: 3px;
  background: linear-gradient(90deg, #6366f1, #818cf8);
  transition: width 0.3s ease;
}
.progress-count {
  font-size: 12px;
  font-weight: 600;
  color: #4338ca;
  min-width: 36px;
  text-align: right;
}

.progress-brief {
  margin: 0 0 10px;
  font-size: 13px;
  line-height: 1.55;
  color: #334155;
}

.progress-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
  margin: 0 0 12px;
}
.continue-btn {
  border: none;
  border-radius: 8px;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, #6366f1, #4f46e5);
  cursor: pointer;
  &:disabled {
    opacity: 0.65;
    cursor: not-allowed;
  }
}
.continue-hint {
  font-size: 12px;
  color: #64748b;
}

.step-status-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.step-status-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.7);
  &.done .step-dot { background: #22c55e; }
  &.err .step-dot { background: #ef4444; }
  &.wait .step-dot { background: #f59e0b; }
  &.core-step {
    background: #fffbeb;
    border: 1px solid #fde68a;
  }
}
.step-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #cbd5e1;
  flex-shrink: 0;
}
.step-order {
  font-weight: 700;
  color: #6366f1;
  min-width: 16px;
}
.step-action {
  flex: 1;
  color: #475569;
}
.step-state {
  font-size: 11px;
  color: #64748b;
}
</style>
