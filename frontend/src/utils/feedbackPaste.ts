import { uploadFeedbackImage } from '@/api/feedback'

export function collectClipboardImages(data: DataTransfer): File[] {
  const files: File[] = []
  const seen = new Set<string>()
  const add = (file: File | null) => {
    if (!file || !file.type.startsWith('image/')) return
    const key = `${file.type}:${file.size}:${file.lastModified || 0}`
    if (seen.has(key)) return
    seen.add(key)
    files.push(file)
  }

  if (data.items?.length) {
    for (const item of Array.from(data.items)) {
      if (item.kind === 'file' && item.type.startsWith('image/')) {
        add(item.getAsFile())
      }
    }
  }
  if (!files.length && data.files?.length) {
    for (const f of Array.from(data.files)) {
      if (f.type.startsWith('image/')) add(f)
    }
  }
  return files
}

export function validateImageFile(file: File, maxMb = 2): string | null {
  if (!file.type.startsWith('image/')) return '仅支持图片文件'
  if (file.size > maxMb * 1024 * 1024) return `图片不能超过 ${maxMb}MB`
  return null
}

const pasteGuard = { sig: '', at: 0 }

export function shouldSkipDuplicatePaste(sig: string, windowMs = 400): boolean {
  const now = Date.now()
  if (sig === pasteGuard.sig && now - pasteGuard.at < windowMs) return true
  pasteGuard.sig = sig
  pasteGuard.at = now
  return false
}

export async function uploadFeedbackImages(
  files: File[],
  currentCount: number,
  maxCount = 4,
): Promise<{ url: string; name: string }[]> {
  const remain = maxCount - currentCount
  if (remain <= 0) return []
  const uploaded: { url: string; name: string }[] = []
  for (const file of files.slice(0, remain)) {
    const err = validateImageFile(file)
    if (err) throw new Error(err)
    const uploadFile = file.name
      ? file
      : new File([file], `paste-${Date.now()}.png`, { type: file.type || 'image/png' })
    const item = await uploadFeedbackImage(uploadFile)
    uploaded.push({ url: item.url, name: item.name || uploadFile.name })
  }
  return uploaded
}
