<template>
  <div class="shield-ripple-bg" aria-hidden="true">
    <svg ref="stageRef" class="shield-stage" viewBox="-70 -80 140 160" preserveAspectRatio="xMidYMid meet">
      <defs>
        <linearGradient id="shieldCoreGrad" x1="50%" y1="0%" x2="50%" y2="100%">
          <stop offset="0%" stop-color="#e0f2fe" />
          <stop offset="55%" stop-color="#93c5fd" />
          <stop offset="100%" stop-color="#60a5fa" />
        </linearGradient>
        <filter id="coreGlow" x="-80%" y="-80%" width="260%" height="260%">
          <feGaussianBlur stdDeviation="5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>

      <g class="ripple-wrap">
        <path
          v-for="n in 4"
          :key="n"
          class="shield-ripple"
          :class="`ripple-${n}`"
          :d="shieldOutline"
          fill="none"
          stroke="#7dd3fc"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </g>

      <path
        class="shield-border"
        :d="shieldOutline"
        fill="none"
        stroke="#93c5fd"
        stroke-width="2.6"
        stroke-linecap="round"
        stroke-linejoin="round"
      />

      <path
        class="shield-core"
        :d="shieldCore"
        fill="url(#shieldCoreGrad)"
        filter="url(#coreGlow)"
      />
    </svg>

    <div class="ambient-glow"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, nextTick } from 'vue'
import { setShieldRippleCenter } from '@/composables/shieldRippleSync'

/** 盾形路径（中心为原点，便于缩放波纹） */
const shieldOutline =
  'M 0 -62 C -14 -62 -21 -54 -25 -47 L -41 -10 C -45 6 -34 24 0 68 C 34 24 45 6 41 -10 L 25 -47 C 21 -54 14 -62 0 -62 Z'

const shieldCore =
  'M 0 -44 C -9 -44 -14 -39 -17 -33 L -29 -10 C -31 2 -24 16 0 42 C 24 16 31 2 29 -10 L 17 -33 C 14 -39 9 -44 0 -44 Z'

const stageRef = ref<HTMLElement | null>(null)
let resizeObs: ResizeObserver | null = null

function syncRippleCenter() {
  const el = stageRef.value
  if (!el) return
  const r = el.getBoundingClientRect()
  const radius = Math.max(r.width, r.height) * 0.52
  setShieldRippleCenter(r.left + r.width / 2, r.top + r.height / 2, radius)
}

onMounted(() => {
  nextTick(() => {
    syncRippleCenter()
    requestAnimationFrame(syncRippleCenter)
  })
  window.addEventListener('resize', syncRippleCenter)
  if (stageRef.value) {
    resizeObs = new ResizeObserver(syncRippleCenter)
    resizeObs.observe(stageRef.value)
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', syncRippleCenter)
  resizeObs?.disconnect()
})
</script>

<style lang="scss" scoped>
.shield-ripple-bg {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
  z-index: 0;
  background: linear-gradient(180deg, #f8fbff 0%, #ffffff 42%, #f0f9ff 100%);
}

.shield-stage {
  position: absolute;
  left: 50%;
  top: var(--welcome-visual-center, 50%);
  width: min(300px, 40vw);
  height: auto;
  transform: translate(-50%, -50%);
  overflow: visible;
}

.ripple-wrap {
  transform-origin: 0 0;
}

.shield-core {
  animation: core-pulse 5s cubic-bezier(0.4, 0, 0.2, 1) infinite;
}

.shield-border {
  animation: border-breathe 5s cubic-bezier(0.4, 0, 0.2, 1) infinite;
}

.shield-ripple {
  opacity: 0;
  stroke-width: 2.2;
  transform-origin: 0 0;
  animation: ripple-expand 5s cubic-bezier(0.16, 0.84, 0.24, 1) infinite;
}

.ripple-1 { animation-delay: 2.4s; }
.ripple-2 { animation-delay: 2.62s; }
.ripple-3 { animation-delay: 2.74s; }
.ripple-4 { animation-delay: 2.86s; }

.ambient-glow {
  position: absolute;
  left: 50%;
  top: var(--welcome-visual-center, 50%);
  width: min(560px, 75vw);
  height: min(560px, 58vh);
  transform: translate(-50%, -50%);
  border-radius: 50%;
  background: radial-gradient(
    circle,
    rgba(147, 197, 253, 0.24) 0%,
    rgba(191, 219, 254, 0.1) 40%,
    transparent 70%
  );
  animation: ambient-pulse 5s ease-in-out infinite;
}

@keyframes core-pulse {
  0%, 20% {
    opacity: 0.5;
  }
  48%, 52% {
    opacity: 1;
  }
  80%, 100% {
    opacity: 0.52;
  }
}

@keyframes border-breathe {
  0%, 20% { stroke: #bae6fd; opacity: 0.72; }
  48%, 52% { stroke: #38bdf8; opacity: 1; }
  80%, 100% { stroke: #bae6fd; opacity: 0.75; }
}

@keyframes ripple-expand {
  0%, 45% {
    opacity: 0;
    transform: scale(1);
    stroke-width: 2.4;
  }
  46% {
    opacity: 0.58;
    transform: scale(1);
    stroke-width: 2.4;
  }
  100% {
    opacity: 0;
    transform: scale(5.5);
    stroke-width: 0.5;
  }
}

@keyframes ambient-pulse {
  0%, 100% { opacity: 0.4; transform: translate(-50%, -50%) scale(0.9); }
  50% { opacity: 0.92; transform: translate(-50%, -50%) scale(1.1); }
}

@media (prefers-reduced-motion: reduce) {
  .shield-core,
  .shield-border,
  .shield-ripple,
  .ambient-glow {
    animation: none;
  }
  .shield-core { opacity: 0.72; }
}
</style>
