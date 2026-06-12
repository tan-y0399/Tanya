/** Inward-notch puzzle silhouettes (center-facing edges) — all coords within 0–100% */
export const PUZZLE_CLIP: Record<PuzzleQuadrant, string> = {
  tl: 'polygon(7% 0%, 93% 0%, 100% 7%, 100% 38%, 91% 50%, 100% 62%, 100% 93%, 93% 100%, 62% 100%, 50% 91%, 38% 100%, 7% 100%, 0% 93%, 0% 7%)',
  tr: 'polygon(7% 0%, 93% 0%, 100% 7%, 100% 93%, 93% 100%, 62% 100%, 50% 91%, 38% 100%, 7% 100%, 0% 93%, 0% 62%, 9% 50%, 0% 38%, 0% 7%)',
  bl: 'polygon(7% 0%, 38% 0%, 50% 9%, 62% 0%, 93% 0%, 100% 7%, 100% 38%, 91% 50%, 100% 62%, 100% 93%, 93% 100%, 7% 100%, 0% 93%, 0% 7%)',
  br: 'polygon(38% 0%, 50% 9%, 62% 0%, 93% 0%, 100% 7%, 100% 93%, 93% 100%, 7% 100%, 0% 93%, 0% 62%, 9% 50%, 0% 38%, 0% 7%, 7% 0%)',
}

export type PuzzleQuadrant = 'tl' | 'tr' | 'bl' | 'br'

export const QUADRANT_CHANNEL = {
  tl: { tag: 'MOD-01', code: 'LLM', color: '#2563eb', label: '模型配置' },
  tr: { tag: 'MOD-02', code: 'TOOL', color: '#06b6d4', label: '工具管理' },
  bl: { tag: 'MOD-03', code: 'SEC', color: '#6366f1', label: '安全配置' },
  br: { tag: 'MOD-04', code: 'SYS', color: '#10b981', label: '系统状态' },
} as const
