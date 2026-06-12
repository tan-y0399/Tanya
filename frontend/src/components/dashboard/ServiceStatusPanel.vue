<template>
  <div class="service-panel glass-panel">
    <div class="panel-head">
      <div class="head-left">
        <span class="panel-tag">SVC</span>
        <h4>服务状态</h4>
      </div>
      <span class="health-badge" :class="allUp ? 'ok' : 'warn'">
        {{ upCount }}/{{ services.length }} RUNNING
      </span>
    </div>

    <ServiceSectorChart :services="services" :scanning="scanning" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import ServiceSectorChart from './ServiceSectorChart.vue'

const props = defineProps<{
  services: any[]
  scanning?: boolean
}>()

const upCount = computed(() => props.services.filter(s => s.status === 'running').length)
const allUp = computed(() => props.services.length > 0 && upCount.value === props.services.length)
</script>

<style lang="scss" scoped>
.service-panel {
  padding: 18px 16px 14px;
  border-color: rgba(186, 230, 253, 0.65) !important;
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.head-left {
  display: flex;
  align-items: center;
  gap: 8px;
  h4 { margin: 0; font-size: 14px; font-weight: 600; color: #334155; }
}

.panel-tag {
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: #6366f1;
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid rgba(99, 102, 241, 0.2);
}

.health-badge {
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.04em;
  padding: 3px 10px;
  border-radius: 999px;
  &.ok { background: rgba(16, 185, 129, 0.1); color: #047857; border: 1px solid rgba(16, 185, 129, 0.3); }
  &.warn { background: rgba(239, 68, 68, 0.08); color: #dc2626; border: 1px solid rgba(239, 68, 68, 0.25); }
}
</style>
