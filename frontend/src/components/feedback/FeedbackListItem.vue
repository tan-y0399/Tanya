<template>
  <article
    class="fb-item glass-panel"
    :class="[`accent-${sourceTone(row)}`, { 'has-reply': !!row.adminReply, pending: row.status === 'pending' }]"
    @click="emit('select', row)"
  >
    <div class="item-rail" :class="sourceTone(row)" />

    <div class="item-body">
      <div class="row-top">
        <span class="source-pill" :class="sourceTone(row)">{{ getSourceLabel(row) }}</span>
        <span class="type-pill" :class="getTypeTone(row)">{{ getTypeLabel(row) }}</span>
        <span class="status-pill" :class="row.status">{{ STATUS_LABELS[row.status] }}</span>
        <span v-if="row.attachments?.length" class="attach-badge">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
            <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
          </svg>
          {{ row.attachments.length }}
        </span>
        <span class="fb-time">{{ formatTime(row.createdAt) }}</span>
      </div>

      <h4 class="fb-title">{{ getDisplayTitle(row) }}</h4>
      <p v-if="getContentExcerpt(row)" class="fb-excerpt">{{ getContentExcerpt(row) }}</p>

      <div v-if="row.traceId || row.sessionId" class="trace-row">
        <span v-if="row.sessionId" class="trace-chip">SID {{ shortId(row.sessionId) }}</span>
        <span v-if="row.traceId" class="trace-chip mono">TRC {{ shortId(row.traceId) }}</span>
      </div>

      <div class="row-foot">
        <span class="fb-user">
          <span class="user-dot">{{ (row.username || '?')[0] }}</span>
          {{ row.username }}
        </span>
        <span class="reply-hint" :class="{ pending: !row.adminReply }">
          {{ row.adminReply ? '管理员已回复' : '等待回复' }}
        </span>
        <span class="view-btn">DETAIL →</span>
      </div>
    </div>
  </article>
</template>

<script setup lang="ts">
import type { FeedbackInfo } from '@/api/feedback'
import {
  getSourceLabel,
  getTypeLabel,
  getDisplayTitle,
  getContentExcerpt,
  getTypeTone,
  STATUS_LABELS,
  SOURCE_TONE,
} from '@/utils/feedbackMeta'

defineProps<{ row: FeedbackInfo }>()
const emit = defineEmits<{ select: [row: FeedbackInfo] }>()

function sourceTone(row: FeedbackInfo) {
  return SOURCE_TONE[row.source || 'manual'] || 'tone-manual'
}

function shortId(id: string) {
  if (!id || id.length <= 12) return id
  return `${id.slice(0, 8)}…`
}

function formatTime(t: string) {
  if (!t) return '—'
  const d = new Date(t)
  if (Number.isNaN(d.getTime())) return t
  const diff = Math.floor((Date.now() - d.getTime()) / 1000)
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  return d.toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
  })
}
</script>

<style lang="scss" scoped>
.fb-item {
  display: flex;
  padding: 0;
  overflow: hidden;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.2s;
  border-color: rgba(226, 232, 240, 0.9) !important;

  &:hover {
    transform: translateY(-1px);
    box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);
    border-color: rgba(124, 58, 237, 0.25) !important;
  }

  &.pending:not(.has-reply) {
    animation: pulse-soft 3s ease-in-out infinite;
  }
}

.item-rail {
  width: 4px;
  flex-shrink: 0;

  &.tone-session { background: linear-gradient(180deg, #3b82f6, #6366f1); }
  &.tone-eval { background: linear-gradient(180deg, #10b981, #059669); }
  &.tone-manual { background: linear-gradient(180deg, #94a3b8, #64748b); }
}

.item-body {
  flex: 1;
  min-width: 0;
  padding: 14px 16px;
}

.row-top {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.fb-time {
  margin-left: auto;
  font-size: 11px;
  color: #94a3b8;
  font-variant-numeric: tabular-nums;
}

.source-pill, .type-pill, .status-pill {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.03em;
  padding: 2px 8px;
  border-radius: 999px;
}

.source-pill {
  &.tone-manual { background: #f1f5f9; color: #64748b; }
  &.tone-session { background: #eff6ff; color: #2563eb; }
  &.tone-eval { background: #ecfdf5; color: #059669; }
}

.type-pill {
  &.type-default { background: #faf5ff; color: #7c3aed; }
  &.type-ok { background: #ecfdf5; color: #059669; }
  &.type-partial { background: #fef3c7; color: #b45309; }
  &.type-fail { background: #fce7f3; color: #be185d; }
}

.status-pill {
  &.pending { background: #fffbeb; color: #d97706; border: 1px solid #fde68a; }
  &.replied { background: #ecfdf5; color: #059669; border: 1px solid #a7f3d0; }
  &.closed { background: #f1f5f9; color: #64748b; }
}

.attach-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #f1f5f9;
  color: #64748b;
  font-size: 10px;
  font-weight: 700;
}

.fb-title {
  margin: 0 0 4px;
  font-size: 15px;
  font-weight: 700;
  color: #0f172a;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fb-excerpt {
  margin: 0 0 8px;
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.trace-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.trace-chip {
  font-size: 10px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(99, 102, 241, 0.08);
  color: #4338ca;

  &.mono {
    font-family: ui-monospace, monospace;
    background: rgba(15, 23, 42, 0.05);
    color: #475569;
  }
}

.row-foot {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
}

.fb-user {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #475569;
  font-weight: 600;
}

.user-dot {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.reply-hint {
  color: #059669;
  font-size: 11px;
  &.pending { color: #d97706; }
}

.view-btn {
  margin-left: auto;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.06em;
  color: #94a3b8;
}

@keyframes pulse-soft {
  0%, 100% { box-shadow: 0 0 0 0 rgba(217, 119, 6, 0); }
  50% { box-shadow: 0 0 0 2px rgba(217, 119, 6, 0.12); }
}
</style>
