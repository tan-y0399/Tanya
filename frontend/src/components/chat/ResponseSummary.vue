<template>
  <div class="response-summary" v-if="hasContent">
    <div class="summary-head">
      <div class="head-left">
        <span class="head-icon" aria-hidden="true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/>
          </svg>
        </span>
        <div>
          <span class="head-title">执行结论</span>
          <span class="head-sub">基于工具执行结果为您整理</span>
        </div>
      </div>
      <div class="head-actions">
        <RollbackButton
          v-if="showFullRollback"
          variant="full"
          size="md"
          :busy="rollbackBusy"
          @click="$emit('fullRollback')"
        />
        <span v-if="parsed.report" class="head-badge">含详细报告</span>
      </div>
    </div>

    <div class="summary-body">
      <div v-if="parsed.error && !parsed.report" class="error-banner">
        <span class="error-icon">⚠</span>
        <span>{{ parsed.error }}</span>
      </div>

      <!-- 结构化结论：总览 / 关键发现 / 结论与建议（流式逐段呈现） -->
      <div v-if="parsed.sections.length" class="conclusion-sections" :class="{ streaming }">
        <section
          v-for="(sec, idx) in parsed.sections"
          :key="sec.id + '-' + idx"
          class="c-block"
          :class="[
            `c-block-${sec.id}`,
            { 'c-block-streaming': streaming && idx === parsed.sections.length - 1 },
          ]"
        >
          <div class="c-block-head">
            <span class="c-icon" aria-hidden="true">{{ sectionIcon(sec.id) }}</span>
            <h4 class="c-title">{{ sec.title }}</h4>
          </div>
          <div class="c-block-body">
            <p v-if="sec.type === 'paragraph'" class="c-paragraph" v-html="renderItem(sec.items[0])" />
            <ol v-else-if="sec.type === 'numbered'" class="c-list c-list-num">
              <li v-for="(item, ii) in sec.items" :key="ii" class="c-list-item" v-html="renderItem(item)" />
            </ol>
            <ul v-else class="c-list c-list-dot">
              <li v-for="(item, ii) in sec.items" :key="ii" class="c-list-item" v-html="renderItem(item)" />
            </ul>
          </div>
        </section>
      </div>

      <div v-else-if="parsed.summaryHtml" class="conclusion-highlight" v-html="parsed.summaryHtml" />

      <div v-else-if="parsed.report?.tools.length" class="conclusion-highlight fallback-hint">
        <p>本次运维检查已完成，关键结果如下表所示；展开下方报告可查看完整记录。</p>
      </div>

      <div v-if="showOpsFooter" class="ops-report">
        <div class="report-meta" v-if="displayMeta.length">
          <div v-for="m in displayMeta" :key="m.label" class="meta-chip">
            <span class="meta-label">{{ m.label }}</span>
            <span class="meta-value">{{ m.value }}</span>
          </div>
        </div>

        <div v-if="displayTools.length" class="tool-results">
          <div class="section-label">工具执行记录</div>
          <div class="tool-grid">
            <div
              v-for="(t, idx) in displayTools"
              :key="idx"
              class="tool-card"
              :class="toolStatusClass(t.status)"
            >
              <div class="tool-card-top">
                <span class="risk-tag" :class="'risk-' + (t.risk || 'L1').toLowerCase()">{{ t.risk }}</span>
                <code class="tool-name">{{ t.name }}</code>
                <span class="status-pill">{{ statusLabel(t.status) }}</span>
              </div>
              <p class="tool-summary">{{ t.summary }}</p>
            </div>
          </div>
        </div>

        <div
          v-for="(sec, si) in reportSections"
          :key="si"
          class="report-section"
          :class="reportSectionClass(sec.title)"
        >
          <h4 class="section-title">
            <span class="section-icon">{{ reportSectionIcon(sec.title) }}</span>
            {{ sec.title }}
          </h4>
          <ul class="section-list" :class="{ 'section-list-num': sec.title === '后续建议' }">
            <li v-for="(item, ii) in sec.items" :key="ii" v-html="renderItem(item)" />
          </ul>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  parseConclusionContent,
  inlineMd,
  type ConclusionSectionId,
  type ToolExecRow,
} from '@/utils/conclusionParser'
import RollbackButton from '@/components/chat/RollbackButton.vue'

interface ToolCallLike {
  toolName: string
  riskLevel?: string
  status: string
  displaySummary?: string
  result?: { display_summary?: string; success?: boolean; error?: string }
}

const props = defineProps<{
  content: string
  showFullRollback?: boolean
  rollbackBusy?: boolean
  traceId?: string
  intent?: string | null
  userQuestion?: string
  tools?: ToolCallLike[]
  streaming?: boolean
}>()

defineEmits<{ fullRollback: [] }>()

const parsed = computed(() => parseConclusionContent(props.content || ''))

function toolCallToRow(tc: ToolCallLike): ToolExecRow {
  const summary = tc.displaySummary
    || tc.result?.display_summary
    || (tc.status === 'completed' ? '执行完成' : tc.result?.error || tc.status)
  return {
    risk: tc.riskLevel || 'L1',
    name: tc.toolName,
    status: tc.status === 'completed' ? 'completed' : tc.status,
    summary: String(summary),
  }
}

const displayMeta = computed(() => {
  if (parsed.value.report?.meta.length) return parsed.value.report.meta
  const chips: { label: string; value: string }[] = []
  if (props.traceId) chips.push({ label: 'Trace ID', value: props.traceId })
  if (props.intent) chips.push({ label: '意图', value: props.intent })
  if (props.userQuestion) chips.push({ label: '用户诉求', value: props.userQuestion.slice(0, 120) })
  return chips
})

const displayTools = computed((): ToolExecRow[] => {
  if (parsed.value.report?.tools.length) return parsed.value.report.tools
  return (props.tools || [])
    .filter(t => ['completed', 'failed', 'blocked', 'rejected'].includes(t.status))
    .map(toolCallToRow)
})

const showOpsFooter = computed(() =>
  displayMeta.value.length > 0
  || displayTools.value.length > 0
  || (parsed.value.report?.sections.length || 0) > 0,
)

const TOOL_SECTION_NAMES = ['工具执行记录', '排查过程与执行命令']

const reportSections = computed(() => {
  const secs = parsed.value.report?.sections || []
  const hasToolCards = (parsed.value.report?.tools.length || 0) > 0
  const hasStructuredFindings = parsed.value.sections.some(s => s.id === 'findings')
  const hasStructuredSuggestions = parsed.value.sections.some(s => s.id === 'suggestions')
  return secs.filter(s => {
    if (!s.items.length) return false
    if (hasToolCards && TOOL_SECTION_NAMES.includes(s.title)) return false
    // 执行结论已有结构化章节时，隐藏报告中重复的「关键发现 / 后续建议」
    if (hasStructuredFindings && s.title === '关键发现') return false
    if (hasStructuredSuggestions && (s.title === '后续建议' || s.title === '结论与建议')) return false
    return true
  })
})

const hasContent = computed(() => {
  const p = parsed.value
  return !!(
    p.sections.length
    || p.summaryHtml
    || p.report
    || p.error
    || showOpsFooter.value
    || props.streaming
  )
})

function renderItem(text: string) {
  return inlineMd(text || '')
}

function sectionIcon(id: ConclusionSectionId) {
  const icons: Record<ConclusionSectionId, string> = {
    overview: '◎',
    findings: '◆',
    suggestions: '→',
    stats: '▤',
    other: 'ℹ',
  }
  return icons[id] || '•'
}

function statusLabel(status: string) {
  const s = (status || '').toLowerCase()
  if (s === 'completed') return '已完成'
  if (s === 'failed') return '失败'
  if (s === 'blocked') return '已阻止'
  if (s === 'pending_approval') return '待审批'
  return status
}

function toolStatusClass(status: string) {
  const s = (status || '').toLowerCase()
  if (s === 'completed') return 'is-ok'
  if (s === 'failed' || s === 'blocked') return 'is-err'
  return 'is-warn'
}

function reportSectionClass(title: string) {
  if (title === '关键发现') return 'rs-findings'
  if (title === '后续建议' || title === '结论与建议') return 'rs-suggestions'
  if (title === '查询概要') return 'rs-overview'
  return ''
}

function reportSectionIcon(title: string) {
  const m: Record<string, string> = {
    '查询概要': '◎',
    '关键发现': '◆',
    '后续建议': '→',
    '结论与建议': '→',
  }
  return m[title] || '•'
}
</script>

<style scoped lang="scss">
.response-summary {
  margin: 0;
  border-radius: 16px;
  border: 1px solid #bfdbfe;
  background: linear-gradient(165deg, #f0f9ff 0%, #ffffff 50%, #f8fafc 100%);
  overflow: hidden;
  box-shadow: 0 6px 20px rgba(37, 99, 235, 0.07);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.summary-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 18px;
  border-bottom: 1px solid #dbeafe;
  background: linear-gradient(90deg, #eff6ff, #fff);
}
.head-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.head-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border-radius: 11px;
  background: linear-gradient(135deg, #2563eb, #3b82f6);
  color: #fff;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.25);
}
.head-title {
  display: block;
  font-size: 15px;
  font-weight: 700;
  color: #1e3a8a;
  letter-spacing: 0.02em;
}
.head-sub {
  display: block;
  font-size: 12px;
  color: #64748b;
  margin-top: 3px;
}
.head-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
  overflow: visible;
}
.head-badge {
  font-size: 11px;
  padding: 4px 10px;
  border-radius: 20px;
  background: #dbeafe;
  color: #1d4ed8;
  font-weight: 500;
}

.summary-body {
  padding: 16px 18px 18px;
}

.error-banner {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 10px 12px;
  margin-bottom: 14px;
  border-radius: 10px;
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #b91c1c;
  font-size: 13px;
  line-height: 1.55;
}

/* ── 结构化结论区块 ── */
.conclusion-sections {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 16px;
}

.c-block {
  border-radius: 12px;
  overflow: hidden;
  border: 1px solid transparent;
  transition: box-shadow 0.2s;
}

.c-block-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
}

.c-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 700;
  flex-shrink: 0;
}

.c-title {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.03em;
}

.c-block-body {
  padding: 0 14px 14px 52px;
}

.c-paragraph {
  margin: 0;
  font-size: 14px;
  line-height: 1.8;
  color: #1e293b;
}

.c-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.c-list-item {
  position: relative;
  font-size: 13px;
  line-height: 1.75;
  color: #334155;
  padding-left: 0;

  :deep(strong) {
    color: #0f172a;
    font-weight: 600;
  }
  :deep(.md-code),
  :deep(code) {
    font-family: ui-monospace, 'SF Mono', Menlo, monospace;
    font-size: 12px;
    padding: 2px 6px;
    border-radius: 5px;
    background: rgba(15, 23, 42, 0.06);
    color: #4338ca;
    border: 1px solid rgba(99, 102, 241, 0.15);
  }
}

.c-list-dot .c-list-item {
  padding-left: 16px;
  &::before {
    content: '';
    position: absolute;
    left: 0;
    top: 0.62em;
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: currentColor;
    opacity: 0.55;
  }
}

.c-list-num {
  counter-reset: sug;
  .c-list-item {
    padding-left: 28px;
    counter-increment: sug;
    &::before {
      content: counter(sug);
      position: absolute;
      left: 0;
      top: 0.15em;
      width: 20px;
      height: 20px;
      border-radius: 50%;
      font-size: 11px;
      font-weight: 700;
      display: flex;
      align-items: center;
      justify-content: center;
      background: currentColor;
      color: #fff;
    }
  }
}

/* 总览 */
.c-block-overview {
  background: linear-gradient(135deg, #eff6ff 0%, #f0f9ff 100%);
  border-color: #bfdbfe;
  .c-block-head { background: rgba(255, 255, 255, 0.5); }
  .c-icon { background: #dbeafe; color: #1d4ed8; }
  .c-title { color: #1e40af; }
  .c-paragraph { color: #1e3a8a; font-weight: 500; }
}

/* 关键发现 */
.c-block-findings {
  background: #fff;
  border-color: #bbf7d0;
  .c-icon { background: #dcfce7; color: #15803d; }
  .c-title { color: #166534; }
  .c-list-dot .c-list-item { color: #14532d; }
  .c-list-dot .c-list-item::before { background: #22c55e; opacity: 1; }
}

/* 结论与建议 */
.c-block-suggestions {
  background: linear-gradient(135deg, #fffbeb 0%, #fff 100%);
  border-color: #fde68a;
  .c-icon { background: #fef3c7; color: #b45309; }
  .c-title { color: #92400e; }
  .c-list-num .c-list-item::before {
    background: #f59e0b;
    color: #fff;
  }
}

.c-block-stats,
.c-block-other {
  background: #f8fafc;
  border-color: #e2e8f0;
  .c-icon { background: #e2e8f0; color: #475569; }
  .c-title { color: #475569; }
}

.conclusion-sections.streaming .c-block-streaming {
  animation: section-flow-in 0.35s ease-out;
  box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.12);
}

@keyframes section-flow-in {
  from { opacity: 0.55; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}

/* 回退 HTML 渲染 */
.conclusion-highlight {
  padding: 14px 16px;
  margin-bottom: 14px;
  border-radius: 12px;
  background: #fff;
  border-left: 4px solid #2563eb;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.05);
  font-size: 14px;
  line-height: 1.75;
  color: #0f172a;

  :deep(.sum-p) { margin: 0 0 10px; &:last-child { margin-bottom: 0; } }
  :deep(.sum-ul), :deep(.sum-list) {
    margin: 8px 0 0;
    padding-left: 20px;
    color: #334155;
  }
  :deep(.sum-section-title) {
    margin: 12px 0 8px;
    font-size: 14px;
    font-weight: 700;
    color: #1e40af;
    &:first-child { margin-top: 0; }
  }
  :deep(strong) { color: #0f172a; font-weight: 600; }
  :deep(code), :deep(.md-code) {
    font-size: 12px;
    padding: 2px 6px;
    border-radius: 4px;
    background: #f1f5f9;
    color: #4338ca;
  }
}

.fallback-hint p {
  margin: 0;
  font-size: 14px;
  color: #334155;
}

.ops-report {
  border-top: 1px dashed #cbd5e1;
  padding-top: 16px;
  margin-top: 4px;
}

.report-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}
.meta-chip {
  display: inline-flex;
  flex-direction: column;
  gap: 3px;
  padding: 8px 12px;
  border-radius: 10px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  min-width: 120px;
}
.meta-label {
  font-size: 10px;
  color: #64748b;
  font-weight: 600;
  letter-spacing: 0.04em;
}
.meta-value {
  font-size: 12px;
  color: #0f172a;
  font-family: ui-monospace, monospace;
  word-break: break-all;
}

.section-label {
  font-size: 13px;
  font-weight: 700;
  color: #475569;
  margin-bottom: 10px;
  letter-spacing: 0.02em;
}

.tool-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 14px;
}
.tool-card {
  padding: 12px 14px;
  border-radius: 11px;
  border: 1px solid #e2e8f0;
  background: #fafafa;
  &.is-ok {
    border-color: #bbf7d0;
    background: linear-gradient(135deg, #f0fdf4, #fff);
  }
  &.is-err {
    border-color: #fecaca;
    background: #fef2f2;
  }
  &.is-warn {
    border-color: #fde68a;
    background: #fffbeb;
  }
}
.tool-card-top {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 6px;
}
.risk-tag {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 5px;
  background: #e2e8f0;
  color: #475569;
  &.risk-l1 { background: #dcfce7; color: #166534; }
  &.risk-l2 { background: #fef9c3; color: #854d0e; }
  &.risk-l3 { background: #ffedd5; color: #9a3412; }
  &.risk-l4 { background: #fee2e2; color: #991b1b; }
}
.tool-name {
  font-size: 12px;
  color: #1e293b;
  background: transparent;
  font-family: ui-monospace, monospace;
}
.status-pill {
  margin-left: auto;
  font-size: 11px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 999px;
  background: #e2e8f0;
  color: #475569;
}
.is-ok .status-pill {
  background: #22c55e;
  color: #fff;
}
.tool-summary {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: #475569;
}

.report-section {
  margin-top: 12px;
  padding: 12px 14px;
  border-radius: 11px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  &.rs-overview {
    background: linear-gradient(135deg, #eff6ff, #f8fafc);
    border-color: #bfdbfe;
  }
  &.rs-findings {
    background: #fff;
    border-color: #bbf7d0;
  }
  &.rs-suggestions {
    background: linear-gradient(135deg, #fffbeb, #fff);
    border-color: #fde68a;
  }
}
.section-title {
  margin: 0 0 10px;
  font-size: 14px;
  font-weight: 700;
  color: #334155;
  display: flex;
  align-items: center;
  gap: 8px;
}
.section-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  font-size: 12px;
  background: #e2e8f0;
  color: #475569;
}
.rs-findings .section-icon { background: #dcfce7; color: #15803d; }
.rs-suggestions .section-icon { background: #fef3c7; color: #b45309; }
.rs-overview .section-icon { background: #dbeafe; color: #1d4ed8; }
.section-list {
  margin: 0;
  padding-left: 0;
  list-style: none;
  font-size: 13px;
  line-height: 1.75;
  color: #475569;
  li {
    margin-bottom: 8px;
    padding-left: 14px;
    position: relative;
    &:last-child { margin-bottom: 0; }
    &::before {
      content: '';
      position: absolute;
      left: 0;
      top: 0.65em;
      width: 5px;
      height: 5px;
      border-radius: 50%;
      background: #94a3b8;
    }
    :deep(strong) { color: #0f172a; font-weight: 600; }
    :deep(code), :deep(.md-code) {
      font-family: ui-monospace, monospace;
      font-size: 12px;
      padding: 1px 5px;
      border-radius: 4px;
      background: rgba(99, 102, 241, 0.08);
      color: #4338ca;
    }
  }
}
.section-list-num li {
  padding-left: 28px;
  counter-increment: rs;
  &::before {
    content: counter(rs);
    width: 18px;
    height: 18px;
    top: 0.2em;
    border-radius: 50%;
    background: #f59e0b;
    color: #fff;
    font-size: 10px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
  }
}
.section-list-num { counter-reset: rs; }
</style>
