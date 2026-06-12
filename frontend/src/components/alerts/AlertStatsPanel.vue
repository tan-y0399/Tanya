<template>
  <section class="stats-panel glass-panel" aria-label="告警统计概览">
    <div class="panel-label">STAT · 告警统计</div>
    <div class="stats-grid">
      <button
        v-for="s in stats"
        :key="s.key"
        type="button"
        class="stat-card"
        :class="{ active: activeStatus === s.filter }"
        @click="emit('filter-status', s.filter)"
      >
        <span class="stat-code">{{ s.code }}</span>
        <span class="stat-num" :style="{ color: s.color }">{{ s.value }}</span>
        <span class="stat-lbl">{{ s.label }}</span>
        <span class="stat-hint">{{ s.hint }}</span>
      </button>
    </div>
    <div class="severity-row">
      <span class="sev-label">SEVERITY · 级别分布</span>
      <div class="sev-chips">
        <span class="sev-chip critical"><span class="dot"></span>紧急 {{ severityCounts.critical }}</span>
        <span class="sev-chip warning"><span class="dot"></span>警告 {{ severityCounts.warning }}</span>
        <span class="sev-chip info"><span class="dot"></span>提示 {{ severityCounts.info }}</span>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  alerts: any[]
  activeStatus: string
}>()

const emit = defineEmits<{ 'filter-status': [status: string] }>()

const severityCounts = computed(() => ({
  critical: props.alerts.filter(a => a.severity === 'critical').length,
  warning: props.alerts.filter(a => a.severity === 'warning').length,
  info: props.alerts.filter(a => a.severity === 'info').length,
}))

const stats = computed(() => {
  const all = props.alerts
  return [
    {
      key: 'all',
      code: 'TOT',
      label: '全部告警',
      hint: '点击筛选全部',
      value: all.length,
      color: '#0f172a',
      filter: '',
    },
    {
      key: 'active',
      code: 'ACT',
      label: '进行中',
      hint: '待处理告警',
      value: all.filter(a => a.status === 'active').length,
      color: '#ef4444',
      filter: 'active',
    },
    {
      key: 'ack',
      code: 'ACK',
      label: '已确认',
      hint: '已受理跟进',
      value: all.filter(a => a.status === 'acknowledged').length,
      color: '#f59e0b',
      filter: 'acknowledged',
    },
    {
      key: 'resolved',
      code: 'RES',
      label: '已解决',
      hint: '闭环完成',
      value: all.filter(a => a.status === 'resolved').length,
      color: '#10b981',
      filter: 'resolved',
    },
  ]
})
</script>

<style lang="scss" scoped>
.stats-panel {
  padding: 14px 16px;
  margin-bottom: 14px;
  border-color: rgba(239, 68, 68, 0.12) !important;
}

.panel-label {
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: #94a3b8;
  margin-bottom: 10px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;
  margin-bottom: 12px;

  @media (max-width: 900px) {
    grid-template-columns: repeat(2, 1fr);
  }
}

.stat-card {
  position: relative;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: rgba(255, 255, 255, 0.75);
  text-align: left;
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    border-color: rgba(239, 68, 68, 0.35);
    box-shadow: 0 4px 14px rgba(239, 68, 68, 0.08);
  }

  &.active {
    border-color: #ef4444;
    background: rgba(239, 68, 68, 0.05);
    box-shadow: inset 0 0 0 1px rgba(239, 68, 68, 0.15);
  }
}

.stat-code {
  display: block;
  font-size: 8px;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: #94a3b8;
  margin-bottom: 4px;
}

.stat-num {
  display: block;
  font-size: 26px;
  font-weight: 800;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.stat-lbl {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  font-weight: 600;
  color: #334155;
}

.stat-hint {
  display: block;
  margin-top: 2px;
  font-size: 10px;
  color: #94a3b8;
}

.severity-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding-top: 10px;
  border-top: 1px solid rgba(239, 68, 68, 0.08);
}

.sev-label {
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.06em;
  color: #94a3b8;
}

.sev-chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.sev-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  border: 1px solid transparent;

  .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
  }

  &.critical {
    color: #dc2626;
    background: rgba(239, 68, 68, 0.08);
    border-color: rgba(239, 68, 68, 0.2);
    .dot { background: #ef4444; box-shadow: 0 0 6px rgba(239, 68, 68, 0.5); }
  }

  &.warning {
    color: #b45309;
    background: rgba(245, 158, 11, 0.08);
    border-color: rgba(245, 158, 11, 0.2);
    .dot { background: #f59e0b; }
  }

  &.info {
    color: #2563eb;
    background: rgba(59, 130, 246, 0.08);
    border-color: rgba(59, 130, 246, 0.2);
    .dot { background: #3b82f6; }
  }
}
</style>
