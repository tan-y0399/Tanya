import { reactive, readonly } from 'vue'

/** 与盾牌背景 CSS 动画一致的 5s 周期 */
export const SHIELD_RIPPLE_CYCLE_MS = 5000
export const SHIELD_RIPPLE_START_PHASE = 0.46
export const SHIELD_RIPPLE_MAX_SCALE = 5.5
const RIPPLE_EXPAND_DURATION_PHASE = 1 - SHIELD_RIPPLE_START_PHASE

/** 与 CSS .ripple-1~4 的 animation-delay 一致（ms） */
const RIPPLE_DELAYS_MS = [2400, 2620, 2740, 2860]

/** 波纹可见 opacity 阈值（与 CSS keyframe 46% 处 0.58 对应） */
const RIPPLE_VISIBLE_OPACITY = 0.08

const state = reactive({
  centerX: 0,
  centerY: 0,
  baseRadius: 150,
  ready: false,
})

export interface RippleWave {
  scale: number
  opacity: number
  phase: number
}

export function useShieldRippleState() {
  return readonly(state)
}

export function setShieldRippleCenter(x: number, y: number, radius: number) {
  state.centerX = x
  state.centerY = y
  state.baseRadius = Math.max(radius, 80)
  state.ready = true
}

export function ensureShieldRippleCenter() {
  if (state.ready) return
  const el = document.querySelector('.shield-ripple-bg .shield-stage') as SVGElement | null
  if (!el) return
  const r = el.getBoundingClientRect()
  if (r.width < 1) return
  setShieldRippleCenter(r.left + r.width / 2, r.top + r.height / 2, Math.max(r.width, r.height) * 0.52)
}

function scaleFromPhase(phase: number): number | null {
  const local = phase - SHIELD_RIPPLE_START_PHASE
  if (local < 0 || local > RIPPLE_EXPAND_DURATION_PHASE) return null
  const p = local / RIPPLE_EXPAND_DURATION_PHASE
  return 1 + (SHIELD_RIPPLE_MAX_SCALE - 1) * p
}

/** CSS: 46% opacity 0.58 → 100% opacity 0 */
function opacityFromExpandProgress(p: number): number {
  return Math.max(0, 0.58 * (1 - p))
}

function rippleFromPhase(phase: number): RippleWave | null {
  const local = phase - SHIELD_RIPPLE_START_PHASE
  if (local < 0 || local > RIPPLE_EXPAND_DURATION_PHASE) return null
  const p = local / RIPPLE_EXPAND_DURATION_PHASE
  const opacity = opacityFromExpandProgress(p)
  if (opacity < RIPPLE_VISIBLE_OPACITY) return null
  return {
    scale: 1 + (SHIELD_RIPPLE_MAX_SCALE - 1) * p,
    opacity,
    phase: p,
  }
}

function readRipplesFromDom(): RippleWave[] {
  const ripples = document.querySelectorAll<SVGElement>('.shield-ripple-bg .shield-ripple')
  if (!ripples.length) return []

  const waves: RippleWave[] = []
  ripples.forEach((el) => {
    const anim = el.getAnimations()[0]
    if (!anim?.effect) return
    const timing = anim.effect.getTiming()
    const dur = Number(timing.duration)
    if (!dur || dur <= 0) return
    const ct = Number(anim.currentTime ?? 0)
    if (ct < 0) return
    const phase = (ct % dur) / dur
    const wave = rippleFromPhase(phase)
    if (!wave) return
    const domOpacity = parseFloat(getComputedStyle(el).opacity || '0')
    if (domOpacity < RIPPLE_VISIBLE_OPACITY) return
    waves.push({ ...wave, opacity: domOpacity })
  })
  return waves
}

function readRipplesFromClock(nowMs: number): RippleWave[] {
  const waves: RippleWave[] = []
  for (const delay of RIPPLE_DELAYS_MS) {
    const t = (((nowMs - delay) % SHIELD_RIPPLE_CYCLE_MS) + SHIELD_RIPPLE_CYCLE_MS) % SHIELD_RIPPLE_CYCLE_MS
    const wave = rippleFromPhase(t / SHIELD_RIPPLE_CYCLE_MS)
    if (wave) waves.push(wave)
  }
  return waves
}

/** 当前可见、正在扩散的波纹 */
export function getVisibleRipples(nowMs = performance.now()): RippleWave[] {
  const fromDom = readRipplesFromDom()
  if (fromDom.length) return fromDom
  return readRipplesFromClock(nowMs)
}

/** 背景是否正在泛出波纹 */
export function isRippleBurstActive(nowMs = performance.now()): boolean {
  return getVisibleRipples(nowMs).length > 0
}

export function getActiveRippleScales(nowMs = performance.now()): number[] {
  return getVisibleRipples(nowMs).map(w => w.scale)
}

interface PageRect {
  left: number
  top: number
  right: number
  bottom: number
}

function ellipseNorm(pageX: number, pageY: number, scale: number): number {
  const dx = pageX - state.centerX
  const dy = pageY - state.centerY
  const rx = state.baseRadius * 0.9 * scale
  const ry = state.baseRadius * 1.12 * scale
  if (rx < 1 || ry < 1) return Infinity
  return (dx * dx) / (rx * rx) + (dy * dy) / (ry * ry)
}

function sampleRectEdgePoints(rect: PageRect, step = 8): [number, number][] {
  const pts: [number, number][] = [
    [rect.left, rect.top],
    [rect.right, rect.top],
    [rect.left, rect.bottom],
    [rect.right, rect.bottom],
    [(rect.left + rect.right) / 2, (rect.top + rect.bottom) / 2],
  ]
  const w = rect.right - rect.left
  const h = rect.bottom - rect.top
  for (let x = rect.left; x <= rect.right; x += step) {
    pts.push([x, rect.top], [x, rect.bottom])
  }
  for (let y = rect.top; y <= rect.bottom; y += step) {
    pts.push([rect.left, y], [rect.right, y])
  }
  if (w > 0 && h > 0) {
    pts.push([rect.left + w * 0.25, rect.top + h * 0.5], [rect.left + w * 0.75, rect.top + h * 0.5])
  }
  return pts
}

/** 弹幕与波纹前沿接触强度 0~1（0 表示未接触） */
export function getDanmakuRippleContact(
  rect: PageRect,
  nowMs = performance.now(),
): { hit: boolean; intensity: number; ripplePhase: number } {
  ensureShieldRippleCenter()
  if (!state.ready) return { hit: false, intensity: 0, ripplePhase: 0 }

  const waves = getVisibleRipples(nowMs)
  if (!waves.length) return { hit: false, intensity: 0, ripplePhase: 0 }

  let bestIntensity = 0
  let bestPhase = 0

  for (const wave of waves) {
    const band = 0.16 + Math.min(0.12, (wave.scale - 1) * 0.028)
    let hasInner = false
    let hasOuter = false
    let closestRingDist = Infinity

    for (const [x, y] of sampleRectEdgePoints(rect)) {
      const norm = ellipseNorm(x, y, wave.scale)
      const ringDist = Math.abs(norm - 1)
      closestRingDist = Math.min(closestRingDist, ringDist)
      if (norm < 1 - band) hasInner = true
      else if (norm > 1 + band) hasOuter = true
    }

    const crosses = closestRingDist < band || (hasInner && hasOuter)
    if (!crosses) continue

    const proximity = Math.max(0, 1 - closestRingDist / band)
    const intensity = proximity * wave.opacity * (0.55 + wave.phase * 0.45)
    if (intensity > bestIntensity) {
      bestIntensity = intensity
      bestPhase = wave.phase
    }
  }

  return {
    hit: bestIntensity > 0.04,
    intensity: bestIntensity,
    ripplePhase: bestPhase,
  }
}

export function isDanmakuHitByRipple(rect: PageRect, nowMs = performance.now()): boolean {
  return getDanmakuRippleContact(rect, nowMs).hit
}

export function rippleShakeOffset(seed: number, intensity: number): { x: number; y: number } {
  const t = seed * 0.017
  return {
    x: Math.sin(t * 7.3) * intensity,
    y: Math.cos(t * 5.1) * intensity * 0.75,
  }
}
