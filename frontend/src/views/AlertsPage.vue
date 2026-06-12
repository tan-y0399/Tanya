<template>
  <div class="alerts-page">
    <AlertPageBackground />

    <div class="alerts-content">
      <AlertPageHeader
        :refreshing="loading"
        :last-refresh="lastRefresh"
        @refresh="loadAlerts"
      />

      <AlertStatsPanel
        :alerts="alerts"
        :active-status="statusFilter"
        @filter-status="onStatusFilter"
      />

      <AlertFilterBar
        v-model:severity="severityFilter"
        v-model:status="statusFilter"
        :count="filteredAlerts.length"
      />

      <section class="list-section glass-panel" aria-label="告警列表">
        <div class="list-head">
          <span class="list-label">FEED · 告警流</span>
          <span class="list-hint">点击条目查看根因分析与处理建议</span>
        </div>

        <div v-if="loading && !alerts.length" class="list-empty">
          <span class="empty-spinner"></span>
          <p>正在同步告警数据…</p>
        </div>

        <div v-else-if="!filteredAlerts.length" class="list-empty">
          <p>当前筛选条件下暂无告警</p>
          <button type="button" class="reset-btn" @click="resetFilters">重置筛选</button>
        </div>

        <div v-else class="alert-list">
          <AlertListItem
            v-for="a in filteredAlerts"
            :key="a.id"
            :alert="a"
            @select="selectedAlert = a"
          />
        </div>
      </section>
    </div>

    <AlertDetailModal
      :alert="selectedAlert"
      @close="selectedAlert = null"
      @acknowledge="acknowledgeAlert"
      @resolve="resolveAlert"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import api from '@/api/index'
import AlertPageBackground from '@/components/alerts/AlertPageBackground.vue'
import AlertPageHeader from '@/components/alerts/AlertPageHeader.vue'
import AlertStatsPanel from '@/components/alerts/AlertStatsPanel.vue'
import AlertFilterBar from '@/components/alerts/AlertFilterBar.vue'
import AlertListItem from '@/components/alerts/AlertListItem.vue'
import AlertDetailModal from '@/components/alerts/AlertDetailModal.vue'

const alerts = ref<any[]>([])
const loading = ref(false)
const lastRefresh = ref('')
const severityFilter = ref('')
const statusFilter = ref('')
const selectedAlert = ref<any | null>(null)

const filteredAlerts = computed(() => {
  let list = alerts.value
  if (severityFilter.value) list = list.filter(a => a.severity === severityFilter.value)
  if (statusFilter.value) list = list.filter(a => a.status === statusFilter.value)
  return list
})

function onStatusFilter(status: string) {
  statusFilter.value = status
}

function resetFilters() {
  severityFilter.value = ''
  statusFilter.value = ''
}

async function loadAlerts() {
  loading.value = true
  try {
    const { data } = await api.get('/alerts/list')
    if (data.code === 0) alerts.value = data.data.items || []
    lastRefresh.value = new Date().toLocaleTimeString('zh-CN', {
      hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
    })
    if (selectedAlert.value) {
      selectedAlert.value = alerts.value.find(a => a.id === selectedAlert.value?.id) || null
    }
  } catch {
    /* keep previous data */
  } finally {
    loading.value = false
  }
}

function acknowledgeAlert() {
  if (!selectedAlert.value) return
  selectedAlert.value.status = 'acknowledged'
  const item = alerts.value.find(a => a.id === selectedAlert.value.id)
  if (item) item.status = 'acknowledged'
}

function resolveAlert() {
  if (!selectedAlert.value) return
  selectedAlert.value.status = 'resolved'
  const item = alerts.value.find(a => a.id === selectedAlert.value.id)
  if (item) item.status = 'resolved'
}

onMounted(loadAlerts)
</script>

<style lang="scss" scoped>
.alerts-page {
  position: relative;
  min-height: 100%;
  overflow-x: hidden;
}

.alerts-content {
  position: relative;
  z-index: 1;
  max-width: 1200px;
  margin: 0 auto;
  padding: 24px 32px 40px;
  width: 100%;
  min-width: 0;
}

.list-section {
  padding: 14px 16px 16px;
  border-color: rgba(148, 163, 184, 0.2) !important;
}

.list-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.list-label {
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: #94a3b8;
}

.list-hint {
  font-size: 11px;
  color: #94a3b8;
}

.alert-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.list-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 180px;
  color: #94a3b8;
  font-size: 13px;
}

.empty-spinner {
  width: 28px;
  height: 28px;
  border: 2px solid #e2e8f0;
  border-top-color: #ef4444;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

.reset-btn {
  padding: 6px 14px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #fff;
  font-size: 12px;
  color: #64748b;
  cursor: pointer;

  &:hover {
    border-color: #ef4444;
    color: #dc2626;
  }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
