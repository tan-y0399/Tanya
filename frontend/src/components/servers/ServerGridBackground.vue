<template>
  <div class="server-grid-bg" :class="{ shocking: shockPlaying }" aria-hidden="true">
    <svg class="hex-pattern" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <pattern id="hexGrid" width="56" height="48" patternUnits="userSpaceOnUse">
          <path
            d="M28 0 L56 14 L56 34 L28 48 L0 34 L0 14 Z"
            fill="none"
            stroke="rgba(37,99,235,0.06)"
            stroke-width="1"
          />
        </pattern>
        <pattern id="hexGridBright" width="56" height="48" patternUnits="userSpaceOnUse">
          <path
            d="M28 0 L56 14 L56 34 L28 48 L0 34 L0 14 Z"
            fill="none"
            stroke="rgba(56,189,248,0.55)"
            stroke-width="1.2"
          />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#hexGrid)" />
      <rect class="hex-flash" width="100%" height="100%" fill="url(#hexGridBright)" />
    </svg>

    <!-- 触电波纹：从四边向中心汇聚 -->
    <div class="shock-layer" v-if="shockPlaying">
      <div class="shock-edge shock-edge--top"></div>
      <div class="shock-edge shock-edge--bottom"></div>
      <div class="shock-edge shock-edge--left"></div>
      <div class="shock-edge shock-edge--right"></div>
      <div
        v-for="n in 4"
        :key="n"
        class="shock-ring"
        :style="{ animationDelay: `${(n - 1) * 0.12}s` }"
      ></div>
      <div class="shock-core"></div>
      <div class="shock-spark" v-for="n in 8" :key="`s-${n}`" :style="sparkStyle(n)"></div>
    </div>

    <div class="ambient-orb ambient-orb--1"></div>
    <div class="ambient-orb ambient-orb--2"></div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{ shockTick?: number }>()

const shockPlaying = ref(false)
let shockTimer = 0

function sparkStyle(n: number) {
  const angle = (n / 8) * 360
  return {
    '--spark-angle': `${angle}deg`,
    animationDelay: `${0.55 + n * 0.04}s`,
  }
}

function playShock() {
  shockPlaying.value = true
  window.clearTimeout(shockTimer)
  shockTimer = window.setTimeout(() => {
    shockPlaying.value = false
  }, 1100)
}

watch(
  () => props.shockTick,
  (v) => {
    if (v && v > 0) playShock()
  },
)
</script>

<style lang="scss" scoped>
.server-grid-bg {
  position: absolute;
  inset: 0;
  min-height: 100%;
  pointer-events: none;
  overflow: hidden;
  background: linear-gradient(180deg, #f8fbff 0%, #f5f6f8 45%, #f0f4f8 100%);
}

.hex-pattern {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  opacity: 0.85;
}

.hex-flash {
  opacity: 0;
  transition: opacity 0.15s;
  .shocking & {
    animation: hex-pulse 1s ease-out forwards;
  }
}

.shock-layer {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.shock-edge {
  position: absolute;
  background: linear-gradient(var(--dir), rgba(56, 189, 248, 0.7), transparent);
  animation: edge-in 0.75s ease-in forwards;
  &--top {
    --dir: to bottom;
    top: 0; left: 0; right: 0; height: 40%;
  }
  &--bottom {
    --dir: to top;
    bottom: 0; left: 0; right: 0; height: 40%;
    animation-delay: 0.05s;
  }
  &--left {
    --dir: to right;
    left: 0; top: 0; bottom: 0; width: 40%;
    animation-delay: 0.08s;
  }
  &--right {
    --dir: to left;
    right: 0; top: 0; bottom: 0; width: 40%;
    animation-delay: 0.08s;
  }
}

.shock-ring {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 220vmax;
  height: 220vmax;
  margin-left: -110vmax;
  margin-top: -110vmax;
  border-radius: 50%;
  border: 2px solid rgba(56, 189, 248, 0.45);
  box-shadow:
    0 0 24px rgba(56, 189, 248, 0.35),
    inset 0 0 30px rgba(99, 102, 241, 0.15);
  animation: ring-converge 0.85s ease-in forwards;
  opacity: 0;
}

.shock-core {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 120px;
  height: 120px;
  margin: -60px 0 0 -60px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(56, 189, 248, 0.5) 0%, transparent 70%);
  animation: core-flash 0.35s ease-out 0.72s forwards;
  opacity: 0;
  transform: scale(0.2);
}

.shock-spark {
  position: absolute;
  left: 50%;
  top: 50%;
  width: 3px;
  height: 28px;
  margin-left: -1.5px;
  margin-top: -14px;
  background: linear-gradient(180deg, rgba(125, 211, 252, 0.9), transparent);
  transform-origin: center 14px;
  transform: rotate(var(--spark-angle)) translateY(-80px) scaleY(0);
  animation: spark-burst 0.4s ease-out forwards;
  opacity: 0;
}

@keyframes hex-pulse {
  0% { opacity: 0; }
  25% { opacity: 0.85; }
  50% { opacity: 0.45; }
  75% { opacity: 0.7; }
  100% { opacity: 0; }
}

@keyframes edge-in {
  0% { opacity: 0.85; }
  100% { opacity: 0; }
}

@keyframes ring-converge {
  0% {
    transform: scale(1);
    opacity: 0.75;
  }
  100% {
    transform: scale(0);
    opacity: 0;
  }
}

@keyframes core-flash {
  0% { opacity: 0; transform: scale(0.2); }
  40% { opacity: 1; transform: scale(1.2); }
  100% { opacity: 0; transform: scale(1.6); }
}

@keyframes spark-burst {
  0% { opacity: 0; transform: rotate(var(--spark-angle)) translateY(-40px) scaleY(0); }
  30% { opacity: 1; transform: rotate(var(--spark-angle)) translateY(-90px) scaleY(1); }
  100% { opacity: 0; transform: rotate(var(--spark-angle)) translateY(-20px) scaleY(0.3); }
}
</style>
