<template>
  <div class="sys-stopwatch" :class="{ ticking: isActive }">
    <svg viewBox="0 0 100 100" class="sw-svg" aria-hidden="true">
      <defs>
        <linearGradient :id="caseGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#eef2ff" />
          <stop offset="100%" stop-color="#e0e7ff" />
        </linearGradient>
        <linearGradient :id="handGrad" x1="0" y1="1" x2="0" y2="0">
          <stop offset="0%" stop-color="#6366f1" />
          <stop offset="100%" stop-color="#818cf8" />
        </linearGradient>
        <filter :id="swGlow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="1.5" stdDeviation="2" flood-color="#6366f1" flood-opacity="0.28" />
        </filter>
      </defs>

      <!-- 顶部按钮 -->
      <rect x="46" y="10" width="8" height="7" rx="2" class="crown-btn" />
      <rect x="44" y="16" width="12" height="4" rx="1.5" class="crown-base" />
      <!-- 侧按钮 -->
      <rect x="14" y="44" width="5" height="10" rx="2" class="side-btn" />

      <!-- 表壳 -->
      <circle cx="50" cy="54" r="34" :fill="`url(#${caseGrad})`" :filter="`url(#${swGlow})`" class="case-body" />
      <circle cx="50" cy="54" r="34" class="case-ring" />

      <!-- 刻度 -->
      <g class="ticks">
        <line
          v-for="(t, i) in tickMarks"
          :key="i"
          :x1="t.x1" :y1="t.y1" :x2="t.x2" :y2="t.y2"
          :class="{ major: t.major }"
        />
      </g>

      <!-- 运行弧迹（当前 60 秒内已转过的角度） -->
      <path :d="sweepArc" class="sweep-trail" />

      <!-- 指针：与中心秒数同步，每 60 秒一圈 -->
      <g
        class="hand-group"
        :class="{ rotating: isRotating, 'no-transition': skipTransition }"
        :style="{ '--hand-deg': `${needleAngle}deg` }"
      >
        <line x1="50" y1="54" x2="50" y2="28" class="hand-line" :stroke="`url(#${handGrad})`" />
        <circle cx="50" cy="54" r="3.2" class="hand-hub" />
        <circle cx="50" cy="28" r="2" class="hand-tip" />
      </g>

      <!-- 中心秒数（0-59，与系统运行时间秒位同步） -->
      <text x="50" y="58" text-anchor="middle" class="sec-label">{{ secInMinute }}</text>
    </svg>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted, onUnmounted, nextTick } from 'vue'

const props = defineProps<{
  uptime?: string | null
  uptimeSeconds?: number | null
}>()

const emit = defineEmits<{
  'update:label': [text: string]
}>()

const uid = Math.random().toString(36).slice(2, 8)
const caseGrad = `swCase-${uid}`
const handGrad = `swHand-${uid}`
const swGlow = `swGlow-${uid}`

const totalSeconds = ref(0)
const anchorSeconds = ref(0)
const anchorTime = ref(0)
const skipTransition = ref(false)
let timer: ReturnType<typeof setInterval> | null = null

function parseChineseUptime(text: string): number {
  if (!text || text === '-' || text === 'N/A') return 0
  let total = 0
  const w = text.match(/(\d+)周/)
  const d = text.match(/(\d+)天/)
  const h = text.match(/(\d+)小时/)
  const m = text.match(/(\d+)分钟/)
  const s = text.match(/(\d+)秒/)
  if (w) total += parseInt(w[1], 10) * 7 * 86400
  if (d) total += parseInt(d[1], 10) * 86400
  if (h) total += parseInt(h[1], 10) * 3600
  if (m) total += parseInt(m[1], 10) * 60
  if (s) total += parseInt(s[1], 10)
  return total
}

function formatChineseUptime(sec: number): string {
  if (sec <= 0) return '-'
  const d = Math.floor(sec / 86400)
  const h = Math.floor((sec % 86400) / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const parts: string[] = []
  if (d) parts.push(`${d}天`)
  if (h) parts.push(`${h}小时`)
  if (m || (!d && !h)) parts.push(`${m}分钟`)
  return parts.join(' ') || '0分钟'
}

function currentTotalSeconds(): number {
  if (anchorTime.value <= 0) return totalSeconds.value
  return anchorSeconds.value + Math.floor((Date.now() - anchorTime.value) / 1000)
}

function reanchor(serverSeconds: number) {
  anchorSeconds.value = Math.max(0, serverSeconds)
  anchorTime.value = Date.now()
  totalSeconds.value = anchorSeconds.value
}

const isActive = computed(() => totalSeconds.value > 0)

const secInMinute = computed(() => totalSeconds.value % 60)

const isRotating = computed(() => secInMinute.value > 0)

const needleAngle = computed(() => (secInMinute.value / 60) * 360)

watch(secInMinute, (cur, prev) => {
  if (cur === 0 && prev === 59) {
    skipTransition.value = true
    nextTick(() => {
      requestAnimationFrame(() => { skipTransition.value = false })
    })
  }
})

const liveLabel = computed(() => formatChineseUptime(totalSeconds.value))

const tickMarks = computed(() => {
  const cx = 50
  const cy = 54
  const rOuter = 30
  const rInnerMajor = 24
  const rInnerMinor = 26
  const marks = []
  for (let i = 0; i < 60; i++) {
    const angle = ((i / 60) * 360 - 90) * (Math.PI / 180)
    const major = i % 5 === 0
    const rInner = major ? rInnerMajor : rInnerMinor
    marks.push({
      x1: cx + Math.cos(angle) * rInner,
      y1: cy + Math.sin(angle) * rInner,
      x2: cx + Math.cos(angle) * rOuter,
      y2: cy + Math.sin(angle) * rOuter,
      major,
    })
  }
  return marks
})

const sweepArc = computed(() => {
  const cx = 50
  const cy = 54
  const r = 27
  const angle = needleAngle.value
  if (angle <= 0) return ''
  const rad = ((angle - 90) * Math.PI) / 180
  const x = cx + Math.cos(rad) * r
  const y = cy + Math.sin(rad) * r
  const large = angle > 180 ? 1 : 0
  return `M ${cx} ${cy - r} A ${r} ${r} 0 ${large} 1 ${x} ${y} L ${cx} ${cy} Z`
})

function syncFromProp() {
  if (props.uptimeSeconds != null && props.uptimeSeconds >= 0) {
    const serverSec = Math.floor(props.uptimeSeconds)
    const drift = Math.abs(serverSec - currentTotalSeconds())
    if (anchorTime.value <= 0 || drift > 2) {
      reanchor(serverSec)
    }
  } else {
    const parsed = parseChineseUptime(props.uptime || '')
    if (parsed > 0 && (anchorTime.value <= 0 || Math.abs(parsed - currentTotalSeconds()) > 2)) {
      reanchor(parsed)
    }
  }
  emit('update:label', liveLabel.value)
}

function tick() {
  if (anchorTime.value > 0) {
    totalSeconds.value = currentTotalSeconds()
  } else if (totalSeconds.value > 0 || (props.uptime && props.uptime !== '-' && props.uptime !== 'N/A')) {
    totalSeconds.value++
  }
  emit('update:label', liveLabel.value)
}

watch(() => props.uptimeSeconds, syncFromProp)
watch(() => props.uptime, syncFromProp)
watch(liveLabel, (v) => emit('update:label', v))

onMounted(() => {
  syncFromProp()
  timer = setInterval(tick, 1000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style lang="scss" scoped>
.sys-stopwatch {
  position: relative;
  width: 100px;
  height: 100px;
  margin: 0 auto 4px;
}

.sw-svg {
  width: 100%;
  height: 100%;
  display: block;
}

.crown-btn { fill: #a5b4fc; stroke: #818cf8; stroke-width: 0.5; }
.crown-base { fill: #c7d2fe; stroke: #a5b4fc; stroke-width: 0.4; }
.side-btn { fill: #c7d2fe; stroke: #a5b4fc; stroke-width: 0.4; }

.case-body { stroke: none; }
.case-ring {
  fill: none;
  stroke: rgba(99, 102, 241, 0.42);
  stroke-width: 1.4;
}

.ticks line {
  stroke: rgba(99, 102, 241, 0.28);
  stroke-width: 0.6;
  stroke-linecap: round;
  &.major {
    stroke: rgba(99, 102, 241, 0.55);
    stroke-width: 1.1;
  }
}

.sweep-trail {
  fill: rgba(99, 102, 241, 0.1);
  transition: d 1s linear;
}

.hand-group {
  transform: rotate(var(--hand-deg, 0deg));
  transform-origin: 50px 54px;
  transition: transform 1s linear;

  &.no-transition {
    transition: none;
  }
}

.hand-line {
  stroke-width: 2;
  stroke-linecap: round;
}

.hand-hub,
.hand-tip {
  transition: none;
  opacity: 1;
  visibility: visible;
}

.hand-group.rotating .hand-hub,
.hand-group.rotating .hand-tip {
  opacity: 0;
  visibility: hidden;
}

.hand-hub {
  fill: #4f46e5;
  stroke: #fff;
  stroke-width: 0.8;
}

.hand-tip {
  fill: #f43f5e;
  filter: drop-shadow(0 0 2px rgba(244, 63, 94, 0.6));
}

.sec-label {
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 7px;
  font-weight: 700;
  fill: #6366f1;
  pointer-events: none;
}

</style>
