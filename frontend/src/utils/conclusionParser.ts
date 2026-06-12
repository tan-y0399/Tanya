/** 解析 Agent 执行结论区：隐藏技术标记，拆分结构化章节与运维报告 */

import { extractLastConclusionBlock } from './conclusionContent'

export const TOOLS_MARKER = '\n\n<!--KYLIN_TOOLS-->\n\n'
export const REPORT_MARKER = '<!--KYLIN_REPORT-->'

export interface ToolExecRow {
  risk: string
  name: string
  status: string
  summary: string
}

export interface ReportSection {
  title: string
  items: string[]
}

export interface ParsedOpsReport {
  title: string
  meta: { label: string; value: string }[]
  tools: ToolExecRow[]
  sections: ReportSection[]
}

export type ConclusionSectionId = 'overview' | 'findings' | 'suggestions' | 'stats' | 'other'

export interface ConclusionSection {
  id: ConclusionSectionId
  title: string
  type: 'paragraph' | 'list' | 'numbered'
  items: string[]
}

export interface ParsedConclusion {
  summaryHtml: string
  summaryPlain: string
  sections: ConclusionSection[]
  report: ParsedOpsReport | null
  error: string | null
}

const TOOL_RECORD_SECTION_TITLES = new Set([
  '工具执行记录',
  '排查过程与执行命令',
])

const SECTION_DEFS: { id: ConclusionSectionId; pattern: RegExp; title: string; type: ConclusionSection['type'] }[] = [
  { id: 'overview', pattern: /总览/, title: '总览', type: 'paragraph' },
  { id: 'findings', pattern: /关键发现/, title: '关键发现', type: 'list' },
  { id: 'suggestions', pattern: /结论与建议/, title: '结论与建议', type: 'numbered' },
  { id: 'stats', pattern: /统计|方案进度|方案执行摘要/, title: '执行统计', type: 'list' },
  { id: 'other', pattern: /说明|提示/, title: '补充说明', type: 'list' },
]

function stripTechnicalNoise(text: string): string {
  return text
    .replace(/<!--KYLIN_REPORT-->/g, '')
    .replace(/<!--KYLIN_TOOLS-->/g, '')
    .replace(/⚠\s*Agent 处理异常[^\n]*/g, '')
    .replace(/⚠\s*系统处理异常[^\n]*/g, '')
    .replace(/⚠\s*LLM 服务[^\n]*/g, '')
    .trim()
}

function extractError(text: string): string | null {
  const m = text.match(/⚠\s*(Agent 处理异常|系统处理异常|LLM 服务[^\n]+)[^\n]*/)
  return m ? m[0].trim() : null
}

function parseMetaLine(line: string): { label: string; value: string } | null {
  const m = line.match(/^\*\*(.+?)\*\*:\s*(.+)$/)
  if (!m) return null
  return { label: m[1].trim(), value: m[2].replace(/^`|`$/g, '').trim() }
}

function parseToolLine(line: string): ToolExecRow | null {
  const m = line.match(/^-\s*\[([^\]]+)\]\s*`([^`]+)`\s*[—–-]\s*([^:]+):\s*(.+)$/i)
  if (!m) return null
  return {
    risk: m[1].trim(),
    name: m[2].trim(),
    status: m[3].trim(),
    summary: m[4].trim(),
  }
}

function parseOpsReport(reportText: string): ParsedOpsReport | null {
  const clean = stripTechnicalNoise(reportText)
  if (!clean.includes('运维执行报告') && !clean.includes('###')) return null

  const lines = clean.split('\n')
  const meta: { label: string; value: string }[] = []
  const tools: ToolExecRow[] = []
  const sections: ReportSection[] = []
  let current: ReportSection | null = null

  for (const raw of lines) {
    const line = raw.trim()
    if (!line || line.startsWith('## 运维执行报告')) continue
    const metaItem = parseMetaLine(line)
    if (metaItem) {
      meta.push(metaItem)
      continue
    }
    const tool = parseToolLine(line)
    if (tool) {
      tools.push(tool)
      continue
    }
    if (line.startsWith('### ')) {
      const title = line.slice(4).trim()
      if (TOOL_RECORD_SECTION_TITLES.has(title)) {
        current = null
        continue
      }
      current = { title, items: [] }
      sections.push(current)
      continue
    }
    if (line.startsWith('- ') && current) {
      current.items.push(line.slice(2).trim())
    }
  }

  return {
    title: '运维执行报告',
    meta,
    tools,
    sections: sections.filter(
      s => s.items.length > 0 && !TOOL_RECORD_SECTION_TITLES.has(s.title),
    ),
  }
}

/** 行内 Markdown → HTML（粗体、代码） */
export function inlineMd(text: string): string {
  return (text || '')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code class="md-code">$1</code>')
}

function cleanSectionBody(body: string): string {
  return body
    .replace(/^[（(][^）)]*[）)]\s*/u, '')
    .replace(/^\d+[～~\-]\d+\s*(条|项|句)?\s*/u, '')
    .replace(/^#+\s*执行结论\s*/gm, '')
    .trim()
}

function sanitizeListItems(items: string[]): string[] {
  return items
    .map(it => it.replace(/^#+\s*执行结论\s*/g, '').trim())
    .filter(it => it.length > 0 && it !== '执行结论')
}

/** 从段落中提取列表项（支持多行、编号、行内分隔） */
export function splitListItems(text: string): string[] {
  const t = cleanSectionBody(text)
  if (!t) return []

  const lines = t.split('\n').map(l => l.trim()).filter(Boolean)
  const structured = lines.filter(l => /^[-*•]\s+/.test(l) || /^\d+[.)]\s+/.test(l))
  if (structured.length >= 1) {
    return structured.map(l =>
      l.replace(/^[-*•]\s+/, '').replace(/^\d+[.)]\s+/, '').trim(),
    )
  }

  if (/\d+[.)]\s/.test(t)) {
    const parts = t.split(/(?=\d+[.)]\s+)/).filter(p => p.trim())
    if (parts.length >= 2) {
      return parts.map(p => p.replace(/^\d+[.)]\s+/, '').trim())
    }
  }

  if (/\s+[–—]\s+/.test(t)) {
    const parts = t.split(/\s+[–—]\s+/).filter(p => p.trim().length > 8)
    if (parts.length >= 2) return parts.map(p => p.trim())
  }

  if (/\s+-\s+/.test(t) && t.split(/\s+-\s+/).length >= 3) {
    return t.split(/\s+-\s+/).map(p => p.trim()).filter(Boolean)
  }

  return [t]
}

function resolveSectionId(title: string): typeof SECTION_DEFS[0] | undefined {
  return SECTION_DEFS.find(d => d.pattern.test(title))
}

function dedupeSections(sections: ConclusionSection[]): ConclusionSection[] {
  const order: ConclusionSectionId[] = ['overview', 'findings', 'suggestions', 'stats', 'other']
  const map = new Map<ConclusionSectionId, ConclusionSection>()
  for (const s of sections) map.set(s.id, s)
  const ordered = order.filter(id => map.has(id)).map(id => map.get(id)!)
  const rest = [...map.values()].filter(s => !order.includes(s.id))
  return [...ordered, ...rest]
}

/** 解析执行结论为结构化章节 */
export function parseConclusionSections(summary: string): ConclusionSection[] {
  let text = extractLastConclusionBlock(summary)
    .replace(/^#+\s*执行结论\s*/gm, '')
    .replace(/^##\s*执行结论\s*/gm, '')
    .trim()

  if (!text) return []

  const markerRe = /\*\*(总览|关键发现|结论与建议|统计|方案进度|方案执行摘要|说明|提示)\*\*[：:]?\s*/g
  const markers: { index: number; title: string; len: number }[] = []
  let m: RegExpExecArray | null
  while ((m = markerRe.exec(text)) !== null) {
    markers.push({ index: m.index, title: m[1], len: m[0].length })
  }

  if (markers.length === 0) {
    const items = splitListItems(text)
    if (items.length >= 2) {
      return [{ id: 'other', title: '执行摘要', type: 'list', items }]
    }
    return [{ id: 'overview', title: '总览', type: 'paragraph', items: [text] }]
  }

  const sections: ConclusionSection[] = []
  for (let i = 0; i < markers.length; i++) {
    const start = markers[i].index + markers[i].len
    const end = i + 1 < markers.length ? markers[i + 1].index : text.length
    const body = text.slice(start, end).trim()
    if (!body) continue

    const def = resolveSectionId(markers[i].title) || {
      id: 'other' as ConclusionSectionId,
      title: markers[i].title,
      type: 'list' as const,
    }

    if (def.type === 'paragraph') {
      sections.push({
        id: def.id,
        title: def.title,
        type: 'paragraph',
        items: [cleanSectionBody(body.replace(/\n+/g, ' '))],
      })
    } else if (def.type === 'numbered') {
      sections.push({
        id: def.id,
        title: def.title,
        type: 'numbered',
        items: sanitizeListItems(splitListItems(body)),
      })
    } else {
      sections.push({
        id: def.id,
        title: def.title,
        type: 'list',
        items: sanitizeListItems(splitListItems(body)),
      })
    }
  }

  return dedupeSections(sections)
}

function sectionsToHtml(sections: ConclusionSection[]): string {
  return sections.map(sec => {
    const title = `<h4 class="sum-section-title sum-${sec.id}">${sec.title}</h4>`
    if (sec.type === 'paragraph') {
      return `${title}<p class="sum-p sum-overview">${inlineMd(sec.items[0] || '')}</p>`
    }
    if (sec.type === 'numbered') {
      const items = sec.items.map(it => `<li class="sum-li">${inlineMd(it)}</li>`).join('')
      return `${title}<ol class="sum-ol">${items}</ol>`
    }
    const items = sec.items.map(it => `<li class="sum-li">${inlineMd(it)}</li>`).join('')
    return `${title}<ul class="sum-ul">${items}</ul>`
  }).join('')
}

function summaryToHtml(summary: string, sections?: ConclusionSection[]): string {
  const parsed = sections || parseConclusionSections(summary)
  if (parsed.length) return sectionsToHtml(parsed)

  let html = summary
    .replace(/^#+\s*执行结论\s*/gm, '')
    .replace(/^#+\s+/gm, '')
    .trim()
  if (!html) return ''

  return html
    .split('\n\n')
    .map(block => {
      const t = block.trim()
      if (!t || t === '执行结论') return ''
      if (t.startsWith('- ')) {
        const items = t.split('\n').filter(l => l.startsWith('- ')).map(l => `<li class="sum-li">${inlineMd(l.slice(2))}</li>`)
        return `<ul class="sum-ul">${items.join('')}</ul>`
      }
      if (t.startsWith('### ')) {
        return `<h4 class="sum-section-title">${inlineMd(t.slice(4))}</h4>`
      }
      return `<p class="sum-p">${inlineMd(t)}</p>`
    })
    .filter(Boolean)
    .join('')
}

export function parseConclusionContent(raw: string): ParsedConclusion {
  if (!raw?.trim()) {
    return { summaryHtml: '', summaryPlain: '', sections: [], report: null, error: null }
  }

  const err = extractError(raw)
  let body = raw

  let reportPart = ''
  const ri = body.indexOf(REPORT_MARKER)
  if (ri >= 0) {
    reportPart = body.slice(ri + REPORT_MARKER.length)
    body = body.slice(0, ri)
  }

  const hi = body.indexOf('## 执行结论')
  let summaryPart = hi >= 0 ? body.slice(hi) : body
  if (hi > 0) {
    const intro = body.slice(0, hi).trim()
    if (intro && !summaryPart.includes(intro)) {
      summaryPart = intro + '\n\n' + summaryPart
    }
  }

  summaryPart = stripTechnicalNoise(summaryPart)
  const report = reportPart ? parseOpsReport(reportPart) : null
  const sections = parseConclusionSections(summaryPart)

  if (report && report.tools.some(t => t.status === 'completed')) {
    const cleaned = summaryPart.replace(/⚠\s*Agent 处理异常[^\n]*/g, '').trim()
    const secs = parseConclusionSections(cleaned)
    return {
      summaryHtml: summaryToHtml(cleaned, secs),
      summaryPlain: cleaned,
      sections: secs,
      report,
      error: null,
    }
  }

  return {
    summaryHtml: summaryToHtml(summaryPart, sections),
    summaryPlain: summaryPart,
    sections,
    report,
    error: err,
  }
}
