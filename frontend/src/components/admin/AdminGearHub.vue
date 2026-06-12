<template>
  <section class="gear-hub" aria-label="齿轮模块导航">
    <div class="hub-label">GEAR · 模块驱动 · 点击小齿轮切换，大齿轮联动旋转后展示内容</div>

    <div class="small-gears-track">
      <button
        v-for="(m, idx) in modules"
        :key="m.key"
        type="button"
        class="small-gear-btn"
        :class="{
          active: activeKey === m.key,
          driving: rotating && targetKey === m.key,
          disabled: rotating,
        }"
        :style="{ '--gear-color': m.color, '--gear-glow': m.glow, zIndex: activeKey === m.key ? 5 : 4 - idx }"
        :disabled="rotating"
        @click="selectModule(m.key)"
      >
        <div class="gear-visual-wrap">
          <div
            class="gear-spin-wrap small"
            :class="{ spin: rotating && targetKey === m.key }"
          >
            <svg viewBox="0 0 100 100" class="gear-svg" aria-hidden="true">
              <polygon :points="smallGearPoints" class="gear-body" />
            </svg>
          </div>
          <div
            class="gear-icon-hub"
            :class="{ active: activeKey === m.key }"
            :style="{ '--gear-color': m.color }"
          >
            <svg class="hub-ring" viewBox="0 0 44 44" aria-hidden="true">
              <circle cx="22" cy="22" r="19" class="hub-ring-bg" />
              <circle cx="22" cy="22" r="19" class="hub-ring-dash" />
            </svg>
            <AdminModuleIcon
              :module-key="m.key"
              :color="m.color"
              :active="activeKey === m.key"
            />
          </div>
        </div>
        <div class="gear-meta">
          <span class="gear-code">{{ m.code }}</span>
          <span class="gear-name">{{ m.label }}</span>
          <span class="gear-stat">{{ m.stat }}</span>
          <span class="gear-desc">{{ m.desc }}</span>
        </div>
      </button>
    </div>

    <div class="mesh-zone" aria-hidden="true">
      <svg class="mesh-svg" viewBox="0 0 800 48" preserveAspectRatio="none">
        <path d="M120 44 Q200 8 400 12 Q600 16 680 44" fill="none" stroke="rgba(37,99,235,0.15)" stroke-width="1.5" stroke-dasharray="4 6" />
      </svg>
    </div>

    <div class="large-gear-stage">
      <div
        class="large-gear-rotate"
        :class="{ spinning: rotating }"
        :style="{ transform: `rotate(${largeRotation}deg)` }"
      >
        <svg viewBox="0 0 200 200" class="large-gear-svg" aria-hidden="true">
          <polygon :points="largeGearPoints" class="large-gear-body" />
          <circle cx="100" cy="100" r="28" class="large-gear-hole" />
        </svg>
      </div>

      <div
        class="large-gear-content glass-panel"
        :class="{ 'content-hidden': rotating, 'content-reveal': justRevealed }"
      >
        <span class="panel-corner panel-corner--tl" aria-hidden="true"></span>
        <span class="panel-corner panel-corner--tr" aria-hidden="true"></span>
        <span class="panel-corner panel-corner--bl" aria-hidden="true"></span>
        <span class="panel-corner panel-corner--br" aria-hidden="true"></span>

        <div class="panel-status">
          <span class="panel-tag">HUB OUTPUT</span>
          <span class="panel-ready" :class="{ syncing: rotating }">
            {{ rotating ? 'SYNC · 传动中' : 'READY · 内容就绪' }}
          </span>
        </div>

        <div class="content-head">
          <div class="content-title-row">
            <span class="content-code">{{ activeModule?.code }}</span>
            <h3 class="content-title">{{ activeModule?.label }}</h3>
          </div>
          <span class="content-stat">{{ activeModule?.stat }}</span>
        </div>

        <div class="content-slot">
          <slot />
        </div>
      </div>
    </div>

    <div v-if="rotating" class="gear-status">大齿轮运转中…</div>
  </section>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { gearPoints, type AdminGearKey, type AdminGearModule } from './gearPaths'
import AdminModuleIcon from './AdminModuleIcon.vue'

const props = defineProps<{
  modules: AdminGearModule[]
  activeKey: AdminGearKey
}>()

const emit = defineEmits<{
  'update:activeKey': [key: AdminGearKey]
}>()

const smallGearPoints = gearPoints(50, 50, 10, 42, 36)
const largeGearPoints = gearPoints(100, 100, 16, 92, 78)

const rotating = ref(false)
const targetKey = ref<AdminGearKey | null>(null)
const largeRotation = ref(0)
const justRevealed = ref(false)
let revealTimer = 0

const activeModule = computed(() =>
  props.modules.find(m => m.key === props.activeKey),
)

function selectModule(key: AdminGearKey) {
  if (key === props.activeKey || rotating.value) return
  targetKey.value = key
  rotating.value = true
  justRevealed.value = false
  largeRotation.value += 360

  window.setTimeout(() => {
    emit('update:activeKey', key)
    rotating.value = false
    targetKey.value = null
    justRevealed.value = true
    window.clearTimeout(revealTimer)
    revealTimer = window.setTimeout(() => {
      justRevealed.value = false
    }, 500)
  }, 920)
}

watch(
  () => props.activeKey,
  () => {
    justRevealed.value = false
  },
)
</script>

<style lang="scss" scoped>
.gear-hub {
  position: relative;
  margin-bottom: 8px;
}

.hub-label {
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.07em;
  color: #94a3b8;
  margin-bottom: 12px;
  text-align: center;
}

.small-gears-track {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  max-width: 920px;
  margin: 0 auto -28px;
  padding: 0 8px;
  position: relative;
  z-index: 3;

  @media (max-width: 900px) {
    grid-template-columns: repeat(2, 1fr);
    margin-bottom: -12px;
  }
}

.small-gear-btn {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 10px 8px 12px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.82);
  cursor: pointer;
  transition: border-color 0.2s, box-shadow 0.2s, transform 0.15s;

  &:hover:not(:disabled) {
    border-color: var(--gear-color);
    box-shadow: 0 0 20px color-mix(in srgb, var(--gear-glow) 35%, transparent);
    transform: translateY(-2px);
  }

  &.active {
    border-color: var(--gear-color);
    background: color-mix(in srgb, var(--gear-glow) 8%, #fff);
    box-shadow: 0 0 0 2px color-mix(in srgb, var(--gear-color) 20%, transparent),
      0 8px 24px color-mix(in srgb, var(--gear-glow) 25%, transparent);
    transform: translateY(6px);

    .gear-body {
      fill: color-mix(in srgb, var(--gear-color) 22%, #dbeafe);
      stroke: var(--gear-color);
      stroke-width: 1.4;
    }
    .hub-ring-bg { fill: color-mix(in srgb, var(--gear-color) 6%, #fff); }
    .hub-ring-dash { stroke: color-mix(in srgb, var(--gear-color) 35%, #94a3b8); }
  }

  &.driving .gear-spin-wrap.spin {
    animation: small-drive 0.92s cubic-bezier(0.45, 0.05, 0.2, 1) forwards;
  }

  &:disabled {
    cursor: wait;
    opacity: 0.85;
  }
}

.gear-visual-wrap {
  position: relative;
  width: 72px;
  height: 72px;
  flex-shrink: 0;
}

.gear-spin-wrap {
  position: absolute;
  inset: 0;
  transition: transform 0.3s;

  &.small .gear-svg {
    width: 100%;
    height: 100%;
    filter: drop-shadow(0 4px 10px rgba(15, 23, 42, 0.12));
  }
}

.gear-icon-hub {
  position: absolute;
  inset: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;

  .hub-ring {
    position: absolute;
    width: 44px;
    height: 44px;
  }

  .hub-ring-bg {
    fill: #fff;
    stroke: none;
  }

  .hub-ring-dash {
    fill: none;
    stroke: color-mix(in srgb, var(--gear-color, #94a3b8) 35%, #94a3b8);
    stroke-width: 1.2;
    stroke-dasharray: 3.5 4.5;
  }

  &.active .hub-ring-bg {
    fill: color-mix(in srgb, var(--gear-color) 6%, #fff);
  }

  &.active .hub-ring-dash {
    stroke: color-mix(in srgb, var(--gear-color) 50%, #94a3b8);
  }

  :deep(.module-icon) {
    --icon-color: var(--gear-color, #64748b);
  }
}

.gear-body {
  fill: #e8eef8;
  stroke: #94a3b8;
  stroke-width: 1.2;
  stroke-linejoin: round;
  transition: fill 0.2s, stroke 0.2s;
}

.gear-meta {
  text-align: center;
  min-width: 0;
}

.gear-code {
  display: block;
  font-size: 8px;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: #94a3b8;
}

.gear-name {
  display: block;
  font-size: 13px;
  font-weight: 700;
  color: #0f172a;
  margin-top: 2px;
}

.gear-stat {
  display: block;
  font-size: 16px;
  font-weight: 800;
  color: var(--gear-color);
  margin-top: 2px;
  font-variant-numeric: tabular-nums;
}

.gear-desc {
  display: block;
  font-size: 10px;
  color: #94a3b8;
  margin-top: 2px;
  line-height: 1.35;
}

.mesh-zone {
  height: 28px;
  margin: -4px 0 -8px;
  position: relative;
  z-index: 2;
}

.mesh-svg {
  width: 100%;
  height: 100%;
}

.large-gear-stage {
  position: relative;
  max-width: 100%;
  margin: 0 auto;
  padding-top: 36px;
}

.large-gear-rotate {
  position: absolute;
  top: 0;
  left: 50%;
  width: min(520px, 92vw);
  height: auto;
  aspect-ratio: 1;
  margin-left: min(-260px, -46vw);
  pointer-events: none;
  z-index: 1;
  transition: transform 0.92s cubic-bezier(0.45, 0.05, 0.2, 1);

  &.spinning {
    transition: transform 0.92s cubic-bezier(0.45, 0.05, 0.2, 1);
  }
}

.large-gear-svg {
  width: 100%;
  height: 100%;
  opacity: 0.55;
}

.large-gear-body {
  fill: rgba(226, 232, 240, 0.35);
  stroke: rgba(37, 99, 235, 0.35);
  stroke-width: 1.5;
  stroke-linejoin: round;
}

.large-gear-hole {
  fill: transparent;
}

.large-gear-content {
  position: relative;
  z-index: 2;
  margin: 48px auto 0;
  max-width: 100%;
  padding: 16px 22px 24px;
  border-color: rgba(37, 99, 235, 0.12) !important;
  border-radius: 16px !important;
  box-shadow:
    0 0 0 1px rgba(255, 255, 255, 0.85) inset,
    0 12px 40px rgba(15, 23, 42, 0.06);
  transition: opacity 0.25s, transform 0.4s;

  &.content-hidden {
    opacity: 0;
    transform: scale(0.98);
    pointer-events: none;
  }

  &.content-reveal {
    animation: content-in 0.45s ease-out;
  }
}

.panel-corner {
  position: absolute;
  width: 14px;
  height: 14px;
  border-color: rgba(37, 99, 235, 0.28);
  border-style: solid;
  pointer-events: none;
}

.panel-corner--tl { top: 10px; left: 10px; border-width: 2px 0 0 2px; }
.panel-corner--tr { top: 10px; right: 10px; border-width: 2px 2px 0 0; }
.panel-corner--bl { bottom: 10px; left: 10px; border-width: 0 0 2px 2px; }
.panel-corner--br { bottom: 10px; right: 10px; border-width: 0 2px 2px 0; }

.panel-status {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  padding-bottom: 10px;
  border-bottom: 1px solid rgba(241, 245, 249, 0.95);
}

.panel-tag {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: #2563eb;
}

.panel-ready {
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: #10b981;

  &.syncing {
    color: #f59e0b;
    animation: pulse-text 0.8s ease-in-out infinite;
  }
}

.content-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.content-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.content-code {
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: #2563eb;
  padding: 3px 9px;
  border-radius: 6px;
  background: rgba(37, 99, 235, 0.08);
  border: 1px solid rgba(37, 99, 235, 0.12);
}

.content-title {
  margin: 0;
  font-size: 18px;
  font-weight: 800;
  color: #0f172a;
  letter-spacing: -0.02em;
}

.content-stat {
  font-size: 13px;
  font-weight: 700;
  color: #64748b;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  padding-top: 2px;
}

.content-slot {
  min-height: 120px;
}

.gear-status {
  text-align: center;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.06em;
  color: #2563eb;
  margin-top: 8px;
  animation: pulse-text 0.8s ease-in-out infinite;
}

@keyframes small-drive {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes content-in {
  from { opacity: 0; transform: translateY(8px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes pulse-text {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>
