/*
 Navicat Premium Dump SQL

 Source Server         : PSQL
 Source Server Type    : PostgreSQL
 Source Server Version : 180003 (180003)
 Source Host           : localhost:5432
 Source Catalog        : yunwei
 Source Schema         : public

 Target Server Type    : PostgreSQL
 Target Server Version : 180003 (180003)
 File Encoding         : 65001

 Date: 29/05/2026 16:26:49
*/


-- ----------------------------
-- Table structure for knowledge_articles
-- ----------------------------
DROP TABLE IF EXISTS "public"."knowledge_articles";
CREATE TABLE "public"."knowledge_articles" (
  "id" varchar(24) COLLATE "pg_catalog"."default" NOT NULL,
  "title" varchar(200) COLLATE "pg_catalog"."default" NOT NULL,
  "category" varchar(64) COLLATE "pg_catalog"."default" NOT NULL,
  "tags" varchar(300) COLLATE "pg_catalog"."default",
  "content" text COLLATE "pg_catalog"."default",
  "source" varchar(64) COLLATE "pg_catalog"."default",
  "severity" varchar(16) COLLATE "pg_catalog"."default",
  "view_count" int4,
  "created_at" timestamp(6),
  "updated_at" timestamp(6)
)
;

-- ----------------------------
-- Records of knowledge_articles
-- ----------------------------
INSERT INTO "public"."knowledge_articles" VALUES ('50467673b01a', '1.1 根目录空间满导致服务无法启动', '磁盘与文件系统问题', '磁盘,文件系统,日志,SSH,服务,systemd,启动,内核', '### 1.1 根目录空间满导致服务无法启动

| 项目 | 内容 |
|---|---|
| **问题编号** | DISK-001 |
| **问题描述** | 根分区使用率接近100%时，系统关键服务（systemd、rsyslog、docker等）因无法写入临时文件或日志而启动失败 |
| **典型表现** | 服务启动报错"No space left on device"；journalctl显示日志写入失败；SSH登录缓慢或失败；df -h显示/分区使用率≥95% |
| **常见诱因** | ①日志文件过度增长（/var/log）；②残留旧内核包（/boot）；③临时文件堆积（/tmp、/var/tmp）；④缓存数据未清理（/var/cache）；⑤应用日志或转储文件（/opt、/home） |
| **排查命令** | `df -h` → `du -sh * \| sort -hr \| head -10` → `du -sh /var/log/* \| sort -hr` → `find / -xdev -type f -size +100M -exec ls -lh {} \;` |
| **解决方案** | ①清理旧日志：`truncate -s 0 /var/log/syslog` 或 `logrotate -f /etc/logrotate.conf`；②卸载冗余软件包：`yum autoremove`；③清理临时文件：`find /tmp -type f -mtime +7 -delete`；④启用logrotate策略；⑤配置磁盘监控告警 |
| **预防措施** | 部署Prometheus+Node Exporter监控，根分区使用率≥85%告警Warning，≥95%告警Critical |', 'imported', 'critical', 0, '2026-05-29 01:21:54.637962', '2026-05-29 01:21:54.637965');
INSERT INTO "public"."knowledge_articles" VALUES ('39fbf43f7198', '1.2 文件系统变为只读', '磁盘与文件系统问题', '磁盘,文件系统,I/O,日志,配置,fsck', '### 1.2 文件系统变为只读

| 项目 | 内容 |
|---|---|
| **问题编号** | DISK-002 |
| **问题描述** | 文件系统突然变为只读模式，无法写入任何文件 |
| **典型表现** | 写入文件报错"Read-only file system"；dmesg中出现EXT4-fs error；系统日志出现remounting read-only |
| **常见诱因** | ①磁盘坏道导致I/O错误；②异常断电导致文件系统元数据损坏；③RAID阵列降级 |
| **排查命令** | `dmesg \| grep -i "error\|read-only\|remount"` → `smartctl -a /dev/sda` → `fsck -n /dev/sda1` |
| **解决方案** | ①进入救援模式执行`fsck -y /dev/sda1`修复文件系统；②如磁盘物理损坏需更换磁盘；③检查RAID状态并重建 |
| **预防措施** | 定期执行`smartctl`检测磁盘健康；配置UPS防止异常断电；启用文件系统日志功能 |', 'imported', 'critical', 0, '2026-05-29 01:21:54.637973', '2026-05-29 01:21:54.637974');
INSERT INTO "public"."knowledge_articles" VALUES ('23bd4463793f', '1.3 磁盘I/O性能瓶颈', '磁盘与文件系统问题', '磁盘,文件系统,I/O,进程,配置,时间同步,性能,负载', '### 1.3 磁盘I/O性能瓶颈

| 项目 | 内容 |
|---|---|
| **问题编号** | DISK-003 |
| **问题描述** | 系统响应缓慢，磁盘I/O等待时间过长 |
| **典型表现** | iostat中%util接近100%；await值持续偏高；系统负载高但CPU使用率不高 |
| **常见诱因** | ①高I/O进程占用；②磁盘碎片化严重；③RAID配置不当；④磁盘老化 |
| **排查命令** | `iostat -x 1 3` → `iotop -aoP` → `pidstat -d 1` |
| **解决方案** | ①优化高I/O进程的读写模式；②将随机I/O改为顺序I/O；③升级为SSD；④调整I/O调度器（deadline/noop） |', 'imported', 'warning', 0, '2026-05-29 01:21:54.637978', '2026-05-29 01:21:54.637979');
INSERT INTO "public"."knowledge_articles" VALUES ('6446a9df2171', '1.4 日志文件过度膨胀', '磁盘与文件系统问题', '磁盘,文件系统,日志,配置', '### 1.4 日志文件过度膨胀

| 项目 | 内容 |
|---|---|
| **问题编号** | DISK-004 |
| **问题描述** | /var/log下日志文件持续增长，占用大量磁盘空间 |
| **典型表现** | 单个日志文件超过1GB；/var/log目录总大小超过5GB |
| **常见诱因** | ①logrotate未正确配置；②应用日志级别设置过低（DEBUG）；③异常事件导致日志爆发式增长 |
| **排查命令** | `du -sh /var/log/* \| sort -hr` → `ls -lh /var/log/syslog*` → `cat /etc/logrotate.conf` |
| **解决方案** | ①配置logrotate策略：按天轮转、压缩归档、保留7天；②调整应用日志级别为INFO/WARN；③手动清理：`truncate -s 0 /var/log/syslog` |

---', 'imported', 'info', 0, '2026-05-29 01:21:54.637982', '2026-05-29 01:21:54.637983');
INSERT INTO "public"."knowledge_articles" VALUES ('60460dd4e00e', '2.1 僵尸进程堆积', '进程与内存问题', '进程,内存,僵尸进程', '### 2.1 僵尸进程堆积

| 项目 | 内容 |
|---|---|
| **问题编号** | PROC-001 |
| **问题描述** | 系统中存在大量Z状态（僵尸）进程，占用进程表项资源 |
| **典型表现** | ps输出中存在大量Z状态进程；系统进程数持续增长；最终可能导致无法创建新进程 |
| **常见诱因** | ①父进程未正确处理SIGCHLD信号；②父进程未调用wait()/waitpid()回收子进程；③程序BUG导致子进程退出后父进程未清理 |
| **排查命令** | `ps -A -o stat,pid,ppid,cmd \| grep -e ''[zZ]''` → `pstree -p <父进程PID>` |
| **解决方案** | ①通知父进程回收：`kill -SIGCHLD <父进程PID>`；②终止产生僵尸进程的父进程：`kill -9 <父进程PID>`；③修复父进程代码，正确处理子进程退出 |
| **预防措施** | 在父进程中注册SIGCHLD信号处理函数；使用waitpid()回收子进程 |', 'imported', 'info', 0, '2026-05-29 01:21:54.637986', '2026-05-29 01:21:54.637987');
INSERT INTO "public"."knowledge_articles" VALUES ('8fd2728f99b7', '2.2 内存泄漏/OOM Killer触发', '进程与内存问题', '进程,内存,OOM,安全,时间同步,国产化', '### 2.2 内存泄漏/OOM Killer触发

| 项目 | 内容 |
|---|---|
| **问题编号** | PROC-002 |
| **问题描述** | 应用程序长时间运行后内存持续增长，最终触发OOM Killer |
| **典型表现** | dmesg中出现"Out of memory"和"Killed process"；系统可用内存持续下降；swap使用率升高 |
| **常见诱因** | ①应用程序内存管理缺陷（未释放已分配内存）；②国产化驱动DMA缓冲区未释放；③安全代理注入共享库导致内存增长 |
| **排查命令** | `free -h` → `vmstat 1 10` → `cat /proc/meminfo` → `ps aux --sort=-%mem \| head -11` → `pmap -x <PID>` → `cat /proc/<PID>/smaps \| grep -i "rss\|size"` |
| **解决方案** | ①临时：重启泄漏进程；②定位：使用gdb附加进程分析内存分配；③排除驱动问题：检查/proc/slabinfo中内核对象缓存增长；④修复应用代码内存管理逻辑 |
| **预防措施** | 部署内存监控告警；定期采样/proc/meminfo绘制趋势图 |', 'imported', 'critical', 0, '2026-05-29 01:21:54.63799', '2026-05-29 01:21:54.637991');
INSERT INTO "public"."knowledge_articles" VALUES ('26b0289e9396', '2.3 系统负载过高', '进程与内存问题', '进程,内存,I/O,负载', '### 2.3 系统负载过高

| 项目 | 内容 |
|---|---|
| **问题编号** | PROC-003 |
| **问题描述** | 系统负载持续偏高，响应缓慢 |
| **典型表现** | uptime显示load average持续高于CPU核心数；top显示CPU使用率接近100% |
| **常见诱因** | ①CPU密集型进程占用；②I/O等待过高；③进程数过多导致上下文切换频繁 |
| **排查命令** | `uptime` → `top -bn1 \| head -20` → `mpstat -P ALL 1 3` → `pidstat -u 1` |
| **解决方案** | ①调整高负载进程优先级：`renice +10 <PID>`；②优化应用代码；③增加CPU资源；④使用cgroups限制资源 |', 'imported', 'warning', 0, '2026-05-29 01:21:54.637994', '2026-05-29 01:21:54.637995');
INSERT INTO "public"."knowledge_articles" VALUES ('5e8f341c9e7e', '2.4 进程崩溃（Segmentation Fault）', '进程与内存问题', '进程,内存,I/O,崩溃,段错误,服务', '### 2.4 进程崩溃（Segmentation Fault）

| 项目 | 内容 |
|---|---|
| **问题编号** | PROC-004 |
| **问题描述** | 进程异常崩溃退出，产生core dump |
| **典型表现** | dmesg中出现"segfault"；/var/log/messages记录进程崩溃信息 |
| **常见诱因** | ①空指针解引用；②缓冲区溢出；③内存越界访问；④库版本不兼容 |
| **排查命令** | `dmesg \| grep -i segfault` → `journalctl -u <服务名> --since "1 hour ago"` → `gdb <程序> <core文件>` |
| **解决方案** | ①分析core dump定位崩溃位置；②检查库版本兼容性；③更新有缺陷的软件包 |

---', 'imported', 'critical', 0, '2026-05-29 01:21:54.637998', '2026-05-29 01:21:54.637999');
INSERT INTO "public"."knowledge_articles" VALUES ('1c32dbf4d84a', '3.1 网络不可达（Network is Unreachable）', '网络问题', '网络,I/O,DNS,网卡,配置', '### 3.1 网络不可达（Network is Unreachable）

| 项目 | 内容 |
|---|---|
| **问题编号** | NET-001 |
| **问题描述** | 系统无法建立网络连接，报错"network is unreachable" |
| **典型表现** | ping网关不通；无法访问外部网络；ifconfig显示网卡未获取IP |
| **常见诱因** | ①网络适配器未正确启用；②IP/网关/DNS配置错误；③网线未连接或网卡驱动异常；④路由表缺失默认网关 |
| **排查命令** | `ip addr` → `ip route` → `ping <网关IP>` → `nmcli device status` → `systemctl status NetworkManager` |
| **解决方案** | ①启用网卡：`nmcli connection up "有线网络1"`；②配置IP：`nmtui`或编辑`/etc/network/interfaces`；③添加默认路由：`ip route add default via <网关IP>`；④重启网络服务：`systemctl restart NetworkManager` |', 'imported', 'info', 0, '2026-05-29 01:21:54.638002', '2026-05-29 01:21:54.638003');
INSERT INTO "public"."knowledge_articles" VALUES ('aa93b9739054', '3.2 端口不通/防火墙阻断', '网络问题', '网络,端口,防火墙,服务', '### 3.2 端口不通/防火墙阻断

| 项目 | 内容 |
|---|---|
| **问题编号** | NET-002 |
| **问题描述** | ping IP地址通但端口不通，服务无法被外部访问 |
| **典型表现** | telnet IP port不通；服务本地可访问但远程无法连接 |
| **常见诱因** | ①防火墙（firewalld）未放行端口；②服务仅监听127.0.0.1；③SELinux阻止 |
| **排查命令** | `ss -tlnp \| grep <端口>` → `systemctl status firewalld` → `firewall-cmd --list-ports` → `netstat -atunlp \| grep <端口>` |
| **解决方案** | ①放行端口：`firewall-cmd --add-port=<端口>/tcp --permanent && firewall-cmd --reload`；②修改服务监听地址为0.0.0.0；③检查SELinux策略 |', 'imported', 'warning', 0, '2026-05-29 01:21:54.638006', '2026-05-29 01:21:54.638007');
INSERT INTO "public"."knowledge_articles" VALUES ('c7940cc367ce', '3.3 网络连接数过高', '网络问题', '网络,内存,防火墙,服务,内核,配置,NTP', '### 3.3 网络连接数过高

| 项目 | 内容 |
|---|---|
| **问题编号** | NET-003 |
| **问题描述** | 系统网络连接数过高导致服务卡顿或中断 |
| **典型表现** | 某服务无法访问但系统可正常登录；内存增高不下；默认最大连接65000，超过20k+服务出现卡顿 |
| **常见诱因** | ①连接未正确释放（TIME_WAIT堆积）；②遭受DDoS攻击；③应用连接池配置不当 |
| **排查命令** | `ss -s` → `netstat -anp \| grep ^tcp \| wc -l` → `netstat -antp \| awk ''{print $5}'' \| cut -d: -f1 \| sort \| uniq -c \| sort -rn \| head` |
| **解决方案** | ①调整内核参数：`sysctl -w net.ipv4.tcp_tw_reuse=1`；②优化应用连接池；③配置防火墙限流规则 |', 'imported', 'warning', 0, '2026-05-29 01:21:54.63801', '2026-05-29 01:21:54.638011');
INSERT INTO "public"."knowledge_articles" VALUES ('09dea2c05355', '3.4 DNS解析失败', '网络问题', '网络,DNS,服务,配置', '### 3.4 DNS解析失败

| 项目 | 内容 |
|---|---|
| **问题编号** | NET-004 |
| **问题描述** | 系统无法解析域名，但IP地址可正常访问 |
| **典型表现** | ping域名失败但ping IP正常；nslookup/dig返回错误 |
| **常见诱因** | ①/etc/resolv.conf中DNS服务器配置错误；②DNS服务器不可达；③/etc/nsswitch.conf配置异常 |
| **排查命令** | `cat /etc/resolv.conf` → `nslookup <域名>` → `dig <域名>` → `ping <DNS服务器IP>` |
| **解决方案** | ①修改/etc/resolv.conf添加正确DNS：`nameserver 114.114.114.114`；②检查DHCP是否正确获取DNS；③使用`chattr +i /etc/resolv.conf`防止被覆盖 |', 'imported', 'warning', 0, '2026-05-29 01:21:54.638014', '2026-05-29 01:21:54.638015');
INSERT INTO "public"."knowledge_articles" VALUES ('9c1c5cb066ec', '3.5 板载网卡驱动不兼容', '网络问题', '网络,I/O,网卡,配置,飞腾', '### 3.5 板载网卡驱动不兼容

| 项目 | 内容 |
|---|---|
| **问题编号** | NET-005 |
| **问题描述** | 银河麒麟V11升级后板载网卡DHCP获取失败、手动IP不通、重启后配置失效 |
| **典型表现** | NetworkManager配置重启后丢失；dmesg中出现CRC错误；USB网卡正常但板载网卡异常 |
| **常见诱因** | ①phytium-dwmac驱动与飞腾平台不兼容；②NetworkManager配置未持久化；③OSTree环境配置不生效 |
| **排查命令** | `dmesg \| grep -i "dwmac\|phytium\|crc"` → `nmcli connection show` → `ethtool -i <网卡名>` |
| **解决方案** | ①优化驱动参数：`options stmmac flow_ctrl=0 rx_delay=16`；②修复NetworkManager配置持久化；③更新initramfs：`update-initramfs -u -k all`；④配置udev规则确保重启后生效 |

---', 'imported', 'warning', 0, '2026-05-29 01:21:54.638018', '2026-05-29 01:21:54.638019');
INSERT INTO "public"."knowledge_articles" VALUES ('f7356f437cbc', '4.1 服务启动失败', '服务管理问题', '服务,systemd,磁盘,端口,启动,权限,配置', '### 4.1 服务启动失败

| 项目 | 内容 |
|---|---|
| **问题编号** | SVC-001 |
| **问题描述** | 系统服务无法正常启动 |
| **典型表现** | systemctl start返回失败；systemctl status显示failed/inactive |
| **常见诱因** | ①配置文件语法错误；②依赖服务未启动；③端口被占用；④权限不足；⑤磁盘空间满 |
| **排查命令** | `systemctl status <服务名>` → `journalctl -u <服务名> --since "1 hour ago"` → `systemctl list-dependencies <服务名>` |
| **解决方案** | ①检查并修复配置文件；②启动依赖服务；③释放被占用的端口；④检查文件权限和磁盘空间 |', 'imported', 'warning', 0, '2026-05-29 01:21:54.638022', '2026-05-29 01:21:54.638023');
INSERT INTO "public"."knowledge_articles" VALUES ('8189813128ff', '4.2 SSH登录失败', '服务管理问题', '服务,systemd,磁盘,端口,防火墙,SSH,启动,配置', '### 4.2 SSH登录失败

| 项目 | 内容 |
|---|---|
| **问题编号** | SVC-002 |
| **问题描述** | 无法通过SSH远程登录系统 |
| **典型表现** | SSH连接超时或拒绝；认证失败；登录缓慢 |
| **常见诱因** | ①sshd服务未运行；②防火墙阻止22端口；③/etc/ssh/sshd_config配置错误；④PAM认证模块异常；⑤磁盘满导致无法写入会话文件 |
| **排查命令** | `systemctl status sshd` → `ss -tlnp \| grep 22` → `cat /var/log/auth.log` → `firewall-cmd --list-ports` |
| **解决方案** | ①启动sshd：`systemctl start sshd`；②放行22端口；③检查sshd_config配置；④检查PAM配置：`cat /etc/pam.d/sshd` |', 'imported', 'warning', 0, '2026-05-29 01:21:54.638026', '2026-05-29 01:21:54.638027');
INSERT INTO "public"."knowledge_articles" VALUES ('7aee5839ca2d', '4.3 图形界面登录闪退', '服务管理问题', '服务,systemd,磁盘,I/O,权限,密码,配置', '### 4.3 图形界面登录闪退

| 项目 | 内容 |
|---|---|
| **问题编号** | SVC-003 |
| **问题描述** | 输入正确用户名密码后，图形界面登录闪退，重新跳转到登录界面 |
| **典型表现** | 登录后黑屏片刻又返回登录界面；.xsession-errors中有错误信息 |
| **常见诱因** | ①用户目录磁盘配额满；②.Xauthority文件权限错误；③图形驱动异常；④/home分区空间不足 |
| **排查命令** | `cat ~/.xsession-errors` → `df -h /home` → `ls -la ~/.Xauthority` → `quota -u <用户名>` |
| **解决方案** | ①清理磁盘空间；②修复.Xauthority权限：`chown <用户>:<用户> ~/.Xauthority`；③重置图形配置：`mv ~/.config ~/.config.bak` |

---', 'imported', 'warning', 0, '2026-05-29 01:21:54.638029', '2026-05-29 01:21:54.63803');
INSERT INTO "public"."knowledge_articles" VALUES ('f721a3727c59', '5.1 系统无故自动重启', '系统启动与内核问题', '内核,启动,I/O,内存,崩溃,Kernel Panic', '### 5.1 系统无故自动重启

| 项目 | 内容 |
|---|---|
| **问题编号** | BOOT-001 |
| **问题描述** | 系统运行过程中无故自动重启 |
| **典型表现** | 系统突然重启，无预警；/var/log/messages中有Kernel panic记录 |
| **常见诱因** | ①内核崩溃（Oops/Panic）；②硬件故障（内存损坏、CPU过热、电源不稳定）；③驱动不兼容；④恶意软件攻击；⑤ACPI电源管理异常 |
| **排查命令** | `dmesg \| grep -i "reboot\|panic"` → `journalctl -b -1` → `cat /var/crash/` → `smartctl -a /dev/sda` → `ipmitool sensor` |
| **解决方案** | ①分析kdump转储文件定位内核崩溃原因；②检测硬件：`memtest86`测试内存；③卸载可疑驱动模块；④更新系统补丁；⑤检查BIOS电源管理设置 |', 'imported', 'critical', 0, '2026-05-29 01:21:54.638033', '2026-05-29 01:21:54.638034');
INSERT INTO "public"."knowledge_articles" VALUES ('167a33ef25df', '5.2 开机停在Logo界面', '系统启动与内核问题', '内核,启动,文件系统,日志,服务,配置,fsck', '### 5.2 开机停在Logo界面

| 项目 | 内容 |
|---|---|
| **问题编号** | BOOT-002 |
| **问题描述** | 系统开机启动后停在银河麒麟Logo界面，无法进入系统 |
| **典型表现** | 开机后一直显示Logo，无进度条；按Esc可看到启动卡在某服务 |
| **常见诱因** | ①文件系统损坏导致fsck检查卡住；②某系统服务启动超时；③图形界面驱动异常 |
| **排查命令** | 开机时按Esc查看详细启动日志 → 进入救援模式检查 |
| **解决方案** | ①进入救援模式执行fsck修复文件系统；②禁用问题服务：`systemctl disable <服务名>`；③重新配置图形驱动 |', 'imported', 'info', 0, '2026-05-29 01:21:54.638037', '2026-05-29 01:21:54.638038');
INSERT INTO "public"."knowledge_articles" VALUES ('821c9a69fb5d', '5.3 非法断电后进入BusyBox', '系统启动与内核问题', '内核,启动,文件系统,BusyBox,fsck', '### 5.3 非法断电后进入BusyBox

| 项目 | 内容 |
|---|---|
| **问题编号** | BOOT-003 |
| **问题描述** | 机器非法断电后无法正常启动，直接进入BusyBox界面 |
| **典型表现** | 启动后进入initramfs的BusyBox shell；提示文件系统需要手动修复 |
| **常见诱因** | 异常断电导致文件系统元数据损坏；fstab中的挂载点不存在 |
| **排查命令** | 在BusyBox中执行`fsck -y /dev/sda1` |
| **解决方案** | ①执行fsck修复：`fsck -y /dev/sda1`；②修复后重启：`reboot`；③如fstab异常，手动挂载根分区修复 |', 'imported', 'critical', 0, '2026-05-29 01:21:54.638041', '2026-05-29 01:21:54.638042');
INSERT INTO "public"."knowledge_articles" VALUES ('efa0410f69f3', '5.4 内核Call Trace', '系统启动与内核问题', '内核,启动,I/O,日志,内存,Kernel Panic', '### 5.4 内核Call Trace

| 项目 | 内容 |
|---|---|
| **问题编号** | BOOT-004 |
| **问题描述** | 系统日志中出现大量Call Trace信息，系统可能hang住 |
| **典型表现** | /var/log/messages中出现list_del corruption、WARNING: CPU: PID等内核调用栈信息；系统短暂hang住 |
| **常见诱因** | ①内核数据结构不一致（如链表操作竞态）；②驱动BUG；③内存损坏导致内核数据结构异常 |
| **排查命令** | `grep -i "call trace\|panic\|oops" /var/log/messages` → `dmesg -T \| grep -i "warning\|bug"` |
| **解决方案** | ①升级内核版本修复已知BUG；②卸载可疑第三方模块；③如为内存问题，运行memtest86检测 |

---', 'imported', 'warning', 0, '2026-05-29 01:21:54.638045', '2026-05-29 01:21:54.638046');
INSERT INTO "public"."knowledge_articles" VALUES ('85b1eab71000', '6.1 用户密码忘记/无法登录', '安全与权限问题', '安全,权限,启动,密码,GRUB', '### 6.1 用户密码忘记/无法登录

| 项目 | 内容 |
|---|---|
| **问题编号** | SEC-001 |
| **问题描述** | 忘记用户密码，无法登录系统 |
| **典型表现** | 输入密码提示认证失败 |
| **解决方案** | ①重启进入GRUB，编辑启动项在linux行末添加`rw init=/bin/bash`；②进入单用户模式后执行`passwd <用户名>`修改密码；③修改后执行`exec /sbin/init`重启 |', 'imported', 'warning', 0, '2026-05-29 01:21:54.638048', '2026-05-29 01:21:54.638049');
INSERT INTO "public"."knowledge_articles" VALUES ('4000a98310ab', '6.2 文件权限错误导致无法访问', '安全与权限问题', '安全,权限,I/O,配置', '### 6.2 文件权限错误导致无法访问

| 项目 | 内容 |
|---|---|
| **问题编号** | SEC-002 |
| **问题描述** | 文件或目录权限设置错误，导致用户无法访问 |
| **典型表现** | Permission denied；无法执行脚本或读取配置文件 |
| **常见诱因** | ①chmod/chown误操作；②应用安装时权限设置不当；③SELinux策略阻止 |
| **排查命令** | `ls -la <路径>` → `namei -l <路径>` → `getenforce` → `audit2why < /var/log/audit/audit.log` |
| **解决方案** | ①修复权限：`chmod 755 <路径>` 或 `chown <用户>:<组> <路径>`；②检查SELinux：`setenforce 0`临时关闭测试；③恢复SELinux上下文：`restorecon -Rv <路径>` |', 'imported', 'info', 0, '2026-05-29 01:21:54.638054', '2026-05-29 01:21:54.638054');
INSERT INTO "public"."knowledge_articles" VALUES ('61a3393f09f8', '6.3 异常登录/入侵检测', '安全与权限问题', '安全,权限,端口,SSH,密码,入侵检测,时间同步', '### 6.3 异常登录/入侵检测

| 项目 | 内容 |
|---|---|
| **问题编号** | SEC-003 |
| **问题描述** | 系统出现异常登录行为或疑似入侵 |
| **典型表现** | /var/log/auth.log中出现大量Failed password记录；发现未知用户；异常时间段的登录记录 |
| **排查命令** | `last -a` → `lastb` → `cat /var/log/auth.log \| grep "Failed password"` → `who` → `ausearch -m USER_LOGIN --start recent` |
| **解决方案** | ①封禁攻击IP：`firewall-cmd --add-rich-rule=''rule family=ipv4 source address=<IP> reject''`；②修改SSH端口；③禁用密码登录，仅允许密钥认证；④部署fail2ban |', 'imported', 'critical', 0, '2026-05-29 01:21:54.638057', '2026-05-29 01:21:54.638058');
INSERT INTO "public"."knowledge_articles" VALUES ('d5dbea5a5336', '6.4 防火墙配置问题', '安全与权限问题', '安全,权限,端口,防火墙,服务,配置', '### 6.4 防火墙配置问题

| 项目 | 内容 |
|---|---|
| **问题编号** | SEC-004 |
| **问题描述** | 防火墙配置不当导致服务无法访问或系统安全风险 |
| **典型表现** | 服务本地可访问但远程不通；防火墙规则混乱 |
| **排查命令** | `systemctl status firewalld` → `firewall-cmd --list-all` → `iptables -L -n` |
| **解决方案** | ①添加服务端口：`firewall-cmd --add-service=<服务> --permanent`；②自定义规则：`firewall-cmd --add-port=<端口>/tcp --permanent`；③重载：`firewall-cmd --reload` |

---', 'imported', 'info', 0, '2026-05-29 01:21:54.638061', '2026-05-29 01:21:54.638062');
INSERT INTO "public"."knowledge_articles" VALUES ('3c4d28fee7a7', '7.1 配置文件漂移', '配置漂移与系统管理问题', '配置,系统管理,服务,安全', '### 7.1 配置文件漂移

| 项目 | 内容 |
|---|---|
| **问题编号** | CFG-001 |
| **问题描述** | 系统配置文件被意外修改导致服务异常 |
| **典型表现** | 服务配置与预期不符；系统行为异常；安全策略被绕过 |
| **常见诱因** | ①人为误修改；②自动化脚本异常；③系统更新覆盖配置；④恶意篡改 |
| **排查命令** | `diff <当前配置> <基线配置>` → `rpm -V <包名>` → `auditctl -l` → `ausearch -f <配置文件路径>` |
| **解决方案** | ①恢复基线配置：`cp <基线配置> <当前配置>`；②锁定关键配置：`chattr +i <文件>`；③部署配置审计：使用auditd监控关键配置文件变更 |
| **预防措施** | 建立配置基线快照；定期执行配置合规检查；使用版本控制管理配置文件 |', 'imported', 'warning', 0, '2026-05-29 01:21:54.638065', '2026-05-29 01:21:54.638066');
INSERT INTO "public"."knowledge_articles" VALUES ('9a6a6872c1c9', '7.2 系统时间不同步', '配置漂移与系统管理问题', '配置,系统管理,日志,服务,时间同步,NTP', '### 7.2 系统时间不同步

| 项目 | 内容 |
|---|---|
| **问题编号** | CFG-002 |
| **问题描述** | 系统时间不准确，导致日志时间戳错误、证书验证失败等 |
| **典型表现** | 日志时间与实际时间不符；HTTPS证书验证失败；定时任务执行时间错误 |
| **排查命令** | `date` → `timedatectl status` → `ntpq -p` |
| **解决方案** | ①同步时间：`ntpdate <NTP服务器>`；②启用chronyd：`systemctl enable --now chronyd`；③设置时区：`timedatectl set-timezone Asia/Shanghai` |', 'imported', 'warning', 0, '2026-05-29 01:21:54.638069', '2026-05-29 01:21:54.63807');
INSERT INTO "public"."knowledge_articles" VALUES ('0f6cf650e619', '7.3 内核参数调优', '配置漂移与系统管理问题', '配置,系统管理,网络,内核,性能', '### 7.3 内核参数调优

| 项目 | 内容 |
|---|---|
| **问题编号** | CFG-003 |
| **问题描述** | 系统默认内核参数不适合高并发/高性能场景 |
| **典型表现** | TCP连接数受限；文件描述符不足；网络性能不佳 |
| **常见调优参数** | ①`net.ipv4.tcp_tw_reuse=1`（复用TIME_WAIT连接）；②`net.core.somaxconn=65535`（增大监听队列）；③`vm.swappiness=10`（减少swap使用）；④`fs.file-max=65535`（增大文件描述符限制） |
| **配置方式** | 编辑`/etc/sysctl.conf` → `sysctl -p`生效 |

---', 'imported', 'info', 0, '2026-05-29 01:21:54.638073', '2026-05-29 01:21:54.638074');
INSERT INTO "public"."knowledge_articles" VALUES ('30867eb5bb37', '9.1 飞腾平台网卡兼容性', '国产化平台特有问题', '国产化,网卡,配置,飞腾', '### 9.1 飞腾平台网卡兼容性

| 项目 | 内容 |
|---|---|
| **问题编号** | PLAT-001 |
| **问题描述** | 飞腾FT2000+银河麒麟V11板载网卡不兼容 |
| **典型表现** | DHCP获取失败、手动IP不通、ping网关无响应、重启后配置失效 |
| **解决方案** | ①优化驱动参数：配置`/etc/modprobe.d/phytium-dwmac.conf`；②修复NetworkManager配置持久化；③更新initramfs；④配置udev规则 |', 'imported', 'warning', 0, '2026-05-29 01:21:54.638077', '2026-05-29 01:21:54.638078');
INSERT INTO "public"."knowledge_articles" VALUES ('e945dbb323ce', '9.2 龙芯平台软件兼容性', '国产化平台特有问题', '国产化,龙芯', '### 9.2 龙芯平台软件兼容性

| 项目 | 内容 |
|---|---|
| **问题编号** | PLAT-002 |
| **问题描述** | 龙芯LoongArch架构下部分软件包不可用或行为异常 |
| **典型表现** | 软件包安装失败；二进制文件无法执行 |
| **解决方案** | ①使用LoongArch架构专用软件源；②从源码编译安装；③联系软件厂商提供龙芯适配版本 |', 'imported', 'warning', 0, '2026-05-29 01:21:54.638081', '2026-05-29 01:21:54.638082');
INSERT INTO "public"."knowledge_articles" VALUES ('61302360838a', '9.3 内核版本差异', '国产化平台特有问题', '国产化,内核', '### 9.3 内核版本差异

| 项目 | 内容 |
|---|---|
| **问题编号** | PLAT-003 |
| **问题描述** | 银河麒麟V11采用6.6内核，部分旧驱动/模块不兼容 |
| **典型表现** | 内核模块加载失败；系统调用行为变化导致应用异常 |
| **解决方案** | ①确认驱动/模块是否支持6.6内核；②联系厂商更新驱动；③必要时回退到兼容内核版本 |

---', 'imported', 'warning', 0, '2026-05-29 01:21:54.638085', '2026-05-29 01:21:54.638086');
INSERT INTO "public"."knowledge_articles" VALUES ('2ec1f9f1237e', '高级安装ARM版本系统，新建分区sda1必须是/boot分区，sda2是根分区？', '常见-安装问题', '安装,系统安装,部署,分区', '## 高级安装ARM版本系统，新建分区sda1必须是/boot分区，sda2是根分区？

**分类**: 安装问题

是的。且这两个分区类型必须是主分区，除这两个分区外其他分区类型可选择主分区或逻辑分区，但单个硬盘的主分区数量不超过4个', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638089', '2026-05-29 01:21:54.63809');
INSERT INTO "public"."knowledge_articles" VALUES ('a19f82f4d2ea', '用光盘安装或者U盘安装时，无法进入安装界面问题', '常见-安装问题', '安装,系统安装,部署,U盘,光盘,BIOS', '## 用光盘安装或者U盘安装时，无法进入安装界面问题

**分类**: 安装问题

更改bios设置：在Security选项卡下面将Secure boot改为Disable;在Startup选项卡下面，将UEFI/LEGACY BOOT 改为Both或者LEGACY First.', 'faq_imported', 'critical', 0, '2026-05-29 01:21:54.638093', '2026-05-29 01:21:54.638094');
INSERT INTO "public"."knowledge_articles" VALUES ('b5d537f3db14', '麒麟系统无法安装，或安装失败？', '常见-安装问题', '安装,系统安装,部署,光盘', '## 麒麟系统无法安装，或安装失败？

**分类**: 安装问题

①　检查架构是否一致，X86系统无法安装在FT机器，同理，FT系统也不能装在X86硬件上。

②　检查安装介质是否有问题，排除光盘、光驱问题

③　引导选项配置确认', 'faq_imported', 'critical', 0, '2026-05-29 01:21:54.638097', '2026-05-29 01:21:54.638098');
INSERT INTO "public"."knowledge_articles" VALUES ('d4c6c1e98a1e', '安装系统卡死，无法进行，报“call Trace”', '常见-安装问题', '安装,系统安装,部署,GRUB', '## 安装系统卡死，无法进行，报“call Trace”

**分类**: 安装问题

①　开机进入系统引导界面，根据下方提示按“e”进入grub界面

②　在Linux行末加上，acpi=off', 'faq_imported', 'critical', 0, '2026-05-29 01:21:54.638101', '2026-05-29 01:21:54.638101');
INSERT INTO "public"."knowledge_articles" VALUES ('7a843a9aefd5', '无法获知系统的安装时间', '常见-安装问题', '安装,系统安装,部署', '## 无法获知系统的安装时间

**分类**: 安装问题

用tune2fs -l /dev/sda1 | grep Filesystem命令来获知文件系统创建时间，作为装机时间的参考', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638104', '2026-05-29 01:21:54.638105');
INSERT INTO "public"."knowledge_articles" VALUES ('5a76f9352976', '如何使用ghost镜像安装系统', '常见-安装问题', '安装,系统安装,部署,U盘,livecd,ghost,挂载', '## 如何使用ghost镜像安装系统

**分类**: 安装问题

需要进livecd挂载，手动挂载有ghost镜像的U盘，然后点击桌面的安装，选择ghost安装，找到U盘的ghost镜像', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638108', '2026-05-29 01:21:54.638109');
INSERT INTO "public"."knowledge_articles" VALUES ('4accc518cbaf', '安装系统时，怎么进入BIOS界面？', '常见-安装问题', '安装,系统安装,部署,BIOS', '## 安装系统时，怎么进入BIOS界面？

**分类**: 安装问题

请重启机器,等待片刻,待屏幕出现硬件的LOGO时,按DEL键即可进入BIOS,按ESC键退出BIOS

【注1】：不同机器需要按的键不一样,可根据提示或者百度得知

【注2】：进入BIOS的提示的停留时间很短,请抓住机会', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.638112', '2026-05-29 01:21:54.638113');
INSERT INTO "public"."knowledge_articles" VALUES ('e9844e848c91', '装银河麒麟系统 一直停在“正在复制文件”，需要的时间比较长', '常见-安装问题', '安装,系统安装,部署', '## 装银河麒麟系统 一直停在“正在复制文件”，需要的时间比较长

**分类**: 安装问题

这个是正常的,有时候半小时也是正常的,请耐心等待。', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638116', '2026-05-29 01:21:54.638117');
INSERT INTO "public"."knowledge_articles" VALUES ('a99234237ac5', '麒麟系统如何使用ghost安装', '常见-安装问题', '安装,系统安装,部署,U盘,光盘,livecd,ghost', '## 麒麟系统如何使用ghost安装

**分类**: 安装问题

①　打开麒麟备份还原工具,先将原来系统全盘备份一次,然后做成ghost文件

②　把ghost文件拷贝u盘

③　用光盘引导进livecd,然后双击安装系统,镜像来源处,选择”从ghost镜像安装“,然后浏览选中u盘中ghost文件

④　点击”下一步“,后面的步骤跟光盘装系统一样', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.63812', '2026-05-29 01:21:54.638121');
INSERT INTO "public"."knowledge_articles" VALUES ('37e8bb9bde27', '装系统一般需要要多久时间', '常见-安装问题', '安装,系统安装,部署', '## 装系统一般需要要多久时间

**分类**: 安装问题

一般需要半小时到一小时', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638124', '2026-05-29 01:21:54.638124');
INSERT INTO "public"."knowledge_articles" VALUES ('3828f906de72', '银河麒麟系统装在ft2000上面卡死了', '常见-安装问题', '安装,系统安装,部署', '## 银河麒麟系统装在ft2000上面卡死了

**分类**: 安装问题

请确认系统是否是ft2000的,若系统是ft1500的,则会安装失败', 'faq_imported', 'critical', 0, '2026-05-29 01:21:54.638128', '2026-05-29 01:21:54.638128');
INSERT INTO "public"."knowledge_articles" VALUES ('c11913b1a5f6', '怎么安排人上门安装系统', '常见-安装问题', '安装,系统安装,部署', '## 怎么安排人上门安装系统

**分类**: 安装问题

请联系对应商务处理（给您提供系统的负责人）', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638131', '2026-05-29 01:21:54.638132');
INSERT INTO "public"."knowledge_articles" VALUES ('a2555f34ba49', '如何安装麒麟系统', '常见-安装问题', '安装,系统安装,部署,U盘,光盘', '## 如何安装麒麟系统

**分类**: 安装问题

①　安装引导开机启动,将光盘置入光驱中或者把启动U盘插入USB口。按 Del 键(不同的硬件按键不一样)进入固件管理界面。通过上下方向键选择第三项“启动管理”,回车后进入启动引导界面。

②　引导成功光盘或U盘引导步骤完成之后,连续按两次退出键(Esc)退出固件管理界面。此时系统已成功设置光盘或 U 盘启动,只需等待系统进入安装界面。双击图标 “安装 Kylin 0”进行安装。（以Kylin 0为例）

③　系统安装勾选“创建备份还原分区”和“创建数据盘”选择“快速安装”，点击“快速安装”。输入正确的相关信息后，点击“继续”。等待约 10 分钟左右后，完成安装。', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638135', '2026-05-29 01:21:54.638136');
INSERT INTO "public"."knowledge_articles" VALUES ('ca06f0d28a5b', '使用自动化pxe安装操作系统后语言设置失败,脚本上写的是中文,安装好操作系统后却是英文', '常见-安装问题', '安装,系统安装,部署,PXE', '## 使用自动化pxe安装操作系统后语言设置失败,脚本上写的是中文,安装好操作系统后却是英文

**分类**: 安装问题

这应该是配置文件有误,具体修复办法如下：

①　登录系统,打开终端,输入：cat /etc/default/locale |grep LANG=，看一下输出结果是否显示为：LANG=''en_US:UTF-8''

②　修改/etc/default/locale文件内容,将LANG这一行修改为：LANG="zh_CN.UTF-8

③　重启系统即可', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.638139', '2026-05-29 01:21:54.63814');
INSERT INTO "public"."knowledge_articles" VALUES ('13d8d3718f9f', '如何用光驱/U盘启动', '常见-安装问题', '安装,系统安装,部署,U盘,BIOS', '## 如何用光驱/U盘启动

**分类**: 安装问题

请在BIOS里面将第一启动项设置为光驱/ U盘', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638143', '2026-05-29 01:21:54.638144');
INSERT INTO "public"."knowledge_articles" VALUES ('68bd845bcc5c', '如何获取光盘和镜像', '常见-安装问题', '安装,系统安装,部署,光盘,授权', '## 如何获取光盘和镜像

**分类**: 安装问题

光盘和镜像都是需要找商务购买正式授权获取的或者麒麟软件官网——>“试用”，填写完对应的试用模块即可获取到V10系统的镜像文件', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638147', '2026-05-29 01:21:54.638148');
INSERT INTO "public"."knowledge_articles" VALUES ('0e9cfc590d6b', '麒麟有没有u盘启动制作工具', '常见-安装问题', '安装,系统安装,部署,U盘,光盘,dd命令,rsync,挂载', '## 麒麟有没有u盘启动制作工具

**分类**: 安装问题

暂时没有该工具，可以试用命令制作U盘启动：

①　sudo dd if=xxxx.iso of=/dev/sdb

xxx.iso为镜像文件名，/dev/sdb为U盘挂载点

②　sudo rsync -a /mnt/ /mnt2/

其中/mnt是光盘挂载的目录，/mnt2是u盘挂载的目录', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638151', '2026-05-29 01:21:54.638151');
INSERT INTO "public"."knowledge_articles" VALUES ('9f045c15a242', 'U盘启动U盘要什么格式', '常见-安装问题', '安装,系统安装,部署,U盘', '## U盘启动U盘要什么格式

**分类**: 安装问题

需要是ext4格式的', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638154', '2026-05-29 01:21:54.638155');
INSERT INTO "public"."knowledge_articles" VALUES ('5265fffc485f', '未接显示器时,启动系统失败', '常见-启动问题', '启动,引导,开机', '## 未接显示器时,启动系统失败

**分类**: 启动问题

删除/lib/aarch64-linux-gnu/plymouth/renderers/frame-buffer.so文件', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.638158', '2026-05-29 01:21:54.638159');
INSERT INTO "public"."knowledge_articles" VALUES ('cc7518c4e633', '开机启动停在银河麒麟logo界面', '常见-启动问题', '启动,引导,开机,光盘,livecd,分区,挂载,mount', '## 开机启动停在银河麒麟logo界面

**分类**: 启动问题

用光盘启动进livecd,检查分区是否挂载,若挂载则卸载,对系统根分区进行fsck:

sudo mount /dev/sda1 /mnt

sudo fsck -y /dev/sda1

sudo umount /dev/sda1

sudo mount /dev/sda2 /mnt

sudo fsck -y /dev/sda2

sudo umount /dev/sda2

sudo reboot', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638162', '2026-05-29 01:21:54.638163');
INSERT INTO "public"."knowledge_articles" VALUES ('1b3bb6b4fb45', '系统开机启动某服务，如下演示开机启动ssh服务', '常见-启动问题', '启动,引导,开机,SSH,sudo', '## 系统开机启动某服务，如下演示开机启动ssh服务

**分类**: 启动问题

在终端中执行以下命令：

sudo systemctl enable ssh', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638166', '2026-05-29 01:21:54.638167');
INSERT INTO "public"."knowledge_articles" VALUES ('093f696d320e', '机器非法断电导致进不去系统，如开机之后直接进入busybox界面', '常见-启动问题', '启动,引导,开机,分区,BusyBox,sudo', '## 机器非法断电导致进不去系统，如开机之后直接进入busybox界面

**分类**: 启动问题

在busybox界面先执行exit命令看下具体是因为那个分区的损坏导致进不去的系统，然后使用fsck命令对分区进行修复：

exit

sudo fsck /dev/sda2(如是/dev/sda2的分区损坏)', 'faq_imported', 'critical', 0, '2026-05-29 01:21:54.638172', '2026-05-29 01:21:54.638173');
INSERT INTO "public"."knowledge_articles" VALUES ('f96b441359af', '安装好系统无法启动', '常见-启动问题', '启动,引导,开机,sudo', '## 安装好系统无法启动

**分类**: 启动问题

进救援模式下在/etc/modprobe.d/blacklist.conf文件中添加blacklist xhci_hcd参数

sudo pluma /etc/modprobe.d/blacklist.conf', 'faq_imported', 'critical', 0, '2026-05-29 01:21:54.638178', '2026-05-29 01:21:54.638179');
INSERT INTO "public"."knowledge_articles" VALUES ('5d53d0d63167', '图形界面登录闪退，或输入正确用户名密码重新跳转到登录界面', '常见-登录问题', '登录,认证,密码,分区,输入法,权限', '## 图形界面登录闪退，或输入正确用户名密码重新跳转到登录界面

**分类**: 登录问题

有两个常见原因

①　磁盘原因：可能” / ”分区被占满，ctrl+alt+F2切换到文本界面登录，命令行执行:df -h，如若/分区使用率高达100%，此时将个人的数据文件删除（不可删除系统重要文件，且用户重要数据需备份）；也可查看/tmp目录下是否有搜狗输入法产生的大量core文件，删除即可

②　权限问题：切到后台，进入主目录，chown -R 用户名:用户名 .Xauthority,如仍解决不了问题,查看~.xesession-error日志,借助日志解决问题,如出现private socket dir:Permission denied,执行chmod 777 /tmp，修改/tmp权限', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.638184', '2026-05-29 01:21:54.638186');
INSERT INTO "public"."knowledge_articles" VALUES ('799ef486e8cd', '忘记用户密码', '常见-登录问题', '登录,认证,密码,光盘,GRUB,livecd', '## 忘记用户密码

**分类**: 登录问题

默认密码为123123，也可通过管理员用户使用passwd修改用户密码;如忘记管理员用户密码有三种方式恢复：

①　第一种：从grub进到单用户模式，修改用户密码

②　第二种：可将光盘放进光驱,重启系统进入livecd模式，命令行修改密码或/etc/shadow文件中的密码字段,将其置换成某已知密码的字段（目前仅针对桌面系统）

③　第三种：livecd模式下，备份重要数据，还原系统', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.63819', '2026-05-29 01:21:54.638192');
INSERT INTO "public"."knowledge_articles" VALUES ('7cd8099bab7e', '新建用户在锁屏界面,不显示用户名或显示为unknown', '常见-登录问题', '登录,认证,密码', '## 新建用户在锁屏界面,不显示用户名或显示为unknown

**分类**: 登录问题

查看mate-screensaver-preference包版本,并升级此软件包', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638197', '2026-05-29 01:21:54.638198');
INSERT INTO "public"."knowledge_articles" VALUES ('a392f7a00717', '禁止root用户登录的问题', '常见-登录问题', '登录,认证,密码,root,sudo,权限', '## 禁止root用户登录的问题

**分类**: 登录问题

由于root用户几乎拥有所有的权限，为了避免误操作导致系统出现问题，提高系统的安全性，故安装完系统后，默认root密码随机更换，并禁止以root用户登录。若需要使用到root用户的权限，可以使用sudo命令；若需要切换到root用户，可以使用“sudo -i”命令，以保证root密码的随机性。', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.638203', '2026-05-29 01:21:54.638205');
INSERT INTO "public"."knowledge_articles" VALUES ('dd5a3e2b9d3c', '如何激活系统', '常见-激活问题', '激活,授权,license', '## 如何激活系统

**分类**: 激活问题

要激活系统前得满足三个条件:（针对二维码激活）

①　有正式授权书（需要购买正式授权）

②　成为系统激活管理员（找对应商务获取绑定激活管理员的二维码）

③　保证当前系统与正式授权版本一致

激活步骤：（可找客服要对应的激活手册）

①　右击“我的电脑”——“属性”，选择“激活”

②　如果您的服务序列号为七位数的批次号，且没有激活二维码。就需要将正式授权书上的服务序列号编辑进系统里，然后就会出现对应的激活的二维码。如果一打开这个界面就有激活二维码就不需要进行这步操作。

③　然后使用绑定了“激活管理员”的微信号，扫描机器上的“激活二维码”，并且将正式授权书上的验证码填写进去即可获取到对应的激活码。

④　将获取到的激活码填写进系统里面，点击“激活/延长服务”即可', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638213', '2026-05-29 01:21:54.638214');
INSERT INTO "public"."knowledge_articles" VALUES ('cd80b45ca64a', '第三方软件怎么激活（永中office 、wps、360浏览器.......）？', '常见-激活问题', '激活,授权,license,WPS,浏览器', '## 第三方软件怎么激活（永中office 、wps、360浏览器.......）？

**分类**: 激活问题

请咨询第三方软件客服', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638219', '2026-05-29 01:21:54.63822');
INSERT INTO "public"."knowledge_articles" VALUES ('833b3ae6b1af', '激活怎么绑定管理员？', '常见-激活问题', '激活,授权,license,微信', '## 激活怎么绑定管理员？

**分类**: 激活问题

请联系商务或者代理商获取绑定激活管理员的二维码，使用微信扫描上面的二维码进行绑定即可', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638226', '2026-05-29 01:21:54.638228');
INSERT INTO "public"."knowledge_articles" VALUES ('7d7d5cb98c4b', '试用版本能激活系统吗？', '常见-激活问题', '激活,授权,license', '## 试用版本能激活系统吗？

**分类**: 激活问题

试用版本无法激活,若需激活,需购买正式版本服务序列号', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638233', '2026-05-29 01:21:54.638234');
INSERT INTO "public"."knowledge_articles" VALUES ('ac54d30715d5', '绑定激活权限过期怎么办,还可以激活吗？', '常见-激活问题', '激活,授权,license,权限', '## 绑定激活权限过期怎么办,还可以激活吗？

**分类**: 激活问题

绑定激活权限过期之后,激活管理员无法再激活系统,若需激活系统,需联系对应提供系统的商务', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638249', '2026-05-29 01:21:54.638251');
INSERT INTO "public"."knowledge_articles" VALUES ('c1abac264b54', '系统激活过期对操作有什么影响吗？', '常见-激活问题', '激活,授权,license', '## 系统激活过期对操作有什么影响吗？

**分类**: 激活问题

对使用无影响。会有激活到期提示,不能再享受售后服务', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638257', '2026-05-29 01:21:54.638258');
INSERT INTO "public"."knowledge_articles" VALUES ('eee54d73e5ce', '服务序列号和验证码有什么用处？', '常见-激活问题', '激活,授权,license', '## 服务序列号和验证码有什么用处？

**分类**: 激活问题

服务序列号用于验证是否为正式版本,验证码是激活系统使用的', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638268', '2026-05-29 01:21:54.638278');
INSERT INTO "public"."knowledge_articles" VALUES ('1f9df922a8f9', '激活页面没有二维码？', '常见-激活问题', '激活,授权,license', '## 激活页面没有二维码？

**分类**: 激活问题

请将正式授权的服务序列号和单位编辑进去,即可显示激活二维码', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638283', '2026-05-29 01:21:54.638284');
INSERT INTO "public"."knowledge_articles" VALUES ('390c8a019e1b', '一个激活码可以激活多台机器吗？', '常见-激活问题', '激活,授权,license', '## 一个激活码可以激活多台机器吗？

**分类**: 激活问题

不可以，一个激活码只能激活一台机器', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638289', '2026-05-29 01:21:54.638291');
INSERT INTO "public"."knowledge_articles" VALUES ('3c123fb41142', '激活期限到期怎么办？', '常见-激活问题', '激活,授权,license', '## 激活期限到期怎么办？

**分类**: 激活问题

请咨询商务来延期', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638296', '2026-05-29 01:21:54.638298');
INSERT INTO "public"."knowledge_articles" VALUES ('ffeaeb4bb2aa', '点击“激活”按钮，激活界面一直出不来怎么办？', '常见-激活问题', '激活,授权,license,sudo', '## 点击“激活”按钮，激活界面一直出不来怎么办？

**分类**: 激活问题

执行命令：kylin-activation 或者执行命令：sudo kylin-system-verify', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638303', '2026-05-29 01:21:54.638304');
INSERT INTO "public"."knowledge_articles" VALUES ('ec6205ab3953', '打开激活窗口显示“系统文件检测失败”,且没有二维码', '常见-激活问题', '激活,授权,license,sudo', '## 打开激活窗口显示“系统文件检测失败”,且没有二维码

**分类**: 激活问题

命令输入：sudo rm -rf /etc/.kyhwid', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.638309', '2026-05-29 01:21:54.638311');
INSERT INTO "public"."knowledge_articles" VALUES ('b0874567b59b', '如何查看系统到期期限？', '常见-激活问题', '激活,授权,license', '## 如何查看系统到期期限？

**分类**: 激活问题

命令行查看：打开一个终端,输入cat /etc/.kyinfo,回车,term字段的内容即为到期期限；

图形界面查看：右键下方任务栏,点击“关于银河麒麟”字段“技术服务截止日期”即为到期期限。', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638316', '2026-05-29 01:21:54.638317');
INSERT INTO "public"."knowledge_articles" VALUES ('0a942b6a3590', '系统已经激活,重装之后还需要再次激活吗', '常见-激活问题', '激活,授权,license', '## 系统已经激活,重装之后还需要再次激活吗

**分类**: 激活问题

若重装时未更换硬件,可以使用之前的激活码再次对系统进行激活

若重装时更换过硬件,请联系商务处理', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638323', '2026-05-29 01:21:54.638324');
INSERT INTO "public"."knowledge_articles" VALUES ('5a0ee8b79596', '一个服务序列号能激活几台机器？', '常见-激活问题', '激活,授权,license', '## 一个服务序列号能激活几台机器？

**分类**: 激活问题

一个服务序列号能激活几台机器是取决于所签订合同的', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.63833', '2026-05-29 01:21:54.638331');
INSERT INTO "public"."knowledge_articles" VALUES ('ffbd6e0ab7a1', '重装系统 之后再次激活，没有更换过硬件。再次激活的时候发现注册码发生改变，会提示激活的名额已经用完，怎么处理？', '常见-激活问题', '激活,授权,license,apt,sudo', '## 重装系统 之后再次激活，没有更换过硬件。再次激活的时候发现注册码发生改变，会提示激活的名额已经用完，怎么处理？

**分类**: 激活问题

开始菜单——>所有程序——>麒麟助手——>系统信息——>硬盘。看下 设备名是否是：/dev/nvme0（这个型号的会导致系统重启注册码发生改变）

如果是的话，需要升级libkylin-activation的软件包之后，然后重启机器观察 下注册码是否还会发生改变。

①　升级libkylin-activation包命令：sudo apt install libkylin-activation

②　找对应商务说明情况，取消之前的激活。使用命令：sudo kylin_gen_register，可查出需要取消激活的注册码。

③　重新对系统进行激活。', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.638336', '2026-05-29 01:21:54.638338');
INSERT INTO "public"."knowledge_articles" VALUES ('1ea33a66bd34', '之前使用ukey激活，ukey丢了,可以使用二维码激活吗？', '常见-激活问题', '激活,授权,license,ukey', '## 之前使用ukey激活，ukey丢了,可以使用二维码激活吗？

**分类**: 激活问题

不可以,建议找商务重新申请ukey。使用ukey激活的后续就只能通过ukey激活(如未同步到激活平台，则只能使用ukey激活)', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638343', '2026-05-29 01:21:54.638345');
INSERT INTO "public"."knowledge_articles" VALUES ('549dcb4621a6', '银河麒麟系统激活之后硬件（主板、硬盘...）坏了,更换硬件的话需要再一次激活吗？', '常见-激活问题', '激活,授权,license', '## 银河麒麟系统激活之后硬件（主板、硬盘...）坏了,更换硬件的话需要再一次激活吗？

**分类**: 激活问题

更换过硬件之前的激活码是不能在用了,因为激活码是和硬件绑定到一起的,建议找商务再去要一个激活名额。', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.63835', '2026-05-29 01:21:54.63836');
INSERT INTO "public"."knowledge_articles" VALUES ('0a69578e283b', '激活界面报错，如“授权文件异常”', '常见-激活问题', '激活,授权,license', '## 激活界面报错，如“授权文件异常”

**分类**: 激活问题

删除/etc/.kyactivation后，重新替换授权文件，需保证系统时间与硬件时间正确', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.638365', '2026-05-29 01:21:54.638366');
INSERT INTO "public"."knowledge_articles" VALUES ('061c7423e058', '系统在一年授权到期后每次开机需按s跳过，开机会有系统已过期的提示', '常见-激活问题', '激活,授权,license', '## 系统在一年授权到期后每次开机需按s跳过，开机会有系统已过期的提示

**分类**: 激活问题

已制作补丁包，去掉按s跳过的步骤和过期提示', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638372', '2026-05-29 01:21:54.638373');
INSERT INTO "public"."knowledge_articles" VALUES ('afb5ded0e4a0', '输入错误激活码导致系统服务期限异常', '常见-激活问题', '激活,授权,license,sudo', '## 输入错误激活码导致系统服务期限异常

**分类**: 激活问题

删除/etc/.kyactivation后,重新输入正确的激活码。替换激活文件，执行sudo kylin_activation_check显示错误的序列号', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.638379', '2026-05-29 01:21:54.63838');
INSERT INTO "public"."knowledge_articles" VALUES ('02a68e740037', '之前是试用版本,已购买正式版本服务序列号,如何激活？（这个是针对6位序列号的）', '常见-激活问题', '激活,授权,license,光盘,浏览器,挂载,sudo', '## 之前是试用版本,已购买正式版本服务序列号,如何激活？（这个是针对6位序列号的）

**分类**: 激活问题

若试用版本和正式版本的版本一致,可以直接替换授权文件,然后进行激活操作，具体步骤如下：

①　将光盘放置到光驱,打开文件浏览器 后,将目录切换至光盘挂载目录,一般为/media/kylin/KYLIN-V4

②　在/media/kylin/KYLIN-V4目录的空白处右键选择“在终端中打开”,在命令行输入以下两行命令：

sudo cp LICENSE /etc/

sudo cp .kyinfo /etc/

③　然后根据激活步骤激活

若试用版本和正式版本的版本不一致,则需重装系统后再进行激活操作,具体步骤如下：右键我的电脑,点击”属性“,选择激活,获取激活二维码后,然后根据激活步骤激活', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638385', '2026-05-29 01:21:54.638387');
INSERT INTO "public"."knowledge_articles" VALUES ('601204480b46', '激活系统报“文件检测失败错误码#0014”', '常见-激活问题', '激活,授权,license', '## 激活系统报“文件检测失败错误码#0014”

**分类**: 激活问题

若请检查您的系统时间是否准确,若不准确,请修改系统时间后,再次尝试激活', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.638392', '2026-05-29 01:21:54.638394');
INSERT INTO "public"."knowledge_articles" VALUES ('8ad4173494a1', '银河麒麟系统已经激活过的如何看本机的注册码呢？', '常见-激活问题', '激活,授权,license,sudo', '## 银河麒麟系统已经激活过的如何看本机的注册码呢？

**分类**: 激活问题

使用命令：sudo kylin_gen_register', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.6384', '2026-05-29 01:21:54.638401');
INSERT INTO "public"."knowledge_articles" VALUES ('a01a17c144ce', '系统在试用期内,但报“System Unauthorized”错误？', '常见-激活问题', '激活,授权,license,BIOS', '## 系统在试用期内,但报“System Unauthorized”错误？

**分类**: 激活问题

请检查主板上的BIOS电池是否有电,确保有电后,手动修改正确日期后,重启即可', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.638406', '2026-05-29 01:21:54.638408');
INSERT INTO "public"."knowledge_articles" VALUES ('a8afd1ed4333', '不小心在光盘试用模式激活怎么办？', '常见-激活问题', '激活,授权,license,光盘', '## 不小心在光盘试用模式激活怎么办？

**分类**: 激活问题

这种情况下不能取消激活,请联系商务再增加一个激活名额', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638413', '2026-05-29 01:21:54.638415');
INSERT INTO "public"."knowledge_articles" VALUES ('1efa2c0cef43', '过期提示能不能隐藏？', '常见-激活问题', '激活,授权,license', '## 过期提示能不能隐藏？

**分类**: 激活问题

过期提示是无法隐藏的', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.63842', '2026-05-29 01:21:54.638421');
INSERT INTO "public"."knowledge_articles" VALUES ('01cf17f8e31c', '激活页面提示错误代码#0048？', '常见-激活问题', '激活,授权,license', '## 激活页面提示错误代码#0048？

**分类**: 激活问题

一种情况是,更新软件源后upgrade升级了所有包,导致系统很多文件和环境被破坏,恢复工程量较大,条件允许的话,建议重装系统', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.638427', '2026-05-29 01:21:54.638428');
INSERT INTO "public"."knowledge_articles" VALUES ('bdf3493478fb', '命令行激活显示硬件信息错误？', '常见-激活问题', '激活,授权,license,sudo', '## 命令行激活显示硬件信息错误？

**分类**: 激活问题

删除/etc/.kyhwid即可，执行命令：sudo rm -rf /etc/.kyhwid', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.638433', '2026-05-29 01:21:54.638435');
INSERT INTO "public"."knowledge_articles" VALUES ('9069735cc485', '替换授权文件提示权限不足？', '常见-激活问题', '激活,授权,license,sudo,权限', '## 替换授权文件提示权限不足？

**分类**: 激活问题

可使用命令替换，在授权文件的目录下，打开终端

执行命令：sudo cp .kyinfo /etc/.kyinfo

执行命令：sudo cp LICENSE /etc/LICENSE', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.63844', '2026-05-29 01:21:54.638441');
INSERT INTO "public"."knowledge_articles" VALUES ('f4ecaa7fdc08', '激活界面报0017错误代码,且执行kylin_activation_check报无法获取硬件信息？', '常见-激活问题', '激活,授权,license,sudo', '## 激活界面报0017错误代码,且执行kylin_activation_check报无法获取硬件信息？

**分类**: 激活问题

移走/etc/.kyhwid文件解决，执行命令：sudo rm -rf /etc/.kyhwid', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.638447', '2026-05-29 01:21:54.638448');
INSERT INTO "public"."knowledge_articles" VALUES ('381faf518061', '替换激活文件，执行sudo kylin_activation_check显示错误的序列号', '常见-激活问题', '激活,授权,license,root,sudo', '## 替换激活文件，执行sudo kylin_activation_check显示错误的序列号

**分类**: 激活问题

执行rm -rf ~/.gnupg,rm -rf /root/.gnupg,rm -rf /etc.kyhwid，然后再替换激活文件。', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.638453', '2026-05-29 01:21:54.638455');
INSERT INTO "public"."knowledge_articles" VALUES ('d7f17de57090', '麒麟没有激活系统,输入命令经常提醒权限不够，无法通过管理员安装软件或运行有执行权限脚本', '常见-权限问题', '权限,安全,sudo,激活', '## 麒麟没有激活系统,输入命令经常提醒权限不够，无法通过管理员安装软件或运行有执行权限脚本

**分类**: 权限问题

打开终端执行命令：sudo setstatus softmode -p（是默认开了安全导致,可用命令解除安全限制）', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.63846', '2026-05-29 01:21:54.638462');
INSERT INTO "public"."knowledge_articles" VALUES ('ee6b786454e1', '如何开启/关闭新四核sp3版本系统的安全', '常见-权限问题', '权限,安全,sudo,apparmor', '## 如何开启/关闭新四核sp3版本系统的安全

**分类**: 权限问题

开启安全执行命令：sudo security-switch --default

关闭安全执行命令：sudo security-switch --set custom --list apparmor', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638467', '2026-05-29 01:21:54.638468');
INSERT INTO "public"."knowledge_articles" VALUES ('f8aee5e442ae', '编译的应用无法连接到mysql', '常见-权限问题', '权限,安全,sudo,SELinux,MySQL', '## 编译的应用无法连接到mysql

**分类**: 权限问题

开启安全执行命令：sudo security-switch --default ,关闭selinux后即可连接；永久关闭：vim /etc/selinux/config 把SELINUX=enforcing 修改成SELINUX=disabled。临时关闭：disabled selinux', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.638473', '2026-05-29 01:21:54.638475');
INSERT INTO "public"."knowledge_articles" VALUES ('63b58e5456a5', '银河V10桌面版本，关闭/开启防火墙 命令', '常见-权限问题', '权限,安全,sudo,防火墙', '## 银河V10桌面版本，关闭/开启防火墙 命令

**分类**: 权限问题

永久关闭：service ufw disable

临时关闭：service ufw stop

永久启动：sudo service ufw enable

临时启动：sudo service ufw start', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.63848', '2026-05-29 01:21:54.638482');
INSERT INTO "public"."knowledge_articles" VALUES ('90b7dacb337e', '如何打开桌面KYSEC', '常见-权限问题', '权限,安全,sudo', '## 如何打开桌面KYSEC

**分类**: 权限问题

执行命令：security-switch --set default', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638487', '2026-05-29 01:21:54.638488');
INSERT INTO "public"."knowledge_articles" VALUES ('0ec81dac31f3', '查看系统版本', '常见-版本问题', '版本,内核,更新', '## 查看系统版本

**分类**: 版本问题

右键状态栏空白部分,选择”关于银河麒麟”,或命令行执行:cat /etc/.kyinfo', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638494', '2026-05-29 01:21:54.638495');
INSERT INTO "public"."knowledge_articles" VALUES ('a3d72e8b4e00', '查看序列号', '常见-版本问题', '版本,内核,更新', '## 查看序列号

**分类**: 版本问题

图形化方法：右键我的电脑——>属性，弹窗最下侧的“服务序列号”；

命令行方法：kylin-verify，打印信息中的SN号；', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.6385', '2026-05-29 01:21:54.638502');
INSERT INTO "public"."knowledge_articles" VALUES ('ed7343e9074a', '如何区别哪个光盘是对应哪个版本的系统', '常见-版本问题', '版本,内核,更新,光盘,授权,挂载', '## 如何区别哪个光盘是对应哪个版本的系统

**分类**: 版本问题

挂载后打开挂载目录下的LICENSE或.kyinfo文件,可查看版本相关信息', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638507', '2026-05-29 01:21:54.638509');
INSERT INTO "public"."knowledge_articles" VALUES ('3eb6ec4e9708', '如何获取试用版本？', '常见-版本问题', '版本,内核,更新', '## 如何获取试用版本？

**分类**: 版本问题

麒麟软件官网可申请版本试用,但是只能以企业的名义', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638514', '2026-05-29 01:21:54.638515');
INSERT INTO "public"."knowledge_articles" VALUES ('14195c3386f1', '试用版本使用期限是多久？', '常见-版本问题', '版本,内核,更新', '## 试用版本使用期限是多久？

**分类**: 版本问题

试用版本可以一直使用,但是不享受售后服务', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638521', '2026-05-29 01:21:54.638522');
INSERT INTO "public"."knowledge_articles" VALUES ('c38e86a345c4', '个人用户可获得版本试用么？', '常见-版本问题', '版本,内核,更新', '## 个人用户可获得版本试用么？

**分类**: 版本问题

目前个人用户是无法申请版本试用,可前往优麒麟官网 https://www.ubuntukylin.com下载优麒麟操作系统试用', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638527', '2026-05-29 01:21:54.638529');
INSERT INTO "public"."knowledge_articles" VALUES ('8b4bfa5a4dd7', '银河麒麟服务器版本的内核包怎么查看？', '常见-版本问题', '版本,内核,更新,dpkg', '## 银河麒麟服务器版本的内核包怎么查看？

**分类**: 版本问题

执行命令：dpkg -l | grep linux-headers', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638534', '2026-05-29 01:21:54.638535');
INSERT INTO "public"."knowledge_articles" VALUES ('15f9ddc2ffbd', '怎么查看内核版本？', '常见-版本问题', '版本,内核,更新', '## 怎么查看内核版本？

**分类**: 版本问题

可通过右键我的电脑,然后点击属性查看内核版本；使用命令：uname -r；

打开开始菜单——>所有软件——>麒麟助手,在系统信息里可查看内核版本', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.63854', '2026-05-29 01:21:54.638542');
INSERT INTO "public"."knowledge_articles" VALUES ('17a6f0de383e', '银河麒麟有什么版本？', '常见-版本问题', '版本,内核,更新', '## 银河麒麟有什么版本？

**分类**: 版本问题

目前有V4和v10版本,对应都有服务器版本和桌面版本', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638549', '2026-05-29 01:21:54.638551');
INSERT INTO "public"."knowledge_articles" VALUES ('5faf98e24810', '版本之间有什么区别？', '常见-版本问题', '版本,内核,更新', '## 版本之间有什么区别？

**分类**: 版本问题

新版本相对于旧版本都会有内核或者其他的层面的更新,具体可咨询商务或者参考官网对系统的介绍', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638556', '2026-05-29 01:21:54.638558');
INSERT INTO "public"."knowledge_articles" VALUES ('3941592370f2', '电脑装了Windows10和银河麒麟系统双系统数据盘可以共用吗？', '常见-版本问题', '版本,内核,更新', '## 电脑装了Windows10和银河麒麟系统双系统数据盘可以共用吗？

**分类**: 版本问题

不可以共用', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638563', '2026-05-29 01:21:54.638564');
INSERT INTO "public"."knowledge_articles" VALUES ('db88dee46afd', 'V10银河麒麟桌面系统下可安装的软件类型', '常见-软件安装', '软件,安装,卸载,deb,飞腾', '## V10银河麒麟桌面系统下可安装的软件类型

**分类**: 软件安装

根据系统架构，飞腾系统的安装包后缀为arm6deb，x86系统的安装包后缀为amd6deb；麒麟系统无法安装.exe后缀的软件；', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.63857', '2026-05-29 01:21:54.638571');
INSERT INTO "public"."knowledge_articles" VALUES ('734d624eb21a', '麒麟系统下如何离线安装软件', '常见-软件安装', '软件,安装,卸载,密码,dpkg,deb,sudo', '## 麒麟系统下如何离线安装软件

**分类**: 软件安装

此处假设安装QQ客户端，在QQ安装包所在目录空白处，右键选择“在终端中打开”，执行命令：sudo dpkg -i qq-0-arm6deb

输完命令回车，提示输入密码（输入的密码不会显示在屏幕），输完回车即可完成；', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638577', '2026-05-29 01:21:54.638578');
INSERT INTO "public"."knowledge_articles" VALUES ('56f7cab826f0', '麒麟系统下如何在线安装软件', '常见-软件安装', '软件,安装,卸载', '## 麒麟系统下如何在线安装软件

**分类**: 软件安装

开始菜单——所有软件，打开“麒麟软件中心”或“麒麟软件商店”，点击右上角齿轮图标，添加软件源并更新软件源，更新软件源后可通过搜索来安装对应软件；

【注】不同版本的系统有对应软件源，具体参照以下链接查询：

http://archive.kylinos.cn/kylin/KYLIN-ALL/', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638583', '2026-05-29 01:21:54.638585');
INSERT INTO "public"."knowledge_articles" VALUES ('6e327cecab4c', '安装软件时出现“已安装post-installation脚本返回了错误号10”的问题。', '常见-软件安装', '软件,安装,卸载,root,dpkg,apt', '## 安装软件时出现“已安装post-installation脚本返回了错误号10”的问题。

**分类**: 软件安装

切换到root用户

1.cd /var/lib/dpkg

2.mv info info.bak

3.mkdir info

4.apt-get update

5.apt-get -f install

6.mv info/\* info.bak

7.rm -rf info

8.mv info.bak info', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.63859', '2026-05-29 01:21:54.638592');
INSERT INTO "public"."knowledge_articles" VALUES ('c3cc3f07e130', '软件除了在应用商店还可以去哪里下载？', '常见-软件安装', '软件,安装,卸载', '## 软件除了在应用商店还可以去哪里下载？

**分类**: 软件安装

①　可以到我们的官网http://www.kylinos.cn/进行下载，入口为“兼容适配”——“软件下载”，里面可以下载到一些软件的软件包

②　对应第三方软件的官网。例如QQ，就在https://im.qq.com/——“下载”——“QQ for Linux”——“立即下载”里面就能下载到对应的软件', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638596', '2026-05-29 01:21:54.638598');
INSERT INTO "public"."knowledge_articles" VALUES ('3c48e42f3c7e', '如何更新软件源？', '常见-软件安装', '软件,安装,卸载,apt,sudo', '## 如何更新软件源？

**分类**: 软件安装

登录系统,确保系统可连接外网

①　命令行更新方法：Ctrl+alt+t，调出终端，执行命令：sudo apt update更新软件源

②　图形界面更新方法：“麒麟软件商店”——“设置”——“全选”——“更新软件源”', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638603', '2026-05-29 01:21:54.638604');
INSERT INTO "public"."knowledge_articles" VALUES ('f5c1e33b7e15', '软件商店误删后如何重装？', '常见-软件安装', '软件,安装,卸载,dpkg,apt,sudo', '## 软件商店误删后如何重装？

**分类**: 软件安装

①　ctrl+alt+t，调出终端

②　在线安装：sudo apt update

sudo   apt    install   kylin-software-center

③　离线安装（获取到相关的软件包）：sudo dpkg -i 软件包名', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638609', '2026-05-29 01:21:54.638611');
INSERT INTO "public"."knowledge_articles" VALUES ('ac1f17858e22', '银河系统都能安装安卓模拟器么？', '常见-软件安装', '软件,安装,卸载,飞腾,鲲鹏', '## 银河系统都能安装安卓模拟器么？

**分类**: 软件安装

现在只有飞腾和鲲鹏版本的系统能安装安卓模拟器。', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638616', '2026-05-29 01:21:54.638618');
INSERT INTO "public"."knowledge_articles" VALUES ('96454a88d642', '可以安装apk应用软件吗？', '常见-软件安装', '软件,安装,卸载', '## 可以安装apk应用软件吗？

**分类**: 软件安装

不可以安装，只能使用软件商店已有的“手机APP”的应用。', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638623', '2026-05-29 01:21:54.638624');
INSERT INTO "public"."knowledge_articles" VALUES ('48c11e1a4c08', 'deb和rpm有什么区别？', '常见-软件安装', '软件,安装,卸载,deb,rpm', '## deb和rpm有什么区别？

**分类**: 软件安装

deb和rpm代表软件架构,deb是可以在银河麒麟下安装,rpm是在中标麒麟下安装。', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638629', '2026-05-29 01:21:54.63863');
INSERT INTO "public"."knowledge_articles" VALUES ('301ccebb3b9a', '为什么微信安装成功了不能正常登录？', '常见-软件安装', '软件,安装,卸载,激活,微信', '## 为什么微信安装成功了不能正常登录？

**分类**: 软件安装

①　首先确保系统是银河系统正式版激活的（腾讯官方要求）；

②　确保微信账号绑定过银行卡（腾讯官方要求）；

最新版本的微信需要同时满足这两个条件才能正常使用', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638636', '2026-05-29 01:21:54.638637');
INSERT INTO "public"."knowledge_articles" VALUES ('94b70df5a8b6', '能安装IE浏览器吗？', '常见-软件安装', '软件,安装,卸载,浏览器', '## 能安装IE浏览器吗？

**分类**: 软件安装

麒麟系统不支持安装IE浏览器', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638643', '2026-05-29 01:21:54.638644');
INSERT INTO "public"."knowledge_articles" VALUES ('dc0fb80bdd75', '银河麒麟系统如何安装软件？', '常见-软件安装', '软件,安装,卸载,dpkg,apt,sudo', '## 银河麒麟系统如何安装软件？

**分类**: 软件安装

①　图形化方法：开始菜单——>所有程序——>麒麟软件商店，点击设置按钮添加软件源并更新软件源后，可搜索安装软件

②　使用命令的方法：

离线安装命令：sudo dpkg -i 软件名

在线安装命令：sudo apt install 软件名', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638649', '2026-05-29 01:21:54.638651');
INSERT INTO "public"."knowledge_articles" VALUES ('645a555fbd9b', '银河麒麟系统如何卸载软件？', '常见-软件安装', '软件,安装,卸载,dpkg,apt,sudo', '## 银河麒麟系统如何卸载软件？

**分类**: 软件安装

①　图形化方法：开始菜单——>所有程序——>麒麟软件商店，可搜索软件，进入软件界面点击卸载即可

卸载命令：sudo apt remove 软件名

卸载命令：sudo dpkg -P 软件名（P是大写）', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638656', '2026-05-29 01:21:54.638658');
INSERT INTO "public"."knowledge_articles" VALUES ('63501cedebfb', '怎么安装杀毒软件', '常见-软件安装', '软件,安装,卸载', '## 怎么安装杀毒软件

**分类**: 软件安装

可先登录麒麟软件官网,进入软件兼容适配列表查看支持的杀毒软件。可通过“开始菜单”——“所有程序”——“麒麟软件商店”安装', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638663', '2026-05-29 01:21:54.638664');
INSERT INTO "public"."knowledge_articles" VALUES ('941f9e93dae8', '安装软件提示缺失依赖', '常见-软件安装', '软件,安装,卸载,apt,sudo', '## 安装软件提示缺失依赖

**分类**: 软件安装

可单独下载依赖包解决依赖问题：

sudo apt-get install xxx（依赖包名）

重新安装该软件

sudo apt install -f', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.638673', '2026-05-29 01:21:54.638674');
INSERT INTO "public"."knowledge_articles" VALUES ('292a221bfe25', 'dpkg安装命令出错,报“与本机系统体系结构不符...”', '常见-软件安装', '软件,安装,卸载,dpkg,飞腾,鲲鹏,龙芯,x86', '## dpkg安装命令出错,报“与本机系统体系结构不符...”

**分类**: 软件安装

请按照架构安装对应软件，按CPU的型号分架构的。

鲲鹏——>arm , 飞腾——>arm , 龙芯——>mips , 兆芯——>x86

海光——>x86 , 申威——>alpha', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.63868', '2026-05-29 01:21:54.638681');
INSERT INTO "public"."knowledge_articles" VALUES ('0a63117a3cbb', '怎么批量安装软件', '常见-软件安装', '软件,安装,卸载,dpkg,sudo', '## 怎么批量安装软件

**分类**: 软件安装

新建一个空白软件夹,将想批量安装的软件拷贝至此处

在该文件夹空白处右键,点击从终端打开,输入命令：sudo dpkg -i \*, 即可批量安装软件

【注】：部分软件的依赖包存在安装顺序问题,如果安装顺序不对,软件将 不能正确被配置', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.638686', '2026-05-29 01:21:54.638688');
INSERT INTO "public"."knowledge_articles" VALUES ('90f3d0752f40', '安装软件一直在0%', '常见-软件安装', '软件,安装,卸载', '## 安装软件一直在0%

**分类**: 软件安装

一般后台正在下载,请耐心等待。如果很久没反应的话，建议更新下外网源', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638693', '2026-05-29 01:21:54.638695');
INSERT INTO "public"."knowledge_articles" VALUES ('b79ca159a7ca', '下载到了软件包，怎么安装', '常见-软件安装', '软件,安装,卸载,dpkg,deb,sudo', '## 下载到了软件包，怎么安装

**分类**: 软件安装

系统版本相符的话是可以安装使用的

进入软件包所在目录,在空白处右键,点击打开终端

输入命令：sudo dpkg -i xxx.deb（需要输入软件包完整名称）', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.6387', '2026-05-29 01:21:54.638701');
INSERT INTO "public"."knowledge_articles" VALUES ('e9722a363ad1', '麒麟操作系统有可以查看CPU/GPU的温度检测硬件鲁大师的工具吗？', '常见-软件安装', '软件,安装,卸载', '## 麒麟操作系统有可以查看CPU/GPU的温度检测硬件鲁大师的工具吗？

**分类**: 软件安装

目前暂时无这样的工具', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638707', '2026-05-29 01:21:54.638708');
INSERT INTO "public"."knowledge_articles" VALUES ('4f36ce10a3a8', '麒麟操作系统支持哪些杀毒软件？', '常见-软件安装', '软件,安装,卸载', '## 麒麟操作系统支持哪些杀毒软件？

**分类**: 软件安装

麒麟操作系统目前支持360、瑞星、江民、景云等杀毒软件,详情请前往麒麟软件官网查看软件兼容列表', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638713', '2026-05-29 01:21:54.638715');
INSERT INTO "public"."knowledge_articles" VALUES ('cd4950448ea6', '光盘问题：麒麟系统下空光盘使用光盘刻录器刻录文件显示无剩余空间', '常见-外设使用', '外设,打印机,光盘', '## 光盘问题：麒麟系统下空光盘使用光盘刻录器刻录文件显示无剩余空间

**分类**: 外设使用

RW的DVD盘有这个问题，可以换成R的DVD盘；', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.63872', '2026-05-29 01:21:54.638721');
INSERT INTO "public"."knowledge_articles" VALUES ('d3ae10102aea', '光盘问题：怎么刻录光盘', '常见-外设使用', '外设,打印机,光盘', '## 光盘问题：怎么刻录光盘

**分类**: 外设使用

按F1——>“光盘刻录器”，里面有对光盘刻录的使用说明

开始菜单——>所有程序——>光盘刻录器

确认光盘和或外置光驱正确插入,点击刻录，刻录完成,光盘会自动弹出', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.638727', '2026-05-29 01:21:54.638729');
INSERT INTO "public"."knowledge_articles" VALUES ('f2b25e8ae0fc', '打印机：打印机驱动获取或打印机使用', '常见-外设使用', '外设,打印机,光盘,驱动', '## 打印机：打印机驱动获取或打印机使用

**分类**: 外设使用

已适配的打印机，大部分驱动已集成到系统，可通过添加打印机查找是否有对应驱动，如无驱动则需向打印机厂商获取；直连的打印机可在添加界面识别到，直接添加即可；请通过用户手册获取打印机的详细使用方法；', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638734', '2026-05-29 01:21:54.638735');
INSERT INTO "public"."knowledge_articles" VALUES ('43b24db2ffb4', '打印机：银河麒麟操作系统如何安装某一款打印机驱动？', '常见-外设使用', '外设,打印机,光盘,dpkg,驱动,sudo', '## 打印机：银河麒麟操作系统如何安装某一款打印机驱动？

**分类**: 外设使用

首先,需要咨询打印机厂商是否已经与麒麟操作系统完成适配,或者去麒麟软件官网-兼容列表查询该款打印机是否已完成兼容适配

若打印机已完成适配,则需要咨询厂商,获取驱动安装包

登录系统,安装驱动安装包，使用命令：sudo dpkg -i 驱动包名。如安装不成功可找客服处理。', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638741', '2026-05-29 01:21:54.638742');
INSERT INTO "public"."knowledge_articles" VALUES ('82fa3024e99f', '打印机：怎么看麒麟系统支持使用什么打印机，有没有对应的打印机列表', '常见-外设使用', '外设,打印机,光盘', '## 打印机：怎么看麒麟系统支持使用什么打印机，有没有对应的打印机列表

**分类**: 外设使用

可通过兼容适配列表查看适配情况：https://eco.kylinos.cn/zoology/commercial.html', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638747', '2026-05-29 01:21:54.638748');
INSERT INTO "public"."knowledge_articles" VALUES ('47939e64c413', '光盘：怎么光盘都不能进行续刻', '常见-外设使用', '外设,打印机,光盘', '## 光盘：怎么光盘都不能进行续刻

**分类**: 外设使用

开始菜单——所有软件——光盘刻录器；如果要续刻，请在刻录的时候选择“不关闭盘片xxx下次续刻”的选项', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638754', '2026-05-29 01:21:54.638755');
INSERT INTO "public"."knowledge_articles" VALUES ('8ccab191c54c', '打印机：为什么使用系统自带的驱动打印会出现乱码、打印页数不对......一些不正常的打印现象', '常见-外设使用', '外设,打印机,光盘,驱动', '## 打印机：为什么使用系统自带的驱动打印会出现乱码、打印页数不对......一些不正常的打印现象

**分类**: 外设使用

您这边去咨询下打印机厂商，看下有没有新版本的驱动提供。可能是现有的这个驱动的版本比较老，然后导致您这个情况发生。如果系统里还集成了别的驱动，可以换个驱动看下是否打印还是这个情况。', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.638761', '2026-05-29 01:21:54.638762');
INSERT INTO "public"."knowledge_articles" VALUES ('b9609527ae1b', '如何查看用户手册', '常见-手册问题', '手册,文档,帮助', '## 如何查看用户手册

**分类**: 手册问题

按F1键或状态栏空白处右键选择“帮助”，即可弹出用户手册；', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638767', '2026-05-29 01:21:54.638769');
INSERT INTO "public"."knowledge_articles" VALUES ('b3a0a604e443', '删除了用户手册怎么装回来', '常见-手册问题', '手册,文档,帮助,apt,sudo', '## 删除了用户手册怎么装回来

**分类**: 手册问题

执行命令：sudo apt install kylin-user-guide，默认的快捷方式无法恢复', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638774', '2026-05-29 01:21:54.638776');
INSERT INTO "public"."knowledge_articles" VALUES ('db07293dfb73', '浪潮一体机状态栏图标出现在状态栏中间,日历打不开', '常见-显示问题', '显示,桌面,任务栏', '## 浪潮一体机状态栏图标出现在状态栏中间,日历打不开

**分类**: 显示问题

机器会识别到两个显示器，把未知的显示器关掉即可', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638781', '2026-05-29 01:21:54.638783');
INSERT INTO "public"."knowledge_articles" VALUES ('301dc6f8229e', '控制面板无屏保设置', '常见-显示问题', '显示,桌面,任务栏', '## 控制面板无屏保设置

**分类**: 显示问题

命令行mate-screensaver-preference可调出屏保设置窗口', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638788', '2026-05-29 01:21:54.638789');
INSERT INTO "public"."knowledge_articles" VALUES ('0c0df1c8f18c', '挂载的硬盘需隐藏在桌面的挂载图标', '常见-显示问题', '显示,桌面,任务栏,挂载', '## 挂载的硬盘需隐藏在桌面的挂载图标

**分类**: 显示问题

通过gsetting解决：gsetting set org.mate.caja.desktop volumes-visible false', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638795', '2026-05-29 01:21:54.638796');
INSERT INTO "public"."knowledge_articles" VALUES ('14c2b39d4ffb', 'Ctrl+alt+T无法打开终端', '常见-显示问题', '显示,桌面,任务栏', '## Ctrl+alt+T无法打开终端

**分类**: 显示问题

删除当前用户主目录的.config文件,再重启系统', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.638802', '2026-05-29 01:21:54.638803');
INSERT INTO "public"."knowledge_articles" VALUES ('4a6d594ab0ab', 'Sogou五笔输入法乱码', '常见-显示问题', '显示,桌面,任务栏,输入法', '## Sogou五笔输入法乱码

**分类**: 显示问题

重启输入法，杀死fcitx和sogou-qimpanel进程,执行killall fcitx和killall sogou-qimpanel,再后台fcitx-autostart &和sogou-qimpanel &.', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.638808', '2026-05-29 01:21:54.63881');
INSERT INTO "public"."knowledge_articles" VALUES ('891928d8dbf4', '浪潮服务器上系统无桌面显示', '常见-显示问题', '显示,桌面,任务栏', '## 浪潮服务器上系统无桌面显示

**分类**: 显示问题

鼠标右键选择<桌面背景>,再选择<显示器>,将笔记本显示器关掉即可', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638815', '2026-05-29 01:21:54.638817');
INSERT INTO "public"."knowledge_articles" VALUES ('aed9d6f7bb9b', '图形界面配置双屏镜像屏幕,重启系统后未生效', '常见-显示问题', '显示,桌面,任务栏,sudo', '## 图形界面配置双屏镜像屏幕,重启系统后未生效

**分类**: 显示问题

使用用户的显示配置文件覆盖lightdm的，然后重启lightdm服务

sudo cp ~/.config/monitors.xml /var/lib/lightdm/.config/

sudo service lightdm restart', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.638822', '2026-05-29 01:21:54.638824');
INSERT INTO "public"."knowledge_articles" VALUES ('c3f94d1c99df', '开始菜单无法打开', '常见-显示问题', '显示,桌面,任务栏', '## 开始菜单无法打开

**分类**: 显示问题

删除./face文件', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.638829', '2026-05-29 01:21:54.638831');
INSERT INTO "public"."knowledge_articles" VALUES ('5a274f06e6d2', '开机后,底端状态栏显示一直不停在打开"正在启动caja"', '常见-显示问题', '显示,桌面,任务栏', '## 开机后,底端状态栏显示一直不停在打开"正在启动caja"

**分类**: 显示问题

执行ctrl+alt+F2切换到文本模式，删除家目录下的.Xauthory及.config解决', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638836', '2026-05-29 01:21:54.638838');
INSERT INTO "public"."knowledge_articles" VALUES ('909cc91aff30', '一台机器桌面下方任务栏不停闪烁，一段时间后卡住死机', '常见-显示问题', '显示,桌面,任务栏', '## 一台机器桌面下方任务栏不停闪烁，一段时间后卡住死机

**分类**: 显示问题

重装mate-panel包', 'faq_imported', 'critical', 0, '2026-05-29 01:21:54.638846', '2026-05-29 01:21:54.638848');
INSERT INTO "public"."knowledge_articles" VALUES ('c21b64ac24be', '桌面右键菜单中没有新建WPS文档的选项', '常见-显示问题', '显示,桌面,任务栏,WPS', '## 桌面右键菜单中没有新建WPS文档的选项

**分类**: 显示问题

将WPS安装目录下templates目录的WPS相关文档拷贝至家目录模板目录下，如kylin用户则为/home/kylin/模板/，即可达到所有效果；如WPS的模板一般放置在/opt/kingsoft/wps-office/templates下，若此目录下无对应模板，也可将其他麒麟系统下的模板拷贝至/home/kylin/模板/', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638853', '2026-05-29 01:21:54.638855');
INSERT INTO "public"."knowledge_articles" VALUES ('12f01608ff25', '桌面回收站图标丢失', '常见-显示问题', '显示,桌面,任务栏', '## 桌面回收站图标丢失

**分类**: 显示问题

在终端中输入gsetting set org.mate.caja.desktop trash-icon-icon-visible false即可', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.63886', '2026-05-29 01:21:54.638862');
INSERT INTO "public"."knowledge_articles" VALUES ('30b8facd28eb', '安装系统屏幕分裂', '常见-显示问题', '显示,桌面,任务栏', '## 安装系统屏幕分裂

**分类**: 显示问题

需要联系硬件厂商升级固件即可', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638867', '2026-05-29 01:21:54.638869');
INSERT INTO "public"."knowledge_articles" VALUES ('94362617b8dd', '桌面图标全部消失不见，只剩任务栏和开始菜单。', '常见-显示问题', '显示,桌面,任务栏,apt,sudo', '## 桌面图标全部消失不见，只剩任务栏和开始菜单。

**分类**: 显示问题

可能是把caja误删了，重装重启机器即可

执行命令：sudo apt install caja caja-common', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.638874', '2026-05-29 01:21:54.638875');
INSERT INTO "public"."knowledge_articles" VALUES ('859f92f65590', '在哪里关闭锁屏并且设置锁屏时间', '常见-显示问题', '显示,桌面,任务栏', '## 在哪里关闭锁屏并且设置锁屏时间

**分类**: 显示问题

设置锁屏：开始菜单——>控制面板——>电源管理——>屏幕保护', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638881', '2026-05-29 01:21:54.638882');
INSERT INTO "public"."knowledge_articles" VALUES ('76f53ead7c79', '任务栏消失', '常见-显示问题', '显示,桌面,任务栏', '## 任务栏消失

**分类**: 显示问题

删除主目录下.config/，重启机器后任务栏恢复正常', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.638887', '2026-05-29 01:21:54.638888');
INSERT INTO "public"."knowledge_articles" VALUES ('dc04d9caaee9', '以太网连接增加,部分连接失效', '常见-网络问题', '网络,IP,DNS', '## 以太网连接增加,部分连接失效

**分类**: 网络问题

删除/etc/udev/rules.d/下的网络连接配置文件，重启机器再自动生成', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.638894', '2026-05-29 01:21:54.638895');
INSERT INTO "public"."knowledge_articles" VALUES ('7c4ddee15b58', 'ssh连接服务器速度慢', '常见-网络问题', '网络,IP,DNS,SSH', '## ssh连接服务器速度慢

**分类**: 网络问题

注释/etc/ssh/ssh_config文件中ForwardX11一行', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.6389', '2026-05-29 01:21:54.638902');
INSERT INTO "public"."knowledge_articles" VALUES ('2e3203ceb675', '网络被人修改配置后时断时续', '常见-网络问题', '网络,IP,DNS,权限', '## 网络被人修改配置后时断时续

**分类**: 网络问题

查看日志,确定问题所在。情况一:/etc目录下配置文件属主或权限被修改,则按照正确配置一一修改回原来配置', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.638906', '2026-05-29 01:21:54.638908');
INSERT INTO "public"."knowledge_articles" VALUES ('f969e6c7d4bd', '切换用户提示无法解析主机', '常见-网络问题', '网络,IP,DNS', '## 切换用户提示无法解析主机

**分类**: 网络问题

修改hostname,但未同步修改/etc/hosts导致,更改/etc/hosts中的主机名为hostname命令得到的主机名', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638913', '2026-05-29 01:21:54.638915');
INSERT INTO "public"."knowledge_articles" VALUES ('1b682cf193e2', 'service networking restart 失败的问题', '常见-网络问题', '网络,IP,DNS', '## service networking restart 失败的问题

**分类**: 网络问题

由于现系统中，默认使用network-manager，所以networking无法接管网络，造成对networking服务的操作失败。因此，如果需要重启网络服务，使用命令“service network-manager restart”即可', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.638919', '2026-05-29 01:21:54.638922');
INSERT INTO "public"."knowledge_articles" VALUES ('a994bff08a34', '网络配置好，但无法访问网页', '常见-网络问题', '网络,IP,DNS', '## 网络配置好，但无法访问网页

**分类**: 网络问题

①　命令行执行：ping ip

②　能ping通，再修改/etc/resolv.conf

③　添加dns，如：nameserver 8.8.8.8', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.638942', '2026-05-29 01:21:54.638943');
INSERT INTO "public"."knowledge_articles" VALUES ('26c82497f032', 'mac地址漂移问题，导致网络异常', '常见-网络问题', '网络,IP,DNS', '## mac地址漂移问题，导致网络异常

**分类**: 网络问题

通过nameif绑定mac地址解决', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.638948', '2026-05-29 01:21:54.63895');
INSERT INTO "public"."knowledge_articles" VALUES ('bdd995be945a', '如何手动配置网络？', '常见-网络问题', '网络,IP,DNS', '## 如何手动配置网络？

**分类**: 网络问题

①　登录系统

②　打开控制面板-网络连接

③　选择要编辑的网络连接,然后点击“编辑”

④　在打开的窗口中,选择”IPv4设置“,找到”DNS服务器“,填入DNS服务器地址即可', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638954', '2026-05-29 01:21:54.638956');
INSERT INTO "public"."knowledge_articles" VALUES ('7e369aa83640', '系统配置网络无效,网关通,DNS ping不通,网上不了？', '常见-网络问题', '网络,IP,DNS', '## 系统配置网络无效,网关通,DNS ping不通,网上不了？

**分类**: 网络问题

请检查您的DNS配置是否有误。若确定DNS配置无误,请联系您的网管。', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638961', '2026-05-29 01:21:54.638963');
INSERT INTO "public"."knowledge_articles" VALUES ('eb843a8b567b', '点图形化配置网络提示“系统的网络服务与此版本的网络管理器不兼容”？', '常见-网络问题', '网络,IP,DNS', '## 点图形化配置网络提示“系统的网络服务与此版本的网络管理器不兼容”？

**分类**: 网络问题

请尝试重启NetworkManager服务，执行命令：service NetworkManager start', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.638967', '2026-05-29 01:21:54.638969');
INSERT INTO "public"."knowledge_articles" VALUES ('e428cfe1dc79', '网卡型号怎么查看？', '常见-网络问题', '网络,IP,DNS,网卡', '## 网卡型号怎么查看？

**分类**: 网络问题

请打开开始菜单——>所有软件——>麒麟助手,在系统信息里可网卡详细信息', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638974', '2026-05-29 01:21:54.638975');
INSERT INTO "public"."knowledge_articles" VALUES ('8f36a6afb029', 'networking服务的网卡配置文件路径？', '常见-网络问题', '网络,IP,DNS,网卡', '## networking服务的网卡配置文件路径？

**分类**: 网络问题

网卡配置文件路径是/etc/network/interfaces', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.63898', '2026-05-29 01:21:54.638982');
INSERT INTO "public"."knowledge_articles" VALUES ('6fc1f891b994', '怎么查看mac地址？', '常见-网络问题', '网络,IP,DNS,网卡', '## 怎么查看mac地址？

**分类**: 网络问题

请打开开始菜单——>所有软件——>麒麟助手,在系统信息里可网卡

执行命令：ifconfig', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638987', '2026-05-29 01:21:54.638988');
INSERT INTO "public"."knowledge_articles" VALUES ('91c92368b9c3', '换了办公环境就上不了网了？', '常见-网络问题', '网络,IP,DNS', '## 换了办公环境就上不了网了？

**分类**: 网络问题

更换网络环境后,需要重新配置网络连接,请联系您的网管', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.638993', '2026-05-29 01:21:54.638995');
INSERT INTO "public"."knowledge_articles" VALUES ('4954a5aca89f', '如何配置网络代理？', '常见-网络问题', '网络,IP,DNS', '## 如何配置网络代理？

**分类**: 网络问题

可通过开始菜单——>控制面板——>网络代理打开配置界面,根据具体情况进行配置', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639', '2026-05-29 01:21:54.639002');
INSERT INTO "public"."knowledge_articles" VALUES ('655cb2480f3d', '设置网卡限速？', '常见-网络问题', '网络,IP,DNS,网卡', '## 设置网卡限速？

**分类**: 网络问题

设置方法：ethtool -s eth0 speed 100 duplex full', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639007', '2026-05-29 01:21:54.639008');
INSERT INTO "public"."knowledge_articles" VALUES ('85e3f6eb33e9', '设置ip后,重启系统,网络连接会变,例如eth0一开始连接的是A网络,但是偶尔重启会连接到B网络？', '常见-网络问题', '网络,IP,DNS,网卡', '## 设置ip后,重启系统,网络连接会变,例如eth0一开始连接的是A网络,但是偶尔重启会连接到B网络？

**分类**: 网络问题

编辑“网络连接”——>“以太网”——>“设备”需要指定网络连接对应的网卡设备', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.639013', '2026-05-29 01:21:54.639015');
INSERT INTO "public"."knowledge_articles" VALUES ('1eab217bd302', '右下角网络图标消失？', '常见-网络问题', '网络,IP,DNS', '## 右下角网络图标消失？

**分类**: 网络问题

建议您修改/var/lib/NetworkManager下的NetworkManager.state文件,将所有值都设置为true,然后重启系统

或者建议您直接删除/var/lib/NetworkManager下的NetworkManager.state文件,然后重启系统', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.639019', '2026-05-29 01:21:54.639021');
INSERT INTO "public"."knowledge_articles" VALUES ('f49a9a19b874', '图形界面无法配置网卡？', '常见-网络问题', '网络,IP,DNS,网卡,sudo', '## 图形界面无法配置网卡？

**分类**: 网络问题

应该是network-manager服务未启动,注释/etc/network/interfaces中的自定义内容后,然后启动networ-manager服务并设置为开机自启：

sudo systemctl start network-manager

sudo systemctl enable network-manager', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639025', '2026-05-29 01:21:54.639038');
INSERT INTO "public"."knowledge_articles" VALUES ('bec68ea910a6', '系统右下角的时间无法与网络时间同步,每次重启后,时间变至2016.012（不正常的日期）？', '常见-网络问题', '网络,IP,DNS,sudo', '## 系统右下角的时间无法与网络时间同步,每次重启后,时间变至2016.012（不正常的日期）？

**分类**: 网络问题

①　请检查您的网络是否能连接外网。若网络畅通,请打开控制面板-时间与日期,确认是否已勾选”与网络时间同步“

②　若无法连接外网,请打开控制面板-时间与日期,取消勾选”与网络时间同步“,然后设置正确的时间。然后打开一个终端,执行：sudo hwclock -w', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.639043', '2026-05-29 01:21:54.639045');
INSERT INTO "public"."knowledge_articles" VALUES ('b186df8011f0', '电脑链接不上内网,插了网线用不了？', '常见-网络问题', '网络,IP,DNS', '## 电脑链接不上内网,插了网线用不了？

**分类**: 网络问题

请检查是否未配置内网IP,检查方式为：右键任务栏右侧的电脑图标,在菜单中选择“连接信息”,查看活动的网络连接中是否有有线连接

若未配置IP,请配置内网IP地址,IP地址请咨询贵公司的网管获得', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.63905', '2026-05-29 01:21:54.639051');
INSERT INTO "public"."knowledge_articles" VALUES ('73d3b8491aa4', '台式机如何连接wifi？', '常见-网络问题', '网络,IP,DNS,网卡,wifi', '## 台式机如何连接wifi？

**分类**: 网络问题

台式机主机中未内置无线网卡,一般无法连接无线网络,若需连接无线网络,需连接外置无线网卡（网卡需要和系统做适配）。', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.639056', '2026-05-29 01:21:54.639058');
INSERT INTO "public"."knowledge_articles" VALUES ('280e720bac83', '飞腾笔记本无法使用自带键盘和触摸板的问题', '常见-输入问题', '输入法,键盘,fcitx,GRUB,apt,飞腾', '## 飞腾笔记本无法使用自带键盘和触摸板的问题

**分类**: 输入问题

将/boot/grub.cfg配置文件中的drivicetree/dtb/u-boot-general.dtb修改为drivicetree/dtb/u-boot-changcheng-laptop.dtb', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.639062', '2026-05-29 01:21:54.639064');
INSERT INTO "public"."knowledge_articles" VALUES ('a4c3c800b078', '搜狗拼音输入法乱码问题', '常见-输入问题', '输入法,键盘,fcitx', '## 搜狗拼音输入法乱码问题

**分类**: 输入问题

删除~/.cache、~/.gconf和～/.config解决', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.639069', '2026-05-29 01:21:54.63907');
INSERT INTO "public"."knowledge_articles" VALUES ('e60ed8227508', '搜狗输入法在/tmp/下产生大量core文件', '常见-输入问题', '输入法,键盘,fcitx', '## 搜狗输入法在/tmp/下产生大量core文件

**分类**: 输入问题

升级搜狗输入法', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639075', '2026-05-29 01:21:54.639076');
INSERT INTO "public"."knowledge_articles" VALUES ('21d0ffe3f560', '搜狗五笔输入法无五码首选上屏功能', '常见-输入问题', '输入法,键盘,fcitx', '## 搜狗五笔输入法无五码首选上屏功能

**分类**: 输入问题

升级搜狗输入法到0及以上版本', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639081', '2026-05-29 01:21:54.639082');
INSERT INTO "public"."knowledge_articles" VALUES ('bd44fb519bde', '输入法用不了,任务栏没有键盘图标', '常见-输入问题', '输入法,键盘,fcitx,apt,sudo', '## 输入法用不了,任务栏没有键盘图标

**分类**: 输入问题

需要重新安装fcitx：

sudo apt-get update

sudo apt-get install fcitx', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639087', '2026-05-29 01:21:54.639089');
INSERT INTO "public"."knowledge_articles" VALUES ('65393d6bfc49', '去哪里下载五笔输入法？', '常见-输入问题', '输入法,键盘,fcitx', '## 去哪里下载五笔输入法？

**分类**: 输入问题

目前没有单独的五笔输入法安装包,搜狗输入法默认集成了搜狗五笔输入法', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639094', '2026-05-29 01:21:54.639095');
INSERT INTO "public"."knowledge_articles" VALUES ('cabeea4b9d8f', '搜狗输入法没有办法切换到五笔输入，或者输入某些字符不对时', '常见-输入问题', '输入法,键盘,fcitx', '## 搜狗输入法没有办法切换到五笔输入，或者输入某些字符不对时

**分类**: 输入问题

可以通过设置搜狗设置“恢复默认配置”', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.6391', '2026-05-29 01:21:54.639101');
INSERT INTO "public"."knowledge_articles" VALUES ('3a362571bac0', '在有x权限的情况下执行shell脚本/二进制程序报“没有权限”错误', '常见-挂卸载问题', '挂载,卸载,分区,权限', '## 在有x权限的情况下执行shell脚本/二进制程序报“没有权限”错误

**分类**: 挂卸载问题

取消文件系统挂载的noexec参数并重新挂载', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.639106', '2026-05-29 01:21:54.639107');
INSERT INTO "public"."knowledge_articles" VALUES ('642ed381a84e', '如何配置自动挂载', '常见-挂卸载问题', '挂载,卸载,分区,fstab,mount,sudo', '## 如何配置自动挂载

**分类**: 挂卸载问题

修改/etc/fstab:sudo pluma /etc/fstab

文末添加如下内容：

UUID=bfe83d28-ce85-4999-84bb-d47167da6b07 /home/kylin/data ext4 errors=remount-ro 0 0

上述内容中UUID为待挂载分区标识，使用blkid获取；', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639112', '2026-05-29 01:21:54.639113');
INSERT INTO "public"."knowledge_articles" VALUES ('f5779f86d250', '两台客户端同时挂载NFS，分别对其中的同一个文件进行dd写入或读取时，会出现读取速度异常变慢的情况', '常见-挂卸载问题', '挂载,卸载,分区,dd命令,NFS,mount', '## 两台客户端同时挂载NFS，分别对其中的同一个文件进行dd写入或读取时，会出现读取速度异常变慢的情况

**分类**: 挂卸载问题

使用mount命令挂载NFS时，去除nfs的"nolock"挂载参数，使用默认参数或者lock参数挂载', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.639138', '2026-05-29 01:21:54.63914');
INSERT INTO "public"."knowledge_articles" VALUES ('7cd03c436cf9', '/etc/fstab自动挂载出来的分区，分区挂载之前的可执行脚本，手动chmod 777和chown都没有可执行权限', '常见-挂卸载问题', '挂载,卸载,分区,fstab,权限', '## /etc/fstab自动挂载出来的分区，分区挂载之前的可执行脚本，手动chmod 777和chown都没有可执行权限

**分类**: 挂卸载问题

在/etc/fstab的挂载选项了加一个挂载参数exec', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639148', '2026-05-29 01:21:54.63915');
INSERT INTO "public"."knowledge_articles" VALUES ('796183010976', '挂载的硬盘在桌面上有图标，需设置隐藏', '常见-挂卸载问题', '挂载,卸载,分区', '## 挂载的硬盘在桌面上有图标，需设置隐藏

**分类**: 挂卸载问题

通过gsettings解决：gsettings set org.mate.caja.desktop volumes-visible false', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639155', '2026-05-29 01:21:54.639156');
INSERT INTO "public"."knowledge_articles" VALUES ('fd14944beb91', 'U盘不能自动挂载', '常见-挂卸载问题', '挂载,卸载,分区,U盘', '## U盘不能自动挂载

**分类**: 挂卸载问题

拔掉U盘，rm -rf /media/\* ，把/usr/share/hal/fdi/policy/10osvendor 下的25-storage-methods.fdi删掉.ubuntu 9.10开始使用devkit-disks来处理挂载，可能和hal冲突了。', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639161', '2026-05-29 01:21:54.639162');
INSERT INTO "public"."knowledge_articles" VALUES ('a9b747820e9b', '意外掉电或硬关机系统后，有时会出现使用iscsiadm能正常查看Target设备，但无法挂载该设备的问题。（日志报告无法挂载或磁盘已挂载）', '常见-挂卸载问题', '挂载,卸载,分区', '## 意外掉电或硬关机系统后，有时会出现使用iscsiadm能正常查看Target设备，但无法挂载该设备的问题。（日志报告无法挂载或磁盘已挂载）

**分类**: 挂卸载问题

删除/var/lib/iscsi/nodes目录下iSCSI存储服务器上的Target名命名的文件夹下相关内容。', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.63917', '2026-05-29 01:21:54.639171');
INSERT INTO "public"."knowledge_articles" VALUES ('709f07fbb28e', '挂载的u盘双击无法打开', '常见-挂卸载问题', '挂载,卸载,分区,U盘,sudo,权限', '## 挂载的u盘双击无法打开

**分类**: 挂卸载问题

请先cd到挂载目录,通过ll命令查看挂载目录是否有rw权限,如有rw权限,请继续下面步骤：

请通过ll命令确认挂载目录权限及属主

①　按照正常系统的facl设置/media/greatwall（目录名称具系统实际情况而定）及u盘挂载目录的facl：

sudo setfacl -m u:greatwall:rx /media/greatwall

②　设置facl权限的mask:

sudo setfacl -m m::rx /media/greatwall

③　正确修改后,请重新插拔U盘,即可正常使用', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.639177', '2026-05-29 01:21:54.639178');
INSERT INTO "public"."knowledge_articles" VALUES ('4a27823f3979', '银河麒麟操作系统支持多个分区挂载到同一目录吗', '常见-挂卸载问题', '挂载,卸载,分区', '## 银河麒麟操作系统支持多个分区挂载到同一目录吗

**分类**: 挂卸载问题

①　当把多个分区都挂载到同一个目录时，目录只会显示最后挂载分区的内容。而把最后挂载的分区卸载后，该目录将显示倒数第二个被挂载的分区，依此类推。

②　打开开始菜单-所有程序-附件-分区编辑器

在右上角硬盘下拉菜单中选择新硬盘

对其进行分区、格式化操作后,选择其中的一个分区,在右键菜单中选择挂载', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639183', '2026-05-29 01:21:54.639185');
INSERT INTO "public"."knowledge_articles" VALUES ('2643a1324ecc', '服务器和台式机都有小概率出现插了usb0的u盘后不能自动挂载的问题，此时通过命令行挂载后可进行读写访问', '常见-挂卸载问题', '挂载,卸载,分区,U盘', '## 服务器和台式机都有小概率出现插了usb0的u盘后不能自动挂载的问题，此时通过命令行挂载后可进行读写访问

**分类**: 挂卸载问题

插拔过快导致，手动卸载u盘再拔掉u盘，然后重新插进u盘，不会出现此情况', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.63919', '2026-05-29 01:21:54.639191');
INSERT INTO "public"."knowledge_articles" VALUES ('e6b937b9be75', '如何用光盘挂载本地源？', '常见-挂卸载问题', '挂载,卸载,分区,光盘,apt,deb', '## 如何用光盘挂载本地源？

**分类**: 挂卸载问题

具体的配置参数依据实际而定，参考步骤如下：

①　将本地源网址写进/etc/apt/sources.list：cat /etc/apt/sources.list ；

②　添加本地源网址：deb file:///media/kylin/Kylin-0.2 juniper main 其中Kylin-0.2是大写的K，且光盘要挂载在这个目录下。', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639197', '2026-05-29 01:21:54.639207');
INSERT INTO "public"."knowledge_articles" VALUES ('e5ff66dcd081', '画图软件', '常见-应用问题', '应用,浏览器,办公', '## 画图软件

**分类**: 应用问题

可联系麒麟公司提供dia软件', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639213', '2026-05-29 01:21:54.639214');
INSERT INTO "public"."knowledge_articles" VALUES ('7f74d8aece8f', '安装软件时提示达梦数据库相关错误', '常见-应用问题', '应用,浏览器,办公,数据库', '## 安装软件时提示达梦数据库相关错误

**分类**: 应用问题

先卸载达梦数据库，再装需要安装的软件，装完后再把达梦装回来(注意备份数据库相关数据)', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.639219', '2026-05-29 01:21:54.639221');
INSERT INTO "public"."knowledge_articles" VALUES ('ef40caaa2265', 'Firefox 打开java applet程序警告', '常见-应用问题', '应用,浏览器,办公,deb', '## Firefox 打开java applet程序警告

**分类**: 应用问题

编写打包applet程序时添加Permission和Application-Library-Allowable-Codebase属性', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639226', '2026-05-29 01:21:54.639227');
INSERT INTO "public"."knowledge_articles" VALUES ('e89a879bcad6', '打开VMware报vmmon无法编译', '常见-应用问题', '应用,浏览器,办公,VMware', '## 打开VMware报vmmon无法编译

**分类**: 应用问题

将/usr/src/linux-headers-xxx/include/miscdevice.h第71行void改为int', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639233', '2026-05-29 01:21:54.639234');
INSERT INTO "public"."knowledge_articles" VALUES ('f909b860962c', '无法使用xmanager', '常见-应用问题', '应用,浏览器,办公,xmanager', '## 无法使用xmanager

**分类**: 应用问题

启用XDMCP,修改/usr/share/lightdm/lightdm.conf.d/60-kylin.conf文件，添加如下内容

[XDMCPServer]

enabled=true', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.639239', '2026-05-29 01:21:54.639241');
INSERT INTO "public"."knowledge_articles" VALUES ('9447da449d39', '编译ltp,报缺少kdeamon.h文件', '常见-应用问题', '应用,浏览器,办公', '## 编译ltp,报缺少kdeamon.h文件

**分类**: 应用问题

降级libc6-dev版本至21或者升级ltp版本解决,或者将ltp的makefile文件的kdeamon.h的行注释再编译', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639246', '2026-05-29 01:21:54.639247');
INSERT INTO "public"."knowledge_articles" VALUES ('6811f84f1730', '火狐浏览器的网页如何添加快捷方式？', '常见-应用问题', '应用,浏览器,办公,微信', '## 火狐浏览器的网页如何添加快捷方式？

**分类**: 应用问题

拖拽网址前的锁形图标或叹号图标等到桌面，

【注】由于微信安全设置，无法创建微信的网页快捷方式', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639252', '2026-05-29 01:21:54.639254');
INSERT INTO "public"."knowledge_articles" VALUES ('da999847916d', '定位dmserver创建库文件后启动权限不够的问题', '常见-应用问题', '应用,浏览器,办公,权限', '## 定位dmserver创建库文件后启动权限不够的问题

**分类**: 应用问题

安全类型为dmdb_data_t并非执行dmdb_exec_t类型，chcon修改bin目录的类型调用和为执行类型，kysec_set -n exectl -v verified kysoft install.sh后生成的文件权限为执行权限', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.639259', '2026-05-29 01:21:54.63926');
INSERT INTO "public"."knowledge_articles" VALUES ('8f8aa0c76e2b', '安装libpcre包，mysql 本地地址为登录参数时，无法登录的问题', '常见-应用问题', '应用,浏览器,办公,网卡,MySQL', '## 安装libpcre包，mysql 本地地址为登录参数时，无法登录的问题

**分类**: 应用问题

通过解除网卡绑定解决', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.639266', '2026-05-29 01:21:54.639267');
INSERT INTO "public"."knowledge_articles" VALUES ('9912230f1228', '通过蓝牙连接不能互发文件，或者蓝牙无法连接问题', '常见-应用问题', '应用,浏览器,办公,蓝牙', '## 通过蓝牙连接不能互发文件，或者蓝牙无法连接问题

**分类**: 应用问题

Kylin系统安装bluman-0.4-1 kord4k9版本', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.639272', '2026-05-29 01:21:54.639274');
INSERT INTO "public"."knowledge_articles" VALUES ('bb3e335703d2', '每开一个视频网站，都会提醒插件存在安全隐患，要激活或者需要允许运行', '常见-应用问题', '应用,浏览器,办公,激活', '## 每开一个视频网站，都会提醒插件存在安全隐患，要激活或者需要允许运行

**分类**: 应用问题

安装kylin-settings-110.53kord-1 ukui以上版本', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639279', '2026-05-29 01:21:54.63928');
INSERT INTO "public"."knowledge_articles" VALUES ('407abfa1b9e1', '无驱打印机添加失败，提示cups操作中出现一个错误：client-error-possible', '常见-应用问题', '应用,浏览器,办公,打印机', '## 无驱打印机添加失败，提示cups操作中出现一个错误：client-error-possible

**分类**: 应用问题

系统缺少libnss-mdns包导致，将libnss-mdns添加进系统包列表', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.639285', '2026-05-29 01:21:54.639287');
INSERT INTO "public"."knowledge_articles" VALUES ('dc8dd937f6be', '银河麒麟系统，用火狐浏览器观看视频时，没有安装flash player插件，无法观看视频。', '常见-应用问题', '应用,浏览器,办公,flash,权限', '## 银河麒麟系统，用火狐浏览器观看视频时，没有安装flash player插件，无法观看视频。

**分类**: 应用问题

直接点击视频中间的安装插件按钮，会自动打开flashplayer的下载界面，我选择的是.tar.gz方式安装，下载完成后解压，将libflashplayer.so 复制到 /usr/lib/mozilla/plugins文件夹，再进入/ usr/lib/mozilla/plugins文件夹，执行chmod 755 libflashplayer.so,更改插件权限，此时就可以观看视频了。', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639292', '2026-05-29 01:21:54.639293');
INSERT INTO "public"."knowledge_articles" VALUES ('e017de7e9f60', '如何设置火狐浏览器的下载目录', '常见-应用问题', '应用,浏览器,办公', '## 如何设置火狐浏览器的下载目录

**分类**: 应用问题

首选项——>下载，点“浏览”，设置默认的下载目录', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639298', '2026-05-29 01:21:54.6393');
INSERT INTO "public"."knowledge_articles" VALUES ('a8250f02111c', '天工圆圆软件双击无法打开', '常见-应用问题', '应用,浏览器,办公', '## 天工圆圆软件双击无法打开

**分类**: 应用问题

原因是系统时间不对，导致软件认证不通过，修改系统时间后，正常使用', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.639305', '2026-05-29 01:21:54.639306');
INSERT INTO "public"."knowledge_articles" VALUES ('a5088a6befca', 'qt5装了qt5designer的包但是建立qt5的工程后没法找到designer插件', '常见-应用问题', '应用,浏览器,办公', '## qt5装了qt5designer的包但是建立qt5的工程后没法找到designer插件

**分类**: 应用问题

安装qttools5-dev和qttools5-dev-tools两个包', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639311', '2026-05-29 01:21:54.639313');
INSERT INTO "public"."knowledge_articles" VALUES ('b749dc53e3e5', 'xmanager连不上', '常见-应用问题', '应用,浏览器,办公,xmanager', '## xmanager连不上

**分类**: 应用问题

在custom.conf中添加DisplaysPerHost参数解决', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639318', '2026-05-29 01:21:54.63932');
INSERT INTO "public"."knowledge_articles" VALUES ('8aa6ca0cd454', '服务器vnc进程占用大量cpu资源', '常见-应用问题', '应用,浏览器,办公,VNC', '## 服务器vnc进程占用大量cpu资源

**分类**: 应用问题

vnc创建的窗口中出现caja报错的问题，删除所有vnc相关的进程并重新安装配置后解决。', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.639325', '2026-05-29 01:21:54.639326');
INSERT INTO "public"."knowledge_articles" VALUES ('5570cc62b1d1', '通过xmanager连接ft1500a系统，qt中输入有问题。', '常见-应用问题', '应用,浏览器,办公,xmanager', '## 通过xmanager连接ft1500a系统，qt中输入有问题。

**分类**: 应用问题

修改windows上的xmanager配置，将xkeyboard打开即可', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.639332', '2026-05-29 01:21:54.639333');
INSERT INTO "public"."knowledge_articles" VALUES ('1ff5784b55e3', '怎么使用flash', '常见-应用问题', '应用,浏览器,办公,激活,flash', '## 怎么使用flash

**分类**: 应用问题

正式版本激活系统后才可以使用flash', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639338', '2026-05-29 01:21:54.639339');
INSERT INTO "public"."knowledge_articles" VALUES ('d1b653f55088', '银河麒麟支持什么浏览器', '常见-应用问题', '应用,浏览器,办公', '## 银河麒麟支持什么浏览器

**分类**: 应用问题

支持火狐浏览器、谷歌浏览器、360浏览器等,具体可登录麒麟软件官网查看软件兼容列表', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639344', '2026-05-29 01:21:54.639346');
INSERT INTO "public"."knowledge_articles" VALUES ('dccf49c33967', '银河麒麟为什么从网页或者wps里面复制粘贴字体会乱码或者格式不对', '常见-应用问题', '应用,浏览器,办公,WPS,微信', '## 银河麒麟为什么从网页或者wps里面复制粘贴字体会乱码或者格式不对

**分类**: 应用问题

这个是微信的一个bug，因为字符编码差异导致的，微信还没有解决这个问题的。您可以先把wps的文字复制到一个文本文档里，再从文本文档里复制到微信即可解决。', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.639351', '2026-05-29 01:21:54.639352');
INSERT INTO "public"."knowledge_articles" VALUES ('58b26b66732c', '获知系统安装时间', '常见-其他问题', '其他,工具,技巧,分区', '## 获知系统安装时间

**分类**: 其他问题

建议用tune2fs -l /dev/sda1| grep Filesystem命令来获知文件系统创建时间，作为装机时间的参考,其中/dev/sda1为需要查看的分区', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639357', '2026-05-29 01:21:54.639359');
INSERT INTO "public"."knowledge_articles" VALUES ('4cc133b0eff8', '麒麟更新管理器一直报“无可用的更新源”', '常见-其他问题', '其他,工具,技巧', '## 麒麟更新管理器一直报“无可用的更新源”

**分类**: 其他问题

卸载kylin-update-manager软件包或升级成0版本即可；', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639364', '2026-05-29 01:21:54.639365');
INSERT INTO "public"."knowledge_articles" VALUES ('c2555a3b0883', '卸载 USB 存储设备时提示“ Device is busy ”，怎么办?', '常见-其他问题', '其他,工具,技巧', '## 卸载 USB 存储设备时提示“ Device is busy ”，怎么办?

**分类**: 其他问题

①　首先，执行sync命令，以保证文件系统数据完整性。

②　然后，用命令fuser -m /dev/sda1(sda1是USB存储设备的设备文件)，查看哪些进程正在使用要卸载的这个USB设备。

③　使用killall PID杀死这些进程，再卸载USB设备就不会再提示“ Device is busy”。

④　看不懂时执行这个命令。sync && fuser -m /dev/sda1 -k然后再卸载 usb设备。偶发性的桌面图标消失,需要刷新才能显示.', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639371', '2026-05-29 01:21:54.639372');
INSERT INTO "public"."knowledge_articles" VALUES ('86e648fbca1d', 'windows下编辑的文件发送或拷贝到麒麟系统名字乱码', '常见-其他问题', '其他,工具,技巧', '## windows下编辑的文件发送或拷贝到麒麟系统名字乱码

**分类**: 其他问题

Windows和麒麟系统的编码差异', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.639377', '2026-05-29 01:21:54.639378');
INSERT INTO "public"."knowledge_articles" VALUES ('6ffcc01b26f8', '开始菜单或状态栏消失', '常见-其他问题', '其他,工具,技巧', '## 开始菜单或状态栏消失

**分类**: 其他问题

①　开始菜单：命令行运行mate-menu

②　状态栏：mate-panel --reset

③　或删除家目录下的.config文件。', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.639384', '2026-05-29 01:21:54.639385');
INSERT INTO "public"."knowledge_articles" VALUES ('d4e6e25f8b8c', '如何获取银河麒麟系统学习资料？', '常见-其他问题', '其他,工具,技巧', '## 如何获取银河麒麟系统学习资料？

**分类**: 其他问题

http://train.kylinos.cn:35202/mooc/', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.63939', '2026-05-29 01:21:54.639391');
INSERT INTO "public"."knowledge_articles" VALUES ('3e0144d69db0', 'windows上可以使用哪些远程控制软件连接到麒麟系统', '常见-其他问题', '其他,工具,技巧,VNC,xmanager,teamviewer', '## windows上可以使用哪些远程控制软件连接到麒麟系统

**分类**: 其他问题

x86系统可使用teamviewer、vnc、xmanager等； FT系统可使用vnc及xmanager；', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639396', '2026-05-29 01:21:54.639398');
INSERT INTO "public"."knowledge_articles" VALUES ('737b3b74c74b', '一台机器不能sudo，报段错误', '常见-其他问题', '其他,工具,技巧,挂载,sudo', '## 一台机器不能sudo，报段错误

**分类**: 其他问题

可能是/etc/sudoer文件被篡改，将系统盘挂载到其他机器上，拷贝正常的sudoer文件后恢复正常', 'faq_imported', 'warning', 0, '2026-05-29 01:21:54.639403', '2026-05-29 01:21:54.639404');
INSERT INTO "public"."knowledge_articles" VALUES ('813ce18be485', '如何获取已适配软件的安装包，如杀毒软件等下载地址', '常见-其他问题', '其他,工具,技巧', '## 如何获取已适配软件的安装包，如杀毒软件等下载地址

**分类**: 其他问题

找对应厂商，或访问麒麟官网“兼容适配”——“软件下载”

【注】“软件下载”中仅为部分已适配软件；', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639419', '2026-05-29 01:21:54.639421');
INSERT INTO "public"."knowledge_articles" VALUES ('ab4567bc2f48', '如何显示麒麟系统下的隐藏文件？', '常见-其他问题', '其他,工具,技巧', '## 如何显示麒麟系统下的隐藏文件？

**分类**: 其他问题

使用快捷键ctrl+h', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639427', '2026-05-29 01:21:54.639428');
INSERT INTO "public"."knowledge_articles" VALUES ('4944dd3eb1eb', '执行命令和安装软件都需要密码，那个密码是什么？', '常见-其他问题', '其他,工具,技巧,密码', '## 执行命令和安装软件都需要密码，那个密码是什么？

**分类**: 其他问题

就是登录系统的密码，默认输入密码不显示，输完敲回车即可', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639434', '2026-05-29 01:21:54.639435');
INSERT INTO "public"."knowledge_articles" VALUES ('74b3a99d74b2', '有没有什么推荐的硬件？', '常见-其他问题', '其他,工具,技巧', '## 有没有什么推荐的硬件？

**分类**: 其他问题

这边是不能推荐任何硬件产品的，需要用户自己查兼容适配列表后购买的。购买的时候最好找硬件厂商咨询下适配情况。', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639441', '2026-05-29 01:21:54.639442');
INSERT INTO "public"."knowledge_articles" VALUES ('6f1eaf26b59a', '麒麟系统如何截图？', '常见-其他问题', '其他,工具,技巧', '## 麒麟系统如何截图？

**分类**: 其他问题

快捷键：prtsc截全屏，prtsc+shift区域截图

图形界面：开始菜单——>所有程序——>抓图，选择抓图类型然后点击“抓图（S）”', 'faq_imported', 'info', 0, '2026-05-29 01:21:54.639447', '2026-05-29 01:21:54.639449');
INSERT INTO "public"."knowledge_articles" VALUES ('17b712c6a27a', '执行df和ls /home命令卡住，且无法正常关机，提示"mount.nfs : /home/nfs : device is busy"', '常见-其他问题', '其他,工具,技巧,NFS,mount', '## 执行df和ls /home命令卡住，且无法正常关机，提示"mount.nfs : /home/nfs : device is busy"

**分类**: 其他问题

手动umount -l /home/nfs,且避免随意关闭存储', 'faq_imported', 'warning', 2, '2026-05-29 01:21:54.639454', '2026-05-29 01:22:28.403808');

-- ----------------------------
-- Indexes structure for table knowledge_articles
-- ----------------------------
CREATE INDEX "ix_knowledge_articles_category" ON "public"."knowledge_articles" USING btree (
  "category" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table knowledge_articles
-- ----------------------------
ALTER TABLE "public"."knowledge_articles" ADD CONSTRAINT "knowledge_articles_pkey" PRIMARY KEY ("id");
