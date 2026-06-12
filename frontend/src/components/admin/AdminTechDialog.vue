<template>
  <Teleport to="body">
    <Transition name="admin-modal">
      <div v-if="modelValue" class="admin-dialog-overlay" @click.self="handleCancel">
        <div
          class="admin-dialog-card glass-panel"
          :class="{ loading }"
          :style="{ '--dialog-accent': accentColor, width }"
          role="dialog"
          :aria-labelledby="dialogId"
        >
          <span class="corner corner--tl" aria-hidden="true"></span>
          <span class="corner corner--tr" aria-hidden="true"></span>
          <span class="corner corner--bl" aria-hidden="true"></span>
          <span class="corner corner--br" aria-hidden="true"></span>

          <header class="dialog-header" :style="{ background: headerGradient }">
            <div class="header-icon">
              <AdminModuleIcon :module-key="moduleKey" color="#fff" :active="true" />
            </div>
            <div class="header-text">
              <span class="header-code">{{ code }}</span>
              <h3 :id="dialogId">{{ title }}</h3>
              <p v-if="subtitle" class="header-sub">{{ subtitle }}</p>
            </div>
            <button type="button" class="header-close" :disabled="loading" @click="handleCancel">×</button>
          </header>

          <div class="dialog-status">
            <span class="status-tag">FORM PANEL</span>
            <span class="status-ready">INPUT · 参数录入</span>
          </div>

          <div class="dialog-body">
            <slot />
          </div>

          <footer class="dialog-footer">
            <slot name="footer">
              <button type="button" class="btn ghost" :disabled="loading" @click="handleCancel">
                {{ cancelText }}
              </button>
              <button
                type="button"
                class="btn primary"
                :disabled="loading || confirmDisabled"
                @click="emit('confirm')"
              >
                <span v-if="loading" class="btn-spinner"></span>
                {{ loading ? loadingText : confirmText }}
              </button>
            </slot>
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import AdminModuleIcon from './AdminModuleIcon.vue'
import type { AdminGearKey } from './gearPaths'

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    title: string
    subtitle?: string
    code?: string
    moduleKey?: AdminGearKey
    accentColor?: string
    width?: string
    confirmText?: string
    cancelText?: string
    loadingText?: string
    loading?: boolean
    confirmDisabled?: boolean
  }>(),
  {
    code: 'DIALOG',
    moduleKey: 'users',
    accentColor: '#2563eb',
    width: 'min(480px, 96vw)',
    confirmText: '确认',
    cancelText: '取消',
    loadingText: '处理中…',
  },
)

const emit = defineEmits<{
  'update:modelValue': [boolean]
  confirm: []
  cancel: []
}>()

const dialogId = `admin-dialog-${Math.random().toString(36).slice(2, 8)}`

const headerGradient = computed(() => {
  const c = props.accentColor
  return `linear-gradient(135deg, color-mix(in srgb, ${c} 85%, #0f172a), color-mix(in srgb, ${c} 65%, #4338ca))`
})

function handleCancel() {
  if (props.loading) return
  emit('update:modelValue', false)
  emit('cancel')
}
</script>

<style lang="scss" scoped>
.admin-modal-enter-active,
.admin-modal-leave-active {
  transition: opacity 0.22s ease;
}

.admin-modal-enter-from,
.admin-modal-leave-to {
  opacity: 0;
}

.admin-dialog-overlay {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(15, 23, 42, 0.55);
  backdrop-filter: blur(8px);
}

.admin-dialog-card {
  position: relative;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  border-radius: 16px !important;
  border-color: rgba(37, 99, 235, 0.15) !important;
  box-shadow: 0 24px 80px rgba(15, 23, 42, 0.22);
  overflow: hidden;
  animation: dialog-in 0.32s cubic-bezier(0.34, 1.35, 0.64, 1);

  &.loading {
    pointer-events: none;
    opacity: 0.96;
  }
}

@keyframes dialog-in {
  from { opacity: 0; transform: scale(0.94) translateY(12px); }
  to { opacity: 1; transform: none; }
}

.corner {
  position: absolute;
  width: 14px;
  height: 14px;
  border-color: rgba(37, 99, 235, 0.35);
  border-style: solid;
  pointer-events: none;
  z-index: 2;
}

.corner--tl { top: 8px; left: 8px; border-width: 2px 0 0 2px; }
.corner--tr { top: 8px; right: 8px; border-width: 2px 2px 0 0; }
.corner--bl { bottom: 8px; left: 8px; border-width: 0 0 2px 2px; }
.corner--br { bottom: 8px; right: 8px; border-width: 0 2px 2px 0; }

.dialog-header {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 20px;
  color: #fff;
}

.header-icon {
  width: 44px;
  height: 44px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.14);
  border: 1px solid rgba(255, 255, 255, 0.22);

  :deep(.module-icon) {
    width: 24px;
    height: 24px;
    color: #fff !important;
    filter: none;
  }
}

.header-code {
  display: inline-block;
  margin-bottom: 4px;
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.14);
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.1em;
}

.header-text {
  flex: 1;
  min-width: 0;

  h3 {
    margin: 0;
    font-size: 17px;
    font-weight: 800;
    letter-spacing: -0.02em;
  }
}

.header-sub {
  margin: 4px 0 0;
  font-size: 10px;
  letter-spacing: 0.06em;
  opacity: 0.88;
}

.header-close {
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
  transition: background 0.15s;

  &:hover:not(:disabled) {
    background: rgba(239, 68, 68, 0.45);
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.dialog-status {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 20px;
  border-bottom: 1px solid #f1f5f9;
  background: rgba(248, 250, 252, 0.9);
}

.status-tag {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.1em;
  color: var(--dialog-accent, #2563eb);
}

.status-ready {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: #10b981;
}

.dialog-body {
  padding: 18px 20px;
  overflow-y: auto;
  flex: 1;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 20px;
  border-top: 1px solid #f1f5f9;
  background: rgba(248, 250, 252, 0.95);
}

.btn {
  padding: 9px 18px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  border: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  &.ghost {
    background: #fff;
    border: 1px solid #e2e8f0 !important;
    color: #475569;

    &:hover:not(:disabled) {
      border-color: #cbd5e1;
      background: #f8fafc;
    }
  }

  &.primary {
    background: linear-gradient(135deg, var(--dialog-accent, #2563eb), color-mix(in srgb, var(--dialog-accent, #2563eb) 70%, #6366f1));
    color: #fff;
    box-shadow: 0 4px 14px color-mix(in srgb, var(--dialog-accent, #2563eb) 30%, transparent);

    &:hover:not(:disabled) {
      filter: brightness(1.05);
    }
  }
}

.btn-spinner {
  width: 14px;
  height: 14px;
  margin-right: 6px;
  border: 2px solid rgba(255, 255, 255, 0.35);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
