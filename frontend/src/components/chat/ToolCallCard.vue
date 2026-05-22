<template>
  <div class="tc-card" :class="[`status-${tool.status}`]">
    <!-- 头部 -->
    <div class="tc-header">
      <span class="tc-dot" :class="statusClass"></span>
      <span class="tc-name">{{ tool.toolName }}</span>
      <span class="tc-status">{{ statusLabel }}</span>
      <span class="tc-risk" v-if="tool.riskLevel && tool.riskLevel !== 'L1'">L{{ tool.riskLevel }}</span>
      <button v-if="tool.result" class="tc-detail-btn" @click.stop="$emit('viewDetail', tool)" title="查看完整结果">
        详情 →
      </button>
    </div>

    <!-- 执行中 -->
    <div v-if="tool.status === 'executing'" class="tc-loading">
      <span class="loading-bar"></span>
      <span class="loading-text">正在查询麒麟VM...</span>
    </div>

    <!-- 结果 -->
    <div v-if="tool.result && tool.status === 'completed'" class="tc-body">
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

        <!-- 系统信息 KV -->
        <div v-else-if="tool.toolName === 'get_system_info'" class="kv-grid">
          <div v-for="(v, k) in flatObj(tool.result.data)" :key="k" class="kv-row">
            <span class="kv-k">{{ String(k).replace(/_/g, ' ') }}</span>
            <span class="kv-v">{{ String(v) }}</span>
          </div>
        </div>

        <!-- 命令输出表格化展示 -->
        <div v-else-if="isRunCommand && hasStdout && parsedTable" class="cmd-output-wrap">
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
                <tr v-for="(row, rIdx) in parsedTable.rows" :key="rIdx" class="data-row">
                  <td v-for="(cell, cIdx) in row" :key="cIdx" class="data-cell">{{ cell }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else-if="parsedTable.type === 'list'" class="cmd-list-container">
            <div v-for="(item, idx) in parsedTable.items" :key="idx" class="list-card">
              <span class="list-index">{{ idx + 1 }}</span>
              <span class="list-content">{{ item }}</span>
            </div>
          </div>
          <pre v-else class="tc-code">{{ tool.result.data.stdout }}</pre>
        </div>

        <!-- 进程列表 -->
        <div v-else-if="hasRaw && tool.toolName.includes('process')">
          <pre class="tc-mini-pre">{{ procPreview }}</pre>
          <div v-if="procCount > 5" class="tc-more">共 {{ procCount }} 个进程，点击「详情 →」查看全部</div>
        </div>

        <!-- 网络/日志等纯文本 -->
        <pre v-else-if="hasRaw" class="tc-code">{{ tool.result.data.raw }}</pre>

        <!-- 通用 JSON -->
        <pre v-else class="tc-code">{{ formatJson(tool.result.data) }}</pre>
      </template>

      <div v-else-if="tool.result.success === false" class="tc-error">{{ tool.result.error || '执行失败' }}</div>
      <pre v-else class="tc-code">{{ formatJson(tool.result) }}</pre>
    </div>

    <!-- 失败 -->
    <div v-if="tool.status === 'rejected' || tool.status === 'timeout'" class="tc-error">
      {{ tool.status === 'rejected' ? '工具调用被拒绝' : '工具执行超时' }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ToolCall } from '@/stores/chat'

const props = defineProps<{ tool: ToolCall }>()
defineEmits<{ viewDetail: [tool: ToolCall] }>()

const statusClass = computed(() => {
  const m: Record<string, string> = { executing: 'dot-busy', completed: 'dot-ok', rejected: 'dot-err', timeout: 'dot-err' }
  return m[props.tool.status] || ''
})

const statusLabel = computed(() => {
  const m: Record<string, string> = { executing: '执行中...', completed: '已完成', rejected: '已拒绝', timeout: '超时' }
  return m[props.tool.status] || ''
})

const data = computed(() => props.tool.result?.data)
const hasDisks = computed(() => data.value?.disks && Array.isArray(data.value.disks))
const hasRaw = computed(() => !!data.value?.raw)
const hasStdout = computed(() => !!data.value?.stdout)
const isCpuData = computed(() => data.value && ('cpu_cores' in data.value || 'cpu_usage' in data.value))
const isMemData = computed(() => data.value && ('mem_total_mb' in data.value || 'mem_used_mb' in data.value))
const isRunCommand = computed(() => props.tool.toolName === 'execute_command' || props.tool.toolName === 'run_command')

const memPct = computed(() => {
  const d = data.value as any
  return parseFloat(d?.usage_pct || d?.mem_usage_pct || '0')
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
  margin: 6px 0; border-radius: 12px; border: 1px solid #e2e8f0; background: #ffffff; overflow: hidden;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.04);
  &.status-executing { border-color: #fde68a; }
  &.status-rejected, &.status-timeout { border-color: #fecaca; }
}
.tc-header {
  display: flex; align-items: center; gap: 8px; padding: 10px 16px; border-bottom: 1px solid #f1f5f9; background: linear-gradient(135deg, #f8fafc 0%, #fafbfc 100%);
}
.tc-dot {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
  &.dot-busy { background: #f59e0b; animation: blink 1s infinite; }
  &.dot-ok { background: #10b981; }
  &.dot-err { background: #ef4444; }
}
.tc-name { font-family: 'JetBrains Mono', monospace; font-size: 13px; color: #2563eb; font-weight: 600; flex: 1; }
.tc-status { font-size: 11px; color: #94a3b8; }
.tc-risk { font-size: 10px; font-weight: 600; padding: 2px 8px; border-radius: 6px; background: #fef2f2; color: #dc2626; border: 1px solid #fecaca; }
.tc-detail-btn {
  font-size: 11px; color: #2563eb; background: none; border: none; cursor: pointer; padding: 4px 10px; border-radius: 6px; font-weight: 500;
  &:hover { background: #eff6ff; transform: translateY(-1px); transition: all 0.2s ease; }
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

// 美观的表格样式
.cmd-table-container {
  background: #ffffff;
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid #f1f5f9;
}
.pretty-table {
  width: 100%;
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
.tc-error { padding: 10px 14px; border-radius: 8px; background: linear-gradient(135deg, #fef2f2 0%, #fee2e2 100%); color: #dc2626; font-size: 13px; border: 1px solid #fecaca; }

@keyframes blink { 0%,100%{opacity:1} 50%{opacity:.3} }
@keyframes slide { 0% { transform: translateX(-100%); } 100% { transform: translateX(350%); } }
</style>
