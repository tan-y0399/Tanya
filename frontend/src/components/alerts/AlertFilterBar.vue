<template>
  <section class="filter-bar glass-panel" aria-label="告警筛选">
    <div class="filter-block">
      <span class="block-label">FILTER · 告警级别</span>
      <div class="btn-group">
        <button class="f-btn" :class="{ active: !severity }" @click="emit('update:severity', '')">全部级别</button>
        <button class="f-btn critical" :class="{ active: severity === 'critical' }" @click="emit('update:severity', 'critical')">
          <span class="dot"></span>紧急
        </button>
        <button class="f-btn warning" :class="{ active: severity === 'warning' }" @click="emit('update:severity', 'warning')">
          <span class="dot"></span>警告
        </button>
        <button class="f-btn info" :class="{ active: severity === 'info' }" @click="emit('update:severity', 'info')">
          <span class="dot"></span>提示
        </button>
      </div>
    </div>
    <div class="filter-block">
      <span class="block-label">STATUS · 处理状态</span>
      <div class="btn-group">
        <button class="f-btn" :class="{ active: !status }" @click="emit('update:status', '')">全部状态</button>
        <button class="f-btn" :class="{ active: status === 'active' }" @click="emit('update:status', 'active')">进行中</button>
        <button class="f-btn" :class="{ active: status === 'acknowledged' }" @click="emit('update:status', 'acknowledged')">已确认</button>
        <button class="f-btn" :class="{ active: status === 'resolved' }" @click="emit('update:status', 'resolved')">已解决</button>
      </div>
    </div>
    <div class="result-hint">
      <span class="hint-label">RESULT</span>
      共 <strong>{{ count }}</strong> 条告警
    </div>
  </section>
</template>

<script setup lang="ts">
defineProps<{
  severity: string
  status: string
  count: number
}>()

const emit = defineEmits<{
  'update:severity': [value: string]
  'update:status': [value: string]
}>()
</script>

<style lang="scss" scoped>
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-end;
  gap: 16px 24px;
  padding: 12px 16px;
  margin-bottom: 14px;
  border-color: rgba(148, 163, 184, 0.2) !important;
}

.filter-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.block-label {
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.07em;
  color: #94a3b8;
}

.btn-group {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.f-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: rgba(255, 255, 255, 0.8);
  font-size: 12px;
  font-weight: 500;
  color: #64748b;
  cursor: pointer;
  transition: all 0.15s;

  &:hover {
    border-color: #cbd5e1;
    color: #334155;
  }

  &.active {
    font-weight: 700;
    color: #0f172a;
    border-color: #64748b;
    background: #f8fafc;
    box-shadow: inset 0 0 0 1px rgba(15, 23, 42, 0.06);
  }

  &.critical.active { border-color: #ef4444; color: #dc2626; background: rgba(239, 68, 68, 0.06); }
  &.warning.active { border-color: #f59e0b; color: #b45309; background: rgba(245, 158, 11, 0.06); }
  &.info.active { border-color: #3b82f6; color: #2563eb; background: rgba(59, 130, 246, 0.06); }

  .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
  }

  &.critical .dot { background: #ef4444; }
  &.warning .dot { background: #f59e0b; }
  &.info .dot { background: #3b82f6; }
}

.result-hint {
  margin-left: auto;
  font-size: 12px;
  color: #64748b;

  strong {
    color: #0f172a;
    font-weight: 800;
  }
}

.hint-label {
  display: inline-block;
  margin-right: 8px;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.06em;
  color: #94a3b8;
}
</style>
