/** 按会话 + trace 记录反馈是否已提交或已关闭（仅当前浏览器） */

const PREFIX = 'kylinops:trace-feedback:'

function key(sessionId: string, traceId: string) {
  return `${PREFIX}${sessionId}:${traceId}`
}

export type FeedbackCloseReason = 'submitted' | 'dismissed'

export function isTraceFeedbackClosed(sessionId: string, traceId: string): boolean {
  if (!sessionId || !traceId) return true
  return localStorage.getItem(key(sessionId, traceId)) != null
}

export function markTraceFeedbackClosed(
  sessionId: string,
  traceId: string,
  reason: FeedbackCloseReason,
) {
  if (!sessionId || !traceId) return
  localStorage.setItem(key(sessionId, traceId), reason)
}

const PENDING_KEY = `${PREFIX}pending`

/** 每个会话最近一次待反馈的 traceId */
export function getPendingFeedbackTrace(sessionId: string): string | null {
  try {
    const raw = sessionStorage.getItem(PENDING_KEY)
    if (!raw) return null
    const map = JSON.parse(raw) as Record<string, string>
    return map[sessionId] || null
  } catch {
    return null
  }
}

export function setPendingFeedbackTrace(sessionId: string, traceId: string) {
  if (!sessionId || !traceId) return
  try {
    const raw = sessionStorage.getItem(PENDING_KEY)
    const map = raw ? (JSON.parse(raw) as Record<string, string>) : {}
    map[sessionId] = traceId
    sessionStorage.setItem(PENDING_KEY, JSON.stringify(map))
  } catch { /* ignore */ }
}

export function clearPendingFeedbackTrace(sessionId: string) {
  if (!sessionId) return
  try {
    const raw = sessionStorage.getItem(PENDING_KEY)
    if (!raw) return
    const map = JSON.parse(raw) as Record<string, string>
    delete map[sessionId]
    sessionStorage.setItem(PENDING_KEY, JSON.stringify(map))
  } catch { /* ignore */ }
}
