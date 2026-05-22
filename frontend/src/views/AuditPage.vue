<template>
  <div class="audit-page">
    <div class="page-header">
      <h2 class="page-title">审计日志</h2>
      <p class="page-desc">推理链路溯源 · 异常回溯定位 · 全流程审计记录</p>
    </div>

    <!-- 搜索栏 -->
    <div class="search-bar card">
      <div class="search-row">
        <el-input
          v-model="filters.userId"
          placeholder="用户"
          class="search-input"
          clearable
          size="default"
        />
        <el-select
          v-model="filters.eventType"
          placeholder="事件类型"
          class="search-input"
          clearable
          size="default"
        >
          <el-option label="全部" value="" />
          <el-option label="LLM 调用" value="LLM_CALL" />
          <el-option label="工具执行" value="TOOL_EXECUTION" />
          <el-option label="安全校验" value="SECURITY_CHECK" />
          <el-option label="审批" value="APPROVAL" />
        </el-select>
        <el-select
          v-model="filters.riskLevel"
          placeholder="风险等级"
          class="search-input"
          clearable
          size="default"
        >
          <el-option label="全部" value="" />
          <el-option label="L1 只读" value="L1" />
          <el-option label="L2 可逆" value="L2" />
          <el-option label="L3 不可逆" value="L3" />
          <el-option label="L4 关键变更" value="L4" />
        </el-select>
        <el-date-picker
          v-model="filters.dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始"
          end-placeholder="结束"
          class="search-input"
          size="default"
        />
        <button class="search-btn tech-btn primary" @click="doSearch">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <circle
              cx="6"
              cy="6"
              r="4.5"
              stroke="currentColor"
              stroke-width="1.5"
            />
            <path
              d="M9.5 9.5L13 13"
              stroke="currentColor"
              stroke-width="1.5"
              stroke-linecap="round"
            />
          </svg>
          搜索
        </button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-row">
      <div class="stat-card card" v-for="s in stats" :key="s.label">
        <div class="stat-value">{{ s.value }}</div>
        <div class="stat-label">{{ s.label }}</div>
      </div>
    </div>

    <!-- 审计时间线 -->
    <div class="audit-timeline card">
      <div class="timeline-list" v-if="records.length">
        <div
          class="timeline-item"
          v-for="(r, i) in records"
          :key="r.id"
          @click="openDetail(r)"
        >
          <div class="tl-side">
            <div class="tl-dot" :class="eventClass(r.eventType)"></div>
            <div class="tl-line" v-if="i < records.length - 1"></div>
          </div>
          <div class="tl-content">
            <div class="tl-header">
              <span class="tl-type">{{ eventLabel(r.eventType) }}</span>
              <span class="risk-tag" :class="`l${r.riskLevel || 'L1'}`">{{
                r.riskLevel
              }}</span>
              <span class="tl-time">{{ formatTime(r.timestamp) }}</span>
            </div>
            <div class="tl-summary">{{ r.summary }}</div>
            <div class="tl-meta">
              <span>用户: {{ r.userId }}</span>
              <span>TraceId: {{ r.traceId?.slice(0, 20) }}...</span>
              <span class="replay-link" @click.stop="openReplay(r.traceId)"
                >&#9654; 执行回放</span
              >
            </div>
          </div>
        </div>
      </div>
      <div class="empty-state" v-else>
        <p>暂无审计记录</p>
      </div>

      <div class="pagination-row" v-if="total > filters.size">
        <el-pagination
          :current-page="filters.page"
          :page-size="filters.size"
          :total="total"
          layout="prev, pager, next"
          background
          @update:current-page="onPageChange"
        />
      </div>
    </div>

    <!-- 详情抽屉 -->
    <el-drawer v-model="drawerVisible" size="460px" direction="rtl">
      <template #header>
        <div class="drawer-title-bar">
          <span class="drawer-title">审计详情</span>
          <span
            class="risk-tag"
            :class="`l${currentRecord?.riskLevel || 'L1'}`"
            >{{ currentRecord?.riskLevel }}</span
          >
        </div>
      </template>
      <div class="drawer-body" v-if="currentRecord">
        <div
          class="detail-row"
          v-for="(val, key) in formattedDetail"
          :key="key"
        >
          <div class="detail-key">{{ key }}</div>
          <div class="detail-val">{{ val }}</div>
        </div>
      </div>
    </el-drawer>

    <!-- 执行回放弹窗 -->
    <teleport to="body">
      <div
        class="modal-overlay"
        v-if="replayVisible"
        @click.self="replayVisible = false"
      >
        <div class="replay-modal" @click.stop>
          <button class="modal-close" @click="replayVisible = false">
            &times;
          </button>
          <h3 class="replay-title">
            执行回放 · {{ replayTraceId?.slice(0, 20) }}...
          </h3>
          <div class="replay-timeline">
            <div class="replay-step" v-for="(s, i) in replaySteps" :key="i">
              <div class="rs-line">
                <div class="rs-node" :class="s.status">
                  <span class="rs-num">{{ s.step }}</span>
                </div>
                <div
                  class="rs-connector"
                  v-if="i < replaySteps.length - 1"
                  :class="s.status"
                ></div>
              </div>
              <div class="rs-body">
                <div class="rs-type">{{ s.eventType }}</div>
                <div class="rs-title">{{ s.title }}</div>
                <div class="rs-detail">{{ s.detail }}</div>
                <div class="rs-meta">
                  <span v-if="s.time">{{ s.time }}</span>
                  <span v-if="s.duration" class="rs-duration"
                    >{{ s.duration }}ms</span
                  >
                  <span
                    v-if="s.riskLevel"
                    class="risk-tag"
                    :class="`l${s.riskLevel}`"
                    >{{ s.riskLevel }}</span
                  >
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from "vue";
import { getAuditRecords, getAuditDetail } from "@/api/audit";
import api from "@/api/index";
import { formatTime } from "@/utils";

const filters = reactive({
  page: 1,
  size: 20,
  userId: "",
  eventType: "",
  riskLevel: "",
  dateRange: null as any,
});

const records = ref<any[]>([]);
const total = ref(0);
const drawerVisible = ref(false);
const currentRecord = ref<any>(null);

const stats = computed(() => [
  { label: "总操作数", value: total.value },
  {
    label: "L3+ 高风险",
    value: records.value.filter((r: any) => ["L3", "L4"].includes(r.riskLevel))
      .length,
  },
  { label: "当前页", value: records.value.length },
  {
    label: "今日操作",
    value: records.value.filter((r: any) => {
      if (!r.timestamp) return false;
      const t = new Date(r.timestamp);
      const now = new Date();
      return t.toDateString() === now.toDateString();
    }).length,
  },
]);

const formattedDetail = computed(() => {
  if (!currentRecord.value) return {};
  const flatObj: Record<string, any> = {};
  function flatten(obj: any, prefix = "") {
    for (const key in obj) {
      const val = obj[key];
      const fullKey = prefix ? `${prefix}.${key}` : key;
      if (val && typeof val === "object" && !Array.isArray(val)) {
        flatten(val, fullKey);
      } else {
        flatObj[fullKey] =
          typeof val === "object" ? JSON.stringify(val) : String(val);
      }
    }
  }
  flatten(currentRecord.value);
  return flatObj;
});

function eventClass(type: string) {
  const m: Record<string, string> = {
    LLM_CALL: "llm",
    TOOL_EXECUTION: "tool",
    SECURITY_CHECK: "security",
    APPROVAL: "approval",
    chat: "llm",
  };
  return m[type] || "llm";
}

function eventLabel(type: string) {
  const m: Record<string, string> = {
    LLM_CALL: "LLM 调用",
    TOOL_EXECUTION: "工具执行",
    SECURITY_CHECK: "安全校验",
    APPROVAL: "审批操作",
    chat: "Agent 对话",
  };
  return m[type] || type;
}

async function doSearch() {
  const params: any = {
    page: filters.page,
    size: filters.size,
    userId: filters.userId || undefined,
    eventType: filters.eventType || undefined,
    riskLevel: filters.riskLevel || undefined,
  };
  if (filters.dateRange?.length === 2) {
    params.startTime = filters.dateRange[0].toISOString();
    params.endTime = filters.dateRange[1].toISOString();
  }
  try {
    const data = await getAuditRecords(params);
    records.value = data.items || [];
    total.value = data.total || 0;
  } catch {}
}

function onPageChange(val: number) {
  filters.page = val;
  doSearch();
}

const replayVisible = ref(false);
const replayTraceId = ref("");
const replaySteps = ref<any[]>([]);

async function openReplay(traceId: string) {
  replayTraceId.value = traceId;
  replayVisible.value = true;
  try {
    const { data } = await api.get(`/audit/replay/${traceId}`);
    if (data.code === 0) replaySteps.value = data.data.steps || [];
  } catch {}
}

async function openDetail(record: any) {
  currentRecord.value = record;
  drawerVisible.value = true;
  if (record.traceId) {
    try {
      await getAuditDetail(record.traceId);
    } catch {}
  }
}

onMounted(doSearch);
</script>

<style lang="scss" scoped>
.audit-page {
  width: 100%;
  min-width: 0;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 20px;
  .page-title {
    font-size: 20px;
    font-weight: 700;
    color: #1e293b;
  }
  .page-desc {
    font-size: 13px;
    color: #94a3b8;
    margin-top: 4px;
  }
}

.search-bar {
  padding: 16px;
  margin-bottom: 16px;
}

.search-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
}

.search-input {
  width: 150px;
}

.search-btn {
  display: flex;
  align-items: center;
  gap: 6px;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.stat-card {
  padding: 16px;
  text-align: center;
  .stat-value {
    font-size: 28px;
    font-weight: 700;
    font-family: "JetBrains Mono", Consolas, monospace;
    color: #2563eb;
  }
  .stat-label {
    font-size: 12px;
    color: #94a3b8;
    margin-top: 4px;
  }
}

.audit-timeline {
  padding: 20px;
}

.timeline-item {
  display: flex;
  gap: 12px;
  cursor: pointer;
  &:hover .tl-content {
    background: #f8fafc;
  }
}

.tl-side {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 14px;
  flex-shrink: 0;
  padding-top: 4px;
  .tl-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #cbd5e1;
    &.llm {
      background: #2563eb;
    }
    &.tool {
      background: #10b981;
    }
    &.security {
      background: #f59e0b;
    }
    &.approval {
      background: #6366f1;
    }
  }
  .tl-line {
    flex: 1;
    width: 1px;
    background: #e2e8f0;
    margin: 4px 0;
    min-height: 30px;
  }
}

.tl-content {
  flex: 1;
  padding: 6px 0 20px;
  border-radius: 6px;
  transition: background 0.15s;
}

.tl-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
  .tl-type {
    font-size: 13px;
    font-weight: 600;
    color: #1e293b;
  }
  .tl-time {
    margin-left: auto;
    font-size: 11px;
    color: #94a3b8;
  }
}

.tl-summary {
  font-size: 13px;
  color: #64748b;
  margin-bottom: 4px;
}

.tl-meta {
  display: flex;
  gap: 16px;
  font-size: 11px;
  color: #94a3b8;
  font-family: "JetBrains Mono", Consolas, monospace;
}

.empty-state {
  text-align: center;
  padding: 48px;
  color: #94a3b8;
}

.pagination-row {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}

.drawer-title-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  .drawer-title {
    font-size: 16px;
    font-weight: 600;
    color: #1e293b;
  }
}

.drawer-body {
  .detail-row {
    margin-bottom: 12px;
    .detail-key {
      font-size: 11px;
      font-weight: 600;
      color: #94a3b8;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 2px;
    }
    .detail-val {
      font-size: 13px;
      color: #1e293b;
      word-break: break-all;
      font-family: "JetBrains Mono", Consolas, monospace;
    }
  }
}

.replay-link {
  color: #2563eb;
  cursor: pointer;
  font-size: 12px;
  &:hover {
    text-decoration: underline;
  }
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.4);
  backdrop-filter: blur(4px);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
}
.replay-modal {
  background: #fff;
  border-radius: 16px;
  padding: 28px;
  width: 560px;
  max-height: 80vh;
  overflow-y: auto;
  position: relative;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.12);
}
.modal-close {
  position: absolute;
  top: 12px;
  right: 12px;
  background: none;
  border: none;
  font-size: 24px;
  color: #94a3b8;
  cursor: pointer;
  &:hover {
    color: #1e293b;
  }
}
.replay-title {
  font-size: 16px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 20px;
}

.replay-timeline {
  padding-left: 8px;
}
.replay-step {
  display: flex;
  gap: 12px;
}
.rs-line {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 32px;
  flex-shrink: 0;
}
.rs-node {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
  background: #e2e8f0;
  color: #64748b;
  &.success {
    background: #d1fae5;
    color: #059669;
  }
  &.error {
    background: #fee2e2;
    color: #dc2626;
  }
  &.info {
    background: #dbeafe;
    color: #2563eb;
  }
}
.rs-num {
  line-height: 1;
}
.rs-connector {
  flex: 1;
  width: 2px;
  background: #e2e8f0;
  margin: 4px 0;
  min-height: 24px;
  &.success {
    background: #a7f3d0;
  }
  &.error {
    background: #fecaca;
  }
  &.info {
    background: #bfdbfe;
  }
}
.rs-body {
  flex: 1;
  padding-bottom: 16px;
}
.rs-type {
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.rs-title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  margin: 2px 0;
}
.rs-detail {
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}
.rs-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  font-size: 11px;
  color: #94a3b8;
}
.rs-duration {
  font-family: "JetBrains Mono", monospace;
  color: #64748b;

  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #f1f5f9;
  background: #f8fafc;
  .list-title { font-size: 14px; font-weight: 600; color: #1e293b; }
  .list-tip { font-size: 12px; color: #94a3b8; }
}

.trace-list { max-height: 600px; overflow-y: auto; }

.trace-item {
  display: flex;
  gap: 12px;
  padding: 16px 20px;
  border-bottom: 1px solid #f1f5f9;
  cursor: pointer;
  transition: background 0.15s;
  &:hover { background: #f8fafc; }
}

.trace-status {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: #d1fae5;
  color: #059669;
  &.error {
    background: #fee2e2;
    color: #dc2626;
  }
}

.trace-main {
  flex: 1;
  min-width: 0;
}

.trace-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 6px;
  .trace-summary {
    font-size: 14px;
    font-weight: 600;
    color: #1e293b;
  }
  .trace-time {
    margin-left: auto;
    font-size: 12px;
    color: #94a3b8;
  }
}

.trace-meta {
  display: flex;
  gap: 16px;
  font-size: 11px;
  color: #94a3b8;
  margin-bottom: 8px;
  font-family: 'JetBrains Mono', Consolas, monospace;
}

.trace-preview {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.preview-step {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  color: #64748b;
  background: #f1f5f9;
  &.error { background: #fee2e2; color: #dc2626; }
  &.warning { background: #fef3c7; color: #d97706; }
}

.trace-arrow {
  width: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #cbd5e1;
  flex-shrink: 0;
}

.empty-state { text-align: center; padding: 48px; color: #94a3b8; }

.pagination-row { display: flex; justify-content: center; padding: 16px; border-top: 1px solid #f1f5f9; }

.trace-modal-overlay {
  position: fixed; inset: 0; background: rgba(15,23,42,0.4);
  backdrop-filter: blur(4px); z-index: 1000;
  display: flex; align-items: center; justify-content: center;
}

.trace-modal {
  background: #fff; border-radius: 16px;
  width: 700px; max-height: 85vh;
  display: flex; flex-direction: column;
  box-shadow: 0 20px 60px rgba(0,0,0,0.12);
}

.trace-modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #f1f5f9;
}

.trace-modal-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 700;
  color: #1e293b;
  svg { color: #2563eb; }
}

.trace-modal-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.action-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #64748b;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  &:hover { border-color: #2563eb; color: #2563eb; background: #eff6ff; }
}

.modal-close {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  background: none;
  border: none;
  font-size: 24px;
  line-height: 1;
  color: #94a3b8;
  cursor: pointer;
  &:hover { color: #1e293b; }
}

.trace-summary-bar {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  padding: 16px 20px;
  background: #f8fafc;
  border-bottom: 1px solid #f1f5f9;
}

.sum-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  .sum-label { font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.5px; }
  .sum-value { font-size: 12px; color: #1e293b; font-family: 'JetBrains Mono', Consolas, monospace; word-break: break-all; }
}

.trace-steps {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.chain-step {
  display: flex;
  gap: 12px;
  &:last-child {
    .step-line { display: none; }
  }
  &.error {
    .step-content { background: #fef2f2; border-radius: 8px; padding: 12px; }
  }
}

.step-indicator {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 28px;
  flex-shrink: 0;
  padding-top: 2px;
}

.step-node {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  background: #e2e8f0;
  color: #64748b;
  &.success { background: #d1fae5; color: #059669; }
  &.error { background: #fee2e2; color: #dc2626; }
  &.warning { background: #fef3c7; color: #d97706; }
}

.step-line {
  flex: 1;
  width: 2px;
  background: #e2e8f0;
  margin: 4px 0;
  min-height: 40px;
  &.success { background: #a7f3d0; }
  &.error { background: #fecaca; }
  &.warning { background: #fde68a; }
}

.step-content {
  flex: 1;
  padding-bottom: 20px;
}

.step-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.step-type {
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.step-status {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  &.success { background: #d1fae5; color: #059669; }
  &.error { background: #fee2e2; color: #dc2626; }
  &.warning { background: #fef3c7; color: #d97706; }
}

.step-time, .step-duration {
  font-size: 11px;
  color: #94a3b8;
  font-family: 'JetBrains Mono', Consolas, monospace;
}

.step-time { margin-left: auto; }

.step-title {
  font-size: 14px;
  font-weight: 600;
  color: #1e293b;
  margin-bottom: 6px;
}

.step-detail, .step-error {
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}

.step-detail pre, .step-error pre {
  margin: 0;
  padding: 8px 10px;
  background: #f1f5f9;
  border-radius: 6px;
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 11px;
  white-space: pre-wrap;
  word-break: break-all;
}

.step-data {
  margin-top: 8px;
}

.data-row {
  display: flex;
  gap: 8px;
  margin-bottom: 4px;
  font-size: 12px;
}

.data-key {
  min-width: 80px;
  color: #94a3b8;
  font-weight: 500;
}

.data-val {
  flex: 1;
  color: #1e293b;
  font-family: 'JetBrains Mono', Consolas, monospace;
  white-space: pre-wrap;
  word-break: break-all;
}

.error-title {
  font-size: 11px;
  font-weight: 600;
  color: #dc2626;
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
</style>
