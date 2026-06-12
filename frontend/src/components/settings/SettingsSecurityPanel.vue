<template>
  <div class="sec-panel">
    <div class="sec-overview">
      <div class="overview-left">
        <span class="sec-badge">SHIELD ACTIVE</span>
        <span class="sec-sub">{{ activeLayers }}/5 防护层运行中</span>
        <span v-if="readOnly" class="sec-readonly">只读 · 需管理员权限修改</span>
      </div>
      <div class="rules-ring">
        <span class="ring-num">{{ totalRules }}</span>
        <span class="ring-label">RULES</span>
      </div>
    </div>

    <div class="sec-metrics">
      <div class="metric-cell">
        <span class="m-label">TIMEOUT</span>
        <span class="m-val">{{ approvalTimeout }}s</span>
      </div>
      <div class="metric-cell">
        <span class="m-label">ROUNDS</span>
        <span class="m-val">{{ maxRounds }}</span>
      </div>
      <div class="metric-cell">
        <span class="m-label">RISK</span>
        <span class="m-val">L1–L5</span>
      </div>
    </div>

    <div class="policy-row">
      <div class="policy-card">
        <label>审批超时（秒）</label>
        <el-input-number
          :model-value="approvalTimeout"
          :min="10"
          :max="300"
          :step="10"
          size="small"
          :disabled="disabled"
          @update:model-value="emit('update:approvalTimeout', $event)"
        />
        <span class="policy-hint">L4 审批等待上限</span>
      </div>
      <div class="policy-card">
        <label>最大对话轮次</label>
        <el-input-number
          :model-value="maxRounds"
          :min="5"
          :max="100"
          :step="5"
          size="small"
          :disabled="disabled"
          @update:model-value="emit('update:maxRounds', $event)"
        />
        <span class="policy-hint">单会话 Agent 轮次</span>
      </div>
    </div>

    <div class="risk-ladder">
      <div
        v-for="tier in riskTiers"
        :key="tier.level"
        class="risk-seg"
        :class="tier.level.toLowerCase()"
        :title="tier.desc"
      >
        <span class="risk-lv">{{ tier.level }}</span>
        <span class="risk-action">{{ tier.action }}</span>
      </div>
    </div>

    <div class="layer-list">
      <div v-for="layer in securityLayers" :key="layer.code" class="layer-row">
        <span class="layer-code">{{ layer.code }}</span>
        <div class="layer-main">
          <div class="layer-top">
            <span class="layer-name">{{ layer.name }}</span>
            <span class="layer-count">{{ layer.count }}</span>
            <span class="layer-status">ACTIVE</span>
          </div>
          <div class="layer-bar">
            <div class="layer-fill" :style="{ width: layerBarWidth(layer.count) }"></div>
          </div>
          <span class="layer-desc">{{ layer.desc }}</span>
        </div>
      </div>
    </div>

    <div class="sec-footer">
      <div class="footer-tags">
        <span class="ftag">注入防护</span>
        <span class="ftag">路径保护</span>
        <span class="ftag">审批链</span>
      </div>
      <span class="footer-note">高危工具 {{ highRiskTools }} 项受控</span>
    </div>
  </div>
</template>

<script setup lang="ts">
const SECURITY_LAYERS = [
  { code: 'L1', name: '命令分组匹配', count: 12, desc: 'systemctl · journalctl · ps 等分组策略' },
  { code: 'L2', name: '黑名单硬阻断', count: 14, desc: 'rm -rf / · fork 炸弹 · 远程管道执行' },
  { code: 'L3', name: '高危参数检测', count: 14, desc: 'chmod 777 · 命令替换 · 安全文件访问' },
  { code: 'L4', name: 'Shell 注入绕过', count: 13, desc: '编码绕过 · eval · IFS 空格绕过' },
  { code: 'L5', name: '路径保护验证', count: 17, desc: '/etc/shadow · /root/.ssh · /boot' },
] as const

const RISK_TIERS = [
  { level: 'L1', action: '自动', desc: '只读查询，自动放行' },
  { level: 'L2', action: '确认', desc: '低风险写操作，用户确认' },
  { level: 'L3', action: '确认', desc: '中风险操作，二次确认' },
  { level: 'L4', action: '审批', desc: '高危变更，管理员审批' },
  { level: 'L5', action: '阻断', desc: '致命操作，直接拒绝' },
] as const

defineProps<{
  approvalTimeout: number
  maxRounds: number
  disabled?: boolean
  readOnly?: boolean
  highRiskTools?: number
}>()

const emit = defineEmits<{
  'update:approvalTimeout': [v: number]
  'update:maxRounds': [v: number]
}>()

const securityLayers = SECURITY_LAYERS
const riskTiers = RISK_TIERS
const activeLayers = SECURITY_LAYERS.length
const totalRules = SECURITY_LAYERS.reduce((s, l) => s + l.count, 0)

const maxLayerCount = Math.max(...SECURITY_LAYERS.map(l => l.count))

function layerBarWidth(count: number) {
  return `${Math.max(12, (count / maxLayerCount) * 100)}%`
}
</script>

<style lang="scss" scoped>
.sec-panel {
  display: flex;
  flex-direction: column;
  gap: 10px;
  height: 100%;
}

.sec-overview {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(99, 102, 241, 0.06);
  border: 1px solid rgba(99, 102, 241, 0.14);
}

.overview-left {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.sec-badge {
  font-family: 'Inter', 'PingFang SC', sans-serif;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.08em;
  color: #4338ca;
  padding: 2px 7px;
  border-radius: 4px;
  background: rgba(99, 102, 241, 0.15);
  width: fit-content;
}

.sec-sub {
  font-size: 11px;
  font-weight: 600;
  color: #64748b;
}

.sec-readonly {
  font-size: 9px;
  font-weight: 600;
  color: #b45309;
  margin-top: 2px;
}

.rules-ring {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  border: 2px solid rgba(99, 102, 241, 0.25);
  background: rgba(255, 255, 255, 0.8);
  flex-shrink: 0;

  .ring-num {
    font-family: 'Inter', 'PingFang SC', sans-serif;
    font-size: 13px;
    font-weight: 800;
    color: #4338ca;
    line-height: 1;
  }

  .ring-label {
    font-size: 6px;
    font-weight: 700;
    letter-spacing: 0.06em;
    color: #94a3b8;
    margin-top: 1px;
  }
}

.sec-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 6px;
}

.metric-cell {
  padding: 6px 8px;
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.7);
  border: 1px solid rgba(99, 102, 241, 0.1);
  text-align: center;

  .m-label {
    display: block;
    font-family: 'Inter', 'PingFang SC', sans-serif;
    font-size: 7px;
    font-weight: 700;
    letter-spacing: 0.06em;
    color: #94a3b8;
    margin-bottom: 2px;
  }

  .m-val {
    display: block;
    font-size: 10px;
    font-weight: 700;
    color: #1e293b;
  }
}

.policy-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.policy-card {
  padding: 8px 10px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.75);
  border: 1px solid rgba(99, 102, 241, 0.1);

  label {
    display: block;
    font-size: 10px;
    font-weight: 600;
    color: #64748b;
    margin-bottom: 6px;
  }

  :deep(.el-input-number) {
    width: 100%;
  }

  .policy-hint {
    display: block;
    margin-top: 4px;
    font-size: 8px;
    color: #94a3b8;
    letter-spacing: 0.02em;
  }
}

.risk-ladder {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 4px;
}

.risk-seg {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 5px 2px;
  border-radius: 6px;
  border: 1px solid transparent;

  &.l1 { background: rgba(16, 185, 129, 0.1); border-color: rgba(16, 185, 129, 0.2); .risk-lv { color: #047857; } }
  &.l2 { background: rgba(6, 182, 212, 0.1); border-color: rgba(6, 182, 212, 0.2); .risk-lv { color: #0891b2; } }
  &.l3 { background: rgba(245, 158, 11, 0.1); border-color: rgba(245, 158, 11, 0.2); .risk-lv { color: #b45309; } }
  &.l4 { background: rgba(239, 68, 68, 0.08); border-color: rgba(239, 68, 68, 0.18); .risk-lv { color: #dc2626; } }
  &.l5 { background: rgba(127, 29, 29, 0.08); border-color: rgba(127, 29, 29, 0.2); .risk-lv { color: #991b1b; } }
}

.risk-lv {
  font-family: 'Inter', 'PingFang SC', sans-serif;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.04em;
}

.risk-action {
  font-size: 8px;
  font-weight: 600;
  color: #64748b;
}

.layer-list {
  display: flex;
  flex-direction: column;
  gap: 5px;
  flex: 1;
  min-height: 0;
  max-height: 118px;
  overflow-y: auto;
  padding-right: 2px;
}

.layer-row {
  display: flex;
  gap: 8px;
  padding: 6px 8px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.65);
  border: 1px solid rgba(99, 102, 241, 0.08);
}

.layer-code {
  font-family: 'Inter', 'PingFang SC', sans-serif;
  font-size: 8px;
  font-weight: 800;
  color: #6366f1;
  padding: 2px 4px;
  border-radius: 3px;
  background: rgba(99, 102, 241, 0.1);
  height: fit-content;
  flex-shrink: 0;
}

.layer-main {
  flex: 1;
  min-width: 0;
}

.layer-top {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 3px;
}

.layer-name {
  flex: 1;
  font-size: 10px;
  font-weight: 600;
  color: #1e293b;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.layer-count {
  font-family: 'Inter', 'PingFang SC', sans-serif;
  font-size: 9px;
  font-weight: 700;
  color: #6366f1;
}

.layer-status {
  font-size: 7px;
  font-weight: 800;
  letter-spacing: 0.05em;
  color: #047857;
  padding: 1px 4px;
  border-radius: 3px;
  background: rgba(16, 185, 129, 0.1);
  flex-shrink: 0;
}

.layer-bar {
  height: 2px;
  border-radius: 1px;
  background: #f1f5f9;
  overflow: hidden;
  margin-bottom: 2px;
}

.layer-fill {
  height: 100%;
  border-radius: 1px;
  background: linear-gradient(90deg, #818cf8, #6366f1);
  transition: width 0.35s ease;
}

.layer-desc {
  font-size: 8px;
  color: #94a3b8;
  display: block;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sec-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding-top: 8px;
  margin-top: auto;
  border-top: 1px solid rgba(99, 102, 241, 0.12);
  flex-wrap: wrap;
}

.footer-tags {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}

.ftag {
  font-size: 8px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #6366f1;
  padding: 2px 6px;
  border-radius: 999px;
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid rgba(99, 102, 241, 0.15);
}

.footer-note {
  font-size: 9px;
  color: #94a3b8;
  white-space: nowrap;
}
</style>
