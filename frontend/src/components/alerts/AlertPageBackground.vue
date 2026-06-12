<template>
  <div class="alert-bg" aria-hidden="true">
    <svg class="grid-svg" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <pattern id="alertGrid" width="28" height="28" patternUnits="userSpaceOnUse">
          <circle cx="1" cy="1" r="0.8" fill="rgba(239,68,68,0.06)" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#alertGrid)" />
    </svg>
    <div class="scan-line"></div>
    <div class="glow glow--1"></div>
    <div class="glow glow--2"></div>
  </div>
</template>

<style lang="scss" scoped>
.alert-bg {
  position: absolute;
  inset: 0;
  min-height: 100%;
  pointer-events: none;
  overflow: hidden;
  background: linear-gradient(165deg, #fff7f7 0%, #f8fafc 45%, #f1f5f9 100%);
}

.grid-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  opacity: 0.9;
}

.scan-line {
  position: absolute;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(239, 68, 68, 0.25), transparent);
  animation: scan-y 10s linear infinite;
}

.glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(60px);
  opacity: 0.35;
}

.glow--1 {
  width: 280px;
  height: 280px;
  top: -80px;
  right: 10%;
  background: rgba(239, 68, 68, 0.12);
}

.glow--2 {
  width: 220px;
  height: 220px;
  bottom: 10%;
  left: 5%;
  background: rgba(59, 130, 246, 0.1);
}

@keyframes scan-y {
  0% { top: -1px; opacity: 0; }
  8% { opacity: 0.6; }
  92% { opacity: 0.6; }
  100% { top: 100%; opacity: 0; }
}
</style>
