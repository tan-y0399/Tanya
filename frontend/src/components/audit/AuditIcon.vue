<template>
  <span class="audit-icon" :class="[tone, sizeClass, { boxed }]" :style="boxStyle" aria-hidden="true">
    <svg :width="svgSize" :height="svgSize" viewBox="0 0 24 24" fill="none">
      <!-- 总审计 / 统计 -->
      <template v-if="name === 'stats-total'">
        <rect x="4" y="14" width="3" height="6" rx="1" :fill="fillSoft" :stroke="stroke" stroke-width="1.5" />
        <rect x="10.5" y="9" width="3" height="11" rx="1" :fill="fillSoft" :stroke="stroke" stroke-width="1.5" />
        <rect x="17" y="5" width="3" height="15" rx="1" :fill="fillSoft" :stroke="stroke" stroke-width="1.5" />
        <path d="M3 20h18" :stroke="stroke" stroke-width="1.5" stroke-linecap="round" />
      </template>

      <!-- 今日操作 -->
      <template v-else-if="name === 'stats-today'">
        <rect x="4" y="5" width="16" height="15" rx="2.5" :stroke="stroke" stroke-width="1.5" />
        <path d="M4 10h16" :stroke="stroke" stroke-width="1.5" />
        <path d="M9 3v3M15 3v3" :stroke="stroke" stroke-width="1.5" stroke-linecap="round" />
        <rect x="8" y="13" width="3" height="3" rx="0.8" :fill="fillStrong" />
        <rect x="13" y="13" width="3" height="3" rx="0.8" :fill="fillSoft" />
      </template>

      <!-- L3+ 高风险 -->
      <template v-else-if="name === 'stats-risk'">
        <path
          d="M12 4.5 20.5 19H3.5L12 4.5Z"
          :stroke="stroke"
          stroke-width="1.5"
          stroke-linejoin="round"
          :fill="fillSoft"
        />
        <path d="M12 10v4.5" :stroke="stroke" stroke-width="1.8" stroke-linecap="round" />
        <circle cx="12" cy="17" r="1" :fill="fillStrong" />
      </template>

      <!-- 安全拦截 -->
      <template v-else-if="name === 'stats-blocked'">
        <path
          d="M12 3.5 18.5 6.5V11.5c0 3.6-2.8 6.9-6.5 8-3.7-1.1-6.5-4.4-6.5-8V6.5L12 3.5Z"
          :stroke="stroke"
          stroke-width="1.5"
          stroke-linejoin="round"
          :fill="fillSoft"
        />
        <path d="M9 12.5 15 12.5" :stroke="stroke" stroke-width="1.8" stroke-linecap="round" />
      </template>

      <!-- 全部 -->
      <template v-else-if="name === 'module-all'">
        <rect x="5" y="4" width="14" height="16" rx="2" :stroke="stroke" stroke-width="1.5" />
        <path d="M8.5 9h7M8.5 12.5h7M8.5 16h4.5" :stroke="stroke" stroke-width="1.5" stroke-linecap="round" />
      </template>

      <!-- Agent 对话 -->
      <template v-else-if="name === 'module-chat'">
        <path
          d="M5 6.5h14a2 2 0 012 2v6.5a2 2 0 01-2 2H10l-4.5 3.5V8.5a2 2 0 012-2Z"
          :stroke="stroke"
          stroke-width="1.5"
          stroke-linejoin="round"
          :fill="fillSoft"
        />
        <path d="M9 11h6M9 13.5h3.5" :stroke="stroke" stroke-width="1.5" stroke-linecap="round" />
      </template>

      <!-- 审批恢复 -->
      <template v-else-if="name === 'module-resume'">
        <path
          d="M7 6.5h10a2 2 0 012 2v8a2 2 0 01-2 2H7a2 2 0 01-2-2v-8a2 2 0 012-2Z"
          :stroke="stroke"
          stroke-width="1.5"
          :fill="fillSoft"
        />
        <path
          d="M12 9.5v5M9.5 12h5"
          :stroke="stroke"
          stroke-width="1.5"
          stroke-linecap="round"
        />
        <path
          d="M16.5 5.5a5 5 0 010 4"
          :stroke="stroke"
          stroke-width="1.5"
          stroke-linecap="round"
        />
        <path
          d="M18.5 5.5 16.5 5.5 16.5 7.5"
          :stroke="stroke"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </template>

      <!-- 安全流程 -->
      <template v-else-if="name === 'module-workflow'">
        <rect x="6" y="11" width="12" height="9" rx="2" :stroke="stroke" stroke-width="1.5" :fill="fillSoft" />
        <path
          d="M9 11V8.5a3 3 0 116 0V11"
          :stroke="stroke"
          stroke-width="1.5"
          stroke-linecap="round"
        />
        <circle cx="12" cy="15.5" r="1.2" :fill="fillStrong" />
        <path d="M12 16.7v1.3" :stroke="stroke" stroke-width="1.5" stroke-linecap="round" />
      </template>

      <!-- 安全拦截（盾牌） -->
      <template v-else-if="name === 'module-blocked'">
        <path
          d="M12 3.5 18.5 6.5V11.5c0 3.6-2.8 6.9-6.5 8-3.7-1.1-6.5-4.4-6.5-8V6.5L12 3.5Z"
          :stroke="stroke"
          stroke-width="1.5"
          stroke-linejoin="round"
          :fill="fillSoft"
        />
        <path d="M12 8.5v4.5" :stroke="stroke" stroke-width="1.8" stroke-linecap="round" />
        <circle cx="12" cy="15.5" r="1" :fill="fillStrong" />
      </template>

      <!-- 用户 -->
      <template v-else-if="name === 'meta-user'">
        <circle cx="12" cy="8.5" r="3" :stroke="stroke" stroke-width="1.5" />
        <path
          d="M6 19.5c.8-3 2.9-4.5 6-4.5s5.2 1.5 6 4.5"
          :stroke="stroke"
          stroke-width="1.5"
          stroke-linecap="round"
        />
      </template>

      <!-- TraceId -->
      <template v-else-if="name === 'meta-trace'">
        <path
          d="M10.5 8.5a3.5 3.5 0 114.95 4.95l-5.2 5.2a2.5 2.5 0 11-3.54-3.54l5.2-5.2"
          :stroke="stroke"
          stroke-width="1.5"
          stroke-linecap="round"
        />
      </template>

      <!-- 耗时 -->
      <template v-else-if="name === 'meta-time'">
        <circle cx="12" cy="12" r="7.5" :stroke="stroke" stroke-width="1.5" />
        <path d="M12 8v4.2l2.8 1.6" :stroke="stroke" stroke-width="1.5" stroke-linecap="round" />
      </template>

      <!-- 工具 -->
      <template v-else-if="name === 'meta-tool'">
        <path
          d="M14.5 6.5 9.5 11.5a2.2 2.2 0 103.1 3.1l5-5a2.2 2.2 0 10-3.1-3.1Z"
          :stroke="stroke"
          stroke-width="1.5"
          stroke-linejoin="round"
        />
        <path d="M7 17l-2 2" :stroke="stroke" stroke-width="1.5" stroke-linecap="round" />
      </template>

      <!-- 空状态 -->
      <template v-else-if="name === 'empty-list'">
        <rect x="5" y="4" width="14" height="16" rx="2" :stroke="stroke" stroke-width="1.5" />
        <path d="M8.5 9h7M8.5 12.5h5.5" :stroke="stroke" stroke-width="1.5" stroke-linecap="round" opacity="0.55" />
        <circle cx="16.5" cy="16.5" r="3.5" :stroke="stroke" stroke-width="1.5" />
        <path d="M15 16.5h3M16.5 15v3" :stroke="stroke" stroke-width="1.5" stroke-linecap="round" />
      </template>

      <!-- 回放 -->
      <template v-else-if="name === 'action-replay'">
        <path d="M9 8.5 5.5 12 9 15.5V13h6.5a3 3 0 000-6H9V8.5Z" :fill="fillSoft" :stroke="stroke" stroke-width="1.5" stroke-linejoin="round" />
      </template>
    </svg>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AuditIconName } from './auditEventMeta'

const props = withDefaults(
  defineProps<{
    name: AuditIconName
    tone?: 'default' | 'blue' | 'cyan' | 'orange' | 'red' | 'muted'
    size?: 'sm' | 'md' | 'lg'
    boxed?: boolean
  }>(),
  {
    tone: 'default',
    size: 'md',
    boxed: false,
  },
)

const sizeClass = computed(() => `size-${props.size}`)

const svgSize = computed(() => {
  if (props.size === 'sm') return 16
  if (props.size === 'lg') return 28
  return 20
})

const boxStyle = computed(() => {
  const px = props.boxed ? (props.size === 'lg' ? 44 : props.size === 'sm' ? 28 : 36) : undefined
  return px ? { width: `${px}px`, height: `${px}px` } : undefined
})

const stroke = computed(() => {
  const map = {
    default: '#475569',
    blue: '#2563eb',
    cyan: '#0891b2',
    orange: '#ea580c',
    red: '#dc2626',
    muted: '#94a3b8',
  }
  return map[props.tone]
})

const fillSoft = computed(() => {
  const map = {
    default: '#f1f5f9',
    blue: '#eff6ff',
    cyan: '#ecfeff',
    orange: '#fff7ed',
    red: '#fef2f2',
    muted: '#f8fafc',
  }
  return map[props.tone]
})

const fillStrong = computed(() => stroke.value)
</script>

<style scoped lang="scss">
.audit-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  line-height: 0;
  vertical-align: middle;

  &.boxed {
    border-radius: 12px;
    &.blue { background: linear-gradient(135deg, #eff6ff, #dbeafe); }
    &.cyan { background: linear-gradient(135deg, #ecfeff, #cffafe); }
    &.orange { background: linear-gradient(135deg, #fff7ed, #ffedd5); }
    &.red { background: linear-gradient(135deg, #fef2f2, #fee2e2); }
    &.default { background: linear-gradient(135deg, #f8fafc, #f1f5f9); }
    &.muted { background: #f8fafc; }
  }
}
</style>
