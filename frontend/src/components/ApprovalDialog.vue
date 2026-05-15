<template>
  <el-dialog v-model="visible" title="高风险操作审批" width="520px">
    <el-descriptions :column="1" border>
      <el-descriptions-item label="动作">{{ action }}</el-descriptions-item>
      <el-descriptions-item label="原因">{{ reason }}</el-descriptions-item>
      <el-descriptions-item label="风险等级">{{ riskLevel }}</el-descriptions-item>
    </el-descriptions>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="emit('reject')">拒绝</el-button>
        <el-button type="primary" @click="emit('approve')">批准</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  modelValue: boolean
  action: string
  reason: string
  riskLevel: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  approve: []
  reject: []
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value),
})
</script>
