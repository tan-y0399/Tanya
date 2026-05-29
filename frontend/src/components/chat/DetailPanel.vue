<template>
  <div class="detail-panel" :class="{ 'fullscreen': isFullscreen }" v-if="visible">
    <div class="panel-header">
      <h3>{{ title }}</h3>
      <div class="header-buttons">
        <button class="fullscreen-btn" @click="toggleFullscreen" :title="isFullscreen ? '退出全屏' : '全屏放大'">
          <svg v-if="!isFullscreen" width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M3 3h4v1h-3v3H3V3zM13 10v3h-3v1h4v-4h-1zM13 3h-4v1h3v3h1V3zM3 10v3h4v-1H4v-3H3z" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <svg v-else width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M5 3H3v2h2V3zM11 3h2v2h-2V3zM5 13H3v-2h2v2zM11 13h2v-2h-2v2z" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
        <button class="close-btn" @click="$emit('close')">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <path d="M4 4l8 8M12 4l-8 8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </button>
      </div>
    </div>

    <div class="panel-content">
      <!-- TraceId 链路时间线 -->
      <template v-if="mode === 'trace' && (traceEvents || []).length">
        <div class="trace-event" v-for="(ev, i) in (traceEvents || [])" :key="i">
          <div class="event-side">
            <div class="event-dot" :class="ev.type"></div>
            <div class="event-line" v-if="i < (traceEvents || []).length - 1"></div>
          </div>
          <div class="event-body">
            <div class="event-type">{{ ev.label }}</div>
            <div class="event-time">{{ ev.time }}</div>
            <div class="event-detail" v-if="ev.detail">{{ ev.detail }}</div>
          </div>
        </div>
      </template>

      <!-- 工具详情 -->
      <template v-if="mode === 'tool' && toolDetail">
        <div class="detail-block">
          <div class="detail-label">工具</div>
          <div class="detail-value mono">{{ toolDetail.toolName }}</div>
        </div>
        <div class="detail-row">
          <div class="detail-block half">
            <div class="detail-label">状态</div>
            <div class="detail-value">
              <span class="status-chip" :class="toolDetail.status">
                {{ {executing:'执行中',completed:'已完成',rejected:'已拒绝',timeout:'超时',blocked:'已阻止',pending_approval:'待审批',pending_confirm:'待确认'}[toolDetail.status] }}
              </span>
            </div>
          </div>
          <div class="detail-block half">
            <div class="detail-label">风险</div>
            <div class="detail-value">
              <span class="risk-chip" :class="`l${toolDetail.riskLevel || 'L1'}`">L{{ toolDetail.riskLevel || '1' }}</span>
            </div>
          </div>
        </div>

        <!-- 入参 -->
        <div class="detail-block" v-if="toolDetail.params && Object.keys(toolDetail.params).length">
          <div class="detail-label">入参</div>
          <pre class="code-block">{{ JSON.stringify(toolDetail.params, null, 2) }}</pre>
        </div>

        <!-- 结果 - 结构化展示 -->
        <div class="detail-block" v-if="toolDetail.result">
          <div class="detail-label">执行结果</div>
          <template v-if="toolDetail.result.success === true && toolDetail.result.data">
            <!-- 结构化数据展示 -->
            <div class="result-data">
              <template v-if="typeof toolDetail.result.data === 'object' && !Array.isArray(toolDetail.result.data)">
                <div class="kv-list">
                  <div class="kv-item" v-for="(v, k) in flattenResult(toolDetail.result.data)" :key="k">
                    <span class="kv-key">{{ k }}</span>
                    <span class="kv-value" :class="{ mono: isNumLike(v) }">{{ formatVal(v) }}</span>
                  </div>
                </div>
                <!-- 特殊处理 disks 数组 -->
                <div v-if="toolDetail.result.data.disks" class="sub-section">
                  <div class="sub-title">磁盘分区</div>
                  <div class="disk-table" v-for="d in toolDetail.result.data.disks" :key="d.filesystem">
                    <div class="disk-name">{{ d.filesystem }} <span class="disk-mount">→ {{ d.mount }}</span></div>
                    <div class="disk-bar">
                      <div class="disk-bar-fill" :style="{ width: d.use_percent || '0%', background: diskColor(d.use_percent) }"></div>
                    </div>
                    <div class="disk-info">{{ d.size }} 总量 · {{ d.used }} 已用 · {{ d.available }} 可用 ({{ d.use_percent }})</div>
                  </div>
                </div>
                
                <!-- 命令输出智能解析成表格 -->
                <div v-if="hasStdout && parsedTable" class="cmd-output-wrap">
                  <table v-if="parsedTable.type === 'table'" class="pretty-table">
                    <thead>
                      <tr>
                        <th v-for="(h, idx) in parsedTable.headers" :key="idx">
                          <span class="th-content">{{ h }}</span>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(row, rIdx) in (parsedTable?.rows || [])" :key="rIdx" class="data-row" :class="{ 'high-cpu': isHighCpuRow(row, parsedTable?.headers || []) }">
                        <td v-for="(cell, cIdx) in row" :key="cIdx" class="data-cell">{{ cell }}</td>
                      </tr>
                    </tbody>
                  </table>
                  <div v-else-if="parsedTable.type === 'list'" class="cmd-list-container">
                    <div v-for="(item, idx) in parsedTable.items" :key="idx" class="list-card">
                      <span class="list-index">{{ idx + 1 }}</span>
                      <span class="list-content">{{ item }}</span>
                    </div>
                  </div>
                </div>
                
                <!-- CPU分析和运维建议 -->
                <div v-if="hasCpuData && cpuAnalysis.length > 0" class="sub-section cpu-section">
                  <div class="sub-title">CPU使用分析</div>
                  <div class="cpu-chart-wrap">
                    <div v-for="(item, idx) in cpuAnalysis" :key="idx" class="cpu-item">
                      <div class="cpu-name">{{ item.command }}</div>
                      <div class="cpu-bar-wrap">
                        <div class="cpu-bar" :style="{ width: item.percent + '%', background: getCpuColor(item.percent) }"></div>
                      </div>
                      <div class="cpu-percent" :style="{ color: getCpuColor(item.percent) }">{{ item.percent }}%</div>
                    </div>
                  </div>
                </div>
                
                <!-- 运维建议 -->
                <div v-if="suggestions.length > 0" class="sub-section suggestions-section">
                  <div class="sub-title">运维建议</div>
                  <div class="suggestion-list">
                    <div v-for="(suggestion, idx) in suggestions" :key="idx" class="suggestion-item" :class="suggestion.type">
                      <div class="suggestion-icon">{{ suggestion.icon }}</div>
                      <div class="suggestion-text">{{ suggestion.text }}</div>
                    </div>
                  </div>
                </div>
              </template>
              
              <pre v-else class="code-block">{{ JSON.stringify(toolDetail.result.data, null, 2) }}</pre>
            </div>
          </template>
          <div v-else-if="toolDetail.result.success === false" class="result-error">
            {{ toolDetail.result.error || '执行失败' }}
          </div>
          <pre class="code-block" v-else>{{ JSON.stringify(toolDetail.result, null, 2) }}</pre>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import type { ToolCall } from '@/stores/chat'

const props = defineProps<{
  visible: boolean
  title: string
  mode: 'trace' | 'tool'
  traceEvents?: { type: string; label: string; time: string; detail?: string }[]
  toolDetail?: ToolCall | null
}>()

const emit = defineEmits<{ close: [] }>()

const isFullscreen = ref(false)

function toggleFullscreen() {
  isFullscreen.value = !isFullscreen.value
}

// 关闭面板时退出全屏
watch(() => props.visible, (newVal) => {
  if (!newVal) {
    isFullscreen.value = false
  }
})

// 计算属性 - 判断是否有stdout和raw
const hasStdout = computed(() => {
  return props.toolDetail?.result?.data?.stdout !== undefined
})

const hasRaw = computed(() => {
  return props.toolDetail?.result?.data?.raw !== undefined
})

// 检查是否有CPU数据
const hasCpuData = computed(() => {
  return hasStdout.value && parsedTable.value?.type === 'table' &&
         (parsedTable.value?.headers ?? []).some(h => h.includes('%CPU') || h.includes('CPU'))
})

// CPU分析数据
const cpuAnalysis = computed(() => {
  if (!hasCpuData.value || !parsedTable.value) return []
  
  const table = parsedTable.value
  const headers = table.headers ?? []
  const rows = table.rows ?? []
  const cpuIndex = headers.findIndex(h => h.includes('%CPU') || h.includes('CPU'))
  const commandIndex = headers.findIndex(h => h.includes('COMMAND') || h.includes('CMD') || h.includes('command'))
  
  if (cpuIndex === -1) return []
  
  const analysis: { command: string; percent: number }[] = []
  
  rows.forEach(row => {
    const cpuStr = row[cpuIndex]
    const cpu = parseFloat(cpuStr)
    if (!isNaN(cpu) && cpu > 0) {
      let command = commandIndex >= 0 ? row[commandIndex] : ''
      // 简化命令显示
      if (command.length > 40) {
        command = command.substring(0, 37) + '...'
      }
      analysis.push({ command: command || `进程 ${analysis.length + 1}`, percent: cpu })
    }
  })
  
  // 按CPU使用率排序，只显示前5个
  return analysis.sort((a, b) => b.percent - a.percent).slice(0, 5)
})

// 运维建议
const suggestions = computed(() => {
  const suggestionList: { type: 'warning' | 'info' | 'success'; icon: string; text: string }[] = []
  
  if (hasCpuData.value && cpuAnalysis.value.length > 0) {
    const highCpu = cpuAnalysis.value.filter(item => item.percent > 50)
    const mediumCpu = cpuAnalysis.value.filter(item => item.percent >= 20 && item.percent <= 50)
    
    if (highCpu.length > 0) {
      suggestionList.push({
        type: 'warning',
        icon: '⚠️',
        text: `发现 ${highCpu.length} 个CPU使用率超过50%的进程，建议关注性能瓶颈`
      })
    }
    
    if (mediumCpu.length > 2) {
      suggestionList.push({
        type: 'info',
        icon: '💡',
        text: '有多个进程CPU使用率较高，建议检查是否有资源竞争'
      })
    }
    
    suggestionList.push({
      type: 'success',
      icon: '✅',
      text: '已获取进程CPU使用情况，可根据需要进一步分析'
    })
  }
  
  // 其他通用建议
  if (!hasCpuData.value && hasStdout.value) {
    suggestionList.push({
      type: 'info',
      icon: '📊',
      text: '可以尝试使用 `ps aux --sort=-%cpu` 命令获取CPU使用详情'
    })
  }
  
  return suggestionList
})

// 判断是否是高CPU行
function isHighCpuRow(row: string[], headers: string[]): boolean {
  const cpuIndex = headers.findIndex(h => h.includes('%CPU') || h.includes('CPU'))
  if (cpuIndex === -1) return false
  
  const cpu = parseFloat(row[cpuIndex])
  return !isNaN(cpu) && cpu > 50
}

// 获取CPU颜色
function getCpuColor(percent: number): string {
  if (percent > 70) return '#ef4444'
  if (percent > 50) return '#f59e0b'
  if (percent > 20) return '#3b82f6'
  return '#10b981'
}

// 智能解析命令输出为表格
const parsedTable = computed(() => {
  if (!hasStdout.value) return null
  const stdout = (props.toolDetail?.result?.data as any)?.stdout as string
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

function flattenResult(data: Record<string, any>, prefix = ''): Record<string, any> {
  const result: Record<string, any> = {}
  for (const [k, v] of Object.entries(data)) {
    if (k === 'disks' || k === 'all_disks' || k === 'raw') continue
    const key = prefix ? `${prefix}.${k}` : k
    if (typeof v === 'object' && v !== null && !Array.isArray(v)) {
      Object.assign(result, flattenResult(v, key))
    } else {
      result[key] = v
    }
  }
  return result
}

function isNumLike(v: any): boolean {
  return typeof v === 'number' || (typeof v === 'string' && !isNaN(Number(v)) && v.length < 10)
}

function formatVal(v: any): string {
  if (v === null || v === undefined) return '-'
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

function diskColor(pct: string | undefined): string {
  const n = parseFloat(pct || '0')
  if (n > 80) return '#ef4444'
  if (n > 60) return '#f59e0b'
  return '#10b981'
}
</script>

<style lang="scss" scoped>
.detail-panel {
  width: 300px;
  min-width: 300px;
  height: 100%;
  display: flex;
  flex-direction: column;
  border-left: 1px solid #e2e8f0;
  background: #ffffff;
  transition: all 0.3s ease;
  &.fullscreen {
    position: fixed;
    top: 0;
    right: 0;
    width: 100vw;
    min-width: 100vw;
    height: 100vh;
    z-index: 9999;
    border-left: none;
    box-shadow: -10px 0 40px rgba(0, 0, 0, 0.1);
  }
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px;
  border-bottom: 1px solid #f1f5f9;
  h3 {
    font-size: 13px;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
}

.header-buttons {
  display: flex;
  align-items: center;
  gap: 8px;
}

.fullscreen-btn {
  background: none;
  border: none;
  color: #94a3b8;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: all 0.15s ease;
  &:hover {
    color: #2563eb;
    background: #eff6ff;
  }
}

.close-btn {
  background: none;
  border: none;
  color: #94a3b8;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  &:hover { color: #ef4444; background: #fef2f2; }
}

.panel-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.trace-event {
  display: flex;
  gap: 10px;
  padding-bottom: 0;
}

.event-side {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 16px;
  flex-shrink: 0;
  .event-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #cbd5e1;
    flex-shrink: 0;
    &.user { background: #3b82f6; }
    &.llm { background: #2563eb; }
    &.security { background: #f59e0b; }
    &.approval { background: #f59e0b; }
    &.tool { background: #10b981; }
    &.error { background: #ef4444; }
  }
  .event-line {
    flex: 1;
    width: 1px;
    background: #e2e8f0;
    margin: 4px 0;
    min-height: 20px;
  }
}

.event-body {
  flex: 1;
  padding-bottom: 12px;
  .event-type { font-size: 13px; color: #1e293b; font-weight: 500; }
  .event-time { font-size: 11px; color: #94a3b8; margin-top: 2px; }
  .event-detail { font-size: 12px; color: #64748b; margin-top: 4px; }
}

.detail-block {
  margin-bottom: 14px;
}

.detail-label {
  font-size: 11px;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
}

.detail-value {
  font-size: 13px;
  color: #1e293b;
  &.mono { font-family: 'JetBrains Mono', Consolas, monospace; color: #2563eb; }
}

.code-block {
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 12px;
  background: #f8fafc;
  color: #1e293b;
  padding: 10px;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
  max-height: 300px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
  line-height: 1.5;
}

.detail-row { display: flex; gap: 12px; .half { flex: 1; } }

.status-chip {
  font-size: 12px; padding: 2px 8px; border-radius: 4px; font-weight: 500;
  &.completed { background: #ecfdf5; color: #059669; }
  &.executing { background: #fffbeb; color: #b45309; }
  &.rejected, &.timeout { background: #fef2f2; color: #dc2626; }
}

.risk-chip {
  font-size: 12px; padding: 2px 8px; border-radius: 4px; font-weight: 600;
  &.l1 { background: #f1f5f9; color: #94a3b8; }
  &.l2 { background: #fffbeb; color: #b45309; }
  &.l3, &.l4 { background: #fef2f2; color: #dc2626; }
}

.kv-list { display: flex; flex-direction: column; gap: 1px; }
.kv-item {
  display: flex; gap: 8px; padding: 6px 8px; border-radius: 4px;
  &:nth-child(odd) { background: #f8fafc; }
}
.kv-key {
  font-size: 11px; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.3px;
  min-width: 80px; flex-shrink: 0;
}
.kv-value {
  font-size: 13px; color: #1e293b; word-break: break-all;
  &.mono { font-family: 'JetBrains Mono', Consolas, monospace; color: #2563eb; }
}

.sub-section { margin-top: 10px; }
.sub-title { font-size: 11px; font-weight: 600; color: #94a3b8; text-transform: uppercase; margin-bottom: 6px; }

.disk-table {
  padding: 8px; margin-bottom: 6px; border-radius: 6px; background: #f8fafc; border: 1px solid #f1f5f9;
}
.disk-name { font-size: 12px; font-weight: 500; color: #1e293b; }
.disk-mount { color: #94a3b8; font-size: 11px; }
.disk-bar {
  height: 6px; background: #e2e8f0; border-radius: 3px; margin: 6px 0; overflow: hidden;
  .disk-bar-fill { height: 100%; border-radius: 3px; transition: width 0.3s; }
}
.disk-info { font-size: 11px; color: #94a3b8; }

.result-error { padding: 10px; border-radius: 6px; background: #fef2f2; color: #dc2626; font-size: 13px; border: 1px solid #fecaca; }

.cmd-output-wrap {
  margin-top: 12px;
}

.pretty-table {
  width: 100%;
  border-collapse: separate;
  border-spacing: 0;
  font-size: 13px;
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
  border: 1px solid #e2e8f0;
  
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
        transform: scale(1.002);
        
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
        font-family: 'JetBrains Mono', Consolas, monospace;
        font-size: 12px;
        border-bottom: 1px solid #f1f5f9;
        transition: all 0.2s ease;
      }
    }
  }
}

.cmd-list-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 12px;
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
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 12px;
  font-weight: 600;
  border-radius: 8px;
  flex-shrink: 0;
}

.list-content {
  flex: 1;
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 12px;
  color: #334155;
  line-height: 1.6;
}

/* 高CPU行高亮 */
.pretty-table tbody .data-row.high-cpu {
  background: #fff1f0;
  border-left: 3px solid #ef4444;
  
  &:nth-child(even) {
    background: #fff1f0;
  }
  
  &:hover {
    background: #ffe0e0 !important;
  }
}

/* CPU分析区域 */
.cpu-section {
  margin-top: 16px;
}

.cpu-chart-wrap {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.cpu-item {
  display: grid;
  grid-template-columns: 180px 1fr 60px;
  gap: 12px;
  align-items: center;
}

.cpu-name {
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 12px;
  color: #334155;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cpu-bar-wrap {
  height: 8px;
  background: #e2e8f0;
  border-radius: 4px;
  overflow: hidden;
}

.cpu-bar {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
}

.cpu-percent {
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 14px;
  font-weight: 600;
  text-align: right;
}

/* 运维建议区域 */
.suggestions-section {
  margin-top: 16px;
}

.suggestion-list {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.suggestion-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 14px;
  border-radius: 8px;
  transition: all 0.2s ease;
  
  &:hover {
    transform: translateX(4px);
  }
  
  &.warning {
    background: #fffbeb;
    border: 1px solid #fef3c7;
  }
  
  &.info {
    background: #eff6ff;
    border: 1px solid #dbeafe;
  }
  
  &.success {
    background: #f0fdf4;
    border: 1px solid #dcfce7;
  }
}

.suggestion-icon {
  font-size: 18px;
  flex-shrink: 0;
  margin-top: 1px;
}

.suggestion-text {
  flex: 1;
  font-size: 13px;
  color: #334155;
  line-height: 1.5;
}

/* 全屏状态下的优化样式 */
.detail-panel.fullscreen {
  .panel-content {
    padding: 24px 40px;
  }
  
  .pretty-table {
    font-size: 14px;
    thead th {
      padding: 18px 24px;
      font-size: 13px;
    }
    tbody .data-cell {
      padding: 16px 24px;
      font-size: 13px;
    }
  }
  
  .list-card {
    padding: 16px 20px;
  }
  
  .code-block {
    font-size: 13px;
    padding: 16px;
    max-height: 500px;
  }
  
  .detail-label {
    font-size: 12px;
  }
  
  .cpu-item {
    grid-template-columns: 220px 1fr 70px;
  }
  
  .cpu-name {
    font-size: 13px;
  }
  
  .cpu-percent {
    font-size: 16px;
  }
  
  .suggestion-text {
    font-size: 14px;
  }
}
</style>
