const URL_PATTERN = /(?:https?:\/\/|www\.)\S+/gi

function markdownToReadableText(markdown: string): string {
  return (markdown || '')
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, ' $1 ')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, ' $1 ')
    .replace(/<[^>]+>/g, ' ')
    .replace(URL_PATTERN, ' ')
    .replace(/`([^`]*)`/g, ' $1 ')
    .replace(/^\s*[-+*]\s+/gm, ' ')
    .replace(/^\s*\d+[.)]\s+/gm, ' ')
    .replace(/^\s*#{1,6}\s*/gm, '')
    .replace(/^\s*>\s?/gm, '')
    .replace(/^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$/gm, ' ')
}

export function sanitizeSpeechText(markdown: string): string {
  return markdownToReadableText(markdown)
    .replace(/[^\p{Script=Han}\p{Script=Latin}\p{Number}\s]/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

export function createSpeechChunks(markdown: string, maxLength = 520): string[] {
  const readable = markdownToReadableText(markdown)
  const sentences = readable.split(/(?<=[。！？!?；;：:\n])/u)
  const chunks: string[] = []
  let current = ''

  const pushCurrent = () => {
    const clean = sanitizeSpeechText(current)
    if (clean) chunks.push(clean)
    current = ''
  }

  for (const sentence of sentences) {
    const clean = sanitizeSpeechText(sentence)
    if (!clean) continue
    if (clean.length > maxLength) {
      pushCurrent()
      for (let offset = 0; offset < clean.length; offset += maxLength) {
        chunks.push(clean.slice(offset, offset + maxLength))
      }
      continue
    }
    if (current && sanitizeSpeechText(`${current} ${clean}`).length > maxLength) pushCurrent()
    current += ` ${clean}`
  }
  pushCurrent()
  return chunks
}
