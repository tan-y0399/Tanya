<template>
  <svg
    class="module-icon"
    :class="[{ active }, `mod-${moduleKey}`]"
    :style="{ '--icon-color': color }"
    viewBox="0 0 24 24"
    fill="none"
    aria-hidden="true"
  >
    <!-- 用户管理 -->
    <g v-if="moduleKey === 'users'">
      <circle cx="12" cy="8.5" r="3.2" stroke="currentColor" stroke-width="1.6" />
      <path
        d="M5.5 19c0-3.6 2.9-5.5 6.5-5.5s6.5 1.9 6.5 5.5"
        stroke="currentColor"
        stroke-width="1.6"
        stroke-linecap="round"
      />
      <path d="M12 3v1.2M12 20.8V22M3 12h1.2M19.8 12H22" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" opacity="0.45" />
    </g>

    <!-- 工具管理：Agent 可调用函数 -->
    <g v-else-if="moduleKey === 'tools'">
      <rect x="5" y="5" width="14" height="14" rx="3" stroke="currentColor" stroke-width="1.6" />
      <path
        d="M8 7l-2.5 5 2.5 5M16 7l2.5 5-2.5 5M13.5 6.5l-3 11"
        stroke="currentColor"
        stroke-width="1.5"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
      <circle cx="12" cy="12" r="1.2" fill="currentColor" opacity="0.5" />
    </g>

    <!-- 安全配置 -->
    <g v-else-if="moduleKey === 'security'">
      <path
        d="M12 3.5l6.5 3v5.2c0 4.1-2.8 7.9-6.5 9.3-3.7-1.4-6.5-5.2-6.5-9.3V6.5L12 3.5z"
        stroke="currentColor"
        stroke-width="1.6"
        stroke-linejoin="round"
      />
      <path
        d="M9.2 12.2l1.8 1.8 3.8-3.8"
        stroke="currentColor"
        stroke-width="1.6"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
    </g>

    <!-- 知识库 -->
    <g v-else-if="moduleKey === 'knowledge'">
      <path
        d="M5 6.5h11.5a1.5 1.5 0 011.5 1.5V18a1.5 1.5 0 01-1.5 1.5H5A1.5 1.5 0 013.5 18V8A1.5 1.5 0 015 6.5z"
        stroke="currentColor"
        stroke-width="1.5"
      />
      <path d="M8 6.5V18M14.5 10h4M14.5 13.5h3.2" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
      <path
        d="M16.5 6.5H19a1.5 1.5 0 011.5 1.5V16"
        stroke="currentColor"
        stroke-width="1.5"
        stroke-linecap="round"
        opacity="0.55"
      />
    </g>
  </svg>
</template>

<script setup lang="ts">
import type { AdminGearKey } from './gearPaths'

defineProps<{
  moduleKey: AdminGearKey
  color?: string
  active?: boolean
}>()
</script>

<style lang="scss" scoped>
.module-icon {
  position: relative;
  z-index: 1;
  width: 28px;
  height: 28px;
  color: var(--icon-color, #64748b);
  opacity: 0.82;
  transition: color 0.2s ease, opacity 0.2s ease, filter 0.2s ease;

  &.active {
    opacity: 1;
    filter: drop-shadow(0 0 6px color-mix(in srgb, var(--icon-color, #2563eb) 40%, transparent));
  }
}
</style>
