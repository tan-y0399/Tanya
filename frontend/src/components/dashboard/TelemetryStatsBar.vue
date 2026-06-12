<template>
  <div class="stats-bar glass-panel">
    <div class="stat-item">
      <span class="stat-label">今日操作</span>
      <span class="stat-val">{{ stats.todayOperations ?? 0 }}</span>
    </div>
    <div class="stat-div"></div>
    <div class="stat-item">
      <span class="stat-label">总操作</span>
      <span class="stat-val">{{ stats.totalOperations ?? 0 }}</span>
    </div>
    <div class="stat-div"></div>
    <div class="stat-item" :class="{ warn: (stats.pendingApprovals ?? 0) > 0 }">
      <span class="stat-label">待审批</span>
      <span class="stat-val">{{ stats.pendingApprovals ?? 0 }}</span>
    </div>
    <div class="stat-div"></div>
    <div class="stat-item">
      <span class="stat-label">采集间隔</span>
      <span class="stat-val muted">10s</span>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{ stats: Record<string, any> }>()
</script>

<style lang="scss" scoped>
.stats-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  padding: 10px 18px;
  margin-bottom: 14px;
  border-color: rgba(186, 230, 253, 0.65) !important;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  &:first-child { padding-left: 0; }
  &.warn .stat-val { color: #d97706; }
}

.stat-div {
  width: 1px;
  height: 18px;
  background: #e2e8f0;
}

.stat-label {
  font-size: 12px;
  color: #94a3b8;
}

.stat-val {
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 14px;
  font-weight: 700;
  color: #1e293b;
  &.muted { color: #64748b; font-weight: 600; }
}
</style>
