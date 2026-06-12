<template>
  <div
    class="server-card glass-panel"
    :class="{ default: server.isDefault, offline: server.status === 'offline', testing }"
  >
    <div v-if="server.isDefault" class="default-corner">DEFAULT</div>
    <div v-if="testing" class="test-progress"></div>

    <div class="card-top">
      <div class="card-info">
        <span class="card-status" :class="server.status"></span>
        <span class="card-name">{{ server.name }}</span>
        <span class="card-auth-tag" v-if="server.authConfigured">SSH READY</span>
      </div>
      <div class="card-actions">
        <button type="button" class="act-btn test" title="测试连接" @click="emit('test', server)">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M3 7l3 3 5-5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </button>
        <button v-if="!server.isDefault" type="button" class="act-btn set-default" title="设为默认" @click="emit('setDefault', server)">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M7 1.5l1.4 2.8 3.1.5-2.2 2.1.5 3.1L7 8.8 4.2 10l.5-3.1L2.5 4.8l3.1-.5L7 1.5z" stroke="currentColor" stroke-width="1.1" stroke-linejoin="round"/></svg>
        </button>
        <button type="button" class="act-btn edit" title="编辑" @click="emit('edit', server)">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M9.5 2.5l2 2L5 11H3v-2L9.5 2.5z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/></svg>
        </button>
        <button type="button" class="act-btn del" title="删除" @click="emit('delete', server)">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><path d="M3 4h8M5.5 4V3h3v1M6 6.5v3M8 6.5v3M4.5 4l.5 7h4l.5-7" stroke="currentColor" stroke-width="1.1" stroke-linecap="round" stroke-linejoin="round"/></svg>
        </button>
      </div>
    </div>

    <div class="card-body">
      <div class="card-row">
        <span class="card-label">HOST</span>
        <code class="host-code">{{ server.host }}:{{ server.port }}</code>
      </div>
      <div class="card-row">
        <span class="card-label">USER</span>
        <span class="card-value">{{ server.username }}</span>
      </div>
      <div class="card-row" v-if="server.description">
        <span class="card-label">DESC</span>
        <span class="card-value">{{ server.description }}</span>
      </div>
      <div class="card-tags" v-if="server.tags?.length">
        <span class="tag-chip" v-for="t in server.tags" :key="t">{{ t }}</span>
      </div>
    </div>

    <div class="card-foot">
      <span class="foot-status" :class="server.status">
        <span class="foot-dot"></span>
        {{ statusLabel(server.status) }}
      </span>
      <span class="foot-time" v-if="server.lastChecked">LAST {{ formatDate(server.lastChecked) }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ServerInfo } from '@/api/servers'

defineProps<{
  server: ServerInfo
  testing?: boolean
}>()

const emit = defineEmits<{
  test: [server: ServerInfo]
  setDefault: [server: ServerInfo]
  edit: [server: ServerInfo]
  delete: [server: ServerInfo]
}>()

function statusLabel(status: string) {
  return ({ online: 'ONLINE', offline: 'OFFLINE', unknown: 'UNKNOWN' } as Record<string, string>)[status] || 'UNKNOWN'
}

function formatDate(iso: string) {
  return iso ? iso.replace('T', ' ').slice(0, 19) : '-'
}
</script>

<style lang="scss" scoped>
.server-card {
  position: relative;
  padding: 16px;
  border-radius: 14px;
  border-color: rgba(186, 230, 253, 0.65) !important;
  transition: all 0.22s cubic-bezier(0.4, 0, 0.2, 1);
  overflow: hidden;

  &:hover {
    border-color: rgba(96, 165, 250, 0.8) !important;
    box-shadow: 0 12px 40px rgba(37, 99, 235, 0.12);
    transform: translateY(-3px);
  }

  &.default {
    border-color: rgba(37, 99, 235, 0.55) !important;
    box-shadow: 0 4px 20px rgba(37, 99, 235, 0.1);
    &::before {
      content: '';
      position: absolute;
      left: 0;
      top: 0;
      bottom: 0;
      width: 3px;
      background: linear-gradient(180deg, #2563eb, #6366f1);
      box-shadow: 0 0 10px rgba(37, 99, 235, 0.5);
    }
  }

  &.offline { opacity: 0.88; }
}

.default-corner {
  position: absolute;
  top: 10px;
  right: 10px;
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.08em;
  padding: 2px 7px;
  border-radius: 4px;
  background: rgba(37, 99, 235, 0.1);
  color: #2563eb;
  border: 1px solid rgba(37, 99, 235, 0.25);
}

.test-progress {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, #2563eb, transparent);
  animation: scan 1.2s ease-in-out infinite;
}

.card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
  padding-right: 52px;
}

.card-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.card-status {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
  &.online {
    background: #10b981;
    box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.2);
    animation: pulse-online 2.5s ease-in-out infinite;
  }
  &.offline { background: #ef4444; box-shadow: 0 0 0 3px rgba(239, 68, 68, 0.15); }
  &.unknown { background: #cbd5e1; }
}

.card-name {
  font-size: 15px;
  font-weight: 700;
  color: #1e293b;
}

.card-auth-tag {
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.04em;
  padding: 2px 7px;
  border-radius: 4px;
  background: rgba(16, 185, 129, 0.08);
  color: #047857;
  border: 1px solid rgba(16, 185, 129, 0.35);
}

.card-actions {
  display: flex;
  gap: 5px;
}

.act-btn {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: rgba(255, 255, 255, 0.9);
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.15s;
  color: #64748b;
  &:hover { transform: scale(1.06); }
  &.test:hover { color: #10b981; background: #ecfdf5; border-color: #6ee7b7; box-shadow: 0 0 12px rgba(16, 185, 129, 0.2); }
  &.set-default:hover { color: #f59e0b; background: #fffbeb; border-color: #fcd34d; }
  &.edit:hover { color: #2563eb; background: #eff6ff; border-color: #93c5fd; box-shadow: 0 0 12px rgba(37, 99, 235, 0.2); }
  &.del:hover { color: #ef4444; background: #fef2f2; border-color: #fca5a5; }
}

.card-body { margin-bottom: 12px; }

.card-row {
  display: flex;
  gap: 10px;
  margin-bottom: 6px;
  font-size: 13px;
  align-items: baseline;
}

.card-label {
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 10px;
  font-weight: 700;
  color: #94a3b8;
  min-width: 40px;
  letter-spacing: 0.04em;
}

.host-code {
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 12px;
  color: #2563eb;
  background: #f0f9ff;
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid rgba(186, 230, 253, 0.8);
}

.card-value { color: #475569; }

.card-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 8px;
}

.tag-chip {
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 4px;
  background: #f1f5f9;
  color: #64748b;
  border: 1px solid #e2e8f0;
}

.card-foot {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
  padding-top: 12px;
  border-top: 1px solid rgba(226, 232, 240, 0.8);
}

.foot-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-weight: 600;
  letter-spacing: 0.04em;
  &.online { color: #059669; }
  &.offline { color: #dc2626; }
  &.unknown { color: #94a3b8; }
}

.foot-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
}

.foot-time {
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  color: #94a3b8;
  font-size: 10px;
}

@keyframes pulse-online {
  0%, 100% { box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.2); }
  50% { box-shadow: 0 0 0 6px rgba(16, 185, 129, 0.08); }
}

@keyframes scan {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}
</style>
