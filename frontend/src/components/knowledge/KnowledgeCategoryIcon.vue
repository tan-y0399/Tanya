<template>
  <span class="kb-cat-icon" :class="{ sm, active }" :style="{ '--icon-bg': meta.color }">
    <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <g v-html="svgInner" />
    </svg>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { resolveCategoryIcon, type CategoryIconKey, type CategoryIconMeta } from './categoryIconMeta'

const props = withDefaults(
  defineProps<{
    name?: string
    iconKey?: CategoryIconKey
    color?: string
    sm?: boolean
    active?: boolean
  }>(),
  { name: '', sm: false, active: false },
)

const ICON_PATHS: Record<CategoryIconKey, string> = {
  all: '<path d="M5 6.5h5v5H5v-5Zm9 0h5v5h-5v-5ZM5 12.5h5v5H5v-5Zm9 0h5v5h-5v-5Z" fill="#fff" opacity=".95"/>',
  security: '<rect x="7" y="10" width="10" height="8" rx="1.5" stroke="#fff" stroke-width="1.8"/><path d="M9 10V8.5a3 3 0 116 0V10" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/>',
  boot: '<rect x="5" y="6" width="14" height="10" rx="1.5" stroke="#fff" stroke-width="1.8"/><path d="M9 17v1.5M15 17v1.5M8 9h8" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/>',
  service: '<path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/>',
  config: '<path d="M9 5H7a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2" stroke="#fff" stroke-width="1.8"/><rect x="9" y="3" width="6" height="4" rx="1" stroke="#fff" stroke-width="1.8"/><path d="M9 12h6M9 16h4" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/>',
  disk: '<ellipse cx="12" cy="7" rx="7" ry="3" stroke="#fff" stroke-width="1.8"/><path d="M5 7v6c0 1.66 3.13 3 7 3s7-1.34 7-3V7" stroke="#fff" stroke-width="1.8"/><path d="M5 13v4c0 1.66 3.13 3 7 3s7-1.34 7-3v-4" stroke="#fff" stroke-width="1.8"/>',
  log: '<path d="M8 6h8M8 10h8M8 14h5" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/><rect x="5" y="4" width="14" height="16" rx="2" stroke="#fff" stroke-width="1.8"/>',
  domestic: '<path d="M4 18V9l8-5 8 5v9H4Z" stroke="#fff" stroke-width="1.8" stroke-linejoin="round"/><path d="M9 18v-5h6v5" stroke="#fff" stroke-width="1.8"/>',
  process: '<rect x="6" y="6" width="12" height="12" rx="2" stroke="#fff" stroke-width="1.8"/><path d="M9 9h6v6H9V9Z" fill="#fff" opacity=".9"/><path d="M12 6V4M12 20v-2M6 12H4M20 12h-2" stroke="#fff" stroke-width="1.6" stroke-linecap="round"/>',
  network: '<circle cx="12" cy="12" r="8" stroke="#fff" stroke-width="1.8"/><ellipse cx="12" cy="12" rx="3.5" ry="8" stroke="#fff" stroke-width="1.6"/><path d="M4 12h16" stroke="#fff" stroke-width="1.6"/>',
  install: '<path d="M12 4v10M8.5 10.5 12 14l3.5-3.5" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><path d="M5 18h14" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/>',
  startup: '<path d="M8 16l4-8 4 8H8Z" stroke="#fff" stroke-width="1.8" stroke-linejoin="round"/><path d="M12 6V4" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/>',
  login: '<circle cx="12" cy="9" r="3" stroke="#fff" stroke-width="1.8"/><path d="M6 19c0-3.314 2.686-5 6-5s6 1.686 6 5" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/>',
  activate: '<circle cx="12" cy="12" r="8" stroke="#fff" stroke-width="1.8"/><path d="M8.5 12.5 11 15l4.5-5" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
  permission: '<path d="M12 3l7 3v6c0 4.5-3.2 7.4-7 8-3.8-.6-7-3.5-7-8V6l7-3Z" stroke="#fff" stroke-width="1.8" stroke-linejoin="round"/>',
  version: '<path d="M7 7h10v10H7V7Z" stroke="#fff" stroke-width="1.8"/><path d="M9 5h6M9 19h6" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/>',
  software: '<rect x="5" y="5" width="6" height="6" rx="1.2" fill="#fff" opacity=".9"/><rect x="13" y="5" width="6" height="6" rx="1.2" stroke="#fff" stroke-width="1.6"/><rect x="5" y="13" width="6" height="6" rx="1.2" stroke="#fff" stroke-width="1.6"/><rect x="13" y="13" width="6" height="6" rx="1.2" fill="#fff" opacity=".9"/>',
  peripheral: '<rect x="6" y="8" width="12" height="8" rx="1.5" stroke="#fff" stroke-width="1.8"/><path d="M9 16v2h6v-2M10 8V6h4v2" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/>',
  manual: '<path d="M6 5h11a2 2 0 012 2v12H8a2 2 0 01-2-2V5Z" stroke="#fff" stroke-width="1.8"/><path d="M8 5v12a2 2 0 002 2h9" stroke="#fff" stroke-width="1.8"/><path d="M10 9h6M10 13h4" stroke="#fff" stroke-width="1.6" stroke-linecap="round"/>',
  display: '<rect x="4" y="6" width="16" height="10" rx="1.5" stroke="#fff" stroke-width="1.8"/><path d="M10 18h4" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/>',
  'network-faq': '<path d="M5 12a7 7 0 0114 0" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/><path d="M8.5 16.5h7" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/><circle cx="12" cy="12" r="1.5" fill="#fff"/>',
  input: '<rect x="5" y="8" width="14" height="8" rx="1.5" stroke="#fff" stroke-width="1.8"/><path d="M8 11h2M8 14h4" stroke="#fff" stroke-width="1.6" stroke-linecap="round"/>',
  mount: '<path d="M12 4v12M8 12l4 4 4-4" stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/><path d="M5 18h14" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/>',
  app: '<path d="M8 8h3v3H8V8Zm5 0h3v3h-3V8ZM8 13h3v3H8v-3Zm5 0h3v3h-3v-3Z" stroke="#fff" stroke-width="1.6"/>',
  other: '<circle cx="12" cy="12" r="2" fill="#fff"/><path d="M12 5v2M12 17v2M5 12h2M17 12h2" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/>',
  default: '<path d="M8 6h8v12H8V6Z" stroke="#fff" stroke-width="1.8"/><path d="M10 9h4M10 12h4M10 15h2" stroke="#fff" stroke-width="1.6" stroke-linecap="round"/>',
}

const meta = computed<CategoryIconMeta>(() => {
  if (props.iconKey) {
    return { key: props.iconKey, color: props.color || resolveCategoryIcon('').color }
  }
  const resolved = resolveCategoryIcon(props.name)
  if (props.color) return { ...resolved, color: props.color }
  return resolved
})

const svgInner = computed(() => ICON_PATHS[meta.value.key] || ICON_PATHS.default)
</script>

<style scoped lang="scss">
.kb-cat-icon {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--icon-bg);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  box-shadow: 0 2px 8px color-mix(in srgb, var(--icon-bg) 35%, transparent);
  transition: transform 0.2s ease, box-shadow 0.2s ease;

  svg {
    width: 16px;
    height: 16px;
  }

  &.sm {
    width: 24px;
    height: 24px;
    svg { width: 14px; height: 14px; }
  }

  &.active {
    transform: scale(1.06);
    box-shadow: 0 4px 14px color-mix(in srgb, var(--icon-bg) 45%, transparent);
  }
}
</style>
