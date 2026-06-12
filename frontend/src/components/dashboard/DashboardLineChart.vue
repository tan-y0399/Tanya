<template>
  <div class="chart-card glass-panel">
    <div class="ch-head">
      <span class="ch-dot" :style="{ background: color }"></span>
      <span class="ch-title">{{ title }}</span>
      <span class="stream-badge">STREAM</span>
    </div>
    <v-chart :option="chartOption" autoresize class="chart-body" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([LineChart, GridComponent, TooltipComponent, CanvasRenderer])

const props = defineProps<{
  title: string
  color: string
  history: { time: string; value: number }[]
}>()

function makeOption(history: { time: string; value: number }[], color: string) {
  const labels = history.map(d => d.time)
  const values = history.map(d => d.value)
  const labelStep = Math.max(1, Math.floor(history.length / 10))

  return {
    animation: true,
    animationDuration: 300,
    animationDurationUpdate: 600,
    animationEasing: 'linear' as const,
    animationEasingUpdate: 'cubicInOut' as const,
    grid: { top: 8, right: 16, bottom: 24, left: 40 },
    xAxis: {
      type: 'category',
      data: labels,
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
      max: 100,
      min: 0,
      axisLabel: { fontSize: 10, color: '#94a3b8' },
      splitLine: { lineStyle: { color: '#f1f5f9', type: 'dashed' } },
    },
    series: [{
      data: values,
      type: 'line',
      smooth: true,
      symbol: 'none',
      lineStyle: { color, width: 2.5, shadowColor: color + '60', shadowBlur: 8 },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: color + '35' },
            { offset: 1, color: color + '05' },
          ],
        },
      },
    }],
    tooltip: {
      trigger: 'axis',
      borderColor: '#e2e8f0',
      backgroundColor: '#fff',
      textStyle: { color: '#334155', fontSize: 12 },
      formatter: (params: any) => {
        const p = Array.isArray(params) ? params[0] : params
        return `${p.axisValue}<br/><span style="color:${color};font-weight:600">${p.value}%</span>`
      },
    },
  }
}

const chartOption = computed(() => makeOption(props.history || [], props.color))
</script>

<style lang="scss" scoped>
.chart-card {
  padding: 16px 18px;
  border-color: rgba(186, 230, 253, 0.65) !important;
}

.ch-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.ch-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.ch-title {
  font-size: 13px;
  font-weight: 600;
  color: #475569;
}

.stream-badge {
  margin-left: auto;
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: #06b6d4;
  padding: 2px 7px;
  border-radius: 4px;
  background: rgba(6, 182, 212, 0.08);
  border: 1px solid rgba(6, 182, 212, 0.3);
  animation: stream-blink 2.5s ease-in-out infinite;
}

.chart-body {
  height: 200px;
  width: 100%;
}

@keyframes stream-blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.55; }
}
</style>
