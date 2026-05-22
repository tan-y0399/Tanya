<template>
  <div class="alerts-page">
    <div class="page-header">
      <h2 class="page-title">告警中心</h2>
      <p class="page-desc">实时告警监控 · 根因分析 · 智能处理建议</p>
    </div>

    <!-- 统计 -->
    <div class="stats-row">
      <div class="stat-item" v-for="s in stats" :key="s.label" @click="statusFilter = s.filter; severityFilter = ''">
        <div class="stat-num" :style="{ color: s.color }">{{ s.value }}</div>
        <div class="stat-lbl">{{ s.label }}</div>
      </div>
    </div>

    <!-- 筛选 -->
    <div class="filter-row">
      <div class="filter-group">
        <button class="f-btn" :class="{ active: !severityFilter }" @click="severityFilter = ''">全部级别</button>
        <button class="f-btn critical" :class="{ active: severityFilter === 'critical' }" @click="severityFilter = 'critical'">
          <span class="dot red"></span> 紧急
        </button>
        <button class="f-btn warn" :class="{ active: severityFilter === 'warning' }" @click="severityFilter = 'warning'">
          <span class="dot orange"></span> 警告
        </button>
        <button class="f-btn info" :class="{ active: severityFilter === 'info' }" @click="severityFilter = 'info'">
          <span class="dot blue"></span> 提示
        </button>
      </div>
      <div class="filter-group">
        <button class="f-btn" :class="{ active: !statusFilter }" @click="statusFilter = ''">全部状态</button>
        <button class="f-btn" :class="{ active: statusFilter === 'active' }" @click="statusFilter = 'active'">进行中</button>
        <button class="f-btn" :class="{ active: statusFilter === 'acknowledged' }" @click="statusFilter = 'acknowledged'">已确认</button>
        <button class="f-btn" :class="{ active: statusFilter === 'resolved' }" @click="statusFilter = 'resolved'">已解决</button>
      </div>
    </div>

    <!-- 告警列表 -->
    <div class="alert-list">
      <div class="alert-card" v-for="a in filteredAlerts" :key="a.id" @click="selectedAlert = a">
        <div class="alert-left">
          <span class="severity-bar" :class="a.severity"></span>
          <div class="alert-info">
            <div class="alert-title">
              <span class="severity-badge" :class="a.severity">{{ severityLabel(a.severity) }}</span>
              {{ a.title }}
            </div>
            <div class="alert-detail">{{ a.detail }}</div>
            <div class="alert-meta">
              <span>{{ a.host }}</span>
              <span class="dot-sep"></span>
              <span>{{ a.source }}</span>
              <span class="dot-sep"></span>
              <span>{{ a.time }}</span>
              <span class="dot-sep"></span>
              <span class="status-badge" :class="a.status">{{ statusLabel(a.status) }}</span>
            </div>
          </div>
        </div>
        <div class="alert-right">
          <span class="arrow">&#8250;</span>
        </div>
      </div>
    </div>

    <!-- 详情弹窗 -->
    <teleport to="body">
      <div class="modal-overlay" v-if="selectedAlert" @click.self="selectedAlert = null">
        <div class="modal-card" @click.stop>
          <button class="modal-close" @click="selectedAlert = null">&times;</button>
          <div class="modal-severity" :class="selectedAlert.severity">{{ severityLabel(selectedAlert.severity) }}</div>
          <h3 class="modal-title">{{ selectedAlert.title }}</h3>
          <div class="modal-meta">
            <span>{{ selectedAlert.host }}</span><span>{{ selectedAlert.time }}</span><span>{{ selectedAlert.type }}</span>
          </div>

          <div class="info-block">
            <h4>告警详情</h4>
            <p>{{ selectedAlert.detail }}</p>
          </div>

          <div class="info-block root-cause">
            <h4>根因分析</h4>
            <p>{{ selectedAlert.rootCause }}</p>
          </div>

          <div class="info-block suggestion">
            <h4>处理建议</h4>
            <p>{{ selectedAlert.suggestion }}</p>
          </div>

          <div class="info-block" v-if="Object.keys(selectedAlert.relatedMetrics || {}).length">
            <h4>关联指标</h4>
            <div class="metrics-grid">
              <div class="metric-item" v-for="(val, key) in selectedAlert.relatedMetrics" :key="key">
                <span class="metric-key">{{ key }}</span>
                <span class="metric-val">{{ val }}</span>
              </div>
            </div>
          </div>

          <div class="modal-actions">
            <button class="action-btn primary" v-if="selectedAlert.status === 'active'" @click="selectedAlert.status = 'acknowledged'">确认告警</button>
            <button class="action-btn" v-if="selectedAlert.status !== 'resolved'" @click="selectedAlert.status = 'resolved'">标记已解决</button>
          </div>
        </div>
      </div>
    </teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import api from '@/api/index'

const alerts = ref([] as any[])
const severityFilter = ref('')
const statusFilter = ref('')

const stats = computed(() => {
  const all = alerts.value
  return [
    { label: '全部告警', value: all.length, color: '#1e293b', filter: '' },
    { label: '进行中', value: all.filter(a => a.status === 'active').length, color: '#ef4444', filter: 'active' },
    { label: '已确认', value: all.filter(a => a.status === 'acknowledged').length, color: '#f59e0b', filter: 'acknowledged' },
    { label: '已解决', value: all.filter(a => a.status === 'resolved').length, color: '#10b981', filter: 'resolved' },
  ]
})

const filteredAlerts = computed(() => {
  let list = alerts.value
  if (severityFilter.value) list = list.filter((a: any) => a.severity === severityFilter.value)
  if (statusFilter.value) list = list.filter((a: any) => a.status === statusFilter.value)
  return list
})

const selectedAlert = ref(null as any)

function severityLabel(s: string) {
  const m: any = { critical: '紧急', warning: '警告', info: '提示' }
  return m[s] || s
}
function statusLabel(s: string) {
  const m: any = { active: '进行中', acknowledged: '已确认', resolved: '已解决' }
  return m[s] || s
}

onMounted(async () => {
  try {
    const { data } = await api.get('/alerts/list')
    if (data.code === 0) alerts.value = data.data.items || []
  } catch {}
})
</script>

<style lang="scss" scoped>
.alerts-page { max-width: 1200px; margin: 0 auto; }
.page-header { margin-bottom: 20px; .page-title { font-size: 20px; font-weight: 700; color: #1e293b; } .page-desc { font-size: 13px; color: #94a3b8; } }

.stats-row { display: flex; gap: 12px; margin-bottom: 16px; }
.stat-item {
  padding: 14px 24px; background: #fff; border: 1px solid #e2e8f0; border-radius: 12px;
  text-align: center; cursor: pointer; flex: 1; transition: all 0.15s;
  &:hover { border-color: #2563eb; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }
  .stat-num { font-size: 28px; font-weight: 700; }
  .stat-lbl { font-size: 12px; color: #94a3b8; margin-top: 2px; }
}

.filter-row { display: flex; gap: 16px; margin-bottom: 16px; }
.filter-group { display: flex; gap: 4px; }
.f-btn {
  padding: 6px 14px; border-radius: 20px; border: 1px solid #e2e8f0;
  background: #fff; font-size: 12px; color: #64748b; cursor: pointer;
  display: flex; align-items: center; gap: 4px; transition: all 0.15s;
  &:hover { border-color: #cbd5e1; }
  &.active { background: #eff6ff; border-color: #2563eb; color: #2563eb; font-weight: 500; }
}
.dot { width: 6px; height: 6px; border-radius: 50%; &.red { background: #ef4444; } &.orange { background: #f59e0b; } &.blue { background: #3b82f6; } }

.alert-list { display: flex; flex-direction: column; gap: 8px; }
.alert-card {
  display: flex; align-items: center; background: #fff; border: 1px solid #e2e8f0;
  border-radius: 10px; cursor: pointer; transition: all 0.15s;
  &:hover { border-color: #2563eb; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }
}
.alert-left { display: flex; flex: 1; min-width: 0; }
.severity-bar {
  width: 4px; border-radius: 10px 0 0 10px; flex-shrink: 0;
  &.critical { background: #ef4444; }
  &.warning { background: #f59e0b; }
  &.info { background: #3b82f6; }
}
.alert-info { padding: 14px 16px; flex: 1; min-width: 0; }
.alert-title { font-size: 14px; font-weight: 600; color: #1e293b; display: flex; align-items: center; gap: 8px; }
.severity-badge {
  font-size: 11px; padding: 1px 6px; border-radius: 4px; font-weight: 500;
  &.critical { background: #fef2f2; color: #dc2626; }
  &.warning { background: #fffbeb; color: #b45309; }
  &.info { background: #eff6ff; color: #2563eb; }
}
.alert-detail { font-size: 13px; color: #64748b; margin-top: 4px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.alert-meta { display: flex; align-items: center; gap: 6px; margin-top: 6px; font-size: 11px; color: #94a3b8; }
.dot-sep { width: 3px; height: 3px; border-radius: 50%; background: #cbd5e1; }
.status-badge {
  font-size: 11px; padding: 1px 6px; border-radius: 4px;
  &.active { background: #fef2f2; color: #dc2626; }
  &.acknowledged { background: #fffbeb; color: #b45309; }
  &.resolved { background: #f0fdf4; color: #059669; }
}
.alert-right { padding-right: 16px; .arrow { font-size: 20px; color: #cbd5e1; } }

// Modal
.modal-overlay { position: fixed; inset: 0; background: rgba(15,23,42,0.4); backdrop-filter: blur(4px); z-index: 1000; display: flex; align-items: center; justify-content: center; }
.modal-card { background: #fff; border-radius: 16px; padding: 32px; width: 620px; max-height: 80vh; overflow-y: auto; position: relative; box-shadow: 0 20px 60px rgba(0,0,0,0.12); }
.modal-close { position: absolute; top: 12px; right: 12px; background: none; border: none; font-size: 24px; color: #94a3b8; cursor: pointer; }
.modal-severity { display: inline-block; padding: 2px 10px; border-radius: 4px; font-size: 12px; font-weight: 600; margin-bottom: 8px;
  &.critical { background: #fef2f2; color: #dc2626; } &.warning { background: #fffbeb; color: #b45309; } &.info { background: #eff6ff; color: #2563eb; }
}
.modal-title { font-size: 20px; font-weight: 700; color: #1e293b; margin-bottom: 6px; }
.modal-meta { display: flex; gap: 16px; font-size: 12px; color: #94a3b8; margin-bottom: 20px; }
.info-block { margin-bottom: 16px; h4 { font-size: 13px; font-weight: 600; color: #64748b; margin-bottom: 6px; } p { font-size: 14px; color: #1e293b; line-height: 1.7; white-space: pre-line; } }
.info-block.root-cause { padding: 12px; background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px; h4 { color: #92400e; } p { color: #78350f; } }
.info-block.suggestion { padding: 12px; background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; h4 { color: #1e40af; } p { color: #1e3a5f; } }
.metrics-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.metric-item { padding: 8px 12px; background: #f8fafc; border-radius: 6px; display: flex; justify-content: space-between; align-items: center; .metric-key { font-size: 12px; color: #94a3b8; } .metric-val { font-size: 14px; font-weight: 600; color: #1e293b; } }
.modal-actions { display: flex; gap: 10px; margin-top: 20px; }
.action-btn { padding: 8px 20px; border-radius: 8px; border: 1px solid #e2e8f0; background: #fff; font-size: 13px; cursor: pointer; &.primary { background: #2563eb; color: #fff; border: none; &:hover { background: #3b82f6; } } &:hover { border-color: #2563eb; } }
</style>
