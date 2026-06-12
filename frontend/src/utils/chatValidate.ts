/** 阶段1：前端本地预校验（与后端 human_supervision.validate_user_input 对齐） */
const MAX_LEN = 8192
const ILLEGAL = /[\x00-\x08\x0b\x0c\x0e-\x1f]/

export function validateChatInput(text: string): { valid: boolean; message?: string; sanitized?: string } {
  const t = (text || '').trim()
  if (!t) return { valid: false, message: '输入不能为空' }
  if (t.length > MAX_LEN) return { valid: false, message: `输入超过 ${MAX_LEN} 字符限制` }
  if (ILLEGAL.test(t)) return { valid: false, message: '包含非法控制字符' }
  return { valid: true, sanitized: t }
}
