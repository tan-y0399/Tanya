<template>
  <div class="approval-page">
    <div class="page-header">
      <h2 class="page-title">审批管理</h2>
      <p class="page-desc">高危运维操作人工审批，超时自动拒绝</p>
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
        <div class="card-actions">
          <button class="act-btn approve" @click="handleApprove(ap.id)">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M3 8l3 3 7-7" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
            通过
          </button>
          <button class="act-btn reject" @click="handleReject(ap.id)">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            </svg>
            拒绝
          </button>
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
import { ref, onMounted } from 'vue'
import { getPendingApprovals, getApprovalHistory, approveApproval, rejectApproval } from '@/api/approval'
import { formatTime } from '@/utils'

const tab = ref<'pending' | 'history'>('pending')
const pendingItems = ref<any[]>([])
const pendingTotal = ref(0)
const historyItems = ref<any[]>([])

async function loadPending() {
  try {
    const data = await getPendingApprovals()
    pendingItems.value = data.items || []
    pendingTotal.value = data.total || 0
  } catch {}
}

async function loadHistory() {
  try {
    const data = await getApprovalHistory()
    historyItems.value = data.items || []
  } catch {}
}

async function handleApprove(id: string) {
  try { await approveApproval(id, '确认执行'); await loadPending() } catch {}
}

async function handleReject(id: string) {
  try { await rejectApproval(id, '不予执行'); await loadPending() } catch {}
}

onMounted(() => { loadPending(); loadHistory() })
</script>

<style lang="scss" scoped>
.approval-page { max-width: 900px; margin: 0 auto; }

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

.empty-state { text-align: center; padding: 48px; color: #94a3b8; }

.ok { color: #059669; font-weight: 600; }
.fail { color: #dc2626; font-weight: 600; }
</style>
