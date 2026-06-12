export const TOOL_DISPLAY_NAMES: Record<string, string> = {
  list_processes: '进程列表',
  get_process_list: '进程列表',
  get_network_connections: '网络连接',
  get_cpu_info: 'CPU 使用率',
  get_memory_info: '内存使用',
  get_disk_usage: '磁盘空间',
  get_disk_info: '磁盘空间',
  get_service_status: '服务状态',
  manage_service: '服务控制',
  execute_command: '远程命令',
  run_command: '远程命令',
  get_system_info: '系统概览',
  get_process_detail: '进程详情',
  get_logs: '系统日志',
  search_journal_logs: 'Journal 日志',
  get_file_list: '目录列表',
  read_file: '读取文件',
}

export function toolDisplayName(toolName: string): string {
  return TOOL_DISPLAY_NAMES[toolName] || toolName
}

export function toolActionHint(toolName: string, params?: Record<string, unknown>): string {
  const hints: Record<string, string> = {
    list_processes: '按 CPU/内存排序列出进程',
    get_network_connections: '查看监听端口与连接状态',
    get_cpu_info: '采集 CPU 核心数与负载',
    get_memory_info: '采集物理内存与 Swap',
    get_disk_usage: '查看分区使用率',
    get_service_status: '查询 systemd 服务状态',
    manage_service: '在目标主机管理服务启停',
    execute_command: '在目标主机执行远程命令',
    run_command: '在目标主机执行远程命令',
    kill_process: '终止目标主机上的指定进程',
  }
  if (toolName === 'manage_service' && params) {
    const action = String(params.action || '')
    const service = String(params.service_name || params.service || '')
    if (action && service) return `${action} 服务 ${service}`
  }
  return hints[toolName] || '在目标主机执行只读检查'
}
