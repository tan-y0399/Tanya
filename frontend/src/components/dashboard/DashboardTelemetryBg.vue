<template>
  <div class="telemetry-bg" :class="{ pulsing: pulseActive }" aria-hidden="true">
    <svg class="dot-grid" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <pattern id="dashDotGrid" width="24" height="24" patternUnits="userSpaceOnUse">
          <circle cx="1" cy="1" r="0.9" fill="rgba(100,116,139,0.14)" class="dot-cell" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#dashDotGrid)" class="grid-rect" />
      <line x1="50%" y1="0" x2="50%" y2="100%" class="guide-v" />
      <line x1="0" y1="50%" x2="100%" y2="50%" class="guide-h" />
    </svg>

    <div class="scan-line"></div>

    <div v-if="pulseActive" class="sync-pulse-layer">
      <div class="sync-wave"></div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{ pulseTick?: number }>()
const pulseActive = ref(false)
let pulseTimer = 0

watch(
  () => props.pulseTick,
  (v) => {
    if (v && v > 0) triggerPulse()
  },
)

function triggerPulse() {
  pulseActive.value = true
  window.clearTimeout(pulseTimer)
  pulseTimer = window.setTimeout(() => {
    pulseActive.value = false
  }, 1200)
}
</script>

<style lang="scss" scoped>
.telemetry-bg {
  position: absolute;
  inset: 0;
  min-height: 100%;
  pointer-events: none;
  overflow: hidden;
  background: linear-gradient(165deg, #f7faff 0%, #f3f6fa 42%, #eef2f7 100%);
}

.dot-grid {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.grid-rect {
  opacity: 0.85;
  transition: opacity 0.3s;
  .pulsing & {
    animation: grid-flash 0.5s ease-out;
  }
}

.guide-v, .guide-h {
  stroke: rgba(148, 163, 184, 0.08);
  stroke-width: 1;
  stroke-dasharray: 6 8;
}

.scan-line {
  position: absolute;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, rgba(6, 182, 212, 0.35), transparent);
  opacity: 0.5;
  animation: scan-y 8s linear infinite;
}

.sync-pulse-layer {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.sync-wave {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 28%;
  background: linear-gradient(
    90deg,
    transparent,
    rgba(6, 182, 212, 0.08),
    rgba(6, 182, 212, 0.22),
    rgba(6, 182, 212, 0.08),
    transparent
  );
  animation: sync-pulse-x 0.75s ease-out forwards;
}

@keyframes scan-y {
  0% { top: -2px; opacity: 0; }
  8% { opacity: 0.5; }
  92% { opacity: 0.5; }
  100% { top: 100%; opacity: 0; }
}

@keyframes sync-pulse-x {
  from { left: -30%; }
  to { left: 110%; }
}

@keyframes grid-flash {
  0% { opacity: 0.85; }
  35% { opacity: 1; }
  100% { opacity: 0.85; }
}
</style>
