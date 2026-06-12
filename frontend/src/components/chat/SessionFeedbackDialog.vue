<template>
  <el-dialog
    v-model="visible"
    width="560px"
    class="session-feedback-dialog"
    :show-close="false"
    :close-on-click-modal="false"
    destroy-on-close
    align-center
    @closed="onClosed"
  >
    <template #header>
      <div class="sf-header">
        <div class="sf-header-icon">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
            <path d="M12 2l2.4 4.9 5.4.8-3.9 3.8.9 5.3L12 14.9 7.2 17l.9-5.3L4.2 7.7l5.4-.8L12 2z" fill="#fbbf24" stroke="#f59e0b" stroke-width="0.5"/>
          </svg>
        </div>
        <div class="sf-header-text">
          <h3 class="sf-title">会话反馈</h3>
          <p class="sf-subtitle">您的意见会关联当前会话，管理员将在反馈管理中审核回复</p>
        </div>
        <button type="button" class="sf-close" aria-label="关闭" @click="requestClose">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
            <path d="M4 4l10 10M14 4L4 14" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
          </svg>
        </button>
      </div>
    </template>

    <div class="sf-body">
      <section class="sf-section">
        <label class="sf-label"><span class="req">*</span> 问题类型</label>
        <div class="sf-chips">
          <button
            v-for="c in categories"
            :key="c.value"
            type="button"
            class="sf-chip"
            :class="{ active: form.category === c.value }"
            @click="form.category = c.value"
          >
            <span class="chip-emoji">{{ c.emoji }}</span>
            {{ c.label }}
          </button>
        </div>
      </section>

      <section class="sf-section sf-stars-section">
        <label class="sf-label">满意度点评 <span class="opt">（可选，点星评价）</span></label>
        <div class="sf-stars-block" @mouseleave="hoverStar = 0">
          <div class="sf-stars-line" role="group" aria-label="满意度 1 到 5 星">
            <button
              v-for="n in 5"
              :key="n"
              type="button"
              class="sf-star-btn"
              :aria-label="`${n} 星`"
              @click="setStar(n)"
              @mouseenter="hoverStar = n"
            >
              <svg class="star-svg" width="36" height="36" viewBox="0 0 24 24" fill="none">
                <path
                  d="M12 2l2.4 4.9 5.4.8-3.9 3.8.9 5.3L12 14.9 7.2 17l.9-5.3L4.2 7.7l5.4-.8L12 2z"
                  :fill="isStarFilled(n) ? '#fbbf24' : '#e8ecf1'"
                  :stroke="isStarFilled(n) ? '#f59e0b' : '#cbd5e1'"
                  stroke-width="0.8"
                />
              </svg>
            </button>
          </div>
          <p class="sf-star-caption">
            <template v-if="displayStarLevel">
              <strong>{{ displayStarLabel }}</strong>
              <span class="caption-sub">（{{ displayStarLevel }} 星）</span>
              <button type="button" class="link-clear" @click="clearStar">清除</button>
            </template>
            <span v-else class="caption-placeholder">点击星星进行评价</span>
          </p>
        </div>
      </section>

      <section class="sf-section">
        <label class="sf-label"><span class="req">*</span> 详细说明</label>
        <div class="sf-editor" @paste.capture.stop="onEditorPaste">
          <el-input
            v-model="form.content"
            type="textarea"
            :rows="4"
            maxlength="2000"
            resize="none"
            placeholder="请描述遇到的问题、期望结果或改进建议…（支持 Ctrl+C / Ctrl+V 粘贴文字与截图）"
            class="sf-textarea"
          />
          <div class="sf-upload-bar">
            <input
              ref="fileInputRef"
              type="file"
              accept="image/jpeg,image/png,image/gif,image/webp"
              multiple
              class="sf-file-input"
              @change="onPickFiles"
            />
            <button
              type="button"
              class="sf-upload-btn"
              :disabled="uploading || images.length >= maxImages"
              @click="fileInputRef?.click()"
            >
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <rect x="1" y="3" width="14" height="11" rx="2" stroke="currentColor" stroke-width="1.2"/>
                <circle cx="5.5" cy="7" r="1.2" fill="currentColor"/>
                <path d="M1 11l4-3 3 2 3-3 4 4" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
              <span>{{ uploading ? '上传中…' : '添加图片' }}</span>
              <span class="upload-count">{{ images.length }}/{{ maxImages }}</span>
            </button>
            <span class="sf-upload-tip">支持截图，可 Ctrl+V 粘贴，单张 ≤2MB</span>
          </div>
          <div v-if="images.length" class="sf-previews">
            <div v-for="(img, idx) in images" :key="`${img.url}-${idx}`" class="sf-preview-item">
              <el-image
                :src="img.url"
                :preview-src-list="previewUrls"
                :initial-index="idx"
                fit="cover"
                class="sf-preview-img"
                preview-teleported
              />
              <span class="sf-preview-hint">预览</span>
              <button type="button" class="sf-preview-remove" @click.stop="removeImage(idx)">×</button>
            </div>
          </div>
        </div>
      </section>

      <div v-if="existingStatus" class="sf-status">
        <span class="status-dot" />
        本会话已有反馈 · 状态 {{ existingStatus }} · 再次提交将更新记录
      </div>
    </div>

    <template #footer>
      <div class="sf-footer">
        <button type="button" class="sf-btn ghost" @click="handleDefer">先不提交了</button>
        <button type="button" class="sf-btn primary" :disabled="submitting" @click="handleSubmit">
          <span v-if="submitting" class="btn-spin" />
          {{ submitting ? '提交中…' : '提交反馈 ✨' }}
        </button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, watch, computed, h } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  getSessionFeedback,
  submitSessionFeedback,
  uploadFeedbackImage,
} from '@/api/feedback'

const props = defineProps<{
  modelValue: boolean
  sessionId: string
  sessionTitle?: string
  traceId?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [v: boolean]
  submitted: []
}>()

const maxImages = 4
const maxImageBytes = 2 * 1024 * 1024

const starOptions = [
  { value: 1, label: '很不满意', outcome: 'unsolved' as const },
  { value: 2, label: '不满意', outcome: 'unsolved' as const },
  { value: 3, label: '一般', outcome: 'partial' as const },
  { value: 4, label: '较满意', outcome: 'partial' as const },
  { value: 5, label: '非常满意', outcome: 'solved' as const },
]

const categories = [
  { value: 'wrong_answer', label: '回答不准', emoji: '🎯' },
  { value: 'not_solved', label: '未解决', emoji: '🔧' },
  { value: 'tool_error', label: '工具异常', emoji: '⚡' },
  { value: 'ui_issue', label: '界面体验', emoji: '✨' },
  { value: 'other', label: '其他', emoji: '💬' },
]

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const submitting = ref(false)
const uploading = ref(false)
const existingStatus = ref('')
const starRating = ref(0)
const hoverStar = ref(0)
const fileInputRef = ref<HTMLInputElement>()
const images = ref<{ url: string; name: string }[]>([])

const form = reactive({
  category: 'not_solved',
  content: '',
})

interface FormSnapshot {
  category: string
  content: string
  starRating: number
  images: { url: string; name: string }[]
}

interface FeedbackDraft extends FormSnapshot {
  updatedAt: string
}

const baselineSnapshot = ref<FormSnapshot>({
  category: 'not_solved',
  content: '',
  starRating: 0,
  images: [],
})

function draftStorageKey() {
  return `kylinops:session-feedback-draft:${props.sessionId || ''}`
}

function captureSnapshot(): FormSnapshot {
  return {
    category: form.category,
    content: form.content,
    starRating: starRating.value,
    images: images.value.map(i => ({ url: i.url, name: i.name })),
  }
}

function isDirty() {
  return JSON.stringify(captureSnapshot()) !== JSON.stringify(baselineSnapshot.value)
}

function isEmptySnapshot(snap: FormSnapshot) {
  return !snap.content.trim()
    && !snap.images.length
    && !snap.starRating
    && snap.category === 'not_solved'
}

function persistDraft() {
  if (!props.sessionId) return
  const snap = captureSnapshot()
  if (isEmptySnapshot(snap)) {
    clearDraft()
    return
  }
  try {
    const draft: FeedbackDraft = {
      ...snap,
      updatedAt: new Date().toISOString(),
    }
    sessionStorage.setItem(draftStorageKey(), JSON.stringify(draft))
  } catch { /* ignore quota */ }
}

function readDraftFromStorage(): FeedbackDraft | null {
  if (!props.sessionId) return null
  try {
    const raw = sessionStorage.getItem(draftStorageKey())
    if (!raw) return null
    const data = JSON.parse(raw) as FeedbackDraft
    if (!data || typeof data !== 'object') return null
    return {
      category: data.category || 'not_solved',
      content: data.content || '',
      starRating: Number(data.starRating) || 0,
      images: Array.isArray(data.images) ? data.images : [],
      updatedAt: data.updatedAt || '',
    }
  } catch {
    return null
  }
}

function clearDraft() {
  if (!props.sessionId) return
  try {
    sessionStorage.removeItem(draftStorageKey())
  } catch { /* ignore */ }
}

function applySnapshot(snap: FormSnapshot) {
  form.category = snap.category || 'not_solved'
  form.content = snap.content || ''
  starRating.value = snap.starRating || 0
  hoverStar.value = 0
  images.value = snap.images.map(i => ({ url: i.url, name: i.name || '' }))
}

function closeDialog() {
  emit('update:modelValue', false)
}

async function requestClose() {
  if (isDirty()) {
    try {
      await ElMessageBox.confirm(
        h('div', { class: 'sf-exit-confirm-body' }, [
          h('p', { class: 'sf-exit-lead' }, '反馈内容尚未提交'),
          h('div', { class: 'sf-exit-row' }, [
            h('span', { class: 'sf-exit-icon', 'aria-hidden': 'true' }, [
              h('svg', { width: 22, height: 22, viewBox: '0 0 24 24', fill: 'none' }, [
                h('circle', { cx: 12, cy: 12, r: 10, fill: '#fef3c7', stroke: '#f59e0b', 'stroke-width': 1 }),
                h('path', {
                  d: 'M12 8v5M12 16h.01',
                  stroke: '#d97706',
                  'stroke-width': 2,
                  'stroke-linecap': 'round',
                }),
              ]),
            ]),
            h('p', { class: 'sf-exit-desc' }, '退出后草稿将自动保存，下次打开可继续编辑。'),
          ]),
        ]),
        '确认退出编辑？',
        {
          customClass: 'sf-exit-confirm-box',
          distinguishCancelAndClose: true,
          confirmButtonText: '仍然退出',
          cancelButtonText: '继续编辑',
          icon: '',
          autofocus: false,
        },
      )
    } catch {
      return
    }
  }
  persistDraft()
  closeDialog()
}

function handleDefer() {
  persistDraft()
  closeDialog()
}

const displayStarLevel = computed(() => hoverStar.value || starRating.value)

const previewUrls = computed(() => images.value.map(i => i.url))

const displayStarLabel = computed(() => {
  const o = starOptions.find(s => s.value === displayStarLevel.value)
  return o?.label || ''
})

function isStarFilled(n: number) {
  const lit = hoverStar.value || starRating.value
  return n <= lit
}

const statusMap: Record<string, string> = {
  pending: '待审核',
  replied: '已回复',
  closed: '已关闭',
}

function setStar(v: number) {
  starRating.value = starRating.value === v ? 0 : v
}

function clearStar() {
  starRating.value = 0
  hoverStar.value = 0
}

function collectClipboardImages(data: DataTransfer): File[] {
  const files: File[] = []
  const seen = new Set<string>()
  const add = (file: File | null) => {
    if (!file || !file.type.startsWith('image/')) return
    const key = `${file.type}:${file.size}:${file.lastModified || 0}`
    if (seen.has(key)) return
    seen.add(key)
    files.push(file)
  }

  let foundFromItems = false
  if (data.items?.length) {
    for (let i = 0; i < data.items.length; i++) {
      const item = data.items[i]
      if (item.kind === 'file' && item.type.startsWith('image/')) {
        add(item.getAsFile())
        foundFromItems = true
      }
    }
  }
  if (!foundFromItems && data.files?.length) {
    for (let i = 0; i < data.files.length; i++) add(data.files[i])
  }
  return files
}

function validateImageFile(file: File): string | null {
  if (!file.type.startsWith('image/')) return '仅支持 JPG / PNG / GIF / WebP 图片'
  if (file.size > maxImageBytes) return '单张图片不能超过 2MB'
  return null
}

async function uploadImageFiles(rawFiles: File[]) {
  if (!rawFiles.length) return
  const remain = maxImages - images.value.length
  if (remain <= 0) {
    ElMessage.warning(`最多上传 ${maxImages} 张图片`)
    return
  }
  const files = rawFiles.slice(0, remain)
  if (rawFiles.length > remain) {
    ElMessage.warning(`最多还能添加 ${remain} 张图片`)
  }
  uploading.value = true
  try {
    for (const file of files) {
      const err = validateImageFile(file)
      if (err) {
        ElMessage.warning(err)
        continue
      }
      const uploadFile = file.name
        ? file
        : new File([file], `paste-${Date.now()}.png`, { type: file.type || 'image/png' })
      const item = await uploadFeedbackImage(uploadFile)
      images.value.push({ url: item.url, name: item.name || uploadFile.name })
    }
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '图片上传失败')
  } finally {
    uploading.value = false
  }
}

const pasteGuard = { sig: '', at: 0 }

function onEditorPaste(ev: ClipboardEvent) {
  const data = ev.clipboardData
  if (!data) return

  const imageFiles = collectClipboardImages(data)
  if (!imageFiles.length) return

  ev.preventDefault()

  const sig = imageFiles.map(f => `${f.type}:${f.size}:${f.lastModified || 0}`).join('|')
  const now = Date.now()
  if (sig === pasteGuard.sig && now - pasteGuard.at < 400) return
  pasteGuard.sig = sig
  pasteGuard.at = now

  void uploadImageFiles(imageFiles)
}

async function onPickFiles(ev: Event) {
  const input = ev.target as HTMLInputElement
  const files = input.files
  if (!files?.length) return
  await uploadImageFiles(Array.from(files))
  input.value = ''
}

function removeImage(idx: number) {
  images.value.splice(idx, 1)
}

async function loadExistingStatus() {
  existingStatus.value = ''
  if (!props.sessionId) return
  try {
    const { item } = await getSessionFeedback(props.sessionId)
    if (!item) return
    existingStatus.value = statusMap[item.status] || item.status
  } catch { /* ignore */ }
}

async function initForm() {
  existingStatus.value = ''
  const draft = readDraftFromStorage()
  if (draft) {
    applySnapshot(draft)
  } else {
    resetForm()
  }
  await loadExistingStatus()
  baselineSnapshot.value = captureSnapshot()
}

function resetForm() {
  form.category = 'not_solved'
  form.content = ''
  starRating.value = 0
  hoverStar.value = 0
  images.value = []
}

watch(
  () => props.modelValue,
  (open) => {
    if (open) void initForm()
  },
)

function onClosed() {
  existingStatus.value = ''
}

async function handleSubmit() {
  if (!props.sessionId) {
    ElMessage.warning('请先选择或创建会话')
    return
  }
  if (!form.content.trim()) {
    ElMessage.warning('请填写详细说明')
    return
  }
  submitting.value = true
  try {
    const star = starOptions.find(s => s.value === starRating.value)
    await submitSessionFeedback({
      sessionId: props.sessionId,
      content: form.content.trim(),
      category: form.category,
      outcome: star?.outcome,
      traceId: props.traceId,
      sessionTitle: props.sessionTitle,
      starRating: starRating.value || undefined,
      starLabel: star?.label,
      images: images.value.map(i => i.url),
    })
    ElMessage.success('反馈已提交，感谢您对 KylinOps 的帮助～')
    emit('submitted')
    clearDraft()
    resetForm()
    baselineSnapshot.value = captureSnapshot()
    closeDialog()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '提交失败')
  } finally {
    submitting.value = false
  }
}
</script>

<style lang="scss" scoped>
:global(.session-feedback-dialog.el-dialog) {
  border-radius: 20px;
  overflow: hidden;
  box-shadow: 0 24px 48px rgba(37, 99, 235, 0.12), 0 8px 24px rgba(15, 23, 42, 0.08);
}

:global(.session-feedback-dialog .el-dialog__header) {
  padding: 0;
  margin: 0;
}

:global(.session-feedback-dialog .el-dialog__body) {
  padding: 0 22px 8px;
}

:global(.session-feedback-dialog .el-dialog__footer) {
  padding: 12px 22px 20px;
}

.sf-header {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 20px 22px 16px;
  background: linear-gradient(135deg, #eff6ff 0%, #f5f3ff 55%, #fff 100%);
  border-bottom: 1px solid #e8eef7;
}

.sf-header-icon {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  background: #fff;
  border: 1px solid #dbeafe;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(37, 99, 235, 0.1);
  flex-shrink: 0;
}

.sf-header-text { flex: 1; min-width: 0; }

.sf-title {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  color: #1e3a8a;
  letter-spacing: 0.02em;
}

.sf-subtitle {
  margin: 4px 0 0;
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}

.sf-close {
  border: none;
  background: rgba(255, 255, 255, 0.8);
  color: #94a3b8;
  width: 32px;
  height: 32px;
  border-radius: 10px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;
  &:hover { color: #2563eb; background: #fff; }
}

.sf-body { padding-top: 4px; }

.sf-section { margin-bottom: 18px; }

.sf-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #334155;
  margin-bottom: 10px;
  .req { color: #f43f5e; margin-right: 2px; }
  .opt { font-weight: 400; color: #94a3b8; font-size: 12px; }
}

.sf-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.sf-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border-radius: 20px;
  border: 1px solid #e2e8f0;
  background: #fafbfc;
  color: #475569;
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
  .chip-emoji { font-size: 14px; }
  &:hover {
    border-color: #93c5fd;
    background: #f0f9ff;
    color: #2563eb;
  }
  &.active {
    border-color: #2563eb;
    background: linear-gradient(135deg, #dbeafe, #e0e7ff);
    color: #1d4ed8;
    font-weight: 600;
    box-shadow: 0 2px 8px rgba(37, 99, 235, 0.15);
  }
}

.sf-stars-section {
  padding: 16px 18px 14px;
  background: linear-gradient(180deg, #fffbeb 0%, #fff 100%);
  border: 1px solid #fde68a;
  border-radius: 14px;
}

.sf-stars-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.sf-stars-line {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}

.sf-star-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 4px;
  border: none;
  background: transparent;
  border-radius: 10px;
  cursor: pointer;
  transition: transform 0.15s ease;
  .star-svg {
    display: block;
    filter: drop-shadow(0 1px 2px rgba(15, 23, 42, 0.06));
    transition: transform 0.15s ease;
  }
  &:hover {
    transform: scale(1.08);
    .star-svg { filter: drop-shadow(0 2px 6px rgba(245, 158, 11, 0.35)); }
  }
  &:active {
    transform: scale(0.96);
  }
}

.sf-star-caption {
  margin: 0;
  font-size: 13px;
  color: #78716c;
  text-align: center;
  min-height: 20px;
  strong { color: #b45309; font-weight: 600; }
  .caption-sub { color: #94a3b8; font-size: 12px; margin-left: 2px; }
  .caption-placeholder { color: #94a3b8; font-size: 12px; }
  .link-clear {
    margin-left: 10px;
    border: none;
    background: none;
    color: #2563eb;
    font-size: 12px;
    cursor: pointer;
    &:hover { text-decoration: underline; }
  }
}

.sf-editor {
  border: 1px solid #e2e8f0;
  border-radius: 14px;
  overflow: hidden;
  background: #fafbfc;
  transition: border-color 0.2s, box-shadow 0.2s;
  &:focus-within {
    border-color: #93c5fd;
    box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.08);
    background: #fff;
  }
}

:deep(.sf-textarea .el-textarea__inner) {
  border: none;
  box-shadow: none;
  background: transparent;
  padding: 12px 14px;
  font-size: 14px;
  line-height: 1.65;
  color: #1e293b;
  user-select: text;
  cursor: text;
}

.sf-upload-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-top: 1px dashed #e2e8f0;
  background: #f8fafc;
}

.sf-file-input {
  position: absolute;
  width: 0;
  height: 0;
  opacity: 0;
  pointer-events: none;
}

.sf-upload-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 5px 12px;
  border-radius: 10px;
  border: 1px solid #dbeafe;
  background: #fff;
  color: #2563eb;
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  .upload-count {
    font-size: 10px;
    color: #94a3b8;
    background: #f1f5f9;
    padding: 1px 6px;
    border-radius: 8px;
  }
  &:hover:not(:disabled) {
    background: #eff6ff;
    border-color: #2563eb;
    transform: translateY(-1px);
  }
  &:disabled { opacity: 0.5; cursor: not-allowed; }
}

.sf-upload-tip {
  font-size: 11px;
  color: #94a3b8;
}

.sf-previews {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 12px 12px;
  background: #fff;
}

.sf-preview-item {
  position: relative;
  width: 72px;
  height: 72px;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid #e2e8f0;
  cursor: zoom-in;
  &:hover .sf-preview-hint { opacity: 1; }
  :deep(.sf-preview-img) {
    width: 72px;
    height: 72px;
    display: block;
    .el-image__inner {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }
  }
}

.sf-preview-hint {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 2px 0;
  font-size: 10px;
  text-align: center;
  color: #fff;
  background: linear-gradient(transparent, rgba(15, 23, 42, 0.55));
  opacity: 0;
  transition: opacity 0.15s;
  pointer-events: none;
}

.sf-preview-remove {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 20px;
  height: 20px;
  border: none;
  border-radius: 50%;
  background: rgba(15, 23, 42, 0.65);
  color: #fff;
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
  &:hover { background: #ef4444; }
}

.sf-status {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #64748b;
  padding: 10px 12px;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  border-radius: 10px;
  .status-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #22c55e;
    flex-shrink: 0;
  }
}

.sf-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.sf-btn {
  padding: 9px 18px;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
  &.ghost {
    background: #f1f5f9;
    color: #64748b;
    &:hover { background: #e2e8f0; color: #475569; }
  }
  &.primary {
    background: linear-gradient(135deg, #2563eb, #6366f1);
    color: #fff;
    box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35);
    &:hover:not(:disabled) {
      transform: translateY(-1px);
      box-shadow: 0 6px 18px rgba(37, 99, 235, 0.4);
    }
    &:disabled { opacity: 0.65; cursor: not-allowed; }
  }
}

.btn-spin {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  margin-right: 6px;
  vertical-align: middle;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>

<style lang="scss">
.sf-exit-confirm-box.el-message-box {
  border-radius: 16px;
  padding: 22px 22px 18px;
  max-width: 420px;
  box-shadow: 0 20px 48px rgba(15, 23, 42, 0.14);

  .el-message-box__header {
    padding-bottom: 8px;
  }

  .el-message-box__title {
    font-size: 16px;
    font-weight: 700;
    color: #1e293b;
  }

  .el-message-box__status {
    display: none;
  }

  .el-message-box__content {
    padding: 8px 0 16px;
  }

  .el-message-box__message {
    padding-left: 0;
  }

  .el-message-box__btns {
    padding-top: 4px;
    .el-button {
      border-radius: 10px;
      padding: 8px 18px;
      font-weight: 600;
    }
    .el-button--default {
      color: #2563eb;
      border-color: #bfdbfe;
      background: #eff6ff;
      &:hover {
        background: #dbeafe;
        border-color: #93c5fd;
      }
    }
    .el-button--primary {
      background: linear-gradient(135deg, #64748b, #475569);
      border: none;
      box-shadow: none;
      &:hover {
        background: linear-gradient(135deg, #475569, #334155);
      }
    }
  }
}

.sf-exit-confirm-body {
  .sf-exit-lead {
    margin: 0 0 8px;
    font-size: 14px;
    font-weight: 600;
    color: #334155;
    line-height: 1.5;
  }

  .sf-exit-row {
    display: flex;
    align-items: flex-start;
    gap: 10px;
  }

  .sf-exit-icon {
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 22px;
    height: 22px;
    margin-top: 1px;
  }

  .sf-exit-desc {
    flex: 1;
    min-width: 0;
    margin: 0;
    font-size: 13px;
    color: #64748b;
    line-height: 1.65;
  }
}
</style>
