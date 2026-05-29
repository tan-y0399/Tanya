<template>
  <div class="reasoning-chain">
    <div class="chain-header" @click="toggleExpand">
      <span class="icon">🧠</span>
      <span class="title">推理过程</span>
      <span class="toggle-icon">{{ expanded ? '▼' : '▶' }}</span>
    </div>

    <transition name="expand">
      <div v-if="expanded" class="chain-content">
        <div v-for="(step, index) in steps" :key="index" class="step-item">
          <div class="step-number">{{ step.step }}</div>
          <div class="step-content">
            <div v-if="step.thought" class="step-thought">
              <span class="label">💭 思考:</span>
              <span class="text">{{ step.thought }}</span>
            </div>
            <div v-if="step.action" class="step-action">
              <span class="label">⚡ 行动:</span>
              <span class="text">{{ step.action }}</span>
            </div>
            <div v-if="step.observation" class="step-observation">
              <span class="label">👁 观察:</span>
              <span class="text">{{ step.observation }}</span>
            </div>
          </div>
        </div>

        <div v-if="steps.length === 0" class="no-steps">
          暂无推理步骤
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

interface ReasoningStep {
  step: number
  thought?: string
  action?: string
  observation?: string
}

interface Props {
  steps: ReasoningStep[]
}

defineProps<Props>()
const expanded = ref(true)

const toggleExpand = () => {
  expanded.value = !expanded.value
}
</script>

<style scoped>
.reasoning-chain {
  margin: 12px 0;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #f9fafb;
  overflow: hidden;
}

.chain-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: #f3f4f6;
  cursor: pointer;
  user-select: none;
}

.chain-header:hover {
  background: #e5e7eb;
}

.chain-header .icon {
  font-size: 16px;
}

.chain-header .title {
  flex: 1;
  font-size: 14px;
  font-weight: 600;
  color: #374151;
}

.chain-header .toggle-icon {
  font-size: 12px;
  color: #6b7280;
  transition: transform 0.2s;
}

.chain-content {
  padding: 16px;
}

.step-item {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.step-item:last-child {
  margin-bottom: 0;
}

.step-number {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #3b82f6;
  color: white;
  border-radius: 50%;
  font-size: 12px;
  font-weight: 600;
}

.step-content {
  flex: 1;
}

.step-thought,
.step-action,
.step-observation {
  margin-bottom: 8px;
  font-size: 13px;
  line-height: 1.6;
}

.step-thought:last-child,
.step-action:last-child,
.step-observation:last-child {
  margin-bottom: 0;
}

.step-content .label {
  font-weight: 600;
  color: #374151;
  margin-right: 8px;
}

.step-content .text {
  color: #4b5563;
}

.no-steps {
  text-align: center;
  color: #9ca3af;
  font-size: 13px;
  padding: 20px;
}

.expand-enter-active,
.expand-leave-active {
  transition: max-height 0.3s ease, opacity 0.3s ease;
  max-height: 500px;
  overflow: hidden;
}

.expand-enter-from,
.expand-leave-to {
  max-height: 0;
  opacity: 0;
}
</style>
