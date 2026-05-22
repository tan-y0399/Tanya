"""邮件发送服务 - 使用 SMTP 真实发送验证码"""
import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from .config import settings


# SMTP 配置（默认使用 QQ 邮箱，可改为其他邮箱）
# 需要先开启 SMTP 服务并获取授权码
# QQ邮箱: 设置 → 账户 → POP3/SMTP服务 → 开启 → 获取授权码
SMTP_CONFIG = {
    "host": getattr(settings, "smtp_host", "smtp.qq.com"),
    "port": getattr(settings, "smtp_port", 587),
    "username": getattr(settings, "smtp_username", ""),
    "password": getattr(settings, "smtp_password", ""),
    "from_name": getattr(settings, "smtp_from_name", "KylinOps 运维平台"),
}


def _send_email_sync(to_email: str, subject: str, body: str) -> bool:
    """同步发送邮件（在后台线程中执行）"""
    if not SMTP_CONFIG["username"] or not SMTP_CONFIG["password"]:
        print(f"[EMAIL] SMTP 未配置，无法发送邮件到 {to_email}")
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = f"{SMTP_CONFIG['from_name']} <{SMTP_CONFIG['username']}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html", "utf-8"))

        server = smtplib.SMTP(SMTP_CONFIG["host"], SMTP_CONFIG["port"], timeout=10)
        server.starttls()
        server.login(SMTP_CONFIG["username"], SMTP_CONFIG["password"])
        server.sendmail(SMTP_CONFIG["username"], to_email, msg.as_string())
        server.quit()
        print(f"[EMAIL] 邮件已发送到 {to_email}")
        return True
    except Exception as e:
        print(f"[EMAIL] 发送失败: {e}")
        return False


def send_verification_email(to_email: str, code: str, purpose: str = "register") -> None:
    """异步发送验证码邮件"""
    title_map = {"register": "邮箱验证码 - 注册", "login": "邮箱验证码 - 登录"}
    purpose_map = {"register": "注册账号", "login": "登录账号"}

    subject = title_map.get(purpose, "邮箱验证码")
    body = f"""
    <div style="max-width:500px;margin:0 auto;font-family:Arial,sans-serif;">
        <div style="background:#2563eb;padding:20px;border-radius:12px 12px 0 0;text-align:center;">
            <h1 style="color:#fff;margin:0;font-size:22px;">KylinOps</h1>
            <p style="color:#bfdbfe;margin:4px 0 0;">麒麟智能运维 Agent 平台</p>
        </div>
        <div style="border:1px solid #e2e8f0;border-top:none;padding:24px;border-radius:0 0 12px 12px;">
            <p style="color:#1e293b;font-size:15px;">您正在{purpose_map.get(purpose, '')}，验证码如下：</p>
            <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:16px;text-align:center;margin:16px 0;">
                <span style="font-size:32px;font-weight:700;letter-spacing:8px;color:#2563eb;">{code}</span>
            </div>
            <p style="color:#94a3b8;font-size:12px;">验证码 5 分钟内有效，请勿告知他人。如非本人操作，请忽略此邮件。</p>
        </div>
    </div>
    """

    thread = threading.Thread(target=_send_email_sync, args=(to_email, subject, body))
    thread.daemon = True
    thread.start()
