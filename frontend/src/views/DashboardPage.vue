<template>
  <div class="dash">
    <div class="dash-top">
      <h2>运维仪表盘</h2>
      <div class="dash-top-right">
        <span class="last-update" v-if="lastUpdate && !loading">更新于 {{ lastUpdate }}</span>
        <button class="refresh-btn" @click="refresh" :disabled="loading">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" :class="{ spinning: loading }"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/></svg>
          刷新
        </button>
        <div class="srv-pick">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="8" height="8" rx="2"/><rect x="14" y="2" width="8" height="8" rx="2"/><rect x="2" y="14" width="8" height="8" rx="2"/><rect x="14" y="14" width="8" height="8" rx="2"/></svg>
          <select v-model="server" @change="refresh">
            <option v-for="s in servers" :key="s.id" :value="s.id">{{ s.name }}</option>
          </select>
          <span class="srv-dot" :class="srvOn ? 'on' : 'off'"></span>
        </div>
      </div>
    </div>

    <!-- 首次加载状态 -->
    <div v-if="loading && isFirstLoad" class="loading-state">
      <div class="loading-spinner"></div>
      <span>正在获取服务器数据...</span>
    </div>

    <!-- SSH 完全离线提示（仅在没有任何数据时显示） -->
    <div v-else-if="isOffline && !hasPartialData" class="offline-banner">
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
        <path d="M9 6v4M9 12.5v.5" stroke="#b45309" stroke-width="1.5" stroke-linecap="round"/>
        <circle cx="9" cy="9" r="7.5" stroke="#b45309" stroke-width="1.5"/>
      </svg>
      <div>
        <strong>无法连接到麒麟服务器 (192.168.163.15)</strong>
        <p>请确认服务器 SSH 服务是否正常运行，或点击「刷新」重试</p>
      </div>
    </div>

    <!-- 数据内容区（有数据就显示，即使是部分数据） -->
    <template v-if="!isFirstLoad || !loading">
    <!-- 快速指标卡片（不需要 ECharts，直接显示） -->
    <div class="quick-metrics">
      <div class="qm-card">
        <span class="qm-label">CPU 使用率</span>
        <span class="qm-val" :style="{color: (mdata.cpu?.current||0)>80?'#ef4444':'#2563eb'}">{{ mdata.cpu?.current ?? '-' }}%</span>
        <span class="qm-sub">{{ mdata.cpu?.cores ?? '-' }} 核 | load {{ mdata.cpu?.load1 ?? '-' }}</span>
      </div>
      <div class="qm-card">
        <span class="qm-label">内存使用率</span>
        <span class="qm-val" :style="{color: (mdata.memory?.current||0)>80?'#ef4444':'#10b981'}">{{ mdata.memory?.current ?? '-' }}%</span>
        <span class="qm-sub">已用 {{ mdata.memory?.used_mb ?? '-' }} / {{ mdata.memory?.total_mb ?? '-' }} MB</span>
      </div>
      <div class="qm-card">
        <span class="qm-label">磁盘使用率</span>
        <span class="qm-val" :style="{color: (mdata.disk?.current||0)>80?'#ef4444':'#f59e0b'}">{{ mdata.disk?.current ?? '-' }}%</span>
        <span class="qm-sub">{{ mdata.disk?.size ?? '-' }} | 已用 {{ mdata.disk?.used ?? '-' }}</span>
      </div>
      <div class="qm-card">
        <span class="qm-label">系统运行</span>
        <span class="qm-val" style="color:#0f172a;font-size:20px">{{ stats.systemUptime || '-' }}</span>
        <span class="qm-sub">服务 {{ stats.mcpToolsOnline ?? 0 }}/{{ stats.mcpToolsTotal ?? 4 }} 在线</span>
      </div>
    </div>

    <!-- ECharts 折线图 -->
    <div class="charts" v-if="hasHistory">
      <div class="chart-card">
        <div class="ch-head"><span class="ch-dot cpu"></span>CPU 历史趋势<span class="live-badge">LIVE</span></div>
        <v-chart :option="cpuOption" autoresize style="height:200px" />
      </div>
      <div class="chart-card">
        <div class="ch-head"><span class="ch-dot mem"></span>内存历史趋势<span class="live-badge">LIVE</span></div>
        <v-chart :option="memOption" autoresize style="height:200px" />
      </div>
      <div class="chart-card">
        <div class="ch-head"><span class="ch-dot disk"></span>磁盘历史趋势<span class="live-badge">LIVE</span></div>
        <v-chart :option="diskOption" autoresize style="height:200px" />
      </div>
    </div>

    <!-- 底部 -->
    <div class="bottom">
      <div class="panel">
        <div class="p-head"><h4>异常事件</h4><span class="badge" v-if="alerts.length">{{ alerts.length }}</span></div>
        <div v-if="alerts.length">
          <div class="a-row" v-for="a in alerts" :key="a.id">
            <span class="a-dot" :class="a.severity"></span>
            <span class="a-title">{{ a.title }}</span>
            <span class="a-time">{{ a.time }}</span>
          </div>
        </div>
        <div class="empty" v-else>暂无异常事件</div>
      </div>
      <div class="panel">
        <div class="p-head"><h4>服务状态</h4><span class="badge green">{{ upCount }}/{{ svcList.length }}</span></div>
        <div class="s-row" v-for="s in svcList" :key="s.name">
          <span class="s-dot" :class="s.status === 'running' ? 'on' : 'off'"></span>
          <span class="s-name">{{ s.name }}</span>
          <span class="s-port" v-if="s.port && s.port !== 'N/A'">:{{ s.port }}</span>
          <span class="s-up" v-if="s.uptime && s.uptime !== 'N/A'">{{ s.uptime }}</span>
        </div>
      </div>
      <div class="panel">
        <div class="p-head"><h4>快捷操作</h4></div>
        <div class="qa">
          <button @click="$router.push('/chat')"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>对话</button>
          <button @click="$router.push('/servers')"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="8" height="8" rx="2"/><rect x="14" y="2" width="8" height="8" rx="2"/><rect x="2" y="14" width="8" height="8" rx="2"/><rect x="14" y="14" width="8" height="8" rx="2"/></svg>服务器</button>
          <button @click="$router.push('/audit')"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>审计</button>
          <button @click="$router.push('/alerts')"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 01-3.46 0"/></svg>告警</button>
        </div>
      </div>
    </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import api from '@/api/index'
import { getServers, type ServerInfo } from '@/api/servers'

use([LineChart, GridComponent, TooltipComponent, CanvasRenderer])

const loading = ref(true)
const isFirstLoad = ref(true)
const lastUpdate = ref('')
const stats = ref<Record<string, any>>({})
const mdata = ref<Record<string, any>>({})
const alerts = ref<any[]>([])
const svcList = ref<any[]>([])
const servers = ref<ServerInfo[]>([])
const server = ref('')
let timer: any = null

const srvOn = computed(() => servers.value.find(x => x.id === server.value)?.status === 'online')
const upCount = computed(() => svcList.value.filter((s: any) => s.status === 'running').length)
const hasHistory = computed(() => (mdata.value.cpu?.history?.length || 0) > 0)
const hasPartialData = computed(() => {
  return (mdata.value.cpu?.current !== undefined) ||
         (mdata.value.memory?.current !== undefined) ||
         (mdata.value.disk?.current !== undefined)
})
const isOffline = computed(() => {
  if (loading.value) return false
  return !hasPartialData.value
})

async function refresh() {
  loading.value = true
  try {
    const res = await api.get('/dashboard/overview', { params: { server_id: server.value || undefined } })
    const payload: any = res.data
    if (payload && payload.data) {
      stats.value = payload.data.stats || {}
      mdata.value = payload.data.metrics || {}
      alerts.value = payload.data.anomalies || []
      svcList.value = payload.data.services || []
      const now = new Date()
      lastUpdate.value = now.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    }
  } catch (e) {
    // 请求失败时保留上次数据，不清空
  } finally {
    loading.value = false
    isFirstLoad.value = false
  }
}

const cards = computed(() => {
  const s = stats.value
  return [
    { label: '今日操作', val: s.todayOperations ?? 0,
      bg: 'linear-gradient(135deg,#eff6ff,#dbeafe)',
      icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#2563eb" stroke-width="2"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>' },
    { label: '总操作数', val: s.totalOperations ?? 0,
      bg: 'linear-gradient(135deg,#f0fdf4,#dcfce7)',
      icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#16a34a" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>' },
    { label: '待审批', val: s.pendingApprovals ?? 0,
      bg: 'linear-gradient(135deg,#fffbeb,#fef3c7)',
      icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#d97706" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="12" x2="16" y2="12"/></svg>' },
    { label: '服务在线', val: (s.mcpToolsOnline ?? 0) + '/' + (s.mcpToolsTotal ?? 4),
      bg: 'linear-gradient(135deg,#f5f3ff,#ede9fe)',
      icon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#7c3aed" stroke-width="2"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>' },
  ]
})

function makeOption(history: any[], color: string) {
  const labels = history.map((d: any) => d.time)
  const values = history.map((d: any) => d.value)
  // 每 6 个点显示一个标签，避免过于拥挤
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
        fontSize: 10, color: '#94a3b8',
        interval: labelStep - 1,
        showMaxLabel: true,
        showMinLabel: true,
      },
      axisLine: { lineStyle: { color: '#e2e8f0' } },
      axisTick: { show: false },
    },
    yAxis: {
      type: 'value', max: 100, min: 0,
      axisLabel: { fontSize: 10, color: '#94a3b8' },
      splitLine: { lineStyle: { color: '#f1f5f9', type: 'dashed' } },
    },
    series: [{
      data: values,
      type: 'line', smooth: true, symbol: 'none',
      lineStyle: { color, width: 2.5 },
      areaStyle: {
        color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [{ offset: 0, color: color + '30' }, { offset: 1, color: color + '05' }],
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

const cpuOption = computed(() => makeOption(mdata.value.cpu?.history || [], '#2563eb'))
const memOption = computed(() => makeOption(mdata.value.memory?.history || [], '#10b981'))
const diskOption = computed(() => makeOption(mdata.value.disk?.history || [], '#f59e0b'))

onMounted(async () => {
  try {
    const srvData = await getServers()
    servers.value = srvData?.items || []
    if (servers.value.length > 0) {
      const d = servers.value.find(s => s.isDefault)
      server.value = d ? d.id : servers.value[0].id
    }
  } catch { /* ignore */ }
  await refresh()
  timer = setInterval(refresh, 10000)
})

onUnmounted(() => { clearInterval(timer) })
</script>

<style lang="scss" scoped>
.dash { width: 100%; min-width: 0; margin: 0 auto; }
.dash-top {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px;
  h2 { margin: 0; font-size: 22px; font-weight: 700; color: #0f172a; }
}
.dash-top-right {
  display: flex; align-items: center; gap: 10px;
}
.last-update {
  font-size: 11px; color: #94a3b8;
}
.refresh-btn {
  display: flex; align-items: center; gap: 5px;
  padding: 6px 12px; border: 1px solid #e2e8f0; border-radius: 8px;
  background: #fff; cursor: pointer; font-family: inherit; font-size: 12px;
  color: #475569; transition: all .15s;
  &:hover:not(:disabled) { background: #f1f5f9; border-color: #cbd5e1; }
  &:disabled { opacity: 0.6; cursor: not-allowed; }
  .spinning { animation: spin 0.8s linear infinite; }
}
.srv-pick {
  display: flex; align-items: center; gap: 8px;
  padding: 7px 14px; background: #fff; border: 1px solid #e2e8f0; border-radius: 10px;
  svg { color: #94a3b8; }
  select { border: none; outline: none; background: none; font-size: 13px; color: #0f172a; cursor: pointer; font-family: inherit; min-width: 150px; }
}
.srv-dot { width: 7px; height: 7px; border-radius: 50%;
  &.on { background: #10b981; box-shadow: 0 0 6px rgba(16,185,129,.4); }
  &.off { background: #ef4444; }
}

.quick-metrics { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }
.qm-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 14px; padding: 18px 20px; text-align: center; }
.qm-label { font-size: 12px; color: #94a3b8; display: block; margin-bottom: 6px; }
.qm-val { font-size: 28px; font-weight: 700; }
.qm-sub { font-size: 12px; color: #94a3b8; display: block; margin-top: 4px; }

.charts { display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 16px; }
.chart-card { background: #fff; border: 1px solid #e2e8f0; border-radius: 14px; padding: 16px 20px; }
.ch-head { display: flex; align-items: center; gap: 8px; font-size: 13px; font-weight: 600; color: #475569; margin-bottom: 4px; }
.ch-dot { width: 8px; height: 8px; border-radius: 50%;
  &.cpu { background: #2563eb; } &.mem { background: #10b981; } &.disk { background: #f59e0b; }
}
.live-badge {
  margin-left: auto;
  font-size: 10px; font-weight: 700; color: #ef4444;
  padding: 2px 6px; border-radius: 4px;
  background: #fef2f2; border: 1px solid #fecaca;
  animation: live-pulse 2s ease-in-out infinite;
}
@keyframes live-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.bottom { display: grid; grid-template-columns: 2fr 2fr 1fr; gap: 14px; }
.panel { background: #fff; border: 1px solid #e2e8f0; border-radius: 14px; padding: 18px 20px; }
.p-head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;
  h4 { margin: 0; font-size: 14px; font-weight: 600; color: #334155; }
}
.badge { font-size: 11px; padding: 2px 8px; border-radius: 100px; background: #fef2f2; color: #ef4444; font-weight: 600;
  &.green { background: #f0fdf4; color: #16a34a; }
}

.a-row { display: flex; align-items: center; gap: 8px; padding: 8px 0; border-bottom: 1px solid #f8fafc;
  &:last-child { border-bottom: none; }
  .a-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0;
    &.critical { background: #ef4444; } &.warning { background: #f59e0b; } &.info { background: #3b82f6; }
  }
  .a-title { flex: 1; font-size: 13px; color: #1e293b; }
  .a-time { font-size: 11px; color: #94a3b8; }
}

.s-row { display: flex; align-items: center; gap: 8px; padding: 8px 0; border-bottom: 1px solid #f8fafc;
  &:last-child { border-bottom: none; }
  .s-dot { width: 7px; height: 7px; border-radius: 50%;
    &.on { background: #10b981; } &.off { background: #ef4444; }
  }
  .s-name { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #1e293b; flex: 1; }
  .s-port { font-size: 11px; color: #94a3b8; }
  .s-up { font-size: 11px; color: #94a3b8; margin-left: auto; }
}

.qa { display: grid; grid-template-columns: 1fr 1fr; gap: 8px;
  button {
    display: flex; align-items: center; gap: 8px; justify-content: center;
    padding: 14px 12px; border: 1px solid #e2e8f0; border-radius: 10px;
    background: #fafbfc; cursor: pointer; font-family: inherit; font-size: 13px; color: #475569;
    transition: all .15s;
    &:hover { background: #f1f5f9; border-color: #cbd5e1; }
    svg { color: #64748b; flex-shrink: 0; }
  }
}

.empty { text-align: center; color: #94a3b8; font-size: 13px; padding: 20px 0; }

.offline-banner {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px 20px;
  margin-bottom: 16px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 10px;
  strong { font-size: 14px; color: #92400e; }
  p { font-size: 12px; color: #a16207; margin: 4px 0 0; }
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px;
  color: #94a3b8;
  font-size: 14px;
  gap: 16px;
}
.loading-spinner {
  width: 36px;
  height: 36px;
  border: 3px solid #e2e8f0;
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
