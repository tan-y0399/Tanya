<template>
  <div class="session-sidebar">
    <div class="session-header">
      <h3 class="section-title">会话列表</h3>
      <button class="new-btn" @click="$emit('newSession')" title="新建会话">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <path d="M7 1v12M1 7h12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>
      </button>
    </div>

    <div class="session-list" v-if="sessions.length">
      <div
        v-for="s in sessions"
        :key="s.id"
        class="session-item"
        :class="{ active: s.id === activeId }"
        @click="$emit('selectSession', s.id)"
      >
        <svg class="item-icon" width="14" height="14" viewBox="0 0 14 14" fill="none">
          <rect x="2" y="2" width="10" height="10" rx="2" stroke="currentColor" stroke-width="1.3"/>
          <path d="M4 6h6M4 9h4" stroke="currentColor" stroke-width="1" stroke-linecap="round"/>
        </svg>
        <div class="item-info">
          <div class="item-title">{{ s.title }}</div>
          <div class="item-meta">{{ s.messageCount }} 条消息</div>
        </div>
        <button class="item-delete" @click.stop="$emit('deleteSession', s.id)" title="删除">
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M3 3l6 6M9 3l-6 6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </button>
      </div>
    </div>

    <div class="session-empty" v-else>
      <p class="empty-text">暂无会话记录</p>
      <span class="empty-hint">点击上方 + 新建会话</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Session } from '@/stores/chat'

defineProps<{
  sessions: Session[]
  activeId: string | null
}>()

defineEmits<{
  newSession: []
  selectSession: [id: string]
  deleteSession: [id: string]
}>()
</script>

<style lang="scss" scoped>
.session-sidebar {
  width: 260px;
  min-width: 260px;
  height: 100%;
  display: flex;
  flex-direction: column;
  border-right: 1px solid #e2e8f0;
  background: #fafbfc;
}

.session-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  .section-title {
    font-size: 12px;
    font-weight: 600;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 1px;
  }
}

.new-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #fff;
  color: #64748b;
  cursor: pointer;
  transition: all 0.15s;
  &:hover {
    border-color: #2563eb;
    color: #2563eb;
    background: #eff6ff;
  }
}

.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 8px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.session-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
  .item-icon { color: #94a3b8; flex-shrink: 0; }
  &:hover {
    background: #f1f5f9;
    .item-delete { opacity: 1; }
  }
  &.active {
    background: #eff6ff;
    border: 1px solid #dbeafe;
    .item-icon { color: #2563eb; }
  }
  .item-info {
    flex: 1;
    min-width: 0;
    .item-title {
      font-size: 13px;
      color: #1e293b;
      font-weight: 500;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .item-meta {
      font-size: 11px;
      color: #94a3b8;
      margin-top: 2px;
    }
  }
  .item-delete {
    opacity: 0;
    background: none;
    border: none;
    color: #94a3b8;
    cursor: pointer;
    padding: 2px;
    border-radius: 4px;
    &:hover { color: #ef4444; background: #fef2f2; }
  }
}

.session-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  .empty-text { font-size: 14px; color: #94a3b8; }
  .empty-hint { font-size: 12px; color: #cbd5e1; }
}
</style>
