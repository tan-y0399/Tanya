<template>
  <div class="agent-msg">
    <div class="msg-avatar">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
        <rect x="3" y="3" width="18" height="18" rx="5" stroke="#2563eb" stroke-width="1.5"/>
        <circle cx="9" cy="10" r="2" stroke="#2563eb" stroke-width="1.2"/>
        <circle cx="15" cy="10" r="2" stroke="#2563eb" stroke-width="1.2"/>
        <path d="M8 16c2 2 6 2 8 0" stroke="#2563eb" stroke-width="1.2" stroke-linecap="round"/>
      </svg>
    </div>
    <div class="msg-body">
      <div class="msg-meta">
        <span class="msg-role">KylinOps Agent</span>
        <span v-if="maxRiskLevel && maxRiskLevel !== 'L1'" class="risk-badge" :class="'risk-' + maxRiskLevel.toLowerCase()">{{ maxRiskLevel }}</span>
        <span class="msg-time">{{ formattedTime }}</span>
      </div>
      <div class="msg-content" v-html="renderedContent"></div>
      <div class="msg-trace" v-if="traceId" @click="$emit('viewTrace', traceId)">
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
          <circle cx="6" cy="6" r="5" stroke="currentColor" stroke-width="1"/>
          <path d="M6 3v3l2 2" stroke="currentColor" stroke-width="1" stroke-linecap="round"/>
        </svg>
        <span>推理链路 · {{ shortTraceId }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'
import { formatTime } from '@/utils'

const props = defineProps<{
  content: string
  traceId?: string
  createdAt: string
  maxRiskLevel?: string
}>()

defineEmits<{ viewTrace: [traceId: string] }>()

const md = new MarkdownIt({
  breaks: true,
  linkify: true,
  html: false,
  typographer: true,
})

const renderedContent = computed(() => md.render(props.content))
const formattedTime = computed(() => formatTime(props.createdAt))
const shortTraceId = computed(() => props.traceId ? props.traceId.slice(0, 28) + '...' : '')
</script>

<style lang="scss" scoped>
.agent-msg {
  display: flex;
  gap: 12px;
  padding: 10px 0;
  animation: fadeIn 0.25s ease;
}

.msg-avatar {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  background: #eff6ff;
  border: 1px solid #dbeafe;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.msg-body {
  flex: 1;
  min-width: 0;
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
  color: #1e293b;
  line-height: 1.75;

  // 段落
  :deep(p) { margin: 8px 0; }

  // 行内代码
  :deep(code) {
    font-family: 'JetBrains Mono', Consolas, monospace;
    background: #f1f5f9;
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 13px;
    color: #2563eb;
  }

  // 代码块
  :deep(pre) {
    font-family: 'JetBrains Mono', Consolas, monospace;
    background: #1e293b;
    color: #e2e8f0;
    padding: 14px 18px;
    border-radius: 10px;
    overflow-x: auto;
    font-size: 12px;
    line-height: 1.6;
    margin: 12px 0;
    code { background: none; padding: 0; color: inherit; font-size: inherit; }
  }

  // 标题
  :deep(h1) { font-size: 19px; font-weight: 700; color: #0f172a; margin: 20px 0 10px; padding-bottom: 8px; border-bottom: 2px solid #e2e8f0; }
  :deep(h2) { font-size: 17px; font-weight: 700; color: #1e293b; margin: 18px 0 8px; }
  :deep(h3) { font-size: 15px; font-weight: 600; color: #334155; margin: 14px 0 6px; }
  :deep(h4) { font-size: 14px; font-weight: 600; color: #475569; margin: 10px 0 4px; }

  // 粗体高亮
  :deep(strong) {
    color: #0f172a;
    font-weight: 700;
  }

  // 表格
  :deep(table) {
    border-collapse: separate;
    border-spacing: 0;
    width: 100%;
    margin: 12px 0;
    border-radius: 10px;
    overflow: hidden;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    border: 1px solid #e2e8f0;

    thead th {
      background: #f1f5f9;
      color: #475569;
      font-weight: 600;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      padding: 10px 14px;
      text-align: left;
      border-bottom: 2px solid #e2e8f0;
    }

    tbody {
      tr {
        transition: background 0.1s;
        &:nth-child(even) { background: #f8fafc; }
        &:hover { background: #eff6ff; }
      }
      td {
        padding: 9px 14px;
        font-size: 13px;
        color: #334155;
        border-bottom: 1px solid #f1f5f9;
        vertical-align: middle;
        code { font-size: 12px; }
      }
    }
  }

  // 列表
  :deep(ul), :deep(ol) {
    padding-left: 20px;
    margin: 8px 0;
    li {
      margin: 4px 0;
      padding-left: 4px;
      &::marker { color: #2563eb; }
    }
  }

  // 引用
  :deep(blockquote) {
    border-left: 3px solid #2563eb;
    margin: 10px 0;
    padding: 8px 16px;
    background: #f8fafc;
    border-radius: 0 8px 8px 0;
    color: #64748b;
    font-size: 13px;
    p { margin: 4px 0; }
  }

  // 水平线
  :deep(hr) {
    border: none;
    border-top: 1px solid #e2e8f0;
    margin: 16px 0;
  }

  // 链接
  :deep(a) {
    color: #2563eb;
    text-decoration: none;
    &:hover { text-decoration: underline; }
  }
}

.msg-trace {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  padding: 4px 10px;
  border-radius: 6px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  font-size: 11px;
  color: #94a3b8;
  cursor: pointer;
  transition: all 0.15s;
  &:hover {
    color: #2563eb;
    border-color: #bfdbfe;
    background: #eff6ff;
  }
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

.risk-badge {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 700;
  margin-left: 6px;

  &.risk-l1 { background: #ecfdf5; color: #059669; border: 1px solid #a7f3d0; }
  &.risk-l2 { background: #fffbeb; color: #b45309; border: 1px solid #fde68a; }
  &.risk-l3 { background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; }
  &.risk-l4 { background: #fef2f2; color: #991b1b; border: 1px solid #fca5a5; }
  &.risk-l5 { background: #fef2f2; color: #7f1d1d; border: 1px solid #fca5a5; }
}
</style>
