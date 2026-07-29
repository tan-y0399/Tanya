<template>
  <div class="user-msg">
    <div class="msg-body">
      <div class="msg-meta">
        <span class="msg-time">{{ formattedTime }}</span>
        <span class="msg-role">我</span>
      </div>
      <div v-if="attachments?.length" class="msg-attachments">
        <img
          v-for="att in attachments"
          :key="att.id || att.url || att.name"
          :src="att.url || att.dataUrl"
          :alt="att.name"
          class="msg-image"
        />
      </div>
      <div v-if="content" class="msg-content">{{ content }}</div>
    </div>
    <div class="msg-avatar">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
        <circle cx="12" cy="9" r="4" stroke="#fff" stroke-width="1.5"/>
        <path d="M4 21c0-4 3.5-7 8-7s8 3 8 7" stroke="#fff" stroke-width="1.5" stroke-linecap="round"/>
      </svg>
    </div>
  </div>
</template>

<script setup lang="ts">
import { formatTime } from '@/utils'
import type { ChatAttachment } from '@/stores/chat'

const props = defineProps<{
  content: string
  createdAt: string
  attachments?: ChatAttachment[]
}>()

const formattedTime = formatTime(props.createdAt)
</script>

<style lang="scss" scoped>
.user-msg {
  display: flex;
  gap: 12px;
  padding: 10px 0;
  justify-content: flex-end;
  animation: fadeIn 0.25s ease;
}

.msg-avatar {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: linear-gradient(135deg, #2563eb, #6366f1);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.msg-body {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  max-width: 70%;
}

.msg-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 4px;
  .msg-role {
    font-size: 12px;
    font-weight: 600;
    color: #2563eb;
  }
  .msg-time {
    font-size: 11px;
    color: #94a3b8;
  }
}

.msg-content {
  font-size: 14px;
  color: #fff;
  line-height: 1.6;
  padding: 10px 16px;
  background: linear-gradient(135deg, #2563eb, #3b82f6);
  border-radius: 14px 4px 14px 14px;
  white-space: pre-wrap;
  word-break: break-word;
}

.msg-attachments {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(120px, 180px));
  gap: 8px;
  justify-content: end;
  margin-bottom: 8px;
}

.msg-image {
  width: 100%;
  max-height: 180px;
  object-fit: cover;
  border-radius: 10px;
  border: 1px solid rgba(191, 219, 254, 0.9);
  background: #eff6ff;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
