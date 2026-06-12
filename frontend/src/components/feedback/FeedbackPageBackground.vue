<template>
  <div class="fb-bg" aria-hidden="true">
    <svg class="grid-svg" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <pattern id="fbGrid" width="28" height="28" patternUnits="userSpaceOnUse">
          <circle cx="1" cy="1" r="0.8" fill="rgba(124,58,237,0.07)" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#fbGrid)" />
    </svg>
    <div class="scan-line"></div>
    <div class="glow glow--1"></div>
    <div class="glow glow--2"></div>
  </div>
</template>

<style lang="scss" scoped>
.fb-bg {
  position: absolute;
  inset: 0;
  min-height: 100%;
  pointer-events: none;
  overflow: hidden;
  background: linear-gradient(165deg, #faf5ff 0%, #f8fafc 45%, #f1f5f9 100%);
}

.grid-svg {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
}

.scan-line {
  position: absolute;
  left: 0;
  right: 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(124, 58, 237, 0.28), transparent);
  animation: scan-y 11s linear infinite;
}

.glow {
  position: absolute;
  border-radius: 50%;
  filter: blur(64px);
  opacity: 0.4;
}

.glow--1 {
  width: 260px;
  height: 260px;
  top: -60px;
  right: 8%;
  background: rgba(124, 58, 237, 0.14);
}

.glow--2 {
  width: 200px;
  height: 200px;
  bottom: 8%;
  left: 6%;
  background: rgba(37, 99, 235, 0.1);
}

@keyframes scan-y {
  0% { top: -1px; opacity: 0; }
  8% { opacity: 0.55; }
  92% { opacity: 0.55; }
  100% { top: 100%; opacity: 0; }
}
</style>
