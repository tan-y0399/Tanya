<template>
  <div class="sector-chart" :class="phase">
    <svg viewBox="0 0 260 260" class="sector-svg" aria-hidden="true">
      <defs>
        <filter id="sectorGlow" x="-20%" y="-20%" width="140%" height="140%">
          <feDropShadow dx="0" dy="1" stdDeviation="2" flood-opacity="0.15" />
        </filter>
      </defs>

      <g class="ring-group" :class="{ spinning: phase === 'spinning' }" filter="url(#sectorGlow)">
        <path
          v-for="seg in sectors"
          :key="seg.key"
          :d="seg.path"
          class="sector-slice"
          :class="{ running: seg.running, stopped: !seg.running }"
          :fill="seg.running ? seg.color : 'transparent'"
          :stroke="seg.color"
          stroke-width="2.5"
          stroke-linejoin="round"
        />
      </g>

      <g class="callout-layer">
        <g
          v-for="c in callouts"
          :key="c.key"
          class="callout"
          :class="[phase, { stopped: !c.running }]"
        >
          <polyline
            :points="c.linePoints"
            class="callout-line"
            :stroke="c.color"
            fill="none"
            stroke-width="1.5"
            stroke-linecap="round"
            stroke-linejoin="round"
            :pathLength="100"
          />
          <foreignObject
            :x="c.labelX"
            :y="c.labelY"
            :width="c.labelW"
            :height="c.labelH"
            class="callout-label-box"
          >
            <div class="label-inner" xmlns="http://www.w3.org/1999/xhtml">
              <div class="label-name" :style="{ color: c.color }">{{ c.name }}</div>
              <div class="label-row" v-if="c.port">端口 {{ c.port }}</div>
              <div class="label-row">
                <span class="status-pill" :class="c.running ? 'on' : 'off'">
                  {{ c.running ? 'RUNNING' : 'STOPPED' }}
                </span>
              </div>
              <div class="label-row time" v-if="c.time">{{ c.time }}</div>
            </div>
          </foreignObject>
        </g>
      </g>

      <circle :cx="CX" :cy="CY" r="22" class="center-hole" />
      <text :x="CX" :y="CY - 2" text-anchor="middle" class="center-count">{{ upCount }}/{{ total }}</text>
      <text :x="CX" :y="CY + 10" text-anchor="middle" class="center-sub">ONLINE</text>
    </svg>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'

interface SvcItem {
  name: string
  port?: string
  status?: string
  uptime?: string
}

const props = defineProps<{
  services: SvcItem[]
  scanning?: boolean
}>()

const CX = 130
const CY = 130
const R_OUT = 52
const R_IN = 30
const GAP = 4

const SECTOR_META = [
  { key: 'pg', color: '#3b82f6' },
  { key: 'nginx', color: '#10b981' },
  { key: 'backend', color: '#6366f1' },
  { key: 'redis', color: '#f59e0b' },
]

const phase = ref<'idle' | 'spinning' | 'lines' | 'text'>('idle')
let seqTimer = 0

function polar(cx: number, cy: number, r: number, deg: number) {
  const rad = (deg * Math.PI) / 180
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) }
}

function sectorPath(cx: number, cy: number, rIn: number, rOut: number, startDeg: number, endDeg: number) {
  const s = startDeg + GAP / 2
  const e = endDeg - GAP / 2
  const p1 = polar(cx, cy, rOut, s)
  const p2 = polar(cx, cy, rOut, e)
  const p3 = polar(cx, cy, rIn, e)
  const p4 = polar(cx, cy, rIn, s)
  const large = e - s > 180 ? 1 : 0
  return `M ${p1.x} ${p1.y} A ${rOut} ${rOut} 0 ${large} 1 ${p2.x} ${p2.y} L ${p3.x} ${p3.y} A ${rIn} ${rIn} 0 ${large} 0 ${p4.x} ${p4.y} Z`
}

const normalizedServices = computed(() => {
  const list = props.services?.length ? props.services : []
  return list.slice(0, 4)
})

const upCount = computed(() =>
  normalizedServices.value.filter(s => s.status === 'running').length,
)
const total = computed(() => Math.max(normalizedServices.value.length, 4))

const sectors = computed(() => {
  const n = 4
  return SECTOR_META.map((meta, i) => {
    const svc = normalizedServices.value[i]
    const start = i * (360 / n) - 90
    const end = (i + 1) * (360 / n) - 90
    const running = svc?.status === 'running'
    return {
      key: meta.key,
      color: meta.color,
      running,
      path: sectorPath(CX, CY, R_IN, R_OUT, start, end),
    }
  })
})

const callouts = computed(() => {
  const n = 4
  const layouts = [
    { elbow: 70, lx: 152, ly: 14, lw: 100, lh: 56, right: true },
    { elbow: 70, lx: 152, ly: 190, lw: 100, lh: 56, right: true },
    { elbow: 70, lx: 8, ly: 190, lw: 100, lh: 56, right: false },
    { elbow: 70, lx: 8, ly: 14, lw: 100, lh: 56, right: false },
  ]

  return SECTOR_META.map((meta, i) => {
    const svc = normalizedServices.value[i]
    const mid = i * (360 / n) - 90 + 45
    const edge = polar(CX, CY, R_OUT + 3, mid)
    const elbow = polar(CX, CY, layouts[i].elbow, mid)
    const layout = layouts[i]
    const endX = layout.right ? layout.lx + 6 : layout.lx + layout.lw - 6
    const endY = layout.ly + layout.lh / 2
    const linePoints = `${edge.x},${edge.y} ${elbow.x},${elbow.y} ${endX},${endY}`

    const port = svc?.port && svc.port !== 'N/A' ? `:${svc.port}` : ''
    const time = svc?.uptime && svc.uptime !== 'N/A' ? svc.uptime : ''

    return {
      key: meta.key,
      name: svc?.name || '—',
      port,
      time,
      color: meta.color,
      running: svc?.status === 'running',
      linePoints,
      labelX: layout.lx,
      labelY: layout.ly,
      labelW: layout.lw,
      labelH: layout.lh,
    }
  })
})

function clearSeq() {
  window.clearTimeout(seqTimer)
}

function runSequence() {
  if (phase.value === 'spinning') return
  clearSeq()
  phase.value = 'spinning'
  seqTimer = window.setTimeout(() => {
    phase.value = 'lines'
    seqTimer = window.setTimeout(() => {
      phase.value = 'text'
      seqTimer = window.setTimeout(() => {
        phase.value = 'idle'
      }, 350)
    }, 450)
  }, 1100)
}

watch(() => props.scanning, (v) => { if (v) runSequence() })

let mounted = false
watch(
  () => props.services,
  () => {
    if (!normalizedServices.value.length) return
    if (!mounted && normalizedServices.value.length) {
      mounted = true
      phase.value = 'text'
      seqTimer = window.setTimeout(() => { phase.value = 'idle' }, 400)
    }
  },
  { deep: true },
)
</script>

<style lang="scss" scoped>
.sector-chart {
  width: 100%;
  max-width: 320px;
  margin: 0 auto;
}

.sector-svg {
  width: 100%;
  height: auto;
  display: block;
}

.ring-group {
  transform-origin: 130px 130px;
  transform-box: view-box;

  &.spinning {
    animation: sector-spin 1.1s cubic-bezier(0.45, 0.05, 0.2, 1) forwards;
  }
}

.sector-slice {
  transition: fill 0.45s ease, opacity 0.35s;

  &.running {
    opacity: 0.92;
    filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.08));
  }

  &.stopped {
    opacity: 0.55;
    stroke-dasharray: 4 3;
  }
}

.center-hole {
  fill: #fff;
  stroke: #e2e8f0;
  stroke-width: 1;
}

.center-count {
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 13px;
  font-weight: 700;
  fill: #1e293b;
}

.center-sub {
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 7px;
  font-weight: 700;
  letter-spacing: 0.1em;
  fill: #94a3b8;
}

.callout-line {
  stroke-dasharray: 100;
  stroke-dashoffset: 0;
  transition: none;
}

.callout-layer {
  .callout.spinning .callout-line,
  .sector-chart.spinning .callout-line {
    stroke-dashoffset: 100;
    opacity: 0;
  }

  .callout.spinning .callout-label-box,
  .sector-chart.spinning .callout-label-box {
    opacity: 0;
    visibility: hidden;
  }

  .callout.lines .callout-line {
    animation: line-draw 0.45s ease-out forwards;
  }

  .callout.lines .callout-label-box {
    opacity: 0;
    visibility: hidden;
  }

  .callout.text .callout-line {
    stroke-dashoffset: 0;
    opacity: 1;
  }

  .callout.text .callout-label-box {
    animation: label-in 0.35s ease-out forwards;
  }

  .callout.idle .callout-line {
    stroke-dashoffset: 0;
    opacity: 1;
  }

  .callout.idle .callout-label-box {
    opacity: 1;
    visibility: visible;
  }
}

.label-inner {
  padding: 6px 8px;
  background: rgba(255, 255, 255, 0.95);
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.06);
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 10px;
  line-height: 1.35;
  color: #64748b;
}

.label-name {
  font-size: 11px;
  font-weight: 700;
  margin-bottom: 3px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.label-row {
  margin-top: 2px;
}

.status-pill {
  display: inline-block;
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 0.04em;
  padding: 1px 5px;
  border-radius: 4px;
  &.on { color: #047857; background: rgba(16, 185, 129, 0.12); }
  &.off { color: #dc2626; background: rgba(239, 68, 68, 0.1); }
}

.label-row.time {
  font-size: 9px;
  color: #94a3b8;
  font-variant-numeric: tabular-nums;
}

@keyframes sector-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes line-draw {
  from { stroke-dashoffset: 100; opacity: 0; }
  to { stroke-dashoffset: 0; opacity: 1; }
}

@keyframes label-in {
  from { opacity: 0; transform: translateY(4px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
