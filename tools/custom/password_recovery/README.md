# 密码找回 Agent 工具集

通过 **管理工作台 → 工具管理 → 添加工具** 拖拽上传 `.py` 或 `.json` 文件。每个工具均提供两种格式，**推荐上传 `.py`**。

## 工具一览

| 工具名 | 层级 | 风险 | 作用 |
|--------|------|------|------|
| `check_console_access_available` | 第一层 | L1 | 询问/记录是否有控制台（VMware/物理机等），离线恢复必须控制台 |
| `check_ssh_connectivity` | 第一层 | L1 | 检测 SSH 可达与登录账号，决定在线改密或离线指引 |
| `get_user_account_info` | 第一层 | L1 | 查 UID、家目录、shell、过期信息，确认改密对象 |
| `check_account_lock_status` | 第一层 | L1 | 查 faillock / pam_tally2 是否锁定 |
| `get_password_policy` | 第一层 | L1 | 读 pwquality.conf、login.defs，生成符合策略的临时密码 |
| `reset_user_password` | 第二层 | **L5** | 在线 chpasswd 重置密码（需审批，试运行默认 dry_run） |
| `verify_account_after_reset` | 第二层 | L2 | 改密后验证账户未锁、家目录与 shadow 正常 |

离线手册（已有）：`../get_password_recovery_playbook.py`

## 推荐导入顺序

1. 第一层 5 个工具（L1）
2. `verify_account_after_reset`（L2）
3. `reset_user_password`（L5，需审批配置）
4. `get_password_recovery_playbook`（离线手册）

## 典型 Agent 流程

```
check_ssh_connectivity
  ├─ SSH 可达 → get_user_account_info → check_account_lock_status
  │              → get_password_policy → reset_user_password → verify_account_after_reset
  └─ SSH 不可达 → check_console_access_available → get_password_recovery_playbook
```

## 参数说明

### check_console_access_available

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `has_console` | bool | 是 | 用户是否能打开虚拟机控制台 |
| `console_type` | string | 否 | `vmware` / `virtualbox` / `vnc` / `physical` / `ipmi` / `unknown` |
| `target_host` | string | 否 | 目标主机 IP 或名称 |
| `notes` | string | 否 | 备注 |

### check_ssh_connectivity

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `host` | string | 否 | 目标 IP |
| `port` | int | 否 | SSH 端口，默认 22 |
| `ssh_user` | string | 否 | 当前连接账号，默认 root |

### get_user_account_info / check_account_lock_status / verify_account_after_reset

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `username` | string | 是 | 目标 Linux 用户名 |

### get_password_policy

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `username` | string | 否 | 附带查询该用户 chage -l |

### reset_user_password

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `username` | string | 是 | 目标用户名 |
| `new_password` | string | 是 | 符合策略的新密码 |
| `dry_run` | bool | 否 | 试运行为 true，仅生成命令不执行 |

## 远程执行说明

除 `check_console_access_available` 外，其余工具的 `run()` 返回 `commands` 列表与 `agent_instruction`。
Agent 应通过 `execute_command` 在**已绑定 SSH 的目标 VM** 上执行，而非在后端沙箱内执行真实改密。

`reset_user_password` 禁止直接编辑 `/etc/shadow`；生产执行前须 L4/L5 审批。
