<template>
  <div
    class="gauge-card glass-panel"
    :class="[channel, { alert: isAlert, glowing: glowActive }]"
    :style="{ '--channel-color': color, animationDelay: `${glowDelay}ms` }"
  >
    <div class="channel-label">{{ channelLabel }}</div>

    <div v-if="mode === 'cpu-chip'" class="chip-wrap">
      <CpuChipGauge :value="value" />
    </div>

    <div v-else-if="mode === 'mem-sphere'" class="sphere-wrap">
      <MemorySphereGauge :value="value" />
    </div>

    <div v-else-if="mode === 'disk-usb'" class="usb-wrap">
      <DiskUsbGauge :value="value" />
    </div>

    <div v-else-if="mode === 'gauge'" class="gauge-wrap">
      <svg viewBox="0 0 80 80" class="gauge-svg">
        <circle cx="40" cy="40" r="32" fill="none" stroke="#e2e8f0" stroke-width="6" />
        <circle
          cx="40" cy="40" r="32"
          fill="none"
          :stroke="isAlert ? '#ef4444' : color"
          stroke-width="6"
          stroke-linecap="round"
          :stroke-dasharray="circumference"
          :stroke-dashoffset="dashOffset"
          transform="rotate(-90 40 40)"
          class="gauge-arc"
        />
      </svg>
      <div class="gauge-val" :style="{ color: isAlert ? '#ef4444' : color }">
        {{ displayValue }}<span class="unit">%</span>
      </div>
    </div>

    <div v-else-if="mode === 'sys-stopwatch'" class="stopwatch-wrap">
      <SysStopwatchGauge
        :uptime="String(value ?? '')"
        :uptime-seconds="uptimeSeconds"
        @update:label="liveUptime = $event"
      />
    </div>

    <div v-else class="uptime-wrap">
      <svg width="36" height="36" viewBox="0 0 36 36" fill="none" class="clock-icon">
        <circle cx="18" cy="18" r="14" stroke="#6366f1" stroke-width="1.5" stroke-opacity="0.35"/>
        <circle cx="18" cy="18" r="2" fill="#6366f1"/>
        <line x1="18" y1="18" x2="18" y2="10" stroke="#6366f1" stroke-width="1.5" stroke-linecap="round"/>
        <line x1="18" y1="18" x2="24" y2="18" stroke="#6366f1" stroke-width="1.5" stroke-linecap="round"/>
      </svg>
      <div class="uptime-val">{{ displayValue }}</div>
    </div>

    <div class="gauge-sub">
      {{ mode === 'sys-stopwatch' ? liveUptime : subText }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import CpuChipGauge from './CpuChipGauge.vue'
import MemorySphereGauge from './MemorySphereGauge.vue'
import DiskUsbGauge from './DiskUsbGauge.vue'
import SysStopwatchGauge from './SysStopwatchGauge.vue'

const liveUptime = ref('-')

const props = withDefaults(defineProps<{
  channel: 'cpu' | 'memory' | 'disk' | 'system'
  channelLabel: string
  color: string
  value?: number | string | null
  uptimeSeconds?: number | null
  subText: string
  mode?: 'gauge' | 'uptime' | 'cpu-chip' | 'mem-sphere' | 'disk-usb' | 'sys-stopwatch'
  glowActive?: boolean
  glowDelay?: number
}>(), {
  mode: 'gauge',
  glowActive: false,
  glowDelay: 0,
})

const circumference = 2 * Math.PI * 32

const numericValue = computed(() => {
  const v = props.value
  if (v === null || v === undefined || v === '-') return null
  return typeof v === 'number' ? v : parseFloat(String(v))
})

const displayValue = computed(() => {
  if (props.value === null || props.value === undefined || props.value === '') return '-'
  return props.value
})

const isAlert = computed(() =>
  (props.mode === 'gauge' || props.mode === 'cpu-chip' || props.mode === 'mem-sphere' || props.mode === 'disk-usb') &&
  numericValue.value !== null &&
  numericValue.value > 80,
)

const dashOffset = computed(() => {
  if (numericValue.value === null) return circumference
  const pct = Math.min(100, Math.max(0, numericValue.value))
  return circumference * (1 - pct / 100)
})
</script>

<style lang="scss" scoped>
.gauge-card {
  padding: 16px 18px 14px;
  border-color: rgba(186, 230, 253, 0.65) !important;
  text-align: center;
  transition: box-shadow 0.3s, border-color 0.3s;
  display: flex;
  flex-direction: column;

  &.glowing {
    animation: channel-glow 0.5s ease-out;
    animation-delay: var(--animation-delay, 0ms);
    animation-fill-mode: both;
  }

  &.alert { border-color: rgba(239, 68, 68, 0.4) !important; }
}

.channel-label {
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--channel-color);
  margin-bottom: 10px;
  text-align: left;
}

.chip-wrap,
.sphere-wrap,
.usb-wrap,
.stopwatch-wrap {
  display: flex;
  justify-content: center;
  align-items: center;
  flex: 1;
  min-height: 96px;
  margin-bottom: 0;
}

.gauge-wrap {
  position: relative;
  width: 88px;
  height: 88px;
  margin: 0 auto 8px;
}

.gauge-svg {
  width: 100%;
  height: 100%;
}

.gauge-arc {
  transition: stroke-dashoffset 0.45s cubic-bezier(0.4, 0, 0.2, 1);
}

.gauge-val {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 700;
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  .unit { font-size: 12px; margin-left: 1px; opacity: 0.85; }
}

.uptime-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  min-height: 88px;
  justify-content: center;
  margin-bottom: 8px;
}

.uptime-val {
  font-size: 16px;
  font-weight: 700;
  color: #4338ca;
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  line-height: 1.3;
}

.gauge-sub {
  margin-top: auto;
  padding-top: 8px;
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.01em;
  line-height: 1.35;
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  text-align: center;
  white-space: nowrap;
}

.gauge-card.cpu .gauge-sub { color: #2563eb; }
.gauge-card.memory .gauge-sub { color: #059669; }
.gauge-card.disk .gauge-sub { color: #d97706; }
.gauge-card.system .gauge-sub { color: #4338ca; }

.gauge-card.alert .gauge-sub { color: #dc2626; }

@keyframes channel-glow {
  0% { box-shadow: 0 0 0 0 transparent; border-color: rgba(186, 230, 253, 0.65); }
  40% { box-shadow: 0 0 22px color-mix(in srgb, var(--channel-color) 35%, transparent); border-color: var(--channel-color); }
  100% { box-shadow: 0 2px 12px rgba(37, 99, 235, 0.06); }
}
</style>
