import type { FeedbackInfo } from '@/api/feedback'

export const SOURCE_LABELS: Record<string, string> = {
  manual: '手动反馈',
  session_chat: '会话反馈',
  agent_chat: '会话评价',
}

export const SOURCE_TONE: Record<string, string> = {
  manual: 'tone-manual',
  session_chat: 'tone-session',
  agent_chat: 'tone-eval',
}

export const TYPE_LABELS: Record<string, string> = {
  wrong_answer: '回答不准确',
  not_solved: '未解决问题',
  tool_error: '工具执行异常',
  ui_issue: '界面体验',
  other: '其他',
  general: '一般反馈',
  solved: '已解决',
  partial: '部分解决',
  unsolved: '未解决',
}

export const STATUS_LABELS: Record<string, string> = {
  pending: '待回复',
  replied: '已回复',
  closed: '已关闭',
}

export const MANUAL_CATEGORIES = [
  { value: 'general', label: '一般反馈' },
  { value: 'ui_issue', label: '界面体验' },
  { value: 'other', label: '其他问题' },
]

export function getSourceLabel(row: FeedbackInfo) {
  return row.sourceLabel || SOURCE_LABELS[row.source || 'manual'] || '手动反馈'
}

export function getTypeLabel(row: FeedbackInfo) {
  return row.typeLabel || TYPE_LABELS[row.category || ''] || '—'
}

export function getDisplayTitle(row: FeedbackInfo) {
  return row.sessionTitle || row.title || '—'
}

export interface ParsedFeedbackField {
  label: string
  value: string
  tone?: 'default' | 'highlight' | 'mono'
}

export interface ParsedFeedbackContent {
  fields: ParsedFeedbackField[]
  body: string
  imageUrls: string[]
}

const FIELD_LABELS = [
  '来源', '会话 ID', '最近 Trace', 'Trace ID', '问题类型', '满意度', '评价结果',
]

export function parseFeedbackContent(
  content: string,
  attachments?: { url: string }[],
): ParsedFeedbackContent {
  const lines = (content || '').split('\n')
  const fields: ParsedFeedbackField[] = []
  const imageUrls: string[] = []
  let body = ''
  let inBody = false

  for (const raw of lines) {
    const line = raw.trim()
    if (!line) continue

    if (/^详细说明[：:]?\s*$/.test(line)) {
      inBody = true
      continue
    }
    if (/^附图[：:]?\s*$/.test(line)) {
      inBody = false
      continue
    }

    const imgMatch = line.match(/^[-*]?\s*图\d+[：:]\s*(.+)$/i)
    if (imgMatch) {
      imageUrls.push(imgMatch[1].trim())
      continue
    }

    const kvMatch = line.match(/^([^：:]{2,12})[：:]\s*(.+)$/)
    if (kvMatch && FIELD_LABELS.some(l => kvMatch[1].includes(l) || kvMatch[1] === l)) {
      const label = kvMatch[1].trim()
      const value = kvMatch[2].trim()
      fields.push({
        label,
        value,
        tone: label.includes('Trace') || label.includes('会话') ? 'mono' : 'default',
      })
      if (label.includes('满意度') || label.includes('评价') || label.includes('问题类型')) {
        fields[fields.length - 1].tone = 'highlight'
      }
      continue
    }

    if (inBody) {
      body += (body ? '\n' : '') + line
    } else if (!fields.length && line.length > 4) {
      body += (body ? '\n' : '') + line
    }
  }

  if (attachments?.length) {
    for (const att of attachments) {
      if (att.url && !imageUrls.includes(att.url)) imageUrls.push(att.url)
    }
  }

  return { fields, body: body.trim(), imageUrls }
}

export function getContentExcerpt(row: FeedbackInfo, maxLen = 72): string {
  const parsed = parseFeedbackContent(row.content || '', row.attachments)
  const text = parsed.body || (row.content || '').replace(/\n/g, ' ')
  return text.length > maxLen ? `${text.slice(0, maxLen)}…` : text
}

export function getTypeTone(row: FeedbackInfo): string {
  const t = getTypeLabel(row)
  if (t === '已解决') return 'type-ok'
  if (t === '部分解决') return 'type-partial'
  if (t === '未解决') return 'type-fail'
  return 'type-default'
}
