<template>
  <div class="settings-page">
    <div class="page-header">
      <h2 class="page-title">系统设置</h2>
      <p class="page-desc">模型配置、工具管理、安全规则与系统状态监控</p>
    </div>

    <div class="settings-grid">
      <!-- 模型配置 -->
      <div class="panel card">
        <div class="panel-head">
          <div class="panel-icon">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <rect x="2" y="2" width="16" height="16" rx="4" stroke="#2563eb" stroke-width="1.5"/>
              <path d="M6 10l3 3 5-6" stroke="#2563eb" stroke-width="1.5" stroke-linecap="round"/>
            </svg>
          </div>
          <h3>模型配置</h3>
        </div>
        <div class="panel-body">
          <div class="field">
            <label>API 地址</label>
            <el-input v-model="settings.llm.apiBase" size="default" :disabled="isSaving"/>
          </div>
          <div class="field">
            <label>模型名称</label>
            <el-input v-model="settings.llm.model" size="default" :disabled="isSaving"/>
          </div>
          <div class="field">
            <label>API Key</label>
            <el-input v-model="settings.llm.apiKey" type="password" show-password size="default" :disabled="isSaving"/>
          </div>
          <div class="field-row">
            <div class="field">
              <label>温度</label>
              <el-input-number v-model="settings.llm.temperature" :min="0" :max="2" :step="0.1" :precision="1" size="default" :disabled="isSaving"/>
            </div>
            <div class="field">
              <label>最大 Token</label>
              <el-input-number v-model="settings.llm.maxTokens" :min="512" :max="32768" :step="512" size="default" :disabled="isSaving"/>
            </div>
          </div>
        </div>
      </div>

      <!-- 工具管理 -->
      <div class="panel card">
        <div class="panel-head">
          <div class="panel-icon">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <rect x="3" y="3" width="6" height="6" rx="1.5" stroke="#2563eb" stroke-width="1.3"/>
              <rect x="11" y="3" width="6" height="6" rx="1.5" stroke="#2563eb" stroke-width="1.3"/>
              <rect x="3" y="11" width="6" height="6" rx="1.5" stroke="#2563eb" stroke-width="1.3"/>
              <rect x="11" y="11" width="6" height="6" rx="1.5" stroke="#2563eb" stroke-width="1.3"/>
            </svg>
          </div>
          <h3>工具管理</h3>
        </div>
        <div class="panel-body">
          <div class="tool-list">
            <div class="tool-item" v-for="tool in tools" :key="tool.name">
              <div class="tool-info">
                <span class="tool-name">{{ tool.name }}</span>
                <span class="tool-desc">{{ tool.desc }}</span>
              </div>
              <el-switch v-model="tool.enabled" active-color="#2563eb" :disabled="isSaving"/>
            </div>
          </div>
        </div>
      </div>

      <!-- 安全配置 -->
      <div class="panel card">
        <div class="panel-head">
          <div class="panel-icon">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M4 10l3-6h6l3 6-6 8-6-8z" stroke="#2563eb" stroke-width="1.5"/>
              <circle cx="10" cy="11" r="2" stroke="#2563eb" stroke-width="1.3"/>
            </svg>
          </div>
          <h3>安全配置</h3>
        </div>
        <div class="panel-body">
          <div class="field">
            <label>审批超时（秒）</label>
            <el-input-number v-model="settings.security.approvalTimeout" :min="10" :max="300" :step="10" size="default" :disabled="isSaving"/>
          </div>
          <div class="field">
            <label>最大对话轮次</label>
            <el-input-number v-model="settings.security.maxRounds" :min="5" :max="100" :step="5" size="default" :disabled="isSaving"/>
          </div>
          <div class="field">
            <label>安全规则</label>
            <div class="rule-count">
              <span class="count-num">24</span>
              <span class="count-unit">条活跃规则</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 系统状态 -->
      <div class="panel card">
        <div class="panel-head">
          <div class="panel-icon">
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <circle cx="10" cy="10" r="7" stroke="#2563eb" stroke-width="1.5"/>
              <path d="M10 6v4l3 2" stroke="#2563eb" stroke-width="1.3" stroke-linecap="round"/>
            </svg>
          </div>
          <h3>系统状态</h3>
        </div>
        <div class="panel-body">
          <div class="health-grid">
            <div class="health-item" v-for="comp in components" :key="comp.name">
              <span class="status-dot" :class="comp.status"></span>
              <div class="comp-info">
                <span class="comp-name">{{ comp.name }}</span>
                <span class="comp-latency" v-if="comp.latency">{{ comp.latency }}ms</span>
              </div>
            </div>
          </div>
          <div class="health-footer">
            <span>版本: v1.0.0</span>
            <button class="refresh-btn" @click="loadHealth" :disabled="isRefreshing">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" :class="{ spinning: isRefreshing }">
                <path d="M1 7a6 6 0 0111.3-3M13 7a6 6 0 01-11.3 3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                <path d="M1 1v3h3M13 13v-3h-3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              </svg>
              {{ isRefreshing ? '刷新中...' : '刷新' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="save-row">
      <button class="tech-btn primary save-btn" @click="saveSettings" :disabled="isSaving">
        <svg v-if="isSaving" width="16" height="16" viewBox="0 0 24 24" fill="none" class="spinning">
          <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" stroke-opacity="0.3"/>
          <path d="M12 2a10 10 0 0110 10" stroke="currentColor" stroke-width="3" stroke-linecap="round"/>
        </svg>
        {{ isSaving ? '保存中...' : '保存配置' }}
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getConfig, updateConfig, getHealth } from '@/api/system'

const isSaving = ref(false)
const isRefreshing = ref(false)

const settings = reactive({
  llm: {
    apiBase: 'https://api.example.com/v1',
    model: 'qwen-plus',
    apiKey: '',
    temperature: 0.1,
    maxTokens: 4096,
  },
  security: {
    approvalTimeout: 60,
    maxRounds: 20,
  },
})

const tools = ref([
  { name: 'get_cpu_info', desc: 'CPU 信息采集', enabled: true },
  { name: 'get_memory_info', desc: '内存信息采集', enabled: true },
  { name: 'get_disk_usage', desc: '磁盘使用率查询', enabled: true },
  { name: 'get_disk_io', desc: '磁盘 I/O 统计', enabled: true },
  { name: 'list_processes', desc: '进程列表', enabled: true },
  { name: 'get_process_detail', desc: '进程详情', enabled: true },
  { name: 'get_network_connections', desc: '网络连接查询', enabled: true },
  { name: 'search_journal_logs', desc: '系统日志查询', enabled: true },
  { name: 'restart_service', desc: '服务重启', enabled: false },
  { name: 'clean_temp_files', desc: '临时文件清理', enabled: false },
  { name: 'clean_old_logs', desc: '旧日志清理', enabled: false },
])

const components = ref([
  { name: '数据库', status: 'online', latency: 2 },
  { name: 'LLM API', status: 'online', latency: 150 },
  { name: 'system-info MCP', status: 'online', latency: 5 },
  { name: 'logs MCP', status: 'online', latency: 8 },
  { name: 'actions MCP', status: 'warning', latency: null },
  { name: 'network MCP', status: 'online', latency: 4 },
])

async function loadHealth() {
  if (isRefreshing.value) return
  isRefreshing.value = true
  try {
    const data = await getHealth()
    if (data?.components) {
      const comps = data.components
      const list: any[] = []
      if (comps.database) list.push({ name: '数据库', status: comps.database.status === 'up' ? 'online' : 'offline', latency: comps.database.latencyMs })
      if (comps.llmApi) list.push({ name: 'LLM API', status: comps.llmApi.status === 'up' ? 'online' : 'offline', latency: comps.llmApi.latencyMs })
      if (comps.mcpServers) {
        for (const [name, info] of Object.entries(comps.mcpServers) as any) {
          list.push({ name: `${name} MCP`, status: info?.status === 'up' ? 'online' : 'offline', latency: null })
        }
      }
      if (list.length) components.value = list
    }
    ElMessage.success('状态刷新成功')
  } catch {
    ElMessage.error('状态刷新失败')
  } finally {
    isRefreshing.value = false
  }
}

async function saveSettings() {
  if (isSaving.value) return
  isSaving.value = true
  try {
    await updateConfig(settings)
    ElMessage.success('配置保存成功！')
  } catch (error: any) {
    ElMessage.error(error?.message || '配置保存失败，请重试')
  } finally {
    isSaving.value = false
  }
}

onMounted(() => {
  loadHealth()
  getConfig().then(data => {
    if (data) {
      if (data.llm) Object.assign(settings.llm, data.llm)
      if (data.security) Object.assign(settings.security, data.security)
    }
  })
})
</script>

<style lang="scss" scoped>
.settings-page { max-width: 1200px; margin: 0 auto; }

.page-header {
  margin-bottom: 20px;
  .page-title { font-size: 20px; font-weight: 700; color: #1e293b; }
  .page-desc { font-size: 13px; color: #94a3b8; margin-top: 4px; }
}

.settings-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.panel {
  padding: 20px;
  .panel-head {
    display: flex; align-items: center; gap: 10px;
    margin-bottom: 16px;
    h3 { font-size: 15px; font-weight: 600; color: #1e293b; }
  }
  .panel-icon {
    width: 36px; height: 36px;
    border-radius: 8px;
    background: #eff6ff;
    display: flex;
    align-items: center;
    justify-content: center;
  }
}

.field {
  margin-bottom: 14px;
  label {
    display: block;
    font-size: 12px;
    font-weight: 600;
    color: #94a3b8;
    margin-bottom: 4px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
}

.field-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.tool-list {
  display: flex; flex-direction: column;
  gap: 2px; max-height: 300px;
  overflow-y: auto;
}

.tool-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  border-radius: 8px;
  &:hover { background: #f8fafc; }
  .tool-info {
    .tool-name {
      font-family: 'JetBrains Mono', Consolas, monospace;
      font-size: 13px; color: #2563eb; font-weight: 500;
      display: block;
    }
    .tool-desc { font-size: 11px; color: #94a3b8; }
  }
}

.rule-count {
  display: flex; align-items: baseline; gap: 8px;
  .count-num {
    font-size: 28px; font-weight: 700;
    font-family: 'JetBrains Mono', Consolas, monospace;
    color: #2563eb;
  }
  .count-unit { font-size: 13px; color: #94a3b8; }
}

.health-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.health-item {
  display: flex; align-items: center; gap: 8px;
  padding: 8px;
  border-radius: 6px;
  background: #f8fafc;
  .comp-info {
    .comp-name { font-size: 12px; color: #1e293b; font-weight: 500; display: block; }
    .comp-latency { font-size: 11px; color: #94a3b8; }
  }
}

.health-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid #f1f5f9;
  font-size: 12px; color: #94a3b8;
}

.refresh-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 14px;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #64748b;
  font-size: 12px;
  cursor: pointer;
  &:hover:not(:disabled) { border-color: #2563eb; color: #2563eb; background: #eff6ff; }
  &:disabled { opacity: 0.6; cursor: not-allowed; }
}

.save-row {
  display: flex;
  justify-content: center;
  margin-top: 24px;
}

.save-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  &:disabled { opacity: 0.7; cursor: not-allowed; }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.spinning {
  animation: spin 0.8s linear infinite;
}
</style>
