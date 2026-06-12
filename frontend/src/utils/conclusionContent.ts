/** 执行结论内容辅助：去重、剥离轻量模板、保留运维报告附录 */

import { REPORT_MARKER, TOOLS_MARKER } from './conclusionParser'

const LIGHTWEIGHT_MARKERS = [
  '已根据您的诉求',
  '已完成远程检查，结果如下',
  '以上数据来自目标主机实时查询',
  '如需进一步排查，请说明具体现象',
]

/** 是否为前端补全的轻量模板结论（非 LLM 深度总结） */
export function isLightweightConclusion(conclusion: string): boolean {
  if (!conclusion?.includes('## 执行结论')) return false
  const body = (conclusion.split('## 执行结论').pop() || '').trim()
  if (body.length < 40) return false
  const hasGeneric = LIGHTWEIGHT_MARKERS.some(m => body.includes(m))
  if (!hasGeneric) return false
  // 含具体 PID/百分比等深度指标则视为 LLM 结论
  if (/\bPID\s*\d+/i.test(body) || /占用.*\d+\.?\d*%/.test(body)) return false
  return true
}

/** 从完整 assistant 内容中拆出「工具标记后」的结论区与报告附录 */
export function splitConclusionAndReport(content: string): {
  head: string
  conclusion: string
  reportSuffix: string
} {
  const raw = content || ''
  const mi = raw.indexOf(TOOLS_MARKER)
  if (mi < 0) {
    return { head: raw, conclusion: '', reportSuffix: '' }
  }
  const head = raw.slice(0, mi + TOOLS_MARKER.length)
  const tail = raw.slice(mi + TOOLS_MARKER.length)
  const ri = tail.indexOf(REPORT_MARKER)
  if (ri < 0) {
    return { head, conclusion: tail, reportSuffix: '' }
  }
  return {
    head,
    conclusion: tail.slice(0, ri),
    reportSuffix: tail.slice(ri),
  }
}

/** 去掉轻量模板结论，保留报告附录 */
export function stripLightweightConclusion(content: string): string {
  const { head, conclusion, reportSuffix } = splitConclusionAndReport(content)
  if (!isLightweightConclusion(conclusion)) return content
  return head + reportSuffix
}

/** 写入/追加结论时保留报告附录 */
export function mergeConclusionPreservingReport(
  content: string,
  newConclusion: string,
): string {
  const { head, reportSuffix } = splitConclusionAndReport(content)
  const base = head || content
  if (!base.includes(TOOLS_MARKER)) {
    return newConclusion + reportSuffix
  }
  return base + newConclusion + reportSuffix
}

/** 取最后一个「## 执行结论」块（去重） */
export function extractLastConclusionBlock(text: string): string {
  if (!text?.includes('## 执行结论')) return text
  const parts = text.split(/##\s*执行结论/)
  const last = (parts[parts.length - 1] || '').trim()
  if (!last) return text
  return `## 执行结论\n\n${last}`
}
