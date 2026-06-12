/** 知识问答：将 Agent 开场白与正文拆开，便于在中间插入思考过程 */

const INTRO_OPENER = /^(好的|收到|根据|这是为您|以下为|以下为您)/

/** 是否为简短开场白（有则显示在思考过程上方，否则全文在思考过程下方） */
export function hasKnowledgeOpener(text: string): boolean {
  const trimmed = (text || '').trim()
  if (!trimmed) return false
  const firstPara = trimmed.split(/\n\n+/)[0]?.trim() || trimmed
  if (firstPara.length > 280) return false
  return INTRO_OPENER.test(firstPara)
    || /^(以下为您|这是为您)/.test(firstPara)
    || /^根据知识库/.test(firstPara)
}

function trySplit(intro: string, body: string, totalLen: number): { intro: string; body: string } | null {
  const i = intro.trim()
  const b = body.trim()
  if (b.length < 40 || i.length < 8) return null
  if (i.length >= totalLen * 0.85) return null
  return { intro: i, body: b }
}

export function splitKnowledgeIntroBody(text: string): { intro: string; body: string } {
  const trimmed = (text || '').trim()
  if (!trimmed) return { intro: '', body: '' }

  // 首段为简短开场白（如「好的，这是为您整理的…指南。」）
  const blank = trimmed.indexOf('\n\n')
  if (blank > 0) {
    const first = trimmed.slice(0, blank).trim()
    const rest = trimmed.slice(blank + 2).trim()
    if (INTRO_OPENER.test(first) && first.length <= 240 && !first.includes('\n')) {
      const hit = trySplit(first, rest, trimmed.length)
      if (hit) return hit
    }
  }

  // 首行开场白 + 空行（单行 intro）
  const firstLine = trimmed.match(/^((?:好的|收到|根据知识库)[^\n]{8,280}[。．])\s*\n\n/)
  if (firstLine) {
    const splitAt = firstLine[0].length
    const hit = trySplit(trimmed.slice(0, splitAt).trim(), trimmed.slice(splitAt), trimmed.length)
    if (hit) return hit
  }

  // 「以下为您梳理…」「这是为您整理…」
  const guideIntroRe =
    /((?:以下为您梳理|这是为您整理|以下为您介绍)[^。\n]*[。．])\s*\n+/
  const gm = trimmed.match(guideIntroRe)
  if (gm && gm.index !== undefined) {
    const splitAt = gm.index + gm[0].length
    const hit = trySplit(trimmed.slice(0, splitAt), trimmed.slice(splitAt), trimmed.length)
    if (hit) return hit
  }

  // 无开场白时不再按标题/编号拆分，保证知识正文整体位于思考过程下方
  return { intro: trimmed, body: '' }
}

export const TOOLS_CONTENT_MARKER = '\n\n<!--KYLIN_TOOLS-->\n\n'

export function splitAgentContent(content: string): {
  intro: string
  body: string
  conclusion: string
} {
  let raw = content || ''
  const i = raw.indexOf(TOOLS_CONTENT_MARKER)
  if (i >= 0) {
    return {
      intro: raw.slice(0, i).trim(),
      body: '',
      conclusion: raw.slice(i + TOOLS_CONTENT_MARKER.length).trim(),
    }
  }
  const h = '## 执行结论'
  const hi = raw.indexOf(h)
  if (hi >= 0) {
    return { intro: raw.slice(0, hi).trim(), body: '', conclusion: raw.slice(hi).trim() }
  }
  const ri = raw.indexOf('<!--KYLIN_REPORT-->')
  if (ri >= 0) {
    return {
      intro: raw.slice(0, ri).trim(),
      body: '',
      conclusion: raw.slice(ri).trim(),
    }
  }
  const { intro, body } = splitKnowledgeIntroBody(raw)
  return { intro, body, conclusion: '' }
}
