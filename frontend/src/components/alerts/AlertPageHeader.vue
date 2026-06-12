<template>
  <header class="alert-header">
    <div class="header-main">
      <div class="title-bar">
        <span class="title-accent"></span>
        <div>
          <div class="mod-tag">MOD-ALT · 告警中心</div>
          <h2 class="page-title">告警中心</h2>
          <p class="page-sub">[ REAL-TIME · RCA · AI SUGGEST ]</p>
        </div>
      </div>
      <p class="page-desc">实时告警监控 · 根因分析 · 智能处理建议</p>
    </div>
    <div class="header-actions">
      <span v-if="lastRefresh" class="sync-time">SYNC {{ lastRefresh }}</span>
      <button
        type="button"
        class="refresh-btn"
        :class="{ active: refreshing }"
        :disabled="refreshing"
        @click="emit('refresh')"
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none" :class="{ spinning: refreshing }">
          <path d="M1 7a6 6 0 0111.3-3M13 7a6 6 0 01-11.3 3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
        </svg>
        {{ refreshing ? '同步中…' : '同步告警' }}
      </button>
    </div>
  </header>
</template>

<script setup lang="ts">
defineProps<{
  refreshing?: boolean
  lastRefresh?: string
}>()

const emit = defineEmits<{ refresh: [] }>()
</script>

<style lang="scss" scoped>
.alert-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.title-bar {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.title-accent {
  width: 4px;
  height: 52px;
  border-radius: 2px;
  background: linear-gradient(180deg, #ef4444, #f97316);
  flex-shrink: 0;
}

.mod-tag {
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.1em;
  color: #ef4444;
  margin-bottom: 4px;
}

.page-title {
  margin: 0;
  font-size: 22px;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: 0.02em;
}

.page-sub {
  margin: 4px 0 0;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #94a3b8;
}

.page-desc {
  margin: 8px 0 0;
  font-size: 13px;
  color: #64748b;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.sync-time {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: #94a3b8;
  font-variant-numeric: tabular-nums;
}

.refresh-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 8px;
  border: 1px solid rgba(239, 68, 68, 0.25);
  background: rgba(255, 255, 255, 0.85);
  color: #dc2626;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;

  &:hover:not(:disabled) {
    border-color: #ef4444;
    box-shadow: 0 0 16px rgba(239, 68, 68, 0.15);
  }

  &:disabled {
    opacity: 0.65;
    cursor: not-allowed;
  }

  &.active {
    background: rgba(239, 68, 68, 0.08);
  }
}

.spinning {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
