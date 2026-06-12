<template>
  <Transition name="tech-confirm-fade">
    <div v-if="visible" class="tech-confirm-overlay" @click.self="emit('cancel')">
      <div class="tech-confirm-card" :class="type">
        <div class="tech-confirm-accent"></div>
        <div class="tech-confirm-header">
          <span class="tech-confirm-badge">{{ typeLabel }}</span>
          <h4 class="tech-confirm-title">{{ title }}</h4>
          <button type="button" class="tech-confirm-close" @click="emit('cancel')">×</button>
        </div>
        <p class="tech-confirm-message">{{ message }}</p>
        <div class="tech-confirm-actions">
          <button type="button" class="tech-btn" @click="emit('cancel')">{{ cancelText }}</button>
          <button
            type="button"
            class="tech-btn"
            :class="confirmClass"
            @click="emit('confirm')"
          >{{ confirmText }}</button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(defineProps<{
  visible: boolean
  title: string
  message: string
  type?: 'info' | 'warning' | 'danger'
  confirmText?: string
  cancelText?: string
}>(), {
  type: 'info',
  confirmText: '确定',
  cancelText: '取消',
})

const emit = defineEmits<{ confirm: []; cancel: [] }>()

const typeLabel = computed(() => ({
  info: 'CONFIRM',
  warning: 'WARNING',
  danger: 'DELETE',
}[props.type]))

const confirmClass = computed(() => {
  if (props.type === 'danger') return 'danger primary'
  return 'primary'
})
</script>

<style lang="scss" scoped>
.tech-confirm-overlay {
  position: fixed;
  inset: 0;
  z-index: 300;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(15, 23, 42, 0.55);
  backdrop-filter: blur(8px);
}

.tech-confirm-card {
  position: relative;
  width: min(420px, 92vw);
  padding: 22px 24px 20px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid rgba(186, 230, 253, 0.8);
  box-shadow: 0 24px 64px rgba(15, 23, 42, 0.22), 0 0 0 1px rgba(255, 255, 255, 0.6) inset;
  overflow: hidden;
  animation: confirm-in 0.28s cubic-bezier(0.34, 1.4, 0.64, 1);

  &.info .tech-confirm-accent { background: linear-gradient(90deg, #2563eb, #6366f1); }
  &.warning .tech-confirm-accent { background: linear-gradient(90deg, #f59e0b, #f97316); }
  &.danger .tech-confirm-accent { background: linear-gradient(90deg, #ef4444, #dc2626); }
}

.tech-confirm-accent {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 3px;
}

.tech-confirm-header {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 14px;
}

.tech-confirm-badge {
  flex-shrink: 0;
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  padding: 3px 8px;
  border-radius: 4px;
  background: #eff6ff;
  color: #2563eb;
  border: 1px solid #bfdbfe;
  margin-top: 2px;

  .warning & { background: #fffbeb; color: #b45309; border-color: #fde68a; }
  .danger & { background: #fef2f2; color: #dc2626; border-color: #fecaca; }
}

.tech-confirm-title {
  flex: 1;
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.4;
}

.tech-confirm-close {
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 6px;
  background: #f1f5f9;
  color: #64748b;
  font-size: 18px;
  cursor: pointer;
  transition: all 0.15s;
  &:hover { background: #fee2e2; color: #ef4444; }
}

.tech-confirm-message {
  margin: 0 0 20px;
  font-size: 14px;
  color: #64748b;
  line-height: 1.65;
  white-space: pre-wrap;
}

.tech-confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;

  .tech-btn.primary {
    background: linear-gradient(135deg, #2563eb, #6366f1);
    border: none;
    color: #fff;
    box-shadow: 0 4px 14px rgba(37, 99, 235, 0.3);
    &:hover { background: linear-gradient(135deg, #3b82f6, #818cf8); }
  }

  .tech-btn.danger.primary {
    background: linear-gradient(135deg, #ef4444, #dc2626);
    box-shadow: 0 4px 14px rgba(239, 68, 68, 0.3);
    &:hover { background: linear-gradient(135deg, #f87171, #ef4444); }
  }
}

.tech-confirm-fade-enter-active,
.tech-confirm-fade-leave-active { transition: opacity 0.22s; }
.tech-confirm-fade-enter-from,
.tech-confirm-fade-leave-to { opacity: 0; }

@keyframes confirm-in {
  from { opacity: 0; transform: scale(0.94) translateY(8px); }
  to { opacity: 1; transform: none; }
}
</style>
