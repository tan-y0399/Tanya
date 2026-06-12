<template>
  <div class="feedback-page">
    <FeedbackPageBackground />

    <div class="feedback-content">
      <FeedbackPageHeader @create="openCreate" />

      <FeedbackStatsPanel
        v-model:filter="sourceFilter"
        :feedbacks="feedbacks"
      />

      <section class="list-section glass-panel" v-loading="loading" aria-label="反馈列表">
        <div class="list-head">
          <span class="list-label">FEED · 反馈流</span>
          <span class="list-hint">点击条目查看详情 · 支持 Trace / Session 追溯</span>
          <span class="list-count">共 {{ filteredFeedbacks.length }} 条</span>
        </div>

        <div v-if="!filteredFeedbacks.length && !loading" class="empty-state">
          <div class="empty-icon">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none">
              <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" stroke="#94a3b8" stroke-width="1.5" stroke-linecap="round" />
            </svg>
          </div>
          <p>暂无反馈记录</p>
          <button type="button" class="empty-btn" @click="openCreate">提交第一条反馈</button>
        </div>

        <div v-else class="fb-list">
          <FeedbackListItem
            v-for="row in filteredFeedbacks"
            :key="row.id"
            :row="row"
            @select="openDetail"
          />
        </div>
      </section>
    </div>

    <!-- 提交反馈 -->
    <el-dialog v-model="showCreate" width="600px" :show-close="false" class="fb-submit-dialog" align-center destroy-on-close>
      <template #header>
        <div class="submit-banner">
          <div class="banner-icon">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
              <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
            </svg>
          </div>
          <div class="banner-text">
            <span class="banner-code">SUBMIT · 手动反馈</span>
            <h3>提交反馈</h3>
            <p>请尽量描述场景与期望，便于管理员快速定位问题</p>
          </div>
          <button type="button" class="dialog-close light" @click="showCreate = false">&times;</button>
        </div>
      </template>
      <div class="form-body">
        <div class="form-block">
          <label class="form-label">反馈类型 · TYPE</label>
          <div class="chip-row">
            <button
              v-for="c in MANUAL_CATEGORIES"
              :key="c.value"
              type="button"
              class="chip-btn"
              :class="{ active: newFb.category === c.value }"
              @click="newFb.category = c.value"
            >{{ c.label }}</button>
          </div>
        </div>
        <div class="form-block">
          <label class="form-label">标题 · TITLE <span class="req">*</span></label>
          <input v-model="newFb.title" class="form-input" placeholder="简要概括您的问题或建议" maxlength="100" />
        </div>
        <div class="form-block">
          <label class="form-label">详细说明 · BODY <span class="req">*</span></label>
          <div class="paste-zone" @paste.capture.stop="onFormPaste">
            <textarea
              ref="contentRef"
              v-model="newFb.content"
              class="form-textarea"
              rows="5"
              placeholder="请描述问题现象、复现步骤、期望结果…（支持 Ctrl+V 粘贴文字与截图）"
              maxlength="2000"
            />
            <div class="paste-tip">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                <rect x="9" y="9" width="13" height="13" rx="2" stroke="currentColor" stroke-width="2" />
                <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" stroke="currentColor" stroke-width="2" />
              </svg>
              支持 Ctrl+V 粘贴文字与截图，单次粘贴仅执行一次
            </div>
          </div>
        </div>
        <div class="form-block">
          <label class="form-label">附图 · ATTACH（可选，最多 4 张）</label>
          <div class="upload-row">
            <label class="upload-btn">
              <input type="file" accept="image/*" multiple hidden @change="onPickImages" />
              + 添加图片
            </label>
            <span class="upload-hint">JPG/PNG ≤ 2MB · 也可 Ctrl+V 粘贴截图</span>
          </div>
          <div v-if="uploadPreviews.length" class="preview-grid">
            <div v-for="(p, i) in uploadPreviews" :key="p.url" class="preview-item">
              <img :src="p.url" alt="" />
              <button type="button" class="preview-remove" @click="removeImage(i)">&times;</button>
            </div>
          </div>
        </div>
      </div>
      <template #footer>
        <div class="dialog-footer">
          <button type="button" class="foot-btn" @click="showCreate = false">取消</button>
          <button type="button" class="foot-btn primary" :disabled="submitting" @click="submitFeedback">
            {{ submitting ? '提交中…' : '提交反馈' }}
          </button>
        </div>
      </template>
    </el-dialog>

    <!-- 详情 -->
    <el-dialog v-model="showDetail" width="640px" class="fb-detail-dialog" align-center destroy-on-close>
      <template #header>
        <div v-if="viewing" class="detail-head">
          <span class="source-pill" :class="sourceTone(viewing)">{{ getSourceLabel(viewing) }}</span>
          <span class="type-pill" :class="getTypeTone(viewing)">{{ getTypeLabel(viewing) }}</span>
          <span class="status-pill" :class="viewing.status">{{ STATUS_LABELS[viewing.status] }}</span>
        </div>
      </template>
      <div v-if="viewing" class="detail-body">
        <span class="detail-id">ID {{ viewing.id }}</span>
        <h3 class="detail-title">{{ getDisplayTitle(viewing) }}</h3>
        <div class="detail-meta">
          <span class="meta-item">
            <span class="meta-label">USER</span>
            <strong>{{ viewing.username }}</strong>
          </span>
          <span class="meta-item">
            <span class="meta-label">TIME</span>
            <strong>{{ formatTime(viewing.createdAt) }}</strong>
          </span>
        </div>

        <div v-if="parsedDetail.fields.length" class="info-grid">
          <div
            v-for="(f, i) in parsedDetail.fields"
            :key="i"
            class="info-cell"
            :class="[`tone-${f.tone || 'default'}`, { clickable: f.tone === 'mono' }]"
            @click="f.tone === 'mono' && copyText(f.value)"
          >
            <span class="info-label">{{ f.label }}</span>
            <span class="info-value">{{ f.value }}</span>
          </div>
        </div>

        <div v-if="parsedDetail.body" class="detail-section">
          <div class="section-head"><span class="sec-code">BODY</span><strong>详细说明</strong></div>
          <div class="detail-body-text">{{ parsedDetail.body }}</div>
        </div>
        <div v-else-if="!parsedDetail.fields.length" class="detail-section">
          <div class="section-head"><span class="sec-code">BODY</span><strong>反馈内容</strong></div>
          <div class="detail-body-text">{{ viewing.content }}</div>
        </div>

        <div v-if="detailImages.length" class="detail-section">
          <div class="section-head">
            <span class="sec-code">IMG</span>
            <strong>附图</strong>
            <span class="img-count">{{ detailImages.length }} 张</span>
          </div>
          <div class="img-grid">
            <div
              v-for="(url, i) in detailImages"
              :key="url"
              class="thumb-wrap"
              @click="previewIndex = i; showPreview = true"
            >
              <img :src="url" alt="" class="thumb-img" />
              <span class="thumb-index">{{ i + 1 }}</span>
            </div>
          </div>
        </div>

        <div v-if="viewing.adminReply" class="admin-reply">
          <span class="sec-code">REPLY</span>
          <strong>管理员回复</strong>
          <p>{{ viewing.adminReply }}</p>
        </div>
      </div>
    </el-dialog>

    <el-image-viewer
      v-if="showPreview"
      :url-list="detailImages"
      :initial-index="previewIndex"
      @close="showPreview = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getFeedbackList, createFeedback } from '@/api/feedback'
import type { FeedbackInfo } from '@/api/feedback'
import FeedbackPageBackground from '@/components/feedback/FeedbackPageBackground.vue'
import FeedbackPageHeader from '@/components/feedback/FeedbackPageHeader.vue'
import FeedbackStatsPanel from '@/components/feedback/FeedbackStatsPanel.vue'
import FeedbackListItem from '@/components/feedback/FeedbackListItem.vue'
import {
  getSourceLabel,
  getTypeLabel,
  getDisplayTitle,
  getTypeTone,
  parseFeedbackContent,
  STATUS_LABELS,
  MANUAL_CATEGORIES,
  SOURCE_TONE,
} from '@/utils/feedbackMeta'
import {
  collectClipboardImages,
  shouldSkipDuplicatePaste,
  uploadFeedbackImages,
} from '@/utils/feedbackPaste'

const feedbacks = ref<FeedbackInfo[]>([])
const loading = ref(false)
const showCreate = ref(false)
const showDetail = ref(false)
const showPreview = ref(false)
const previewIndex = ref(0)
const viewing = ref<FeedbackInfo | null>(null)
const submitting = ref(false)
const uploadingPaste = ref(false)
const uploadPreviews = ref<{ url: string; name: string }[]>([])
const sourceFilter = ref<'all' | 'session_chat' | 'agent_chat' | 'manual' | 'pending'>('all')
const contentRef = ref<HTMLTextAreaElement | null>(null)

const newFb = reactive({
  title: '',
  content: '',
  category: 'general',
})

const filteredFeedbacks = computed(() => {
  const list = feedbacks.value
  if (sourceFilter.value === 'all') return list
  if (sourceFilter.value === 'pending') return list.filter(f => f.status === 'pending')
  return list.filter(f => f.source === sourceFilter.value)
})

const parsedDetail = computed(() => {
  if (!viewing.value) return { fields: [], body: '', imageUrls: [] }
  return parseFeedbackContent(viewing.value.content || '', viewing.value.attachments)
})

const detailImages = computed(() => parsedDetail.value.imageUrls)

function sourceTone(row: FeedbackInfo) {
  return SOURCE_TONE[row.source || 'manual'] || 'tone-manual'
}

async function load() {
  loading.value = true
  try {
    feedbacks.value = (await getFeedbackList()).items
  } catch {
    ElMessage.error('加载反馈列表失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  showCreate.value = true
}

function openDetail(row: FeedbackInfo) {
  viewing.value = row
  showDetail.value = true
}

async function onPickImages(e: Event) {
  const input = e.target as HTMLInputElement
  const files = input.files
  if (!files?.length) return
  try {
    const uploaded = await uploadFeedbackImages(Array.from(files), uploadPreviews.value.length)
    uploadPreviews.value.push(...uploaded)
  } catch (err) {
    ElMessage.warning(err instanceof Error ? err.message : '图片上传失败')
  }
  input.value = ''
}

function removeImage(idx: number) {
  uploadPreviews.value.splice(idx, 1)
}

async function onFormPaste(ev: ClipboardEvent) {
  const data = ev.clipboardData
  if (!data) return

  const imageFiles = collectClipboardImages(data)
  if (!imageFiles.length) return

  ev.preventDefault()
  if (uploadingPaste.value) return

  const sig = imageFiles.map(f => `${f.type}:${f.size}:${f.lastModified || 0}`).join('|')
  if (shouldSkipDuplicatePaste(sig)) return

  uploadingPaste.value = true
  try {
    const uploaded = await uploadFeedbackImages(imageFiles, uploadPreviews.value.length)
    if (uploaded.length) {
      uploadPreviews.value.push(...uploaded)
      ElMessage.success(`已粘贴 ${uploaded.length} 张图片`)
    } else {
      ElMessage.warning('最多上传 4 张图片')
    }
  } catch (err) {
    ElMessage.warning(err instanceof Error ? err.message : '图片粘贴失败')
  } finally {
    uploadingPaste.value = false
  }
}

async function submitFeedback() {
  if (!newFb.title.trim()) { ElMessage.warning('请输入标题'); return }
  if (!newFb.content.trim()) { ElMessage.warning('请填写详细说明'); return }
  submitting.value = true
  try {
    await createFeedback({
      title: newFb.title.trim(),
      content: newFb.content.trim(),
      category: newFb.category,
      images: uploadPreviews.value.map(p => p.url),
    })
    ElMessage.success('反馈已提交')
    showCreate.value = false
    newFb.title = ''
    newFb.content = ''
    newFb.category = 'general'
    uploadPreviews.value = []
    load()
  } catch {
    ElMessage.error('提交失败')
  } finally {
    submitting.value = false
  }
}

function copyText(text: string) {
  navigator.clipboard?.writeText(text).then(() => {
    ElMessage.success('已复制')
  }).catch(() => {})
}

function formatTime(t: string) {
  return t ? new Date(t).toLocaleString('zh-CN') : ''
}

onMounted(load)
</script>

<style lang="scss" scoped>
.feedback-page {
  position: relative;
  min-height: 100%;
  overflow-x: hidden;
}

.feedback-content {
  position: relative;
  z-index: 1;
  max-width: 1100px;
  margin: 0 auto;
  padding: 24px 32px 40px;
  width: 100%;
  min-width: 0;
}

.list-section {
  padding: 14px 16px 16px;
  min-height: 120px;
  border-color: rgba(124, 58, 237, 0.1) !important;
}

.list-head {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.list-label {
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: #94a3b8;
}

.list-hint {
  font-size: 11px;
  color: #94a3b8;
  flex: 1;
}

.list-count {
  font-size: 11px;
  font-weight: 700;
  color: #64748b;
}

.fb-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.empty-state {
  text-align: center;
  padding: 48px 20px;
  color: #94a3b8;

  p { margin: 8px 0 14px; font-size: 14px; }
}

.empty-btn {
  padding: 8px 16px;
  border-radius: 8px;
  border: 1px solid #7c3aed;
  background: rgba(124, 58, 237, 0.06);
  color: #7c3aed;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;

  &:hover { background: rgba(124, 58, 237, 0.12); }
}

/* Dialog shared styles */
.submit-banner {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 18px 20px;
  margin: -16px -16px 0;
  background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%);
  border-radius: 8px 8px 0 0;
  color: #fff;
}

.banner-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.18);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.banner-text {
  flex: 1;

  .banner-code {
    display: block;
    font-size: 9px;
    font-weight: 800;
    letter-spacing: 0.08em;
    opacity: 0.85;
    margin-bottom: 4px;
  }

  h3 { margin: 0 0 4px; font-size: 18px; font-weight: 700; }
  p { margin: 0; font-size: 12px; opacity: 0.85; }
}

.dialog-close {
  width: 32px;
  height: 32px;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  background: #f8fafc;
  font-size: 20px;
  cursor: pointer;
  color: #64748b;
  flex-shrink: 0;

  &.light {
    border-color: rgba(255, 255, 255, 0.3);
    background: rgba(255, 255, 255, 0.15);
    color: #fff;
  }
}

.form-body { padding-top: 4px; }
.form-block { margin-bottom: 16px; }
.form-label {
  display: block;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 0.04em;
  color: #475569;
  margin-bottom: 8px;
}
.req { color: #ef4444; }

.form-input, .form-textarea {
  width: 100%;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 10px 12px;
  font-size: 13px;
  color: #1e293b;
  outline: none;
  box-sizing: border-box;
  transition: border-color 0.15s, box-shadow 0.15s;

  &:focus {
    border-color: #7c3aed;
    box-shadow: 0 0 0 3px rgba(124, 58, 237, 0.1);
  }
}

.form-textarea {
  resize: vertical;
  min-height: 110px;
  font-family: inherit;
}

.paste-zone {
  border: 1px dashed #cbd5e1;
  border-radius: 12px;
  padding: 2px;
  background: #fafbfc;

  &:focus-within {
    border-color: #a78bfa;
    background: #faf5ff;
  }

  .form-textarea {
    border: none;
    background: transparent;
    box-shadow: none !important;
  }
}

.paste-tip {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px 8px;
  font-size: 11px;
  color: #94a3b8;
}

.chip-row { display: flex; flex-wrap: wrap; gap: 8px; }
.chip-btn {
  padding: 6px 14px;
  border-radius: 999px;
  border: 1px solid #e2e8f0;
  background: #fff;
  font-size: 12px;
  color: #64748b;
  cursor: pointer;
  transition: all 0.15s;

  &:hover { border-color: #a78bfa; color: #7c3aed; }
  &.active {
    background: rgba(124, 58, 237, 0.08);
    border-color: #7c3aed;
    color: #7c3aed;
    font-weight: 600;
  }
}

.upload-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.upload-btn {
  padding: 6px 14px;
  border-radius: 8px;
  border: 1px dashed #a78bfa;
  background: #faf5ff;
  color: #7c3aed;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.upload-hint { font-size: 11px; color: #94a3b8; }

.preview-grid { display: flex; flex-wrap: wrap; gap: 8px; }
.preview-item {
  position: relative;
  width: 64px;
  height: 64px;
  border-radius: 10px;
  overflow: hidden;
  border: 2px solid #e2e8f0;

  img { width: 100%; height: 100%; object-fit: cover; }
}

.preview-remove {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 18px;
  height: 18px;
  border: none;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  cursor: pointer;
  font-size: 12px;
}

.dialog-footer { display: flex; justify-content: flex-end; gap: 10px; }
.foot-btn {
  padding: 8px 18px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #fff;
  font-size: 13px;
  font-weight: 600;
  color: #64748b;
  cursor: pointer;

  &.primary {
    background: linear-gradient(135deg, #2563eb, #7c3aed);
    border: none;
    color: #fff;
  }

  &:disabled { opacity: 0.6; cursor: not-allowed; }
}

.detail-head { display: flex; gap: 8px; flex-wrap: wrap; }

.source-pill, .type-pill, .status-pill {
  font-size: 10px;
  font-weight: 700;
  padding: 3px 10px;
  border-radius: 999px;
}

.source-pill.tone-manual { background: #f1f5f9; color: #64748b; }
.source-pill.tone-session { background: #eff6ff; color: #2563eb; }
.source-pill.tone-eval { background: #ecfdf5; color: #059669; }
.type-pill.type-default { background: #faf5ff; color: #7c3aed; }
.type-pill.type-ok { background: #ecfdf5; color: #059669; }
.type-pill.type-partial { background: #fef3c7; color: #b45309; }
.type-pill.type-fail { background: #fce7f3; color: #be185d; }
.status-pill.pending { background: #fffbeb; color: #d97706; }
.status-pill.replied { background: #ecfdf5; color: #059669; }
.status-pill.closed { background: #f1f5f9; color: #64748b; }

.detail-id {
  display: inline-block;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: #94a3b8;
  margin-bottom: 6px;
}

.detail-title {
  margin: 0 0 10px;
  font-size: 20px;
  font-weight: 800;
  color: #0f172a;
  line-height: 1.35;
}

.detail-meta {
  display: flex;
  gap: 20px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.meta-item {
  display: flex;
  flex-direction: column;
  gap: 2px;

  .meta-label {
    font-size: 9px;
    font-weight: 800;
    letter-spacing: 0.06em;
    color: #94a3b8;
  }

  strong { font-size: 13px; color: #334155; }
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  margin-bottom: 14px;
}

.info-cell {
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid #eef2f7;
  background: #f8fafc;

  &.tone-highlight {
    background: linear-gradient(135deg, #faf5ff, #f5f3ff);
    border-color: #ddd6fe;
    .info-value { color: #6d28d9; font-weight: 700; }
  }

  &.tone-mono {
    cursor: pointer;
    .info-value {
      font-family: ui-monospace, monospace;
      font-size: 11px;
      word-break: break-all;
    }
    &:hover { border-color: #a78bfa; background: #faf5ff; }
  }
}

.info-label {
  display: block;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.06em;
  color: #94a3b8;
  margin-bottom: 4px;
}

.info-value {
  display: block;
  font-size: 13px;
  color: #334155;
  line-height: 1.4;
}

.detail-section { margin-bottom: 14px; }

.section-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;

  strong { font-size: 13px; color: #475569; }
  .img-count { margin-left: auto; font-size: 11px; color: #94a3b8; }
}

.sec-code {
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.06em;
  color: #94a3b8;
  padding: 2px 6px;
  border-radius: 4px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.detail-body-text {
  white-space: pre-wrap;
  font-size: 14px;
  color: #334155;
  line-height: 1.75;
  background: linear-gradient(135deg, #f8fafc, #f1f5f9);
  padding: 14px 16px;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  border-left: 3px solid #7c3aed;
}

.img-grid { display: flex; flex-wrap: wrap; gap: 10px; }

.thumb-wrap {
  position: relative;
  width: 56px;
  height: 56px;
  border-radius: 10px;
  overflow: hidden;
  border: 2px solid #cbd5e1;
  cursor: pointer;

  &:hover {
    transform: scale(1.08);
    border-color: #7c3aed;
  }
}

.thumb-img { width: 100%; height: 100%; object-fit: cover; display: block; }

.thumb-index {
  position: absolute;
  bottom: 2px;
  right: 2px;
  width: 16px;
  height: 16px;
  border-radius: 4px;
  background: rgba(15, 23, 42, 0.65);
  color: #fff;
  font-size: 9px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.admin-reply {
  margin-top: 4px;
  padding: 12px 14px;
  border-radius: 10px;
  background: linear-gradient(135deg, #f0fdf4, #ecfdf5);
  border-left: 3px solid #059669;

  strong { display: block; color: #059669; margin: 6px 0; font-size: 13px; }
  p { margin: 0; font-size: 13px; color: #475569; white-space: pre-wrap; line-height: 1.6; }
}

@media (max-width: 768px) {
  .info-grid { grid-template-columns: 1fr; }
}
</style>

<style lang="scss">
.fb-submit-dialog .el-dialog__header,
.fb-detail-dialog .el-dialog__header { padding: 0; margin-right: 0; }
.fb-submit-dialog .el-dialog__body { padding-top: 16px; }
.fb-submit-dialog .el-dialog,
.fb-detail-dialog .el-dialog { border-radius: 14px; overflow: hidden; }
</style>
