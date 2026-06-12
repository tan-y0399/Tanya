/** 思考步骤文案规范化（展示用，与后端 id 解耦） */

const TITLE_MAP: Record<string, string> = {
  sec: '安全预检',
  intent: '意图识别',
  route: '任务路由',
  llm: '智能推理',
  plan_gen: '诊断方案',
  summary: '结果总结',
}

const TITLE_PREFIX_MAP: Record<string, string> = {
  risk: '风险评估',
  exec: '远程执行',
  plan: '方案步骤',
}

export function formatExploringTitle(raw: string, id?: string): string {
  if (!raw) return '处理中'
  if (id && TITLE_MAP[id]) return TITLE_MAP[id]

  for (const [prefix, label] of Object.entries(TITLE_PREFIX_MAP)) {
    if (id?.startsWith(prefix + '-')) {
      const m = raw.match(/\[([^\]]+)\]/)
      const tool = m?.[1]
      return tool ? `${label} · ${friendlyToolName(tool)}` : label
    }
  }

  return raw
    .replace(/^安全预检 prompt_guard.*$/i, '安全预检')
    .replace(/^意图分类 \+ 知识库检索.*$/i, '意图识别与知识检索')
    .replace(/^路由分发 task_router.*$/i, '任务路由')
    .replace(/^DeepSeek Agent 推理.*$/i, '智能推理')
    .replace(/^评估命令风险 /, '风险评估 · ')
    .replace(/^SSH 执行 /, '远程执行 · ')
    .replace(/^生成执行结果总结.*$/i, '生成执行结论')
    .trim()
}

export function formatExploringDetail(detail?: string, status?: string): string {
  if (!detail?.trim()) {
    return status === 'running' ? '进行中…' : status === 'done' ? '已完成' : ''
  }
  let d = detail.trim()

  if (d === '通过') return '✓ 安全检查通过'
  if (d === '完成') return '✓ 步骤完成'
  if (d.startsWith('拦截')) return d

  const intentM = d.match(/intent=([^\s]+)(?:\s+confidence=([\d.]+))?(?:\s+rag=(\w+))?/)
  if (intentM) {
    const intentZh: Record<string, string> = {
      ops_query: '运维查询',
      fault_analysis: '故障分析',
      high_risk: '高危处置',
      general: '通用对话',
    }
    const name = intentZh[intentM[1]] || intentM[1]
    const conf = intentM[2] ? ` · 置信度 ${(parseFloat(intentM[2]) * 100).toFixed(0)}%` : ''
    const rag = intentM[3] === 'hit' ? ' · 已命中知识库' : intentM[3] === 'miss' ? ' · 未命中知识库' : ''
    return `${name}${conf}${rag}`
  }

  if (d.startsWith('→')) {
    return d.replace('→', '').trim()
  }
  if (d.startsWith('初步等级')) {
    return d.replace('初步等级', '风险等级')
  }
  if (/^第 \d+\/\d+ 轮$/.test(d)) return d.replace('轮', '轮对话')

  if (d.startsWith('{') && d.endsWith('}')) {
    try {
      const o = JSON.parse(d)
      const keys = Object.keys(o).slice(0, 3)
      return keys.length ? keys.map(k => `${k}=${o[k]}`).join(' · ') : '执行参数已就绪'
    } catch {
      return '执行参数已就绪'
    }
  }

  if (d.length > 100) return d.slice(0, 97) + '…'
  return d
}

export function friendlyToolName(name: string): string {
  const map: Record<string, string> = {
    list_processes: '进程列表',
    get_network_connections: '网络连接',
    get_cpu_info: 'CPU 状态',
    get_memory_info: '内存状态',
    get_disk_usage: '磁盘使用',
    get_service_status: '服务状态',
    manage_service: '服务控制',
    execute_command: '命令执行',
    get_system_info: '系统信息',
  }
  return map[name] || name
}
