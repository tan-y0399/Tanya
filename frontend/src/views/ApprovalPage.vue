<template>
  <div class="approval-page">
    <header class="page-header">
      <div class="header-main">
        <span class="page-tag">APPROVAL</span>
        <h2 class="page-title">审批管理</h2>
        <p class="page-desc">L4/L5 高危运维操作的人工审批闸门 · 超时自动拒绝 · 全链路可追溯</p>
      </div>
      <div v-if="isAdmin" class="role-badge admin">管理员模式</div>
      <div v-else class="role-badge user">仅可查看 · 审批需管理员</div>
    </header>

    <ApprovalModuleHub />

    <section class="stats-grid">
      <div
        v-for="card in statCards"
        :key="card.key"
        class="stat-card"
        :style="{ '--card-accent': statAccent(card.tone) }"
      >
        <div class="card-glow" aria-hidden="true"></div>
        <span class="stat-code">{{ card.key.toUpperCase() }}</span>
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ card.value }}</strong>
        <span class="stat-hint">{{ card.hint }}</span>
      </div>
    </section>

    <div v-if="lastExecutionResult" class="execution-result">
      <div class="exec-head">
        <span :class="lastExecutionResult.success ? 'text-green' : 'text-red'">
          {{ lastExecutionResult.success ? '✓ 命令已执行成功' : '✕ 命令执行失败' }}
        </span>
        <button class="exec-close" @click="lastExecutionResult = null">&times;</button>
      </div>
      <pre v-if="lastExecutionResult.result" class="exec-output">{{ JSON.stringify(lastExecutionResult.result, null, 2) }}</pre>
    </div>

    <div class="tabs-row">
      <button class="tab-btn" :class="{ active: tab === 'pending' }" @click="tab = 'pending'">
        <span class="tab-icon">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
            <circle cx="12" cy="12" r="8" stroke="currentColor" stroke-width="1.8" />
            <path d="M12 7v5l3 2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
          </svg>
        </span>
        待审批
        <span v-if="pendingTotal" class="tab-badge">{{ pendingTotal }}</span>
      </button>
      <button class="tab-btn" :class="{ active: tab === 'history' }" @click="tab = 'history'">
        <span class="tab-icon">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
            <path d="M8 6h12M8 12h12M8 18h12M4 6h.01M4 12h.01M4 18h.01" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
          </svg>
        </span>
        审批历史
      </button>
    </div>

    <section class="content-panel">
      <div class="section-head">
        <div>
          <h3 class="section-title">{{ tab === 'pending' ? '待审批队列' : '审批历史记录' }}</h3>
          <p class="section-tip">
            <template v-if="tab === 'pending'">
              共 {{ pendingTotal }} 条待处理 · 管理员需在 120 秒内完成决策
            </template>
            <template v-else>
              共 {{ historyTotal }} 条历史记录 · 点击卡片查看详情
            </template>
          </p>
        </div>
      </div>

      <div v-if="tab === 'pending'" class="flow-list">
        <ApprovalFlowCard
          v-for="ap in pendingItems"
          :key="ap.id"
          :item="ap"
          mode="pending"
          :is-admin="isAdmin"
          :approving="approving === ap.id"
          @open="openDetail"
          @detail="openDetail"
          @approve="handleApprove"
          @reject="handleReject"
          @goto-chat="gotoChat"
        />
        <div v-if="!pendingItems.length" class="empty-state">
          <div class="empty-icon">✓</div>
          <p>暂无待审批操作</p>
          <span class="empty-hint">Agent 发起 L4/L5 高危命令时会在此等待审批</span>
        </div>
      </div>

      <div v-else class="flow-list">
        <ApprovalFlowCard
          v-for="row in historyItems"
          :key="row.id"
          :item="row"
          mode="history"
          :is-admin="isAdmin"
          @open="openDetail"
          @detail="openDetail"
          @goto-chat="gotoChat"
          @action="handleRowAction"
        />
        <div v-if="!historyItems.length" class="empty-state">
          <p>暂无审批历史</p>
        </div>
        <div v-if="historyTotal > historyPageSize" class="pagination-row">
          <el-pagination
            :current-page="historyPage"
            :page-size="historyPageSize"
            :total="historyTotal"
            layout="prev, pager, next"
            background
            @update:current-page="onHistoryPage"
          />
        </div>
      </div>
    </section>

    <ApprovalDetailDrawer
      v-model:visible="detailVisible"
      :approval-id="selectedId"
      @goto-chat="gotoChat"
    />

    <el-dialog
      v-model="editVisible"
      title="修改审批记录"
      width="480px"
      :close-on-click-modal="false"
      class="approval-edit-dialog"
    >
      <el-form v-if="editForm" label-position="top" class="edit-form">
        <el-form-item label="风险等级">
          <el-select v-model="editForm.riskLevel" style="width: 100%">
            <el-option label="L3" value="L3" />
            <el-option label="L4" value="L4" />
            <el-option label="L5" value="L5" />
          </el-select>
        </el-form-item>
        <el-form-item label="风险描述">
          <el-input v-model="editForm.detail" type="textarea" :rows="3" maxlength="500" show-word-limit />
        </el-form-item>
        <el-form-item label="审批意见">
          <el-input v-model="editForm.comment" type="textarea" :rows="3" maxlength="500" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <button type="button" class="dialog-btn" @click="editVisible = false">取消</button>
        <button type="button" class="dialog-btn primary" :disabled="saving" @click="saveEdit">
          {{ saving ? '保存中…' : '保存' }}
        </button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="deleteVisible"
      width="440px"
      :show-close="false"
      :close-on-click-modal="false"
      class="approval-delete-dialog"
      align-center
    >
      <div class="delete-dialog-body">
        <div class="delete-icon-wrap">
          <svg viewBox="0 0 24 24" fill="none" class="delete-icon">
            <path d="M12 9v4m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
        <h3 class="delete-title">确认删除审批记录</h3>
        <p class="delete-desc">删除后无法恢复，关联的待执行状态也将一并清除。</p>

        <div v-if="deleteTarget" class="delete-preview">
          <div class="preview-head">
            <span class="source-pill sm">{{ deleteTarget.sourceType || 'Agent 对话' }}</span>
            <span class="result-pill" :class="approvalResultClass(deleteTarget.status)">
              {{ approvalResultLabel(deleteTarget.status) }}
            </span>
            <span class="risk-tag" :class="riskClass(deleteTarget.riskLevel)">{{ deleteTarget.riskLevel }}</span>
          </div>
          <p class="preview-event">{{ deleteTarget.eventSummary || deleteTarget.detail || deleteTarget.toolName }}</p>
          <code v-if="deleteTarget.commandPreview" class="preview-cmd">{{ deleteTarget.commandPreview }}</code>
          <div class="preview-meta">
            <span>{{ formatUser(deleteTarget) }}</span>
            <span>{{ formatTime(deleteTarget.resolvedAt || deleteTarget.requestedAt) }}</span>
          </div>
        </div>
      </div>
      <template #footer>
        <div class="delete-footer">
          <button type="button" class="dialog-btn" :disabled="deleting" @click="deleteVisible = false">取消</button>
          <button type="button" class="dialog-btn danger" :disabled="deleting" @click="confirmDelete">
            {{ deleting ? '删除中…' : '确认删除' }}
          </button>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useApprovalStore } from '@/stores/approval'
import ApprovalModuleHub from '@/components/approval/ApprovalModuleHub.vue'
import ApprovalFlowCard from '@/components/approval/ApprovalFlowCard.vue'
import ApprovalDetailDrawer from '@/components/approval/ApprovalDetailDrawer.vue'
import {
  approvalResultClass,
  approvalResultLabel,
  riskClass,
  STAT_ACCENTS,
} from '@/components/approval/approvalMeta'
import {
  getApprovalHistory,
  getApprovalById,
  approveApproval,
  rejectApproval,
  updateApproval,
  deleteApproval,
} from '@/api/approval'
import { getMessages } from '@/api/chat'
import { formatTime } from '@/utils'
import { ElMessage } from 'element-plus'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const approvalStore = useApprovalStore()
const isAdmin = computed(() => userStore.userInfo?.role === 'admin')

const tab = ref<'pending' | 'history'>('pending')
const pendingItems = computed(() => approvalStore.pendingItems)
const pendingTotal = computed(() => approvalStore.pendingTotal)
const stats = computed(() => approvalStore.stats)
const historyItems = ref<any[]>([])
const historyTotal = ref(0)
const historyPage = ref(1)
const historyPageSize = 20
const lastExecutionResult = ref<any>(null)
const approving = ref<string | null>(null)
const detailVisible = ref(false)
const selectedId = ref<string | null>(null)
const editVisible = ref(false)
const editForm = ref<{ id: string; detail: string; comment: string; riskLevel: string } | null>(null)
const saving = ref(false)
const deleteVisible = ref(false)
const deleteTarget = ref<any>(null)
const deleting = ref(false)

const statCards = computed(() => [
  { key: 'pending', label: '待审批', value: stats.value.pending ?? pendingTotal.value, hint: '需尽快处理', tone: 'tone-warn' },
  { key: 'approved', label: '已通过', value: stats.value.approved ?? 0, hint: '累计', tone: 'tone-ok' },
  { key: 'rejected', label: '已拒绝', value: stats.value.rejected ?? 0, hint: '累计', tone: 'tone-fail' },
  { key: 'timeout', label: '已超时', value: stats.value.timeout ?? 0, hint: '累计', tone: 'tone-muted' },
  { key: 'today', label: '今日申请', value: stats.value.today ?? 0, hint: '新发起', tone: 'tone-blue' },
])

function statAccent(tone: string) {
  return STAT_ACCENTS[tone] || '#64748b'
}

function formatUser(row: any) {
  const name = row.requestedBy || row.requestedByUsername
  if (name && row.requestedByRole) return `${name}（${row.requestedByRole}）`
  return name || '—'
}

async function loadStats() {
  await approvalStore.refreshStats()
}

async function loadPending() {
  try {
    await approvalStore.refreshPending()
  } catch {
    ElMessage.error('加载待审批列表失败')
  }
}

async function loadHistory() {
  try {
    const data = await getApprovalHistory(historyPage.value, historyPageSize)
    historyItems.value = data.items || []
    historyTotal.value = data.total || 0
  } catch {
    ElMessage.error('加载审批历史失败')
  }
}

function onHistoryPage(page: number) {
  historyPage.value = page
  loadHistory()
}

async function gotoChat(row: { sessionId?: string; traceId?: string }) {
  if (!row.sessionId) return
  try {
    await getMessages(row.sessionId, 1, 1)
  } catch {
    ElMessage.warning('会话不存在或已被删除')
    return
  }
  detailVisible.value = false
  await router.push({
    path: `/chat/${row.sessionId}`,
    query: row.traceId ? { trace: row.traceId } : {},
  })
}

function openDetail(row: { id: string }) {
  selectedId.value = row.id
  detailVisible.value = true
}

async function openEdit(row: { id: string }) {
  try {
    const data = await getApprovalById(row.id)
    editForm.value = {
      id: data.id,
      detail: data.detail || '',
      comment: data.comment || '',
      riskLevel: data.riskLevel || 'L4',
    }
    editVisible.value = true
  } catch {
    ElMessage.error('加载审批详情失败')
  }
}

async function saveEdit() {
  if (!editForm.value) return
  saving.value = true
  try {
    await updateApproval(editForm.value.id, {
      detail: editForm.value.detail,
      comment: editForm.value.comment,
      riskLevel: editForm.value.riskLevel,
    })
    ElMessage.success('已保存')
    editVisible.value = false
    await refreshAll()
  } catch (e: any) {
    ElMessage.error('保存失败: ' + (e?.response?.data?.detail || e?.message || '操作失败'))
  } finally {
    saving.value = false
  }
}

function openDelete(row: any) {
  deleteTarget.value = row
  deleteVisible.value = true
}

async function confirmDelete() {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    await deleteApproval(deleteTarget.value.id)
    ElMessage.success('审批记录已删除')
    deleteVisible.value = false
    deleteTarget.value = null
    await refreshAll()
  } catch (e: any) {
    ElMessage.error('删除失败: ' + (e?.response?.data?.detail || e?.message || '操作失败'))
  } finally {
    deleting.value = false
  }
}

function handleRowAction(cmd: string, row: any) {
  if (cmd === 'detail') openDetail(row)
  else if (cmd === 'edit') openEdit(row)
  else if (cmd === 'delete') openDelete(row)
}

async function handleApprove(id: string) {
  approving.value = id
  try {
    const res = await approveApproval(id, '确认执行')
    ElMessage.success(res?.data?.message || res?.message || '审批通过，请在对话页面确认执行')
    await refreshAll()
  } catch (e: any) {
    ElMessage.error('审批失败: ' + (e?.response?.data?.detail || e?.message || '操作失败'))
  } finally {
    approving.value = null
  }
}

async function handleReject(id: string) {
  approving.value = id
  try {
    const res = await rejectApproval(id, '不予执行')
    ElMessage.warning(res?.data?.message || res?.message || '已拒绝')
    await refreshAll()
  } catch (e: any) {
    ElMessage.error('拒绝失败: ' + (e?.response?.data?.detail || e?.message || '操作失败'))
  } finally {
    approving.value = null
  }
}

async function refreshAll() {
  await Promise.all([loadStats(), loadPending(), loadHistory()])
}

watch(
  () => approvalStore.pendingTotal,
  (count, prev) => {
    if (count > 0 && (prev === 0 || prev === undefined) && tab.value === 'history') {
      tab.value = 'pending'
    }
  },
)

watch(
  () => route.path,
  (path) => {
    if (path === '/approval') void refreshAll()
  },
)

onMounted(() => {
  approvalStore.startPolling(5000)
  void refreshAll()
})

onUnmounted(() => {
  approvalStore.stopPolling()
})
</script>

<style lang="scss" scoped>
.approval-page {
  max-width: 1100px;
  margin: 0 auto;
  position: relative;

  &::before {
    content: '';
    position: fixed;
    inset: 0;
    pointer-events: none;
    z-index: -1;
    background-image:
      linear-gradient(rgba(124, 58, 237, 0.03) 1px, transparent 1px),
      linear-gradient(90deg, rgba(124, 58, 237, 0.03) 1px, transparent 1px);
    background-size: 32px 32px;
    mask-image: radial-gradient(ellipse 80% 60% at 50% 0%, #000 20%, transparent 75%);
  }
}

.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 18px;
  flex-wrap: wrap;
}

.page-tag {
  display: inline-block;
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: #7c3aed;
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid #ddd6fe;
  background: #f5f3ff;
  margin-bottom: 6px;
}

.page-title {
  font-size: 22px;
  font-weight: 700;
  color: #1e293b;
  margin: 0;
}

.page-desc {
  font-size: 13px;
  color: #64748b;
  margin: 6px 0 0;
  line-height: 1.5;
}

.role-badge {
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  &.admin { background: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe; }
  &.user { background: #f8fafc; color: #64748b; border: 1px solid #e2e8f0; }
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  margin-bottom: 18px;
}

.stat-card {
  position: relative;
  padding: 14px 16px;
  border-radius: 14px;
  border: 1px solid color-mix(in srgb, var(--card-accent) 18%, #e2e8f0);
  background:
    radial-gradient(ellipse at 100% 0%, color-mix(in srgb, var(--card-accent) 8%, transparent), transparent 60%),
    #fff;
  box-shadow: 0 2px 10px rgba(15, 23, 42, 0.04);
  overflow: hidden;
  transition: transform 0.15s, box-shadow 0.15s, border-color 0.15s;
  &:hover {
    transform: translateY(-1px);
    border-color: color-mix(in srgb, var(--card-accent) 30%, #cbd5e1);
    box-shadow: 0 8px 24px color-mix(in srgb, var(--card-accent) 10%, rgba(15, 23, 42, 0.06));
  }
}

.card-glow {
  position: absolute;
  inset: -30% auto auto -10%;
  width: 70px;
  height: 70px;
  background: radial-gradient(circle, color-mix(in srgb, var(--card-accent) 12%, transparent), transparent 70%);
  pointer-events: none;
}

.stat-code {
  display: block;
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: var(--card-accent);
  opacity: 0.85;
  margin-bottom: 2px;
}

.stat-label { display: block; font-size: 11px; color: #94a3b8; margin-bottom: 4px; }
.stat-value {
  display: block;
  font-size: 22px;
  font-weight: 800;
  line-height: 1.1;
  color: var(--card-accent);
  font-family: 'JetBrains Mono', Consolas, monospace;
}
.stat-hint { display: block; font-size: 10px; color: #cbd5e1; margin-top: 4px; }

.execution-result {
  margin-bottom: 16px;
  padding: 14px 16px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 12px;
  .exec-head {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 14px;
    font-weight: 600;
    .text-green { color: #059669; }
    .text-red { color: #dc2626; }
    .exec-close {
      margin-left: auto;
      background: none;
      border: none;
      font-size: 18px;
      cursor: pointer;
      color: #94a3b8;
    }
  }
  .exec-output {
    margin-top: 10px;
    font-size: 12px;
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 10px;
    max-height: 200px;
    overflow: auto;
    font-family: 'JetBrains Mono', monospace;
  }
}

.tabs-row {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.tab-btn {
  padding: 10px 20px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #64748b;
  font-size: 13px;
  font-weight: 600;
  border-radius: 10px;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  transition: all 0.15s;
  &:hover { border-color: #c4b5fd; color: #7c3aed; }
  &.active {
    color: #7c3aed;
    border-color: #7c3aed;
    background: linear-gradient(180deg, #f5f3ff, #fff);
    box-shadow: 0 4px 12px rgba(124, 58, 237, 0.12);
  }
}

.tab-icon {
  display: flex;
  align-items: center;
  opacity: 0.85;
}

.tab-badge {
  background: #ef4444;
  color: #fff;
  padding: 1px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
}

.content-panel {
  padding: 20px;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  background: #fff;
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.04);
}

.section-head {
  margin-bottom: 16px;
}

.section-title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: #1e293b;
}

.section-tip {
  margin: 4px 0 0;
  font-size: 12px;
  color: #64748b;
}

.flow-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.pagination-row {
  display: flex;
  justify-content: center;
  margin-top: 8px;
  padding-top: 16px;
  border-top: 1px solid #f1f5f9;
}

.empty-state {
  text-align: center;
  padding: 56px 24px;
  background: #f8fafc;
  border: 1px dashed #e2e8f0;
  border-radius: 14px;
  .empty-icon {
    width: 48px;
    height: 48px;
    margin: 0 auto 12px;
    border-radius: 50%;
    background: #ecfdf5;
    color: #059669;
    font-size: 22px;
    line-height: 48px;
    font-weight: 700;
  }
  p { margin: 0; font-size: 15px; font-weight: 600; color: #64748b; }
  .empty-hint { display: block; margin-top: 6px; font-size: 12px; color: #94a3b8; }
}

.source-pill {
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  background: #eef2ff;
  color: #4338ca;
  &.sm { font-size: 10px; padding: 2px 8px; }
}

.result-pill {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
  &.ok { background: #ecfdf5; color: #059669; }
  &.warn { background: #fffbeb; color: #d97706; }
  &.fail { background: #fef2f2; color: #dc2626; }
  &.pending { background: #eff6ff; color: #2563eb; }
}

.risk-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 700;
  &.l3 { background: #fff7ed; color: #ea580c; }
  &.l4, &.l5 { background: #fef2f2; color: #dc2626; }
}

.dialog-btn {
  padding: 8px 18px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #64748b;
  margin-left: 8px;
  &.primary {
    color: #fff;
    background: #2563eb;
    border-color: #2563eb;
    &:hover:not(:disabled) { background: #1d4ed8; }
    &:disabled { opacity: 0.6; cursor: not-allowed; }
  }
  &.danger {
    color: #fff;
    background: #dc2626;
    border-color: #dc2626;
    &:hover:not(:disabled) { background: #b91c1c; }
    &:disabled { opacity: 0.6; cursor: not-allowed; }
  }
}

.delete-dialog-body { text-align: center; padding: 4px 8px 0; }

.delete-icon-wrap {
  width: 52px;
  height: 52px;
  margin: 0 auto 14px;
  border-radius: 50%;
  background: #fef2f2;
  border: 1px solid #fecaca;
  display: flex;
  align-items: center;
  justify-content: center;
}

.delete-icon { width: 26px; height: 26px; color: #dc2626; }

.delete-title {
  margin: 0 0 6px;
  font-size: 17px;
  font-weight: 700;
  color: #1e293b;
}

.delete-desc {
  margin: 0 0 16px;
  font-size: 13px;
  color: #94a3b8;
  line-height: 1.5;
}

.delete-preview {
  text-align: left;
  padding: 14px;
  border-radius: 12px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.preview-head {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.preview-event {
  margin: 0 0 6px;
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  line-height: 1.45;
}

.preview-cmd {
  display: block;
  font-size: 11px;
  color: #64748b;
  font-family: 'JetBrains Mono', Consolas, monospace;
  background: #fff;
  padding: 6px 8px;
  border-radius: 6px;
  border: 1px solid #eef2f7;
  word-break: break-all;
  margin-bottom: 8px;
}

.preview-meta {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: #94a3b8;
}

.delete-footer {
  display: flex;
  justify-content: center;
  gap: 10px;
  .dialog-btn { margin-left: 0; min-width: 96px; }
}

@media (max-width: 960px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>

<style lang="scss">
.approval-delete-dialog .el-dialog__header { display: none; }
.approval-delete-dialog .el-dialog__body { padding: 28px 24px 8px; }
.approval-delete-dialog .el-dialog__footer { padding: 12px 24px 24px; border-top: none; }
</style>
