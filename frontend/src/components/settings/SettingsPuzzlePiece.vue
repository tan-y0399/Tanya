<template>
  <div
    class="puzzle-piece"
    :class="[quadrant, phase, { disabled }]"
    :style="pieceStyle"
  >
    <div class="piece-inner">
      <div class="piece-head">
        <div class="head-left">
          <span class="piece-tag">{{ meta.tag }}</span>
          <h3>{{ meta.label }}</h3>
        </div>
        <span class="piece-code">{{ meta.code }}</span>
      </div>
      <div class="piece-body">
        <slot />
      </div>
      <div class="seam-glow" aria-hidden="true"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { PUZZLE_CLIP, QUADRANT_CHANNEL, type PuzzleQuadrant } from './puzzlePaths'

const props = defineProps<{
  quadrant: PuzzleQuadrant
  phase: 'idle' | 'assembling' | 'locked' | 'success' | 'releasing'
  disabled?: boolean
  /** 覆盖拼图块标题（布局仍由 quadrant 决定） */
  channelTag?: string
  channelCode?: string
  channelLabel?: string
  channelColor?: string
}>()

const meta = computed(() => {
  const base = QUADRANT_CHANNEL[props.quadrant]
  return {
    tag: props.channelTag ?? base.tag,
    code: props.channelCode ?? base.code,
    label: props.channelLabel ?? base.label,
    color: props.channelColor ?? base.color,
  }
})

const OFFSET: Record<PuzzleQuadrant, { x: number; y: number }> = {
  tl: { x: -4, y: -4 },
  tr: { x: 4, y: -4 },
  bl: { x: -4, y: 4 },
  br: { x: 4, y: 4 },
}

const pieceStyle = computed(() => ({
  '--ch': meta.value.color,
  clipPath: PUZZLE_CLIP[props.quadrant],
  transform:
    props.phase === 'idle' || props.phase === 'releasing'
      ? `translate(${OFFSET[props.quadrant].x}px, ${OFFSET[props.quadrant].y}px)`
      : 'translate(0, 0)',
}))
</script>
<style lang="scss" scoped>
.puzzle-piece {
  --ch: #2563eb;
  position: relative;
  min-height: 320px;
  transition:
    transform 0.65s cubic-bezier(0.34, 1.1, 0.48, 1),
    filter 0.4s ease;

  &.assembling,
  &.locked,
  &.success {
    transform: translate(0, 0) !important;
  }

  &.locked .seam-glow,
  &.success .seam-glow {
    opacity: 1;
  }

  &.success .piece-inner {
    box-shadow:
      inset 0 0 0 1px color-mix(in srgb, var(--ch) 25%, #e2e8f0),
      0 0 24px color-mix(in srgb, var(--ch) 12%, transparent);
  }
}

.piece-inner {
  height: 100%;
  padding: 18px 20px 16px;
  background:
    radial-gradient(ellipse at 30% 0%, color-mix(in srgb, var(--ch) 7%, transparent), transparent 65%),
    rgba(255, 255, 255, 0.92);
  border: 1px solid color-mix(in srgb, var(--ch) 18%, #e2e8f0);
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.04);
  display: flex;
  flex-direction: column;
  transition: box-shadow 0.45s ease, border-color 0.45s ease;
}

.piece-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 14px;
  gap: 8px;
}

.head-left {
  display: flex;
  align-items: center;
  gap: 8px;
  h3 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: #1e293b;
  }
}

.piece-tag {
  font-family: 'Inter', 'PingFang SC', sans-serif;
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: var(--ch);
  padding: 2px 5px;
  border-radius: 4px;
  background: color-mix(in srgb, var(--ch) 10%, transparent);
  border: 1px solid color-mix(in srgb, var(--ch) 22%, transparent);
}

.piece-code {
  font-family: 'Inter', 'PingFang SC', sans-serif;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.1em;
  color: var(--ch);
  opacity: 0.75;
}

.piece-body {
  flex: 1;
  min-height: 0;
}

.puzzle-piece.tl .piece-inner { padding-right: 40px; padding-bottom: 36px; }
.puzzle-piece.tr .piece-inner { padding-left: 40px; padding-bottom: 36px; }
.puzzle-piece.bl .piece-inner { padding-right: 40px; padding-top: 36px; }
.puzzle-piece.br .piece-inner { padding-left: 40px; padding-top: 36px; }

.seam-glow {
  position: absolute;
  inset: 0;
  pointer-events: none;
  opacity: 0;
  transition: opacity 0.35s ease 0.45s;
  background:
    linear-gradient(90deg, transparent 49.2%, color-mix(in srgb, var(--ch) 35%, transparent) 50%, transparent 50.8%),
    linear-gradient(0deg, transparent 49.2%, color-mix(in srgb, var(--ch) 35%, transparent) 50%, transparent 50.8%);
  mix-blend-mode: multiply;
}

.puzzle-piece.success .seam-glow {
  animation: seam-pulse 0.8s ease 2;
}

@keyframes seam-pulse {
  0%, 100% { opacity: 0.3; }
  50% { opacity: 0.85; }
}

.puzzle-piece.disabled {
  pointer-events: none;
  opacity: 0.72;
}
</style>
