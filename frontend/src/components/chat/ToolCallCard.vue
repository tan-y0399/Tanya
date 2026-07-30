<template>
  <div class="tc-card" :class="[`status-${tool.status}`, { 'tc-failed': isFailed }]">
    <!-- 头部 -->
    <div class="tc-header">
      <span class="tc-dot" :class="statusClass"></span>
      <div class="tc-title-block">
        <span class="tc-name">{{ displayName }}</span>
        <span class="tc-hint">{{ actionHint }}</span>
      </div>
      <span class="tc-status" :class="statusClass">{{ statusLabel }}</span>
      <span v-if="planStepLabel" class="tc-step">{{ planStepLabel }}</span>
      <div v-if="showRollbackArea" class="tc-header-actions">
        <RollbackButton
          v-if="showRollback || rolledBack"
          variant="single"
          size="sm"
          :busy="rollbackBusy"
          :rolled-back="rolledBack"
          :hint="rollbackHint"
          @click="$emit('rollback', tool)"
        />
        <span class="tc-risk" v-if="tool.riskLevel && tool.riskLevel !== 'L1'">{{ tool.riskLevel }}</span>
        <button v-if="tool.result || isTerminalFailure" class="tc-detail-btn" @click.stop="$emit('viewDetail', tool)" title="查看完整结果">
          详情
        </button>
      </div>
    </div>

    <!-- 执行中 -->
    <div v-if="tool.status === 'executing'" class="tc-loading">
      <span class="loading-bar"></span>
      <span class="loading-text">正在查询麒麟VM...</span>
    </div>

    <!-- 已拒绝 / 超时 / 审批未通过 -->
    <div v-else-if="isRejectionState" class="tc-reject-footer">
      <div class="tc-reject-inner">
        <span class="tc-reject-badge">{{ rejectBadge }}</span>
        <div class="tc-reject-copy">
          <p class="tc-reject-title">{{ rejectTitle }}</p>
          <p class="tc-reject-desc">{{ rejectDetail }}</p>
        </div>
      </div>
      <div v-if="commandPreview" class="tc-reject-cmd-row">
        <span class="tc-reject-cmd-label">未执行命令</span>
        <code class="tc-reject-cmd">{{ commandPreview }}</code>
      </div>
    </div>

    <!-- 待确认 / 待审批（仅展示，操作在底部确认框） -->
    <div v-else-if="tool.status === 'pending_confirm' || tool.status === 'pending_approval'" class="tc-body">
      <div class="tc-pending-block">
        <p class="tc-pending-title">{{ tool.status === 'pending_approval' ? '等待管理员审批' : '等待您确认执行' }}</p>
        <p v-if="planStepAction" class="tc-pending-action">{{ planStepAction }}</p>
        <code v-if="commandPreview" class="tc-pending-cmd">{{ commandPreview }}</code>
        <p class="tc-pending-hint">
          {{ tool.status === 'pending_approval'
            ? '审批通过后，请在本步骤上方的确认框中执行。'
            : '请在本步骤上方的确认框中点击「执行」。' }}
        </p>
      </div>
    </div>

    <!-- 结果 -->
    <div v-else-if="tool.result && tool.status === 'completed'" class="tc-body">
      <template v-if="tool.result.success && tool.result.data">
        <!-- 磁盘表格 -->
        <table v-if="hasDisks" class="tc-table">
          <thead><tr><th>分区</th><th>总量</th><th>已用</th><th>可用</th><th>使用率</th></tr></thead>
          <tbody>
            <tr v-for="d in tool.result.data.disks" :key="d.filesystem">
              <td><span class="disk-fs">{{ d.filesystem }}</span><span class="disk-mount"> → {{ d.mount }}</span></td>
              <td>{{ d.size }}</td><td>{{ d.used }}</td><td class="col-avail">{{ d.available }}</td>
              <td>
                <div class="mini-bar"><div class="mini-bar-fill" :style="{ width: d.use_percent || '0%', background: barColor(d.use_percent) }"></div></div>
                <span class="pct-text">{{ d.use_percent }}</span>
              </td>
            </tr>
          </tbody>
        </table>

        <!-- CPU 指标卡 -->
        <div v-else-if="isCpuData" class="metric-row">
          <div class="metric-card"><div class="metric-val">{{ tool.result.data.cpu_cores || '-' }}</div><div class="metric-key">CPU核心</div></div>
          <div class="metric-card"><div class="metric-val">{{ tool.result.data.cpu_usage || '0' }}%</div><div class="metric-key">使用率</div></div>
          <div class="metric-card"><div class="metric-val">{{ tool.result.data.load_1_5_15 || '-' }}</div><div class="metric-key">1m/5m/15m 负载</div></div>
        </div>

        <!-- 内存进度条 -->
        <div v-else-if="isMemData" class="mem-block">
          <div class="mem-bar-wrap">
            <div class="mem-bar"><div class="mem-bar-fill" :style="{ width: memPct + '%', background: barColor(String(memPct)) }"></div></div>
            <span class="mem-pct">{{ memPct.toFixed(1) }}%</span>
          </div>
          <div class="mem-info">总量 {{ tool.result.data.mem_total_mb || '?' }}MB · 已用 {{ tool.result.data.mem_used_mb || '?' }}MB · 可用 {{ tool.result.data.mem_available_mb || '?' }}MB</div>
          <div class="mem-info">Swap: {{ tool.result.data.swap_used_mb || '?' }}MB / {{ tool.result.data.swap_total_mb || '?' }}MB</div>
        </div>

        <!-- 服务状态（systemctl） -->
        <div v-else-if="isServiceStatus" class="service-block">
          <div class="svc-badge" :class="serviceActive ? 'svc-on' : 'svc-off'">
            {{ serviceSummary }}
          </div>
          <div class="svc-grid" v-if="serviceFields.length">
            <div v-for="f in serviceFields" :key="f.label" class="svc-row">
              <span class="svc-label">{{ f.label }}</span>
              <span class="svc-value">{{ f.value }}</span>
            </div>
          </div>
          <details v-if="serviceRaw" class="svc-raw">
            <summary>查看原始 systemctl 输出</summary>
            <pre class="tc-mini-pre">{{ serviceRaw }}</pre>
          </details>
        </div>

        <!-- 系统信息 KV -->
        <div v-else-if="tool.toolName === 'get_system_info'" class="kv-grid">
          <div v-for="(v, k) in flatObj(tool.result.data)" :key="k" class="kv-row">
            <span class="kv-k">{{ String(k).replace(/_/g, ' ') }}</span>
            <span class="kv-v">{{ String(v) }}</span>
          </div>
        </div>

        <!-- 命令输出表格化展示 -->
        <div v-else-if="isRunCommand && hasStdout && !preferPlainOutput && parsedTable" class="cmd-output-wrap">
          <div class="output-toolbar" v-if="showOutputToggle">
            <span class="output-hint">{{ outputWindowHint }}</span>
            <button type="button" class="output-toggle" @click="outputExpanded = !outputExpanded">
              {{ outputExpanded ? '收起' : '展开全部' }}
            </button>
          </div>
          <div class="output-window" :class="{ expanded: outputExpanded }">
          <div v-if="parsedTable.type === 'table'" class="cmd-table-container">
            <table class="pretty-table">
              <thead>
                <tr>
                  <th v-for="(h, idx) in parsedTable.headers" :key="idx">
                    <span class="th-content">{{ h }}</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, rIdx) in visibleTableRows" :key="rIdx" class="data-row">
                  <td v-for="(cell, cIdx) in row" :key="cIdx" class="data-cell">{{ cell }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else-if="parsedTable.type === 'list'" class="cmd-list-container">
            <div v-for="(item, idx) in visibleListItems" :key="idx" class="list-card">
              <span class="list-index">{{ idx + 1 }}</span>
              <span class="list-content">{{ item }}</span>
            </div>
          </div>
          <pre v-else class="tc-code">{{ visibleStdout }}</pre>
          </div>
        </div>

        <!-- 命令 KV / 纯文本输出 -->
        <div v-else-if="isRunCommand && hasStdout" class="cmd-output-wrap">
          <div v-if="displaySummary" class="output-toolbar">
            <span class="output-hint">{{ summaryWindowHint }}</span>
            <button v-if="summaryNeedsToggle" type="button" class="output-toggle" @click="outputExpanded = !outputExpanded">
              {{ outputExpanded ? '收起' : '展开全部' }}
            </button>
          </div>
          <div v-if="displaySummary" class="output-window" :class="{ expanded: outputExpanded }">
            <div class="summary-block">{{ visibleSummary }}</div>
          </div>
          <div v-if="parsedKvRows.length" class="kv-grid">
            <div v-for="row in parsedKvRows" :key="row.key" class="kv-row">
              <span class="kv-k">{{ row.key }}</span>
              <span class="kv-v">{{ row.value }}</span>
            </div>
          </div>
          <template v-else>
            <div class="output-toolbar" v-if="showOutputToggle">
              <span class="output-hint">{{ outputWindowHint }}</span>
              <button type="button" class="output-toggle" @click="outputExpanded = !outputExpanded">
                {{ outputExpanded ? '收起' : '展开全部' }}
              </button>
            </div>
            <div class="output-window" :class="{ expanded: outputExpanded }">
              <pre class="tc-code">{{ visibleStdout }}</pre>
            </div>
          </template>
        </div>

        <!-- 进程列表 -->
        <div v-else-if="hasRaw && tool.toolName.includes('process')">
          <pre class="tc-mini-pre">{{ procPreview }}</pre>
          <div v-if="procCount > 5" class="tc-more">共 {{ procCount }} 个进程，点击「详情 →」查看全部</div>
        </div>

        <!-- 网络/日志等纯文本 -->
        <div v-else-if="hasRaw" class="cmd-output-wrap">
          <div class="output-toolbar" v-if="showOutputToggle">
            <span class="output-hint">{{ outputWindowHint }}</span>
            <button type="button" class="output-toggle" @click="outputExpanded = !outputExpanded">
              {{ outputExpanded ? '收起' : '展开全部' }}
            </button>
          </div>
          <div class="output-window" :class="{ expanded: outputExpanded }">
            <pre class="tc-code">{{ visibleRaw }}</pre>
          </div>
        </div>

        <!-- 展示摘要（无专用模板时） -->
        <div v-else-if="displaySummary" class="cmd-output-wrap">
          <div class="output-toolbar">
            <span class="output-hint">{{ summaryWindowHint }}</span>
            <button v-if="summaryNeedsToggle" type="button" class="output-toggle" @click="outputExpanded = !outputExpanded">
              {{ outputExpanded ? '收起' : '展开全部' }}
            </button>
          </div>
          <div class="output-window" :class="{ expanded: outputExpanded }">
            <div class="summary-block">{{ visibleSummary }}</div>
          </div>
        </div>

        <!-- 通用 JSON -->
        <pre v-else class="tc-code">{{ formatJson(tool.result.data) }}</pre>
      </template>

      <div v-else-if="tool.result.success === false" class="tc-error-block">
        <span class="tc-error-icon">!</span>
        <div class="tc-error-text">
          <strong>执行未成功</strong>
          <p>{{ friendlyError }}</p>
        </div>
      </div>
      <pre v-else class="tc-code">{{ formatJson(tool.result) }}</pre>
    </div>

    <!-- 失败（非拒绝/超时） -->
    <div v-else-if="tool.status === 'failed' || tool.status === 'blocked'" class="tc-body">
      <div class="tc-error-block">
        <span class="tc-error-icon">!</span>
        <div class="tc-error-text">
          <strong>{{ tool.status === 'blocked' ? '操作已阻止' : '执行失败' }}</strong>
          <p>{{ friendlyError }}</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ToolCall } from '@/stores/chat'
import { toolDisplayName, toolActionHint } from '@/utils/toolDisplay'
import RollbackButton from '@/components/chat/RollbackButton.vue'

const props = defineProps<{
  tool: ToolCall
  rollbackEnabled?: boolean
  rollbackHint?: string
  rollbackBusy?: boolean
  rolledBack?: boolean
}>()
defineEmits<{ viewDetail: [tool: ToolCall]; rollback: [tool: ToolCall] }>()

const WRITE_TOOLS = new Set(['execute_command', 'run_command', 'manage_service', 'kill_process'])
const ROLLBACK_RISKS = new Set(['L2', 'L3', 'L4'])
const LOG_TOOL_NAMES = new Set(['get_logs', 'read_log_file', 'search_journal_logs'])
const COLLAPSED_TABLE_ROWS = 8
const COLLAPSED_LIST_ITEMS = 10
const COLLAPSED_TEXT_LINES = 8
const LONG_TEXT_THRESHOLD = 900

const outputExpanded = ref(false)

const showRollback = computed(() => {
  if (props.tool.status !== 'completed' || props.rolledBack || props.tool.result?.success === false) {
    return false
  }
  if (props.rollbackEnabled) return true
  const risk = props.tool.riskLevel || ''
  return ROLLBACK_RISKS.has(risk) && WRITE_TOOLS.has(props.tool.toolName || '')
})

const isFailed = computed(() =>
  props.tool.status === 'failed'
  || props.tool.status === 'rejected'
  || props.tool.status === 'timeout'
  || props.tool.status === 'blocked'
  || (props.tool.status === 'completed' && props.tool.result?.success === false),
)

const isRejectionState = computed(() => {
  const status = props.tool.status
  if (status === 'rejected' || status === 'timeout') return true
  if (props.tool.result?.success !== false) return false
  const err = String(props.tool.result?.error || '')
  return /拒绝|审批未通过|不予执行|已超时|未批准/.test(err)
})

const isTerminalFailure = computed(() =>
  ['rejected', 'timeout', 'failed', 'blocked'].includes(props.tool.status) || isRejectionState.value,
)

const showRollbackArea = computed(() =>
  showRollback.value
  || props.rolledBack
  || (props.tool.riskLevel && props.tool.riskLevel !== 'L1')
  || !!(props.tool.result || isTerminalFailure.value),
)

const rejectBadge = computed(() =>
  props.tool.status === 'timeout' ? '超时' : '未通过',
)

const rejectTitle = computed(() =>
  props.tool.status === 'timeout' ? '审批已超时' : '工具调用被拒绝',
)

const rejectDetail = computed(() => {
  const err = props.tool.result?.error
  if (err) {
    const text = String(err)
    if (text === rejectTitle.value) {
      return props.tool.status === 'timeout'
        ? '该操作未在审批时限内完成，命令未在虚拟机执行。'
        : '管理员未批准此次操作，命令未在虚拟机执行。'
    }
    return text
  }
  if (props.tool.status === 'timeout') {
    return '该操作未在审批时限内完成，命令未在虚拟机执行。'
  }
  return '管理员未批准此次操作，命令未在虚拟机执行。'
})

const commandPreview = computed(() => {
  const p = props.tool.params || {}
  if (props.tool.toolName === 'manage_service') {
    const svc = p.service_name || p.service || '?'
    return `systemctl ${p.action || '?'} ${svc}`
  }
  if (p.command) return String(p.command)
  if (p.cmd) return String(p.cmd)
  return ''
})

const statusClass = computed(() => {
  if (isFailed.value) return 'status-err'
  if (props.tool.status === 'pending_confirm' || props.tool.status === 'pending_approval') return 'status-warn'
  const m: Record<string, string> = {
    executing: 'status-busy', completed: 'status-ok',
  }
  return m[props.tool.status] || ''
})

const planStepLabel = computed(() => {
  const order = (props.tool as any).planStepOrder
  const total = (props.tool as any).planStepTotal
  if (!order || !total) return ''
  return `步骤 ${order}/${total}`
})

const planStepAction = computed(() =>
  String((props.tool as any).planStepAction || ''),
)

const statusLabel = computed(() => {
  if (props.tool.status === 'executing') return '执行中'
  if (props.tool.status === 'pending_confirm') return '待确认'
  if (props.tool.status === 'pending_approval') return '待审批'
  if (isFailed.value) return '失败'
  if (props.tool.status === 'completed') return '已完成'
  const m: Record<string, string> = {
    failed: '失败', rejected: '已拒绝', timeout: '超时', blocked: '已阻止',
  }
  return m[props.tool.status] || ''
})

const displayName = computed(() => toolDisplayName(props.tool.toolName))
const actionHint = computed(() => {
  if (isRejectionState.value) {
    return props.tool.status === 'timeout' ? '审批超时，命令未执行' : '审批未通过，命令未执行'
  }
  return toolActionHint(props.tool.toolName, props.tool.params)
})

const friendlyError = computed(() => {
  const err = props.tool.result?.error || '工具执行失败，请查看详情或重试'
  return String(err).replace(/^get_process_list\(\)\s*/, '')
})

const data = computed(() => props.tool.result?.data)
const hasDisks = computed(() => data.value?.disks && Array.isArray(data.value.disks))
const hasRaw = computed(() => !!data.value?.raw)
const hasStdout = computed(() => !!data.value?.stdout)
const isCpuData = computed(() => data.value && ('cpu_cores' in data.value || 'cpu_usage' in data.value))
const isMemData = computed(() => data.value && ('mem_total_mb' in data.value || 'mem_used_mb' in data.value))
const isRunCommand = computed(() => props.tool.toolName === 'execute_command' || props.tool.toolName === 'run_command')
const executedCommand = computed(() =>
  String(props.tool.params?.command || props.tool.params?.cmd || '').toLowerCase(),
)
const isLogLikeOutput = computed(() => {
  if (LOG_TOOL_NAMES.has(props.tool.toolName || '')) return true
  const cmd = executedCommand.value
  if (/\b(journalctl|dmesg|tail|less)\b|\/var\/log|\.log\b/.test(cmd)) return true

  const source = [stdoutText.value, rawText.value, displaySummary.value].filter(Boolean).join('\n')
  const lines = source.split('\n').filter(Boolean).slice(0, 20)
  if (lines.length < 3) return false
  const logLineCount = lines.filter(line =>
    /^[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+/.test(line)
    || /^\d{1,2}\s*月\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}\s+/.test(line)
    || /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}/.test(line)
    || /\b(systemd|kernel|audit|dbus|gnome-session|lightdm|sshd|localhost\.localdomain)\b/i.test(line),
  ).length
  return logLineCount >= Math.max(3, Math.floor(lines.length * 0.5))
})
const preferPlainOutput = computed(() =>
  isLogLikeOutput.value || (isRunCommand.value && /^(chronyc|timedatectl|date)\b/.test(executedCommand.value)),
)

const stdoutText = computed(() => String((data.value as any)?.stdout || ''))
const rawText = computed(() => String((data.value as any)?.raw || ''))
const activeText = computed(() => hasStdout.value ? stdoutText.value : rawText.value)
const activeTextLines = computed(() => activeText.value.split('\n'))

const visibleStdout = computed(() => compactText(stdoutText.value))
const visibleRaw = computed(() => compactText(rawText.value))

const visibleTableRows = computed(() => {
  const table = parsedTable.value
  if (!table || table.type !== 'table') return []
  const rows = Array.isArray(table.rows) ? table.rows : []
  return outputExpanded.value ? rows : rows.slice(0, COLLAPSED_TABLE_ROWS)
})

const visibleListItems = computed(() => {
  const table = parsedTable.value
  if (!table || table.type !== 'list') return []
  const items = Array.isArray(table.items) ? table.items : []
  return outputExpanded.value ? items : items.slice(0, COLLAPSED_LIST_ITEMS)
})

const showOutputToggle = computed(() => {
  const table = parsedTable.value
  if (summaryNeedsToggle.value) return true
  if (table?.type === 'table') return (table.rows?.length || 0) > COLLAPSED_TABLE_ROWS
  if (table?.type === 'list') return (table.items?.length || 0) > COLLAPSED_LIST_ITEMS
  return activeTextLines.value.length > COLLAPSED_TEXT_LINES || activeText.value.length > LONG_TEXT_THRESHOLD
})

const outputWindowHint = computed(() => {
  const table = parsedTable.value
  if (table?.type === 'table') {
    const rowCount = table.rows?.length || 0
    return outputExpanded.value
      ? `已展开全部 ${rowCount} 行`
      : `仅显示前 ${Math.min(COLLAPSED_TABLE_ROWS, rowCount)} 行，共 ${rowCount} 行`
  }
  if (table?.type === 'list') {
    const itemCount = table.items?.length || 0
    return outputExpanded.value
      ? `已展开全部 ${itemCount} 条`
      : `仅显示前 ${Math.min(COLLAPSED_LIST_ITEMS, itemCount)} 条，共 ${itemCount} 条`
  }
  const total = activeTextLines.value.length
  return outputExpanded.value
    ? `已展开全部 ${total} 行`
    : `仅显示前 ${Math.min(COLLAPSED_TEXT_LINES, total)} 行，共 ${total} 行`
})

const parsedKvRows = computed(() => {
  if (!hasStdout.value) return []
  if (preferPlainOutput.value || isLogLikeOutput.value) return []
  const stdout = String((data.value as any)?.stdout || '')
  if (!stdout.includes(':')) return []
  const rows: { key: string; value: string }[] = []
  for (const line of stdout.split('\n')) {
    if (!line.includes(':')) continue
    const idx = line.indexOf(':')
    const key = line.slice(0, idx).trim()
    const value = line.slice(idx + 1).trim()
    if (key && value) rows.push({ key, value })
  }
  return rows.length >= 3 ? rows : []
})

const isServiceStatus = computed(() => props.tool.toolName === 'get_service_status' || props.tool.toolName === 'manage_service')

const displaySummary = computed(() =>
  props.tool.displaySummary
  || props.tool.result?.display_summary
  || (data.value as any)?.summary
  || ''
)
const summaryText = computed(() => String(displaySummary.value || ''))
const summaryNeedsToggle = computed(() =>
  summaryText.value.split('\n').length > COLLAPSED_TEXT_LINES
  || summaryText.value.length > LONG_TEXT_THRESHOLD,
)
const visibleSummary = computed(() => compactText(summaryText.value))
const summaryWindowHint = computed(() => {
  const total = summaryText.value.split('\n').length
  return outputExpanded.value
    ? `已展开全部 ${total} 行摘要`
    : `仅显示前 ${Math.min(COLLAPSED_TEXT_LINES, total)} 行摘要`
})

const serviceActive = computed(() => !!(data.value as any)?.active)
const serviceSummary = computed(() => displaySummary.value || (serviceActive.value ? '服务运行中' : '服务未运行'))
const serviceRaw = computed(() => (data.value as any)?.raw_status || (data.value as any)?.status || '')

const serviceFields = computed(() => {
  const d = data.value as any
  if (!d || !isServiceStatus.value) return []
  const rows: { label: string; value: string }[] = []
  if (d.service) rows.push({ label: '服务名', value: d.service })
  if (d.state) rows.push({ label: '状态', value: `${d.state}${d.substate ? ` (${d.substate})` : ''}` })
  if (d.loaded) rows.push({ label: '开机自启', value: d.loaded })
  if (d.main_pid) rows.push({ label: '主进程 PID', value: String(d.main_pid) })
  if (d.since) rows.push({ label: '启动时间', value: d.since })
  if (d.memory) rows.push({ label: '内存占用', value: d.memory })
  return rows
})

const memPct = computed(() => {
  const d = data.value as any
  if (!d) return 0
  const fromField = parseFloat(d.usage_pct ?? d.mem_usage_pct)
  if (!Number.isNaN(fromField) && fromField > 0) return fromField
  const total = parseFloat(d.mem_total_mb)
  const used = parseFloat(d.mem_used_mb)
  if (total > 0 && !Number.isNaN(used)) return Math.round((used / total) * 1000) / 10
  return 0
})

const procPreview = computed(() => {
  const raw = (data.value as any)?.raw || ''
  const lines = raw.split('\n').filter(Boolean)
  return lines.slice(0, 6).join('\n')
})

const procCount = computed(() => {
  const raw = (data.value as any)?.raw || ''
  return raw.split('\n').filter(Boolean).length - 1
})

// 智能解析命令输出为表格
const parsedTable = computed(() => {
  if (!hasStdout.value) return null
  if (preferPlainOutput.value) return null
  const stdout = (data.value as any).stdout as string
  const lines = stdout.split('\n').filter(Boolean)
  
  if (lines.length === 0) return null

  // 尝试解析 ps 命令 - 特殊处理
  if (lines[0].includes('PID') && lines[0].includes('USER')) {
    const { headers, dataLines } = parsePsOutput(lines)
    if (headers.length > 0 && dataLines.length > 0) {
      return { type: 'table', headers, rows: dataLines }
    }
  }

  // 尝试解析 df / du 命令
  if ((lines[0].includes('Filesystem') || lines[0].includes('Size')) && lines.length > 1) {
    const { headers, dataLines } = parseGenericTable(lines)
    if (headers.length > 0 && dataLines.length > 0) {
      return { type: 'table', headers, rows: dataLines }
    }
  }

  // 尝试解析 ls -l 命令
  if (lines.every(l => /^[-dlcbps]/.test(l)) && lines.length > 0) {
    return { type: 'list', items: lines }
  }

  // 尝试解析 free 命令
  if (lines[0].includes('total') && lines[0].includes('used')) {
    const headers = ['类型', '总量', '已用', '可用', '共享', '缓冲/缓存', '可用']
    const rows = lines.slice(1).map(line => line.trim().split(/\s+/))
    return { type: 'table', headers: headers.slice(0, rows[0]?.length || headers.length), rows }
  }

  // 通用空格分隔表格 - 增强版
  if (lines.length > 1) {
    const { headers, dataLines } = parseGenericTable(lines)
    if (headers.length > 0 && dataLines.length > 0) {
      // 验证列数是否一致
      const validRows = dataLines.filter(row => row.length === headers.length)
      if (validRows.length > 0) {
        return { type: 'table', headers, rows: validRows }
      }
    }
  }

  // 列表形式
  if (lines.length > 1 && lines.length < 50) {
    return { type: 'list', items: lines }
  }

  return null
})

// 专门解析 ps 命令输出
function parsePsOutput(lines: string[]) {
  const headerLine = lines[0]
  const dataLines = lines.slice(1)
  
  // 找到所有标题的起始位置
  const headerMatches = [...headerLine.matchAll(/\b([A-Z%][A-Z0-9_]*)\b/g)]
  const headers: string[] = []
  const positions: number[] = []
  
  for (const match of headerMatches) {
    headers.push(match[0])
    positions.push(match.index || 0)
  }
  
  if (headers.length === 0) {
    return { headers: [], dataLines: [] }
  }
  
  // 按位置分割数据行
  const rows: string[][] = dataLines.map(line => {
    const row: string[] = []
    for (let i = 0; i < headers.length; i++) {
      const start = positions[i]
      const end = i < headers.length - 1 ? positions[i + 1] : line.length
      row.push(line.substring(start, end).trim())
    }
    return row
  })
  
  return { headers, dataLines: rows }
}

// 通用表格解析
function parseGenericTable(lines: string[]) {
  const headerLine = lines[0]
  const dataLines = lines.slice(1)
  
  // 首先尝试多空格分割
  let headers = parseHeadersByMultiSpace(headerLine)
  
  // 如果列数太少，尝试其他方法
  if (headers.length <= 2) {
    headers = parseHeadersBySingleSpace(headerLine)
  }
  
  // 解析数据行
  const rows: string[][] = dataLines.map(line => {
    let row = parseColumnsByPosition(line, headers, headerLine)
    if (row.length === headers.length) return row
    
    row = parseColumnsByMultiSpace(line)
    if (row.length === headers.length) return row
    
    return parseColumnsBySingleSpace(line)
  })
  
  return { headers, dataLines: rows }
}

// 按多空格分割表头
function parseHeadersByMultiSpace(line: string): string[] {
  return line.trim().split(/\s{2,}|\t/).filter(Boolean)
}

// 按单个空格分割表头
function parseHeadersBySingleSpace(line: string): string[] {
  return line.trim().split(/\s+/).filter(Boolean)
}

// 根据表头位置分割列
function parseColumnsByPosition(line: string, headers: string[], headerLine: string): string[] {
  const positions: number[] = []
  let currentIndex = 0
  
  for (const header of headers) {
    const index = headerLine.indexOf(header, currentIndex)
    if (index !== -1) {
      positions.push(index)
      currentIndex = index + header.length
    }
  }
  
  if (positions.length !== headers.length) {
    return []
  }
  
  const row: string[] = []
  for (let i = 0; i < headers.length; i++) {
    const start = positions[i]
    const end = i < headers.length - 1 ? positions[i + 1] : line.length
    row.push(line.substring(start, end).trim())
  }
  
  return row
}

// 按多空格分割列
function parseColumnsByMultiSpace(line: string): string[] {
  return line.trim().split(/\s{2,}|\t/).filter(Boolean)
}

// 按单个空格分割列
function parseColumnsBySingleSpace(line: string): string[] {
  return line.trim().split(/\s+/).filter(Boolean)
}

function compactText(text: string): string {
  if (outputExpanded.value) return text
  const lines = text.split('\n')
  if (lines.length <= COLLAPSED_TEXT_LINES && text.length <= LONG_TEXT_THRESHOLD) return text

  const preview = lines.slice(0, COLLAPSED_TEXT_LINES).join('\n')
  const hiddenLines = Math.max(0, lines.length - COLLAPSED_TEXT_LINES)
  if (hiddenLines > 0) {
    return `${preview}\n\n... 已折叠 ${hiddenLines} 行，点击“展开全部”查看完整日志`
  }
  return `${text.slice(0, LONG_TEXT_THRESHOLD)}\n\n... 内容较长，点击“展开全部”查看完整输出`
}

function flatObj(d: any): Record<string, any> {
  const result: Record<string, any> = {}
  for (const [k, v] of Object.entries(d || {})) {
    if (k === 'disks' || k === 'all_disks' || k === 'raw' || k === 'stdout' || k === 'stderr' || k === 'exit_code') continue
    if (typeof v === 'object' && v !== null && !Array.isArray(v)) {
      Object.assign(result, flatObj(v))
    } else {
      result[k] = String(v)
    }
  }
  return result
}

function barColor(p: string | undefined): string {
  const n = parseFloat(p || '0')
  if (n > 80) return '#ef4444'
  if (n > 60) return '#f59e0b'
  return '#10b981'
}

function formatJson(v: any): string {
  return typeof v === 'string' ? v : JSON.stringify(v, null, 2)
}
</script>

<style lang="scss" scoped>
.tc-card {
  margin: 0;
  border-radius: 12px;
  border: 1px solid #cbd5e1;
  background: #ffffff;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(15, 23, 42, 0.05);
  &.status-executing { border-color: #fde68a; }
  &.status-pending_confirm, &.status-pending_approval { border-color: #fed7aa; }
  &.status-rejected, &.status-timeout, &.status-failed, &.tc-failed { border-color: #fecaca; }
}
.tc-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 11px 14px;
  border-bottom: 1px solid #e2e8f0;
  background: linear-gradient(90deg, #f8fafc 0%, #fff 100%);
}
.tc-dot {
  width: 9px;
  height: 9px;
  border-radius: 50%;
  flex-shrink: 0;
  &.status-busy { background: #f59e0b; animation: blink 1s infinite; }
  &.status-ok { background: #10b981; }
  &.status-err { background: #ef4444; }
}
.tc-title-block {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.tc-name {
  font-size: 14px;
  color: #0f172a;
  font-weight: 700;
  line-height: 1.3;
}
.tc-hint {
  font-size: 11px;
  color: #64748b;
  line-height: 1.35;
}
.tc-status {
  font-size: 11px;
  font-weight: 600;
  padding: 3px 9px;
  border-radius: 10px;
  background: #f1f5f9;
  color: #64748b;
  &.status-ok { background: #dcfce7; color: #166534; }
  &.status-busy { background: #fef9c3; color: #854d0e; }
  &.status-warn { background: #ffedd5; color: #c2410c; }
  &.status-err { background: #fee2e2; color: #b91c1c; }
}
.tc-step {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 6px;
  background: #eff6ff;
  color: #1d4ed8;
  border: 1px solid #bfdbfe;
  flex-shrink: 0;
}
.tc-pending-block {
  padding: 12px 14px;
  border-radius: 10px;
  background: linear-gradient(135deg, #fff7ed 0%, #fffbeb 100%);
  border: 1px dashed #fdba74;
}
.tc-pending-title {
  margin: 0 0 6px;
  font-size: 13px;
  font-weight: 700;
  color: #9a3412;
}
.tc-pending-action {
  margin: 0 0 8px;
  font-size: 12px;
  color: #7c2d12;
}
.tc-pending-cmd {
  display: block;
  margin-bottom: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  background: #fff;
  border: 1px solid #fed7aa;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: #7c2d12;
  word-break: break-all;
  white-space: pre-wrap;
}
.tc-pending-hint {
  margin: 0;
  font-size: 12px;
  line-height: 1.55;
  color: #92400e;
}
.tc-pending-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 10px;
}
.tc-btn-skip, .tc-btn-cancel, .tc-btn-run {
  padding: 7px 14px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: all 0.15s;
}
.tc-btn-skip {
  background: transparent;
  color: #78716c;
  &:hover { background: rgba(255, 255, 255, 0.8); }
}
.tc-btn-cancel {
  background: #fff;
  color: #475569;
  border: 1px solid #e2e8f0;
  &:hover { background: #f8fafc; }
}
.tc-btn-run {
  background: #2563eb;
  color: #fff;
  &:hover { background: #1d4ed8; }
}
.tc-header-actions {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
  margin-left: auto;
  overflow: visible;
}
.tc-risk {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 6px;
  background: #fef2f2;
  color: #dc2626;
  border: 1px solid #fecaca;
}
.tc-detail-btn {
  font-size: 11px;
  color: #2563eb;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
  cursor: pointer;
  padding: 4px 10px;
  border-radius: 6px;
  font-weight: 600;
  &:hover { background: #dbeafe; }
}

.tc-loading { display: flex; align-items: center; gap: 10px; padding: 14px 16px; }
.loading-bar {
  width: 120px; height: 4px; background: #e2e8f0; border-radius: 2px; overflow: hidden;
  &::after { content: ''; display: block; width: 40%; height: 100%; background: linear-gradient(90deg, #f59e0b, #fbbf24, #f59e0b); border-radius: 2px; animation: slide 1.2s infinite; }
}
.loading-text { font-size: 12px; color: #94a3b8; }

.tc-body { padding: 14px 16px 16px; }

.tc-table {
  width: 100%; font-size: 12px; border-collapse: collapse;
  th { font-size: 11px; font-weight: 600; color: #64748b; text-transform: uppercase; text-align: left; padding: 10px 12px; border-bottom: 2px solid #e2e8f0; background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%); border-radius: 8px 8px 0 0; }
  td { padding: 10px 12px; border-bottom: 1px solid #f8fafc; color: #334155; font-size: 13px; }
  .disk-fs { font-family: 'JetBrains Mono', monospace; color: #2563eb; font-size: 12px; font-weight: 500; }
  .disk-mount { color: #94a3b8; font-size: 11px; }
  .col-avail { color: #059669; font-weight: 600; }
}

.cmd-output-wrap {
  min-width: 0;
}

.output-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.output-hint {
  min-width: 0;
  font-size: 12px;
  line-height: 1.5;
  color: #64748b;
}

.output-toggle {
  flex-shrink: 0;
  padding: 5px 10px;
  border-radius: 6px;
  border: 1px solid #bfdbfe;
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s ease;

  &:hover {
    background: #dbeafe;
    border-color: #93c5fd;
  }
}

.output-window {
  max-height: 320px;
  overflow: auto;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;

  &.expanded {
    max-height: min(70vh, 720px);
  }

  .tc-code {
    max-height: none;
    border: 0;
    border-radius: 0;
  }
}

// 美观的表格样式
.cmd-table-container {
  background: #ffffff;
  border-radius: 10px;
  overflow: auto;
  border: 1px solid #f1f5f9;
}
.pretty-table {
  width: 100%;
  min-width: 720px;
  border-collapse: separate;
  border-spacing: 0;
  font-size: 13px;
  
  thead {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    tr {
      th {
        padding: 14px 16px;
        text-align: left;
        color: #ffffff;
        font-weight: 600;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        border-bottom: none;
        
        &:first-child { border-top-left-radius: 10px; }
        &:last-child { border-top-right-radius: 10px; }
        
        .th-content {
          display: inline-flex;
          align-items: center;
          gap: 6px;
        }
      }
    }
  }
  
  tbody {
    .data-row {
      transition: all 0.2s ease;
      background: #ffffff;
      
      &:nth-child(even) {
        background: #f8fafc;
      }
      
      &:hover {
        background: linear-gradient(135deg, #eff6ff 0%, #e0e7ff 100%);
        transform: scale(1.005);
        
        .data-cell {
          color: #1e40af;
        }
      }
      
      &:last-child {
        .data-cell:first-child {
          border-bottom-left-radius: 10px;
        }
        .data-cell:last-child {
          border-bottom-right-radius: 10px;
        }
      }
      
      .data-cell {
        padding: 12px 16px;
        color: #334155;
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
        border-bottom: 1px solid #f1f5f9;
        transition: all 0.2s ease;
      }
    }
  }
}

// 美观的列表样式
.cmd-list-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.list-card {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 14px;
  background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  transition: all 0.2s ease;
  
  &:hover {
    transform: translateX(4px);
    border-color: #c7d2fe;
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.1);
  }
}

.list-index {
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  height: 28px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #ffffff;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  font-weight: 600;
  border-radius: 8px;
  flex-shrink: 0;
}

.list-content {
  flex: 1;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: #334155;
  line-height: 1.6;
}

.mini-bar { width: 56px; height: 4px; background: #e2e8f0; border-radius: 2px; overflow: hidden; display: inline-block; vertical-align: middle; margin-right: 6px; }
.mini-bar-fill { height: 100%; border-radius: 2px; }
.pct-text { font-size: 11px; color: #64748b; vertical-align: middle; }

.metric-row { display: flex; gap: 12px; }
.metric-card { flex: 1; text-align: center; padding: 14px 10px; background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%); border-radius: 10px; border: 1px solid #e2e8f0; }
.metric-val { font-family: 'JetBrains Mono', monospace; font-size: 20px; font-weight: 700; color: #2563eb; }
.metric-key { font-size: 11px; color: #64748b; margin-top: 6px; text-transform: uppercase; font-weight: 500; }

.mem-bar-wrap { display: flex; align-items: center; gap: 12px; }
.mem-bar { flex: 1; height: 12px; background: #e2e8f0; border-radius: 8px; overflow: hidden; }
.mem-bar-fill { height: 100%; border-radius: 8px; transition: width 0.4s ease; }
.mem-pct { font-family: 'JetBrains Mono', monospace; font-size: 20px; font-weight: 700; color: #1e293b; }
.mem-info { font-size: 12px; color: #64748b; margin-top: 8px; }

.kv-grid { display: flex; flex-direction: column; gap: 2px; }
.kv-row { display: flex; gap: 12px; padding: 8px 10px; border-radius: 8px; &:nth-child(odd) { background: #f8fafc; } }
.kv-k { font-size: 11px; color: #64748b; text-transform: uppercase; letter-spacing: 0.3px; min-width: 80px; font-weight: 500; }
.kv-v { font-size: 13px; color: #1e293b; font-family: 'JetBrains Mono', monospace; font-weight: 500; }

.tc-mini-pre { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #64748b; background: #f8fafc; padding: 12px; border-radius: 8px; margin: 0; overflow-x: auto; white-space: pre; line-height: 1.6; border: 1px solid #f1f5f9; }
.tc-more { font-size: 12px; color: #64748b; margin-top: 8px; }
.tc-code { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #475569; background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%); padding: 12px; border-radius: 8px; margin: 0; max-height: 220px; overflow: auto; white-space: pre-wrap; line-height: 1.6; border: 1px solid #e2e8f0; }
.tc-error-block {
  display: flex;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 8px;
  background: #fef2f2;
  border: 1px solid #fecaca;
}
.tc-error-icon {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  background: #ef4444;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.tc-error-text {
  flex: 1;
  min-width: 0;
  strong { display: block; font-size: 13px; color: #991b1b; margin-bottom: 4px; }
  p { margin: 0; font-size: 12px; line-height: 1.55; color: #b91c1c; word-break: break-word; }
}

.tc-reject-footer {
  padding: 12px 14px 14px;
  border-top: 1px solid #fecaca;
  background: linear-gradient(180deg, #fffbeb 0%, #fef2f2 100%);
  box-sizing: border-box;
}

.tc-reject-inner {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.tc-reject-badge {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 700;
  padding: 3px 8px;
  border-radius: 6px;
  background: #fee2e2;
  color: #b91c1c;
  border: 1px solid #fecaca;
  line-height: 1.2;
  margin-top: 1px;
}

.tc-reject-copy {
  flex: 1;
  min-width: 0;
}

.tc-reject-title {
  margin: 0 0 4px;
  font-size: 13px;
  font-weight: 600;
  color: #991b1b;
  line-height: 1.45;
  word-break: break-word;
}

.tc-reject-desc {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: #7f1d1d;
  word-break: break-word;
}

.tc-reject-cmd-row {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed #fecaca;
}

.tc-reject-cmd-label {
  display: block;
  font-size: 11px;
  color: #9a3412;
  margin-bottom: 6px;
  font-weight: 600;
}

.tc-reject-cmd {
  display: block;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid #fecaca;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  line-height: 1.5;
  color: #7f1d1d;
  word-break: break-all;
  white-space: pre-wrap;
}

.service-block { display: flex; flex-direction: column; gap: 12px; }
.svc-badge {
  padding: 12px 14px; border-radius: 10px; font-size: 14px; font-weight: 600; line-height: 1.5;
  &.svc-on { background: #ecfdf5; color: #047857; border: 1px solid #a7f3d0; }
  &.svc-off { background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; }
}
.svc-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.svc-row { padding: 8px 10px; background: #f8fafc; border-radius: 8px; border: 1px solid #f1f5f9; }
.svc-label { display: block; font-size: 11px; color: #64748b; margin-bottom: 2px; }
.svc-value { font-size: 13px; color: #1e293b; font-family: 'JetBrains Mono', monospace; word-break: break-all; }
.svc-raw summary { font-size: 12px; color: #64748b; cursor: pointer; user-select: none; }
.summary-block { font-size: 14px; line-height: 1.6; color: #334155; padding: 10px 12px; background: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0; white-space: pre-wrap; }

@keyframes blink { 0%,100%{opacity:1} 50%{opacity:.3} }
@keyframes slide { 0% { transform: translateX(-100%); } 100% { transform: translateX(350%); } }
</style>
