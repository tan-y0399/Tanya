<template>
  <div class="server-page-header">
    <div class="header-main">
      <div class="title-bar">
        <span class="title-accent"></span>
        <div>
          <h2 class="page-title">服务器管理</h2>
          <p class="page-sub">[ CLUSTER · SSH AUTO-PROVISION · MULTI-NODE ]</p>
        </div>
      </div>
      <p class="page-desc">多机集群运维 · 智能 SSH 自动化配置 · 添加/编辑/删除服务器节点</p>
    </div>
    <div class="header-actions">
      <button
        type="button"
        class="refresh-status-btn"
        :class="{ active: refreshing }"
        :disabled="refreshing"
        @click="emit('refreshStatus')"
        title="检测并刷新所有服务器状态"
      >
        <span class="btn-glow"></span>
        <svg class="refresh-icon" width="18" height="18" viewBox="0 0 18 18" fill="none" :class="{ spinning: refreshing }">
          <circle cx="9" cy="9" r="7" stroke="currentColor" stroke-width="1.2" stroke-opacity="0.25"/>
          <path
            d="M9 2.5a6.5 6.5 0 016.5 6.5"
            stroke="url(#refreshGrad)"
            stroke-width="1.6"
            stroke-linecap="round"
          />
          <path
            d="M15.5 9V5.5M15.5 5.5H12"
            stroke="url(#refreshGrad)"
            stroke-width="1.4"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
          <path
            d="M9 15.5a6.5 6.5 0 01-6.5-6.5"
            stroke="url(#refreshGrad2)"
            stroke-width="1.6"
            stroke-linecap="round"
            stroke-opacity="0.85"
          />
          <path
            d="M2.5 9v3.5M2.5 12.5H6"
            stroke="url(#refreshGrad2)"
            stroke-width="1.4"
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-opacity="0.85"
          />
          <circle cx="9" cy="9" r="1.8" fill="#38bdf8"/>
          <circle cx="9" cy="9" r="3.5" stroke="#7dd3fc" stroke-width="0.6" stroke-dasharray="2 2" opacity="0.7"/>
          <defs>
            <linearGradient id="refreshGrad" x1="9" y1="2" x2="16" y2="10" gradientUnits="userSpaceOnUse">
              <stop stop-color="#2563eb"/>
              <stop offset="1" stop-color="#38bdf8"/>
            </linearGradient>
            <linearGradient id="refreshGrad2" x1="9" y1="16" x2="2" y2="8" gradientUnits="userSpaceOnUse">
              <stop stop-color="#6366f1"/>
              <stop offset="1" stop-color="#93c5fd"/>
            </linearGradient>
          </defs>
        </svg>
        <span class="btn-label">{{ refreshing ? '检测中…' : '刷新状态' }}</span>
      </button>
      <button type="button" class="tech-btn primary add-btn" @click="emit('add')">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <path d="M8 3v10M3 8h10" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>
        添加服务器
      </button>
    </div>
  </div>

  <div class="cluster-overview glass-panel" v-if="total > 0">
    <div class="overview-item">
      <span class="dot online"></span>
      <span class="ov-label">在线</span>
      <span class="ov-value">{{ onlineCount }}</span>
    </div>
    <div class="overview-divider"></div>
    <div class="overview-item">
      <span class="dot offline"></span>
      <span class="ov-label">离线</span>
      <span class="ov-value">{{ offlineCount }}</span>
    </div>
    <div class="overview-divider"></div>
    <div class="overview-item">
      <span class="ov-label">节点总数</span>
      <span class="ov-value">{{ total }}</span>
    </div>
    <div class="overview-divider" v-if="defaultName"></div>
    <div class="overview-item" v-if="defaultName">
      <span class="ov-label">默认节点</span>
      <span class="ov-value default-name">{{ defaultName }}</span>
    </div>
    <div class="overview-divider" v-if="refreshing"></div>
    <div class="overview-item scanning" v-if="refreshing">
      <span class="scan-pulse"></span>
      <span class="ov-label">全集群检测中</span>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  onlineCount: number
  offlineCount: number
  total: number
  defaultName?: string
  refreshing?: boolean
}>()

const emit = defineEmits<{ add: []; refreshStatus: [] }>()
</script>

<style lang="scss" scoped>
.server-page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.title-bar {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.title-accent {
  width: 3px;
  height: 36px;
  border-radius: 2px;
  background: linear-gradient(180deg, #2563eb, #6366f1);
  box-shadow: 0 0 12px rgba(37, 99, 235, 0.4);
  flex-shrink: 0;
  margin-top: 2px;
}

.page-title {
  font-size: 22px;
  font-weight: 700;
  color: #0f172a;
  margin: 0;
  letter-spacing: 0.01em;
}

.page-sub {
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: #6366f1;
  margin: 4px 0 0;
  opacity: 0.85;
}

.page-desc {
  font-size: 13px;
  color: #94a3b8;
  margin: 8px 0 0;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
}

.refresh-status-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 9px 16px;
  border-radius: 10px;
  border: 1px solid rgba(56, 189, 248, 0.55);
  background: linear-gradient(135deg, rgba(239, 246, 255, 0.95), rgba(255, 255, 255, 0.9));
  color: #2563eb;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  overflow: hidden;
  transition: all 0.2s ease;
  box-shadow: 0 2px 12px rgba(37, 99, 235, 0.1);

  &:hover:not(:disabled) {
    border-color: #38bdf8;
    box-shadow: 0 4px 20px rgba(56, 189, 248, 0.25);
    transform: translateY(-1px);
  }

  &.active, &:disabled {
    cursor: wait;
    border-color: #6366f1;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15), 0 4px 20px rgba(56, 189, 248, 0.2);
  }

  &:disabled { opacity: 0.92; }
}

.btn-glow {
  position: absolute;
  inset: 0;
  background: linear-gradient(105deg, transparent 40%, rgba(56, 189, 248, 0.15) 50%, transparent 60%);
  transform: translateX(-100%);
  .active & { animation: btn-sweep 1.2s ease-in-out infinite; }
}

.refresh-icon {
  flex-shrink: 0;
  filter: drop-shadow(0 0 4px rgba(56, 189, 248, 0.4));
  &.spinning { animation: spin 0.9s linear infinite; }
}

.btn-label {
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 12px;
  letter-spacing: 0.02em;
}

.add-btn {
  background: linear-gradient(135deg, #2563eb, #6366f1) !important;
  border: none !important;
  color: #fff !important;
  box-shadow: 0 4px 16px rgba(37, 99, 235, 0.35);
  font-weight: 600;
  &:hover {
    box-shadow: 0 6px 22px rgba(37, 99, 235, 0.45);
    transform: translateY(-1px);
  }
}

.cluster-overview {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px 0;
  padding: 12px 18px;
  margin-bottom: 20px;
  border-color: rgba(186, 230, 253, 0.7) !important;
  box-shadow: 0 2px 12px rgba(37, 99, 235, 0.06);
  transition: box-shadow 0.3s;

  &:has(.scanning) {
    box-shadow: 0 2px 20px rgba(56, 189, 248, 0.2);
    border-color: rgba(56, 189, 248, 0.5) !important;
  }
}

.overview-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 16px;
  &:first-child { padding-left: 0; }

  &.scanning .ov-label { color: #2563eb; font-weight: 600; }
}

.overview-divider {
  width: 1px;
  height: 20px;
  background: #e2e8f0;
}

.scan-pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #38bdf8;
  animation: pulse-scan 0.8s ease-in-out infinite;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  &.online {
    background: #10b981;
    box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.15);
    animation: pulse-online 2.5s ease-in-out infinite;
  }
  &.offline { background: #ef4444; }
}

.ov-label {
  font-size: 12px;
  color: #94a3b8;
}

.ov-value {
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 14px;
  font-weight: 700;
  color: #1e293b;
  &.default-name {
    font-size: 12px;
    color: #2563eb;
    max-width: 120px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
}

@keyframes spin { to { transform: rotate(360deg); } }
@keyframes btn-sweep { to { transform: translateX(100%); } }
@keyframes pulse-online {
  0%, 100% { box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.15); }
  50% { box-shadow: 0 0 0 6px rgba(16, 185, 129, 0.08); }
}
@keyframes pulse-scan {
  0%, 100% { box-shadow: 0 0 0 0 rgba(56, 189, 248, 0.5); }
  50% { box-shadow: 0 0 0 6px rgba(56, 189, 248, 0); }
}
</style>
