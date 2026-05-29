<template>
  <div class="feedback-page">
    <div class="page-header">
      <h2 class="page-title">反馈</h2>
      <p class="page-desc">提交问题反馈，与管理员沟通</p>
    </div>

    <div class="tab-toolbar">
      <el-button type="primary" size="small" @click="showCreate = true">提交反馈</el-button>
    </div>

    <el-table :data="feedbacks" stripe size="small" v-loading="loading">
      <el-table-column prop="title" label="标题" min-width="200" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status==='pending'?'warning':row.status==='replied'?'success':'info'" size="small">
            {{ statusMap[row.status] }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="adminReply" label="管理员回复" min-width="200" />
      <el-table-column prop="createdAt" label="时间" width="170">
        <template #default="{ row }">{{ formatTime(row.createdAt) }}</template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="showCreate" title="提交反馈" width="500px">
      <el-form label-width="80px">
        <el-form-item label="标题"><el-input v-model="newFb.title" /></el-form-item>
        <el-form-item label="内容"><el-input v-model="newFb.content" type="textarea" :rows="5" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" @click="submitFeedback">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getFeedbackList, createFeedback } from '@/api/feedback'
import type { FeedbackInfo } from '@/api/feedback'

const feedbacks = ref<FeedbackInfo[]>([])
const loading = ref(false)
const showCreate = ref(false)
const newFb = reactive({ title: '', content: '' })
const statusMap: Record<string, string> = { pending: '待回复', replied: '已回复', closed: '已关闭' }

async function load() {
  loading.value = true
  try { feedbacks.value = (await getFeedbackList()).items } catch {}
  finally { loading.value = false }
}

async function submitFeedback() {
  if (!newFb.title.trim()) { ElMessage.warning('请输入标题'); return }
  try { await createFeedback({ ...newFb }); ElMessage.success('反馈已提交'); showCreate.value = false; newFb.title = ''; newFb.content = ''; load() } catch {}
}

function formatTime(t: string) { return t ? new Date(t).toLocaleString('zh-CN') : '' }

onMounted(() => { load() })
</script>

<style lang="scss" scoped>
.feedback-page { max-width: 1000px; margin: 0 auto; }
.page-header {
  margin-bottom: 16px;
  .page-title { font-size: 20px; font-weight: 700; color: #1e293b; }
  .page-desc { font-size: 13px; color: #94a3b8; margin-top: 4px; }
}
.tab-toolbar { margin-bottom: 12px; }
</style>
