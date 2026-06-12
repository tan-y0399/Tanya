<template>
  <div class="provision-pipeline" :class="{ success: allOk }">
    <div class="pipeline-header">
      <span class="pipeline-label">DEPLOY PIPELINE</span>
      <span class="pipeline-count">{{ doneCount }}/{{ steps.length || '…' }}</span>
    </div>

    <div class="progress-track" v-if="steps.length">
      <div class="progress-fill" :style="{ width: progressPct + '%' }"></div>
    </div>

    <div class="pipeline-loading" v-if="loading && !steps.length">
      <span class="spinner"></span>
      <span>正在连接主机并配置 SSH 免密…</span>
    </div>

    <ul class="pipeline-steps" v-if="steps.length">
      <li
        v-for="(step, idx) in steps"
        :key="idx"
        :class="[step.status, { current: idx === currentIdx }]"
      >
        <span class="step-marker">
          <span v-if="step.status === 'ok'" class="marker-icon">✓</span>
          <span v-else-if="step.status === 'error'" class="marker-icon">✕</span>
          <span v-else-if="step.status === 'warn'" class="marker-icon">!</span>
          <span v-else-if="idx === currentIdx && loading" class="marker-spin"></span>
          <span v-else class="marker-dot"></span>
        </span>
        <span class="step-text">{{ step.message }}</span>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ProvisionStep } from '@/api/servers'

const props = defineProps<{
  steps: ProvisionStep[]
  loading?: boolean
}>()

const doneCount = computed(() =>
  props.steps.filter(s => s.status === 'ok' || s.status === 'error' || s.status === 'warn').length,
)

const progressPct = computed(() => {
  if (!props.steps.length) return 0
  return Math.round((doneCount.value / props.steps.length) * 100)
})

const currentIdx = computed(() => {
  const idx = props.steps.findIndex(s => s.status === 'info')
  return idx >= 0 ? idx : props.steps.length - 1
})

const allOk = computed(() =>
  props.steps.length > 0 && props.steps.every(s => s.status === 'ok'),
)
</script>

<style lang="scss" scoped>
.provision-pipeline {
  background: linear-gradient(180deg, rgba(250, 245, 255, 0.95), rgba(248, 250, 252, 0.95));
  border: 1px solid rgba(167, 139, 250, 0.35);
  border-radius: 12px;
  padding: 14px 16px;
  transition: border-color 0.4s;

  &.success {
    border-color: rgba(16, 185, 129, 0.45);
    background: linear-gradient(180deg, rgba(236, 253, 245, 0.95), rgba(248, 250, 252, 0.95));
  }
}

.pipeline-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.pipeline-label {
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #7c3aed;
}

.pipeline-count {
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 11px;
  font-weight: 700;
  color: #6366f1;
}

.progress-track {
  height: 4px;
  background: rgba(167, 139, 250, 0.2);
  border-radius: 2px;
  margin-bottom: 12px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #6366f1, #8b5cf6);
  border-radius: 2px;
  transition: width 0.35s ease;
}

.pipeline-loading {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
  color: #6d28d9;
}

.spinner, .marker-spin {
  width: 16px;
  height: 16px;
  border: 2px solid #c4b5fd;
  border-top-color: #7c3aed;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  flex-shrink: 0;
}

.marker-spin { width: 14px; height: 14px; }

.pipeline-steps {
  list-style: none;
  padding: 0;
  margin: 0;
}

.pipeline-steps li {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  font-size: 12px;
  padding: 7px 0;
  border-bottom: 1px dashed rgba(167, 139, 250, 0.25);
  color: #475569;
  &:last-child { border-bottom: none; }

  &.ok { color: #047857; }
  &.error { color: #dc2626; }
  &.warn { color: #b45309; }
  &.current {
    color: #4338ca;
    .step-text { font-weight: 600; }
  }
}

.step-marker {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.marker-icon {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 10px;
  font-weight: 700;
  .ok & { background: #d1fae5; color: #059669; }
  .error & { background: #fee2e2; color: #dc2626; }
  .warn & { background: #fef3c7; color: #b45309; }
}

.marker-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #c4b5fd;
}

.step-text { line-height: 1.45; flex: 1; }

@keyframes spin { to { transform: rotate(360deg); } }
</style>
