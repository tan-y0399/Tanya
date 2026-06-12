<template>
  <div class="disk-usb-gauge" :class="{ alert: isAlert, transferring: isTransferring }">
    <svg viewBox="0 0 100 100" class="usb-svg" aria-hidden="true">
      <defs>
        <mask :id="fillMask">
          <rect :x="BODY.x" :y="BODY.y" :width="BODY.w" :height="BODY.h" :rx="BODY.rx" fill="white" />
          <ellipse :cx="BODY.x + BODY.w * 0.52" :cy="BODY.y + BODY.h * 0.5" rx="21" ry="14" fill="black" />
        </mask>

        <linearGradient :id="bodyGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#fff7ed" />
          <stop offset="100%" stop-color="#ffedd5" />
        </linearGradient>

        <linearGradient :id="fillGrad" x1="0" y1="1" x2="0" y2="0">
          <stop offset="0%" :stop-color="fillDark" />
          <stop offset="100%" :stop-color="fillColor" />
        </linearGradient>

        <linearGradient :id="metalGrad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stop-color="#d4d4d8" />
          <stop offset="50%" stop-color="#f4f4f5" />
          <stop offset="100%" stop-color="#a1a1aa" />
        </linearGradient>

        <filter :id="usbGlow" x="-25%" y="-25%" width="150%" height="150%">
          <feDropShadow dx="0" dy="1.5" stdDeviation="2.5" :flood-color="glowColor" flood-opacity="0.38" />
        </filter>
      </defs>

      <!-- USB 插头 -->
      <g class="usb-connector" :filter="`url(#${usbGlow})`">
        <rect x="4" y="30" width="22" height="36" rx="3" :fill="`url(#${metalGrad})`" class="plug-shell" />
        <rect x="8.5" y="35" width="5" height="6" rx="0.8" class="contact" />
        <rect x="16" y="35" width="5" height="6" rx="0.8" class="contact" />
        <rect x="8.5" y="45" width="5" height="6" rx="0.8" class="contact" />
        <rect x="16" y="45" width="5" height="6" rx="0.8" class="contact" />
        <rect x="22" y="42" width="4" height="12" rx="1.2" class="plug-tab" />
      </g>

      <!-- U盘主体 -->
      <g class="usb-body" :filter="`url(#${usbGlow})`">
        <rect :x="BODY.x" :y="BODY.y" :width="BODY.w" :height="BODY.h" :rx="BODY.rx" :fill="`url(#${bodyGrad})`" />
        <!-- 液位填充 -->
        <rect
          :x="BODY.x"
          :y="fillY"
          :width="BODY.w"
          :height="fillHeight"
          :rx="BODY.rx"
          :fill="`url(#${fillGrad})`"
          :mask="`url(#${fillMask})`"
          class="usb-fill"
        />
        <!-- 科技纹理 -->
        <path d="M30 24 H84 M30 70 H84 M30 46 H50" class="trace-line" />
        <path d="M78 24 V70 M70 30 V64" class="trace-line faint" />
        <circle cx="82" cy="22" r="2.6" class="led" :class="{ on: pct > 0 }" />
        <!-- 数据传输流光 -->
        <rect x="28" y="44" width="56" height="5" rx="2.5" class="data-lane" />
        <rect
          v-if="isTransferring"
          x="28"
          y="44"
          width="18"
          height="5"
          rx="2.5"
          class="data-pulse"
        />
      </g>

      <!-- 主体边框 -->
      <rect :x="BODY.x" :y="BODY.y" :width="BODY.w" :height="BODY.h" :rx="BODY.rx" class="body-border" />
      <rect x="4" y="30" width="22" height="36" rx="3" class="plug-border" />
    </svg>

    <div class="usb-val" :class="{ alert: isAlert }">
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
const fillMask = `diskUsbMask-${uid}`
const bodyGrad = `diskBodyGrad-${uid}`
const fillGrad = `diskFillGrad-${uid}`
const metalGrad = `diskMetalGrad-${uid}`
const usbGlow = `diskUsbGlow-${uid}`

const BODY = { x: 26, y: 16, w: 64, h: 60, rx: 9 }

const isTransferring = ref(false)
let transferTimer = 0

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

const fillColor = computed(() => (isAlert.value ? '#ef4444' : '#f59e0b'))
const fillDark = computed(() => (isAlert.value ? '#b91c1c' : '#d97706'))
const glowColor = computed(() => (isAlert.value ? '#ef4444' : '#f59e0b'))

const fillHeight = computed(() => (BODY.h * pct.value) / 100)
const fillY = computed(() => BODY.y + BODY.h - fillHeight.value)

function triggerTransfer() {
  isTransferring.value = false
  requestAnimationFrame(() => {
    isTransferring.value = true
    window.clearTimeout(transferTimer)
    transferTimer = window.setTimeout(() => { isTransferring.value = false }, 1000)
  })
}

watch(numericValue, (nv, ov) => {
  if (nv !== null && nv !== ov) triggerTransfer()
})
</script>

<style lang="scss" scoped>
.disk-usb-gauge {
  position: relative;
  width: 100px;
  height: 100px;
  margin: 0 auto 4px;
}

.usb-svg {
  width: 100%;
  height: 100%;
  display: block;
}

.plug-shell { stroke: rgba(161, 161, 170, 0.5); stroke-width: 0.5; }

.contact {
  fill: #fbbf24;
  stroke: #d97706;
  stroke-width: 0.3;
}

.plug-tab {
  fill: #e4e4e7;
  stroke: rgba(161, 161, 170, 0.6);
  stroke-width: 0.4;
}

.plug-border {
  fill: none;
  stroke: rgba(161, 161, 170, 0.65);
  stroke-width: 0.8;
}

.body-border {
  fill: none;
  stroke: rgba(245, 158, 11, 0.45);
  stroke-width: 1.1;
  .alert & { stroke: rgba(239, 68, 68, 0.5); }
}

.usb-fill {
  transition: y 0.55s cubic-bezier(0.4, 0, 0.2, 1),
              height 0.55s cubic-bezier(0.4, 0, 0.2, 1);
}

.trace-line {
  fill: none;
  stroke: rgba(245, 158, 11, 0.22);
  stroke-width: 0.7;
  stroke-linecap: round;
  &.faint { stroke-opacity: 0.45; }
  .alert & { stroke: rgba(239, 68, 68, 0.22); }
}

.led {
  fill: #e2e8f0;
  stroke: rgba(245, 158, 11, 0.4);
  stroke-width: 0.5;
  transition: fill 0.3s, filter 0.3s;
  &.on {
    fill: #fbbf24;
    filter: drop-shadow(0 0 3px rgba(251, 191, 36, 0.8));
  }
  .alert &.on {
    fill: #f87171;
    filter: drop-shadow(0 0 3px rgba(248, 113, 113, 0.8));
  }
}

.data-lane {
  fill: rgba(245, 158, 11, 0.1);
  stroke: rgba(245, 158, 11, 0.15);
  stroke-width: 0.4;
}

.data-pulse {
  fill: rgba(251, 191, 36, 0.75);
  filter: drop-shadow(0 0 4px rgba(251, 191, 36, 0.6));
  animation: data-flow 0.9s ease-in-out infinite;
}

.transferring .led.on {
  animation: led-blink 0.35s ease-in-out infinite alternate;
}

@keyframes data-flow {
  0% { transform: translateX(0); opacity: 0.5; }
  50% { opacity: 1; }
  100% { transform: translateX(38px); opacity: 0.4; }
}

@keyframes led-blink {
  0% { opacity: 0.6; }
  100% { opacity: 1; }
}

.usb-val {
  position: absolute;
  left: 57%;
  top: 46%;
  transform: translate(-50%, -50%);
  display: flex;
  align-items: baseline;
  justify-content: center;
  pointer-events: none;
  z-index: 2;
  white-space: nowrap;
}

.val-num {
  font-size: 15px;
  font-weight: 700;
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  color: #d97706;
  line-height: 1;
  letter-spacing: -0.02em;
  text-shadow: 0 0 6px rgba(255, 255, 255, 0.95);
  .usb-val.alert & { color: #dc2626; }
}

.val-unit {
  font-size: 8px;
  font-weight: 700;
  color: #f59e0b;
  margin-left: 0.5px;
  .usb-val.alert & { color: #ef4444; }
}

.val-empty {
  font-size: 17px;
  font-weight: 700;
  color: #94a3b8;
}
</style>
