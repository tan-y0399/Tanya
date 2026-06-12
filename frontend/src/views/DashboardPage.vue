<template>
  <div class="dash-page">
    <DashboardTelemetryBg :pulse-tick="pulseTick" />

    <div class="dash-content">
      <DashboardHeader
        :servers="servers"
        :server-id="server"
        :last-update="lastUpdate"
        :syncing="loading"
        :sync-done="syncDone"
        :offline="isOffline && !hasPartialData"
        @sync="manualSync"
        @update:server-id="onServerChange"
      />

      <DashboardLoadingState
        v-if="loading && isFirstLoad"
        :target-label="targetLabel"
      />

      <DashboardOfflineBanner v-else-if="isOffline && !hasPartialData" />

      <template v-if="!isFirstLoad || !loading">
        <TelemetryStatsBar :stats="stats" />

        <MetricGaugeRow
          :mdata="mdata"
          :stats="stats"
          :glow-active="gaugeGlow"
        />

        <MetricChartRow :mdata="mdata" />

        <div class="bottom-row">
          <ServiceStatusPanel :services="svcList" :scanning="svcScanning" />
          <QuickNavPanel :pulse-tick="pulseTick" :scanning="svcScanning" :servers="servers" />
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import api from '@/api/index'
import { getServers, type ServerInfo } from '@/api/servers'
import DashboardTelemetryBg from '@/components/dashboard/DashboardTelemetryBg.vue'
import DashboardHeader from '@/components/dashboard/DashboardHeader.vue'
import DashboardLoadingState from '@/components/dashboard/DashboardLoadingState.vue'
import DashboardOfflineBanner from '@/components/dashboard/DashboardOfflineBanner.vue'
import TelemetryStatsBar from '@/components/dashboard/TelemetryStatsBar.vue'
import MetricGaugeRow from '@/components/dashboard/MetricGaugeRow.vue'
import MetricChartRow from '@/components/dashboard/MetricChartRow.vue'
import ServiceStatusPanel from '@/components/dashboard/ServiceStatusPanel.vue'
import QuickNavPanel from '@/components/dashboard/QuickNavPanel.vue'

const loading = ref(true)
const isFirstLoad = ref(true)
const lastUpdate = ref('')
const syncDone = ref(false)
const pulseTick = ref(0)
const gaugeGlow = ref(false)
const svcScanning = ref(false)
const stats = ref<Record<string, any>>({})
const mdata = ref<Record<string, any>>({})
const svcList = ref<any[]>([])
const servers = ref<ServerInfo[]>([])
const server = ref('')
let timer: ReturnType<typeof setInterval> | null = null
let glowTimer = 0
let scanTimer = 0
let syncDoneTimer = 0

const targetLabel = computed(() => {
  const s = servers.value.find(x => x.id === server.value)
  return s ? `${s.name} · ${s.host}` : undefined
})

const hasPartialData = computed(() =>
  mdata.value.cpu?.current !== undefined ||
  mdata.value.memory?.current !== undefined ||
  mdata.value.disk?.current !== undefined,
)

const isOffline = computed(() => !loading.value && !hasPartialData.value)

function triggerFx() {
  pulseTick.value++
  gaugeGlow.value = false
  window.clearTimeout(glowTimer)
  requestAnimationFrame(() => {
    gaugeGlow.value = true
    glowTimer = window.setTimeout(() => { gaugeGlow.value = false }, 600)
  })
  svcScanning.value = true
  window.clearTimeout(scanTimer)
  scanTimer = window.setTimeout(() => { svcScanning.value = false }, 800)
}

async function refresh(manual = false): Promise<void> {
  loading.value = true
  if (manual) syncDone.value = false
  try {
    const res = await api.get('/dashboard/overview', {
      params: { server_id: server.value || undefined },
    })
    const payload: any = res.data
    if (payload?.data) {
      stats.value = payload.data.stats || {}
      mdata.value = payload.data.metrics || {}
      svcList.value = payload.data.services || []
      const now = new Date()
      lastUpdate.value = now.toLocaleTimeString('zh-CN', {
        hour: '2-digit', minute: '2-digit', second: '2-digit',
      })
      if (manual) {
        syncDone.value = true
        window.clearTimeout(syncDoneTimer)
        syncDoneTimer = window.setTimeout(() => { syncDone.value = false }, 2500)
      }
    }
  } catch {
    // 保留上次数据
  } finally {
    loading.value = false
    if (!isFirstLoad.value && !manual) {
      svcScanning.value = true
      window.clearTimeout(scanTimer)
      scanTimer = window.setTimeout(() => { svcScanning.value = false }, 800)
    }
    isFirstLoad.value = false
  }
}

function manualSync() {
  triggerFx()
  refresh(true)
}

function onServerChange(id: string) {
  server.value = id
  triggerFx()
  refresh(true)
}

onMounted(async () => {
  try {
    const srvData = await getServers()
    servers.value = srvData?.items || []
    if (servers.value.length > 0) {
      const d = servers.value.find(s => s.isDefault)
      server.value = d ? d.id : servers.value[0].id
    }
  } catch { /* ignore */ }
  await refresh(false)
  timer = setInterval(() => refresh(false), 10000)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
  window.clearTimeout(glowTimer)
  window.clearTimeout(scanTimer)
  window.clearTimeout(syncDoneTimer)
})
</script>

<style lang="scss" scoped>
.dash-page {
  position: relative;
  min-height: 100%;
  overflow-x: hidden;
}

.dash-content {
  position: relative;
  z-index: 1;
  max-width: 1280px;
  margin: 0 auto;
  padding: 24px 32px 40px;
  width: 100%;
  min-width: 0;
}

.bottom-row {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 12px;

  @media (max-width: 900px) {
    grid-template-columns: 1fr;
  }
}
</style>
