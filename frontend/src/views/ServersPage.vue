<template>
  <div class="servers-page">
    <div class="page-header">
      <div>
        <h2 class="page-title">服务器管理</h2>
        <p class="page-desc">多机集群运维 · 添加/编辑/删除服务器节点</p>
      </div>
      <button class="btn-add" @click="openAddDialog">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <path d="M8 3v10M3 8h10" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>
        添加服务器
      </button>
    </div>

    <!-- 服务器卡片列表 -->
    <div class="server-grid" v-if="servers.length">
      <div class="server-card" v-for="srv in servers" :key="srv.id" :class="{ default: srv.isDefault }">
        <div class="card-top">
          <div class="card-info">
            <span class="card-status" :class="srv.status"></span>
            <span class="card-name">{{ srv.name }}</span>
            <span class="card-default-tag" v-if="srv.isDefault">
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M6 1l1.5 3.5L11 5.5 8 8.5 8.5 12 6 10.5 3.5 12 4 8.5 1 5.5 4.5 4.5 6 1z" fill="currentColor"/>
              </svg>
              默认
            </span>
          </div>
          <div class="card-actions">
            <button class="act-btn test" @click="handleTest(srv)" title="测试连接">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M4 7l2 2 4-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
              </svg>
            </button>
            <button class="act-btn set-default" v-if="!srv.isDefault" @click="handleSetDefault(srv)" title="设为默认">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M7 1l1.8 4L13 6.2 9.8 9 10.6 14 7 11.8 3.4 14 4.2 9 1 6.2 5.2 5 7 1z" fill="currentColor"/>
              </svg>
            </button>
            <button class="act-btn edit" @click="openEditDialog(srv)" title="编辑">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M2 10.5V12h1.5l7.3-7.3-1.5-1.5L2 10.5zM12.6 4.1l-1.5-1.5.8-.8a1 1 0 011.4 0l.1.1a1 1 0 010 1.4l-.8.8z" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
              </svg>
            </button>
            <button class="act-btn del" @click="handleDelete(srv)" title="删除">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M3 4h8M5 4V3a1 1 0 011-1h2a1 1 0 011 1v1M10 4v6a1 1 0 01-1 1H5a1 1 0 01-1-1V4" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
              </svg>
            </button>
          </div>
        </div>
        <div class="card-body">
          <div class="card-row"><span class="card-label">地址</span><code>{{ srv.host }}:{{ srv.port }}</code></div>
          <div class="card-row"><span class="card-label">用户</span><span>{{ srv.username }}</span></div>
          <div class="card-row" v-if="srv.description"><span class="card-label">描述</span><span>{{ srv.description }}</span></div>
          <div class="card-tags" v-if="srv.tags?.length">
            <span class="tag-chip" v-for="t in srv.tags" :key="t">{{ t }}</span>
          </div>
        </div>
        <div class="card-foot">
          <span class="foot-status">状态: {{ statusLabel(srv.status) }}</span>
          <span class="foot-time" v-if="srv.lastChecked">最后检测: {{ formatDate(srv.lastChecked) }}</span>
        </div>
      </div>
    </div>

    <!-- 空态 -->
    <div class="empty-state" v-else>
      <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
        <rect x="6" y="8" width="36" height="32" rx="4" stroke="#cbd5e1" stroke-width="2"/>
        <rect x="12" y="26" width="24" height="2" rx="1" fill="#cbd5e1"/>
        <rect x="12" y="30" width="16" height="2" rx="1" fill="#cbd5e1"/>
        <circle cx="24" cy="19" r="3" stroke="#cbd5e1" stroke-width="1.5"/>
      </svg>
      <p>暂无服务器，点击「添加服务器」开始配置集群</p>
    </div>

    <!-- 添加/编辑对话框 -->
    <div class="dialog-overlay" v-if="dialogVisible" @click.self="dialogVisible = false">
      <div class="dialog-card">
        <h3>{{ editId ? '编辑服务器' : '添加服务器' }}</h3>

        <div class="form-group">
          <label>服务器名称 <span class="req">*</span></label>
          <input v-model="form.name" placeholder="如：生产服务器01" />
        </div>

        <div class="form-row">
          <div class="form-group flex-3">
            <label>主机地址 <span class="req">*</span></label>
            <input v-model="form.host" placeholder="192.168.1.100" />
          </div>
          <div class="form-group flex-1">
            <label>端口</label>
            <input v-model.number="form.port" type="number" placeholder="22" />
          </div>
        </div>

        <div class="form-row">
          <div class="form-group flex-1">
            <label>SSH 用户名</label>
            <input v-model="form.username" placeholder="root" />
          </div>
          <div class="form-group flex-1">
            <label>密钥路径</label>
            <input v-model="form.keyPath" placeholder="~/.ssh/id_rsa" />
          </div>
        </div>

        <div class="form-group">
          <label>描述</label>
          <input v-model="form.description" placeholder="可选描述" />
        </div>

        <div class="form-group">
          <label>标签（逗号分隔）</label>
          <input v-model="tagsInput" placeholder="如：web, db, prod" />
        </div>

        <div class="form-check">
          <input type="checkbox" id="chkDefault" v-model="form.isDefault" />
          <label for="chkDefault">设为默认服务器</label>
        </div>

        <div class="dialog-actions">
          <button class="btn-cancel" @click="dialogVisible = false">取消</button>
          <button class="btn-save" @click="handleSave" :disabled="!form.name || !form.host">
            {{ editId ? '保存修改' : '添加' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { getServers, addServer, updateServer, deleteServer, testServerConnection, type ServerInfo } from '@/api/servers'
import { ElMessage, ElMessageBox } from 'element-plus'

const servers = ref<ServerInfo[]>([])
const dialogVisible = ref(false)
const editId = ref<string | null>(null)
const tagsInput = ref('')

const emptyForm = () => ({
  name: '', host: '', port: 22, username: 'root',
  keyPath: '~/.ssh/id_rsa', description: '', isDefault: false,
})

const form = ref(emptyForm())

async function loadServers() {
  try {
    const data = await getServers()
    servers.value = data.items || []
  } catch {}
}

function statusLabel(status: string) {
  const m: Record<string, string> = { online: '在线', offline: '离线', unknown: '未知' }
  return m[status] || '未知'
}

function formatDate(iso: string) {
  return iso ? iso.replace('T', ' ').slice(0, 19) : '-'
}

function openAddDialog() {
  editId.value = null
  form.value = emptyForm()
  tagsInput.value = ''
  dialogVisible.value = true
}

function openEditDialog(srv: ServerInfo) {
  editId.value = srv.id
  form.value = {
    name: srv.name, host: srv.host, port: srv.port,
    username: srv.username, keyPath: srv.keyPath,
    description: srv.description, isDefault: srv.isDefault,
  }
  tagsInput.value = (srv.tags || []).join(', ')
  dialogVisible.value = true
}

async function handleSave() {
  const tags = tagsInput.value.split(',').map(t => t.trim()).filter(Boolean)
  const payload = { ...form.value, tags }
  try {
    if (editId.value) {
      await updateServer(editId.value, payload)
      ElMessage.success('服务器已更新')
    } else {
      await addServer(payload)
      ElMessage.success('服务器添加成功')
    }
    dialogVisible.value = false
    await loadServers()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || '操作失败')
  }
}

async function handleDelete(srv: ServerInfo) {
  try {
    await ElMessageBox.confirm(`确定要删除服务器「${srv.name}」吗？`, '确认删除', {
      type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
    })
    await deleteServer(srv.id)
    ElMessage.success('已删除')
    await loadServers()
  } catch {}
}

async function handleTest(srv: ServerInfo) {
  try {
    const res = await testServerConnection(srv.id)
    if (res.data?.success) {
      ElMessage.success(`连接成功: ${res.data.hostname || res.data.output}`)
    } else {
      ElMessage.error(`连接失败: ${res.data?.error || '未知错误'}`)
    }
    await loadServers()
  } catch (e: any) {
    ElMessage.error('测试连接失败')
  }
}

async function handleSetDefault(srv: ServerInfo) {
  try {
    await ElMessageBox.confirm(`确定要将「${srv.name}」设为默认服务器吗？`, '确认设置', {
      type: 'info', confirmButtonText: '确定', cancelButtonText: '取消',
    })
    await updateServer(srv.id, { ...srv, isDefault: true })
    ElMessage.success('已设为默认服务器')
    await loadServers()
  } catch {}
}

onMounted(() => loadServers())
</script>

<style lang="scss" scoped>
.servers-page {
  padding: 24px 32px;
  height: 100%;
  overflow-y: auto;
}
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 24px;
  .page-title { font-size: 20px; font-weight: 700; color: #0f172a; }
  .page-desc { font-size: 13px; color: #94a3b8; margin-top: 4px; }
}
.btn-add {
  display: flex; align-items: center; gap: 6px;
  padding: 10px 18px; border-radius: 8px; border: none;
  background: #2563eb; color: #fff; font-size: 13px; font-weight: 600; cursor: pointer;
  &:hover { background: #1d4ed8; }
}
.server-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
}
.server-card {
  background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 16px;
  transition: all 0.15s;
  &:hover { border-color: #bfdbfe; box-shadow: 0 2px 8px rgba(0,0,0,.04); }
  &.default { border-color: #2563eb; background: #fafbff; }
}
.card-top {
  display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;
  .card-info { display: flex; align-items: center; gap: 8px; }
}
.card-status {
  width: 8px; height: 8px; border-radius: 50%;
  &.online { background: #10b981; }
  &.offline { background: #ef4444; }
  &.unknown { background: #cbd5e1; }
}
.card-name { font-size: 15px; font-weight: 600; color: #1e293b; }
.card-default-tag {
  font-size: 10px; font-weight: 600; padding: 2px 8px; border-radius: 6px;
  background: linear-gradient(135deg, #fef3c7, #fde68a); color: #92400e;
  display: flex; align-items: center; gap: 4px;
  border: 1px solid #fcd34d;
  box-shadow: 0 1px 2px rgba(0,0,0,0.05);
}
.card-actions { display: flex; gap: 4px; }
.act-btn {
  width: 28px; height: 28px; border-radius: 6px; border: 1px solid #e2e8f0; background: #fff;
  display: flex; align-items: center; justify-content: center; cursor: pointer;
  &.test { color: #10b981; &:hover { background: #ecfdf5; border-color: #a7f3d0; } }
  &.set-default { color: #f59e0b; &:hover { background: #fffbeb; border-color: #fcd34d; } }
  &.edit { color: #2563eb; &:hover { background: #eff6ff; border-color: #bfdbfe; } }
  &.del { color: #ef4444; &:hover { background: #fef2f2; border-color: #fecaca; } }
}
.card-body { margin-bottom: 12px; }
.card-row {
  display: flex; gap: 8px; margin-bottom: 4px; font-size: 13px;
  .card-label { color: #94a3b8; min-width: 48px; }
  code { font-family: 'JetBrains Mono', monospace; color: #2563eb; font-size: 12px; }
}
.card-tags { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px; }
.tag-chip {
  font-size: 11px; padding: 2px 8px; border-radius: 4px; background: #f1f5f9; color: #64748b;
}
.card-foot {
  display: flex; justify-content: space-between; font-size: 11px; color: #94a3b8;
  padding-top: 10px; border-top: 1px solid #f1f5f9;
}
.empty-state {
  text-align: center; padding: 60px 0; color: #94a3b8;
  p { margin-top: 16px; font-size: 14px; }
}
.dialog-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,.3); z-index: 200;
  display: flex; align-items: center; justify-content: center;
}
.dialog-card {
  background: #fff; border-radius: 14px; padding: 24px; width: 480px; max-height: 80vh; overflow-y: auto;
  box-shadow: 0 20px 60px rgba(0,0,0,.15);
  h3 { font-size: 17px; font-weight: 600; color: #0f172a; margin-bottom: 20px; }
}
.form-group { margin-bottom: 14px; flex: 1; }
.form-row { display: flex; gap: 12px; }
.flex-3 { flex: 3; }
.flex-1 { flex: 1; }
label { display: block; font-size: 12px; font-weight: 600; color: #64748b; margin-bottom: 4px; }
.req { color: #ef4444; }
input[type="text"], input[type="number"] {
  width: 100%; padding: 8px 12px; border: 1px solid #e2e8f0; border-radius: 8px;
  font-size: 13px; color: #1e293b; outline: none; box-sizing: border-box;
  &:focus { border-color: #2563eb; box-shadow: 0 0 0 3px rgba(37,99,235,.1); }
}
.form-check {
  display: flex; align-items: center; gap: 8px; margin-bottom: 16px;
  input[type="checkbox"] { accent-color: #2563eb; }
  label { font-size: 13px; color: #1e293b; cursor: pointer; margin-bottom: 0; }
}
.dialog-actions {
  display: flex; gap: 10px; justify-content: flex-end; padding-top: 8px;
}
.btn-cancel {
  padding: 8px 20px; border-radius: 8px; border: 1px solid #e2e8f0; background: #fff;
  color: #64748b; font-size: 13px; cursor: pointer;
  &:hover { background: #f8fafc; }
}
.btn-save {
  padding: 8px 20px; border-radius: 8px; border: none; background: #2563eb;
  color: #fff; font-size: 13px; font-weight: 600; cursor: pointer;
  &:hover { background: #1d4ed8; }
  &:disabled { background: #94a3b8; cursor: not-allowed; }
}
</style>
