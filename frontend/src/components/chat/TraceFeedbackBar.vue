<template>
  <div class="feedback-bar" v-if="visible">
    <div class="fb-header">
      <span class="fb-label">本次是否解决了您的问题？</span>
      <button type="button" class="fb-close" title="关闭" aria-label="关闭反馈" @click="handleDismiss">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <path d="M3 3l8 8M11 3l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
      </button>
    </div>

    <div v-if="!showForm" class="fb-btns">
      <button type="button" @click="openForm('solved')">已解决</button>
      <button type="button" @click="openForm('partial')">部分解决</button>
      <button type="button" @click="openForm('unsolved')">未解决</button>
    </div>

    <div v-else class="fb-form">
      <p class="fb-form-title">
        {{ outcomeLabels[selectedOutcome] }} — 请填写详细说明（将发送给管理员）
      </p>
      <textarea
        v-model="comment"
        class="fb-textarea"
        :placeholder="placeholders[selectedOutcome]"
        rows="4"
        maxlength="2000"
      />
      <div class="fb-form-actions">
        <button type="button" class="fb-btn secondary" @click="showForm = false">返回</button>
        <button type="button" class="fb-btn primary" :disabled="submitting" @click="handleSubmit">
          {{ submitting ? '提交中…' : '提交反馈' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { submitTraceOutcome } from '@/api/traceOutcome'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  visible: boolean
  traceId: string
  sessionId: string
}>()

const emit = defineEmits<{
  close: []
  submitted: [outcome: 'solved' | 'partial' | 'unsolved']
}>()

const showForm = ref(false)
const selectedOutcome = ref<'solved' | 'partial' | 'unsolved'>('solved')
const comment = ref('')
const submitting = ref(false)

const outcomeLabels = {
  solved: '已解决',
  partial: '部分解决',
  unsolved: '未解决',
} as const

const placeholders = {
  solved: '可选：说明哪些部分对您有帮助，便于管理员优化…',
  partial: '请说明哪些已解决、哪些仍未解决…',
  unsolved: '请描述问题现象、期望结果或改进建议，管理员将跟进…',
} as const

function openForm(outcome: 'solved' | 'partial' | 'unsolved') {
  selectedOutcome.value = outcome
  comment.value = ''
  showForm.value = true
}

function handleDismiss() {
  emit('close')
}

async function handleSubmit() {
  if (!props.traceId || !props.sessionId || submitting.value) return
  const text = comment.value.trim()
  if (selectedOutcome.value !== 'solved' && !text) {
    ElMessage.warning('请填写详细说明，便于管理员处理')
    return
  }
  submitting.value = true
  try {
    await submitTraceOutcome({
      traceId: props.traceId,
      sessionId: props.sessionId,
      outcome: selectedOutcome.value,
      comment: text || undefined,
    })
    ElMessage.success('反馈已提交，感谢')
    emit('submitted', selectedOutcome.value)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '提交失败')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped lang="scss">
.feedback-bar {
  margin: 12px 0;
  padding: 12px 16px;
  border-radius: 10px;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
}
.fb-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.fb-label {
  font-size: 13px;
  color: #166534;
  font-weight: 500;
}
.fb-close {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  &:hover {
    background: rgba(0, 0, 0, 0.06);
    color: #334155;
  }
}
.fb-btns {
  display: flex;
  gap: 8px;
  margin-top: 10px;
  flex-wrap: wrap;
}
.fb-btns button {
  padding: 6px 14px;
  border-radius: 8px;
  border: 1px solid #86efac;
  background: #fff;
  color: #15803d;
  font-size: 12px;
  cursor: pointer;
  &:hover {
    background: #dcfce7;
  }
}
.fb-form {
  margin-top: 10px;
}
.fb-form-title {
  margin: 0 0 8px;
  font-size: 12px;
  color: #15803d;
}
.fb-textarea {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid #86efac;
  font-size: 13px;
  line-height: 1.5;
  resize: vertical;
  min-height: 88px;
  font-family: inherit;
  &:focus {
    outline: none;
    border-color: #22c55e;
    box-shadow: 0 0 0 2px rgba(34, 197, 94, 0.15);
  }
}
.fb-form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 10px;
}
.fb-btn {
  padding: 6px 14px;
  border-radius: 8px;
  font-size: 12px;
  cursor: pointer;
  border: 1px solid transparent;
  &.secondary {
    background: #fff;
    border-color: #cbd5e1;
    color: #64748b;
  }
  &.primary {
    background: #22c55e;
    color: #fff;
    &:disabled {
      opacity: 0.6;
      cursor: not-allowed;
    }
  }
}
</style>
