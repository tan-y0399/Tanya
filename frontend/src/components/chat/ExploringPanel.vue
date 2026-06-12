<template>
  <div
    class="exploring-panel"
    v-if="steps.length"
    :class="{ 'is-streaming-answer': contentStreaming }"
  >
    <div class="exploring-header" @click="expanded = !expanded">
      <div class="header-main">
        <span class="header-icon" :class="{ active: isActive }">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
          </svg>
        </span>
        <div class="header-text">
          <span class="header-title">思考过程</span>
          <span class="header-sub">{{ headerSub }}</span>
        </div>
      </div>
      <div class="header-right">
        <span class="progress-pill">{{ doneCount }}/{{ totalSteps }}</span>
        <span class="toggle-icon">{{ expanded ? '收起' : '展开' }}</span>
      </div>
    </div>

    <transition name="flow-expand">
      <div v-show="expanded" class="flow-body">
        <div class="flow-track">
          <div
            v-for="(s, idx) in displaySteps"
            :key="s.id"
            class="flow-step"
            :class="[s.status, { 'is-last': idx === displaySteps.length - 1 }]"
            :style="{ animationDelay: `${idx * 0.05}s` }"
          >
            <div class="step-rail">
              <span class="step-num">{{ idx + 1 }}</span>
              <span v-if="idx < displaySteps.length - 1" class="step-line" :class="s.status"></span>
            </div>
            <div class="step-card">
              <div class="step-card-head">
                <span class="step-status-icon" :class="s.status">
                  <template v-if="s.status === 'done'">✓</template>
                  <template v-else-if="s.status === 'error'">!</template>
                  <span v-else class="step-spinner"></span>
                </span>
                <span class="step-title">{{ s.displayTitle }}</span>
              </div>
              <p v-if="s.displayDetail" class="step-detail">{{ s.displayDetail }}</p>
            </div>
          </div>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { ExploringStep } from '@/stores/chat'
import { useChatStore } from '@/stores/chat'
import { formatExploringTitle, formatExploringDetail } from '@/utils/exploringLabels'

const props = defineProps<{
  steps: ExploringStep[]
  /** 知识问答正文流式输出中：保持思考动画并展示「整理回答」步骤 */
  contentStreaming?: boolean
}>()
const chatStore = useChatStore()
const expanded = ref(true)

const isActive = computed(() =>
  !!props.contentStreaming
  || (chatStore.isStreaming && props.steps.some(s => s.status === 'running')),
)

const headerSub = computed(() => {
  if (props.contentStreaming) return '正在整理知识回答，下方同步输出…'
  if (isActive.value) return 'Agent 正在逐步推进…'
  return '本轮推理链路已记录'
})

const totalSteps = computed(() =>
  props.contentStreaming ? props.steps.length + 1 : props.steps.length,
)

const doneCount = computed(() =>
  props.steps.filter(s => s.status === 'done').length,
)

const displaySteps = computed(() => {
  const mapped = props.steps.map(s => ({
    ...s,
    displayTitle: formatExploringTitle(s.title, s.id),
    displayDetail: formatExploringDetail(s.detail, s.status),
  }))
  if (props.contentStreaming) {
    return [
      ...mapped,
      {
        id: 'kb-answer-stream',
        title: '整理知识回答',
        detail: '正在流式生成正文…',
        status: 'running' as const,
        displayTitle: '整理知识回答',
        displayDetail: '正在流式生成正文…',
      },
    ]
  }
  return mapped
})
</script>

<style scoped lang="scss">
.exploring-panel {
  border-radius: 12px;
  border: 1px solid #bfdbfe;
  background: linear-gradient(165deg, #f8fbff 0%, #ffffff 55%, #f1f5f9 100%);
  box-shadow: 0 2px 10px rgba(37, 99, 235, 0.06);
  overflow: hidden;

  &.is-streaming-answer {
    border-color: #93c5fd;
    box-shadow: 0 2px 14px rgba(37, 99, 235, 0.12);
    animation: panel-breathe 2s ease-in-out infinite;
  }
}

.exploring-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 11px 14px;
  cursor: pointer;
  user-select: none;
  border-bottom: 1px solid #e0e7ff;
  &:hover { background: rgba(239, 246, 255, 0.7); }
}

.header-main {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.header-icon {
  width: 32px;
  height: 32px;
  border-radius: 9px;
  background: #dbeafe;
  color: #2563eb;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  &.active {
    background: #2563eb;
    color: #fff;
    animation: icon-glow 1.4s ease infinite;
  }
}

.header-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.header-title {
  font-size: 13px;
  font-weight: 700;
  color: #1e3a8a;
}

.header-sub {
  font-size: 11px;
  color: #64748b;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.progress-pill {
  font-size: 11px;
  font-weight: 600;
  padding: 3px 9px;
  border-radius: 12px;
  background: #eff6ff;
  color: #1d4ed8;
  font-variant-numeric: tabular-nums;
}

.toggle-icon {
  font-size: 11px;
  color: #94a3b8;
}

.flow-body {
  padding: 12px 14px 14px;
}

.flow-track {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.flow-step {
  display: flex;
  gap: 12px;
  animation: step-in 0.35s ease both;
  padding-bottom: 10px;
  &.is-last { padding-bottom: 0; }
}

.step-rail {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 28px;
  flex-shrink: 0;
}

.step-num {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #e2e8f0;
  color: #64748b;
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;
  transition: all 0.25s ease;
}

.flow-step.running .step-num {
  background: #2563eb;
  color: #fff;
  box-shadow: 0 0 0 4px rgba(37, 99, 235, 0.2);
}

.flow-step.done .step-num {
  background: #10b981;
  color: #fff;
}

.flow-step.error .step-num {
  background: #ef4444;
  color: #fff;
}

.step-line {
  flex: 1;
  width: 2px;
  min-height: 12px;
  margin: 4px 0;
  background: linear-gradient(180deg, #cbd5e1 0%, #e2e8f0 100%);
  border-radius: 1px;
  &.done { background: linear-gradient(180deg, #10b981 0%, #cbd5e1 100%); }
  &.running {
    background: linear-gradient(180deg, #2563eb 0%, #e2e8f0 100%);
    animation: line-flow 1.2s ease infinite;
  }
  &.error { background: linear-gradient(180deg, #ef4444 0%, #e2e8f0 100%); }
}

.step-card {
  flex: 1;
  min-width: 0;
  padding: 8px 12px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #fff;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.flow-step.running .step-card {
  border-color: #93c5fd;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.08);
}

.flow-step.done .step-card {
  border-color: #bbf7d0;
  background: #fafefb;
}

.flow-step.error .step-card {
  border-color: #fecaca;
  background: #fffbfb;
}

.step-card-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.step-status-icon {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  font-size: 10px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  &.done { background: #dcfce7; color: #166534; }
  &.error { background: #fee2e2; color: #b91c1c; }
  &.running { background: #dbeafe; color: #2563eb; }
}

.step-spinner {
  width: 10px;
  height: 10px;
  border: 2px solid #93c5fd;
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

.step-title {
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  line-height: 1.4;
}

.step-detail {
  margin: 6px 0 0 26px;
  font-size: 12px;
  line-height: 1.55;
  color: #64748b;
}

.flow-expand-enter-active,
.flow-expand-leave-active {
  transition: opacity 0.2s ease, max-height 0.3s ease;
  max-height: 800px;
}
.flow-expand-enter-from,
.flow-expand-leave-to {
  opacity: 0;
  max-height: 0;
}

@keyframes step-in {
  from { opacity: 0; transform: translateX(-6px); }
  to { opacity: 1; transform: translateX(0); }
}
@keyframes spin { to { transform: rotate(360deg); } }
@keyframes line-flow {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}
@keyframes icon-glow {
  0%, 100% { box-shadow: 0 0 0 0 rgba(37, 99, 235, 0.35); }
  50% { box-shadow: 0 0 0 6px rgba(37, 99, 235, 0); }
}
@keyframes panel-breathe {
  0%, 100% { border-color: #93c5fd; }
  50% { border-color: #60a5fa; }
}
</style>
