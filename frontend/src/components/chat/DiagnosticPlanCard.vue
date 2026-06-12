<template>
  <div class="plan-card" :class="[`mode-${mode}`, `intent-${plan.intent || 'default'}`]">
    <!-- 页头 -->
    <header class="plan-head" v-show="visible.head">
      <div class="head-icon" aria-hidden="true">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2"/>
          <rect x="9" y="3" width="6" height="4" rx="1"/>
          <path d="M9 12h6M9 16h6"/>
        </svg>
      </div>
      <div class="head-text">
        <span class="plan-title">{{ plan.title || '运维诊断与执行方案' }}</span>
        <span class="plan-sub">{{ mode === 'confirm' ? '请核对后确认执行' : '执行记录（方案已确认）' }}</span>
      </div>
      <div class="head-badges">
        <span v-if="planOriginLabel" class="origin-badge">{{ planOriginLabel }}</span>
        <span class="plan-tag">{{ intentLabel }}</span>
      </div>
    </header>

    <div class="plan-body">
      <!-- 元数据条 -->
      <div v-show="visible.meta && metaChips.length" class="meta-strip stream-in">
        <div v-for="chip in metaChips" :key="chip.label" class="meta-chip">
          <span class="meta-label">{{ chip.label }}</span>
          <span class="meta-value" :title="chip.value">{{ chip.value }}</span>
        </div>
      </div>

      <!-- 查询目标 -->
      <section v-if="plan.query_goal" v-show="visible.phenomenon" class="block goal-block stream-in">
        <h4 class="block-title"><span class="block-icon">◎</span>查询目标</h4>
        <p class="goal-text">{{ plan.query_goal }}</p>
      </section>

      <!-- 现象 -->
      <section
        v-else-if="plan.phenomenon"
        v-show="visible.phenomenon"
        class="block phenomenon-block stream-in"
      >
        <h4 class="block-title"><span class="block-icon warn">!</span>故障现象</h4>
        <p class="phenomenon-text">{{ plan.phenomenon }}</p>
      </section>

      <!-- 诊断思路 -->
      <section v-if="plan.analysis_summary" v-show="visible.analysis" class="block analysis-block stream-in">
        <h4 class="block-title"><span class="block-icon">💡</span>诊断思路</h4>
        <p class="block-text">{{ plan.analysis_summary }}</p>
      </section>

      <!-- 可能根因 -->
      <section
        v-if="showPossibleCauses"
        v-show="visible.causes"
        class="block causes-block stream-in"
      >
        <h4 class="block-title"><span class="block-icon">◆</span>可能根因</h4>
        <ol class="cause-list">
          <li v-for="(c, i) in plan.possible_causes" :key="i" class="cause-item">
            <span class="cause-num">{{ i + 1 }}</span>
            <span class="cause-text">{{ c }}</span>
          </li>
        </ol>
      </section>

      <!-- 知识库参考 -->
      <section v-if="ragItems.length" v-show="visible.rag" class="block rag-block stream-in">
        <h4 class="block-title"><span class="block-icon">📚</span>知识库参考</h4>
        <div class="rag-chips">
          <span
            v-for="(item, i) in ragItems"
            :key="i"
            class="rag-chip"
            :title="item.title"
          >
            {{ item.title }}
            <em v-if="item.score" class="rag-score">{{ item.score }}</em>
          </span>
        </div>
      </section>

      <!-- 环境感知 + 文件保护（可折叠） -->
      <section
        v-if="showAdvancedInfo"
        v-show="visible.env"
        class="block advanced-block stream-in"
      >
        <button type="button" class="advanced-toggle" @click="advancedOpen = !advancedOpen">
          <span class="toggle-arrow">{{ advancedOpen ? '▼' : '▶' }}</span>
          <span>环境感知与文件保护</span>
          <span class="toggle-hint">{{ protectionCount }} 项保护 · {{ envSummaryShort ? '已采集' : '待执行' }}</span>
        </button>
        <div v-show="advancedOpen" class="advanced-body">
          <p v-if="envSummaryShort" class="block-text env-text">{{ envSummaryShort }}</p>
          <div v-if="protectionCount" class="protect-row">
            <span class="protect-label">保护路径</span>
            <div class="protect-tags">
              <span v-for="(p, i) in protectionPreview" :key="i" class="protect-tag">{{ p }}</span>
              <span v-if="protectionCount > protectionPreview.length" class="protect-more">
                +{{ protectionCount - protectionPreview.length }}
              </span>
            </div>
          </div>
        </div>
      </section>

      <!-- 执行步骤时间线 -->
      <section v-if="plan.steps?.length" v-show="visible.steps" class="block steps-block stream-in">
        <div class="steps-head">
          <h4 class="block-title"><span class="block-icon">▶</span>执行步骤</h4>
          <div class="steps-stats">
            <span class="stat-pill">共 {{ plan.steps.length }} 步</span>
            <span v-if="riskStats.readonly" class="stat-pill stat-l1">只读 {{ riskStats.readonly }}</span>
            <span v-if="riskStats.write" class="stat-pill stat-warn">需确认 {{ riskStats.write }}</span>
          </div>
        </div>

        <ol class="timeline">
          <li
            v-for="(s, idx) in plan.steps"
            :key="s.order"
            class="timeline-item"
            :class="{
              'is-core': s.core,
              'is-visible': visibleStepIndex >= idx,
              'is-last': idx === plan.steps.length - 1,
            }"
          >
            <div class="timeline-rail">
              <span class="timeline-dot" :class="{ 'dot-core': s.core }">{{ s.order }}</span>
              <span v-if="idx < plan.steps.length - 1" class="timeline-line" />
            </div>

            <div class="timeline-card" :class="'risk-border-' + (s.risk || 'l1').toLowerCase()">
              <div class="tc-top">
                <span class="tc-action">{{ s.action }}</span>
                <span v-if="s.core" class="core-tag">核心</span>
                <span v-if="s.risk" class="tc-risk" :class="'risk-' + (s.risk || '').toLowerCase()">{{ s.risk }}</span>
              </div>

              <div v-if="s.expected" class="tc-expected">
                <span class="tc-label">预期</span>
                <span>{{ s.expected }}</span>
              </div>

              <div v-if="s.tool_hint && s.tool_hint !== 'summary'" class="tc-tool">
                <span class="tc-label">工具</span>
                <code>{{ formatToolHint(s.tool_hint) }}</code>
              </div>
            </div>
          </li>
        </ol>
      </section>

      <p v-show="visible.note && plan.risk_note" class="risk-note stream-in">
        <span class="risk-note-icon">⚠</span>
        {{ plan.risk_note }}
      </p>
    </div>

    <footer v-if="mode === 'confirm'" v-show="visible.actions" class="plan-foot stream-in">
      <span class="foot-hint">确认后将按步骤依次执行，写操作需您二次确认</span>
      <div class="foot-actions">
        <button type="button" class="btn-cancel" @click="$emit('cancel')">终止</button>
        <button type="button" class="btn-run" @click="$emit('confirm')">
          确认并执行
          <span v-if="plan.steps?.length" class="btn-step-count">{{ plan.steps.length }} 步</span>
        </button>
      </div>
    </footer>
    <footer v-else class="plan-foot readonly-foot stream-in">
      <span class="readonly-badge">已确认执行</span>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, toRef, watch, onMounted } from 'vue'
import { usePlanStreamReveal } from '@/composables/usePlanStreamReveal'

const props = withDefaults(
  defineProps<{
    plan: Record<string, any>
    mode?: 'confirm' | 'readonly'
    streamReveal?: boolean
    traceId?: string
    userQuestion?: string
  }>(),
  { mode: 'confirm', streamReveal: true },
)

defineEmits<{ confirm: []; cancel: [] }>()

const advancedOpen = ref(false)
const visibleStepIndex = ref(-1)

const enableStream = toRef(() => props.streamReveal && props.mode === 'confirm')
const hasActions = toRef(() => props.mode === 'confirm')
const { visible } = usePlanStreamReveal(enableStream, hasActions)

const intentLabel = computed(() => {
  const m: Record<string, string> = {
    high_risk: '高风险',
    fault_analysis: '故障分析',
    ops_query: '运维查询',
  }
  return m[props.plan.intent] || props.plan.intent || '运维'
})

const planOriginLabel = computed(() => {
  if (props.plan.plan_origin === 'rag_llm') return 'RAG+AI'
  return ''
})

const metaChips = computed(() => {
  const chips: { label: string; value: string }[] = []
  const trace = props.traceId || props.plan.traceId
  if (trace) chips.push({ label: 'Trace ID', value: trace })
  if (props.plan.intent) chips.push({ label: '意图', value: intentLabel.value })
  const userQ = props.userQuestion || props.plan.phenomenon
  if (userQ) chips.push({ label: '用户诉求', value: userQ.slice(0, 100) })
  return chips
})

const showPossibleCauses = computed(() => {
  if (props.plan.plan_type === 'readonly_query') return false
  return Array.isArray(props.plan.possible_causes) && props.plan.possible_causes.length > 0
})

const ragItems = computed(() => {
  const src = props.plan.rag_sources
  if (Array.isArray(src) && src.length) {
    return src.map((s: { title?: string; score?: number; confidence?: string }) => ({
      title: s.title || '',
      score: s.confidence || (s.score ? `${Math.round(s.score * 100)}%` : ''),
    })).filter(i => i.title)
  }
  if (props.plan.rag_reference) {
    return [{ title: '知识库检索摘要', score: '' }]
  }
  return []
})

const protectionList = computed(() => {
  const wl = props.plan.file_protection_whitelist
  return Array.isArray(wl) ? wl : []
})
const protectionCount = computed(() =>
  props.plan.file_protection_count ?? protectionList.value.length,
)
const protectionPreview = computed(() => protectionList.value.slice(0, 8))

const envSummaryShort = computed(() => {
  const scan = props.plan.environment_scan?.summary
  if (scan && typeof scan === 'string') return scan
  const pre = (props.plan.preliminary_analysis || '').trim()
  if (!pre) return ''
  return pre
    .replace(/用户诉求[：:][^。；\n]+[。；]?/g, '')
    .replace(/知识库参考[：:][^。；\n]+[。；]?/g, '')
    .replace(/初步怀疑[：:][^。；\n]+[。；]?/g, '')
    .trim()
})

const showAdvancedInfo = computed(() =>
  !!(envSummaryShort.value || protectionCount.value),
)

const riskStats = computed(() => {
  const steps = props.plan.steps || []
  let readonly = 0
  let write = 0
  for (const s of steps) {
    const r = (s.risk || 'L1').toUpperCase()
    if (r === 'L1') readonly++
    else write++
  }
  return { readonly, write }
})

function formatToolHint(hint: string) {
  const raw = (hint || '').trim()
  const m: Record<string, string> = {
    'list_processes:cpu': 'list_processes --sort=-%cpu',
    'list_processes:mem': 'list_processes --sort=-%mem',
  }
  if (m[raw]) return m[raw]
  if (raw.startsWith('get_service_status:') || raw.startsWith('get_service_status ')) {
    const svc = raw.split(/[: ]/).pop()
    return `get_service_status · ${svc}`
  }
  if (raw.startsWith('execute_command:')) {
    return raw.slice('execute_command:'.length).trim()
  }
  if (raw.startsWith('manage_service ')) {
    return raw
  }
  return raw.replace(/,/g, ' · ')
}

async function revealStepsStaggered() {
  const steps = props.plan.steps || []
  if (!steps.length) return
  visibleStepIndex.value = -1
  for (let i = 0; i < steps.length; i++) {
    await new Promise(r => setTimeout(r, i === 0 ? 80 : 120))
    visibleStepIndex.value = i
  }
}

watch(() => visible.value.steps, (v) => {
  if (v && enableStream.value) void revealStepsStaggered()
  else if (v) visibleStepIndex.value = (props.plan.steps?.length || 1) - 1
})

onMounted(() => {
  if (!enableStream.value) {
    visibleStepIndex.value = (props.plan.steps?.length || 1) - 1
  }
})
</script>

<style scoped lang="scss">
.plan-card {
  border-radius: 16px;
  border: 1px solid #c7d2fe;
  background: linear-gradient(165deg, #fafbff 0%, #fff 40%, #f8fafc 100%);
  overflow: hidden;
  box-shadow: 0 8px 24px rgba(79, 70, 229, 0.1);
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;

  &.mode-readonly {
    border-color: #cbd5e1;
    box-shadow: 0 2px 12px rgba(15, 23, 42, 0.06);
  }
}

/* ── 页头 ── */
.plan-head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 18px;
  background: linear-gradient(135deg, #3730a3 0%, #4f46e5 50%, #6366f1 100%);
  color: #fff;
}

.head-icon {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.18);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.head-text {
  flex: 1;
  min-width: 0;
}

.plan-title {
  display: block;
  font-size: 16px;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.plan-sub {
  display: block;
  font-size: 12px;
  opacity: 0.88;
  margin-top: 3px;
}

.head-badges {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
  flex-shrink: 0;
}

.origin-badge {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 6px;
  background: rgba(16, 185, 129, 0.35);
  border: 1px solid rgba(255, 255, 255, 0.4);
}

.plan-tag {
  font-size: 11px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.2);
  border: 1px solid rgba(255, 255, 255, 0.35);
}

/* ── 主体 ── */
.plan-body {
  padding: 16px 18px 10px;
}

.meta-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.meta-chip {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 8px 12px;
  border-radius: 10px;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  min-width: 100px;
  flex: 1;
  max-width: 220px;
}

.meta-label {
  font-size: 10px;
  font-weight: 600;
  color: #64748b;
  letter-spacing: 0.04em;
}

.meta-value {
  font-size: 12px;
  color: #0f172a;
  font-family: ui-monospace, monospace;
  word-break: break-all;
  line-height: 1.4;
}

.block {
  margin-bottom: 14px;
  border-radius: 12px;
  padding: 14px 16px;
}

.block-title {
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 700;
  color: #334155;
  display: flex;
  align-items: center;
  gap: 8px;
}

.block-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: 6px;
  font-size: 12px;
  background: #e0e7ff;
  color: #4338ca;
  &.warn {
    background: #fef3c7;
    color: #b45309;
    font-weight: 800;
  }
}

.goal-block {
  background: linear-gradient(135deg, #eff6ff, #eef2ff);
  border: 1px solid #bfdbfe;
}

.phenomenon-block {
  background: linear-gradient(135deg, #fff7ed 0%, #fff 100%);
  border: 1px solid #fed7aa;
  border-left: 4px solid #f97316;
}

.phenomenon-text {
  margin: 0;
  font-size: 14px;
  line-height: 1.75;
  color: #9a3412;
  font-weight: 500;
}

.analysis-block {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
}

.causes-block {
  background: #fff;
  border: 1px solid #bbf7d0;
}

.cause-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.cause-item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 8px 0;
  border-bottom: 1px dashed #e2e8f0;
  &:last-child { border-bottom: none; padding-bottom: 0; }
}

.cause-num {
  flex-shrink: 0;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: #dcfce7;
  color: #15803d;
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.cause-text {
  font-size: 13px;
  line-height: 1.65;
  color: #334155;
}

.rag-block {
  background: linear-gradient(135deg, #f0fdf4, #f8fafc);
  border: 1px dashed #86efac;
  padding: 12px 14px;
}

.rag-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.rag-chip {
  font-size: 11px;
  line-height: 1.4;
  padding: 6px 10px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid #bbf7d0;
  color: #166534;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rag-score {
  font-style: normal;
  margin-left: 6px;
  font-size: 10px;
  color: #64748b;
}

.advanced-block {
  padding: 0;
  border: 1px solid #e2e8f0;
  background: #fafbfc;
  overflow: hidden;
}

.advanced-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-family: inherit;
  font-size: 13px;
  font-weight: 600;
  color: #475569;
  text-align: left;
  &:hover { background: #f1f5f9; }
}

.toggle-arrow {
  font-size: 10px;
  color: #94a3b8;
  width: 14px;
}

.toggle-hint {
  margin-left: auto;
  font-size: 11px;
  font-weight: 500;
  color: #94a3b8;
}

.advanced-body {
  padding: 0 14px 14px;
  border-top: 1px dashed #e2e8f0;
}

.env-text {
  margin: 12px 0 0;
  font-size: 12px;
  color: #64748b;
  line-height: 1.65;
}

.protect-row {
  margin-top: 10px;
}

.protect-label {
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
  display: block;
  margin-bottom: 6px;
}

.protect-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.protect-tag {
  font-size: 10px;
  font-family: ui-monospace, monospace;
  padding: 3px 8px;
  border-radius: 5px;
  background: #fff;
  border: 1px solid #fecaca;
  color: #991b1b;
}

.protect-more {
  font-size: 10px;
  color: #94a3b8;
  align-self: center;
}

.block-text {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
  color: #1e293b;
}

.goal-text {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #1e40af;
}

/* ── 步骤时间线 ── */
.steps-block {
  background: transparent;
  padding: 0;
  border: none;
}

.steps-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.steps-stats {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.stat-pill {
  font-size: 11px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 999px;
  background: #e0e7ff;
  color: #4338ca;
}

.stat-l1 {
  background: #dcfce7;
  color: #15803d;
}

.stat-warn {
  background: #fef3c7;
  color: #b45309;
}

.timeline {
  margin: 0;
  padding: 0;
  list-style: none;
}

.timeline-item {
  display: flex;
  gap: 14px;
  opacity: 0;
  transform: translateY(10px);
  transition: opacity 0.35s ease, transform 0.35s ease;
  &.is-visible {
    opacity: 1;
    transform: translateY(0);
  }
}

.timeline-rail {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  width: 28px;
}

.timeline-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: linear-gradient(135deg, #6366f1, #4f46e5);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;
  &.dot-core {
    background: linear-gradient(135deg, #f59e0b, #d97706);
  }
}

.timeline-line {
  flex: 1;
  width: 2px;
  min-height: 16px;
  background: linear-gradient(180deg, #c7d2fe, #e2e8f0);
  margin: 4px 0;
}

.timeline-card {
  flex: 1;
  margin-bottom: 14px;
  padding: 12px 14px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid #e2e8f0;
  box-shadow: 0 2px 6px rgba(15, 23, 42, 0.04);
}

.risk-border-l1 { border-left: 3px solid #22c55e; }
.risk-border-l2 { border-left: 3px solid #f59e0b; }
.risk-border-l3 { border-left: 3px solid #f97316; }
.risk-border-l4 { border-left: 3px solid #ef4444; }

.tc-top {
  display: flex;
  flex-wrap: wrap;
  align-items: flex-start;
  gap: 8px;
}

.tc-action {
  flex: 1;
  font-size: 14px;
  font-weight: 600;
  line-height: 1.55;
  color: #1e293b;
  min-width: 60%;
}

.core-tag {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 999px;
  background: #f59e0b;
  color: #fff;
}

.tc-risk {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 999px;
}
.risk-l1 { background: #ecfdf5; color: #059669; }
.risk-l2 { background: #fef3c7; color: #b45309; }
.risk-l3 { background: #fff7ed; color: #c2410c; }
.risk-l4 { background: #fef2f2; color: #dc2626; }

.tc-expected,
.tc-tool {
  margin-top: 10px;
  font-size: 12px;
  line-height: 1.55;
  color: #64748b;
}

.tc-label {
  font-weight: 600;
  color: #475569;
  margin-right: 6px;
}

.tc-tool code {
  font-family: ui-monospace, Menlo, monospace;
  font-size: 11px;
  padding: 4px 8px;
  border-radius: 6px;
  background: #f1f5f9;
  color: #4338ca;
  border: 1px solid #e2e8f0;
  word-break: break-all;
}

.risk-note {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  margin: 0 0 10px;
  padding: 12px 14px;
  border-radius: 10px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  font-size: 12px;
  line-height: 1.6;
  color: #b45309;
}

.risk-note-icon {
  flex-shrink: 0;
}

/* ── 页脚 ── */
.plan-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  padding: 14px 18px;
  border-top: 1px solid #e2e8f0;
  background: linear-gradient(180deg, #fafbfc, #f1f5f9);
}

.foot-hint {
  font-size: 12px;
  color: #64748b;
  flex: 1;
  min-width: 180px;
}

.foot-actions {
  display: flex;
  gap: 10px;
}

.readonly-foot {
  justify-content: flex-start;
}

.readonly-badge {
  font-size: 12px;
  font-weight: 600;
  color: #059669;
  padding: 5px 12px;
  border-radius: 8px;
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
}

.btn-cancel,
.btn-run {
  padding: 10px 18px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  border: none;
  transition: transform 0.15s, box-shadow 0.15s;
}

.btn-cancel {
  background: #fff;
  color: #475569;
  border: 1px solid #e2e8f0;
  &:hover { background: #f1f5f9; }
}

.btn-run {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: linear-gradient(135deg, #2563eb, #4f46e5);
  color: #fff;
  box-shadow: 0 3px 10px rgba(37, 99, 235, 0.35);
  &:hover {
    transform: translateY(-1px);
    box-shadow: 0 5px 14px rgba(37, 99, 235, 0.4);
  }
}

.btn-step-count {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.25);
}

.stream-in {
  animation: streamIn 0.4s ease both;
}

@keyframes streamIn {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
