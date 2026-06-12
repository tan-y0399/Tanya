<template>
  <button
    type="button"
    class="nav-tile"
    :class="[item.channel, { active: activating, lit: lit, hover: isHover }]"
    :style="{ '--channel': item.color }"
    @mouseenter="isHover = true"
    @mouseleave="isHover = false"
    @click="onClick"
  >
    <!-- HUD corner brackets -->
    <svg class="brackets" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
      <path class="bk tl" d="M4 14 V4 H14" />
      <path class="bk tr" d="M86 4 H96 V14" />
      <path class="bk bl" d="M4 86 V96 H14" />
      <path class="bk br" d="M86 96 H96 V86" />
    </svg>

    <span class="tile-index">{{ indexLabel }}</span>

    <div class="icon-wrap">
      <QuickNavIcon :channel="item.channel" :hovered="isHover" :warn="item.status === 'warn'" />
    </div>

    <span class="tile-label">{{ item.label }}</span>
    <span class="tile-code">{{ item.code }}</span>

    <div class="tile-status" :class="item.status">
      <span class="status-dot"></span>
      <span class="status-text">{{ isHover ? item.hint : item.statusText }}</span>
    </div>

    <span class="ripple" :class="{ go: activating }"></span>
  </button>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import QuickNavIcon from './QuickNavIcon.vue'

export interface NavTileItem {
  path: string
  label: string
  code: string
  channel: 'chat' | 'srv' | 'aud' | 'alt'
  color: string
  status: 'ready' | 'online' | 'idle' | 'warn'
  statusText: string
  hint: string
}

const props = defineProps<{
  item: NavTileItem
  index: number
  lit?: boolean
}>()

const router = useRouter()
const isHover = ref(false)
const activating = ref(false)

const indexLabel = String(props.index + 1).padStart(2, '0')

function onClick() {
  activating.value = true
  window.setTimeout(() => {
    router.push(props.item.path)
    activating.value = false
  }, 140)
}
</script>

<style lang="scss" scoped>
.nav-tile {
  --channel: #06b6d4;
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 14px 10px 22px;
  border: 1px solid rgba(186, 230, 253, 0.5);
  border-radius: 10px;
  background:
    radial-gradient(ellipse at 50% 0%, color-mix(in srgb, var(--channel) 8%, transparent), transparent 70%),
    rgba(255, 255, 255, 0.78);
  cursor: pointer;
  font-family: inherit;
  overflow: hidden;
  transition: border-color 0.25s, box-shadow 0.25s, transform 0.15s;

  &:hover,
  &.hover {
    border-color: color-mix(in srgb, var(--channel) 45%, #e2e8f0);
    box-shadow: 0 4px 20px color-mix(in srgb, var(--channel) 14%, transparent);
    transform: translateY(-1px);
  }

  &:active,
  &.active {
    transform: translateY(1px);
    box-shadow: 0 1px 6px color-mix(in srgb, var(--channel) 10%, transparent);
  }

  &.lit {
    border-color: color-mix(in srgb, var(--channel) 55%, #e2e8f0);
    box-shadow: 0 0 16px color-mix(in srgb, var(--channel) 18%, transparent);
  }
}

.brackets {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;

  .bk {
    fill: none;
    stroke: var(--channel);
    stroke-width: 2.2;
    stroke-linecap: round;
    opacity: 0.22;
    transition: opacity 0.25s, d 0.25s;
  }
}

.nav-tile:hover .bk,
.nav-tile.lit .bk {
  opacity: 0.55;
}

.tile-index {
  position: absolute;
  top: 7px;
  left: 9px;
  font-family: 'Inter', 'PingFang SC', sans-serif;
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: #94a3b8;
}

.icon-wrap {
  margin-top: 4px;
  margin-bottom: 2px;
}

.tile-label {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  line-height: 1.2;
}

.tile-code {
  font-family: 'Inter', 'PingFang SC', sans-serif;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: var(--channel);
}

.tile-status {
  position: absolute;
  bottom: 7px;
  left: 0;
  right: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  font-family: 'Inter', 'PingFang SC', sans-serif;
  font-size: 7px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: #94a3b8;

  &.online { color: #047857; .status-dot { background: #10b981; box-shadow: 0 0 4px rgba(16,185,129,0.5); } }
  &.ready  { color: #0891b2; .status-dot { background: #06b6d4; } }
  &.idle   { color: #94a3b8; .status-dot { background: #cbd5e1; } }
  &.warn   { color: #dc2626; .status-dot { background: #ef4444; box-shadow: 0 0 4px rgba(239,68,68,0.5); animation: warn-blink 1s ease infinite; } }
}

.status-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  flex-shrink: 0;
}

@keyframes warn-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.35; }
}

.status-text {
  max-width: 90%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  transition: color 0.2s;
}

.nav-tile:hover .status-text {
  color: var(--channel);
}

.ripple {
  position: absolute;
  inset: 0;
  background: radial-gradient(circle at 50% 50%, color-mix(in srgb, var(--channel) 25%, transparent), transparent 65%);
  opacity: 0;
  pointer-events: none;

  &.go {
    animation: tile-flash 0.14s ease-out;
  }
}

@keyframes tile-flash {
  0% { opacity: 0.7; }
  100% { opacity: 0; }
}
</style>
