<template>
  <Teleport to="body">
    <Transition name="admin-modal">
      <div v-if="modelValue" class="admin-confirm-overlay" @click.self="handleCancel">
        <div
          class="admin-confirm-card glass-panel"
          :class="{ loading }"
          role="alertdialog"
          aria-modal="true"
          :aria-labelledby="dialogId"
        >
          <span class="corner corner--tl" aria-hidden="true"></span>
          <span class="corner corner--tr" aria-hidden="true"></span>
          <span class="corner corner--bl" aria-hidden="true"></span>
          <span class="corner corner--br" aria-hidden="true"></span>

          <header class="confirm-header">
            <div class="header-icon danger">
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path
                  d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
                  stroke="currentColor"
                  stroke-width="2"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                />
              </svg>
            </div>
            <div class="header-text">
              <span class="header-code">{{ code }}</span>
              <h3 :id="dialogId">{{ title }}</h3>
              <p class="header-sub">{{ subtitle }}</p>
            </div>
            <button type="button" class="header-close" :disabled="loading" @click="handleCancel">×</button>
          </header>

          <div class="confirm-status">
            <span class="status-tag">DELETE · IRREVERSIBLE</span>
            <span class="status-warn">操作不可恢复</span>
          </div>

          <div class="confirm-body">
            <p class="confirm-message">{{ message }}</p>

            <div v-if="itemTitle" class="confirm-preview">
              <div class="preview-head">
                <AdminModuleIcon v-if="moduleKey" :module-key="moduleKey" :color="moduleColor" />
                <span v-if="itemTag" class="preview-tag">{{ itemTag }}</span>
              </div>
              <p class="preview-title">{{ itemTitle }}</p>
              <p v-if="itemMeta" class="preview-meta">{{ itemMeta }}</p>
            </div>

            <p class="confirm-hint">
              <span class="hint-dot" aria-hidden="true"></span>
              删除后相关数据将从系统中永久移除，请谨慎确认。
            </p>
          </div>

          <footer class="confirm-footer">
            <button type="button" class="btn ghost" :disabled="loading" @click="handleCancel">
              {{ cancelText }}
            </button>
            <button type="button" class="btn danger" :disabled="loading" @click="emit('confirm')">
              <span v-if="loading" class="btn-spinner"></span>
              {{ loading ? loadingText : confirmText }}
            </button>
          </footer>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup lang="ts">
import AdminModuleIcon from './AdminModuleIcon.vue'
import type { AdminGearKey } from './gearPaths'

const MODULE_COLORS: Record<AdminGearKey, string> = {
  users: '#2563eb',
  tools: '#7c3aed',
  security: '#059669',
  knowledge: '#d97706',
}

const props = withDefaults(
  defineProps<{
    modelValue: boolean
    title?: string
    subtitle?: string
    message: string
    itemTitle?: string
    itemMeta?: string
    itemTag?: string
    moduleKey?: AdminGearKey
    code?: string
    loading?: boolean
    confirmText?: string
    cancelText?: string
    loadingText?: string
  }>(),
  {
    title: '确认删除',
    subtitle: 'DESTRUCTIVE ACTION · 不可逆操作',
    code: 'ACT-DEL',
    moduleKey: 'users',
    confirmText: '确认删除',
    cancelText: '取消',
    loadingText: '删除中…',
  },
)

const emit = defineEmits<{
  'update:modelValue': [boolean]
  confirm: []
  cancel: []
}>()

const dialogId = `admin-confirm-${Math.random().toString(36).slice(2, 8)}`

const moduleColor = MODULE_COLORS[props.moduleKey ?? 'users']

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

.admin-confirm-overlay {
  position: fixed;
  inset: 0;
  z-index: 3100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: rgba(15, 23, 42, 0.58);
  backdrop-filter: blur(10px);
}

.admin-confirm-card {
  position: relative;
  width: min(460px, 96vw);
  border-radius: 16px !important;
  border-color: rgba(239, 68, 68, 0.18) !important;
  box-shadow: 0 24px 80px rgba(127, 29, 29, 0.18), 0 0 0 1px rgba(255, 255, 255, 0.5) inset;
  overflow: hidden;
  animation: confirm-in 0.32s cubic-bezier(0.34, 1.35, 0.64, 1);

  &.loading {
    pointer-events: none;
    opacity: 0.96;
  }
}

@keyframes confirm-in {
  from { opacity: 0; transform: scale(0.94) translateY(12px); }
  to { opacity: 1; transform: none; }
}

.corner {
  position: absolute;
  width: 14px;
  height: 14px;
  border-color: rgba(239, 68, 68, 0.35);
  border-style: solid;
  pointer-events: none;
  z-index: 2;
}

.corner--tl { top: 8px; left: 8px; border-width: 2px 0 0 2px; }
.corner--tr { top: 8px; right: 8px; border-width: 2px 2px 0 0; }
.corner--bl { bottom: 8px; left: 8px; border-width: 0 0 2px 2px; }
.corner--br { bottom: 8px; right: 8px; border-width: 0 2px 2px 0; }

.confirm-header {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 18px 20px;
  background: linear-gradient(135deg, #991b1b, #dc2626 55%, #ef4444);
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

  svg {
    width: 22px;
    height: 22px;
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
    background: rgba(0, 0, 0, 0.2);
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
}

.confirm-status {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 20px;
  border-bottom: 1px solid #fee2e2;
  background: linear-gradient(180deg, #fef2f2, rgba(255, 255, 255, 0.95));
}

.status-tag {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: #dc2626;
}

.status-warn {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #b45309;
}

.confirm-body {
  padding: 18px 20px;
}

.confirm-message {
  margin: 0 0 14px;
  font-size: 14px;
  color: #475569;
  line-height: 1.65;
}

.confirm-preview {
  padding: 14px 16px;
  margin-bottom: 14px;
  border-radius: 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-left: 3px solid #ef4444;
}

.preview-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;

  :deep(.module-icon) {
    width: 22px;
    height: 22px;
  }
}

.preview-tag {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  padding: 2px 8px;
  border-radius: 4px;
  background: #eff6ff;
  color: #2563eb;
  border: 1px solid #bfdbfe;
}

.preview-title {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  color: #0f172a;
  line-height: 1.5;
  word-break: break-word;
}

.preview-meta {
  margin: 6px 0 0;
  font-size: 12px;
  color: #64748b;
}

.confirm-hint {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 0;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(254, 243, 199, 0.45);
  border: 1px solid rgba(251, 191, 36, 0.25);
  font-size: 12px;
  color: #92400e;
  line-height: 1.55;
}

.hint-dot {
  width: 6px;
  height: 6px;
  margin-top: 6px;
  border-radius: 50%;
  background: #f59e0b;
  flex-shrink: 0;
}

.confirm-footer {
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
  min-width: 96px;

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

  &.danger {
    background: linear-gradient(135deg, #ef4444, #dc2626);
    color: #fff;
    box-shadow: 0 4px 14px rgba(239, 68, 68, 0.35);

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
