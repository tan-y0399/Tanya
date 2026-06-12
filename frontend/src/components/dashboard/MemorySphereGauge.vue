<template>
  <div
    class="memory-sphere"
    :class="{ alert: isAlert, shaking: isShaking, sloshing: isSloshing }"
    role="button"
    tabindex="0"
    title="点击晃动水晶球"
    @click="triggerShake"
    @keydown.enter="triggerShake"
  >
    <svg viewBox="0 0 100 100" class="sphere-svg" aria-hidden="true">
      <defs>
        <clipPath :id="sphereClip">
          <circle cx="50" cy="50" r="38" />
        </clipPath>

        <mask :id="liquidMask">
          <circle cx="50" cy="50" r="38" fill="white" />
          <ellipse cx="50" cy="50" rx="24" ry="15" fill="black" />
        </mask>

        <linearGradient :id="liquidGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" :stop-color="liquidTop" stop-opacity="0.88" />
          <stop offset="55%" :stop-color="liquidMid" stop-opacity="0.95" />
          <stop offset="100%" :stop-color="liquidBottom" />
        </linearGradient>

        <radialGradient :id="sphereShine" cx="35%" cy="30%" r="65%">
          <stop offset="0%" stop-color="#ffffff" stop-opacity="0.45" />
          <stop offset="100%" stop-color="#ffffff" stop-opacity="0" />
        </radialGradient>
      </defs>

      <!-- 球体玻璃底色 -->
      <circle cx="50" cy="50" r="38" class="sphere-glass" />

      <!-- 液体层 -->
      <g :clip-path="`url(#${sphereClip})`" :mask="`url(#${liquidMask})`">
        <g class="liquid-group" :style="liquidStyle">
          <rect x="8" :y="liquidSurfaceY" width="84" :height="88 - liquidSurfaceY" :fill="`url(#${liquidGrad})`" />
          <path :d="wavePathA" class="liquid-wave wave-a" :fill="liquidTop" fill-opacity="0.55" />
          <path :d="wavePathB" class="liquid-wave wave-b" :fill="liquidMid" fill-opacity="0.42" />
        </g>
      </g>

      <!-- 立体经纬线网格 -->
      <g class="wireframe" :clip-path="`url(#${sphereClip})`">
        <ellipse
          v-for="(lat, i) in latitudes"
          :key="`lat-${i}`"
          cx="50"
          :cy="lat.cy"
          :rx="lat.rx"
          :ry="lat.ry"
          class="grid-line"
        />
        <ellipse
          v-for="(lon, i) in longitudes"
          :key="`lon-${i}`"
          cx="50"
          cy="50"
          :rx="lon.rx"
          ry="38"
          class="grid-line"
          :transform="`rotate(${lon.rot} 50 50)`"
        />
      </g>

      <!-- 外圈与高光 -->
      <circle cx="50" cy="50" r="38" class="sphere-border" />
      <circle cx="50" cy="50" r="38" :fill="`url(#${sphereShine})`" class="sphere-shine" />
      <ellipse cx="38" cy="34" rx="10" ry="6" class="specular" />
    </svg>

    <div class="sphere-val" :class="{ alert: isAlert }">
      <template v-if="hasValue">
        <span class="val-num">{{ formattedValue }}</span><span class="val-unit">%</span>
      </template>
      <span v-else class="val-empty">-</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps<{
  value?: number | string | null
}>()

const uid = Math.random().toString(36).slice(2, 8)
const sphereClip = `memSphereClip-${uid}`
const liquidGrad = `memLiquidGrad-${uid}`
const sphereShine = `memSphereShine-${uid}`
const liquidMask = `memLiquidMask-${uid}`

const isShaking = ref(false)
const isSloshing = ref(true)
const wavePhase = ref(0)
const tiltX = ref(0)
const tiltY = ref(0)
let rafId = 0
let shakeTimer = 0
let lastTs = 0

const R = 38
const CY = 50
const BOTTOM = CY + R

const latitudes = [
  { cy: 26, rx: 22, ry: 5 },
  { cy: 34, rx: 30, ry: 6.5 },
  { cy: 42, rx: 35, ry: 7 },
  { cy: 50, rx: 38, ry: 7.5 },
  { cy: 58, rx: 35, ry: 7 },
  { cy: 66, rx: 30, ry: 6.5 },
  { cy: 74, rx: 22, ry: 5 },
]

const longitudes = Array.from({ length: 8 }, (_, i) => ({
  rx: 6 + Math.abs(Math.cos((i / 8) * Math.PI)) * 32,
  rot: (i / 8) * 180,
}))

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

const liquidTop = computed(() => (isAlert.value ? '#f87171' : '#34d399'))
const liquidMid = computed(() => (isAlert.value ? '#ef4444' : '#10b981'))
const liquidBottom = computed(() => (isAlert.value ? '#b91c1c' : '#059669'))

const liquidSurfaceY = computed(() => {
  const fillH = (R * 2 * pct.value) / 100
  return BOTTOM - fillH
})

function buildWave(baseY: number, amp: number, phase: number, wavelength: number) {
  const x0 = 10
  const x1 = 90
  const steps = 8
  const dx = (x1 - x0) / steps
  let d = `M ${x0} ${BOTTOM} L ${x0} ${baseY}`
  for (let i = 0; i <= steps; i++) {
    const x = x0 + i * dx
    const y = baseY + Math.sin((i / steps) * Math.PI * 2 * (wavelength / 10) + phase) * amp
    if (i === 0) d += ` L ${x} ${y}`
    else d += ` Q ${x - dx / 2} ${baseY + Math.sin((i - 0.5) / steps * Math.PI * 2 * (wavelength / 10) + phase) * amp} ${x} ${y}`
  }
  d += ` L ${x1} ${BOTTOM} Z`
  return d
}

const wavePathA = computed(() => buildWave(liquidSurfaceY.value, isShaking.value ? 3.8 : 1.8, wavePhase.value, 2.2))
const wavePathB = computed(() => buildWave(liquidSurfaceY.value + 1.5, isShaking.value ? 2.8 : 1.2, wavePhase.value + 1.4, 1.6))

const liquidStyle = computed(() => ({
  transform: `translate(${tiltX.value}, ${tiltY.value})`,
}))

function tick(ts: number) {
  if (!lastTs) lastTs = ts
  const dt = (ts - lastTs) / 1000
  lastTs = ts

  if (isSloshing.value) {
    const speed = isShaking.value ? 11 : 2.8
    wavePhase.value += dt * speed
    const sway = isShaking.value ? 7.5 : 1.8
    const freq = isShaking.value ? 16 : 3.2
    tiltX.value = Math.sin(wavePhase.value * freq) * sway * 0.42
    tiltY.value = Math.cos(wavePhase.value * (freq * 0.85)) * sway * 0.32
  }

  rafId = requestAnimationFrame(tick)
}

function triggerShake() {
  isShaking.value = true
  window.clearTimeout(shakeTimer)
  shakeTimer = window.setTimeout(() => {
    isShaking.value = false
    tiltX.value = 0
    tiltY.value = 0
  }, 1200)
}

watch(numericValue, () => {
  if (!isShaking.value) {
    isShaking.value = true
    window.clearTimeout(shakeTimer)
    shakeTimer = window.setTimeout(() => { isShaking.value = false }, 600)
  }
})

onMounted(() => {
  rafId = requestAnimationFrame(tick)
})

onUnmounted(() => {
  cancelAnimationFrame(rafId)
  window.clearTimeout(shakeTimer)
})
</script>

<style lang="scss" scoped>
.memory-sphere {
  position: relative;
  width: 100px;
  height: 100px;
  margin: 0 auto 4px;
  cursor: pointer;
  user-select: none;
  outline: none;

  &:focus-visible {
    .sphere-border { stroke: rgba(16, 185, 129, 0.75); stroke-width: 1.6; }
  }

  &.shaking {
    animation: sphere-jolt 0.12s ease-in-out infinite alternate;
  }
}

.sphere-svg {
  width: 100%;
  height: 100%;
  display: block;
}

.sphere-glass {
  fill: rgba(236, 253, 245, 0.55);
  stroke: none;
}

.sphere-border {
  fill: none;
  stroke: rgba(16, 185, 129, 0.42);
  stroke-width: 1.3;
  .alert & { stroke: rgba(239, 68, 68, 0.5); }
}

.sphere-shine {
  pointer-events: none;
}

.specular {
  fill: rgba(255, 255, 255, 0.55);
  transform: rotate(-18deg);
  transform-origin: 38px 34px;
}

.grid-line {
  fill: none;
  stroke: rgba(148, 163, 184, 0.38);
  stroke-width: 0.65;
  .alert & { stroke: rgba(248, 113, 113, 0.32); }
}

.liquid-group {
  transition: transform 0.08s linear;
  will-change: transform;
}

.liquid-wave {
  mix-blend-mode: soft-light;
}

.sphere-val {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  align-items: baseline;
  justify-content: center;
  pointer-events: none;
  z-index: 2;
  white-space: nowrap;
}

.val-num {
  font-size: 14px;
  font-weight: 700;
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  color: #059669;
  line-height: 1;
  letter-spacing: -0.02em;
  text-shadow: 0 0 8px rgba(255, 255, 255, 0.9);
  .sphere-val.alert & { color: #dc2626; }
}

.val-unit {
  font-size: 8px;
  font-weight: 700;
  color: #10b981;
  margin-left: 0.5px;
  .sphere-val.alert & { color: #ef4444; }
}

.val-empty {
  font-size: 17px;
  font-weight: 700;
  color: #94a3b8;
}

@keyframes sphere-jolt {
  0% { transform: rotate(-4deg) translateX(-2px); }
  50% { transform: rotate(0deg) translateX(0); }
  100% { transform: rotate(4deg) translateX(2px); }
}
</style>
