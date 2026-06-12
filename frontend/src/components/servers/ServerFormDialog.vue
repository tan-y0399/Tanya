<template>
  <Transition name="modal-fade">
    <div v-if="visible" class="dialog-overlay" @click.self="emit('close')">
      <div class="dialog-card glass-panel" :class="{ saving }">
        <div class="dialog-header">
          <div class="dialog-header-icon">
            <svg v-if="editId" width="22" height="22" viewBox="0 0 22 22" fill="none">
              <path d="M14 3l5 5-9 9H5v-5l9-9z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
            </svg>
            <svg v-else width="22" height="22" viewBox="0 0 22 22" fill="none">
              <rect x="3" y="5" width="16" height="12" rx="2" stroke="currentColor" stroke-width="1.5"/>
              <path d="M7 9h8M7 12h5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
            </svg>
          </div>
          <div>
            <h3>{{ editId ? '编辑服务器' : '添加服务器' }}</h3>
            <p class="dialog-sub">AUTO SSH PROVISION · PASSWORD → KEY</p>
          </div>
          <button type="button" class="dialog-close" @click="emit('close')" :disabled="saving">×</button>
        </div>

        <div class="dialog-body">
          <section class="form-section">
            <div class="section-title"><span class="section-index">01</span>基本信息</div>
            <div class="form-group">
              <label>服务器名称 <span class="req">*</span></label>
              <input v-model="form.name" class="field-input" placeholder="如：生产服务器01" :disabled="saving" />
            </div>
          </section>

          <section class="form-section">
            <div class="section-title"><span class="section-index network">02</span>连接配置</div>
            <div class="form-row">
              <div class="form-group flex-3">
                <label>主机地址 <span class="req">*</span></label>
                <div class="input-with-action">
                  <input
                    v-model="form.host"
                    class="field-input mono"
                    placeholder="192.168.1.100 或穿透域名"
                    :disabled="saving"
                    @blur="emit('checkReachable')"
                  />
                  <button
                    type="button"
                    class="inline-btn tech-btn"
                    :class="{ pulsing: reachChecking }"
                    @click="emit('checkReachable')"
                    :disabled="saving || !form.host.trim()"
                  >{{ reachChecking ? '检测中…' : '检测连通' }}</button>
                </div>
                <ConnectivityDiagnosis
                  :message="reachMessage"
                  :ok="reachOk"
                  :suggestions="reachSuggestions"
                  :show-subnet-note="!!(reachDiagnosis?.localIp && !reachDiagnosis?.sameSubnet)"
                  :suggested-host="suggestedHost"
                  @apply-suggested-host="emit('applySuggestedHost')"
                />
                <p class="form-warn" v-if="duplicateName">
                  该主机已注册为「{{ duplicateName }}」
                  <button type="button" class="link-btn" @click="emit('editDuplicate')">编辑已有</button>
                </p>
              </div>
              <div class="form-group flex-1">
                <label>端口</label>
                <input v-model.number="form.port" class="field-input mono" type="number" placeholder="22" :disabled="saving" />
              </div>
            </div>
            <div class="form-row">
              <div class="form-group flex-1">
                <label>SSH 用户名 <span class="req">*</span></label>
                <input v-model="form.username" class="field-input mono" :placeholder="defaultUsername" :disabled="saving" />
                <p class="form-hint">禁止使用 root，将自动创建普通用户并配置免密 SSH</p>
              </div>
              <div class="form-group flex-1">
                <label>主机密码 <span class="req" v-if="!editId">*</span></label>
                <div class="password-wrap">
                  <input
                    v-model="form.hostPassword"
                    class="field-input"
                    :type="showPassword ? 'text' : 'password'"
                    :placeholder="editId ? '留空则不重新配置 SSH' : '用于首次登录并自动部署密钥'"
                    :disabled="saving"
                  />
                  <button type="button" class="pwd-toggle" @click="showPassword = !showPassword">
                    {{ showPassword ? '隐藏' : '显示' }}
                  </button>
                </div>
                <p class="form-hint" v-if="editId && editAuthConfigured">当前 SSH 密钥已配置，填写密码可重新自动化部署</p>
              </div>
            </div>
          </section>

          <section class="form-section" v-if="provisionSteps.length || saving">
            <div class="section-title"><span class="section-index auto">03</span>自动化配置</div>
            <ProvisionPipeline :steps="provisionSteps" :loading="saving" />
          </section>

          <section class="form-section">
            <div class="section-title"><span class="section-index extra">04</span>附加信息</div>
            <div class="form-group">
              <label>描述</label>
              <input v-model="form.description" class="field-input" placeholder="可选描述" :disabled="saving" />
            </div>
            <div class="form-group">
              <label>标签（逗号分隔）</label>
              <input
                :value="tagsInput"
                class="field-input"
                placeholder="如：web, db, prod"
                :disabled="saving"
                @input="emit('update:tagsInput', ($event.target as HTMLInputElement).value)"
              />
            </div>
            <label class="form-check">
              <input type="checkbox" v-model="form.isDefault" :disabled="saving" />
              <span>设为默认服务器</span>
            </label>
          </section>
        </div>

        <div class="dialog-actions">
          <button type="button" class="tech-btn" @click="emit('close')" :disabled="saving">取消</button>
          <button type="button" class="tech-btn primary save-btn" @click="emit('save')" :disabled="!canSave || saving">
            <span v-if="saving" class="btn-spinner"></span>
            {{ saving ? '配置中…' : (editId ? '保存并配置' : '添加并自动配置') }}
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { ProvisionStep } from '@/api/servers'
import ConnectivityDiagnosis from './ConnectivityDiagnosis.vue'
import ProvisionPipeline from './ProvisionPipeline.vue'

export interface ServerFormModel {
  name: string
  host: string
  port: number
  username: string
  hostPassword: string
  description: string
  isDefault: boolean
}

defineProps<{
  visible: boolean
  editId: string | null
  form: ServerFormModel
  tagsInput: string
  saving: boolean
  canSave: boolean
  defaultUsername: string
  editAuthConfigured: boolean
  reachChecking: boolean
  reachMessage: string
  reachOk: boolean
  reachSuggestions: string[]
  reachDiagnosis: { localIp?: string; sameSubnet?: boolean } | null
  suggestedHost: string
  duplicateName?: string
  provisionSteps: ProvisionStep[]
}>()

const emit = defineEmits<{
  close: []
  save: []
  checkReachable: []
  applySuggestedHost: []
  editDuplicate: []
  'update:tagsInput': [value: string]
}>()

const showPassword = ref(false)
</script>

<style lang="scss" scoped>
.modal-fade-enter-active, .modal-fade-leave-active { transition: opacity 0.25s; }
.modal-fade-enter-from, .modal-fade-leave-to { opacity: 0; }

.dialog-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.55);
  backdrop-filter: blur(8px);
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.dialog-card {
  width: min(580px, 96vw);
  max-height: 90vh;
  overflow: hidden;
  border-radius: 16px;
  border-color: rgba(186, 230, 253, 0.8) !important;
  box-shadow: 0 24px 80px rgba(15, 23, 42, 0.22);
  display: flex;
  flex-direction: column;
  animation: dialog-in 0.3s cubic-bezier(0.34, 1.4, 0.64, 1);
  padding: 0 !important;
  background: rgba(255, 255, 255, 0.98) !important;

  &.saving { pointer-events: none; opacity: 0.96; }
}

@keyframes dialog-in {
  from { opacity: 0; transform: scale(0.94) translateY(10px); }
  to { opacity: 1; transform: none; }
}

.dialog-header {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 20px 22px;
  background: linear-gradient(135deg, #1e3a8a 0%, #4338ca 55%, #6366f1 100%);
  color: #fff;

  h3 { font-size: 18px; font-weight: 700; margin: 0; }
}

.dialog-sub {
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  font-size: 10px;
  letter-spacing: 0.06em;
  opacity: 0.85;
  margin: 4px 0 0;
}

.dialog-header-icon {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.2);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.dialog-close {
  margin-left: auto;
  width: 32px;
  height: 32px;
  border: none;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.12);
  color: #fff;
  font-size: 22px;
  cursor: pointer;
  transition: background 0.15s;
  &:hover:not(:disabled) { background: rgba(239, 68, 68, 0.5); }
  &:disabled { opacity: 0.5; cursor: not-allowed; }
}

.dialog-body { padding: 18px 22px; overflow-y: auto; flex: 1; }

.form-section { margin-bottom: 18px; }

.section-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 12px;
  font-weight: 700;
  color: #334155;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #f1f5f9;
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  letter-spacing: 0.02em;
}

.section-index {
  font-size: 10px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 4px;
  background: #eff6ff;
  color: #2563eb;
  border: 1px solid #bfdbfe;
  &.network { background: #ecfdf5; color: #047857; border-color: #a7f3d0; }
  &.auto { background: #f5f3ff; color: #7c3aed; border-color: #ddd6fe; }
  &.extra { background: #fffbeb; color: #b45309; border-color: #fde68a; }
}

.form-group { margin-bottom: 12px; flex: 1; }
.form-row { display: flex; gap: 12px; }
.flex-3 { flex: 3; }
.flex-1 { flex: 1; }

label {
  display: block;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  margin-bottom: 6px;
}

.req { color: #ef4444; }

.field-input {
  width: 100%;
  padding: 10px 12px;
  border: 1.5px solid #e2e8f0;
  border-radius: 10px;
  font-size: 13px;
  color: #1e293b;
  outline: none;
  box-sizing: border-box;
  transition: all 0.15s;
  background: #fff;
  &:focus {
    border-color: #6366f1;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.12);
  }
  &:disabled { background: #f8fafc; color: #94a3b8; }
  &.mono { font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', sans-serif; font-size: 12px; }
}

.input-with-action {
  display: flex;
  gap: 8px;
  .field-input { flex: 1; }
}

.inline-btn {
  white-space: nowrap;
  font-size: 12px;
  &.pulsing { animation: pulse-border 1s ease infinite; }
}

@keyframes pulse-border {
  0%, 100% { box-shadow: 0 0 0 0 rgba(99, 102, 241, 0.3); }
  50% { box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.15); }
}

.password-wrap {
  position: relative;
  .field-input { padding-right: 52px; }
}

.pwd-toggle {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  border: none;
  background: none;
  cursor: pointer;
  font-size: 11px;
  color: #6366f1;
  font-weight: 600;
  padding: 4px;
}

.form-hint { font-size: 11px; color: #94a3b8; margin-top: 4px; line-height: 1.4; }

.form-warn {
  font-size: 11px;
  color: #b45309;
  margin-top: 8px;
  padding: 8px 10px;
  background: #fffbeb;
  border: 1px solid #fde68a;
  border-radius: 8px;
}

.link-btn {
  margin-left: 4px;
  padding: 0;
  border: none;
  background: none;
  color: #2563eb;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  text-decoration: underline;
}

.form-check {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font-size: 13px;
  color: #334155;
  input { accent-color: #6366f1; width: 16px; height: 16px; }
}

.dialog-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  padding: 16px 22px;
  border-top: 1px solid #f1f5f9;
  background: rgba(248, 250, 252, 0.9);
}

.save-btn {
  background: linear-gradient(135deg, #2563eb, #6366f1) !important;
  border: none !important;
  color: #fff !important;
  box-shadow: 0 4px 14px rgba(99, 102, 241, 0.35);
  &:disabled { background: #94a3b8 !important; box-shadow: none; }
}

.btn-spinner {
  width: 14px;
  height: 14px;
  margin-right: 6px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
  display: inline-block;
}

@keyframes spin { to { transform: rotate(360deg); } }
</style>
