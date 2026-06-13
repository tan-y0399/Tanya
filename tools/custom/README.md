# 自定义 Agent 工具文件

通过 **管理工作台 → 工具管理 → 添加工具** 拖拽上传 `.py` 或 `.json` 文件。

## 密码找回工具集（password_recovery/）

完整 7 个工具 + 导入说明见 [`password_recovery/README.md`](password_recovery/README.md)。

| 文件前缀 | 作用 |
|----------|------|
| `check_console_access_available` | 是否有控制台，离线恢复分支 |
| `check_ssh_connectivity` | SSH 可达性，在线/离线决策 |
| `get_user_account_info` | 用户 UID/家目录/shell |
| `check_account_lock_status` | faillock / pam_tally2 锁定检查 |
| `get_password_policy` | 密码复杂度策略 |
| `reset_user_password` | 在线 chpasswd 改密（L5） |
| `verify_account_after_reset` | 改密后验证 |

## get_password_recovery_playbook

| 文件 | 说明 |
|------|------|
| `get_password_recovery_playbook.py` | **推荐**：完整模板、知识库引用、多模式手册 |
| `get_password_recovery_playbook.json` | 精简 JSON + 内嵌 Python 逻辑 |

### 导入步骤

1. 打开管理工作台 → 齿轮「工具管理」→ 添加工具
2. 将 `get_password_recovery_playbook.py` 拖入上传区
3. 等待「代码诊断」「试运行」均通过
4. 确认自动填充的名称、描述、分类后点击「添加」

### 调用参数（Agent 传入 run）

| 参数 | 类型 | 说明 |
|------|------|------|
| `username` | string | 需重置密码的用户名（必填） |
| `system_type` | string | `desktop` / `server` / `kylin_v11` / `auto` |
| `recovery_mode` | string | `grub_single` / `rescue` / `livecd` / `auto` |

### 示例

```python
run(username="kylin", system_type="desktop", recovery_mode="auto")
```

返回 `playbooks` 数组，每项含 `title`、`steps`、`warnings`、`kb_ref`。
