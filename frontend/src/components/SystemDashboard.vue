<template>
  <el-card shadow="never">
    <template #header>
      <div class="panel-header">
        <span>系统看板</span>
        <el-tag type="success">实时概览</el-tag>
      </div>
    </template>

    <div class="dashboard-grid">
      <div class="dashboard-card">
        <div class="dashboard-title">CPU 使用率</div>
        <div class="dashboard-value">32%</div>
      </div>
      <div class="dashboard-card">
        <div class="dashboard-title">内存使用率</div>
        <div class="dashboard-value">58%</div>
      </div>
      <div class="dashboard-card">
        <div class="dashboard-title">磁盘使用率</div>
        <div class="dashboard-value warning">71%</div>
      </div>
    </div>

    <div ref="chartRef" class="chart-box"></div>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import * as echarts from 'echarts'

const chartRef = ref<HTMLDivElement | null>(null)

onMounted(() => {
  if (!chartRef.value) return

  const chart = echarts.init(chartRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    xAxis: { type: 'category', data: ['10:00', '10:05', '10:10', '10:15', '10:20'] },
    yAxis: { type: 'value' },
    series: [
      {
        data: [22, 28, 35, 31, 32],
        type: 'line',
        smooth: true,
        areaStyle: {},
      },
    ],
  })
})
</script>
