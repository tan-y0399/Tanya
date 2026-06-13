---
title: 磁盘空间未满但无法创建文件（inode 索引节点耗尽）
category: 磁盘与文件系统问题
tags: 磁盘,inode,文件系统,fontconfig,maildrop,故障排查
severity: warning
source: web_research
---

# 磁盘空间未满但无法创建文件（inode 索引节点耗尽）

**问题编号** | KB-OPS-INODE-001  
**适用系统** | 银河麒麟高级服务器 V10/V11、桌面版（RHEL 系）  
**参考来源** | [CSDN：银河麒麟 inode 节点占用](https://blog.csdn.net/AirIT/article/details/131112444)、华为云 inode 耗尽排查、信创磁盘满排查实践

## 问题描述

业务或系统运维中出现以下现象：

- 创建文件/目录失败，报错 `No space left on device`
- 软件无法写日志、服务启动失败、SSH 会话无法建立临时文件
- 执行 `df -h` 时根分区 `/` **仍有剩余空间**（例如使用率 60%～80%）

这类问题常被误判为「磁盘满了」，实际可能是 **inode（索引节点）耗尽**，而非数据块占满。

## 典型表现

| 检查项 | 正常情况 | 故障情况 |
|--------|----------|----------|
| `df -h /` | Use% < 90% | 有剩余空间 |
| `df -i /` | IUse% < 90% | **IUse% = 100%** |
| 新建文件 | 成功 | `No space left on device` |
| 业务日志 | 正常写入 | 批量报错、服务异常 |

## 根因分析

inode 保存文件元数据（类型、权限、属主、时间戳、数据块指针等），**每个文件/目录占用 1 个 inode**，与文件实际大小无关。

常见诱因：

1. **海量小文件**：字体缓存、包管理缓存、会话临时文件
2. **定时任务未重定向输出**：cron 每执行一次向 `/var/spool/postfix/maildrop` 写入小文件
3. **应用日志碎片化**：按秒/按请求切分的小日志文件
4. **已删除但仍被进程占用的文件**（僵尸文件）：`df -h` 空间不释放，有时伴随 inode 异常

银河麒麟服务器上曾出现 **`/usr/lib/fontconfig/cache` 下 `.cache-*` 小文件过多** 导致根分区 inode 打满的案例。

## 排查步骤

### 1. 区分「空间满」还是「inode 满」

```bash
df -h /
df -i /
```

若 `df -h` 有空间而 `df -i` 的 `IUse%` 为 100%，即可确认 inode 问题。

### 2. 定位 inode 占用最高的目录

```bash
# 根目录下一级目录 inode 用量（推荐）
du --inodes --max-depth=1 / 2>/dev/null | sort -nr | head -20

# 或逐层统计文件数量
for i in /*; do echo "$i"; find "$i" 2>/dev/null | wc -l; done | paste - - | sort -k2 -nr | head -10
```

进入可疑目录继续下钻，例如：

```bash
du --inodes --max-depth=1 /usr/lib/fontconfig 2>/dev/null | sort -nr
find /usr/lib/fontconfig/cache -type f 2>/dev/null | wc -l
```

### 3. 检查僵尸文件（已删除未释放）

```bash
lsof 2>/dev/null | grep deleted | head -20
# 确认后可重启对应服务或 kill 占用进程以释放 inode/空间
```

### 4. 检查 cron 邮件积压

```bash
find /var/spool/postfix/maildrop -type f 2>/dev/null | wc -l
ls -la /var/spool/postfix/maildrop 2>/dev/null | tail -5
```

若定时任务未设置 `>/dev/null 2>&1`，每次执行可能产生 maildrop 小文件。

## 处理方案

### 方案 A：清理过期小文件（fontconfig 缓存示例）

**操作前务必备份**，生产环境建议先打包归档：

```bash
mkdir -p /data/backup
tar czf /data/backup/fontconfig-cache-$(date +%F).tar.gz /usr/lib/fontconfig/cache 2>/dev/null

cd /usr/lib/fontconfig/cache
# 删除 100 天未修改的 cache 文件（按现场调整天数）
find . -type f -mtime +100 -name '*.cache-*' -print | head
find . -type f -mtime +100 -name '*.cache-*' -delete
```

清理后验证：

```bash
df -i /
systemctl restart 受影响的服务名
```

### 方案 B：清理 maildrop / 临时目录

```bash
# 先修复 cron：在 crontab 中为任务添加输出重定向
# * * * * * /path/script.sh >/dev/null 2>&1

# 确认无业务依赖后清理积压（需 root）
find /var/spool/postfix/maildrop -type f -mtime +7 -delete
```

### 方案 C：systemd 临时文件

```bash
systemd-tmpfiles --clean
```

## 验证与预防

**验证：**

```bash
df -i /
touch /tmp/inode-test-$$ && rm -f /tmp/inode-test-$$
echo "inode 恢复，可正常创建文件"
```

**预防建议：**

- 监控同时采集 `df -h` 与 `df -i`，inode 使用率 > 85% 告警
- 日志使用 journald 大小限制（`SystemMaxUse=`）+ logrotate，避免碎片化小文件
- cron 任务统一添加 `>/dev/null 2>&1` 或写入指定日志文件
- 对 fontconfig、应用缓存目录做定期清理策略

## 注意事项

- **禁止**为增加 inode 数量随意对生产分区重新 `mkfs` 格式化
- 大批量 `find ... -delete` 前先 `find ... -print | head` 抽样确认
- inode 耗尽可能导致数据库、systemd、SSH 同时异常，优先恢复 inode 再排查业务

## Agent 运维提示

KylinOps Agent 排查顺序建议：

1. `execute_command`: `df -h / && df -i /`
2. `execute_command`: `du --inodes --max-depth=1 / 2>/dev/null | sort -nr | head -15`
3. 根据结果定位目录，**L3+ 审批**后执行清理命令
4. 清理后再次 `df -i` 并验证服务状态
