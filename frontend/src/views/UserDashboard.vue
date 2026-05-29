<template>
  <div class="user-page">
    <div class="page-header">
      <h2 class="page-title">我的工作台</h2>
      <p class="page-desc">系统配置与反馈</p>
    </div>

    <el-tabs v-model="activeTab" type="border-card">
      <!-- ==================== 系统配置（工具管理 + 安全配置） ==================== -->
      <el-tab-pane label="系统配置" name="config">
        <!-- 工具管理 -->
        <div class="section">
          <h3 class="section-title">工具管理</h3>
          <p class="section-desc">查看可用工具并确认是否启用</p>
          <el-table :data="tools" stripe size="small">
            <el-table-column prop="name" label="工具名称" width="200" />
            <el-table-column prop="description" label="描述" />
            <el-table-column prop="category" label="分类" width="120" />
            <el-table-column label="风险等级" width="90">
              <template #default="{ row }">
                <el-tag :type="riskTagType(row.riskLevel)" size="small">L{{ row.riskLevel }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="启用状态" width="100">
              <template #default="{ row }">
                <el-switch :model-value="row.enabled" active-color="#2563eb" @change="onToggle($event, row)" />
              </template>
            </el-table-column>
          </el-table>
        </div>

        <!-- 安全配置 -->
        <div class="section" style="margin-top:28px">
          <h3 class="section-title">安全配置</h3>
          <p class="section-desc">查看当前安全策略配置</p>
          <div class="config-grid">
            <div class="card config-card">
              <h4>LLM 参数</h4>
              <div class="field"><label>API 地址</label><el-input :model-value="config.llm.apiBase" disabled /></div>
              <div class="field"><label>模型</label><el-input :model-value="config.llm.model" disabled /></div>
              <div class="field-row">
                <div class="field"><label>温度</label><el-input-number :model-value="config.llm.temperature" disabled /></div>
                <div class="field"><label>最大Token</label><el-input-number :model-value="config.llm.maxTokens" disabled /></div>
              </div>
            </div>
            <div class="card config-card">
              <h4>安全策略</h4>
              <div class="field"><label>审批超时(秒)</label><el-input-number :model-value="config.security.approvalTimeout" disabled /></div>
              <div class="field"><label>最大对话轮次</label><el-input-number :model-value="config.security.maxRounds" disabled /></div>
            </div>
          </div>
          <div class="reset-row">
            <el-button type="danger" @click="handleDeleteConfig" :loading="deletingConfig">删除安全配置（重置为默认值）</el-button>
          </div>
        </div>
      </el-tab-pane>

      <!-- ==================== 反馈 ==================== -->
      <el-tab-pane label="反馈" name="feedback">
        <div class="tab-toolbar">
          <el-button type="primary" size="small" @click="showCreateFeedback = true">提交反馈</el-button>
        </div>
        <el-table :data="feedbacks" stripe size="small">
          <el-table-column prop="title" label="标题" />
          <el-table-column prop="status" label="状态" width="90">
            <template #default="{ row }">
              <el-tag :type="row.status==='pending'?'warning':row.status==='replied'?'success':'info'" size="small">{{ fbStatusMap[row.status] }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="adminReply" label="管理员回复" />
          <el-table-column prop="createdAt" label="时间" width="170">
            <template #default="{ row }">{{ formatTime(row.createdAt) }}</template>
          </el-table-column>
        </el-table>

        <el-dialog v-model="showCreateFeedback" title="提交反馈" width="500px">
          <el-form label-width="80px">
            <el-form-item label="标题"><el-input v-model="newFeedback.title" /></el-form-item>
            <el-form-item label="内容"><el-input v-model="newFeedback.content" type="textarea" :rows="5" /></el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="showCreateFeedback = false">取消</el-button>
            <el-button type="primary" @click="submitFeedback">提交</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getTools, toggleTool } from '@/api/tools'
import { getConfig } from '@/api/system'
import { getFeedbackList, createFeedback } from '@/api/feedback'
import api from '@/api/index'
import type { ToolInfo } from '@/api/tools'
import type { FeedbackInfo } from '@/api/feedback'

const activeTab = ref('config')
const fbStatusMap: Record<string, string> = { pending: '待回复', replied: '已回复', closed: '已关闭' }

// ========== 工具管理 ==========
const tools = ref<ToolInfo[]>([])

function riskTagType(level: number) { return level <= 1 ? 'info' : level <= 2 ? '' : level <= 3 ? 'warning' : 'danger' }

async function loadTools() {
  try { tools.value = (await getTools()).items } catch {}
}
function onToggle(v: any, row: ToolInfo) {
  handleToggle(row, v as boolean)
}
async function handleToggle(row: ToolInfo, v: boolean) {
  try { await toggleTool(row.id, v); ElMessage.success(v ? '已启用' : '已禁用'); loadTools() } catch {}
}

// ========== 安全配置 ==========
const config = reactive({ llm: { apiBase: '', model: '', apiKey: '', temperature: 0.1, maxTokens: 4096 }, security: { approvalTimeout: 60, maxRounds: 20 } })
const deletingConfig = ref(false)

async function loadConfig() {
  try { const data = await getConfig(); if (data?.llm) Object.assign(config.llm, data.llm); if (data?.security) Object.assign(config.security, data.security) } catch {}
}
async function handleDeleteConfig() {
  try {
    await ElMessageBox.confirm('确定要删除安全配置并重置为默认值吗？', '确认', { type: 'warning', confirmButtonText: '确定删除' })
    deletingConfig.value = true
    await api.delete('/system/config')
    ElMessage.success('安全配置已删除，已恢复默认值')
    loadConfig()
  } catch { } finally { deletingConfig.value = false }
}

// ========== 反馈 ==========
const feedbacks = ref<FeedbackInfo[]>([])
const showCreateFeedback = ref(false)
const newFeedback = reactive({ title: '', content: '' })

async function loadFeedbacks() {
  try { feedbacks.value = (await getFeedbackList()).items } catch {}
}
async function submitFeedback() {
  if (!newFeedback.title.trim()) { ElMessage.warning('请输入标题'); return }
  try { await createFeedback({ ...newFeedback }); ElMessage.success('反馈已提交'); showCreateFeedback.value = false; newFeedback.title = ''; newFeedback.content = ''; loadFeedbacks() } catch {}
}

function formatTime(t: string) { return t ? new Date(t).toLocaleString('zh-CN') : '' }

onMounted(() => { loadTools(); loadConfig(); loadFeedbacks() })
</script>

<style lang="scss" scoped>
.user-page { max-width: 1100px; margin: 0 auto; }

.page-header {
  margin-bottom: 16px;
  .page-title { font-size: 20px; font-weight: 700; color: #1e293b; }
  .page-desc { font-size: 13px; color: #94a3b8; margin-top: 4px; }
}

.section {
  .section-title { font-size: 15px; font-weight: 600; color: #1e293b; margin: 0 0 4px; }
  .section-desc { font-size: 12px; color: #94a3b8; margin: 0 0 12px; }
}

.tab-toolbar { margin-bottom: 12px; }

.config-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }

.config-card {
  padding: 20px;
  h4 { font-size: 14px; font-weight: 600; color: #1e293b; margin: 0 0 14px; }
  .field { margin-bottom: 14px; label { display: block; font-size: 12px; font-weight: 600; color: #94a3b8; margin-bottom: 4px; } }
  .field-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
}

.reset-row { display: flex; justify-content: center; margin-top: 20px; }
</style>
