<template>
  <DashboardTrendChart :mdata="mdata" />
</template>

<script setup lang="ts">
import DashboardTrendChart from './DashboardTrendChart.vue'

defineProps<{ mdata: Record<string, any> }>()
</script>
