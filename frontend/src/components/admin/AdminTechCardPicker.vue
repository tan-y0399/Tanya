<template>
  <div
    class="tech-card-picker"
    :class="[`cols-${columns}`, { disabled }]"
    role="radiogroup"
    :aria-label="ariaLabel"
  >
    <button
      v-for="opt in options"
      :key="String(opt.value)"
      type="button"
      class="pick-card"
      :class="[opt.tone, { active: isSelected(opt.value), 'is-disabled': disabled }]"
      role="radio"
      :aria-checked="isSelected(opt.value)"
      :disabled="disabled"
      @click="select(opt.value)"
    >
      <span class="card-corner card-corner--tl" aria-hidden="true"></span>
      <span class="card-corner card-corner--br" aria-hidden="true"></span>

      <span class="card-code">{{ opt.code }}</span>

      <span v-if="opt.icon && iconComponents[opt.icon]" class="card-icon" aria-hidden="true">
        <component :is="iconComponents[opt.icon]" />
      </span>

      <strong class="card-label">{{ opt.label }}</strong>
      <span class="card-desc">{{ opt.desc }}</span>
      <span v-if="isSelected(opt.value)" class="card-active-dot" aria-hidden="true"></span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { h, defineComponent, type Component } from 'vue'

export interface TechCardOption {
  value: string | number
  code: string
  label: string
  desc: string
  tone: string
  icon?: string
}

const props = withDefaults(
  defineProps<{
    modelValue: string | number
    options: TechCardOption[]
    columns?: 2 | 3 | 4 | 5
    disabled?: boolean
    ariaLabel?: string
  }>(),
  { columns: 3, disabled: false, ariaLabel: '选项' },
)

const emit = defineEmits<{ 'update:modelValue': [string | number] }>()

function isSelected(value: string | number) {
  return props.modelValue === value
}

function select(value: string | number) {
  if (props.disabled || value === props.modelValue) return
  emit('update:modelValue', value)
}

function mkIcon(render: () => ReturnType<typeof h>[]) {
  return defineComponent({
    render: () => h('svg', { viewBox: '0 0 24 24', fill: 'none' }, render()),
  })
}

const iconComponents: Record<string, Component> = {
  info: mkIcon(() => [
    h('circle', { cx: 12, cy: 12, r: 8, stroke: 'currentColor', 'stroke-width': 1.6 }),
    h('path', { d: 'M12 10v5M12 8h.01', stroke: 'currentColor', 'stroke-width': 1.8, 'stroke-linecap': 'round' }),
  ]),
  warning: mkIcon(() => [
    h('path', { d: 'M12 4.5l8.5 14.5H3.5L12 4.5z', stroke: 'currentColor', 'stroke-width': 1.6, 'stroke-linejoin': 'round' }),
    h('path', { d: 'M12 10v4M12 16.5h.01', stroke: 'currentColor', 'stroke-width': 1.8, 'stroke-linecap': 'round' }),
  ]),
  critical: mkIcon(() => [
    h('path', { d: 'M12 3.5l6.5 3v5.2c0 4.1-2.8 7.9-6.5 9.3-3.7-1.4-6.5-5.2-6.5-9.3V6.5L12 3.5z', stroke: 'currentColor', 'stroke-width': 1.6, 'stroke-linejoin': 'round' }),
    h('path', { d: 'M12 9v4M12 15h.01', stroke: 'currentColor', 'stroke-width': 1.8, 'stroke-linecap': 'round' }),
  ]),
  admin: mkIcon(() => [
    h('circle', { cx: 12, cy: 8, r: 3.2, stroke: 'currentColor', 'stroke-width': 1.6 }),
    h('path', { d: 'M5.5 19c0-3.6 2.9-5.5 6.5-5.5s6.5 1.9 6.5 5.5', stroke: 'currentColor', 'stroke-width': 1.6, 'stroke-linecap': 'round' }),
    h('path', { d: 'M12 4.5V3M16 5l1-1M8 5L7 4', stroke: 'currentColor', 'stroke-width': 1.3, 'stroke-linecap': 'round', opacity: 0.6 }),
  ]),
  user: mkIcon(() => [
    h('circle', { cx: 12, cy: 8.5, r: 3.2, stroke: 'currentColor', 'stroke-width': 1.6 }),
    h('path', { d: 'M5.5 19c0-3.6 2.9-5.5 6.5-5.5s6.5 1.9 6.5 5.5', stroke: 'currentColor', 'stroke-width': 1.6, 'stroke-linecap': 'round' }),
  ]),
  monitor: mkIcon(() => [
    h('rect', { x: 4, y: 5, width: 16, height: 11, rx: 2, stroke: 'currentColor', 'stroke-width': 1.5 }),
    h('path', { d: 'M8 19h8M12 16v3', stroke: 'currentColor', 'stroke-width': 1.5, 'stroke-linecap': 'round' }),
    h('path', { d: 'M8 10h5M8 13h3', stroke: 'currentColor', 'stroke-width': 1.3, 'stroke-linecap': 'round' }),
  ]),
  process: mkIcon(() => [
    h('circle', { cx: 12, cy: 12, r: 7, stroke: 'currentColor', 'stroke-width': 1.5 }),
    h('path', { d: 'M12 8v4l3 2', stroke: 'currentColor', 'stroke-width': 1.5, 'stroke-linecap': 'round' }),
  ]),
  service: mkIcon(() => [
    h('rect', { x: 5, y: 6, width: 14, height: 12, rx: 2, stroke: 'currentColor', 'stroke-width': 1.5 }),
    h('path', { d: 'M9 10h6M9 14h4', stroke: 'currentColor', 'stroke-width': 1.3, 'stroke-linecap': 'round' }),
  ]),
  file: mkIcon(() => [
    h('path', { d: 'M8 4h8l4 4v12a1 1 0 01-1 1H8a1 1 0 01-1-1V5a1 1 0 011-1z', stroke: 'currentColor', 'stroke-width': 1.5, 'stroke-linejoin': 'round' }),
    h('path', { d: 'M16 4v4h4M10 13h6M10 16h4', stroke: 'currentColor', 'stroke-width': 1.3, 'stroke-linecap': 'round' }),
  ]),
  network: mkIcon(() => [
    h('circle', { cx: 6, cy: 12, r: 2.5, stroke: 'currentColor', 'stroke-width': 1.4 }),
    h('circle', { cx: 18, cy: 6, r: 2.5, stroke: 'currentColor', 'stroke-width': 1.4 }),
    h('circle', { cx: 18, cy: 18, r: 2.5, stroke: 'currentColor', 'stroke-width': 1.4 }),
    h('path', { d: 'M8.5 11l7-4M8.5 13l7 4', stroke: 'currentColor', 'stroke-width': 1.3 }),
  ]),
  log: mkIcon(() => [
    h('path', { d: 'M5 6h14v12H5z', stroke: 'currentColor', 'stroke-width': 1.5, 'stroke-linejoin': 'round' }),
    h('path', { d: 'M8 10h8M8 13h6M8 16h4', stroke: 'currentColor', 'stroke-width': 1.3, 'stroke-linecap': 'round' }),
  ]),
  operation: mkIcon(() => [
    h('path', { d: 'M8 7l-3 5 3 5M16 7l3 5-3 5M14 6l-4 12', stroke: 'currentColor', 'stroke-width': 1.6, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }),
  ]),
  risk1: mkIcon(() => [
    h('circle', { cx: 12, cy: 12, r: 7, stroke: 'currentColor', 'stroke-width': 1.5 }),
    h('path', { d: 'M9 12l2 2 4-4', stroke: 'currentColor', 'stroke-width': 1.6, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }),
  ]),
  risk2: mkIcon(() => [
    h('path', { d: 'M12 4.5l7 12.5H5L12 4.5z', stroke: 'currentColor', 'stroke-width': 1.5, 'stroke-linejoin': 'round' }),
    h('path', { d: 'M12 10v3', stroke: 'currentColor', 'stroke-width': 1.6, 'stroke-linecap': 'round' }),
  ]),
  risk3: mkIcon(() => [
    h('path', { d: 'M12 4.5l7 12.5H5L12 4.5z', stroke: 'currentColor', 'stroke-width': 1.5, 'stroke-linejoin': 'round' }),
    h('path', { d: 'M12 9v4M12 15h.01', stroke: 'currentColor', 'stroke-width': 1.6, 'stroke-linecap': 'round' }),
  ]),
  risk4: mkIcon(() => [
    h('path', { d: 'M12 3.5l6.5 3v5.2c0 4.1-2.8 7.9-6.5 9.3-3.7-1.4-6.5-5.2-6.5-9.3V6.5L12 3.5z', stroke: 'currentColor', 'stroke-width': 1.5, 'stroke-linejoin': 'round' }),
    h('path', { d: 'M12 9v4', stroke: 'currentColor', 'stroke-width': 1.6, 'stroke-linecap': 'round' }),
  ]),
  risk5: mkIcon(() => [
    h('path', { d: 'M12 3.5l6.5 3v5.2c0 4.1-2.8 7.9-6.5 9.3-3.7-1.4-6.5-5.2-6.5-9.3V6.5L12 3.5z', stroke: 'currentColor', 'stroke-width': 1.5, 'stroke-linejoin': 'round' }),
    h('path', { d: 'M12 8v5M12 15h.01', stroke: 'currentColor', 'stroke-width': 1.8, 'stroke-linecap': 'round' }),
  ]),
}
</script>

<style lang="scss" scoped>
.tech-card-picker {
  display: grid;
  gap: 10px;

  &.cols-2 { grid-template-columns: repeat(2, 1fr); }
  &.cols-3 { grid-template-columns: repeat(3, 1fr); }
  &.cols-4 { grid-template-columns: repeat(4, 1fr); }
  &.cols-5 { grid-template-columns: repeat(5, 1fr); }

  &.disabled {
    opacity: 0.65;
    pointer-events: none;
  }

  @media (max-width: 560px) {
    &.cols-3,
    &.cols-4,
    &.cols-5 {
      grid-template-columns: repeat(2, 1fr);
    }
  }

  @media (max-width: 400px) {
    grid-template-columns: 1fr !important;
  }
}

.pick-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 14px 8px 12px;
  border: 1.5px solid #e2e8f0;
  border-radius: 12px;
  background: #fff;
  cursor: pointer;
  text-align: center;
  transition: border-color 0.18s, box-shadow 0.18s, transform 0.15s, background 0.18s;

  &:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 6px 18px rgba(15, 23, 42, 0.06);
  }

  &.active {
    transform: translateY(-1px);
  }

  // severity tones
  &.info.active {
    border-color: #2563eb; background: #eff6ff;
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.12), 0 6px 20px rgba(37, 99, 235, 0.1);
    .card-icon { color: #2563eb; }
    .card-code { background: rgba(37, 99, 235, 0.12); color: #2563eb; }
    .card-corner { border-color: rgba(37, 99, 235, 0.45); }
    .card-active-dot { background: #2563eb; }
  }
  &.warning.active {
    border-color: #d97706; background: #fffbeb;
    box-shadow: 0 0 0 2px rgba(217, 119, 6, 0.12), 0 6px 20px rgba(217, 119, 6, 0.1);
    .card-icon { color: #d97706; }
    .card-code { background: rgba(217, 119, 6, 0.12); color: #d97706; }
    .card-corner { border-color: rgba(217, 119, 6, 0.45); }
    .card-active-dot { background: #d97706; }
  }
  &.critical.active {
    border-color: #dc2626; background: #fef2f2;
    box-shadow: 0 0 0 2px rgba(220, 38, 38, 0.12), 0 6px 20px rgba(220, 38, 38, 0.1);
    .card-icon { color: #dc2626; }
    .card-code { background: rgba(220, 38, 38, 0.12); color: #dc2626; }
    .card-corner { border-color: rgba(220, 38, 38, 0.45); }
    .card-active-dot { background: #dc2626; }
  }

  // role tones
  &.admin.active {
    border-color: #dc2626; background: #fef2f2;
    box-shadow: 0 0 0 2px rgba(220, 38, 38, 0.1), 0 6px 20px rgba(220, 38, 38, 0.08);
    .card-icon { color: #dc2626; }
    .card-code { background: rgba(220, 38, 38, 0.1); color: #dc2626; }
    .card-corner { border-color: rgba(220, 38, 38, 0.4); }
    .card-active-dot { background: #dc2626; }
  }
  &.user.active {
    border-color: #2563eb; background: #eff6ff;
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.12), 0 6px 20px rgba(37, 99, 235, 0.1);
    .card-icon { color: #2563eb; }
    .card-code { background: rgba(37, 99, 235, 0.12); color: #2563eb; }
    .card-corner { border-color: rgba(37, 99, 235, 0.45); }
    .card-active-dot { background: #2563eb; }
  }

  // category tones
  &.cat.active {
    border-color: #7c3aed; background: #f5f3ff;
    box-shadow: 0 0 0 2px rgba(124, 58, 237, 0.12), 0 6px 20px rgba(124, 58, 237, 0.1);
    .card-icon { color: #7c3aed; }
    .card-code { background: rgba(124, 58, 237, 0.12); color: #7c3aed; }
    .card-corner { border-color: rgba(124, 58, 237, 0.45); }
    .card-active-dot { background: #7c3aed; }
  }

  // risk tones
  &.risk-l1.active {
    border-color: #059669; background: #ecfdf5;
    box-shadow: 0 0 0 2px rgba(5, 150, 105, 0.12), 0 6px 20px rgba(5, 150, 105, 0.1);
    .card-icon { color: #059669; }
    .card-code { background: rgba(5, 150, 105, 0.12); color: #059669; }
    .card-corner { border-color: rgba(5, 150, 105, 0.45); }
    .card-active-dot { background: #059669; }
  }
  &.risk-l2.active {
    border-color: #2563eb; background: #eff6ff;
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.12), 0 6px 20px rgba(37, 99, 235, 0.1);
    .card-icon { color: #2563eb; }
    .card-code { background: rgba(37, 99, 235, 0.12); color: #2563eb; }
    .card-corner { border-color: rgba(37, 99, 235, 0.45); }
    .card-active-dot { background: #2563eb; }
  }
  &.risk-l3.active {
    border-color: #d97706; background: #fffbeb;
    box-shadow: 0 0 0 2px rgba(217, 119, 6, 0.12), 0 6px 20px rgba(217, 119, 6, 0.1);
    .card-icon { color: #d97706; }
    .card-code { background: rgba(217, 119, 6, 0.12); color: #d97706; }
    .card-corner { border-color: rgba(217, 119, 6, 0.45); }
    .card-active-dot { background: #d97706; }
  }
  &.risk-l4.active {
    border-color: #ea580c; background: #fff7ed;
    box-shadow: 0 0 0 2px rgba(234, 88, 12, 0.12), 0 6px 20px rgba(234, 88, 12, 0.1);
    .card-icon { color: #ea580c; }
    .card-code { background: rgba(234, 88, 12, 0.12); color: #ea580c; }
    .card-corner { border-color: rgba(234, 88, 12, 0.45); }
    .card-active-dot { background: #ea580c; }
  }
  &.risk-l5.active {
    border-color: #dc2626; background: #fef2f2;
    box-shadow: 0 0 0 2px rgba(220, 38, 38, 0.12), 0 6px 20px rgba(220, 38, 38, 0.1);
    .card-icon { color: #dc2626; }
    .card-code { background: rgba(220, 38, 38, 0.12); color: #dc2626; }
    .card-corner { border-color: rgba(220, 38, 38, 0.45); }
    .card-active-dot { background: #dc2626; }
  }
}

.card-corner {
  position: absolute;
  width: 10px;
  height: 10px;
  border-color: rgba(148, 163, 184, 0.35);
  border-style: solid;
  pointer-events: none;
  transition: border-color 0.18s;
}

.card-corner--tl { top: 6px; left: 6px; border-width: 1.5px 0 0 1.5px; }
.card-corner--br { bottom: 6px; right: 6px; border-width: 0 1.5px 1.5px 0; }

.card-code {
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: #94a3b8;
  padding: 2px 7px;
  border-radius: 4px;
  background: #f1f5f9;
  transition: background 0.18s, color 0.18s;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-icon {
  width: 28px;
  height: 28px;
  color: #94a3b8;
  margin: 2px 0;

  :deep(svg) {
    width: 100%;
    height: 100%;
    display: block;
  }
}

.card-label {
  font-size: 13px;
  font-weight: 800;
  color: #1e293b;
  line-height: 1.3;
}

.card-desc {
  font-size: 10px;
  color: #94a3b8;
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-active-dot {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  box-shadow: 0 0 6px currentColor;
}
</style>
