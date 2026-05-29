<template>
  <div class="admin-page">
    <div class="page-header">
      <h2 class="page-title">管理员工作台</h2>
      <p class="page-desc">用户管理、工具管理、安全配置、知识库与反馈管理</p>
    </div>

    <el-tabs v-model="activeTab" type="border-card">
      <!-- ==================== 用户管理 ==================== -->
      <el-tab-pane label="用户管理" name="users">
        <div class="tab-toolbar">
          <el-button type="primary" size="small" @click="showUserDialog = true">添加用户</el-button>
        </div>
        <el-table :data="users" stripe size="small" style="width:100%">
          <el-table-column prop="username" label="用户名" />
          <el-table-column prop="role" label="角色">
            <template #default="{ row }">
              <el-tag :type="row.role === 'admin' ? 'danger' : 'info'" size="small">{{ roleMap[row.role] || row.role }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="id" label="用户ID" width="140" />
          <el-table-column label="操作" width="240">
            <template #default="{ row }">
              <el-button size="small" @click="openEditUser(row)">编辑</el-button>
              <el-button size="small" @click="handleResetPwd(row)">重置密码</el-button>
              <el-button size="small" type="danger" :disabled="row.username==='admin'" @click="handleDeleteUser(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-dialog v-model="showUserDialog" title="添加用户" width="420px">
          <el-form label-width="80px">
            <el-form-item label="用户名"><el-input v-model="newUser.username" /></el-form-item>
            <el-form-item label="密码"><el-input v-model="newUser.password" type="password" show-password /></el-form-item>
            <el-form-item label="角色">
              <el-select v-model="newUser.role">
                <el-option label="管理员" value="admin" />
                <el-option label="普通用户" value="user" />
              </el-select>
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="showUserDialog = false">取消</el-button>
            <el-button type="primary" @click="handleCreateUser" :loading="userCreating">创建</el-button>
          </template>
        </el-dialog>

        <el-dialog v-model="showEditUserDialog" title="编辑用户" width="420px">
          <el-form label-width="80px">
            <el-form-item label="用户名"><el-input :model-value="editUser.username" disabled /></el-form-item>
            <el-form-item label="角色">
              <el-select v-model="editUser.role">
                <el-option label="管理员" value="admin" />
                <el-option label="普通用户" value="user" />
              </el-select>
            </el-form-item>
            <el-form-item label="新密码"><el-input v-model="editUser.password" type="password" show-password placeholder="留空则不修改" /></el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="showEditUserDialog = false">取消</el-button>
            <el-button type="primary" @click="handleUpdateUser">保存</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>

      <!-- ==================== 工具管理 ==================== -->
      <el-tab-pane label="工具管理" name="tools">
        <div class="tab-toolbar">
          <el-button type="primary" size="small" @click="openAddToolDialog">添加工具</el-button>
          <el-button size="small" @click="loadPresetTools">从预设导入</el-button>
        </div>
        <el-table :data="tools" stripe size="small">
          <el-table-column prop="name" label="工具名称" width="200" />
          <el-table-column prop="description" label="描述" />
          <el-table-column prop="category" label="分类" width="120" />
          <el-table-column label="风险级别" width="90">
            <template #default="{ row }">
              <el-tag :type="riskTagType(row.riskLevel)" size="small">L{{ row.riskLevel }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="80">
            <template #default="{ row }">
              <el-switch :model-value="row.enabled" active-color="#2563eb" @change="onToggleTool($event, row)" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="160">
            <template #default="{ row }">
              <el-button size="small" @click="openEditTool(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="handleDeleteTool(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-dialog v-model="showToolDialog" :title="isEditTool ? '编辑工具' : '添加工具'" width="600px">
          <el-form label-width="100px">
            <el-form-item label="工具名称">
              <el-input v-model="currentTool.name" :disabled="isEditTool" placeholder="如: get_disk_usage" />
            </el-form-item>
            <el-form-item label="描述">
              <el-input v-model="currentTool.description" type="textarea" :rows="2" placeholder="工具的功能描述" />
            </el-form-item>
            <el-form-item label="分类">
              <el-select v-model="currentTool.category" placeholder="选择或输入分类" allow-create>
                <el-option label="系统监控" value="system_monitor" />
                <el-option label="进程管理" value="process_management" />
                <el-option label="服务管理" value="service_management" />
                <el-option label="文件管理" value="file_management" />
                <el-option label="网络管理" value="network_management" />
                <el-option label="日志查询" value="log_management" />
                <el-option label="系统操作" value="system_operation" />
              </el-select>
            </el-form-item>
            <el-form-item label="风险级别">
              <el-select v-model="currentTool.riskLevel">
                <el-option v-for="i in 5" :key="i" :label="'L'+i" :value="i" />
              </el-select>
            </el-form-item>
            <el-form-item label="参数配置">
              <el-input v-model="currentTool.configStr" type="textarea" :rows="4" placeholder='JSON格式的参数配置，如 {"timeout": 30}' />
            </el-form-item>
            <el-form-item label="启用状态">
              <el-switch v-model="currentTool.enabled" active-color="#2563eb" />
            </el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="showToolDialog = false">取消</el-button>
            <el-button type="primary" @click="handleSaveTool" :loading="toolSaving">保存</el-button>
          </template>
        </el-dialog>

        <el-dialog v-model="showPresetDialog" title="从预设导入工具" width="700px">
          <div class="preset-tool-list">
            <div class="preset-tool-item" v-for="tool in presetTools" :key="tool.name">
              <el-checkbox v-model="tool.selected">
                <span class="preset-tool-name">{{ tool.name }}</span>
                <span class="preset-tool-desc">{{ tool.description }}</span>
                <el-tag :type="riskTagType(tool.riskLevel)" size="small" class="preset-tool-risk">L{{ tool.riskLevel }}</el-tag>
              </el-checkbox>
            </div>
          </div>
          <template #footer>
            <el-button @click="showPresetDialog = false">取消</el-button>
            <el-button type="primary" @click="importPresetTools" :loading="importing">导入选中</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>

      <!-- ==================== 安全配置 ==================== -->
      <el-tab-pane label="安全配置" name="security">
        <div class="config-grid">
          <div class="card config-card">
            <h3>LLM 参数</h3>
            <div class="field"><label>API 地址</label><el-input v-model="config.llm.apiBase" /></div>
            <div class="field"><label>模型</label><el-input v-model="config.llm.model" /></div>
            <div class="field"><label>API Key</label><el-input v-model="config.llm.apiKey" type="password" show-password /></div>
            <div class="field-row">
              <div class="field"><label>温度</label><el-input-number v-model="config.llm.temperature" :min="0" :max="2" :step="0.1" /></div>
              <div class="field"><label>最大Token</label><el-input-number v-model="config.llm.maxTokens" :min="512" :max="32768" :step="512" /></div>
            </div>
          </div>
          <div class="card config-card">
            <h3>安全策略</h3>
            <div class="field"><label>审批超时(秒)</label><el-input-number v-model="config.security.approvalTimeout" :min="10" :max="300" /></div>
            <div class="field"><label>最大对话轮次</label><el-input-number v-model="config.security.maxRounds" :min="5" :max="100" /></div>
          </div>
        </div>
        <div class="save-row">
          <el-button type="primary" @click="saveConfig" :loading="savingConfig">保存配置</el-button>
        </div>
      </el-tab-pane>

      <!-- ==================== 知识库 ==================== -->
      <el-tab-pane label="知识库" name="knowledge">
        <div class="tab-toolbar">
          <el-button type="primary" size="small" @click="showArticleDialog = true">添加文章</el-button>
        </div>
        <el-table :data="articles" stripe size="small">
          <el-table-column prop="title" label="标题" />
          <el-table-column prop="category" label="分类" width="100" />
          <el-table-column prop="severity" label="级别" width="80">
            <template #default="{ row }">
              <el-tag :type="row.severity==='critical'?'danger':row.severity==='warning'?'warning':'info'" size="small">{{ row.severity }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="160">
            <template #default="{ row }">
              <el-button size="small" @click="openEditArticle(row)">编辑</el-button>
              <el-button size="small" type="danger" @click="handleDeleteArticle(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-dialog v-model="showArticleDialog" title="添加文章" width="600px">
          <el-form label-width="80px">
            <el-form-item label="标题"><el-input v-model="newArticle.title" /></el-form-item>
            <el-form-item label="分类"><el-input v-model="newArticle.category" /></el-form-item>
            <el-form-item label="标签"><el-input v-model="newArticle.tags" placeholder="逗号分隔" /></el-form-item>
            <el-form-item label="级别">
              <el-select v-model="newArticle.severity">
                <el-option label="info" value="info" />
                <el-option label="warning" value="warning" />
                <el-option label="critical" value="critical" />
              </el-select>
            </el-form-item>
            <el-form-item label="内容"><el-input v-model="newArticle.content" type="textarea" :rows="6" /></el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="showArticleDialog = false">取消</el-button>
            <el-button type="primary" @click="handleCreateArticle">创建</el-button>
          </template>
        </el-dialog>

        <el-dialog v-model="showEditArticleDialog" title="编辑文章" width="600px">
          <el-form label-width="80px">
            <el-form-item label="标题"><el-input v-model="editArticle.title" /></el-form-item>
            <el-form-item label="分类"><el-input v-model="editArticle.category" /></el-form-item>
            <el-form-item label="标签"><el-input v-model="editArticle.tags" placeholder="逗号分隔" /></el-form-item>
            <el-form-item label="级别">
              <el-select v-model="editArticle.severity">
                <el-option label="info" value="info" />
                <el-option label="warning" value="warning" />
                <el-option label="critical" value="critical" />
              </el-select>
            </el-form-item>
            <el-form-item label="内容"><el-input v-model="editArticle.content" type="textarea" :rows="6" /></el-form-item>
          </el-form>
          <template #footer>
            <el-button @click="showEditArticleDialog = false">取消</el-button>
            <el-button type="primary" @click="handleUpdateArticle">保存</el-button>
          </template>
        </el-dialog>
      </el-tab-pane>

    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { getUsers, createUser, updateUser, deleteUser, resetPassword } from '@/api/users'
import { getTools, addTool, updateTool, deleteTool, toggleTool } from '@/api/tools'
import { getConfig, updateConfig } from '@/api/system'
import api from '@/api/index'
import type { UserInfo } from '@/api/users'
import type { ToolInfo } from '@/api/tools'

const activeTab = ref('users')
const roleMap: Record<string, string> = { admin: '管理员', user: '普通用户' }

// ========== 用户管理 ==========
const users = ref<UserInfo[]>([])
const showUserDialog = ref(false)
const showEditUserDialog = ref(false)
const userCreating = ref(false)
const newUser = reactive({ username: '', password: '', role: 'user' })
const editUser = reactive({ id: '', username: '', role: '', password: '' })

async function loadUsers() {
  try { users.value = (await getUsers()).items } catch {}
}
function handleCreateUser() {
  if (!newUser.username || !newUser.password) { ElMessage.warning('请填写完整'); return }
  userCreating.value = true
  createUser({ ...newUser }).then(() => { ElMessage.success('创建成功'); showUserDialog.value = false; newUser.username = ''; newUser.password = ''; loadUsers() }).finally(() => userCreating.value = false)
}
function openEditUser(row: UserInfo) {
  editUser.id = row.id; editUser.username = row.username; editUser.role = row.role; editUser.password = ''
  showEditUserDialog.value = true
}
async function handleUpdateUser() {
  try { await updateUser(editUser.id, { role: editUser.role, password: editUser.password || '' }); ElMessage.success('更新成功'); showEditUserDialog.value = false; loadUsers() } catch {}
}
async function handleResetPwd(row: UserInfo) {
  try { await ElMessageBox.prompt('请输入新密码', '重置密码', { confirmButtonText: '确定', inputType: 'password' }); await resetPassword(row.id, (arguments[1] as any)?.value || '123456'); ElMessage.success('密码已重置') } catch {}
}
async function handleDeleteUser(row: UserInfo) {
  try { await ElMessageBox.confirm('确定删除该用户？', '确认', { type: 'warning' }); await deleteUser(row.id); ElMessage.success('已删除'); loadUsers() } catch {}
}

// ========== 工具管理 ==========
const tools = ref<ToolInfo[]>([])
const showToolDialog = ref(false)
const showPresetDialog = ref(false)
const isEditTool = ref(false)
const toolSaving = ref(false)
const importing = ref(false)
const currentTool = reactive({
  id: '',
  name: '',
  description: '',
  category: '',
  riskLevel: 1,
  enabled: true,
  configStr: ''
})
const presetTools = ref<any[]>([])

function riskTagType(level: number) { return level <= 1 ? 'info' : level <= 2 ? '' : level <= 3 ? 'warning' : 'danger' }

const PRESET_TOOLS = [
  { name: 'get_system_info', description: '获取系统概览信息', category: 'system_monitor', riskLevel: 1 },
  { name: 'get_disk_usage', description: '查询磁盘挂载和使用情况', category: 'system_monitor', riskLevel: 1 },
  { name: 'get_cpu_info', description: '获取CPU使用率、核心数、负载等信息', category: 'system_monitor', riskLevel: 1 },
  { name: 'get_memory_info', description: '获取内存和交换区使用情况', category: 'system_monitor', riskLevel: 1 },
  { name: 'list_processes', description: '获取进程列表，可按CPU或内存排序', category: 'process_management', riskLevel: 1 },
  { name: 'get_process_detail', description: '获取指定进程的详细信息', category: 'process_management', riskLevel: 1 },
  { name: 'kill_process', description: '终止指定进程，默认发送TERM信号', category: 'process_management', riskLevel: 3 },
  { name: 'get_network_connections', description: '查询网络连接状态和监听端口', category: 'network_management', riskLevel: 1 },
  { name: 'get_service_status', description: '获取指定系统服务的状态', category: 'service_management', riskLevel: 1 },
  { name: 'manage_service', description: '管理系统服务：启动、停止、重启、重载', category: 'service_management', riskLevel: 3 },
  { name: 'get_file_list', description: '获取指定目录的文件列表', category: 'file_management', riskLevel: 1 },
  { name: 'read_file', description: '读取指定文件的内容', category: 'file_management', riskLevel: 1 },
  { name: 'search_journal_logs', description: '搜索系统日志', category: 'log_management', riskLevel: 1 },
  { name: 'get_users', description: '获取系统用户列表', category: 'system_operation', riskLevel: 1 },
  { name: 'get_groups', description: '获取系统用户组列表', category: 'system_operation', riskLevel: 1 },
  { name: 'execute_command', description: '在远程系统上执行shell命令', category: 'system_operation', riskLevel: 4 },
  { name: 'summarize_task', description: '总结当前任务，结束对话，提供最终报告', category: 'system_operation', riskLevel: 1 },
]

async function loadTools() {
  try { tools.value = (await getTools()).items } catch {}
}
function openAddToolDialog() {
  isEditTool.value = false
  Object.assign(currentTool, { id: '', name: '', description: '', category: '', riskLevel: 1, enabled: true, configStr: '' })
  showToolDialog.value = true
}
function openEditTool(row: ToolInfo) {
  isEditTool.value = true
  Object.assign(currentTool, {
    id: row.id,
    name: row.name,
    description: row.description,
    category: row.category,
    riskLevel: row.riskLevel,
    enabled: row.enabled,
    configStr: JSON.stringify(row.config || {}, null, 2)
  })
  showToolDialog.value = true
}
async function handleSaveTool() {
  if (!currentTool.name) { ElMessage.warning('请填写工具名称'); return }
  toolSaving.value = true
  try {
    let config = {}
    try {
      config = currentTool.configStr ? JSON.parse(currentTool.configStr) : {}
    } catch {
      config = {}
    }
    if (isEditTool.value) {
      await updateTool(currentTool.id, {
        name: currentTool.name,
        description: currentTool.description,
        category: currentTool.category,
        riskLevel: currentTool.riskLevel,
        enabled: currentTool.enabled,
        config
      })
      ElMessage.success('工具已更新')
    } else {
      await addTool({
        name: currentTool.name,
        description: currentTool.description,
        category: currentTool.category,
        riskLevel: currentTool.riskLevel,
        enabled: currentTool.enabled,
        config
      })
      ElMessage.success('工具已添加')
    }
    showToolDialog.value = false
    loadTools()
  } catch (e: any) {
    ElMessage.error(e.message || '保存失败')
  } finally {
    toolSaving.value = false
  }
}
async function onToggleTool(v: any, row: ToolInfo) {
  try { await toggleTool(row.id, v as boolean); loadTools() } catch {}
}
async function handleDeleteTool(row: ToolInfo) {
  try { await ElMessageBox.confirm('确定删除该工具？', '确认', { type: 'warning' }); await deleteTool(row.id); ElMessage.success('已删除'); loadTools() } catch {}
}

function loadPresetTools() {
  presetTools.value = PRESET_TOOLS.map(t => ({ ...t, selected: false }))
  showPresetDialog.value = true
}

async function importPresetTools() {
  const selected = presetTools.value.filter(t => t.selected)
  if (!selected.length) { ElMessage.warning('请选择要导入的工具'); return }
  importing.value = true
  try {
    for (const tool of selected) {
      try {
        await addTool({
          name: tool.name,
          description: tool.description,
          category: tool.category,
          riskLevel: tool.riskLevel,
          enabled: true,
          config: {}
        })
      } catch (e) {
        // 忽略已存在的工具
      }
    }
    ElMessage.success('导入完成')
    showPresetDialog.value = false
    loadTools()
  } finally {
    importing.value = false
  }
}

// ========== 安全配置 ==========
const config = reactive({ llm: { apiBase: '', model: '', apiKey: '', temperature: 0.1, maxTokens: 4096 }, security: { approvalTimeout: 60, maxRounds: 20 } })
const savingConfig = ref(false)

async function loadConfig() {
  try { const data = await getConfig(); if (data?.llm) Object.assign(config.llm, data.llm); if (data?.security) Object.assign(config.security, data.security) } catch {}
}
async function saveConfig() {
  savingConfig.value = true
  try { await updateConfig({ llm: config.llm, security: config.security }); ElMessage.success('配置已保存') } finally { savingConfig.value = false }
}

// ========== 知识库 ==========
const articles = ref<any[]>([])
const showArticleDialog = ref(false)
const showEditArticleDialog = ref(false)
const newArticle = reactive({ title: '', category: '', tags: '', content: '', severity: 'info' })
const editArticle = reactive({ id: '', title: '', category: '', tags: '', content: '', severity: 'info' })

async function loadArticles() {
  try { const { data } = await api.get('/knowledge/articles?size=100'); articles.value = data.data?.items || [] } catch {}
}
async function handleCreateArticle() {
  try { await api.post('/knowledge/articles', { ...newArticle, tags: newArticle.tags }); ElMessage.success('文章已创建'); showArticleDialog.value = false; newArticle.title = ''; newArticle.content = ''; loadArticles() } catch {}
}
function openEditArticle(row: any) {
  editArticle.id = row.id; editArticle.title = row.title; editArticle.category = row.category; editArticle.tags = Array.isArray(row.tags) ? row.tags.join(',') : (row.tags || ''); editArticle.content = row.content; editArticle.severity = row.severity
  showEditArticleDialog.value = true
}
async function handleUpdateArticle() {
  try { await api.put(`/knowledge/articles/${editArticle.id}`, { ...editArticle, tags: editArticle.tags }); ElMessage.success('文章已更新'); showEditArticleDialog.value = false; loadArticles() } catch {}
}
async function handleDeleteArticle(row: any) {
  try { await ElMessageBox.confirm('确定删除该文章？', '确认', { type: 'warning' }); await api.delete(`/knowledge/articles/${row.id}`); ElMessage.success('已删除'); loadArticles() } catch {}
}

onMounted(() => { loadUsers(); loadTools(); loadConfig(); loadArticles() })
</script>

<style lang="scss" scoped>
.admin-page { max-width: 1300px; margin: 0 auto; }

.page-header {
  margin-bottom: 16px;
  .page-title { font-size: 20px; font-weight: 700; color: #1e293b; }
  .page-desc { font-size: 13px; color: #94a3b8; margin-top: 4px; }
}

.tab-toolbar { margin-bottom: 12px; }

.config-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }

.config-card {
  padding: 20px;
  h3 { font-size: 15px; font-weight: 600; color: #1e293b; margin: 0 0 16px; }
  .field { margin-bottom: 14px; label { display: block; font-size: 12px; font-weight: 600; color: #94a3b8; margin-bottom: 4px; } }
  .field-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
}

.preset-tool-list {
  max-height: 400px;
  overflow-y: auto;
  .preset-tool-item {
    padding: 8px 12px;
    border-bottom: 1px solid #f1f5f9;
    &:hover { background: #f8fafc; }
    .preset-tool-name {
      font-family: 'JetBrains Mono', Consolas, monospace;
      font-size: 13px;
      font-weight: 500;
      color: #2563eb;
      margin-right: 12px;
    }
    .preset-tool-desc {
      font-size: 12px;
      color: #64748b;
      margin-right: 12px;
    }
    .preset-tool-risk {
      float: right;
    }
  }
}

.save-row { display: flex; justify-content: center; margin-top: 20px; }
</style>
