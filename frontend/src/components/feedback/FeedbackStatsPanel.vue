<template>
  <section class="stats-panel glass-panel" aria-label="反馈统计">
    <div class="panel-label">STAT · 反馈统计 · 点击卡片筛选来源</div>
    <div class="stats-grid">
      <button
        v-for="s in statCards"
        :key="s.key"
        type="button"
        class="stat-card"
        :class="[s.tone, { active: filter === s.filter }]"
        @click="emit('update:filter', s.filter)"
      >
        <span class="stat-code">{{ s.code }}</span>
        <strong class="stat-value">{{ s.value }}</strong>
        <span class="stat-label">{{ s.label }}</span>
        <span class="stat-hint">{{ s.hint }}</span>
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { FeedbackInfo } from '@/api/feedback'

const props = defineProps<{
  feedbacks: FeedbackInfo[]
  filter: 'all' | 'session_chat' | 'agent_chat' | 'manual' | 'pending'
}>()

const emit = defineEmits<{ 'update:filter': [filter: typeof props.filter] }>()

const statCards = computed(() => {
  const list = props.feedbacks
  return [
    {
      key: 'total',
      code: 'TOT',
      label: '全部',
      hint: '所有反馈记录',
      value: list.length,
      tone: 'tone-blue',
      filter: 'all' as const,
    },
    {
      key: 'session',
      code: 'SES',
      label: '会话反馈',
      hint: '对话页提交',
      value: list.filter(f => f.source === 'session_chat').length,
      tone: 'tone-purple',
      filter: 'session_chat' as const,
    },
    {
      key: 'eval',
      code: 'EVL',
      label: '会话评价',
      hint: 'Agent 结果评价',
      value: list.filter(f => f.source === 'agent_chat').length,
      tone: 'tone-green',
      filter: 'agent_chat' as const,
    },
    {
      key: 'pending',
      code: 'PND',
      label: '待回复',
      hint: '等待管理员',
      value: list.filter(f => f.status === 'pending').length,
      tone: 'tone-warn',
      filter: 'pending' as const,
    },
  ]
})
</script>

<style lang="scss" scoped>
.stats-panel {
  padding: 14px 16px;
  margin-bottom: 14px;
  border-color: rgba(124, 58, 237, 0.12) !important;
}

.panel-label {
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: #94a3b8;
  margin-bottom: 10px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 10px;

  @media (max-width: 768px) {
    grid-template-columns: repeat(2, 1fr);
  }
}

.stat-card {
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: rgba(255, 255, 255, 0.75);
  text-align: left;
  cursor: pointer;
  transition: all 0.2s;

  &:hover {
    border-color: rgba(124, 58, 237, 0.35);
    box-shadow: 0 4px 14px rgba(124, 58, 237, 0.08);
  }

  &.active {
    border-color: #7c3aed;
    background: rgba(124, 58, 237, 0.05);
    box-shadow: inset 0 0 0 1px rgba(124, 58, 237, 0.15);
  }
}

.stat-code {
  display: block;
  font-size: 8px;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: #94a3b8;
  margin-bottom: 4px;
}

.stat-value {
  display: block;
  font-size: 26px;
  font-weight: 800;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.stat-label {
  display: block;
  margin-top: 4px;
  font-size: 12px;
  font-weight: 600;
  color: #334155;
}

.stat-hint {
  display: block;
  margin-top: 2px;
  font-size: 10px;
  color: #94a3b8;
}

.tone-blue .stat-value { color: #2563eb; }
.tone-purple .stat-value { color: #7c3aed; }
.tone-green .stat-value { color: #059669; }
.tone-warn .stat-value { color: #d97706; }
</style>
