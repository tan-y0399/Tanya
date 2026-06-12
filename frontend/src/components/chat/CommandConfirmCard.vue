<template>
  <div class="cmd-confirm-card" :class="'mode-' + mode">
    <div class="card-head">
      <span class="term-icon">$_</span>
      <span class="card-title">{{ title }}</span>
      <span class="risk-tag" :class="'risk-' + riskLevel">{{ riskLevel }}</span>
    </div>
    <div class="card-body">
      <div class="tool-line">
        <span class="label">工具</span>
        <code>{{ toolName }}</code>
      </div>
      <pre v-if="displayCommand" class="cmd-preview">{{ displayCommand }}</pre>
      <p v-if="message" class="hint">{{ message }}</p>
    </div>
    <div class="card-foot">
      <span class="foot-hint">{{ footHint }}</span>
      <div class="foot-btns">
        <button type="button" class="btn-skip" @click="$emit('skip')">跳过</button>
        <button type="button" class="btn-cancel" @click="$emit('cancel')">取消</button>
        <button type="button" class="btn-run" @click="$emit('run')">执行</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  toolName: string
  params: Record<string, any>
  riskLevel?: string
  message?: string
  /** l2: L2 确认；post-approval: 管理员已批准后的执行确认 */
  mode?: 'l2' | 'post-approval'
  commandPreview?: string
}>()

defineEmits<{ skip: []; cancel: []; run: [] }>()

const mode = computed(() => props.mode || 'l2')

const title = computed(() => {
  if (mode.value === 'post-approval') {
    return '管理员已批准 · 待执行命令'
  }
  if (props.toolName === 'execute_command' || props.toolName === 'run_command') {
    return '待执行的系统命令'
  }
  return `待执行操作 · ${props.toolName}`
})

const footHint = computed(() => {
  if (mode.value === 'post-approval') {
    return `${props.riskLevel || 'L4'} 高危操作 · 管理员已批准，需您确认后才会在虚拟机执行`
  }
  return 'L2 低风险操作 · 需您确认后才会在虚拟机执行'
})

const displayCommand = computed(() => {
  if (props.commandPreview) return props.commandPreview
  const p = props.params || {}
  if (p.command) return p.command
  if (props.toolName === 'manage_service') {
    return `systemctl ${p.action || '?'} ${p.service_name || p.service || '?'}`
  }
  if (props.toolName === 'kill_process') {
    return `kill -${p.signal || 'TERM'} ${p.pid}`
  }
  return JSON.stringify(p, null, 2)
})
</script>

<style scoped lang="scss">
.cmd-confirm-card {
  margin: 0;
  border-radius: 12px;
  border: 1px solid #fde68a;
  background: #fffbeb;
  box-shadow: 0 4px 16px rgba(245, 158, 11, 0.12);
  overflow: hidden;

  &.mode-post-approval {
    border-color: #93c5fd;
    background: #eff6ff;
    box-shadow: 0 4px 16px rgba(37, 99, 235, 0.12);
    .card-head {
      background: linear-gradient(135deg, #dbeafe 0%, #eff6ff 100%);
      border-bottom-color: #93c5fd;
    }
    .term-icon { color: #1d4ed8; }
    .card-title { color: #1e40af; }
    .card-foot { border-top-color: #93c5fd; }
    .risk-tag.risk-L4, .risk-tag.risk-L5 {
      background: #fee2e2;
      color: #b91c1c;
      border: 1px solid #fca5a5;
    }
  }
}
.card-head {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: linear-gradient(135deg, #fef3c7 0%, #fff7ed 100%);
  border-bottom: 1px solid #fde68a;
}
.term-icon {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  color: #b45309;
  font-size: 14px;
}
.card-title {
  flex: 1;
  font-size: 14px;
  font-weight: 600;
  color: #92400e;
}
.risk-tag {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 6px;
  &.risk-L2 { background: #fef9c3; color: #a16207; border: 1px solid #fde047; }
  &.risk-L3 { background: #ffedd5; color: #c2410c; border: 1px solid #fdba74; }
  &.risk-L4 { background: #fee2e2; color: #b91c1c; border: 1px solid #fca5a5; }
  &.risk-L5 { background: #fecaca; color: #991b1b; border: 1px solid #f87171; }
}
.card-body { padding: 14px 16px; }
.tool-line {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  .label { font-size: 12px; color: #78716c; }
  code { font-size: 12px; color: #2563eb; background: #f8fafc; padding: 2px 8px; border-radius: 4px; }
}
.cmd-preview {
  margin: 0;
  padding: 12px 14px;
  background: #1e293b;
  color: #e2e8f0;
  border-radius: 8px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 160px;
  overflow: auto;
}
.hint { margin: 10px 0 0; font-size: 13px; color: #57534e; line-height: 1.5; }
.mode-post-approval .hint { color: #334155; }
.card-foot {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 12px 16px;
  border-top: 1px solid #fde68a;
  background: #fff;
}
.foot-hint { font-size: 11px; color: #a8a29e; }
.foot-btns { display: flex; gap: 8px; margin-left: auto; }
.btn-skip, .btn-cancel, .btn-run {
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: all 0.15s;
}
.btn-skip {
  background: transparent;
  color: #78716c;
  &:hover { background: #f5f5f4; }
}
.btn-cancel {
  background: #f1f5f9;
  color: #475569;
  &:hover { background: #e2e8f0; }
}
.btn-run {
  background: #2563eb;
  color: #fff;
  &:hover { background: #1d4ed8; }
}
</style>
