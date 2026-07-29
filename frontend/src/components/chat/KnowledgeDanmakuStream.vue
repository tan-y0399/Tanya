<template>
  <div ref="containerRef" class="kb-danmaku-stream" aria-label="知识库标题溪流">
    <div class="stream-fade stream-fade--left"></div>
    <div class="stream-fade stream-fade--right"></div>

    <span ref="measureRef" class="danmaku-measure" aria-hidden="true"></span>

    <div
      v-for="item in danmakuItems"
      :key="item.uid"
      class="danmaku-item"
      :class="{ 'is-hovered': hoveredId === item.uid, 'is-shaking': item.shaking }"
      :style="itemStyle(item)"
      @mouseenter="hoveredId = item.uid"
      @mouseleave="hoveredId = null"
      @dblclick="onDoubleClick(item)"
    >
      <span class="danmaku-text">{{ item.text }}</span>
      <span v-if="hoveredId === item.uid" class="danmaku-tip">双击发送</span>
    </div>

    <p v-if="loading" class="stream-loading">正在加载知识库标题…</p>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, shallowRef, triggerRef } from 'vue'
import { fetchArticles } from '@/api/knowledge'
import { getDanmakuRippleContact, isRippleBurstActive, rippleShakeOffset } from '@/composables/shieldRippleSync'

const emit = defineEmits<{ send: [text: string] }>()

interface DanmakuItem {
  uid: string
  text: string
  lane: number
  x: number
  width: number
  shakeX: number
  shakeY: number
  shaking: boolean
}

const LANE_COUNT = 3
const LANE_TOP = [6, 48, 90]
const ITEM_HEIGHT = 32
const MIN_GAP = 36
const SPAWN_OFFSET = 24
const SPEED = 44

const containerRef = ref<HTMLElement | null>(null)
const measureRef = ref<HTMLElement | null>(null)
const danmakuItems = shallowRef<DanmakuItem[]>([])
const hoveredId = ref<string | null>(null)
const loading = ref(true)

let titlePool: string[] = []
let titleCursor = 0
let uidSeq = 0
let rafId = 0
let spawnTimer = 0
let lastTs = 0

function activeTexts(items: DanmakuItem[]): Set<string> {
  return new Set(items.map(i => i.text))
}

function measureWidth(text: string): number {
  const el = measureRef.value
  if (!el) return Math.min(text.length * 13 + 36, 420)
  el.textContent = text
  return Math.min(el.offsetWidth + 36, 420)
}

function laneItems(lane: number, items: DanmakuItem[]) {
  return items.filter(i => i.lane === lane)
}

function overlapsLane(lane: number, x: number, width: number, items: DanmakuItem[]) {
  for (const item of laneItems(lane, items)) {
    if (x < item.x + item.width + MIN_GAP && x + width + MIN_GAP > item.x) return true
  }
  return false
}

function canSpawn(lane: number, width: number, spawnX: number, items: DanmakuItem[]) {
  return !overlapsLane(lane, spawnX, width, items)
}

function pickTitleForGap(
  maxWidth: number,
  onScreen: Set<string>,
): { text: string; width: number } | null {
  if (maxWidth < 56 || !titlePool.length) return null

  const poolLen = titlePool.length
  let best: { text: string; width: number } | null = null
  let bestIdx = -1

  for (let i = 0; i < poolLen; i++) {
    const idx = (titleCursor + i) % poolLen
    const text = titlePool[idx]
    if (onScreen.has(text)) continue
    const width = measureWidth(text)
    if (width <= maxWidth && (!best || width > best.width)) {
      best = { text, width }
      bestIdx = idx
    }
  }

  if (best && bestIdx >= 0) {
    titleCursor = (bestIdx + 1) % poolLen
  }
  return best
}

function trySpawn(items: DanmakuItem[], containerW: number): DanmakuItem | null {
  const spawnX = containerW + SPAWN_OFFSET
  const onScreen = activeTexts(items)
  const lanes = Array.from({ length: LANE_COUNT }, (_, i) => i)
  lanes.sort((a, b) => {
    const rightA = Math.max(0, ...laneItems(a, items).map(i => i.x + i.width))
    const rightB = Math.max(0, ...laneItems(b, items).map(i => i.x + i.width))
    return rightA - rightB
  })

  for (const lane of lanes) {
    const rightmost = Math.max(0, ...laneItems(lane, items).map(i => i.x + i.width))
    const gap = spawnX - rightmost - MIN_GAP
    const picked = pickTitleForGap(gap, onScreen)
    if (!picked) continue
    if (!canSpawn(lane, picked.width, spawnX, items)) continue
    onScreen.add(picked.text)
    return {
      uid: `dm-${++uidSeq}`,
      text: picked.text,
      lane,
      x: spawnX,
      width: picked.width,
      shakeX: 0,
      shakeY: 0,
      shaking: false,
    }
  }
  return null
}

function updateRippleShake(items: DanmakuItem[], containerRect: DOMRect, now: number) {
  const burstActive = isRippleBurstActive(now)
  if (!burstActive) {
    for (const item of items) {
      item.shakeX = 0
      item.shakeY = 0
      item.shaking = false
    }
    return
  }

  for (const item of items) {
    const left = containerRect.left + item.x
    const top = containerRect.top + LANE_TOP[item.lane]
    const contact = getDanmakuRippleContact(
      { left, top, right: left + item.width, bottom: top + ITEM_HEIGHT },
      now,
    )
    if (contact.hit) {
      const amp = 1.4 + contact.intensity * 2.6
      const seed = now * 0.12 + item.x * 0.05 + contact.ripplePhase * 12
      const { x, y } = rippleShakeOffset(seed, amp)
      item.shakeX = x
      item.shakeY = y
      item.shaking = true
    } else {
      item.shakeX = 0
      item.shakeY = 0
      item.shaking = false
    }
  }
}

function tick(now: number) {
  if (!lastTs) lastTs = now
  const dt = Math.min((now - lastTs) / 1000, 0.048)
  lastTs = now

  const container = containerRef.value
  if (!container) {
    rafId = requestAnimationFrame(tick)
    return
  }

  const containerW = container.clientWidth
  const rect = container.getBoundingClientRect()
  const items = [...danmakuItems.value]
  let changed = false

  for (const item of items) {
    if (hoveredId.value !== item.uid) {
      item.x -= SPEED * dt
      changed = true
    }
  }

  const alive = items.filter(i => i.x + i.width > -120)
  if (alive.length !== items.length) changed = true

  spawnTimer += dt
  if (spawnTimer >= 0.28) {
    spawnTimer = 0
    const spawned = trySpawn(alive, containerW)
    if (spawned) {
      alive.push(spawned)
      changed = true
    }
  }

  updateRippleShake(alive, rect, now)
  changed = true

  if (changed) {
    danmakuItems.value = alive
    triggerRef(danmakuItems)
  }

  rafId = requestAnimationFrame(tick)
}

function itemStyle(item: DanmakuItem) {
  return {
    top: `${LANE_TOP[item.lane]}px`,
    width: `${item.width}px`,
    transform: `translate3d(${item.x + item.shakeX}px, ${item.shakeY}px, 0)`,
  }
}

function seedInitial() {
  const containerW = containerRef.value?.clientWidth ?? 900
  const items: DanmakuItem[] = []
  const onScreen = activeTexts(items)

  for (let lane = 0; lane < LANE_COUNT; lane++) {
    let cursor = containerW - 24 - lane * 44
    for (let n = 0; n < 4 && cursor > containerW * 0.06; n++) {
      const maxW = cursor - containerW * 0.04
      const picked = pickTitleForGap(maxW, onScreen)
      if (!picked) {
        cursor -= 44
        continue
      }
      const x = cursor - picked.width
      if (overlapsLane(lane, x, picked.width, items)) {
        cursor = x - MIN_GAP
        continue
      }
      onScreen.add(picked.text)
      items.push({
        uid: `dm-${++uidSeq}`,
        text: picked.text,
        lane,
        x,
        width: picked.width,
        shakeX: 0,
        shakeY: 0,
        shaking: false,
      })
      cursor = x - MIN_GAP - 8
    }
  }

  danmakuItems.value = items
}

async function loadTitles() {
  loading.value = true
  try {
    const data = await fetchArticles({ page: 1, size: 250 })
    const titles = ((data.items || []) as Array<{ title?: string }>)
      .map((a: { title?: string }) => (a.title || '').trim())
      .filter((t: string) => t.length >= 4 && t.length <= 48)
    titlePool = [...new Set(titles)]
    if (!titlePool.length) {
      titlePool = ['如何排查磁盘空间不足', 'SSH 连接失败怎么办', '系统负载过高如何处理']
    }
  } catch {
    titlePool = ['如何排查磁盘空间不足', 'SSH 连接失败怎么办', '系统负载过高如何处理']
  } finally {
    loading.value = false
    seedInitial()
    rafId = requestAnimationFrame(tick)
  }
}

function onDoubleClick(item: DanmakuItem) {
  emit('send', item.text)
}

onMounted(loadTitles)
onUnmounted(() => {
  if (rafId) cancelAnimationFrame(rafId)
})
</script>

<style lang="scss" scoped>
.kb-danmaku-stream {
  position: relative;
  width: 100%;
  max-width: 620px;
  height: 118px;
  margin-top: 0;
  margin-left: auto;
  margin-right: auto;
  overflow: hidden;
  mask-image: linear-gradient(90deg, transparent 0%, #000 12%, #000 88%, transparent 100%);
}

.danmaku-measure {
  position: absolute;
  visibility: hidden;
  white-space: nowrap;
  font-size: 12px;
  padding: 0 14px;
  pointer-events: none;
}

.stream-fade {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 56px;
  z-index: 3;
  pointer-events: none;
  &--left {
    left: 0;
    background: linear-gradient(90deg, rgba(255, 255, 255, 0.96), transparent);
  }
  &--right {
    right: 0;
    background: linear-gradient(270deg, rgba(255, 255, 255, 0.96), transparent);
  }
}

.danmaku-item {
  position: absolute;
  left: 0;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  height: 32px;
  padding: 0 14px;
  border-radius: 999px;
  border: 1px solid rgba(186, 230, 253, 0.9);
  background: rgba(255, 255, 255, 0.86);
  backdrop-filter: blur(4px);
  color: #475569;
  font-size: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  box-sizing: border-box;
  cursor: default;
  user-select: none;
  z-index: 1;
  will-change: transform;
  transition: border-color 0.2s, box-shadow 0.2s, color 0.15s;

  &.is-hovered {
    border-color: #60a5fa;
    color: #1d4ed8;
    box-shadow: 0 4px 16px rgba(59, 130, 246, 0.2);
    z-index: 5;
  }

  &.is-shaking {
    border-color: #38bdf8;
    box-shadow: 0 0 14px rgba(56, 189, 248, 0.35);
    .danmaku-text {
      color: #1e40af;
    }
  }
}

.danmaku-text {
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
  min-width: 0;
}

.danmaku-tip {
  flex-shrink: 0;
  font-size: 10px;
  color: #2563eb;
  font-weight: 600;
  padding-left: 6px;
  border-left: 1px solid #bfdbfe;
}

.stream-loading {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #94a3b8;
  margin: 0;
}

@media (prefers-reduced-motion: reduce) {
  .danmaku-item {
    transform: none !important;
  }
}
</style>
