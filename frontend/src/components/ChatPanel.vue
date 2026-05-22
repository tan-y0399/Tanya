<template>
  <el-card shadow="never" class="chat-panel">
    <template #header>
      <div class="panel-header">
        <span>对话窗口</span>
        <el-tag type="success" effect="dark">{{ connectionState }}</el-tag>
      </div>
    </template>

    <div class="chat-list">
      <div v-for="item in messages" :key="item.id" class="chat-item" :class="item.role">
        <div class="chat-role">{{ item.roleLabel }}</div>
        <div class="chat-bubble">{{ item.content }}</div>
      </div>
    </div>

    <el-divider />

    <el-input
      v-model="draft"
      type="textarea"
      :rows="4"
      placeholder="请输入运维指令，例如：检查 nginx 服务状态、分析最近日志异常"
    />

    <div class="chat-actions">
      <el-button :disabled="loading" @click="clearHistory">清空</el-button>
      <el-button type="primary" :loading="loading" @click="handleSend">发送</el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { sendChatMessage } from '../api/chat'
import { fetchMessages, type MessageItem } from '../api/session'

interface ChatItem {
  id: string
  role: 'user' | 'agent' | 'tool'
  roleLabel: string
  content: string
}

const props = defineProps<{
  sessionId: string
  traceId: string
}>()

const messages = ref<ChatItem[]>([])
const draft = ref('')
const loading = ref(false)
const connectionState = ref('联调中')

const loadHistory = async () => {
  const history = await fetchMessages(props.sessionId)
  messages.value = history.map((item: MessageItem) => ({
    id: item.id,
    role: item.role as 'user' | 'agent' | 'tool',
    roleLabel: item.role === 'user' ? '用户' : item.role === 'agent' ? 'Agent' : '工具',
    content: item.content,
  }))
}

onMounted(loadHistory)
watch(() => props.sessionId, loadHistory)

const clearHistory = () => {
  messages.value = []
}

const handleSend = async () => {
  if (!draft.value.trim()) {
    ElMessage.warning('请输入内容')
    return
  }

  const userMessage = draft.value.trim()
  messages.value.push({
    id: `${Date.now()}-user`,
    role: 'user',
    roleLabel: '用户',
    content: userMessage,
  })

  loading.value = true
  try {
    const response = await sendChatMessage({
      sessionId: props.sessionId,
      message: userMessage,
    })

    messages.value.push({
      id: `${Date.now()}-agent`,
      role: 'agent',
      roleLabel: 'Agent',
      content: `${response.reply}（TraceId: ${response.traceId}）`,
    })

    if (response.toolCalls.length > 0) {
      messages.value.push({
        id: `${Date.now()}-tool`,
        role: 'tool',
        roleLabel: '工具调用',
        content: response.toolCalls.map((item) => `${item.name} / ${item.status}`).join('，'),
      })
    }

    draft.value = ''
    connectionState.value = '正常'
  } catch {
    ElMessage.error('消息发送失败，请检查后端服务是否启动')
    connectionState.value = '异常'
  } finally {
    loading.value = false
  }
}
</script>
