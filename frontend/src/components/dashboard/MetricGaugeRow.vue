<template>
  <div class="gauge-row">
    <MetricGaugeCard
      channel="cpu"
      channel-label="CPU CHANNEL"
      color="#3b82f6"
      mode="cpu-chip"
      :value="mdata.cpu?.current ?? null"
      :sub-text="`${mdata.cpu?.cores ?? '-'} CORE · LOAD ${mdata.cpu?.load1 ?? '-'}`"
      :glow-active="glowActive"
      :glow-delay="80"
    />
    <MetricGaugeCard
      channel="memory"
      channel-label="MEM CHANNEL"
      color="#10b981"
      mode="mem-sphere"
      :value="mdata.memory?.current ?? null"
      :sub-text="`USED ${mdata.memory?.used_mb ?? '-'} / ${mdata.memory?.total_mb ?? '-'} MB`"
      :glow-active="glowActive"
      :glow-delay="160"
    />
    <MetricGaugeCard
      channel="disk"
      channel-label="DISK CHANNEL"
      color="#f59e0b"
      mode="disk-usb"
      :value="mdata.disk?.current ?? null"
      :sub-text="`${mdata.disk?.size ?? '-'} · USED ${mdata.disk?.used ?? '-'}`"
      :glow-active="glowActive"
      :glow-delay="240"
    />
    <MetricGaugeCard
      channel="system"
      channel-label="SYS CHANNEL"
      color="#6366f1"
      mode="sys-stopwatch"
      :value="stats.systemUptime || '-'"
      :uptime-seconds="stats.systemUptimeSeconds ?? null"
      sub-text=""
      :glow-active="glowActive"
      :glow-delay="320"
    />
  </div>
</template>

<script setup lang="ts">
import MetricGaugeCard from './MetricGaugeCard.vue'

defineProps<{
  mdata: Record<string, any>
  stats: Record<string, any>
  glowActive?: boolean
}>()
</script>

<style lang="scss" scoped>
.gauge-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 14px;

  @media (max-width: 1100px) {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
