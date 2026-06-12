<template>
  <header class="admin-header">
    <div class="header-main">
      <div class="title-bar">
        <span class="title-accent"></span>
        <div>
          <div class="mod-tag">MOD-ADM · 管理员工作台</div>
          <h2 class="page-title">管理员工作台</h2>
          <p class="page-sub">[ USR · TOOL · SEC · KB ]</p>
        </div>
      </div>
      <p class="page-desc">集中管理系统账号、Agent 工具、安全策略与知识库内容，是平台核心配置入口</p>
    </div>
    <div class="quick-links">
      <router-link to="/admin/feedback" class="quick-link">反馈管理</router-link>
      <router-link to="/approval" class="quick-link">审批管理</router-link>
      <router-link to="/knowledge" class="quick-link">知识库浏览</router-link>
    </div>
  </header>
</template>

<style lang="scss" scoped>
.admin-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 8px;
  flex-wrap: wrap;
}

.title-bar {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.title-accent {
  width: 4px;
  height: 52px;
  border-radius: 2px;
  background: linear-gradient(180deg, #2563eb, #7c3aed);
  flex-shrink: 0;
}

.mod-tag {
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.1em;
  color: #2563eb;
  margin-bottom: 4px;
}

.page-title {
  margin: 0;
  font-size: 22px;
  font-weight: 800;
  color: #0f172a;
}

.page-sub {
  margin: 4px 0 0;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: #94a3b8;
}

.page-desc {
  margin: 8px 0 0;
  font-size: 13px;
  color: #64748b;
  max-width: 560px;
}

.quick-links {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.quick-link {
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid #e2e8f0;
  background: rgba(255, 255, 255, 0.85);
  font-size: 12px;
  font-weight: 600;
  color: #475569;
  text-decoration: none;
  transition: all 0.15s;

  &:hover {
    border-color: #2563eb;
    color: #2563eb;
    background: #eff6ff;
  }
}
</style>
