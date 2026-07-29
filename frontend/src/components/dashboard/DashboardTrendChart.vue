<template>
  <div class="trend-panel glass-panel">
    <div class="panel-head">
      <div class="head-left">
        <div>
          <h3 class="panel-title">资源趋势分析</h3>
          <p class="panel-subtitle">近 20 分钟 · 10 秒采样</p>
        </div>
        <span class="live-tag"><i></i>实时</span>
      </div>
      <div class="head-right">
        <span class="clock-label">系统时间</span>
        <span class="sys-clock">{{ systemTime }}</span>
      </div>
    </div>

    <div class="metric-summary">
      <button
        v-for="item in legendItems"
        :key="item.key"
        type="button"
        class="metric-item"
        :class="[item.key, `level-${item.level}`, { muted: !item.active }]"
        :aria-pressed="item.active"
        @click="toggleSeries(item.key)"
      >
        <span class="metric-color" :style="{ background: item.color }"></span>
        <span class="metric-copy">
          <span class="metric-name">{{ item.name }}</span>
          <span class="metric-meta">均值 {{ item.average }}% · {{ item.changeLabel }}</span>
        </span>
        <span class="metric-value" :style="{ color: item.color }">{{ item.current }}<small>%</small></span>
        <span class="metric-status">{{ item.status }}</span>
      </button>
    </div>

    <div class="chart-toolbar">
      <span class="range-label">{{ rangeLabel }}</span>
      <div class="scale-switch" aria-label="纵轴显示范围">
        <button type="button" :class="{ active: scaleMode === 'focus' }" @click="scaleMode = 'focus'">聚焦波动</button>
        <button type="button" :class="{ active: scaleMode === 'full' }" @click="scaleMode = 'full'">0–100%</button>
      </div>
    </div>

    <div v-if="!hasHistory" class="chart-empty">
      <span class="empty-text">正在同步系统指标，趋势数据加载中…</span>
    </div>
    <div v-else class="chart-shell">
      <v-chart :option="chartOption" autoresize class="chart-body" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const props = defineProps<{ mdata: Record<string, any> }>()

const SERIES_META = [
  { key: 'cpu', name: 'CPU 利用率', color: '#3b82f6', field: 'cpu' },
  { key: 'memory', name: '内存利用率', color: '#10b981', field: 'memory' },
  { key: 'disk', name: '磁盘利用率', color: '#f59e0b', field: 'disk' },
] as const

const systemTime = ref('')
let clockTimer: ReturnType<typeof setInterval> | null = null

function updateClock() {
  systemTime.value = new Date().toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
}

type MetricKey = 'cpu' | 'memory' | 'disk'
type TrendPoint = { time: string; value: number; ts?: number }

const cpuHistory = computed<TrendPoint[]>(() => props.mdata.cpu?.history || [])
const memHistory = computed<TrendPoint[]>(() => props.mdata.memory?.history || [])
const diskHistory = computed<TrendPoint[]>(() => props.mdata.disk?.history || [])

const histories = computed<Record<MetricKey, TrendPoint[]>>(() => ({
  cpu: cpuHistory.value,
  memory: memHistory.value,
  disk: diskHistory.value,
}))
const hasHistory = computed(() => Object.values(histories.value).some(series => series.length > 0))
const visibleSeries = ref<Set<MetricKey>>(new Set(['cpu', 'memory', 'disk']))
const scaleMode = ref<'focus' | 'full'>('focus')

const timeline = computed(() => {
  const points = new Map<string, number>()
  Object.values(histories.value).flat().forEach((point) => {
    points.set(point.time, Number(point.ts) || points.get(point.time) || 0)
  })
  return [...points.entries()]
    .sort((a, b) => a[1] && b[1] ? a[1] - b[1] : a[0].localeCompare(b[0]))
    .map(([time]) => time)
})

const pointCount = computed(() => timeline.value.length)

const rangeLabel = computed(() => {
  if (!pointCount.value) return '等待数据'
  const first = timeline.value[0]
  const last = timeline.value[timeline.value.length - 1]
  if (first && last) return `${first} — ${last} · ${pointCount.value} 个采样点`
  return `${pointCount.value} 个采样点`
})

function numericValues(history: TrendPoint[]): number[] {
  return history.map(point => Number(point.value)).filter(Number.isFinite)
}

function currentValue(key: MetricKey): number {
  const raw = Number(props.mdata[key]?.current)
  if (Number.isFinite(raw)) return raw
  const values = numericValues(histories.value[key])
  return values[values.length - 1] ?? 0
}

function metricLevel(key: MetricKey, value: number): 'normal' | 'watch' | 'high' {
  const watchAt = key === 'disk' ? 70 : 65
  const highAt = key === 'disk' ? 85 : 80
  if (value >= highAt) return 'high'
  if (value >= watchAt) return 'watch'
  return 'normal'
}

const legendItems = computed(() => {
  return SERIES_META.map((s) => {
    const values = numericValues(histories.value[s.key])
    const current = currentValue(s.key)
    const average = values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : current
    const previous = values.length > 1 ? values[values.length - 2] : current
    const change = current - previous
    const level = metricLevel(s.key, current)
    return {
      key: s.key as MetricKey,
      name: s.name,
      color: s.color,
      current: current.toFixed(1).replace(/\.0$/, ''),
      average: average.toFixed(1),
      changeLabel: Math.abs(change) < 0.05 ? '较上次持平' : `较上次 ${change > 0 ? '+' : ''}${change.toFixed(1)}%`,
      level,
      status: level === 'high' ? '较高' : level === 'watch' ? '关注' : '正常',
      active: visibleSeries.value.has(s.key),
    }
  })
})

function toggleSeries(key: MetricKey) {
  const next = new Set(visibleSeries.value)
  if (next.has(key) && next.size > 1) next.delete(key)
  else next.add(key)
  visibleSeries.value = next
}

function alignSeries(history: TrendPoint[], labels: string[]): Array<number | null> {
  const values = new Map(history.map(point => [point.time, Number(point.value)]))
  return labels.map((label) => {
    const value = values.get(label)
    return Number.isFinite(value) ? Number(value) : null
  })
}

const chartOption = computed(() => {
  const labels = timeline.value
  const len = labels.length
  const labelStep = Math.max(1, Math.floor(len / 8))
  const visibleValues = SERIES_META
    .filter(item => visibleSeries.value.has(item.key))
    .flatMap(item => numericValues(histories.value[item.key]))
  const maxValue = visibleValues.length ? Math.max(...visibleValues) : 100
  const focusMax = Math.min(100, Math.max(50, Math.ceil((maxValue + 7) / 10) * 10))

  const series = SERIES_META.filter(s => visibleSeries.value.has(s.key)).map(s => {
    const raw = histories.value[s.key]
    return {
      name: s.name,
      type: 'line' as const,
      smooth: 0.18,
      connectNulls: false,
      symbol: 'circle',
      symbolSize: 5,
      showSymbol: false,
      lineStyle: { color: s.color, width: 2.4 },
      itemStyle: { color: '#fff', borderColor: s.color, borderWidth: 2 },
      areaStyle: {
        color: {
          type: 'linear' as const,
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: s.color + '1f' },
            { offset: 1, color: s.color + '02' },
          ],
        },
      },
      data: alignSeries(raw, labels),
      z: s.key === 'cpu' ? 4 : s.key === 'memory' ? 3 : 2,
      emphasis: { focus: 'series' as const },
    }
  })

  return {
    animation: true,
    animationDuration: 400,
    animationDurationUpdate: 320,
    grid: { top: 18, right: 24, bottom: 34, left: 52, containLabel: false },
    xAxis: {
      type: 'category',
      data: labels,
      boundaryGap: false,
      axisLabel: {
        fontSize: 11,
        color: '#94a3b8',
        interval: labelStep - 1,
        showMaxLabel: true,
        showMinLabel: true,
      },
      axisLine: { lineStyle: { color: '#dbe3ef' } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: scaleMode.value === 'full' ? 100 : focusMax,
      splitNumber: 5,
      axisLabel: { fontSize: 11, color: '#7c8da6', formatter: '{value}%' },
      splitLine: { lineStyle: { color: '#e8eef6', type: 'dashed' } },
      splitArea: {
        show: true,
        areaStyle: { color: ['rgba(248,250,252,0.45)', 'rgba(255,255,255,0)'] },
      },
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#fff',
      borderColor: '#e2e8f0',
      borderWidth: 1,
      padding: [10, 14],
      textStyle: { color: '#334155', fontSize: 12 },
      axisPointer: {
        type: 'line',
        lineStyle: { type: 'dashed', color: '#7c8da6' },
      },
      formatter: (params: any) => {
        const list = Array.isArray(params) ? params : [params]
        const time = list[0]?.axisValue || ''
        let html = `<div style="font-weight:700;margin-bottom:6px;color:#1e293b">${time}</div>`
        list.forEach((p: any) => {
          const v = typeof p.value === 'number' ? p.value.toFixed(1) : '-'
          html += `<div style="display:flex;align-items:center;gap:6px;margin:4px 0">`
            + `<span style="width:8px;height:8px;border-radius:50%;background:${p.color}"></span>`
            + `<span style="flex:1;color:#64748b">${p.seriesName}</span>`
            + `<span style="font-weight:700;color:${p.color}">${v}%</span></div>`
        })
        return html
      },
    },
    graphic: visibleSeries.value.size ? [] : [{
      type: 'text', left: 'center', top: 'middle',
      style: { text: '请选择至少一项指标', fill: '#94a3b8', fontSize: 13 },
    }],
    series,
  }
})

onMounted(() => {
  updateClock()
  clockTimer = setInterval(updateClock, 1000)
})

onUnmounted(() => {
  if (clockTimer) clearInterval(clockTimer)
})
</script>

<style lang="scss" scoped>
.trend-panel {
  padding: 20px 22px 16px;
  margin-bottom: 14px;
  border-color: rgba(186, 230, 253, 0.65) !important;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.head-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.panel-title {
  margin: 0;
  font-size: 16px;
  font-weight: 700;
  color: #1e293b;
}

.panel-subtitle {
  margin: 3px 0 0;
  color: #94a3b8;
  font-size: 11px;
}

.live-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 9px;
  font-weight: 700;
  color: #059669;
  padding: 4px 8px;
  border-radius: 6px;
  background: #ecfdf5;
  border: 1px solid #a7f3d0;

  i {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #10b981;
    box-shadow: 0 0 0 4px rgba(16, 185, 129, 0.12);
    animation: live-pulse 1.8s ease-in-out infinite;
  }
}

.head-right {
  display: flex;
  align-items: center;
  gap: 7px;
}

.clock-label {
  color: #94a3b8;
  font-size: 10px;
}

.sys-clock {
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 12px;
  font-weight: 700;
  color: #0f172a;
  padding: 5px 9px;
  border-radius: 6px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  font-variant-numeric: tabular-nums;
}

.metric-summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}

.metric-item {
  position: relative;
  display: grid;
  grid-template-columns: 8px minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 10px;
  min-width: 0;
  min-height: 60px;
  padding: 9px 11px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid #e2e8f0;
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.16s ease, background 0.16s ease, box-shadow 0.16s ease, opacity 0.16s ease;

  &:hover {
    border-color: #bfdbfe;
    background: #f8fbff;
    box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06);
  }

  &.muted {
    opacity: 0.5;
    background: #f8fafc;
  }

  &.level-watch .metric-status {
    color: #b45309;
    background: #fffbeb;
  }

  &.level-high .metric-status {
    color: #b91c1c;
    background: #fef2f2;
  }
}

.metric-color {
  width: 8px;
  height: 30px;
  border-radius: 4px;
}

.metric-copy {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.metric-name {
  font-size: 12px;
  color: #334155;
  font-weight: 600;
}

.metric-meta {
  overflow: hidden;
  color: #94a3b8;
  font-size: 10px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.metric-value {
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 19px;
  font-weight: 750;
  font-variant-numeric: tabular-nums;

  small {
    margin-left: 1px;
    font-size: 11px;
    font-weight: 600;
  }
}

.metric-status {
  padding: 3px 6px;
  border-radius: 5px;
  background: #ecfdf5;
  color: #047857;
  font-size: 9px;
  font-weight: 700;
}

.chart-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 32px;
  margin-bottom: 4px;
}

.range-label {
  color: #7c8da6;
  font-size: 10px;
  font-variant-numeric: tabular-nums;
}

.scale-switch {
  display: inline-flex;
  gap: 2px;
  padding: 2px;
  border: 1px solid #e2e8f0;
  border-radius: 7px;
  background: #f8fafc;

  button {
    height: 25px;
    padding: 0 9px;
    border: 0;
    border-radius: 5px;
    background: transparent;
    color: #64748b;
    font-size: 10px;
    cursor: pointer;

    &.active {
      background: #fff;
      color: #2563eb;
      box-shadow: 0 1px 4px rgba(15, 23, 42, 0.1);
    }
  }
}

.chart-shell {
  overflow: hidden;
  border-top: 1px solid #f1f5f9;
}

.chart-body {
  height: 300px;
  width: 100%;
}

.chart-empty {
  height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px dashed #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
}

.empty-text {
  font-size: 13px;
  color: #94a3b8;
}

@keyframes live-pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.65; transform: scale(0.82); }
}

@media (max-width: 900px) {
  .metric-summary { grid-template-columns: 1fr; }
  .chart-body, .chart-empty { height: 270px; }
}

@media (max-width: 560px) {
  .trend-panel { padding: 16px 14px 12px; }
  .panel-head, .chart-toolbar { align-items: flex-start; flex-direction: column; }
  .head-right { width: 100%; justify-content: space-between; }
  .metric-item { grid-template-columns: 7px minmax(0, 1fr) auto; }
  .metric-status { display: none; }
  .scale-switch { align-self: stretch; }
  .scale-switch button { flex: 1; }
}

@media (prefers-reduced-motion: reduce) {
  .live-tag i { animation: none; }
  .metric-item { transition: none; }
}
</style>
