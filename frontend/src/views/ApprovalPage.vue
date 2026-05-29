<template>
  <div class="approval-page">
    <div class="page-header">
      <h2 class="page-title">审批管理</h2>
      <p class="page-desc">高危运维操作人工审批，超时自动拒绝</p>
    </div>

    <!-- 最近执行结果 -->
    <div class="execution-result" v-if="lastExecutionResult">
      <div class="exec-head">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="7" :stroke="lastExecutionResult.success ? '#059669' : '#dc2626'" stroke-width="1.3"/>
          <path :d="lastExecutionResult.success ? 'M5 8l2 2 4-4' : 'M5.5 5.5l5 5M10.5 5.5l-5 5'" :stroke="lastExecutionResult.success ? '#059669' : '#dc2626'" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
        <span :class="lastExecutionResult.success ? 'text-green' : 'text-red'">
          {{ lastExecutionResult.success ? '命令已执行成功' : '命令执行失败' }}
        </span>
        <button class="exec-close" @click="lastExecutionResult = null">&times;</button>
      </div>
      <pre class="exec-output" v-if="lastExecutionResult.result">{{ JSON.stringify(lastExecutionResult.result, null, 2) }}</pre>
    </div>

    <div class="tabs-row">
      <button class="tab-btn" :class="{ active: tab === 'pending' }" @click="tab = 'pending'">
        待审批
        <span class="tab-badge" v-if="pendingTotal">{{ pendingTotal }}</span>
      </button>
      <button class="tab-btn" :class="{ active: tab === 'history' }" @click="tab = 'history'">
        审批历史
      </button>
    </div>

    <!-- 待审批 -->
    <div v-if="tab === 'pending'">
      <div class="approval-card card" v-for="ap in pendingItems" :key="ap.id">
        <div class="card-left">
          <div class="card-head">
            <span class="card-tool">{{ ap.toolName }}</span>
            <span class="risk-tag" :class="`l${ap.riskLevel || 'L3'}`">{{ ap.riskLevel }}</span>
          </div>
          <div class="card-detail">{{ ap.detail }}</div>
          <div class="card-meta">
            <span>申请人: {{ ap.requestedBy }}</span>
            <span>{{ formatTime(ap.requestedAt) }}</span>
            <span class="expire" v-if="ap.expiresAt">过期: {{ formatTime(ap.expiresAt) }}</span>
          </div>
          <div class="card-params" v-if="ap.toolParams">
            <div class="params-label">操作参数</div>
            <pre class="code-mini">{{ JSON.stringify(ap.toolParams, null, 2) }}</pre>
          </div>
        </div>
        <div class="card-actions" v-if="isAdmin">
          <button class="act-btn approve" @click="handleApprove(ap.id)" :disabled="approving === ap.id">
            <svg v-if="approving !== ap.id" width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M3 8l3 3 7-7" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
            <span v-else class="btn-spinner"></span>
            {{ approving === ap.id ? '执行中...' : '通过' }}
          </button>
          <button class="act-btn reject" @click="handleReject(ap.id)" :disabled="approving === ap.id">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
            拒绝
          </button>
        </div>
        <div class="card-actions" v-else>
          <div class="no-permission-tip">仅管理员可审批</div>
        </div>
      </div>
      <div class="empty-state" v-if="!pendingItems.length">
        <p>暂无待审批操作</p>
      </div>
    </div>

    <!-- 审批历史 -->
    <div class="card" v-if="tab === 'history'">
      <el-table :data="historyItems" size="default" header-row-class-name="tech-table-header" row-class-name="tech-table-row">
        <el-table-column prop="toolName" label="工具" min-width="140"/>
        <el-table-column label="风险" width="80">
          <template #default="{ row }">
            <span class="risk-tag" :class="`l${row.riskLevel || 'L3'}`">{{ row.riskLevel }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="requestedBy" label="申请人" width="100"/>
        <el-table-column label="结果" width="80">
          <template #default="{ row }">
            <span :class="row.result === 'APPROVED' ? 'ok' : 'fail'">
              {{ row.result === 'APPROVED' ? '已通过' : '已拒绝' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="时间" min-width="160">
          <template #default="{ row }">{{ formatTime(row.requestedAt) }}</template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useUserStore } from '@/stores/user'
import { getPendingApprovals, getApprovalHistory, approveApproval, rejectApproval } from '@/api/approval'
import { formatTime } from '@/utils'
import { ElMessage } from 'element-plus'

const userStore = useUserStore()
const isAdmin = computed(() => userStore.userInfo?.role === 'admin')

const tab = ref<'pending' | 'history'>('pending')
const pendingItems = ref<any[]>([])
const pendingTotal = ref(0)
const historyItems = ref<any[]>([])
const lastExecutionResult = ref<any>(null)
const approving = ref<string | null>(null)

async function loadPending() {
  try {
    const data = await getPendingApprovals()
    pendingItems.value = data.items || []
    pendingTotal.value = data.total || 0
  } catch {
    ElMessage.error('加载待审批列表失败')
  }
}

async function loadHistory() {
  try {
    const data = await getApprovalHistory()
    historyItems.value = data.items || []
  } catch {
    ElMessage.error('加载审批历史失败')
  }
}

async function handleApprove(id: string) {
  approving.value = id
  try {
    const res = await approveApproval(id, '确认执行')
    ElMessage.success(res?.data?.message || res?.message || '审批通过')
    await loadPending()
    await loadHistory()
  } catch (e: any) {
    const detail = e?.response?.data?.detail || e?.message || '操作失败'
    ElMessage.error('审批失败: ' + detail)
  }
  finally { approving.value = null }
}

async function handleReject(id: string) {
  approving.value = id
  try {
    const res = await rejectApproval(id, '不予执行')
    ElMessage.warning(res?.data?.message || res?.message || '已拒绝')
    await loadPending()
    await loadHistory()
  } catch (e: any) {
    const detail = e?.response?.data?.detail || e?.message || '操作失败'
    ElMessage.error('拒绝失败: ' + detail)
  }
  finally { approving.value = null }
}

onMounted(() => { loadPending(); loadHistory() })
</script>

<style lang="scss" scoped>
.approval-page { max-width: 900px; margin: 0 auto; }

.execution-result {
  margin-bottom: 16px;
  padding: 14px 16px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
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
      &:hover { color: #1e293b; }
    }
  }
  .exec-output {
    margin-top: 10px;
    font-size: 12px;
    background: #fff;
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 10px;
    max-height: 200px;
    overflow: auto;
    font-family: 'JetBrains Mono', monospace;
    color: #334155;
  }
}

.page-header {
  margin-bottom: 20px;
  .page-title { font-size: 20px; font-weight: 700; color: #1e293b; }
  .page-desc { font-size: 13px; color: #94a3b8; margin-top: 4px; }
}

.tabs-row { display: flex; gap: 4px; margin-bottom: 16px; }

.tab-btn {
  padding: 8px 20px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #64748b;
  font-size: 13px;
  font-weight: 500;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: all 0.15s;
  &:hover { border-color: #2563eb; color: #2563eb; }
  &.active {
    color: #2563eb;
    border-color: #2563eb;
    background: #eff6ff;
  }
}

.tab-badge {
  background: #fef2f2;
  color: #ef4444;
  padding: 1px 7px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
}

.approval-card {
  display: flex;
  padding: 20px;
  margin-bottom: 12px;
}

.card-left { flex: 1; min-width: 0; }

.card-head {
  display: flex; align-items: center; gap: 8px;
  margin-bottom: 6px;
  .card-tool {
    font-family: 'JetBrains Mono', Consolas, monospace;
    font-size: 15px;
    color: #2563eb;
    font-weight: 600;
  }
}

.card-detail { font-size: 13px; color: #1e293b; margin-bottom: 6px; }

.card-meta {
  display: flex; gap: 16px;
  font-size: 11px; color: #94a3b8;
  .expire { color: #f59e0b; }
}

.card-params {
  margin-top: 10px;
  .params-label { font-size: 11px; font-weight: 600; color: #94a3b8; margin-bottom: 4px; }
}

.code-mini {
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 12px;
  background: #f8fafc;
  color: #1e293b;
  padding: 8px 12px;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
  max-height: 120px;
  overflow: auto;
}

.card-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-left: 20px;
  margin-left: 20px;
  border-left: 1px solid #f1f5f9;
}

.act-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 16px;
  border-radius: 8px;
  border: 1px solid;
  background: #fff;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s;
  &.approve {
    color: #059669;
    border-color: #a7f3d0;
    &:hover { background: #ecfdf5; border-color: #10b981; }
  }
  &.reject {
    color: #dc2626;
    border-color: #fecaca;
    &:hover { background: #fef2f2; border-color: #ef4444; }
  }
}

.btn-spinner {
  width: 14px; height: 14px;
  border: 2px solid #a7f3d0;
  border-top-color: #059669;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
  display: inline-block;
}
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.no-permission-tip {
  font-size: 12px; color: #94a3b8;
  padding: 10px 0; text-align: center;
}
.empty-state { text-align: center; padding: 48px; color: #94a3b8; }

.ok { color: #059669; font-weight: 600; }
.fail { color: #dc2626; font-weight: 600; }
</style>
