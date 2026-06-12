<template>
  <div class="feedback-page">
    <header class="page-header">
      <div>
        <h2 class="page-title">反馈管理</h2>
        <p class="page-desc">审核会话反馈、会话评价与手动反馈，及时回复用户</p>
      </div>
    </header>

    <section class="stats-row">
      <div v-for="s in statCards" :key="s.key" class="stat-card" :class="s.tone">
        <span class="stat-label">{{ s.label }}</span>
        <strong class="stat-value">{{ s.value }}</strong>
      </div>
    </section>

    <section class="table-card">
      <el-table :data="feedbacks" stripe v-loading="loading" empty-text="暂无反馈">
        <el-table-column label="反馈用户" width="100" prop="username" />
        <el-table-column label="来源" width="108">
          <template #default="{ row }">
            <span class="source-pill" :class="sourceTone(row)">{{ getSourceLabel(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="标题" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ getDisplayTitle(row) }}</template>
        </el-table-column>
        <el-table-column label="类型" width="120">
          <template #default="{ row }">
            <span class="type-pill" :class="getTypeTone(row)">{{ getTypeLabel(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="96">
          <template #default="{ row }">
            <span class="status-pill" :class="row.status">{{ STATUS_LABELS[row.status] }}</span>
          </template>
        </el-table-column>
        <el-table-column label="时间" width="168">
          <template #default="{ row }">{{ formatTime(row.createdAt) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="220" fixed="right">
          <template #default="{ row }">
            <button type="button" class="link-btn" @click="openDetail(row)">查看</button>
            <button v-if="row.status === 'pending'" type="button" class="link-btn primary" @click="openReply(row)">回复</button>
            <button v-if="row.status === 'replied'" type="button" class="link-btn muted" @click="handleClose(row)">关闭</button>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <!-- 详情 -->
    <el-dialog v-model="showDetail" width="640px" class="fb-detail-dialog" align-center destroy-on-close :show-close="false">
      <template #header>
        <div v-if="viewing" class="detail-header-bar">
          <div class="detail-head">
            <span class="source-pill" :class="sourceTone(viewing)">{{ getSourceLabel(viewing) }}</span>
            <span class="type-pill" :class="getTypeTone(viewing)">{{ getTypeLabel(viewing) }}</span>
            <span class="status-pill" :class="viewing.status">{{ STATUS_LABELS[viewing.status] }}</span>
          </div>
          <button type="button" class="dialog-close" @click="showDetail = false">&times;</button>
        </div>
      </template>
      <div v-if="viewing" class="detail-body">
        <h3 class="detail-title">{{ getDisplayTitle(viewing) }}</h3>
        <div class="detail-meta">
          <span class="meta-item">
            <span class="meta-label">反馈用户</span>
            <strong>{{ viewing.username }}</strong>
          </span>
          <span v-if="viewing.sessionId" class="meta-item clickable" @click="copyText(viewing.sessionId!)">
            <span class="meta-label">会话 ID</span>
            <strong class="mono">{{ viewing.sessionId }}</strong>
          </span>
          <span v-if="viewing.traceId" class="meta-item clickable" @click="copyText(viewing.traceId!)">
            <span class="meta-label">Trace</span>
            <strong class="mono">{{ viewing.traceId }}</strong>
          </span>
          <span class="meta-item">
            <span class="meta-label">提交时间</span>
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
          <div class="section-head">
            <span class="section-icon">📝</span>
            <strong>详细说明</strong>
          </div>
          <div class="detail-body-text">{{ parsedDetail.body }}</div>
        </div>
        <div v-else-if="!parsedDetail.fields.length" class="detail-section">
          <div class="section-head"><strong>反馈内容</strong></div>
          <div class="detail-body-text">{{ viewing.content }}</div>
        </div>

        <div v-if="detailImages.length" class="detail-section">
          <div class="section-head">
            <span class="section-icon">🖼</span>
            <strong>用户附图</strong>
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
          <strong>管理员回复</strong>
          <p>{{ viewing.adminReply }}</p>
        </div>
      </div>
      <template #footer>
        <div v-if="viewing" class="detail-footer">
          <button type="button" class="foot-btn" @click="showDetail = false">关闭</button>
          <button
            v-if="viewing.status === 'pending'"
            type="button"
            class="foot-btn primary"
            @click="openReplyFromDetail"
          >回复用户</button>
          <button
            v-if="viewing.status === 'replied'"
            type="button"
            class="foot-btn success"
            @click="handleClose(viewing)"
          >标记关闭</button>
        </div>
      </template>
    </el-dialog>

    <!-- 回复 -->
    <el-dialog v-model="showReply" width="560px" class="fb-reply-dialog" align-center destroy-on-close :show-close="false">
      <template #header>
        <div class="reply-banner">
          <div class="banner-icon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none"><path d="M21 11.5a8.38 8.38 0 01-.9 3.8 8.5 8.5 0 01-7.6 4.7 8.38 8.38 0 01-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 01-.9-3.8 8.5 8.5 0 014.7-7.6 8.38 8.38 0 013.8-.9h.5a8.48 8.48 0 018 8v.5z" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
          </div>
          <div class="banner-text">
            <h3>回复反馈</h3>
            <p>回复将通知用户，请清晰说明处理结果或后续计划</p>
          </div>
          <button type="button" class="dialog-close light" @click="showReply = false">&times;</button>
        </div>
      </template>

      <div v-if="viewing" class="reply-body">
        <div class="reply-context">
          <div class="ctx-top">
            <span class="source-pill sm" :class="sourceTone(viewing)">{{ getSourceLabel(viewing) }}</span>
            <span class="type-pill sm" :class="getTypeTone(viewing)">{{ getTypeLabel(viewing) }}</span>
          </div>
          <h4 class="ctx-title">{{ getDisplayTitle(viewing) }}</h4>
          <p v-if="replyExcerpt" class="ctx-excerpt">{{ replyExcerpt }}</p>
          <div class="ctx-meta">
            <span>{{ viewing.username }}</span>
            <span>{{ formatTime(viewing.createdAt) }}</span>
          </div>
        </div>

        <div class="form-block">
          <label class="form-label">回复内容 <span class="req">*</span></label>
          <div class="paste-zone">
            <textarea
              ref="replyRef"
              v-model="replyText"
              class="form-textarea"
              rows="5"
              placeholder="请输入回复内容，说明问题处理情况或改进计划…（支持 Ctrl+V 粘贴文字）"
              maxlength="2000"
            />
            <div class="paste-tip">
              <span>{{ replyText.length }}/2000</span>
              <span>支持 Ctrl+V 粘贴文字</span>
            </div>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="dialog-footer">
          <button type="button" class="foot-btn" @click="showReply = false">取消</button>
          <button type="button" class="foot-btn primary" :disabled="replying || !replyText.trim()" @click="handleReply">
            {{ replying ? '发送中…' : '发送回复' }}
          </button>
        </div>
      </template>
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
import { ref, computed, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { getFeedbackList, replyFeedback, updateFeedbackStatus } from '@/api/feedback'
import type { FeedbackInfo } from '@/api/feedback'
import {
  getSourceLabel,
  getTypeLabel,
  getDisplayTitle,
  getContentExcerpt,
  getTypeTone,
  parseFeedbackContent,
  STATUS_LABELS,
  SOURCE_TONE,
} from '@/utils/feedbackMeta'

const feedbacks = ref<FeedbackInfo[]>([])
const loading = ref(false)
const showDetail = ref(false)
const showReply = ref(false)
const showPreview = ref(false)
const previewIndex = ref(0)
const viewing = ref<FeedbackInfo | null>(null)
const replyText = ref('')
const replying = ref(false)
const replyRef = ref<HTMLTextAreaElement | null>(null)

const statCards = computed(() => {
  const list = feedbacks.value
  return [
    { key: 'total', label: '全部', value: list.length, tone: 'tone-blue' },
    { key: 'pending', label: '待回复', value: list.filter(f => f.status === 'pending').length, tone: 'tone-warn' },
    { key: 'session', label: '会话反馈', value: list.filter(f => f.source === 'session_chat').length, tone: 'tone-purple' },
    { key: 'eval', label: '会话评价', value: list.filter(f => f.source === 'agent_chat').length, tone: 'tone-green' },
  ]
})

const parsedDetail = computed(() => {
  if (!viewing.value) return { fields: [], body: '', imageUrls: [] }
  return parseFeedbackContent(viewing.value.content || '', viewing.value.attachments)
})

const detailImages = computed(() => parsedDetail.value.imageUrls)

const replyExcerpt = computed(() => {
  if (!viewing.value) return ''
  return getContentExcerpt(viewing.value, 96)
})

function sourceTone(row: FeedbackInfo) {
  return SOURCE_TONE[row.source || 'manual'] || 'tone-manual'
}

async function loadFeedbacks() {
  loading.value = true
  try {
    feedbacks.value = (await getFeedbackList()).items
  } catch {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

function openDetail(row: FeedbackInfo) {
  viewing.value = row
  showDetail.value = true
}

function openReply(row: FeedbackInfo) {
  viewing.value = row
  replyText.value = ''
  showReply.value = true
  nextTick(() => replyRef.value?.focus())
}

function openReplyFromDetail() {
  if (!viewing.value) return
  showDetail.value = false
  openReply(viewing.value)
}

async function handleReply() {
  if (!viewing.value || !replyText.value.trim()) {
    ElMessage.warning('请输入回复内容')
    return
  }
  replying.value = true
  try {
    await replyFeedback(viewing.value.id, replyText.value.trim())
    ElMessage.success('已回复')
    showReply.value = false
    replyText.value = ''
    loadFeedbacks()
  } catch {
    ElMessage.error('回复失败')
  } finally {
    replying.value = false
  }
}

async function handleClose(row: FeedbackInfo) {
  try {
    await updateFeedbackStatus(row.id, 'closed')
    ElMessage.success('已关闭')
    showDetail.value = false
    loadFeedbacks()
  } catch {
    ElMessage.error('操作失败')
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

onMounted(loadFeedbacks)
</script>

<style lang="scss" scoped>
.feedback-page { max-width: 1150px; margin: 0 auto; }

.page-header { margin-bottom: 18px; }
.page-title { font-size: 22px; font-weight: 700; color: #1e293b; margin: 0; }
.page-desc { font-size: 13px; color: #64748b; margin: 6px 0 0; }

.stats-row {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px;
}
.stat-card {
  padding: 14px 16px; border-radius: 12px; border: 1px solid #eef2f7; background: #fff;
}
.stat-label { display: block; font-size: 11px; color: #94a3b8; margin-bottom: 4px; }
.stat-value { font-size: 22px; font-weight: 800; }
.tone-blue .stat-value { color: #2563eb; }
.tone-purple .stat-value { color: #7c3aed; }
.tone-green .stat-value { color: #059669; }
.tone-warn .stat-value { color: #d97706; }

.table-card {
  background: #fff; border: 1px solid #e2e8f0; border-radius: 14px; padding: 16px;
}

.source-pill, .type-pill, .status-pill {
  display: inline-block; padding: 3px 10px; border-radius: 999px;
  font-size: 11px; font-weight: 700;
  &.sm { padding: 2px 8px; font-size: 10px; }
}
.source-pill.tone-manual { background: #f1f5f9; color: #64748b; }
.source-pill.tone-session { background: #eff6ff; color: #2563eb; }
.source-pill.tone-eval { background: #ecfdf5; color: #059669; }
.type-pill.type-default { background: #faf5ff; color: #7c3aed; }
.type-pill.type-ok { background: #ecfdf5; color: #059669; }
.type-pill.type-partial { background: #fef3c7; color: #b45309; }
.type-pill.type-fail { background: #fce7f3; color: #be185d; }
.status-pill.pending { background: #fffbeb; color: #d97706; border: 1px solid #fde68a; }
.status-pill.replied { background: #ecfdf5; color: #059669; border: 1px solid #a7f3d0; }
.status-pill.closed { background: #f1f5f9; color: #64748b; }

.link-btn {
  border: none; background: none; font-size: 12px; font-weight: 600; cursor: pointer; margin-right: 8px;
  color: #2563eb; transition: color 0.15s;
  &.primary { color: #059669; }
  &.muted { color: #94a3b8; }
  &:hover { text-decoration: underline; }
}

/* Detail dialog */
.detail-header-bar {
  display: flex; align-items: flex-start; justify-content: space-between; gap: 12px;
}
.detail-head { display: flex; gap: 8px; flex-wrap: wrap; flex: 1; }
.dialog-close {
  width: 32px; height: 32px; border: 1px solid #e2e8f0; border-radius: 8px;
  background: #f8fafc; font-size: 20px; cursor: pointer; color: #64748b; flex-shrink: 0;
  transition: all 0.15s;
  &.light { border-color: rgba(255,255,255,0.3); background: rgba(255,255,255,0.15); color: #fff; }
  &:hover { filter: brightness(0.95); border-color: #cbd5e1; }
}

.detail-title { margin: 0 0 10px; font-size: 20px; font-weight: 800; color: #1e293b; line-height: 1.35; }
.detail-meta {
  display: flex; gap: 16px; margin-bottom: 16px; flex-wrap: wrap;
}
.meta-item {
  display: flex; flex-direction: column; gap: 2px;
  &.clickable { cursor: pointer; }
  &.clickable:hover .mono { color: #2563eb; }
  .meta-label { font-size: 11px; color: #94a3b8; }
  strong { font-size: 13px; color: #334155; }
  .mono { font-family: ui-monospace, monospace; font-size: 11px; word-break: break-all; transition: color 0.15s; }
}

.info-grid {
  display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-bottom: 14px;
}
.info-cell {
  padding: 10px 12px; border-radius: 10px; border: 1px solid #eef2f7; background: #f8fafc;
  transition: all 0.15s;
  &.tone-highlight {
    background: linear-gradient(135deg, #faf5ff, #f5f3ff); border-color: #ddd6fe;
    .info-value { color: #6d28d9; font-weight: 700; }
  }
  &.tone-mono {
    cursor: pointer;
    .info-value { font-family: ui-monospace, monospace; font-size: 11px; color: #475569; word-break: break-all; }
    &:hover { border-color: #93c5fd; background: #eff6ff; }
    &:active { transform: scale(0.98); }
  }
  &:hover { border-color: #cbd5e1; }
}
.info-label { display: block; font-size: 10px; font-weight: 700; color: #94a3b8; letter-spacing: 0.04em; margin-bottom: 4px; }
.info-value { display: block; font-size: 13px; color: #334155; line-height: 1.4; }

.detail-section { margin-bottom: 14px; }
.section-head {
  display: flex; align-items: center; gap: 6px; margin-bottom: 8px;
  strong { font-size: 13px; color: #475569; }
  .section-icon { font-size: 14px; }
  .img-count { margin-left: auto; font-size: 11px; color: #94a3b8; font-weight: 600; }
}
.detail-body-text {
  white-space: pre-wrap; font-size: 14px; color: #334155; line-height: 1.75;
  background: linear-gradient(135deg, #f8fafc, #f1f5f9);
  padding: 14px 16px; border-radius: 12px; border: 1px solid #e2e8f0;
  border-left: 3px solid #6366f1;
}

.img-grid { display: flex; flex-wrap: wrap; gap: 10px; }
.thumb-wrap {
  position: relative; width: 56px; height: 56px; border-radius: 10px; overflow: hidden;
  border: 2px solid #cbd5e1; cursor: pointer; flex-shrink: 0;
  box-shadow: 0 2px 6px rgba(15,23,42,0.08);
  transition: transform 0.18s, border-color 0.18s, box-shadow 0.18s;
  &:hover {
    transform: scale(1.12); border-color: #2563eb;
    box-shadow: 0 4px 14px rgba(37,99,235,0.25); z-index: 1;
  }
  &:active { transform: scale(1.05); }
}
.thumb-img { width: 100%; height: 100%; object-fit: cover; display: block; }
.thumb-index {
  position: absolute; bottom: 2px; right: 2px;
  width: 16px; height: 16px; border-radius: 4px;
  background: rgba(15,23,42,0.65); color: #fff; font-size: 9px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
}

.admin-reply {
  margin-top: 4px; padding: 12px 14px; border-radius: 10px;
  background: linear-gradient(135deg, #f0fdf4, #ecfdf5); border-left: 3px solid #059669;
  strong { display: block; color: #059669; margin-bottom: 6px; font-size: 13px; }
  p { margin: 0; font-size: 13px; color: #475569; white-space: pre-wrap; line-height: 1.6; }
}

.detail-footer, .dialog-footer {
  display: flex; justify-content: flex-end; gap: 10px;
}
.foot-btn {
  padding: 8px 18px; border-radius: 8px; border: 1px solid #e2e8f0;
  background: #fff; font-size: 13px; font-weight: 600; color: #64748b; cursor: pointer;
  transition: background 0.15s, border-color 0.15s, color 0.15s, box-shadow 0.15s, transform 0.15s;
  &:hover:not(:disabled) { border-color: #cbd5e1; background: #f8fafc; color: #475569; }
  &.primary {
    background: #2563eb; border-color: #2563eb; color: #fff;
    &:hover:not(:disabled) {
      background: #1d4ed8; border-color: #1d4ed8; color: #fff;
      box-shadow: 0 4px 12px rgba(37, 99, 235, 0.28);
      transform: translateY(-1px);
    }
    &:active:not(:disabled) {
      background: #1e40af; border-color: #1e40af; color: #fff;
      transform: translateY(0); box-shadow: 0 2px 6px rgba(37, 99, 235, 0.2);
    }
  }
  &.success {
    background: #059669; border-color: #059669; color: #fff;
    &:hover:not(:disabled) {
      background: #047857; border-color: #047857; color: #fff;
      box-shadow: 0 4px 12px rgba(5, 150, 105, 0.28);
      transform: translateY(-1px);
    }
    &:active:not(:disabled) {
      background: #065f46; border-color: #065f46; color: #fff;
      transform: translateY(0);
    }
  }
  &:disabled { opacity: 0.6; cursor: not-allowed; }
}

/* Reply dialog */
.reply-banner {
  display: flex; align-items: flex-start; gap: 14px;
  padding: 18px 20px; margin: -16px -16px 0;
  background: linear-gradient(135deg, #059669 0%, #2563eb 100%);
  border-radius: 8px 8px 0 0; color: #fff;
}
.banner-icon {
  width: 42px; height: 42px; border-radius: 12px;
  background: rgba(255,255,255,0.18); display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.banner-text {
  flex: 1;
  h3 { margin: 0 0 4px; font-size: 17px; font-weight: 700; }
  p { margin: 0; font-size: 12px; opacity: 0.88; }
}

.reply-body { padding-top: 4px; }
.reply-context {
  padding: 12px 14px; border-radius: 12px; margin-bottom: 16px;
  background: linear-gradient(135deg, #f8fafc, #f1f5f9); border: 1px solid #e2e8f0;
  transition: border-color 0.15s;
  &:hover { border-color: #cbd5e1; }
}
.ctx-top { display: flex; gap: 6px; margin-bottom: 6px; }
.ctx-title { margin: 0 0 4px; font-size: 14px; font-weight: 700; color: #1e293b; }
.ctx-excerpt { margin: 0 0 8px; font-size: 12px; color: #64748b; line-height: 1.5; }
.ctx-meta {
  display: flex; gap: 12px; font-size: 11px; color: #94a3b8; font-weight: 600;
}

.form-block { margin-bottom: 0; }
.form-label { display: block; font-size: 12px; font-weight: 700; color: #475569; margin-bottom: 8px; }
.req { color: #ef4444; }
.paste-zone {
  border: 1px dashed #cbd5e1; border-radius: 12px; padding: 2px; background: #fafbfc;
  transition: border-color 0.15s, background 0.15s;
  &:focus-within { border-color: #93c5fd; background: #f8faff; }
}
.form-textarea {
  width: 100%; border: none; background: transparent; border-radius: 10px;
  padding: 10px 12px; font-size: 13px; color: #1e293b; outline: none;
  box-sizing: border-box; resize: vertical; min-height: 120px; font-family: inherit;
}
.paste-tip {
  display: flex; justify-content: space-between; align-items: center;
  padding: 6px 12px 8px; font-size: 11px; color: #94a3b8;
}

@media (max-width: 768px) {
  .stats-row { grid-template-columns: repeat(2, 1fr); }
  .info-grid { grid-template-columns: 1fr; }
}
</style>

<style lang="scss">
.fb-detail-dialog .el-dialog__header,
.fb-reply-dialog .el-dialog__header { padding: 16px 16px 0; margin-right: 0; }
.fb-detail-dialog .el-dialog,
.fb-reply-dialog .el-dialog { border-radius: 14px; overflow: hidden; }
.fb-reply-dialog .el-dialog__body { padding-top: 16px; }
</style>
