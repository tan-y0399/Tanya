# SMTP 邮箱配置指南

## 支持的邮箱服务

- **QQ 邮箱** - smtp.qq.com:587
- **163 邮箱** - smtp.163.com:465
- **Gmail** - smtp.gmail.com:587
- **Outlook/Hotmail** - smtp.office365.com:587
- **企业邮箱** - 请咨询你的邮箱服务商

## QQ 邮箱配置（推荐）

### 步骤1：开启 SMTP 服务

1. 登录 QQ 邮箱：https://mail.qq.com
2. 点击顶部「设置」→「账户」
3. 下滑找到「POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV服务」
4. 开启「POP3/SMTP服务」
5. 点击「生成授权码」（需要手机验证）
6. 保存生成的授权码（注意：不是QQ密码！）

### 步骤2：配置项目

在 `backend/app/core/config.py` 中配置：

```python
smtp_host = "smtp.qq.com"
smtp_port = 587
smtp_username = "your-qq-number@qq.com"  # 你的 QQ 邮箱
smtp_password = "your-authorization-code"  # 刚才获取的授权码
```

### 步骤3：重启后端服务

## 163 邮箱配置

### 步骤1：开启 SMTP 服务

1. 登录 163 邮箱：https://mail.163.com
2. 点击顶部「设置」→「POP3/SMTP/IMAP」
3. 开启「IMAP/SMTP服务」
4. 点击「授权密码管理」
5. 新增授权码并保存

### 步骤2：配置项目

```python
smtp_host = "smtp.163.com"
smtp_port = 465
smtp_username = "your-username@163.com"
smtp_password = "your-authorization-code"
```

## Gmail 配置（需要科学上网）

### 步骤1：开启安全性较低的应用访问

1. 访问：https://myaccount.google.com/security
2. 开启「两步验证」
3. 然后生成「应用专用密码」

### 步骤2：配置项目

```python
smtp_host = "smtp.gmail.com"
smtp_port = 587
smtp_username = "your-email@gmail.com"
smtp_password = "your-app-password"
```

## 测试验证

配置好后，在前端尝试邮箱注册或登录，后端控制台会显示：
```
[EMAIL] 邮件已发送到 xxx@xxx.com
```

如果看到这个就说明邮件发送成功！

## 常见问题

### Q: 邮件发送失败怎么办？
A: 
1. 检查邮箱和授权码是否正确
2. 确认 SMTP 服务已开启
3. 检查防火墙是否阻止
4. 查看后端控制台错误信息

### Q: 收不到验证码邮件？
A: 
1. 检查垃圾箱/广告邮件
2. 确认邮箱地址正确
3. 等待几分钟后重试

### Q: 开发模式没有配置也能测试吗？
A: 可以！开发模式下验证码会打印在后端控制台，你可以直接用那个验证码测试。
