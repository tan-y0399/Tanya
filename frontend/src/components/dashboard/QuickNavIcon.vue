<template>
  <svg
    class="nav-icon-svg"
    :class="[channel, { hover: hovered, warn: warn }]"
    width="36"
    height="36"
    viewBox="0 0 36 36"
    fill="none"
    aria-hidden="true"
  >
    <!-- CHAT -->
    <g v-if="channel === 'chat'">
      <path
        class="chat-bubble-back"
        d="M8 10a2 2 0 012-2h12a2 2 0 012 2v7a2 2 0 01-2 2H14l-3 3v-3H10a2 2 0 01-2-2V10z"
        stroke="currentColor"
        stroke-width="1.4"
        stroke-linejoin="round"
      />
      <path
        class="chat-bubble-front"
        d="M12 16a2 2 0 012-2h10a2 2 0 012 2v6a2 2 0 01-2 2h-4l-2.5 2.5V24h-1.5a2 2 0 01-2-2v-6z"
        stroke="currentColor"
        stroke-width="1.4"
        stroke-linejoin="round"
        fill="rgba(6,182,212,0.06)"
      />
      <circle class="chat-core" cx="20" cy="19" r="2" fill="currentColor" />
      <circle class="chat-pulse" cx="20" cy="19" r="4" stroke="currentColor" stroke-width="0.8" opacity="0.4" />
      <path class="chat-flow" d="M24 14l4-2" stroke="currentColor" stroke-width="1" stroke-linecap="round" opacity="0.5" />
    </g>

    <!-- SRV -->
    <g v-else-if="channel === 'srv'">
      <rect class="srv-cell c1" x="7" y="8" width="9" height="9" rx="2" stroke="currentColor" stroke-width="1.3" />
      <rect class="srv-cell c2" x="20" y="8" width="9" height="9" rx="2" stroke="currentColor" stroke-width="1.3" />
      <rect class="srv-cell c3" x="7" y="21" width="9" height="9" rx="2" stroke="currentColor" stroke-width="1.3" />
      <rect class="srv-cell c4" x="20" y="21" width="9" height="9" rx="2" stroke="currentColor" stroke-width="1.3" />
      <line class="srv-link l1" x1="16" y1="12.5" x2="20" y2="12.5" stroke="currentColor" stroke-width="1" opacity="0.45" />
      <line class="srv-link l2" x1="11.5" y1="17" x2="11.5" y2="21" stroke="currentColor" stroke-width="1" opacity="0.45" />
      <line class="srv-link l3" x1="24.5" y1="17" x2="24.5" y2="21" stroke="currentColor" stroke-width="1" opacity="0.45" />
      <circle class="srv-dot d1" cx="11.5" cy="26.5" r="1.2" fill="currentColor" />
      <circle class="srv-dot d2" cx="24.5" cy="26.5" r="1.2" fill="currentColor" />
    </g>

    <!-- AUD -->
    <g v-else-if="channel === 'aud'">
      <path
        d="M12 8h10l4 4v14a1.5 1.5 0 01-1.5 1.5H12A1.5 1.5 0 0110.5 26V9.5A1.5 1.5 0 0112 8z"
        stroke="currentColor"
        stroke-width="1.4"
        stroke-linejoin="round"
      />
      <path d="M22 8v4h4" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round" />
      <line x1="13" y1="16" x2="23" y2="16" stroke="currentColor" stroke-width="1" opacity="0.35" />
      <line x1="13" y1="19.5" x2="21" y2="19.5" stroke="currentColor" stroke-width="1" opacity="0.35" />
      <line x1="13" y1="23" x2="19" y2="23" stroke="currentColor" stroke-width="1" opacity="0.35" />
      <line class="aud-scan" x1="11" y1="14" x2="24" y2="14" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" />
    </g>

    <!-- ALT -->
    <g v-else-if="channel === 'alt'">
      <path
        class="alt-bell"
        d="M18 8c-3.5 0-6 2.8-6 6.2c0 3.8-1.8 5.5-1.8 5.5h15.6S24 18 24 14.2C24 10.8 21.5 8 18 8z"
        stroke="currentColor"
        stroke-width="1.4"
        stroke-linejoin="round"
      />
      <path d="M15 24.5a3 3 0 006 0" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" />
      <path
        class="alt-radar"
        d="M10 28 A8 8 0 0 1 26 28"
        stroke="currentColor"
        stroke-width="1.2"
        stroke-linecap="round"
        fill="none"
        opacity="0.5"
      />
      <line class="alt-sweep" x1="18" y1="28" x2="24" y2="22" stroke="currentColor" stroke-width="1" stroke-linecap="round" />
    </g>
  </svg>
</template>

<script setup lang="ts">
defineProps<{
  channel: 'chat' | 'srv' | 'aud' | 'alt'
  hovered?: boolean
  warn?: boolean
}>()
</script>

<style lang="scss" scoped>
.nav-icon-svg {
  display: block;
  color: var(--nav-color, #06b6d4);

  &.chat { --nav-color: #06b6d4; }
  &.srv { --nav-color: #2563eb; }
  &.aud { --nav-color: #6366f1; }
  &.alt { --nav-color: #f59e0b; }

  &.alt.warn { --nav-color: #ef4444; }
}

/* CHAT */
.chat-core { animation: chat-breathe 2.4s ease-in-out infinite; }
.chat-pulse { animation: chat-ring 2.4s ease-out infinite; transform-origin: 20px 19px; }
.chat-flow { animation: chat-flow 3s ease-in-out infinite; }

@keyframes chat-breathe {
  0%, 100% { opacity: 0.85; }
  50% { opacity: 1; }
}
@keyframes chat-ring {
  0% { opacity: 0.45; transform: scale(0.7); }
  70% { opacity: 0; transform: scale(1.4); }
  100% { opacity: 0; transform: scale(1.4); }
}
@keyframes chat-flow {
  0%, 100% { opacity: 0.2; stroke-dashoffset: 6; }
  50% { opacity: 0.7; stroke-dashoffset: 0; }
}
.chat-flow { stroke-dasharray: 6; }

.hover.chat .chat-flow { animation-duration: 1.2s; }

/* SRV */
.srv-cell { fill: rgba(37, 99, 235, 0.04); }
.srv-cell.c1 { animation: srv-light 2.4s ease-in-out infinite; }
.srv-cell.c2 { animation: srv-light 2.4s ease-in-out 0.3s infinite; }
.srv-cell.c3 { animation: srv-light 2.4s ease-in-out 0.6s infinite; }
.srv-cell.c4 { animation: srv-light 2.4s ease-in-out 0.9s infinite; }

@keyframes srv-light {
  0%, 100% { fill: rgba(37, 99, 235, 0.04); }
  50% { fill: rgba(37, 99, 235, 0.14); }
}

.srv-link { stroke-dasharray: 4; animation: srv-dash 2s linear infinite; }
@keyframes srv-dash {
  to { stroke-dashoffset: -8; }
}

.hover.srv .srv-dot { animation: srv-blink 0.6s ease infinite alternate; }
@keyframes srv-blink {
  from { opacity: 0.4; }
  to { opacity: 1; }
}

/* AUD */
.aud-scan {
  animation: aud-scan-y 3s ease-in-out infinite;
}
@keyframes aud-scan-y {
  0%, 100% { transform: translateY(0); opacity: 0.3; }
  50% { transform: translateY(10px); opacity: 0.9; }
}

.hover.aud .aud-scan { animation-duration: 1.5s; }

/* ALT */
.alt-sweep {
  transform-origin: 18px 28px;
  animation: alt-sweep 4s linear infinite;
}
@keyframes alt-sweep {
  from { transform: rotate(-60deg); }
  to { transform: rotate(60deg); }
}

.alt-radar { opacity: 0.45; }

.hover.alt .alt-bell {
  animation: alt-ring 0.5s ease-in-out infinite alternate;
  transform-origin: 18px 10px;
}
@keyframes alt-ring {
  from { transform: rotate(-4deg); }
  to { transform: rotate(4deg); }
}

.warn.alt .alt-sweep { animation-duration: 1.5s; }
.warn.alt .alt-radar { stroke: #ef4444; opacity: 0.75; }
</style>
