<template>
  <div class="servers-page">
    <ServerGridBackground :shock-tick="shockTick" />

    <div class="servers-content">
      <ServerPageHeader
        :online-count="onlineCount"
        :offline-count="offlineCount"
        :total="servers.length"
        :default-name="defaultServerName"
        :refreshing="statusRefreshing"
        @add="openAddDialog"
        @refresh-status="refreshAllStatuses"
      />

      <div class="server-grid" v-if="servers.length">
        <ServerCard
          v-for="srv in servers"
          :key="srv.id"
          :server="srv"
          :testing="testingId === srv.id || statusRefreshing"
          @test="handleTest"
          @set-default="handleSetDefault"
          @edit="openEditDialog"
          @delete="handleDelete"
        />
      </div>

      <ServerEmptyState v-else @add="openAddDialog" />
    </div>

    <ServerFormDialog
      :visible="dialogVisible"
      :edit-id="editId"
      :form="form"
      :tags-input="tagsInput"
      :saving="saving"
      :can-save="canSave"
      :default-username="defaultUsername"
      :edit-auth-configured="editAuthConfigured"
      :reach-checking="reachChecking"
      :reach-message="reachMessage"
      :reach-ok="reachOk"
      :reach-suggestions="reachSuggestions"
      :reach-diagnosis="reachDiagnosis"
      :suggested-host="suggestedHost"
      :duplicate-name="duplicateServer?.name"
      :provision-steps="provisionSteps"
      @close="closeDialog"
      @save="handleSave"
      @check-reachable="handleCheckReachable"
      @apply-suggested-host="form.host = suggestedHost"
      @edit-duplicate="onEditDuplicate"
      @update:tags-input="tagsInput = $event"
    />

    <TechConfirmDialog
      :visible="confirm.visible"
      :title="confirm.title"
      :message="confirm.message"
      :type="confirm.type"
      :confirm-text="confirm.confirmText"
      :cancel-text="confirm.cancelText"
      @confirm="resolveConfirm(true)"
      @cancel="resolveConfirm(false)"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import {
  getServers, getServerDefaults, addServer, updateServer, deleteServer,
  testServerConnection, checkServerReachable, type ServerInfo, type ProvisionStep,
} from '@/api/servers'
import { ElMessage } from 'element-plus'
import ServerGridBackground from '@/components/servers/ServerGridBackground.vue'
import ServerPageHeader from '@/components/servers/ServerPageHeader.vue'
import ServerCard from '@/components/servers/ServerCard.vue'
import ServerEmptyState from '@/components/servers/ServerEmptyState.vue'
import ServerFormDialog from '@/components/servers/ServerFormDialog.vue'
import TechConfirmDialog from '@/components/servers/TechConfirmDialog.vue'

const servers = ref<ServerInfo[]>([])
const listLoading = ref(false)
const statusRefreshing = ref(false)
const shockTick = ref(0)
const testingId = ref<string | null>(null)
const defaultUsername = ref('ty')
const restrictedUsers = ref(['root', 'administrator'])
const dialogVisible = ref(false)
const editId = ref<string | null>(null)
const editAuthConfigured = ref(false)
const tagsInput = ref('')
const saving = ref(false)
const reachChecking = ref(false)
const reachMessage = ref('')
const reachOk = ref(false)
const reachSuggestions = ref<string[]>([])
const reachDiagnosis = ref<{ localIp?: string; sameSubnet?: boolean } | null>(null)
const provisionSteps = ref<ProvisionStep[]>([])

const confirm = ref({
  visible: false,
  title: '',
  message: '',
  type: 'info' as 'info' | 'warning' | 'danger',
  confirmText: '确定',
  cancelText: '取消',
})
let confirmResolver: ((v: boolean) => void) | null = null

const emptyForm = () => ({
  name: '', host: '', port: 22, username: defaultUsername.value,
  hostPassword: '', description: '', isDefault: false,
})

const form = ref(emptyForm())

const onlineCount = computed(() => servers.value.filter(s => s.status === 'online').length)
const offlineCount = computed(() => servers.value.filter(s => s.status === 'offline').length)
const defaultServerName = computed(() => servers.value.find(s => s.isDefault)?.name || '')

const duplicateServer = computed(() => {
  if (editId.value) return null
  const host = (form.value.host || '').trim()
  if (!host) return null
  return servers.value.find(s => s.host === host) || null
})

const suggestedHost = computed(() => {
  const host = (form.value.host || '').trim()
  const m = host.match(/^192\.168\.(\d+)\.(\d+)$/)
  if (m && reachDiagnosis.value?.localIp) {
    const prefix = reachDiagnosis.value.localIp.split('.').slice(0, 3).join('.')
    return `${prefix}.${m[2]}`
  }
  return reachDiagnosis.value?.localIp?.replace(/\.\d+$/, '.128') || '192.168.64.128'
})

const canSave = computed(() => {
  if (!form.value.name?.trim() || !form.value.host?.trim() || !form.value.username?.trim()) return false
  if (isRestrictedUsername(form.value.username)) return false
  if (!editId.value && duplicateServer.value) return false
  if (!editId.value && !form.value.hostPassword?.trim()) return false
  return true
})

function isRestrictedUsername(username: string) {
  return restrictedUsers.value.includes((username || '').trim().toLowerCase())
}

function techConfirm(opts: {
  title: string
  message: string
  type?: 'info' | 'warning' | 'danger'
  confirmText?: string
  cancelText?: string
}): Promise<boolean> {
  confirm.value = {
    visible: true,
    title: opts.title,
    message: opts.message,
    type: opts.type || 'info',
    confirmText: opts.confirmText || '确定',
    cancelText: opts.cancelText || '取消',
  }
  return new Promise(resolve => { confirmResolver = resolve })
}

function resolveConfirm(result: boolean) {
  confirm.value.visible = false
  confirmResolver?.(result)
  confirmResolver = null
}

function formatApiError(e: any): string {
  const detail = e?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (detail && typeof detail === 'object' && detail.message) return detail.message
  return '操作失败'
}

function getStepsFromError(e: any): ProvisionStep[] {
  const detail = e?.response?.data?.detail
  if (detail && typeof detail === 'object' && Array.isArray(detail.steps)) return detail.steps
  return []
}

function getExistingFromError(e: any): ServerInfo | null {
  const detail = e?.response?.data?.detail
  if (detail && typeof detail === 'object' && detail.existing) return detail.existing as ServerInfo
  return null
}

async function loadServers(retryCount = 0) {
  listLoading.value = true
  try {
    const data = await getServers()
    servers.value = data.items || []
  } catch {
    if (retryCount < 2) setTimeout(() => loadServers(retryCount + 1), 1000 * (retryCount + 1))
  } finally {
    listLoading.value = false
  }
}

async function refreshAllStatuses() {
  if (statusRefreshing.value) return
  if (!servers.value.length) {
    await loadServers()
    return
  }

  statusRefreshing.value = true
  shockTick.value++

  try {
    await Promise.allSettled(servers.value.map(s => testServerConnection(s.id)))
    await loadServers()
    const online = servers.value.filter(s => s.status === 'online').length
    const total = servers.value.length
    ElMessage.success(`全集群状态已刷新：${online}/${total} 在线`)
  } catch {
    ElMessage.error('批量刷新状态失败')
  } finally {
    statusRefreshing.value = false
  }
}

function resetDialogState() {
  provisionSteps.value = []
  reachMessage.value = ''
  reachOk.value = false
  reachSuggestions.value = []
  reachDiagnosis.value = null
  saving.value = false
}

function openAddDialog() {
  editId.value = null
  editAuthConfigured.value = false
  form.value = emptyForm()
  tagsInput.value = ''
  resetDialogState()
  dialogVisible.value = true
}

function onEditDuplicate() {
  if (duplicateServer.value) openEditDialog(duplicateServer.value)
}

function openEditDialog(srv: ServerInfo) {
  editId.value = srv.id
  editAuthConfigured.value = !!srv.authConfigured
  form.value = {
    name: srv.name, host: srv.host, port: srv.port,
    username: srv.username, hostPassword: '',
    description: srv.description, isDefault: srv.isDefault,
  }
  tagsInput.value = (srv.tags || []).join(', ')
  resetDialogState()
  dialogVisible.value = true
}

function closeDialog() {
  if (saving.value) return
  dialogVisible.value = false
}

async function handleCheckReachable() {
  const host = form.value.host?.trim()
  if (!host) return
  reachChecking.value = true
  reachMessage.value = ''
  reachSuggestions.value = []
  try {
    const res = await checkServerReachable(host, form.value.port || 22)
    reachOk.value = res.reachable
    reachMessage.value = res.message
    reachSuggestions.value = res.suggestions || []
    reachDiagnosis.value = { localIp: res.localIp, sameSubnet: res.sameSubnet }
  } catch {
    reachOk.value = false
    reachMessage.value = '连通性检测失败'
  } finally {
    reachChecking.value = false
  }
}

async function handleSave() {
  if (isRestrictedUsername(form.value.username)) {
    ElMessage.error(`禁止使用 ${form.value.username}，请使用普通用户（如 ${defaultUsername.value}）`)
    return
  }
  if (editId.value && !form.value.hostPassword?.trim()) {
    const ok = await techConfirm({
      title: '提示',
      message: '未填写主机密码，将仅更新基本信息，不会重新配置 SSH。是否继续？',
      type: 'info',
      confirmText: '继续保存',
    })
    if (!ok) return
  }

  const tags = tagsInput.value.split(',').map(t => t.trim()).filter(Boolean)
  const payload = { ...form.value, tags }
  saving.value = true
  provisionSteps.value = []

  try {
    let res: any
    if (editId.value) {
      res = await updateServer(editId.value, payload)
      ElMessage.success(res.message || '服务器已更新')
    } else {
      res = await addServer(payload)
      ElMessage.success(res.message || '服务器添加成功')
    }
    if (res.provision?.steps?.length) provisionSteps.value = res.provision.steps
    await loadServers()
    setTimeout(() => { dialogVisible.value = false }, res.provision?.steps?.length ? 1200 : 0)
  } catch (e: any) {
    const steps = getStepsFromError(e)
    if (steps.length) provisionSteps.value = steps
    const existing = getExistingFromError(e)
    const msg = formatApiError(e)
    if (existing && !editId.value) {
      const ok = await techConfirm({
        title: '主机已存在',
        message: `${msg}\n\n是否打开已有服务器进行编辑？`,
        type: 'warning',
        confirmText: '编辑已有',
      })
      if (ok) {
        openEditDialog(existing)
        return
      }
    }
    ElMessage.error(msg)
  } finally {
    saving.value = false
  }
}

async function handleDelete(srv: ServerInfo) {
  const ok = await techConfirm({
    title: '确认删除',
    message: `确定要删除服务器「${srv.name}」吗？此操作不可撤销。`,
    type: 'danger',
    confirmText: '删除',
  })
  if (!ok) return
  await deleteServer(srv.id)
  ElMessage.success('已删除')
  await loadServers()
}

async function handleTest(srv: ServerInfo) {
  testingId.value = srv.id
  try {
    const res = await testServerConnection(srv.id)
    if (res.data?.success) ElMessage.success(`连接成功: ${res.data.hostname || res.data.output}`)
    else ElMessage.error(`连接失败: ${res.data?.error || '未知错误'}`)
    await loadServers()
  } catch {
    ElMessage.error('测试连接失败')
  } finally {
    testingId.value = null
  }
}

async function handleSetDefault(srv: ServerInfo) {
  const ok = await techConfirm({
    title: '确认设置',
    message: `确定要将「${srv.name}」设为默认服务器吗？`,
    type: 'info',
  })
  if (!ok) return
  await updateServer(srv.id, { name: srv.name, host: srv.host, port: srv.port, username: srv.username, isDefault: true })
  ElMessage.success('已设为默认服务器')
  await loadServers()
}

onMounted(async () => {
  try {
    const defaults = await getServerDefaults()
    defaultUsername.value = defaults.username || 'ty'
    restrictedUsers.value = defaults.restrictedUsers || ['root', 'administrator']
  } catch {}
  await loadServers()
})
</script>

<style lang="scss" scoped>
.servers-page {
  position: relative;
  min-height: 100%;
  overflow-x: hidden;
}

.servers-content {
  position: relative;
  z-index: 1;
  max-width: 1280px;
  margin: 0 auto;
  padding: 24px 32px 40px;
  width: 100%;
  min-width: 0;
}

.server-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
}
</style>
