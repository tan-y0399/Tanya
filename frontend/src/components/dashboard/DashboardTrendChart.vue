<template>
  <div class="trend-panel glass-panel">
    <div class="panel-head">
      <div class="head-left">
        <h3 class="panel-title">资源趋势分析</h3>
        <span class="live-tag">LIVE</span>
        <span class="window-tag">近 20 分钟</span>
      </div>
      <div class="head-right">
        <span class="sys-clock">{{ systemTime }}</span>
        <span class="range-tag">{{ rangeLabel }}</span>
      </div>
    </div>

    <div class="legend-row">
      <div
        v-for="item in legendItems"
        :key="item.key"
        class="legend-item"
        :class="[item.key, { peak: item.isPeak }]"
      >
        <span class="dot" :style="{ background: item.color }"></span>
        <span class="name">{{ item.name }}</span>
        <span class="val" :style="{ color: item.color }">{{ item.current }}%</span>
      </div>
    </div>

    <div v-if="!hasHistory" class="chart-empty">
      <span class="empty-text">正在同步系统指标，趋势数据加载中…</span>
    </div>
    <v-chart v-else :option="chartOption" autoresize class="chart-body" />
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

const cpuHistory = computed(() => props.mdata.cpu?.history || [])
const memHistory = computed(() => props.mdata.memory?.history || [])
const diskHistory = computed(() => props.mdata.disk?.history || [])

const hasHistory = computed(() => cpuHistory.value.length > 0)

const pointCount = computed(() => cpuHistory.value.length)

const rangeLabel = computed(() => {
  if (!pointCount.value) return '等待数据'
  const first = cpuHistory.value[0]?.time
  const last = cpuHistory.value[cpuHistory.value.length - 1]?.time
  if (first && last) return `${first} — ${last}`
  return `${pointCount.value} 个采样点`
})

const legendItems = computed(() => {
  const currents = {
    cpu: props.mdata.cpu?.current ?? '-',
    memory: props.mdata.memory?.current ?? '-',
    disk: props.mdata.disk?.current ?? '-',
  }
  const values = [
    Number(currents.cpu) || 0,
    Number(currents.memory) || 0,
    Number(currents.disk) || 0,
  ]
  const maxVal = Math.max(...values)

  return SERIES_META.map((s, i) => ({
    key: s.key,
    name: s.name,
    color: s.color,
    current: currents[s.field],
    isPeak: values[i] === maxVal && maxVal > 0,
  }))
})

function alignSeries(history: { time: string; value: number }[], len: number) {
  const arr = history.map(d => d.value)
  while (arr.length < len) arr.unshift(null as unknown as number)
  return arr.slice(-len)
}

const chartOption = computed(() => {
  const labels = cpuHistory.value.map(d => d.time)
  const len = labels.length
  const labelStep = Math.max(1, Math.floor(len / 8))

  const series = SERIES_META.map(s => {
    const raw = s.field === 'cpu' ? cpuHistory.value
      : s.field === 'memory' ? memHistory.value
        : diskHistory.value
  return {
    name: s.name,
    type: 'line' as const,
    smooth: true,
    symbol: 'circle',
    symbolSize: 5,
    showSymbol: len <= 24,
    lineStyle: { color: s.color, width: 2.5, shadowColor: s.color + '50', shadowBlur: 6 },
    itemStyle: { color: '#fff', borderColor: s.color, borderWidth: 2 },
    areaStyle: {
      color: {
        type: 'linear' as const,
        x: 0, y: 0, x2: 0, y2: 1,
        colorStops: [
          { offset: 0, color: s.color + '30' },
          { offset: 1, color: s.color + '04' },
        ],
      },
    },
    data: alignSeries(raw, len),
    emphasis: { focus: 'series' as const },
  }
  })

  return {
    animation: true,
    animationDuration: 400,
    animationDurationUpdate: 600,
    grid: { top: 12, right: 20, bottom: 28, left: 44 },
    xAxis: {
      type: 'category',
      data: labels,
      boundaryGap: false,
      axisLabel: {
        fontSize: 10,
        color: '#94a3b8',
        interval: labelStep - 1,
        showMaxLabel: true,
        showMinLabel: true,
      },
      axisLine: { lineStyle: { color: '#e2e8f0' } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      splitNumber: 5,
      axisLabel: { fontSize: 10, color: '#94a3b8', formatter: '{value}%' },
      splitLine: { lineStyle: { color: '#f1f5f9', type: 'dashed' } },
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#fff',
      borderColor: '#e2e8f0',
      borderWidth: 1,
      padding: [10, 14],
      textStyle: { color: '#334155', fontSize: 12 },
      axisPointer: {
        type: 'cross',
        crossStyle: { color: '#cbd5e1' },
        lineStyle: { type: 'dashed', color: '#94a3b8' },
      },
      formatter: (params: any) => {
        const list = Array.isArray(params) ? params : [params]
        const time = list[0]?.axisValue || ''
        let html = `<div style="font-weight:700;margin-bottom:6px;color:#1e293b">${time}</div>`
        list.forEach((p: any) => {
          const v = p.value ?? '-'
          html += `<div style="display:flex;align-items:center;gap:6px;margin:4px 0">`
            + `<span style="width:8px;height:8px;border-radius:50%;background:${p.color}"></span>`
            + `<span style="flex:1;color:#64748b">${p.seriesName}</span>`
            + `<span style="font-weight:700;color:${p.color}">${v}%</span></div>`
        })
        return html
      },
    },
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
  padding: 18px 20px 14px;
  margin-bottom: 14px;
  border-color: rgba(186, 230, 253, 0.65) !important;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.head-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.panel-title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: #1e293b;
}

.live-tag {
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #ef4444;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.25);
  animation: live-blink 2s ease-in-out infinite;
}

.window-tag {
  font-size: 10px;
  font-weight: 600;
  color: #64748b;
  padding: 2px 8px;
  border-radius: 999px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.head-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.sys-clock {
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 12px;
  font-weight: 700;
  color: #0891b2;
  padding: 4px 10px;
  border-radius: 8px;
  background: rgba(6, 182, 212, 0.08);
  border: 1px solid rgba(6, 182, 212, 0.25);
  font-variant-numeric: tabular-nums;
}

.range-tag {
  font-size: 11px;
  color: #94a3b8;
  padding: 4px 10px;
  border-radius: 8px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  font-variant-numeric: tabular-nums;
}

.legend-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 10px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  border-radius: 10px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  transition: border-color 0.2s, box-shadow 0.2s;

  &.peak {
    border-color: rgba(99, 102, 241, 0.35);
    box-shadow: 0 2px 10px rgba(99, 102, 241, 0.1);
  }
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.name {
  font-size: 12px;
  color: #64748b;
  font-weight: 500;
}

.val {
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 14px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.chart-body {
  height: 260px;
  width: 100%;
}

.chart-empty {
  height: 260px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px dashed #e2e8f0;
  border-radius: 12px;
  background: linear-gradient(180deg, #fafbfc 0%, #f8fafc 100%);
}

.empty-text {
  font-size: 13px;
  color: #94a3b8;
}

@keyframes live-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.55; }
}
</style>
