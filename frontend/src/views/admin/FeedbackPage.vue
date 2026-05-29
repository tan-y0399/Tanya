<template>
  <div class="feedback-page">
    <div class="page-header">
      <h2 class="page-title">反馈管理</h2>
      <p class="page-desc">查看与回复用户反馈</p>
    </div>

    <el-table :data="feedbacks" stripe size="small" v-loading="loading">
      <el-table-column prop="username" label="用户" width="100" />
      <el-table-column prop="title" label="标题" min-width="200" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status==='pending'?'warning':row.status==='replied'?'success':'info'" size="small">
            {{ statusMap[row.status] }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="createdAt" label="时间" width="170">
        <template #default="{ row }">{{ formatTime(row.createdAt) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="220">
        <template #default="{ row }">
          <el-button size="small" @click="openDetail(row)">查看</el-button>
          <el-button size="small" type="primary" v-if="row.status==='pending'" @click="openReply(row)">回复</el-button>
          <el-button size="small" type="info" v-if="row.status==='replied'" @click="handleClose(row)">关闭</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showDetail" title="反馈详情" width="520px">
      <div style="margin-bottom:12px"><strong>{{ viewing?.title }}</strong></div>
      <div style="color:#64748b;white-space:pre-wrap;margin-bottom:16px">{{ viewing?.content }}</div>
      <div v-if="viewing?.adminReply" style="background:#f0fdf4;padding:12px;border-radius:8px">
        <strong style="color:#16a34a">管理员回复：</strong>
        <div style="color:#64748b;white-space:pre-wrap;margin-top:4px">{{ viewing?.adminReply }}</div>
      </div>
    </el-dialog>

    <el-dialog v-model="showReply" title="回复反馈" width="500px">
      <el-input v-model="replyText" type="textarea" :rows="4" placeholder="输入回复内容..." />
      <template #footer>
        <el-button @click="showReply = false">取消</el-button>
        <el-button type="primary" @click="handleReply">发送回复</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getFeedbackList, replyFeedback, updateFeedbackStatus } from '@/api/feedback'
import type { FeedbackInfo } from '@/api/feedback'

const feedbacks = ref<FeedbackInfo[]>([])
const loading = ref(false)
const showDetail = ref(false)
const showReply = ref(false)
const viewing = ref<FeedbackInfo | null>(null)
const replyText = ref('')
const statusMap: Record<string, string> = { pending: '待回复', replied: '已回复', closed: '已关闭' }

async function loadFeedbacks() {
  loading.value = true
  try { feedbacks.value = (await getFeedbackList()).items } catch {}
  finally { loading.value = false }
}

function openDetail(row: FeedbackInfo) { viewing.value = row; showDetail.value = true }
function openReply(row: FeedbackInfo) { viewing.value = row; replyText.value = ''; showReply.value = true }

async function handleReply() {
  if (!viewing.value || !replyText.value.trim()) { ElMessage.warning('请输入回复内容'); return }
  try { await replyFeedback(viewing.value.id, replyText.value); ElMessage.success('已回复'); showReply.value = false; loadFeedbacks() } catch {}
}

async function handleClose(row: FeedbackInfo) {
  try { await updateFeedbackStatus(row.id, 'closed'); ElMessage.success('已关闭'); loadFeedbacks() } catch {}
}

function formatTime(t: string) { return t ? new Date(t).toLocaleString('zh-CN') : '' }

onMounted(() => { loadFeedbacks() })
</script>

<style lang="scss" scoped>
.feedback-page { max-width: 1100px; margin: 0 auto; }
.page-header {
  margin-bottom: 16px;
  .page-title { font-size: 20px; font-weight: 700; color: #1e293b; }
  .page-desc { font-size: 13px; color: #94a3b8; margin-top: 4px; }
}
</style>
