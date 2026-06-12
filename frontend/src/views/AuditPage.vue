<template>
  <div class="audit-page">
    <header class="page-header">
      <div class="header-main">
        <span class="page-tag">AUDIT</span>
        <h2 class="page-title">审计中心</h2>
        <p class="page-desc">推理链路溯源 · 异常回溯定位 · 全流程审计记录</p>
      </div>
      <div class="header-modules">
        <div v-for="m in heroModules" :key="m.key" class="hero-chip">
          <AuditIcon :name="m.icon" tone="blue" size="sm" boxed />
          <span>{{ m.label }}</span>
          <span class="hero-count">{{ m.count }}</span>
        </div>
      </div>
    </header>

    <AuditOverviewCards :stats="globalStats" :loading="statsLoading" />

    <AuditFilterBar
      :active-tab="activeTab"
      :keyword="filters.keyword"
      :username="filters.username"
      :risk-level="filters.riskLevel"
      :date-range="filters.dateRange"
      :stats="globalStats"
      :searching="searchLoading"
      @tab-change="onTabChange"
      @update:keyword="filters.keyword = $event"
      @update:username="filters.username = $event"
      @update:risk-level="filters.riskLevel = $event"
      @update:date-range="filters.dateRange = $event"
      @search="onSearch"
    />

    <section
      class="timeline-section audit-panel"
      :class="{ 'is-searching': searchLoading }"
    >
      <AuditWorkflowLinkHub v-if="isWorkflowTab" />
      <AuditModuleHub v-else :active-tab="activeTab" />

      <div class="section-head">
        <div>
          <h3 class="section-title">{{ sectionTitleText }}</h3>
          <p class="section-tip">
            <span v-if="searchLoading" class="searching-hint">
              <span class="inline-spinner"></span> 正在检索审计记录…
            </span>
            <span v-else>{{ sectionTipText }}</span>
          </p>
        </div>
      </div>

      <div v-if="searchLoading && !records.length" class="skeleton-list">
        <div v-for="i in 4" :key="i" class="skeleton-card">
          <div class="sk-band"></div>
          <div class="sk-body">
            <div class="sk-line w60"></div>
            <div class="sk-line w90"></div>
            <div class="sk-line w40"></div>
          </div>
        </div>
      </div>
      <div v-else-if="records.length" class="card-list flow-list" :class="{ 'is-refreshing': searchLoading }">
        <template v-if="isWorkflowTab">
          <AuditWorkflowFlowCard
            v-for="record in records"
            :key="record.id"
            :record="record"
            @open="openDetail"
            @detail="openDetail"
            @replay="(tid) => openReplay(tid, record)"
            @goto-chat="gotoChat"
          />
        </template>
        <template v-else>
          <AuditTimelineCard
            v-for="record in records"
            :key="record.id"
            :record="record"
            :show-pipeline="false"
            @open="openDetail"
            @detail="openDetail"
            @replay="(tid) => openReplay(tid, record)"
            @goto-chat="gotoChat"
          />
        </template>
      </div>
      <div v-else-if="!searchLoading" class="empty-state">
        <AuditIcon name="empty-list" tone="muted" size="lg" boxed />
        <p>暂无符合条件的审计记录</p>
      </div>

      <div v-if="total > filters.size" class="pagination-row">
        <el-pagination
          :current-page="filters.page"
          :page-size="filters.size"
          :total="total"
          layout="prev, pager, next"
          background
          @update:current-page="onPageChange"
        />
      </div>
    </section>

    <AuditDetailDrawer
      ref="detailDrawerRef"
      v-model:visible="drawerVisible"
      :detail="detailData"
      :loading="detailLoading"
      @goto-chat="gotoChat"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import AuditOverviewCards from '@/components/audit/AuditOverviewCards.vue'
import AuditFilterBar from '@/components/audit/AuditFilterBar.vue'
import AuditTimelineCard from '@/components/audit/AuditTimelineCard.vue'
import AuditWorkflowFlowCard from '@/components/audit/AuditWorkflowFlowCard.vue'
import AuditWorkflowLinkHub from '@/components/audit/AuditWorkflowLinkHub.vue'
import AuditModuleHub from '@/components/audit/AuditModuleHub.vue'
import AuditDetailDrawer from '@/components/audit/AuditDetailDrawer.vue'
import { sectionTitle, sectionTip } from '@/components/audit/auditTabMeta'
import AuditIcon from '@/components/audit/AuditIcon.vue'
import type { AuditDetail, AuditRecordItem, AuditStats } from '@/components/audit/auditEventMeta'
import { HERO_MODULES, resolveHeroCount } from '@/components/audit/auditEventMeta'
import { getAuditDetail, getAuditRecords, getAuditStats } from '@/api/audit'
import { getMessages } from '@/api/chat'
import { useChatStore } from '@/stores/chat'

const router = useRouter()
const chatStore = useChatStore()

const filters = reactive({
  page: 1,
  size: 20,
  username: '',
  keyword: '',
  eventType: '',
  riskLevel: '',
  dateRange: null as [Date, Date] | null,
})

const activeTab = ref('')
const records = ref<AuditRecordItem[]>([])
const total = ref(0)
const globalStats = ref<AuditStats | null>(null)
const statsLoading = ref(false)
const searchLoading = ref(false)

const drawerVisible = ref(false)
const detailLoading = ref(false)
const detailData = ref<AuditDetail | null>(null)
const detailDrawerRef = ref<InstanceType<typeof AuditDetailDrawer> | null>(null)

const isWorkflowTab = computed(() => activeTab.value === 'workflow')

const sectionTitleText = computed(() => sectionTitle(activeTab.value))
const sectionTipText = computed(() => sectionTip(activeTab.value, total.value))

const heroModules = computed(() =>
  HERO_MODULES.map((m) => ({
    ...m,
    count: resolveHeroCount(globalStats.value, m.countFrom),
  })),
)

function buildParams() {
  const params: Record<string, unknown> = {
    page: filters.page,
    size: filters.size,
    username: filters.username || undefined,
    eventType: filters.eventType || undefined,
    riskLevel: filters.riskLevel || undefined,
    keyword: filters.keyword || undefined,
  }
  if (filters.dateRange?.length === 2) {
    params.startTime = filters.dateRange[0].toISOString()
    params.endTime = filters.dateRange[1].toISOString()
  }
  return params
}

async function loadStats() {
  statsLoading.value = true
  try {
    globalStats.value = await getAuditStats()
  } catch {
    globalStats.value = null
  } finally {
    statsLoading.value = false
  }
}

async function loadRecords() {
  searchLoading.value = true
  try {
    const data = await getAuditRecords(buildParams() as any)
    records.value = data.items || []
    total.value = data.total || 0
  } catch {
    records.value = []
    total.value = 0
  } finally {
    searchLoading.value = false
  }
}

async function refreshAll() {
  await Promise.all([loadStats(), loadRecords()])
}

function onSearch() {
  filters.page = 1
  loadRecords()
}

function onTabChange(key: string) {
  activeTab.value = key
  filters.eventType = key
  filters.page = 1
  loadRecords()
}

function onPageChange(page: number) {
  filters.page = page
  loadRecords()
}

async function openDetail(record: AuditRecordItem) {
  drawerVisible.value = true
  detailLoading.value = true
  detailData.value = null
  const refId = record.sessionId || record.id || record.traceId
  try {
    detailData.value = await getAuditDetail(refId)
  } catch {
    detailData.value = {
      id: refId,
      traceId: record.traceId,
      sessionId: record.sessionId,
      userId: record.userId,
      username: record.username,
      userDisplayName: record.userDisplayName,
      userRoleLabel: record.userRoleLabel,
      eventType: record.eventType,
      summary: record.summary,
      riskLevel: record.riskLevel,
      timestamp: record.timestamp,
      turnCount: record.turnCount,
      intent: record.intent,
      totalMs: record.totalMs,
    }
  } finally {
    detailLoading.value = false
  }
}

async function openReplay(traceId: string, record?: AuditRecordItem) {
  if (record) {
    const refId = record.sessionId || record.id || record.traceId
    if (!drawerVisible.value || detailData.value?.traceId !== traceId) {
      drawerVisible.value = true
      detailLoading.value = true
      detailData.value = null
      try {
        detailData.value = await getAuditDetail(refId)
      } catch {
        detailData.value = {
          id: refId,
          traceId: record.traceId,
          sessionId: record.sessionId,
          userId: record.userId,
          username: record.username,
          userDisplayName: record.userDisplayName,
          userRoleLabel: record.userRoleLabel,
          eventType: record.eventType,
          summary: record.summary,
          riskLevel: record.riskLevel,
          timestamp: record.timestamp,
          turnCount: record.turnCount,
          intent: record.intent,
        }
      } finally {
        detailLoading.value = false
      }
    }
  } else if (!drawerVisible.value) {
    drawerVisible.value = true
  }
  await nextTick()
  await detailDrawerRef.value?.openReplay(traceId)
}

async function gotoChat(payload: string | { sessionId: string; traceId?: string }) {
  const sessionId = typeof payload === 'string' ? payload : payload.sessionId
  const traceId = typeof payload === 'string' ? detailData.value?.traceId : payload.traceId
  if (!sessionId) return

  try {
    await getMessages(sessionId, 1, 1)
  } catch {
    ElMessage.warning('会话不存在或已被删除')
    return
  }

  drawerVisible.value = false
  if (traceId) {
    chatStore.setCurrentTraceId(traceId)
  }
  await router.push({
    path: `/chat/${sessionId}`,
    query: traceId ? { trace: traceId } : {},
  })
}

onMounted(refreshAll)
</script>

<style scoped lang="scss">
.audit-page {
  width: 100%;
  min-width: 0;
  margin: 0 auto;
  position: relative;

  &::before {
    content: '';
    position: fixed;
    inset: 0;
    pointer-events: none;
    z-index: -1;
    background-image:
      linear-gradient(rgba(37, 99, 235, 0.03) 1px, transparent 1px),
      linear-gradient(90deg, rgba(37, 99, 235, 0.03) 1px, transparent 1px);
    background-size: 32px 32px;
    mask-image: radial-gradient(ellipse 80% 60% at 50% 0%, #000 20%, transparent 75%);
  }
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.page-tag {
  display: inline-block;
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: #2563eb;
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid #bfdbfe;
  background: #eff6ff;
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
  color: #94a3b8;
  margin: 6px 0 0;
}

.header-modules {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.hero-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px 8px 8px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid #e2e8f0;
  font-size: 12px;
  color: #475569;
  transition: border-color 0.15s, box-shadow 0.15s;
  &:hover {
    border-color: #bfdbfe;
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.08);
  }
}

.hero-count {
  min-width: 20px;
  padding: 0 6px;
  border-radius: 999px;
  background: #2563eb;
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  text-align: center;
}

.audit-panel {
  padding: 20px;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  background: #fff;
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.04);
}

.section-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
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
  color: #94a3b8;
}

.searching-hint {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #2563eb;
  font-weight: 500;
}

.inline-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(37, 99, 235, 0.2);
  border-top-color: #2563eb;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

.timeline-section.is-searching {
  position: relative;
}

.card-list.is-refreshing {
  opacity: 0.55;
  pointer-events: none;
  transition: opacity 0.2s ease;
}

.skeleton-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.skeleton-card {
  display: flex;
  border: 1px solid #f1f5f9;
  border-radius: 12px;
  overflow: hidden;
  background: #fff;
}

.sk-band {
  width: 4px;
  background: linear-gradient(180deg, #e2e8f0, #f1f5f9);
  animation: shimmer 1.2s ease-in-out infinite;
}

.sk-body {
  flex: 1;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.sk-line {
  height: 12px;
  border-radius: 6px;
  background: linear-gradient(90deg, #f1f5f9 25%, #e2e8f0 50%, #f1f5f9 75%);
  background-size: 200% 100%;
  animation: shimmer 1.2s ease-in-out infinite;
  &.w60 { width: 60%; }
  &.w90 { width: 90%; }
  &.w40 { width: 40%; }
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.card-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.empty-state {
  text-align: center;
  padding: 56px 24px;
  color: #94a3b8;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  p { margin: 0; }
}

.pagination-row {
  display: flex;
  justify-content: center;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #f1f5f9;
}

.flow-list {
  gap: 16px;
}

.section-tip {
  color: #64748b;
}
</style>
