<template>
  <div class="admin-page">
    <AdminPageBackground />

    <div class="admin-content">
      <AdminPageHeader />

      <AdminGearHub v-model:active-key="activeTab" :modules="gearModules">
        <section class="tab-panel">
      <!-- ==================== 用户管理 ==================== -->
      <div v-show="activeTab === 'users'" class="tab-content">
        <AdminModulePanel
          description="创建与维护系统登录账号，分配管理员或普通用户角色，支持重置密码。内置 <code>admin</code> 账号受保护不可删除。"
          :features="userFeatures"
        >
        <div class="toolbar">
          <div class="toolbar-left">
            <el-input v-model="userSearch" placeholder="搜索用户名…" clearable class="search-input" />
            <div class="filter-chips">
              <button type="button" class="chip" :class="{ active: userRoleFilter === 'all' }" @click="userRoleFilter = 'all'">全部 {{ users.length }}</button>
              <button type="button" class="chip" :class="{ active: userRoleFilter === 'admin' }" @click="userRoleFilter = 'admin'">管理员 {{ adminCount }}</button>
              <button type="button" class="chip" :class="{ active: userRoleFilter === 'user' }" @click="userRoleFilter = 'user'">普通用户 {{ userCount }}</button>
            </div>
          </div>
          <button type="button" class="primary-btn" @click="showUserDialog = true">+ 添加用户</button>
        </div>
        <div class="data-card">
          <el-table :data="filteredUsers" stripe empty-text="暂无匹配用户">
            <el-table-column label="用户" min-width="160">
              <template #default="{ row }">
                <div class="user-cell">
                  <span class="user-avatar">{{ row.username.charAt(0).toUpperCase() }}</span>
                  <div>
                    <strong>{{ row.username }}</strong>
                    <span v-if="row.username === 'admin'" class="builtin-tag">内置</span>
                  </div>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="角色" width="120">
              <template #default="{ row }">
                <span class="role-pill" :class="row.role">{{ roleMap[row.role] || row.role }}</span>
              </template>
            </el-table-column>
            <el-table-column label="用户 ID" width="140">
              <template #default="{ row }">
                <button type="button" class="id-copy" :title="row.id" @click="copyText(row.id)">
                  {{ shortId(row.id) }}
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none"><rect x="9" y="9" width="13" height="13" rx="2" stroke="currentColor" stroke-width="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1" stroke="currentColor" stroke-width="2"/></svg>
                </button>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="64" align="center" fixed="right">
              <template #default="{ row }">
                <el-dropdown trigger="click" @command="(cmd: string) => handleUserAction(cmd, row)">
                  <button type="button" class="more-btn" @click.stop><el-icon><MoreFilled /></el-icon></button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="edit">编辑角色 / 密码</el-dropdown-item>
                      <el-dropdown-item command="reset">重置密码</el-dropdown-item>
                      <el-dropdown-item command="delete" divided :disabled="row.username === 'admin'">
                        <span :class="{ 'danger-text': row.username !== 'admin' }">删除用户</span>
                      </el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
            </el-table-column>
          </el-table>
        </div>
        </AdminModulePanel>
      </div>

      <!-- ==================== 工具管理 ==================== -->
      <div v-show="activeTab === 'tools'" class="tab-content">
        <AdminModulePanel
          description="维护 Agent 可调用的运维工具清单。通过<strong>风险级别</strong>与<strong>启用开关</strong>控制哪些能力对智能对话开放，可从预设批量导入常用工具。"
          :features="toolFeatures"
        >
        <div class="toolbar">
          <div class="toolbar-left">
            <el-input v-model="toolSearch" placeholder="搜索工具名称或描述…" clearable class="search-input" />
            <div class="filter-chips">
              <button type="button" class="chip" :class="{ active: toolCategoryFilter === '' }" @click="toolCategoryFilter = ''">全部 {{ tools.length }}</button>
              <button type="button" class="chip" :class="{ active: toolCategoryFilter === '__enabled' }" @click="toolCategoryFilter = '__enabled'">已启用 {{ enabledToolCount }}</button>
              <button type="button" class="chip warn" :class="{ active: toolCategoryFilter === '__highrisk' }" @click="toolCategoryFilter = '__highrisk'">高风险 {{ highRiskToolCount }}</button>
            </div>
          </div>
          <div class="toolbar-right">
            <button type="button" class="ghost-btn" @click="loadPresetTools">从预设导入</button>
            <button type="button" class="primary-btn" @click="openAddToolDialog">+ 添加工具</button>
          </div>
        </div>
        <div class="data-card">
          <el-table :data="filteredTools" stripe empty-text="暂无匹配工具">
            <el-table-column label="工具名称" width="220">
              <template #default="{ row }">
                <code class="tool-name">{{ row.name }}</code>
                <span v-if="row.builtin" class="builtin-tag">内置</span>
              </template>
            </el-table-column>
            <el-table-column prop="description" label="功能描述" min-width="200" show-overflow-tooltip />
            <el-table-column label="分类" width="110">
              <template #default="{ row }">
                <span class="cat-pill">{{ categoryLabel(row.category) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="风险" width="80" align="center">
              <template #default="{ row }">
                <span class="risk-pill" :class="riskClass(row.riskLevel)">L{{ row.riskLevel }}</span>
              </template>
            </el-table-column>
            <el-table-column label="启用" width="72" align="center">
              <template #default="{ row }">
                <el-switch :model-value="row.enabled" active-color="#2563eb" @change="onToggleTool($event, row)" />
              </template>
            </el-table-column>
            <el-table-column label="操作" width="64" align="center" fixed="right">
              <template #default="{ row }">
                <el-dropdown trigger="click" @command="(cmd: string) => handleToolAction(cmd, row)">
                  <button type="button" class="more-btn" @click.stop><el-icon><MoreFilled /></el-icon></button>
                    <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="edit" :disabled="row.builtin">编辑工具</el-dropdown-item>
                      <el-dropdown-item command="toggle">{{ row.enabled ? '禁用' : '启用' }}</el-dropdown-item>
                      <el-dropdown-item v-if="!row.builtin" command="delete" divided><span class="danger-text">删除</span></el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
            </el-table-column>
          </el-table>
        </div>
        </AdminModulePanel>
      </div>

      <!-- ==================== 安全配置 ==================== -->
      <div v-show="activeTab === 'security'" class="tab-content">
        <AdminModulePanel
          description="配置 LLM 接入参数与系统安全策略，修改后将影响全局智能对话的模型行为、审批超时与对话轮次上限。"
          :features="securityFeatures"
        >
        <AdminSecurityConfigStage
          :llm="config.llm"
          :security="config.security"
          :saving="savingConfig"
          :high-risk-tools="highRiskToolCount"
          @save="saveConfig"
        />
        </AdminModulePanel>
      </div>

      <!-- ==================== 知识库 ==================== -->
      <div v-show="activeTab === 'knowledge'" class="tab-content">
        <AdminModulePanel
          description="维护运维知识文章，供用户浏览与 Agent RAG 检索引用。修改文章后建议重建索引以确保对话检索最新内容。"
          :features="knowledgeFeatures"
        >
        <div class="toolbar">
          <div class="toolbar-left">
            <el-input v-model="articleSearch" placeholder="搜索标题或内容…" clearable class="search-input" />
            <div class="filter-chips">
              <button type="button" class="chip" :class="{ active: articleSeverityFilter === '' }" @click="articleSeverityFilter = ''">全部 {{ articleTotal }}</button>
              <button type="button" class="chip critical" :class="{ active: articleSeverityFilter === 'critical' }" @click="articleSeverityFilter = 'critical'">严重</button>
              <button type="button" class="chip warn" :class="{ active: articleSeverityFilter === 'warning' }" @click="articleSeverityFilter = 'warning'">警告</button>
              <button type="button" class="chip" :class="{ active: articleSeverityFilter === 'info' }" @click="articleSeverityFilter = 'info'">一般</button>
            </div>
          </div>
          <div class="toolbar-right">
            <button type="button" class="ghost-btn" :disabled="reindexing" @click="handleReindex">
              {{ reindexing ? '重建中…' : '重建索引' }}
            </button>
            <button type="button" class="primary-btn" @click="openAddArticleDialog">+ 添加文章</button>
          </div>
        </div>
        <div class="data-card">
          <p v-if="articles.length < articleTotal" class="article-load-hint">
            列表已加载 {{ articles.length }} / {{ articleTotal }} 篇（管理列表上限 1000，数量统计与知识库页同步）
          </p>
          <el-table :data="filteredArticles" stripe empty-text="暂无匹配文章">
            <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
            <el-table-column prop="category" label="分类" width="100" />
            <el-table-column label="级别" width="88">
              <template #default="{ row }">
                <span class="sev-pill" :class="row.severity">{{ severityLabel(row.severity) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="阅读" width="72" align="center">
              <template #default="{ row }">{{ row.viewCount ?? row.view_count ?? 0 }}</template>
            </el-table-column>
            <el-table-column label="操作" width="64" align="center" fixed="right">
              <template #default="{ row }">
                <el-dropdown trigger="click" @command="(cmd: string) => handleArticleAction(cmd, row)">
                  <button type="button" class="more-btn" @click.stop><el-icon><MoreFilled /></el-icon></button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <el-dropdown-item command="edit">编辑文章</el-dropdown-item>
                      <el-dropdown-item command="delete" divided><span class="danger-text">删除</span></el-dropdown-item>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
              </template>
            </el-table-column>
          </el-table>
        </div>
        </AdminModulePanel>
      </div>
    </section>
      </AdminGearHub>
    </div>

    <!-- 用户对话框 -->
    <AdminTechDialog
      v-model="showUserDialog"
      title="添加用户"
      subtitle="CREATE ACCOUNT · 新建系统登录账号"
      code="ACT-NEW"
      module-key="users"
      accent-color="#2563eb"
      confirm-text="创建"
      :loading="userCreating"
      loading-text="创建中…"
      @confirm="handleCreateUser"
    >
      <AdminTechField label="用户名" code="FLD-01" hint="用于登录系统的唯一标识，创建后不可修改" required>
        <el-input v-model="newUser.username" placeholder="登录用户名" />
      </AdminTechField>
      <AdminTechField label="密码" code="FLD-02" hint="初始登录密码，建议包含字母与数字" required tag="SECRET">
        <el-input v-model="newUser.password" type="password" show-password placeholder="初始密码" />
      </AdminTechField>
      <AdminTechField label="角色" code="FLD-03" hint="决定该账号可访问的管理功能范围" required tag="RBAC">
        <AdminTechCardPicker v-model="newUser.role" :options="rolePickerOptions" :columns="2" aria-label="用户角色" />
      </AdminTechField>
    </AdminTechDialog>

    <AdminTechDialog
      v-model="showEditUserDialog"
      title="编辑用户"
      subtitle="UPDATE ACCOUNT · 修改角色或密码"
      code="ACT-EDT"
      module-key="users"
      accent-color="#2563eb"
      confirm-text="保存"
      @confirm="handleUpdateUser"
    >
      <AdminTechField label="用户名" code="FLD-01" hint="用户名不可修改" tag="READONLY">
        <el-input :model-value="editUser.username" disabled />
      </AdminTechField>
      <AdminTechField label="角色" code="FLD-02" hint="admin 内置账号角色不可变更" tag="RBAC">
        <AdminTechCardPicker
          v-model="editUser.role"
          :options="rolePickerOptions"
          :columns="2"
          :disabled="editUser.username === 'admin'"
          aria-label="用户角色"
        />
      </AdminTechField>
      <AdminTechField label="新密码" code="FLD-03" hint="留空则不修改当前密码" tag="SECRET">
        <el-input v-model="editUser.password" type="password" show-password placeholder="留空则不修改" />
      </AdminTechField>
    </AdminTechDialog>

    <!-- 工具对话框 -->
    <AdminTechDialog
      v-model="showToolDialog"
      :title="isEditTool ? '编辑工具' : '添加工具'"
      :subtitle="isEditTool ? 'UPDATE TOOL · 修改 Agent 工具配置' : 'REGISTER TOOL · 注册 Agent 可调用工具'"
      code="TL-REG"
      module-key="tools"
      accent-color="#7c3aed"
      :confirm-text="isEditTool ? '保存' : '添加'"
      :loading="toolSaving"
      loading-text="保存中…"
      :confirm-disabled="toolConfirmDisabled"
      width="min(620px, 96vw)"
      @confirm="handleSaveTool"
    >
      <AdminToolFileDropzone
        v-if="!isEditTool"
        :reset-key="toolFileResetKey"
        @validated="onToolFileValidated"
        @cleared="onToolFileCleared"
      />
      <AdminTechField label="工具名称" code="FLD-01" hint="唯一标识符，如 get_disk_usage；拖拽文件时将自动填入文件名" required tag="API ID">
        <el-input v-model="currentTool.name" :disabled="isEditTool" placeholder="如 get_disk_usage" />
      </AdminTechField>
      <AdminTechField label="功能描述" code="FLD-02" hint="Agent 理解该工具用途的自然语言说明" required>
        <el-input v-model="currentTool.description" type="textarea" :rows="2" placeholder="描述工具功能…" />
      </AdminTechField>
      <AdminTechField label="分类" code="FLD-03" hint="工具所属运维领域，便于筛选管理" tag="CATEGORY">
        <AdminTechCardPicker
          v-model="currentTool.category"
          :options="categoryPickerOptions"
          :columns="3"
          aria-label="工具分类"
        />
      </AdminTechField>
      <AdminTechField label="风险级别" code="FLD-04" hint="L3 及以上执行前需用户审批" tag="RISK">
        <AdminTechCardPicker
          v-model="currentTool.riskLevel"
          :options="riskPickerOptions"
          :columns="5"
          aria-label="工具风险级别"
        />
      </AdminTechField>
      <AdminTechField label="参数配置 (JSON)" code="FLD-05" hint="工具运行时参数，JSON 格式" tag="CONFIG">
        <el-input v-model="currentTool.configStr" type="textarea" :rows="3" placeholder='{"timeout": 30}' />
      </AdminTechField>
      <AdminTechField label="启用状态" code="FLD-06" hint="关闭后 Agent 将无法调用此工具" tag="SWITCH">
        <el-switch v-model="currentTool.enabled" active-color="#7c3aed" />
      </AdminTechField>
    </AdminTechDialog>

    <AdminTechDialog
      v-model="showPresetDialog"
      title="从预设导入工具"
      subtitle="BATCH IMPORT · 批量注册常用运维工具"
      code="TL-BATCH"
      module-key="tools"
      accent-color="#7c3aed"
      :confirm-text="`导入选中 (${selectedPresetCount})`"
      :loading="importing"
      loading-text="导入中…"
      :confirm-disabled="!selectedPresetCount"
      width="min(720px, 96vw)"
      @confirm="importPresetTools"
    >
      <div class="preset-toolbar">
        <button type="button" class="ghost-btn sm" @click="selectAllPresets(true)">全选</button>
        <button type="button" class="ghost-btn sm" @click="selectAllPresets(false)">取消全选</button>
        <span class="preset-count">已选 {{ selectedPresetCount }} / {{ presetTools.length }}</span>
      </div>
      <div class="preset-tool-list">
        <label v-for="tool in presetTools" :key="tool.name" class="preset-tool-item">
          <input type="checkbox" v-model="tool.selected" />
          <div class="preset-body">
            <code class="preset-tool-name">{{ tool.name }}</code>
            <span class="preset-tool-desc">{{ tool.description }}</span>
            <span class="risk-pill sm" :class="riskClass(tool.riskLevel)">L{{ tool.riskLevel }}</span>
          </div>
        </label>
      </div>
    </AdminTechDialog>

    <!-- 知识库对话框 -->
    <AdminTechDialog
      v-model="showArticleDialog"
      title="添加文章"
      subtitle="CREATE ARTICLE · 新建运维知识条目"
      code="KB-NEW"
      module-key="knowledge"
      accent-color="#d97706"
      :confirm-text="articleBatchMode ? `批量导入 (${articleBatchCount})` : '创建'"
      :loading="articleCreating"
      loading-text="保存中…"
      :confirm-disabled="articleConfirmDisabled"
      width="min(620px, 96vw)"
      @confirm="handleCreateArticle"
    >
      <AdminTechField label="文件导入" code="FILE-01" hint="拖拽 .md / .json / .txt，自动解析并填充下方表单；多篇 Markdown 可批量导入" tag="IMPORT">
        <AdminArticleFileDropzone
          :reset-key="articleFileResetKey"
          @validated="onArticleFileValidated"
          @cleared="onArticleFileCleared"
        />
      </AdminTechField>
      <div v-if="articleBatchMode" class="batch-hint">
        已从文件解析 <strong>{{ articleBatchCount }}</strong> 篇文章，点击下方按钮将跳过已存在标题并批量导入。
      </div>
      <AdminTechField v-if="!articleBatchMode" label="标题" code="FLD-01" hint="文章主题，供用户浏览与 RAG 检索；拖拽文件时将自动填入" required>
        <el-input v-model="newArticle.title" placeholder="文章标题" />
      </AdminTechField>
      <AdminTechField v-if="!articleBatchMode" label="分类" code="FLD-02" hint="知识领域分类，如故障排查、性能优化" tag="CATEGORY">
        <el-input v-model="newArticle.category" placeholder="如：故障排查" />
      </AdminTechField>
      <AdminTechField v-if="!articleBatchMode" label="标签" code="FLD-03" hint="逗号分隔，提升检索命中率" tag="TAGS">
        <el-input v-model="newArticle.tags" placeholder="逗号分隔，如：磁盘,性能" />
      </AdminTechField>
      <AdminTechField v-if="!articleBatchMode" label="级别" code="FLD-04" hint="标识文章重要程度，影响展示优先级" tag="SEVERITY">
        <AdminSeverityPicker v-model="newArticle.severity" />
      </AdminTechField>
      <AdminTechField v-if="!articleBatchMode" label="内容" code="FLD-05" hint="正文内容，Agent RAG 将引用此文本" required tag="BODY">
        <el-input v-model="newArticle.content" type="textarea" :rows="6" placeholder="文章正文…" />
      </AdminTechField>
    </AdminTechDialog>

    <AdminTechDialog
      v-model="showEditArticleDialog"
      title="编辑文章"
      subtitle="UPDATE ARTICLE · 修改知识库条目"
      code="KB-EDT"
      module-key="knowledge"
      accent-color="#d97706"
      confirm-text="保存"
      width="min(620px, 96vw)"
      @confirm="handleUpdateArticle"
    >
      <AdminTechField label="标题" code="FLD-01" required>
        <el-input v-model="editArticle.title" />
      </AdminTechField>
      <AdminTechField label="分类" code="FLD-02" tag="CATEGORY">
        <el-input v-model="editArticle.category" />
      </AdminTechField>
      <AdminTechField label="标签" code="FLD-03" hint="逗号分隔" tag="TAGS">
        <el-input v-model="editArticle.tags" placeholder="逗号分隔" />
      </AdminTechField>
      <AdminTechField label="级别" code="FLD-04" hint="标识文章重要程度，影响展示优先级" tag="SEVERITY">
        <AdminSeverityPicker v-model="editArticle.severity" />
      </AdminTechField>
      <AdminTechField label="内容" code="FLD-05" required tag="BODY">
        <el-input v-model="editArticle.content" type="textarea" :rows="6" />
      </AdminTechField>
    </AdminTechDialog>

    <!-- 删除确认 -->
    <AdminConfirmDialog
      v-model="deleteDialog.visible"
      :title="deleteDialog.title"
      :subtitle="deleteDialog.subtitle"
      :message="deleteDialog.message"
      :item-title="deleteDialog.itemTitle"
      :item-meta="deleteDialog.itemMeta"
      :item-tag="deleteDialog.itemTag"
      :module-key="deleteDialog.moduleKey"
      :code="deleteDialog.code"
      :loading="deleteDialog.loading"
      @confirm="confirmDelete"
      @cancel="deleteDialog.visible = false"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { MoreFilled } from '@element-plus/icons-vue'
import { getUsers, createUser, updateUser, deleteUser, resetPassword } from '@/api/users'
import { getTools, addTool, updateTool, deleteTool, toggleTool } from '@/api/tools'
import type { ToolFileValidation } from '@/api/tools'
import { getConfig, updateConfig } from '@/api/system'
import api from '@/api/index'
import type { UserInfo } from '@/api/users'
import type { ToolInfo } from '@/api/tools'
import AdminPageBackground from '@/components/admin/AdminPageBackground.vue'
import AdminPageHeader from '@/components/admin/AdminPageHeader.vue'
import AdminGearHub from '@/components/admin/AdminGearHub.vue'
import AdminModulePanel from '@/components/admin/AdminModulePanel.vue'
import AdminTechDialog from '@/components/admin/AdminTechDialog.vue'
import AdminConfirmDialog from '@/components/admin/AdminConfirmDialog.vue'
import AdminTechField from '@/components/admin/AdminTechField.vue'
import AdminSeverityPicker from '@/components/admin/AdminSeverityPicker.vue'
import type { ArticleSeverity } from '@/components/admin/AdminSeverityPicker.vue'
import AdminTechCardPicker from '@/components/admin/AdminTechCardPicker.vue'
import AdminToolFileDropzone from '@/components/admin/AdminToolFileDropzone.vue'
import AdminArticleFileDropzone from '@/components/admin/AdminArticleFileDropzone.vue'
import AdminSecurityConfigStage from '@/components/admin/AdminSecurityConfigStage.vue'
import { importArticlesBatch, createArticle, type ArticleFileValidation } from '@/api/knowledge'
import type { TechCardOption } from '@/components/admin/AdminTechCardPicker.vue'
import type { AdminGearKey } from '@/components/admin/gearPaths'

const activeTab = ref<AdminGearKey>('users')
const roleMap: Record<string, string> = { admin: '管理员', user: '普通用户' }

const userFeatures = [
  { label: '搜索', text: '按用户名或 ID 快速定位账号' },
  { label: '角色筛选', text: '全部 / 管理员 / 普通用户' },
  { label: '操作', text: '添加、编辑角色、重置密码、删除' },
]
const toolFeatures = [
  { label: '风险分级', text: 'L1 只读至 L4 高危，L3+ 需审批' },
  { label: '启用开关', text: '控制 Agent 是否可调用该工具' },
  { label: '预设导入', text: '批量添加常用运维工具' },
]
const securityFeatures = [
  { label: 'LLM 参数', text: 'API 地址、模型、温度与 Token 上限' },
  { label: '安全策略', text: '审批超时与最大对话轮次' },
  { label: '保存生效', text: '修改后需点击保存才会应用' },
]
const knowledgeFeatures = [
  { label: '文章 CRUD', text: '标题、分类、标签、级别与正文' },
  { label: '级别筛选', text: '一般 / 警告 / 严重' },
  { label: '重建索引', text: '同步 RAG 向量检索库' },
]

const CATEGORY_LABELS: Record<string, string> = {
  system_monitor: '系统监控',
  process_management: '进程管理',
  service_management: '服务管理',
  file_management: '文件管理',
  network_management: '网络管理',
  log_management: '日志查询',
  system_operation: '系统操作',
}

const CATEGORY_META: Record<string, { code: string; desc: string; icon: string }> = {
  system_monitor: { code: 'MON', desc: '系统状态与资源', icon: 'monitor' },
  process_management: { code: 'PRC', desc: '进程查询与终止', icon: 'process' },
  service_management: { code: 'SVC', desc: '服务启停与重载', icon: 'service' },
  file_management: { code: 'FIL', desc: '文件浏览与读取', icon: 'file' },
  network_management: { code: 'NET', desc: '连接与端口查询', icon: 'network' },
  log_management: { code: 'LOG', desc: '日志检索分析', icon: 'log' },
  system_operation: { code: 'OPS', desc: '命令与用户操作', icon: 'operation' },
}

const rolePickerOptions: TechCardOption[] = [
  { value: 'admin', code: 'ADM', label: '管理员', desc: '工作台与全部管理功能', tone: 'admin', icon: 'admin' },
  { value: 'user', code: 'USR', label: '普通用户', desc: '对话、审批与知识库', tone: 'user', icon: 'user' },
]

const categoryPickerOptions = computed<TechCardOption[]>(() =>
  Object.entries(CATEGORY_LABELS).map(([key, label]) => {
    const meta = CATEGORY_META[key]
    return {
      value: key,
      code: meta?.code ?? key.slice(0, 3).toUpperCase(),
      label,
      desc: meta?.desc ?? label,
      tone: 'cat',
      icon: meta?.icon ?? 'operation',
    }
  }),
)

const riskPickerOptions: TechCardOption[] = [
  { value: 1, code: 'L1', label: '只读查询', desc: '无风险只读操作', tone: 'risk-l1', icon: 'risk1' },
  { value: 2, code: 'L2', label: '轻量操作', desc: '低风险变更操作', tone: 'risk-l2', icon: 'risk2' },
  { value: 3, code: 'L3', label: '需审批', desc: '执行前需用户确认', tone: 'risk-l3', icon: 'risk3' },
  { value: 4, code: 'L4', label: '高风险', desc: '可能影响系统稳定', tone: 'risk-l4', icon: 'risk4' },
  { value: 5, code: 'L5', label: '极高风险', desc: '命令执行等高危', tone: 'risk-l5', icon: 'risk5' },
]

const gearModules = computed(() => [
  {
    key: 'users' as const,
    code: 'MOD-USR',
    label: '用户管理',
    desc: '账号创建、角色分配与密码重置',
    stat: `${users.value.length} 个账号`,
    color: '#2563eb',
    glow: '#2563eb',
  },
  {
    key: 'tools' as const,
    code: 'MOD-TL',
    label: '工具管理',
    desc: 'Agent 工具清单与风险管控',
    stat: `${enabledToolCount.value}/${tools.value.length} 已启用`,
    color: '#7c3aed',
    glow: '#7c3aed',
  },
  {
    key: 'security' as const,
    code: 'MOD-SEC',
    label: '安全配置',
    desc: 'LLM 接入与安全策略参数',
    stat: config.llm.model || '未配置模型',
    color: '#059669',
    glow: '#059669',
  },
  {
    key: 'knowledge' as const,
    code: 'MOD-KB',
    label: '知识库',
    desc: '运维文章维护与 RAG 索引',
    stat: `${articleTotal.value} 篇文章`,
    color: '#d97706',
    glow: '#d97706',
  },
])

// ========== 用户管理 ==========
const users = ref<UserInfo[]>([])
const userSearch = ref('')
const userRoleFilter = ref<'all' | 'admin' | 'user'>('all')
const showUserDialog = ref(false)
const showEditUserDialog = ref(false)
const userCreating = ref(false)
const newUser = reactive({ username: '', password: '', role: 'user' })
const editUser = reactive({ id: '', username: '', role: '', password: '' })

const adminCount = computed(() => users.value.filter(u => u.role === 'admin').length)
const userCount = computed(() => users.value.filter(u => u.role === 'user').length)
const filteredUsers = computed(() => {
  let list = users.value
  if (userRoleFilter.value !== 'all') list = list.filter(u => u.role === userRoleFilter.value)
  const q = userSearch.value.trim().toLowerCase()
  if (q) list = list.filter(u => u.username.toLowerCase().includes(q) || u.id.includes(q))
  return list
})

// ========== 工具管理 ==========
const tools = ref<ToolInfo[]>([])
const toolSearch = ref('')
const toolCategoryFilter = ref('')
const showToolDialog = ref(false)
const showPresetDialog = ref(false)
const isEditTool = ref(false)
const toolSaving = ref(false)
const toolFileFromUpload = ref(false)
const toolFilePassed = ref(false)
const toolFileResetKey = ref(0)
const importing = ref(false)
const currentTool = reactive({ id: '', name: '', description: '', category: '', riskLevel: 1, enabled: true, configStr: '' })
const presetTools = ref<any[]>([])

const toolConfirmDisabled = computed(() => {
  if (isEditTool.value) return false
  if (!toolFileFromUpload.value) return false
  return !toolFilePassed.value
})

const enabledToolCount = computed(() => tools.value.filter(t => t.enabled).length)
const highRiskToolCount = computed(() => tools.value.filter(t => t.riskLevel >= 3).length)
const selectedPresetCount = computed(() => presetTools.value.filter(t => t.selected).length)

const filteredTools = computed(() => {
  let list = tools.value
  if (toolCategoryFilter.value === '__enabled') list = list.filter(t => t.enabled)
  else if (toolCategoryFilter.value === '__highrisk') list = list.filter(t => t.riskLevel >= 3)
  const q = toolSearch.value.trim().toLowerCase()
  if (q) list = list.filter(t => t.name.toLowerCase().includes(q) || t.description.toLowerCase().includes(q))
  return list
})

const PRESET_TOOLS = [
  { name: 'get_system_info', description: '获取系统概览信息', category: 'system_monitor', riskLevel: 1 },
  { name: 'get_disk_usage', description: '查询磁盘挂载和使用情况', category: 'system_monitor', riskLevel: 1 },
  { name: 'get_cpu_info', description: '获取CPU使用率、核心数、负载等信息', category: 'system_monitor', riskLevel: 1 },
  { name: 'get_memory_info', description: '获取内存和交换区使用情况', category: 'system_monitor', riskLevel: 1 },
  { name: 'list_processes', description: '获取进程列表，可按CPU或内存排序', category: 'process_management', riskLevel: 1 },
  { name: 'get_process_detail', description: '获取指定进程的详细信息', category: 'process_management', riskLevel: 1 },
  { name: 'kill_process', description: '终止指定进程，默认发送TERM信号', category: 'process_management', riskLevel: 3 },
  { name: 'get_network_connections', description: '查询网络连接状态和监听端口', category: 'network_management', riskLevel: 1 },
  { name: 'get_network_speed', description: '采样计算网卡实时收发速率（KB/s、Mbps），并给出网速好坏评价', category: 'network_management', riskLevel: 1 },
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

// ========== 安全配置 ==========
const config = reactive({
  llm: { apiBase: '', model: '', apiKey: '', apiKeySet: false, temperature: 0.1, maxTokens: 4096 },
  security: { approvalTimeout: 60, maxRounds: 20 },
})
const savingConfig = ref(false)

// ========== 知识库 ==========
const articles = ref<any[]>([])
const articleTotal = ref(0)
const articleSearch = ref('')
const articleSeverityFilter = ref('')
const showArticleDialog = ref(false)
const showEditArticleDialog = ref(false)
const reindexing = ref(false)
const articleCreating = ref(false)
const articleFileFromUpload = ref(false)
const articleFilePassed = ref(false)
const articleFileResetKey = ref(0)
const articleBatchMode = ref(false)
const articleBatchCount = ref(0)
const articleBatchItems = ref<ArticleFileValidation['articles']>([])

const articleConfirmDisabled = computed(() => {
  if (!articleFileFromUpload.value) return false
  return !articleFilePassed.value
})

type DeleteKind = 'user' | 'tool' | 'article'
const deleteDialog = reactive({
  visible: false,
  loading: false,
  kind: 'user' as DeleteKind,
  target: null as any,
  title: '确认删除',
  subtitle: 'DESTRUCTIVE ACTION · 不可逆操作',
  message: '',
  itemTitle: '',
  itemMeta: '',
  itemTag: '',
  moduleKey: 'users' as AdminGearKey,
  code: 'ACT-DEL',
})

function openDeleteDialog(kind: DeleteKind, row: any) {
  deleteDialog.kind = kind
  deleteDialog.target = row
  deleteDialog.loading = false

  if (kind === 'user') {
    deleteDialog.title = '确认删除用户'
    deleteDialog.message = '确定要删除以下用户账号吗？该账号将无法再登录系统。'
    deleteDialog.itemTitle = row.username
    deleteDialog.itemMeta = `角色：${roleMap[row.role] || row.role}`
    deleteDialog.itemTag = 'USER'
    deleteDialog.moduleKey = 'users'
    deleteDialog.code = 'USR-DEL'
  } else if (kind === 'tool') {
    deleteDialog.title = '确认删除工具'
    deleteDialog.message = '确定要删除以下 Agent 工具吗？删除后 Agent 将无法再调用该工具。'
    deleteDialog.itemTitle = row.name
    deleteDialog.itemMeta = row.description || CATEGORY_LABELS[row.category] || row.category
    deleteDialog.itemTag = `L${row.riskLevel ?? 1}`
    deleteDialog.moduleKey = 'tools'
    deleteDialog.code = 'TL-DEL'
  } else {
    deleteDialog.title = '确认删除文章'
    deleteDialog.message = '确定要删除以下知识库文章吗？删除后需重新导入或手动创建。'
    deleteDialog.itemTitle = row.title
    deleteDialog.itemMeta = [row.category, severityLabel(row.severity)].filter(Boolean).join(' · ')
    deleteDialog.itemTag = severityLabel(row.severity)
    deleteDialog.moduleKey = 'knowledge'
    deleteDialog.code = 'KB-DEL'
  }

  deleteDialog.visible = true
}

async function confirmDelete() {
  if (!deleteDialog.target || deleteDialog.loading) return
  deleteDialog.loading = true
  try {
    if (deleteDialog.kind === 'user') {
      await deleteUser(deleteDialog.target.id)
      ElMessage.success('用户已删除')
      loadUsers()
    } else if (deleteDialog.kind === 'tool') {
      await deleteTool(deleteDialog.target.id)
      ElMessage.success('工具已删除')
      loadTools()
    } else {
      await api.delete(`/knowledge/articles/${deleteDialog.target.id}`)
      ElMessage.success('文章已删除')
      loadArticles()
    }
    deleteDialog.visible = false
    deleteDialog.target = null
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '删除失败')
  } finally {
    deleteDialog.loading = false
  }
}

const newArticle = reactive<{ title: string; category: string; tags: string; content: string; severity: ArticleSeverity }>({
  title: '', category: '', tags: '', content: '', severity: 'info',
})
const editArticle = reactive<{ id: string; title: string; category: string; tags: string; content: string; severity: ArticleSeverity }>({
  id: '', title: '', category: '', tags: '', content: '', severity: 'info',
})

const filteredArticles = computed(() => {
  let list = articles.value
  if (articleSeverityFilter.value) list = list.filter(a => a.severity === articleSeverityFilter.value)
  const q = articleSearch.value.trim().toLowerCase()
  if (q) list = list.filter(a => (a.title || '').toLowerCase().includes(q) || (a.content || '').toLowerCase().includes(q))
  return list
})

function categoryLabel(cat: string) { return CATEGORY_LABELS[cat] || cat || '—' }
function severityLabel(s: string) { return ({ info: '一般', warning: '警告', critical: '严重' } as Record<string, string>)[s] || s }
function riskClass(level: number) { return level <= 1 ? 'risk-low' : level <= 2 ? 'risk-mid' : level <= 3 ? 'risk-high' : 'risk-critical' }
function riskHint(i: number) { return ['只读查询', '轻量操作', '需审批', '高风险', '极高风险'][i - 1] || '' }
function shortId(id: string) { return id.length > 10 ? `${id.slice(0, 6)}…${id.slice(-4)}` : id }

function copyText(text: string) {
  navigator.clipboard?.writeText(text).then(() => ElMessage.success('已复制')).catch(() => {})
}

async function loadUsers() {
  try { users.value = (await getUsers()).items } catch { ElMessage.error('加载用户失败') }
}
async function loadTools() {
  try { tools.value = (await getTools()).items } catch { ElMessage.error('加载工具失败') }
}
async function loadConfig() {
  try {
    const data = await getConfig()
    if (data?.llm) {
      config.llm.apiBase = data.llm.apiBase ?? config.llm.apiBase
      config.llm.model = data.llm.model ?? config.llm.model
      config.llm.temperature = data.llm.temperature ?? config.llm.temperature
      config.llm.maxTokens = data.llm.maxTokens ?? config.llm.maxTokens
      config.llm.apiKeySet = Boolean(data.llm.apiKeySet)
      config.llm.apiKey = ''
    }
    if (data?.security) {
      config.security.approvalTimeout = data.security.approvalTimeout ?? config.security.approvalTimeout
      config.security.maxRounds =
        data.security.maxConversationRounds
        ?? data.security.maxRounds
        ?? config.security.maxRounds
    }
  } catch {}
}
async function loadArticles() {
  try {
    const { data } = await api.get('/knowledge/articles', { params: { page: 1, size: 1000 } })
    const payload = data.data || {}
    articles.value = payload.items || []
    articleTotal.value = payload.total ?? articles.value.length
  } catch { ElMessage.error('加载知识库失败') }
}

function handleUserAction(cmd: string, row: UserInfo) {
  if (cmd === 'edit') openEditUser(row)
  else if (cmd === 'reset') handleResetPwd(row)
  else if (cmd === 'delete') handleDeleteUser(row)
}

function handleCreateUser() {
  if (!newUser.username || !newUser.password) { ElMessage.warning('请填写完整'); return }
  userCreating.value = true
  createUser({ ...newUser })
    .then(() => { ElMessage.success('创建成功'); showUserDialog.value = false; newUser.username = ''; newUser.password = ''; loadUsers() })
    .catch(() => ElMessage.error('创建失败'))
    .finally(() => { userCreating.value = false })
}

function openEditUser(row: UserInfo) {
  editUser.id = row.id; editUser.username = row.username; editUser.role = row.role; editUser.password = ''
  showEditUserDialog.value = true
}

async function handleUpdateUser() {
  try {
    await updateUser(editUser.id, { role: editUser.role, password: editUser.password || '' })
    ElMessage.success('更新成功'); showEditUserDialog.value = false; loadUsers()
  } catch { ElMessage.error('更新失败') }
}

async function handleResetPwd(row: UserInfo) {
  try {
    const { value } = await ElMessageBox.prompt('请输入新密码', `重置「${row.username}」的密码`, {
      confirmButtonText: '确定', cancelButtonText: '取消', inputType: 'password',
      inputValidator: v => !!v?.trim() || '密码不能为空',
    })
    await resetPassword(row.id, value)
    ElMessage.success('密码已重置')
  } catch {}
}

async function handleDeleteUser(row: UserInfo) {
  if (row.username === 'admin') return
  openDeleteDialog('user', row)
}

function handleToolAction(cmd: string, row: ToolInfo) {
  if (cmd === 'edit') {
    if (row.builtin) { ElMessage.info('内置工具不可编辑，可使用启用开关控制'); return }
    openEditTool(row)
  }
  else if (cmd === 'toggle') onToggleTool(!row.enabled, row)
  else if (cmd === 'delete') {
    if (row.builtin) { ElMessage.warning('内置工具不可删除，可改用禁用开关'); return }
    handleDeleteTool(row)
  }
}

function openAddToolDialog() {
  isEditTool.value = false
  toolFileFromUpload.value = false
  toolFilePassed.value = false
  toolFileResetKey.value++
  Object.assign(currentTool, { id: '', name: '', description: '', category: '', riskLevel: 1, enabled: true, configStr: '' })
  showToolDialog.value = true
}

function onToolFileValidated(result: ToolFileValidation) {
  toolFileFromUpload.value = true
  toolFilePassed.value = !!result.ok
  if (result.ok) {
    currentTool.name = result.name
    currentTool.description = result.description || ''
    currentTool.category = result.category || 'system_operation'
    currentTool.riskLevel = result.riskLevel ?? 1
    currentTool.configStr = JSON.stringify(result.config || {}, null, 2)
  }
}

function onToolFileCleared() {
  toolFileFromUpload.value = false
  toolFilePassed.value = false
}

function openEditTool(row: ToolInfo) {
  isEditTool.value = true
  Object.assign(currentTool, {
    id: row.id, name: row.name, description: row.description, category: row.category,
    riskLevel: row.riskLevel, enabled: row.enabled, configStr: JSON.stringify(row.config || {}, null, 2),
  })
  showToolDialog.value = true
}

async function handleSaveTool() {
  if (!currentTool.name) { ElMessage.warning('请填写工具名称'); return }
  if (!isEditTool.value && toolFileFromUpload.value && !toolFilePassed.value) {
    ElMessage.warning('工具文件尚未通过诊断与试运行')
    return
  }
  toolSaving.value = true
  try {
    let cfg = {}
    try { cfg = currentTool.configStr ? JSON.parse(currentTool.configStr) : {} } catch { cfg = {} }
    const payload = { name: currentTool.name, description: currentTool.description, category: currentTool.category, riskLevel: currentTool.riskLevel, enabled: currentTool.enabled, config: cfg }
    if (isEditTool.value) { await updateTool(currentTool.id, payload); ElMessage.success('工具已更新') }
    else { await addTool(payload); ElMessage.success('工具已添加') }
    showToolDialog.value = false; loadTools()
  } catch (e: any) { ElMessage.error(e.message || '保存失败') }
  finally { toolSaving.value = false }
}

async function onToggleTool(v: any, row: ToolInfo) {
  try { await toggleTool(row.id, v as boolean); loadTools() } catch { ElMessage.error('切换失败') }
}

async function handleDeleteTool(row: ToolInfo) {
  openDeleteDialog('tool', row)
}

function loadPresetTools() {
  presetTools.value = PRESET_TOOLS.map(t => ({ ...t, selected: false }))
  showPresetDialog.value = true
}

function selectAllPresets(v: boolean) {
  presetTools.value.forEach(t => { t.selected = v })
}

async function importPresetTools() {
  const selected = presetTools.value.filter(t => t.selected)
  if (!selected.length) return
  importing.value = true
  let ok = 0
  try {
    for (const tool of selected) {
      try { await addTool({ ...tool, enabled: true, config: {} }); ok++ } catch {}
    }
    ElMessage.success(`导入完成，成功 ${ok} 个`)
    showPresetDialog.value = false; loadTools()
  } finally { importing.value = false }
}

async function saveConfig() {
  savingConfig.value = true
  try {
    const llm: Record<string, unknown> = {
      apiBase: config.llm.apiBase,
      model: config.llm.model,
      temperature: config.llm.temperature,
      maxTokens: config.llm.maxTokens,
    }
    const nextKey = config.llm.apiKey.trim()
    if (nextKey) llm.apiKey = nextKey

    await updateConfig({
      llm,
      security: {
        approvalTimeout: config.security.approvalTimeout,
        maxConversationRounds: config.security.maxRounds,
      },
    })
    if (nextKey) {
      config.llm.apiKeySet = true
      config.llm.apiKey = ''
    }
    ElMessage.success('配置已保存')
  } catch {
    ElMessage.error('保存失败')
  } finally {
    savingConfig.value = false
  }
}

function handleArticleAction(cmd: string, row: any) {
  if (cmd === 'edit') openEditArticle(row)
  else if (cmd === 'delete') handleDeleteArticle(row)
}

function openAddArticleDialog() {
  articleFileFromUpload.value = false
  articleFilePassed.value = false
  articleBatchMode.value = false
  articleBatchCount.value = 0
  articleBatchItems.value = []
  articleFileResetKey.value++
  Object.assign(newArticle, { title: '', category: '', tags: '', content: '', severity: 'info' })
  showArticleDialog.value = true
}

function onArticleFileValidated(result: ArticleFileValidation) {
  articleFileFromUpload.value = true
  articleFilePassed.value = !!result.ok
  if (!result.ok) return

  if (result.mode === 'batch' && (result.articles?.length || 0) > 1) {
    articleBatchMode.value = true
    articleBatchCount.value = result.articleCount || result.articles?.length || 0
    articleBatchItems.value = result.articles || []
    return
  }

  articleBatchMode.value = false
  articleBatchCount.value = 1
  articleBatchItems.value = []
  newArticle.title = result.title || ''
  newArticle.category = result.category || ''
  newArticle.tags = typeof result.tags === 'string' ? result.tags : ''
  newArticle.content = result.content || ''
  newArticle.severity = (['info', 'warning', 'critical'].includes(result.severity || '')
    ? result.severity
    : 'info') as ArticleSeverity
}

function onArticleFileCleared() {
  articleFileFromUpload.value = false
  articleFilePassed.value = false
  articleBatchMode.value = false
  articleBatchCount.value = 0
  articleBatchItems.value = []
}

async function handleCreateArticle() {
  if (articleFileFromUpload.value && !articleFilePassed.value) {
    ElMessage.warning('知识库文件尚未通过格式诊断与内容解析')
    return
  }

  articleCreating.value = true
  try {
    if (articleBatchMode.value && articleBatchItems.value?.length) {
      const res = await importArticlesBatch(articleBatchItems.value)
      ElMessage.success(res.message || `已导入 ${res.data?.created ?? 0} 篇文章`)
      showArticleDialog.value = false
      loadArticles()
      return
    }

    if (!newArticle.title.trim()) { ElMessage.warning('请填写标题'); return }
    await createArticle({ ...newArticle, tags: newArticle.tags })
    ElMessage.success('文章已创建')
    showArticleDialog.value = false
    newArticle.title = ''
    newArticle.content = ''
    loadArticles()
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '创建失败')
  } finally {
    articleCreating.value = false
  }
}

function openEditArticle(row: any) {
  editArticle.id = row.id; editArticle.title = row.title; editArticle.category = row.category
  editArticle.tags = Array.isArray(row.tags) ? row.tags.join(',') : (row.tags || '')
  editArticle.content = row.content
  editArticle.severity = (row.severity || 'info') as ArticleSeverity
  showEditArticleDialog.value = true
}

async function handleUpdateArticle() {
  try {
    await api.put(`/knowledge/articles/${editArticle.id}`, { ...editArticle, tags: editArticle.tags })
    ElMessage.success('文章已更新'); showEditArticleDialog.value = false; loadArticles()
  } catch { ElMessage.error('更新失败') }
}

async function handleDeleteArticle(row: any) {
  openDeleteDialog('article', row)
}

async function handleReindex() {
  reindexing.value = true
  try {
    const { data } = await api.post('/knowledge/reindex')
    ElMessage.success(data.message || '索引已重建')
  } catch { ElMessage.error('重建失败') }
  finally { reindexing.value = false }
}

onMounted(() => { loadUsers(); loadTools(); loadConfig(); loadArticles() })
</script>

<style lang="scss" scoped>
.admin-page {
  position: relative;
  min-height: 100%;
}

.admin-content {
  position: relative;
  z-index: 1;
  max-width: 1300px;
  margin: 0 auto;
  padding: 24px;
}

.tab-panel {
  background: transparent;
  border: none;
  padding: 0;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  padding: 12px 14px;
  border-radius: 12px;
  background: #fafbfc;
  border: 1px solid #eef2f7;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  flex: 1;
}

.toolbar-right { display: flex; gap: 8px; flex-wrap: wrap; }

.search-input {
  width: 220px;

  :deep(.el-input__wrapper) {
    border-radius: 10px;
    box-shadow: 0 0 0 1px #e2e8f0 inset;
    background: #fff;
  }
}

.filter-chips { display: flex; gap: 8px; flex-wrap: wrap; }

.chip {
  padding: 6px 14px;
  border-radius: 999px;
  border: 1px solid #e2e8f0;
  background: #fff;
  font-size: 12px;
  font-weight: 600;
  color: #64748b;
  cursor: pointer;
  transition: all 0.15s;

  &:hover { border-color: #93c5fd; color: #2563eb; }

  &.active {
    background: #eff6ff;
    border-color: #2563eb;
    color: #2563eb;
    box-shadow: 0 0 0 1px rgba(37, 99, 235, 0.08);
  }

  &.warn.active { background: #fffbeb; border-color: #d97706; color: #d97706; }
  &.critical.active { background: #fef2f2; border-color: #ef4444; color: #ef4444; }
}

.primary-btn, .ghost-btn {
  padding: 9px 18px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.15s;
  border: none;
  white-space: nowrap;

  &:disabled { opacity: 0.6; cursor: not-allowed; }
}

.primary-btn {
  background: linear-gradient(135deg, #2563eb, #4f46e5);
  color: #fff;
  box-shadow: 0 4px 14px rgba(37, 99, 235, 0.22);

  &:hover:not(:disabled) { filter: brightness(1.05); transform: translateY(-1px); }
}

.ghost-btn {
  background: #fff;
  border: 1px solid #e2e8f0 !important;
  color: #475569;

  &:hover:not(:disabled) { border-color: #cbd5e1; background: #f8fafc; }
  &.sm { padding: 5px 12px; font-size: 11px; }
}

.data-card {
  border: 1px solid #eef2f7;
  border-radius: 12px;
  overflow: hidden;
  background: #fff;

  :deep(.el-table) {
    --el-table-border-color: #f1f5f9;
    --el-table-header-bg-color: #f8fafc;
    --el-table-row-hover-bg-color: #f8fbff;
  }

  :deep(.el-table th.el-table__cell) {
    font-size: 12px;
    font-weight: 700;
    color: #64748b;
    padding: 12px 0;
  }

  :deep(.el-table td.el-table__cell) {
    padding: 14px 0;
  }

  :deep(.el-table__row--striped td.el-table__cell) {
    background: #fcfdff;
  }
}

.user-cell {
  display: flex; align-items: center; gap: 10px;
  strong { font-size: 13px; color: #1e293b; }
}
.user-avatar {
  width: 32px; height: 32px; border-radius: 50%;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff; font-size: 13px; font-weight: 700;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.builtin-tag {
  margin-left: 6px; padding: 1px 6px; border-radius: 4px;
  background: #fef3c7; color: #b45309; font-size: 10px; font-weight: 700;
}

.role-pill {
  padding: 3px 10px; border-radius: 999px; font-size: 11px; font-weight: 700;
  &.admin { background: #fef2f2; color: #dc2626; }
  &.user { background: #eff6ff; color: #2563eb; }
}

.id-copy {
  display: inline-flex; align-items: center; gap: 4px;
  border: none; background: #f8fafc; padding: 3px 8px; border-radius: 6px;
  font-family: ui-monospace, monospace; font-size: 11px; color: #64748b; cursor: pointer;
  transition: all 0.15s;
  &:hover { background: #eff6ff; color: #2563eb; }
}

.tool-name { font-size: 12px; color: #2563eb; background: #eff6ff; padding: 2px 8px; border-radius: 4px; }
.cat-pill { padding: 2px 8px; border-radius: 999px; background: #f1f5f9; font-size: 11px; color: #64748b; font-weight: 600; }

.risk-pill {
  padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 700;
  &.risk-low { background: #ecfdf5; color: #059669; }
  &.risk-mid { background: #eff6ff; color: #2563eb; }
  &.risk-high { background: #fffbeb; color: #d97706; }
  &.risk-critical { background: #fef2f2; color: #dc2626; }
  &.sm { font-size: 10px; }
}

.sev-pill {
  padding: 3px 10px; border-radius: 999px; font-size: 11px; font-weight: 700;
  &.info { background: #eff6ff; color: #2563eb; }
  &.warning { background: #fffbeb; color: #d97706; }
  &.critical { background: #fef2f2; color: #dc2626; }
}

.more-btn {
  width: 32px; height: 32px; border: 1px solid #e2e8f0; border-radius: 8px;
  background: #fff; cursor: pointer; display: inline-flex; align-items: center; justify-content: center;
  color: #64748b; transition: all 0.15s;
  &:hover { border-color: #2563eb; color: #2563eb; background: #eff6ff; }
}
.danger-text { color: #ef4444; }

.batch-hint {
  margin-bottom: 14px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid rgba(217, 119, 6, 0.25);
  background: linear-gradient(135deg, rgba(255, 251, 235, 0.95), rgba(254, 243, 199, 0.35));
  font-size: 13px;
  color: #92400e;
  line-height: 1.5;

  strong { color: #b45309; }
}

.article-load-hint {
  margin: 0 0 10px;
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(254, 243, 199, 0.35);
  border: 1px solid rgba(217, 119, 6, 0.2);
  font-size: 12px;
  color: #92400e;
}

.preset-toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding: 10px 12px;
  border-radius: 10px;
  background: #f8fafc;
  border: 1px solid #eef2f7;

  .preset-count {
    margin-left: auto;
    font-size: 12px;
    color: #64748b;
    font-weight: 700;
  }
}

.preset-tool-list {
  max-height: 380px;
  overflow-y: auto;
  border: 1px solid #eef2f7;
  border-radius: 12px;
  background: #fff;
}
.preset-tool-item {
  display: flex; align-items: flex-start; gap: 10px; padding: 10px 14px;
  border-bottom: 1px solid #f8fafc; cursor: pointer;
  &:hover { background: #f8fafc; }
  input { margin-top: 4px; }
  .preset-body { flex: 1; display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
  .preset-tool-name { font-size: 12px; color: #2563eb; }
  .preset-tool-desc { font-size: 12px; color: #64748b; flex: 1; min-width: 160px; }
}

@media (max-width: 560px) {
  .admin-content { padding: 16px; }
  .search-input { width: 100%; }
}
</style>
