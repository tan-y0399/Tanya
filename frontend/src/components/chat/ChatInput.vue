<template>
  <div class="chat-input-area">
    <div class="input-wrapper">
      <textarea
        ref="inputRef"
        v-model="inputText"
        class="input-field"
        placeholder="输入运维指令，如：查看磁盘使用情况..."
        rows="1"
        :disabled="isStreaming"
        @keydown.enter.exact.prevent="send"
        @input="autoResize"
      ></textarea>
      <button v-if="isStreaming" class="stop-btn" @click="stop" title="停止生成">
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
          <rect x="3" y="3" width="12" height="12" rx="2" fill="currentColor"/>
        </svg>
      </button>
      <button v-else
        class="send-btn"
        :class="{ active: inputText.trim(), disabled: !inputText.trim() }"
        :disabled="!inputText.trim()"
        @click="send"
      >
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
          <path d="M2 9l12-6-4.5 12L7 10.5 2 9z" fill="currentColor"/>
        </svg>
      </button>
    </div>
    <div class="input-hint">
      <span>Enter 发送</span>
      <span class="hint-sep">·</span>
      <span>基于 ReAct / Plan-Execute 智能编排</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick } from 'vue'

defineProps<{ isStreaming: boolean }>()
const emit = defineEmits<{
  send: [text: string]
  stop: []
}>()

const inputRef = ref<HTMLTextAreaElement>()
const inputText = ref('')

function autoResize() {
  nextTick(() => {
    const el = inputRef.value
    if (el) {
      el.style.height = 'auto'
      el.style.height = Math.min(el.scrollHeight, 120) + 'px'
    }
  })
}

function send() {
  const text = inputText.value.trim()
  if (!text) return
  emit('send', text)
  inputText.value = ''
  nextTick(autoResize)
}

function stop() {
  emit('stop')
}
</script>

<style lang="scss" scoped>
.chat-input-area {
  padding: 12px 20px;
  border-top: 1px solid #e2e8f0;
  background: rgba(255, 255, 255, 0.7);
}

.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  padding: 8px 14px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  transition: all 0.2s;
  &:focus-within {
    border-color: #2563eb;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.06);
  }
}

.input-field {
  flex: 1;
  border: none;
  background: none;
  color: #1e293b;
  font-size: 14px;
  font-family: inherit;
  line-height: 1.5;
  resize: none;
  outline: none;
  max-height: 120px;
  &::placeholder { color: #94a3b8; }
  &:disabled { opacity: 0.5; }
}

.send-btn {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #94a3b8;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  flex-shrink: 0;
  &.active {
    color: #fff;
    border-color: #2563eb;
    background: #2563eb;
    &:hover {
      background: #3b82f6;
      box-shadow: 0 2px 8px rgba(37, 99, 235, 0.25);
    }
  }
  &.disabled {
    cursor: not-allowed;
    opacity: 0.5;
  }
}

.stop-btn {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  border: 1px solid #ef4444;
  background: #ef4444;
  color: #fff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  flex-shrink: 0;
  animation: pulse-stop 1.5s infinite;
  &:hover {
    background: #dc2626;
    border-color: #dc2626;
  }
}

@keyframes pulse-stop {
  0%, 100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4); }
  50% { box-shadow: 0 0 0 6px rgba(239, 68, 68, 0); }
}

.input-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
  font-size: 11px;
  color: #cbd5e1;
  .hint-sep { color: #e2e8f0; }
}
</style>
