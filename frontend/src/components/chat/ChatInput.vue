<template>
  <div class="chat-input-area">
    <div v-if="attachments.length" class="attachment-strip">
      <div v-for="att in attachments" :key="att.id" class="attachment-chip">
        <img :src="att.dataUrl" :alt="att.name" />
        <span>{{ att.name }}</span>
        <button type="button" @click="removeAttachment(att.id)" title="移除图片">×</button>
      </div>
    </div>
    <div class="input-wrapper" :class="{ 'input-wrapper--multiline': isMultiline }">
      <input
        ref="fileInputRef"
        class="file-input"
        type="file"
        accept="image/png,image/jpeg,image/webp,image/gif"
        multiple
        @change="handleFiles"
      />
      <button
        type="button"
        class="attach-btn"
        :disabled="isStreaming"
        title="上传图片"
        @click="fileInputRef?.click()"
      >
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
          <path d="M5 12.5l2.4-2.7 1.8 1.9 2.2-2.7 2.6 3.5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
          <rect x="2.5" y="3" width="13" height="12" rx="2" stroke="currentColor" stroke-width="1.4"/>
          <circle cx="6.5" cy="6.7" r="1.2" fill="currentColor"/>
        </svg>
      </button>
      <textarea
        ref="inputRef"
        v-model="inputText"
        class="input-field"
        placeholder="输入运维指令，如：查看磁盘使用情况..."
        rows="1"
        :disabled="isStreaming"
        @keydown.enter.exact.prevent="send"
        @paste="onPaste"
        @input="autoResize"
      ></textarea>
      <button v-if="isStreaming" class="stop-btn" @click="stop" title="停止生成">
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
          <rect x="3" y="3" width="12" height="12" rx="2" fill="currentColor"/>
        </svg>
      </button>
      <button v-else
        class="send-btn"
        :class="{ active: canSend, disabled: !canSend }"
        :disabled="!canSend"
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
      <span>Ctrl+V 粘贴文字或图片</span>
      <span class="hint-sep">·</span>
      <span>支持文字与图片，深度思考将启用多模态专家链路</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, nextTick, onMounted } from 'vue'
import type { ChatAttachment } from '@/stores/chat'
import { collectClipboardImages, shouldSkipDuplicatePaste } from '@/utils/feedbackPaste'

const props = defineProps<{ isStreaming: boolean }>()
const emit = defineEmits<{
  send: [text: string, attachments: ChatAttachment[]]
  stop: []
}>()

const inputRef = ref<HTMLTextAreaElement>()
const fileInputRef = ref<HTMLInputElement>()
const inputText = ref('')
const isMultiline = ref(false)
const attachments = ref<ChatAttachment[]>([])
const canSend = computed(() => !!inputText.value.trim() || attachments.value.length > 0)

const INPUT_MIN_HEIGHT = 24
const INPUT_MAX_HEIGHT = 120
const MAX_ATTACHMENTS = 4
const MAX_IMAGE_SIZE = 8 * 1024 * 1024

function autoResize() {
  nextTick(() => {
    const el = inputRef.value
    if (!el) return
    el.style.height = 'auto'
    const next = Math.min(Math.max(el.scrollHeight, INPUT_MIN_HEIGHT), INPUT_MAX_HEIGHT)
    el.style.height = `${next}px`
    isMultiline.value = next > INPUT_MIN_HEIGHT + 6
  })
}

function send() {
  const text = inputText.value.trim()
  if (!canSend.value) return
  emit('send', text, attachments.value)
  inputText.value = ''
  attachments.value = []
  if (fileInputRef.value) fileInputRef.value.value = ''
  nextTick(autoResize)
}

function stop() {
  emit('stop')
}

onMounted(autoResize)

function removeAttachment(id?: string) {
  attachments.value = attachments.value.filter(a => a.id !== id)
}

function addImageFiles(files: File[]) {
  const remain = MAX_ATTACHMENTS - attachments.value.length
  if (remain <= 0) return

  for (const file of files.slice(0, remain)) {
    if (!file.type.startsWith('image/')) continue
    if (file.size > MAX_IMAGE_SIZE) continue
    const reader = new FileReader()
    reader.onload = () => {
      attachments.value.push({
        id: `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
        kind: 'image',
        name: file.name || `paste-${Date.now()}.png`,
        contentType: file.type,
        size: file.size,
        dataUrl: String(reader.result || ''),
      })
    }
    reader.readAsDataURL(file)
  }
}

function insertTextAtCursor(text: string) {
  const el = inputRef.value
  if (!el || !text) return
  const start = el.selectionStart ?? inputText.value.length
  const end = el.selectionEnd ?? inputText.value.length
  const before = inputText.value.slice(0, start)
  const after = inputText.value.slice(end)
  inputText.value = before + text + after
  nextTick(() => {
    const pos = start + text.length
    el.setSelectionRange(pos, pos)
    el.focus()
    autoResize()
  })
}

function onPaste(event: ClipboardEvent) {
  if (props.isStreaming) return
  const data = event.clipboardData
  if (!data) return

  const imageFiles = collectClipboardImages(data)
  if (!imageFiles.length) return

  const sig = imageFiles.map(f => `${f.type}:${f.size}:${f.lastModified || 0}`).join('|')
  if (shouldSkipDuplicatePaste(sig)) {
    event.preventDefault()
    return
  }

  event.preventDefault()
  addImageFiles(imageFiles)

  const plainText = data.getData('text/plain')
  if (plainText) {
    insertTextAtCursor(plainText)
  }
}

function handleFiles(event: Event) {
  const input = event.target as HTMLInputElement
  addImageFiles(Array.from(input.files || []))
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
  align-items: center;
  gap: 10px;
  padding: 10px 12px 10px 16px;
  min-height: 52px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  transition: all 0.2s;
  &:focus-within {
    border-color: #2563eb;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.06);
  }

  &--multiline {
    align-items: flex-end;
    padding-bottom: 8px;
  }
}

.attachment-strip {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.attachment-chip {
  display: flex;
  align-items: center;
  gap: 8px;
  max-width: 220px;
  padding: 6px 8px;
  border: 1px solid #dbeafe;
  border-radius: 8px;
  background: #eff6ff;
  color: #475569;
  font-size: 12px;

  img {
    width: 34px;
    height: 34px;
    border-radius: 6px;
    object-fit: cover;
  }

  span {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  button {
    width: 20px;
    height: 20px;
    border: none;
    border-radius: 5px;
    background: #dbeafe;
    color: #2563eb;
    cursor: pointer;
  }
}

.file-input {
  display: none;
}

.attach-btn {
  width: 34px;
  height: 34px;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #64748b;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  flex-shrink: 0;

  &:hover:not(:disabled) {
    color: #2563eb;
    border-color: #bfdbfe;
    background: #eff6ff;
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
  min-height: 24px;
  max-height: 120px;
  padding: 4px 0;
  margin: 0;
  box-sizing: border-box;
  vertical-align: middle;
  &::placeholder {
    color: #94a3b8;
    line-height: 1.5;
  }
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
