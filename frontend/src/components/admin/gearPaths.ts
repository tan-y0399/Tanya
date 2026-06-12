/** 生成 SVG 齿轮多边形点集 */
export function gearPoints(
  cx: number,
  cy: number,
  teeth: number,
  outerR: number,
  innerR: number,
): string {
  const pts: string[] = []
  const steps = teeth * 2
  for (let i = 0; i < steps; i++) {
    const angle = (Math.PI * 2 * i) / steps - Math.PI / 2
    const r = i % 2 === 0 ? outerR : innerR
    pts.push(`${cx + r * Math.cos(angle)},${cy + r * Math.sin(angle)}`)
  }
  return pts.join(' ')
}

export type AdminGearKey = 'users' | 'tools' | 'security' | 'knowledge'

export interface AdminGearModule {
  key: AdminGearKey
  code: string
  label: string
  desc: string
  stat: string
  color: string
  glow: string
}
