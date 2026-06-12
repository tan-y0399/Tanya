<template>
  <el-drawer
    :model-value="visible"
    size="520px"
    direction="rtl"
    :append-to-body="true"
    :z-index="2100"
    class="approval-detail-drawer"
    @update:model-value="$emit('update:visible', $event)"
  >
    <template #header>
      <div class="drawer-head">
        <div class="drawer-head-main">
          <h3 class="drawer-title">审批详情</h3>
          <p v-if="detail?.id" class="drawer-sub">ID · {{ detail.id }}</p>
        </div>
        <span v-if="detail?.riskLevel" class="risk-tag" :class="riskClass(detail.riskLevel)">
          {{ detail.riskLevel }}
        </span>
      </div>
    </template>

    <div class="drawer-body">
      <div v-if="loading" class="loading-box">
        <span class="loading-ring"></span>
        <span>加载详情…</span>
      </div>

      <template v-else-if="detail">
        <div class="event-hero">
          <span class="source-pill">{{ detail.sourceType || 'Agent 对话' }}</span>
          <span class="result-pill" :class="resultClass(detail.status)">
            {{ resultLabel(detail.status) }}
          </span>
          <h2 class="event-title">{{ detail.eventSummary || detail.detail || detail.toolName }}</h2>
          <code v-if="detail.commandPreview" class="cmd-preview">{{ detail.commandPreview }}</code>
        </div>

        <div class="stats-row">
          <div class="stat-item">
            <span class="stat-label">工具</span>
            <code class="stat-value mono">{{ detail.toolName }}</code>
          </div>
          <div class="stat-item">
            <span class="stat-label">类型</span>
            <strong class="stat-value">{{ detail.sourceType || 'Agent 对话' }}</strong>
          </div>
          <div class="stat-item">
            <span class="stat-label">风险</span>
            <strong class="stat-value">{{ detail.riskLevel }}</strong>
          </div>
        </div>

        <section class="info-section">
          <h4 class="section-title">基本信息</h4>
          <div class="info-grid">
            <div v-for="item in infoItems" :key="item.label" class="info-card">
              <span class="info-label">{{ item.label }}</span>
              <strong class="info-value">{{ item.value }}</strong>
            </div>
          </div>
        </section>

        <section v-if="detail.detail" class="info-section">
          <h4 class="section-title">风险描述</h4>
          <p class="text-block">{{ detail.detail }}</p>
        </section>

        <section v-if="detail.comment" class="info-section">
          <h4 class="section-title">审批意见</h4>
          <p class="text-block comment">{{ detail.comment }}</p>
        </section>

        <section v-if="detail.toolParams" class="info-section">
          <h4 class="section-title">操作参数</h4>
          <pre class="params-box">{{ JSON.stringify(detail.toolParams, null, 2) }}</pre>
        </section>

        <section v-if="detail.traceId || detail.sessionId" class="info-section">
          <h4 class="section-title">链路标识</h4>
          <div class="trace-list">
            <div v-if="detail.traceId" class="trace-row">
              <span class="trace-label">Trace</span>
              <code class="trace-val">{{ detail.traceId }}</code>
            </div>
            <div v-if="detail.sessionId" class="trace-row">
              <span class="trace-label">Session</span>
              <code class="trace-val">{{ detail.sessionId }}</code>
            </div>
          </div>
        </section>
      </template>

      <div v-else class="empty-box">未找到审批记录</div>
    </div>

    <template v-if="detail?.sessionId" #footer>
      <div class="drawer-footer">
        <button type="button" class="footer-btn primary" @click="$emit('goto-chat', detail)">
          跳转对话
        </button>
      </div>
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { getApprovalById } from '@/api/approval'
import { formatTime } from '@/utils'

const props = defineProps<{
  visible: boolean
  approvalId?: string | null
}>()

defineEmits<{
  'update:visible': [value: boolean]
  'goto-chat': [row: any]
}>()

const loading = ref(false)
const detail = ref<any>(null)

function riskClass(level?: string) {
  const lv = (level || 'L3').toLowerCase().replace('l', '')
  return `l${lv}`
}

function resultLabel(status: string) {
  const m: Record<string, string> = {
    approved: '已通过',
    rejected: '已拒绝',
    timeout: '已超时',
    pending: '待审批',
  }
  return m[status] || status || '未知'
}

function resultClass(status: string) {
  if (status === 'approved') return 'ok'
  if (status === 'timeout') return 'warn'
  return 'fail'
}

function formatUser(row: any) {
  const name = row.requestedBy || row.requestedByUsername
  if (name && row.requestedByRole) return `${name}（${row.requestedByRole}）`
  return name || '—'
}

const infoItems = computed(() => {
  if (!detail.value) return []
  const d = detail.value
  const items = [
    { label: '申请人', value: formatUser(d) },
    { label: '申请时间', value: formatTime(d.requestedAt) },
    { label: '审批结果', value: resultLabel(d.status) },
  ]
  if (d.approver) {
    items.push({ label: '审批人', value: d.approverRole ? `${d.approver}（${d.approverRole}）` : d.approver })
  }
  if (d.resolvedAt) {
    items.push({ label: '处理时间', value: formatTime(d.resolvedAt) })
  }
  if (d.expiresAt && d.status === 'pending') {
    items.push({ label: '过期时间', value: formatTime(d.expiresAt) })
  }
  return items
})

async function loadDetail() {
  if (!props.approvalId) {
    detail.value = null
    return
  }
  loading.value = true
  try {
    detail.value = await getApprovalById(props.approvalId)
  } catch {
    detail.value = null
  } finally {
    loading.value = false
  }
}

watch(
  () => [props.visible, props.approvalId] as const,
  ([vis]) => {
    if (vis) loadDetail()
  },
  { immediate: true },
)
</script>

<style lang="scss" scoped>
.drawer-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
}

.drawer-title {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  color: #1e293b;
}

.drawer-sub {
  margin: 4px 0 0;
  font-size: 11px;
  color: #94a3b8;
  font-family: 'JetBrains Mono', Consolas, monospace;
}

.drawer-body {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-bottom: 8px;
}

.loading-box, .empty-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 48px 24px;
  color: #94a3b8;
  font-size: 13px;
}

.loading-ring {
  width: 28px;
  height: 28px;
  border: 3px solid #dbeafe;
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.event-hero {
  padding: 16px;
  border-radius: 12px;
  background: linear-gradient(135deg, #eff6ff 0%, #f8fafc 100%);
  border: 1px solid #dbeafe;
}

.source-pill {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  background: #eef2ff;
  color: #4338ca;
  margin-right: 8px;
}

.result-pill {
  display: inline-block;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 700;
  &.ok { background: #ecfdf5; color: #059669; }
  &.warn { background: #fffbeb; color: #d97706; }
  &.fail { background: #fef2f2; color: #dc2626; }
}

.event-title {
  margin: 10px 0 0;
  font-size: 16px;
  font-weight: 700;
  color: #1e293b;
  line-height: 1.45;
}

.cmd-preview {
  display: block;
  margin-top: 10px;
  font-size: 12px;
  color: #475569;
  font-family: 'JetBrains Mono', Consolas, monospace;
  background: #fff;
  padding: 8px 10px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  word-break: break-all;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.stat-item {
  padding: 12px;
  border-radius: 10px;
  border: 1px solid #eef2f7;
  background: #fff;
}

.stat-label {
  display: block;
  font-size: 10px;
  color: #94a3b8;
  margin-bottom: 4px;
}

.stat-value {
  display: block;
  font-size: 13px;
  color: #1e293b;
  &.mono {
    font-family: 'JetBrains Mono', Consolas, monospace;
    color: #2563eb;
    font-size: 12px;
  }
}

.info-section {
  padding: 14px;
  border-radius: 12px;
  border: 1px solid #eef2f7;
  background: #fff;
}

.section-title {
  margin: 0 0 10px;
  font-size: 12px;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
}

.info-card {
  padding: 10px 12px;
  border-radius: 8px;
  background: #f8fafc;
}

.info-label {
  display: block;
  font-size: 10px;
  color: #94a3b8;
  margin-bottom: 2px;
}

.info-value {
  display: block;
  font-size: 13px;
  color: #1e293b;
  font-weight: 600;
}

.text-block {
  margin: 0;
  font-size: 13px;
  color: #475569;
  line-height: 1.55;
  &.comment {
    padding: 10px 12px;
    background: #f8fafc;
    border-radius: 8px;
    border-left: 3px solid #2563eb;
  }
}

.params-box {
  margin: 0;
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 11px;
  background: #f8fafc;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  max-height: 200px;
  overflow: auto;
}

.trace-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.trace-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.trace-label {
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
  min-width: 56px;
}

.trace-val {
  font-size: 11px;
  font-family: 'JetBrains Mono', Consolas, monospace;
  color: #64748b;
  background: #f8fafc;
  padding: 4px 8px;
  border-radius: 6px;
  word-break: break-all;
}

.drawer-footer {
  display: flex;
  justify-content: flex-end;
}

.footer-btn {
  padding: 10px 20px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid;
  &.primary {
    color: #2563eb;
    border-color: #2563eb;
    background: #eff6ff;
    &:hover { background: #dbeafe; }
  }
}

.risk-tag {
  display: inline-block;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
  &.l1 { background: #ecfdf5; color: #059669; }
  &.l2 { background: #eff6ff; color: #2563eb; }
  &.l3 { background: #fff7ed; color: #ea580c; }
  &.l4, &.l5 { background: #fef2f2; color: #dc2626; }
}
</style>

<style lang="scss">
.approval-detail-drawer .el-drawer__header {
  margin-bottom: 0;
  padding-bottom: 16px;
  border-bottom: 1px solid #f1f5f9;
}
.approval-detail-drawer .el-drawer__body {
  padding-top: 16px;
}
.approval-detail-drawer .el-drawer__footer {
  border-top: 1px solid #f1f5f9;
  padding-top: 12px;
}
</style>
