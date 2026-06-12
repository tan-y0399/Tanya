## 十一、Linux 命令安全与风险分级

> 参考资料：CSDN《工作中尤其需要注意的Linux命令》《Linux高危命令汇总》《Linux常用命令》等，已与 KylinOps `command_security` 引擎 L1–L5 对齐。

### 11.1 KylinOps 命令风险等级总览（L1–L5）

| 等级 | 名称 | 典型影响 | Agent 处置策略 |
|------|------|----------|----------------|
| **L1** | 安全（只读） | 无副作用，仅查询 | 直接执行 |
| **L2** | 低风险（可逆） | 小范围可逆修改 | 用户确认后执行（L2 确认卡） |
| **L3** | 中等风险 | 可能影响服务/网络配置 | 管理员审批 |
| **L4** | 高风险 | 数据丢失、服务中断 | 管理员审批 + 强提示 |
| **L5** | 致命/禁止 | 系统崩溃、全盘破坏 | 默认阻断或强制审批 |

**判别顺序（与代码一致）**：黑名单/注入检测 → 路径保护 → 命令分组 → 参数特例 → 输出最终等级。

**使用建议**：
- 生产环境执行写操作前必须备份或快照。
- 禁止在未指定路径时对 `find` 结果直接 `xargs rm`。
- 黑屏敲命令前先按空格确认，避免误回车执行 `rm -rf /*`。

---

### 11.2 致命与高危命令（L4–L5，慎在生产执行）

| 命令/模式 | 等级 | 风险说明 | 注意事项 |
|-----------|------|----------|----------|
| `rm -rf /` | L5 | 递归删除根目录，系统不可恢复 | KylinOps 硬阻断 |
| `rm -rf /*` | L5 | 删除根下几乎所有内容 | 俗称「自杀命令」 |
| `rm -rf *` | L4 | 删除当前目录全部内容 | 多敲空格成 `rm -rf . *` 更危险 |
| `rm .*` | L4 | 误删用户主目录大量隐藏文件 | `ls .*` 文件数常远大于 `ls *` |
| `dd if=... of=/dev/sdX` | L5 | 裸设备写入，破坏分区/数据 | KylinOps 禁止 dd |
| `mkfs` / `fdisk` / `parted` | L5 | 格式化或重建分区表 | 默认阻断 |
| `> /dev/sda` | L5 | 向磁盘设备写空，破坏文件系统 | 硬阻断 |
| `:(){ :|:& };:`（fork 炸弹） | L5 | 进程爆炸导致系统 hang | 硬阻断 |
| `chmod -R 000 /` | L5 | 全系统不可访问 | 硬阻断 |
| `iptables -F` | L5 | 清空防火墙 | 硬阻断 |
| `shutdown` / `reboot` / `halt` | L5 | 系统停机 | 黑名单 |
| `useradd` / `userdel` / `passwd` | L5 | 账户与认证变更 | 需审批 |
| `yum remove` / `apt purge` | L4 | 卸载软件破坏依赖 | 需审批 |

**经典事故**：`install.sh` 中 `rm -rf /usr /lib/...` 因空格写成 `rm -rf / usr/...` 导致删库。

---

### 11.3 高风险组合与误操作（L3–L4）

| 场景 | 等级 | 说明 |
|------|------|------|
| `find / -name "*.bak" \| xargs rm -rf` | L4 | 未限定路径可能删到系统文件 |
| `ps -ef \| grep xxx \| xargs kill` | L4 | 模式过宽会误杀关键进程 |
| `^cmd^替换^`（历史展开） | L3 | 误将 `rm` 替换成危险命令 |
| `cat > 已有文件` | L3 | 直接覆盖不提示 |
| `tr` 字符集写错 | L2 | 批量替换破坏文本/配置 |
| `ifconfig eth0 down` / `ip link set down` | L4 | 网络中断，集群节点宕机 |
| `ifconfig -a6` vs `ifconfig -a 6` | L4 | 空格导致参数解析错误改 IP |
| `kill -9` / `pkill -9` | L4 | 强杀进程可能导致数据损坏 |
| `systemctl stop sshd` | L5 | 禁止停止关键安全服务 |
| `systemctl restart` 核心服务 | L4 | 需审批 |

---

### 11.4 L1 只读命令（系统监控与审计）

以下命令在 KylinOps 中通常为 **L1，直接执行**：

**系统监控**：`top`, `htop`, `free`, `df`, `uptime`, `vmstat`, `iostat`, `mpstat`, `sar`

**进程查看**：`ps`, `pgrep`, `pidof`（仅查看，不含 kill）

**日志查看**：`journalctl`, `dmesg`, `tail`, `grep`, `cat`, `head`, `less`, `zgrep`

**文件浏览**：`ls`, `pwd`, `stat`, `file`, `find`（仅 `-ls` / 查看）, `du`, `which`, `whereis`

**网络查看**：`ss`, `netstat`, `ip addr show`, `ip route show`, `ping`（少量探测）, `traceroute`

**示例**：`free -h` 查看内存；`df -h` 查看磁盘；`ss -tlnp` 查看监听端口。

---

### 11.5 L2 低风险命令（可逆，需确认）

| 命令 | 等级 | 说明 |
|------|------|------|
| `kill`（默认 TERM） | L2 | 正常结束进程，需确认目标 PID |
| `manage_service start` | L2 | 启动服务 |
| `cp` / `mv`（业务目录内） | L2 | 注意目标路径 |
| `mkdir` / `touch` | L2 | 创建目录/文件 |
| `ping -c 4` | L2 | 网络探测，KylinOps 可能 L3 确认 |

---

### 11.6 L3 中等风险（配置变更，需审批）

| 命令/操作 | 等级 | 说明 |
|-----------|------|------|
| `chmod` / `chown` | L3–L4 | 权限变更，关键目录默认 L4 |
| `rm`（非 -rf 系统路径） | L3 | 删除文件 |
| `ip route add/del` | L3 | 路由变更 |
| `ifconfig up/down` | L3 | 接口状态 |
| `systemctl start/stop/restart` | L3–L4 | 服务生命周期 |
| `firewall-cmd --add-port` | L3 | 防火墙规则 |
| `mount` / `umount` | L3 | 挂载变更 |

---

### 11.7 常见命令速查与推荐等级（Linux 常用）

| 命令 | 推荐等级 | 分类 |
|------|----------|------|
| `cd` / `ls` / `pwd` | L1 | 目录 |
| `mkdir` / `rmdir` | L2 | 目录 |
| `rm` / `rm -rf` | L3–L5 | 视参数而定 |
| `cp` / `mv` | L2–L3 | 文件 |
| `find` | L1（仅查）/ L4（配合 rm） | 搜索 |
| `grep` / `awk` / `sed` | L1（只读）/ L3（`-i` 改文件） | 文本 |
| `vi` / `vim` | L3 | 改文件 |
| `tar -zcvf` | L2 | 打包 |
| `tar -zxvf` | L2 | 解压 |
| `wget` / `curl` | L2–L3 | 下载 |
| `ssh` / `scp` | L2 | 远程 |
| `crontab -e` | L3 | 计划任务 |
| `export` / `source` | L2 | 环境变量 |

---

### 11.8 内存与缓存清理相关命令分级

| 命令 | 等级 | 说明 |
|------|------|------|
| `free -h` / `vmstat` / `cat /proc/meminfo` | L1 | 只读诊断 |
| `top` / `ps aux --sort=-%mem` | L1 | 查占用 |
| `sync; echo 1 > /proc/sys/vm/drop_caches` | L3 | 清 PageCache，需 root，生产谨慎 |
| `echo 3 > /proc/sys/vm/drop_caches` | L4 | 清全部缓存，影响性能 |
| `kill` 大内存进程 | L2–L4 | 视信号而定 |

**建议流程**：先 L1 诊断 → 再 L2/L3 处置 → 避免直接 L4/L5 操作。

---

### 11.9 运维安全检查清单（执行前）

1. 是否明确 **目标路径/主机/服务名**？
2. 是否属于 **只读（L1）** 还是 **写操作（L2+）**？
3. `rm` / `find` / `kill` 是否使用 **管道**？是否加了 `-rf` / `-9`？
4. 生产环境是否已有 **备份/变更窗口/审批单**？
5. 在 KylinOps 中查看工具卡片上的 **L1–L5 标签** 与确认/审批提示。

---

### 11.10 与 KylinOps Agent 问答的对应关系

- 用户问 **「某命令什么风险等级」** → 意图 `knowledge_qa`，查本知识库 + `command_security.analyze_command`。
- 用户问 **「查看当前内存/磁盘」** → 意图 `ops_query`，调用 `get_memory_info` 等 L1 工具。
- 用户要 **执行写命令** → `execute_command` 经安全引擎分级，L3+ 走审批流。

**参考链接（外部）**：
- https://blog.csdn.net/click_idc/article/details/80770272
- https://blog.csdn.net/weixin_35480412/article/details/116950238
- https://blog.csdn.net/weixin_49294616/article/details/141165874
