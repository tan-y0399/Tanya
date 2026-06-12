<template>
  <div class="link-hub">
    <div class="hub-head">
      <span class="hub-tag">SEC-FLOW</span>
      <h3>三条安全执行链路</h3>
      <p>根据意图与风险自动路由 · 节点状态来自实时审计</p>
    </div>
    <div class="link-grid">
      <div
        v-for="link in links"
        :key="link.id"
        class="link-card"
        :style="{ '--lc': link.color, '--lg': link.glow }"
      >
        <div class="link-glow" aria-hidden="true"></div>
        <span class="link-code">{{ link.code }}</span>
        <strong class="link-title">{{ link.label }}</strong>
        <span class="link-desc">{{ link.desc }}</span>
        <div class="link-flow-mini" aria-hidden="true">
          <span v-for="(n, i) in miniNodes(link.id)" :key="i" class="mini-node" :class="{ last: i === miniNodes(link.id).length - 1 }">
            {{ n }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { LINK_CATALOG, type WorkflowLinkId } from './workflowLinkMeta'

const links = Object.values(LINK_CATALOG)

function miniNodes(id: WorkflowLinkId): string[] {
  if (id === 'link_a') return ['预检', '意图', '路由', '应答']
  if (id === 'link_b') return ['预检', '路由', '风险', 'ReAct']
  return ['预检', '方案', '预检', '执行']
}
</script>

<style scoped lang="scss">
.link-hub {
  margin-bottom: 20px;
  padding: 18px 20px;
  border-radius: 16px;
  border: 1px solid #e2e8f0;
  background:
    radial-gradient(ellipse at 100% 0%, rgba(59, 130, 246, 0.06), transparent 55%),
    linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
  box-shadow: 0 2px 12px rgba(15, 23, 42, 0.04);
}

.hub-head {
  margin-bottom: 16px;
  h3 {
    margin: 6px 0 4px;
    font-size: 16px;
    font-weight: 700;
    color: #1e293b;
  }
  p {
    margin: 0;
    font-size: 12px;
    color: #64748b;
  }
}

.hub-tag {
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.1em;
  color: #2563eb;
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid rgba(37, 99, 235, 0.22);
  background: rgba(37, 99, 235, 0.08);
}

.link-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}

.link-card {
  position: relative;
  padding: 14px 14px 12px;
  border-radius: 12px;
  border: 1px solid color-mix(in srgb, var(--lc) 22%, #e2e8f0);
  background: #fff;
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.04);
  transition: border-color 0.15s, box-shadow 0.15s;
  &:hover {
    border-color: color-mix(in srgb, var(--lc) 40%, #cbd5e1);
    box-shadow: 0 6px 18px color-mix(in srgb, var(--lc) 12%, transparent);
  }
}

.link-glow {
  position: absolute;
  top: -30px;
  right: -20px;
  width: 80px;
  height: 80px;
  background: radial-gradient(circle, color-mix(in srgb, var(--lc) 15%, transparent), transparent 70%);
  pointer-events: none;
  opacity: 0.8;
}

.link-code {
  display: inline-block;
  font-family: 'JetBrains Mono', Consolas, monospace;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.06em;
  color: var(--lc);
  margin-bottom: 6px;
}

.link-title {
  display: block;
  font-size: 13px;
  font-weight: 700;
  color: #1e293b;
  margin-bottom: 4px;
}

.link-desc {
  display: block;
  font-size: 10px;
  color: #64748b;
  line-height: 1.4;
  margin-bottom: 10px;
}

.link-flow-mini {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.mini-node {
  font-size: 9px;
  font-weight: 600;
  color: #475569;
  padding: 2px 6px;
  border-radius: 4px;
  background: #f1f5f9;
  border: 1px solid #e2e8f0;
  position: relative;
  &:not(.last)::after {
    content: '→';
    position: absolute;
    right: -10px;
    color: var(--lc);
    opacity: 0.75;
    font-size: 8px;
  }
  &:not(.last) { margin-right: 8px; }
}

@media (max-width: 860px) {
  .link-grid { grid-template-columns: 1fr; }
}
</style>
