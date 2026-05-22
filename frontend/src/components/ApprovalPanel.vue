<template>
  <el-card shadow="never">
    <template #header>
      <div class="panel-header">
        <span>审批中心</span>
        <el-tag type="warning">高风险操作</el-tag>
      </div>
    </template>

    <div class="approval-content">
      <div class="approval-item">
        <strong>动作</strong>
        <div>{{ action }}</div>
      </div>
      <div class="approval-item">
        <strong>原因</strong>
        <div>{{ reason }}</div>
      </div>
    </div>

    <div class="chat-actions">
      <el-button @click="emit('reject')">拒绝</el-button>
      <el-button type="primary" @click="emit('approve')">批准</el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
defineProps<{
  action: string
  reason: string
}>()

const emit = defineEmits<{ approve: []; reject: [] }>()
</script>
