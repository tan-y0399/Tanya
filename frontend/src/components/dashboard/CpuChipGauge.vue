<template>
  <div class="cpu-chip-gauge" :class="{ alert: isAlert, flowing: pinFlow }">
    <svg viewBox="0 0 100 100" class="chip-svg" aria-hidden="true">
      <defs>
        <!-- 芯片内区域减去大脑留白 = 可填充区 -->
        <mask :id="maskId">
          <rect x="20" y="20" width="60" height="60" rx="6" fill="white" />
          <path :d="brainOuter" fill="black" />
        </mask>

        <linearGradient :id="gradId" x1="0" y1="1" x2="0" y2="0">
          <stop offset="0%" :stop-color="fillColorDark" />
          <stop offset="100%" :stop-color="fillColor" />
        </linearGradient>

      </defs>

      <!-- 引脚（四周各 3 个） -->
      <g class="pins">
        <rect
          v-for="(pin, i) in pins"
          :key="i"
          :x="pin.x"
          :y="pin.y"
          :width="pin.w"
          :height="pin.h"
          rx="1"
          class="pin-body"
          :class="`pin-${pin.side}`"
          :style="{ animationDelay: `${pin.delay}ms` }"
        />
        <!-- 引脚向内流动光效 -->
        <line
          v-for="(pin, i) in pinFlows"
          :key="`flow-${i}`"
          :x1="pin.x1"
          :y1="pin.y1"
          :x2="pin.x2"
          :y2="pin.y2"
          class="pin-flow"
          :class="`flow-${pin.side}`"
          :style="{ animationDelay: `${pin.delay}ms` }"
        />
      </g>

      <!-- 芯片底板 -->
      <rect x="20" y="20" width="60" height="60" rx="6" class="chip-base" />

      <!-- 液位填充（大脑外、芯片内） -->
      <rect
        x="20"
        :y="fillY"
        width="60"
        :height="fillHeight"
        rx="6"
        :fill="`url(#${gradId})`"
        :mask="`url(#${maskId})`"
        class="chip-fill"
      />

      <!-- 大脑外轮廓（留白区） -->
      <path :d="brainOuter" class="brain-outline" />
      <!-- 脑沟纹理 -->
      <path :d="brainLines" class="brain-lines" />

      <!-- 芯片外框描边 -->
      <rect x="20" y="20" width="60" height="60" rx="6" class="chip-border" />
    </svg>

    <!-- 百分比文字（大脑留白区） -->
    <div class="chip-val" :class="{ alert: isAlert }">
      <template v-if="hasValue">
        <span class="val-num">{{ formattedValue }}</span><span class="val-unit">%</span>
      </template>
      <span v-else class="val-empty">-</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

const props = defineProps<{
  value?: number | string | null
}>()

const uid = Math.random().toString(36).slice(2, 8)
const gradId = `cpuFillGrad-${uid}`
const maskId = `cpuChipMask-${uid}`

const pinFlow = ref(false)
let flowTimer = 0

// 大脑外轮廓（闭合路径，中心留白）
const brainOuter = [
  'M50 33',
  'C41 33 34 37 32 44',
  'C30 50 31 56 34 60',
  'C37 64 42 66 50 66',
  'C58 66 63 64 66 60',
  'C69 56 70 50 68 44',
  'C66 37 59 33 50 33 Z',
].join(' ')

// 脑沟与半球分割线
const brainLines = [
  'M50 35 L50 63',
  'M50 36 C46 37 43 41 42 45 C41 49 41 53 42 57 C43 60 46 62 50 62',
  'M50 36 C54 37 57 41 58 45 C59 49 59 53 58 57 C57 60 54 62 50 62',
  'M44 40 C42 43 41 47 42 50',
  'M56 40 C58 43 59 47 58 50',
].join(' ')

const CHIP = { x: 20, y: 20, w: 60, h: 60 }

const pins = [
  { x: 32, y: 13, w: 6, h: 7, side: 'top', delay: 0 },
  { x: 44, y: 13, w: 6, h: 7, side: 'top', delay: 60 },
  { x: 56, y: 13, w: 6, h: 7, side: 'top', delay: 120 },
  { x: 32, y: 80, w: 6, h: 7, side: 'bottom', delay: 180 },
  { x: 44, y: 80, w: 6, h: 7, side: 'bottom', delay: 240 },
  { x: 56, y: 80, w: 6, h: 7, side: 'bottom', delay: 300 },
  { x: 13, y: 32, w: 7, h: 6, side: 'left', delay: 40 },
  { x: 13, y: 44, w: 7, h: 6, side: 'left', delay: 100 },
  { x: 13, y: 56, w: 7, h: 6, side: 'left', delay: 160 },
  { x: 80, y: 32, w: 7, h: 6, side: 'right', delay: 80 },
  { x: 80, y: 44, w: 7, h: 6, side: 'right', delay: 140 },
  { x: 80, y: 56, w: 7, h: 6, side: 'right', delay: 200 },
]

const pinFlows = [
  { x1: 35, y1: 20, x2: 35, y2: 28, side: 'top', delay: 0 },
  { x1: 47, y1: 20, x2: 47, y2: 28, side: 'top', delay: 60 },
  { x1: 59, y1: 20, x2: 59, y2: 28, side: 'top', delay: 120 },
  { x1: 35, y1: 80, x2: 35, y2: 72, side: 'bottom', delay: 180 },
  { x1: 47, y1: 80, x2: 47, y2: 72, side: 'bottom', delay: 240 },
  { x1: 59, y1: 80, x2: 59, y2: 72, side: 'bottom', delay: 300 },
  { x1: 20, y1: 35, x2: 28, y2: 35, side: 'left', delay: 40 },
  { x1: 20, y1: 47, x2: 28, y2: 47, side: 'left', delay: 100 },
  { x1: 20, y1: 59, x2: 28, y2: 59, side: 'left', delay: 160 },
  { x1: 80, y1: 35, x2: 72, y2: 35, side: 'right', delay: 80 },
  { x1: 80, y1: 47, x2: 72, y2: 47, side: 'right', delay: 140 },
  { x1: 80, y1: 59, x2: 72, y2: 59, side: 'right', delay: 200 },
]

const numericValue = computed(() => {
  const v = props.value
  if (v === null || v === undefined || v === '-') return null
  const n = typeof v === 'number' ? v : parseFloat(String(v))
  return Number.isFinite(n) ? n : null
})

const hasValue = computed(() => numericValue.value !== null)

const formattedValue = computed(() => {
  if (numericValue.value === null) return '-'
  const v = numericValue.value
  return Number.isInteger(v) ? String(v) : v.toFixed(1)
})

const pct = computed(() => {
  if (numericValue.value === null) return 0
  return Math.min(100, Math.max(0, numericValue.value))
})

const isAlert = computed(() => numericValue.value !== null && numericValue.value > 80)

const fillColor = computed(() => (isAlert.value ? '#ef4444' : '#3b82f6'))
const fillColorDark = computed(() => (isAlert.value ? '#b91c1c' : '#1d4ed8'))

const fillHeight = computed(() => (CHIP.h * pct.value) / 100)
const fillY = computed(() => CHIP.y + CHIP.h - fillHeight.value)

function triggerPinFlow() {
  pinFlow.value = false
  requestAnimationFrame(() => {
    pinFlow.value = true
    window.clearTimeout(flowTimer)
    flowTimer = window.setTimeout(() => { pinFlow.value = false }, 1100)
  })
}

watch(numericValue, (nv, ov) => {
  if (nv !== null && nv !== ov) triggerPinFlow()
})
</script>

<style lang="scss" scoped>
.cpu-chip-gauge {
  position: relative;
  width: 96px;
  height: 96px;
  margin: 0 auto 8px;
}

.chip-svg {
  width: 100%;
  height: 100%;
  display: block;
}

.chip-base {
  fill: #dbeafe;
  stroke: none;
}

.chip-border {
  fill: none;
  stroke: rgba(59, 130, 246, 0.35);
  stroke-width: 1.2;
  .alert & { stroke: rgba(239, 68, 68, 0.45); }
}

.chip-fill {
  transition: y 0.55s cubic-bezier(0.4, 0, 0.2, 1),
              height 0.55s cubic-bezier(0.4, 0, 0.2, 1);
}

.brain-outline {
  fill: #ffffff;
  stroke: rgba(147, 197, 253, 0.9);
  stroke-width: 1.6;
  stroke-linejoin: round;
  .alert & { stroke: rgba(252, 165, 165, 0.95); }
}

.brain-lines {
  fill: none;
  stroke: rgba(147, 197, 253, 0.75);
  stroke-width: 1.1;
  stroke-linecap: round;
  stroke-linejoin: round;
  .alert & { stroke: rgba(252, 165, 165, 0.8); }
}

.pin-body {
  fill: #bfdbfe;
  stroke: rgba(59, 130, 246, 0.25);
  stroke-width: 0.4;
  transition: fill 0.35s;
  .alert & { fill: #fecaca; stroke: rgba(239, 68, 68, 0.3); }
}

.pin-flow {
  stroke: #60a5fa;
  stroke-width: 2.5;
  stroke-linecap: round;
  opacity: 0;
  .alert & { stroke: #f87171; }
}

.flowing {
  .pin-body {
    animation: pin-pulse 0.9s ease-out both;
  }
  .pin-flow {
    animation: flow-inward 0.85s ease-out both;
  }
}

@keyframes pin-pulse {
  0% { opacity: 0.45; filter: brightness(0.9); }
  35% { opacity: 1; filter: brightness(1.35) drop-shadow(0 0 3px rgba(96, 165, 250, 0.8)); }
  100% { opacity: 0.85; filter: none; }
}

@keyframes flow-inward {
  0% {
    opacity: 0;
    stroke-dasharray: 8 8;
    stroke-dashoffset: 8;
  }
  20% { opacity: 1; }
  100% {
    opacity: 0;
    stroke-dasharray: 8 8;
    stroke-dashoffset: -8;
  }
}

.chip-val {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  align-items: baseline;
  justify-content: center;
  pointer-events: none;
  z-index: 2;
}

.val-num {
  font-size: 15px;
  font-weight: 700;
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  color: #2563eb;
  line-height: 1;
  .chip-val.alert & { color: #dc2626; }
}

.val-unit {
  font-size: 9px;
  font-weight: 700;
  color: #3b82f6;
  margin-left: 1px;
  .chip-val.alert & { color: #ef4444; }
}

.val-empty {
  font-size: 18px;
  font-weight: 700;
  color: #94a3b8;
}
</style>
