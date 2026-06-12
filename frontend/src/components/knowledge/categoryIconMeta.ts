export type CategoryIconKey =
  | 'all'
  | 'security'
  | 'boot'
  | 'service'
  | 'config'
  | 'disk'
  | 'log'
  | 'domestic'
  | 'process'
  | 'network'
  | 'install'
  | 'startup'
  | 'login'
  | 'activate'
  | 'permission'
  | 'version'
  | 'software'
  | 'peripheral'
  | 'manual'
  | 'display'
  | 'network-faq'
  | 'input'
  | 'mount'
  | 'app'
  | 'other'
  | 'default'

export interface CategoryIconMeta {
  key: CategoryIconKey
  color: string
}

const CATEGORY_ICON_MAP: Record<string, CategoryIconMeta> = {
  '磁盘与文件系统问题': { key: 'disk', color: '#7C6CF0' },
  '进程与内存问题': { key: 'process', color: '#A78BFA' },
  '网络问题': { key: 'network', color: '#4F8FF7' },
  '服务管理问题': { key: 'service', color: '#38BDF8' },
  '系统启动与内核问题': { key: 'boot', color: '#6366F1' },
  '安全与权限问题': { key: 'security', color: '#F59E0B' },
  '配置漂移与系统管理问题': { key: 'config', color: '#14B8A6' },
  '日志系统问题': { key: 'log', color: '#64748B' },
  '国产化平台特有问题': { key: 'domestic', color: '#F97316' },
  '常见-安装问题': { key: 'install', color: '#22C55E' },
  '常见-启动问题': { key: 'startup', color: '#3B82F6' },
  '常见-登录问题': { key: 'login', color: '#8B5CF6' },
  '常见-激活问题': { key: 'activate', color: '#10B981' },
  '常见-权限问题': { key: 'permission', color: '#EF4444' },
  '常见-版本问题': { key: 'version', color: '#0EA5E9' },
  '常见-软件安装': { key: 'software', color: '#06B6D4' },
  '常见-外设使用': { key: 'peripheral', color: '#EC4899' },
  '常见-手册问题': { key: 'manual', color: '#84CC16' },
  '常见-显示问题': { key: 'display', color: '#6366F1' },
  '常见-网络问题': { key: 'network-faq', color: '#4F8FF7' },
  '常见-输入问题': { key: 'input', color: '#A855F7' },
  '常见-挂卸载问题': { key: 'mount', color: '#7C6CF0' },
  '常见-应用问题': { key: 'app', color: '#F472B6' },
  '常见-其他问题': { key: 'other', color: '#94A3B8' },
}

export function resolveCategoryIcon(name: string): CategoryIconMeta {
  if (!name) return { key: 'all', color: '#4F8FF7' }
  return CATEGORY_ICON_MAP[name] || { key: 'default', color: '#94A3B8' }
}

export const GROUP_OPS_ICON: CategoryIconMeta = { key: 'service', color: '#38BDF8' }
export const GROUP_FAQ_ICON: CategoryIconMeta = { key: 'manual', color: '#84CC16' }
