<template>
  <span
    v-if="rolledBack"
    class="rb-done"
    :class="[`rb-done--${size}`]"
    :title="hint || '该步骤已撤销'"
  >
    <span class="rb-icon-box" aria-hidden="true">
      <svg class="rb-icon" width="16" height="16" viewBox="0 0 20 20" fill="none">
        <path
          d="M5.5 10.5 9 14l3.5-3.5"
          stroke="currentColor"
          stroke-width="1.8"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
    </span>
    <span class="rb-label">已回滚</span>
  </span>
  <button
    v-else
    type="button"
    class="rb-btn"
    :class="[
      `rb-btn--${variant}`,
      `rb-btn--${size}`,
      { 'rb-btn--fx': clickFx },
    ]"
    :disabled="busy"
    :aria-label="ariaLabel"
    :title="hint || defaultHint"
    @mousedown="triggerClickFx"
    @click.stop="$emit('click')"
  >
    <span v-if="busy" class="rb-spinner" aria-hidden="true" />
    <span v-else class="rb-icon-box" aria-hidden="true">
      <svg class="rb-icon" width="16" height="16" viewBox="0 0 20 20" fill="none">
        <path
          d="M7.5 6.5 4.5 9.5 7.5 12.5"
          stroke="currentColor"
          stroke-width="1.75"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
        <path
          d="M4.5 9.5h6a4.5 4.5 0 1 1 0 9"
          stroke="currentColor"
          stroke-width="1.75"
          stroke-linecap="round"
        />
      </svg>
    </span>
    <span class="rb-label">{{ busy ? busyText : label }}</span>
    <span class="rb-ripple" aria-hidden="true" />
  </button>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

const props = withDefaults(defineProps<{
  variant?: 'single' | 'full'
  size?: 'sm' | 'md'
  busy?: boolean
  rolledBack?: boolean
  hint?: string
}>(), {
  variant: 'single',
  size: 'sm',
  busy: false,
  rolledBack: false,
  hint: '',
})

defineEmits<{ click: [] }>()

const clickFx = ref(false)
let fxTimer: ReturnType<typeof setTimeout> | null = null

const label = computed(() => (props.variant === 'full' ? '全量回滚' : '单步回滚'))
const busyText = computed(() => (props.variant === 'full' ? '回滚中…' : '撤销中…'))
const defaultHint = computed(() =>
  props.variant === 'full'
    ? '按逻辑快照逆向回滚本会话所有可撤销的写操作'
    : '撤销该命令对系统的变更',
)
const ariaLabel = computed(() =>
  props.busy ? `${label.value}进行中` : label.value,
)

function triggerClickFx() {
  if (props.busy) return
  clickFx.value = false
  if (fxTimer) clearTimeout(fxTimer)
  requestAnimationFrame(() => {
    clickFx.value = true
    fxTimer = setTimeout(() => {
      clickFx.value = false
    }, 480)
  })
}
</script>

<style lang="scss" scoped>
.rb-btn,
.rb-done {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  flex-shrink: 0;
  white-space: nowrap;
  vertical-align: middle;
  font-family: inherit;
}

.rb-icon-box {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  flex: 0 0 16px;
}

.rb-icon {
  display: block;
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.rb-label {
  line-height: 1;
  transform: translateY(0.5px);
}

.rb-btn {
  min-height: 28px;
  padding: 0 11px;
  font-weight: 600;
  font-size: 11px;
  border-radius: 8px;
  cursor: pointer;
  border: 1px solid #fbbf24;
  background: linear-gradient(180deg, #fffbeb 0%, #fef3c7 100%);
  color: #b45309;
  box-shadow: 0 1px 2px rgba(245, 158, 11, 0.08);
  transition:
    background 0.18s ease,
    border-color 0.18s ease,
    color 0.18s ease,
    box-shadow 0.18s ease,
    transform 0.12s ease;

  &--md {
    min-height: 32px;
    padding: 0 13px;
    font-size: 12px;
    gap: 7px;

    .rb-icon-box,
    .rb-icon {
      width: 17px;
      height: 17px;
      flex-basis: 17px;
    }
  }

  &--full {
    border-color: #f59e0b;
    background: linear-gradient(180deg, #fffbeb 0%, #fde68a 100%);
  }

  &:hover:not(:disabled) {
    border-color: #f59e0b;
    background: linear-gradient(180deg, #fef3c7 0%, #fde68a 100%);
    color: #92400e;
    box-shadow: 0 2px 8px rgba(245, 158, 11, 0.22);

    .rb-icon {
      transform: rotate(-12deg);
      transition: transform 0.2s ease;
    }
  }

  &:active:not(:disabled) {
    transform: scale(0.96);
    box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.28);
  }

  &--fx:not(:disabled) {
    animation: rb-click-pulse 0.48s ease;

    .rb-icon-box {
      animation: rb-icon-spin 0.48s ease;
    }

    .rb-ripple {
      animation: rb-ripple 0.48s ease-out;
    }
  }

  &:focus-visible {
    outline: 2px solid #f59e0b;
    outline-offset: 2px;
  }

  &:disabled {
    opacity: 0.55;
    cursor: not-allowed;
    box-shadow: none;
  }
}

.rb-ripple {
  position: absolute;
  inset: 0;
  border-radius: inherit;
  pointer-events: none;
  opacity: 0;
}

.rb-done {
  min-height: 28px;
  padding: 0 11px;
  font-weight: 600;
  font-size: 11px;
  border-radius: 8px;
  border: 1px solid #bbf7d0;
  background: #f0fdf4;
  color: #15803d;

  &--md {
    min-height: 32px;
    padding: 0 13px;
    font-size: 12px;
  }
}

.rb-spinner {
  width: 16px;
  height: 16px;
  flex: 0 0 16px;
  border: 2px solid #fde68a;
  border-top-color: #d97706;
  border-radius: 50%;
  animation: rb-spin 0.65s linear infinite;
}

@keyframes rb-spin {
  to { transform: rotate(360deg); }
}

@keyframes rb-icon-spin {
  0% { transform: rotate(0deg); }
  45% { transform: rotate(-200deg); }
  100% { transform: rotate(-360deg); }
}

@keyframes rb-click-pulse {
  0% { box-shadow: 0 0 0 0 rgba(245, 158, 11, 0.45); }
  70% { box-shadow: 0 0 0 8px rgba(245, 158, 11, 0); }
  100% { box-shadow: 0 1px 2px rgba(245, 158, 11, 0.08); }
}

@keyframes rb-ripple {
  0% {
    opacity: 0.45;
    background: radial-gradient(circle at 28% 50%, rgba(251, 191, 36, 0.55) 0%, transparent 62%);
  }
  100% {
    opacity: 0;
    background: radial-gradient(circle at 28% 50%, rgba(251, 191, 36, 0) 0%, transparent 72%);
  }
}
</style>
