<template>
  <div class="admin-bg" aria-hidden="true">
    <svg class="grid-svg" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <pattern id="adminGrid" width="32" height="32" patternUnits="userSpaceOnUse">
          <circle cx="1" cy="1" r="0.8" fill="rgba(37,99,235,0.07)" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#adminGrid)" />
    </svg>
    <div class="scan-line"></div>
    <div class="glow g1"></div>
    <div class="glow g2"></div>
  </div>
</template>

<style lang="scss" scoped>
.admin-bg {
  position: absolute;
  inset: 0;
  min-height: 100%;
  pointer-events: none;
  overflow: hidden;
  background: linear-gradient(165deg, #f5f8ff 0%, #f8fafc 50%, #f1f5f9 100%);
}

.grid-svg { position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0.9; }

.scan-line {
  position: absolute;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(37, 99, 235, 0.28), transparent);
  animation: scan-y 12s linear infinite;
}

.glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(70px);
  opacity: 0.35;
}

.g1 { width: 300px; height: 300px; top: -90px; left: 10%; background: rgba(37, 99, 235, 0.12); }
.g2 { width: 240px; height: 240px; bottom: 5%; right: 8%; background: rgba(124, 58, 237, 0.1); }

@keyframes scan-y {
  0% { top: -1px; opacity: 0; }
  8% { opacity: 0.55; }
  92% { opacity: 0.55; }
  100% { top: 100%; opacity: 0; }
}
</style>
