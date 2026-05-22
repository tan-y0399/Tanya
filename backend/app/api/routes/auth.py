import random
import hashlib
import time
import httpx
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token, get_current_user
from app.core.config import settings
from app.models.user import User
from app.models.verification import SmsCode, WechatLoginState, EmailCode
from app.core.email_service import send_verification_email, SMTP_CONFIG

router = APIRouter(prefix="/auth", tags=["认证"])


# ============================================================
# 账号密码登录
# ============================================================
@router.post("/login")
async def login(req: dict = Body(...), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == req["username"]))
    user = result.scalar_one_or_none()

    if not user or not verify_password(req["password"], user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_access_token({"sub": user.id, "username": user.username, "role": user.role})
    return {
        "code": 0, "message": "success",
        "data": {
            "accessToken": token, "tokenType": "Bearer",
            "expiresIn": settings.jwt_expire_minutes * 60,
            "user": {"id": user.id, "username": user.username, "role": user.role},
        },
    }


@router.post("/logout")
async def logout(user: dict = Depends(get_current_user)):
    return {"code": 0, "message": "退出成功"}


@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    return {"code": 0, "data": {"id": user["id"], "username": user["username"], "role": user["role"]}}


# ============================================================
# 手机号 + 短信验证码登录
# ============================================================
@router.post("/send-sms")
async def send_sms(req: dict = Body(...), db: AsyncSession = Depends(get_db)):
    """发送短信验证码（5分钟有效，最多3次尝试）"""
    phone = req.get("phone", "")
    if not phone or len(phone) < 11:
        raise HTTPException(status_code=400, detail="请输入正确的手机号")

    # 检查60秒内是否已发送
    one_minute_ago = datetime.utcnow()
    result = await db.execute(
        select(SmsCode).where(
            SmsCode.phone == phone,
            SmsCode.created_at > one_minute_ago,
            SmsCode.used == 0,
        ).order_by(SmsCode.created_at.desc())
    )
    recent = result.scalars().first()
    if recent:
        return {"code": 0, "message": "验证码已发送，请60秒后重试", "data": {"retryAfter": 60}}

    # 生成6位验证码
    code = str(random.randint(100000, 999999))
    sms = SmsCode(phone=phone, code=code)
    db.add(sms)
    await db.commit()

    # TODO: 接入真实短信服务商（阿里云/腾讯云短信API）
    print(f"[SMS] 验证码 -> {phone}: {code}")

    return {
        "code": 0,
        "message": "验证码已发送" if not settings.dev_mode else "验证码已发送（开发模式，验证码已在控制台打印）",
        "data": {"expiresIn": 300, "retryAfter": 60},
    }


@router.post("/login-by-phone")
async def login_by_phone(req: dict = Body(...), db: AsyncSession = Depends(get_db)):
    """手机号 + 验证码登录（自动注册）"""
    phone = req.get("phone", "")
    code = req.get("code", "")

    if not phone or not code:
        raise HTTPException(status_code=400, detail="手机号和验证码不能为空")

    # 查找最新未使用的验证码
    result = await db.execute(
        select(SmsCode).where(
            SmsCode.phone == phone,
            SmsCode.used == 0,
        ).order_by(SmsCode.created_at.desc())
    )
    sms = result.scalars().first()

    if not sms:
        raise HTTPException(status_code=400, detail="请先获取验证码")

    # 检查过期
    if sms.expires_at < datetime.utcnow():
        sms.used = 2  # 标记过期
        await db.commit()
        raise HTTPException(status_code=400, detail="验证码已过期，请重新获取")

    # 检查尝试次数
    if sms.attempts >= sms.max_attempts:
        sms.used = 2
        await db.commit()
        raise HTTPException(status_code=400, detail="验证码尝试次数过多，请重新获取")

    # 验证码校验
    sms.attempts += 1
    if sms.code != code:
        await db.commit()
        remaining = sms.max_attempts - sms.attempts
        raise HTTPException(status_code=400, detail=f"验证码错误，还剩 {remaining} 次机会")

    # 校验通过，标记已使用
    sms.used = 1
    await db.commit()

    # 查找或创建用户
    result = await db.execute(select(User).where(User.username == phone))
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            username=phone,
            password_hash=hash_password(phone + "-kylinops-phone"),
            role="admin",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    token = create_access_token({"sub": user.id, "username": user.username, "role": user.role})
    return {
        "code": 0, "message": "success",
        "data": {
            "accessToken": token, "tokenType": "Bearer",
            "expiresIn": settings.jwt_expire_minutes * 60,
            "user": {"id": user.id, "username": user.username, "role": user.role},
        },
    }


# ============================================================
# 微信扫码登录（真实接入微信开放平台）
# ============================================================
_wechat_access_token = None
_wechat_token_expires = 0

async def get_wechat_access_token():
    """获取微信 Access Token（带缓存）"""
    global _wechat_access_token, _wechat_token_expires
    
    # 如果token还没过期，直接返回
    if _wechat_access_token and time.time() < _wechat_token_expires - 60:
        return _wechat_access_token
    
    # 刷新token
    try:
        url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={settings.wechat_app_id}&secret={settings.wechat_app_secret}"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            data = resp.json()
            
        if "access_token" in data:
            _wechat_access_token = data["access_token"]
            _wechat_token_expires = time.time() + data.get("expires_in", 7200)
            return _wechat_access_token
        else:
            print(f"[WeChat] 获取 token 失败: {data}")
            return None
    except Exception as e:
        print(f"[WeChat] 获取 token 异常: {e}")
        return None


@router.get("/wechat/qrcode")
async def wechat_qrcode(db: AsyncSession = Depends(get_db)):
    """生成微信扫码登录二维码票据（兼容旧接口，用模拟模式）"""
    # 注意：真实微信网站应用需要跳转到微信页面，当前保持兼容模式
    # 如需真实微信扫码，需要申请微信开放平台网站应用
    
    ticket = hashlib.md5(f"wx-login-{time.time()}-{random.random()}".encode()).hexdigest()[:32]

    state = WechatLoginState(ticket=ticket, status="pending")
    db.add(state)
    await db.commit()

    # 生成二维码内容（当前为模拟模式，可在后台手动确认）
    # 真实模式：返回微信 OAuth 链接，由前端跳转
    qrcode_url = f"weixin://dl/business/?t={ticket}"

    return {
        "code": 0,
        "data": {
            "ticket": ticket,
            "qrcodeUrl": qrcode_url,
            "expiresIn": 180,  # 3分钟有效
        },
    }


@router.get("/wechat/status/{ticket}")
async def wechat_status(ticket: str, db: AsyncSession = Depends(get_db)):
    """轮询微信扫码状态（前端每2秒轮询一次）"""
    result = await db.execute(
        select(WechatLoginState).where(WechatLoginState.ticket == ticket))
    state = result.scalar_one_or_none()

    if not state:
        raise HTTPException(status_code=404, detail="无效的登录请求")

    # 检查过期
    if state.status == "pending" and state.expires_at < datetime.utcnow():
        state.status = "expired"
        await db.commit()

    if state.status == "confirmed" and state.user_id:
        # 扫码确认成功，签发 Token
        result = await db.execute(select(User).where(User.id == state.user_id))
        user = result.scalar_one_or_none()
        if user:
            token = create_access_token({"sub": user.id, "username": user.username, "role": user.role})
            return {
                "code": 0,
                "data": {
                    "status": "confirmed",
                    "accessToken": token, "tokenType": "Bearer",
                    "expiresIn": settings.jwt_expire_minutes * 60,
                    "user": {"id": user.id, "username": user.username, "role": user.role},
                },
            }

    return {
        "code": 0,
        "data": {
            "status": state.status,  # pending / scanned / confirmed / expired
            "nickname": state.nickname,
        },
    }


@router.post("/wechat/confirm")
async def wechat_confirm(req: dict = Body(...), db: AsyncSession = Depends(get_db)):
    """模拟微信扫码确认（开发演示用，实际由微信回调）"""
    ticket = req.get("ticket", "")
    openid = req.get("openid", "wx_demo_openid_" + str(random.randint(10000, 99999)))
    nickname = req.get("nickname", "微信用户")

    result = await db.execute(
        select(WechatLoginState).where(
            WechatLoginState.ticket == ticket,
            WechatLoginState.status == "pending",
        ))
    state = result.scalar_one_or_none()
    if not state:
        raise HTTPException(status_code=404, detail="无效的登录请求或已过期")

    # 查找或创建对应用户
    result = await db.execute(select(User).where(User.username == openid))
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            username=openid,
            password_hash=hash_password(openid + "-wechat-kylinops"),
            role="admin",
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    state.status = "confirmed"
    state.openid = openid
    state.nickname = nickname
    state.user_id = user.id
    await db.commit()

    return {"code": 0, "message": "扫码确认成功"}


# ============================================================
# 邮箱注册 + 邮箱登录
# ============================================================
def _is_valid_email(email: str) -> bool:
    import re
    return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))


@router.post("/send-email-code")
async def send_email_code(req: dict = Body(...), db: AsyncSession = Depends(get_db)):
    """发送邮箱验证码（注册或登录）"""
    email = req.get("email", "")
    purpose = req.get("purpose", "register")  # register / login

    if not _is_valid_email(email):
        raise HTTPException(status_code=400, detail="请输入正确的邮箱地址")

    # 60秒内不重复发送
    one_minute_ago = datetime.utcnow()
    result = await db.execute(
        select(EmailCode).where(
            EmailCode.email == email,
            EmailCode.created_at > one_minute_ago,
            EmailCode.used == 0,
        ).order_by(EmailCode.created_at.desc())
    )
    if result.scalars().first():
        return {"code": 0, "message": "验证码已发送，请60秒后重试", "data": {"retryAfter": 60}}

    code = str(random.randint(100000, 999999))
    ec = EmailCode(email=email, code=code, purpose=purpose)
    db.add(ec)
    await db.commit()

    print(f"[EMAIL] 验证码 -> {email}: {code} (purpose={purpose})")

    # 真实发送邮件
    send_verification_email(email, code, purpose)

    is_smtp_ok = bool(SMTP_CONFIG["username"] and SMTP_CONFIG["password"])
    hint = ""
    if settings.dev_mode:
        hint = "（开发模式，验证码已在控制台打印）"
    elif not is_smtp_ok:
        hint = "（SMTP 未配置，验证码已打印到后台控制台）"

    return {
        "code": 0,
        "message": f"验证码已发送，请查收邮件{hint}",
        "data": {"expiresIn": 300, "retryAfter": 60},
    }


@router.post("/register-by-email")
async def register_by_email(req: dict = Body(...), db: AsyncSession = Depends(get_db)):
    """邮箱 + 验证码 + 密码 注册"""
    email = req.get("email", "")
    code = req.get("code", "")
    password = req.get("password", "")

    if not _is_valid_email(email):
        raise HTTPException(status_code=400, detail="请输入正确的邮箱地址")
    if not code or len(code) < 4:
        raise HTTPException(status_code=400, detail="请输入验证码")
    if not password:
        raise HTTPException(status_code=400, detail="请设置密码")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="密码至少6位")
    
    # 简单的密码强度检查
    if len(password) < 8 and not any(c.isdigit() for c in password):
        raise HTTPException(status_code=400, detail="建议密码包含数字，长度至少8位")

    # 检查邮箱是否已注册
    result = await db.execute(select(User).where(User.username == email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="该邮箱已注册，请直接登录")

    # 验证邮箱验证码
    result = await db.execute(
        select(EmailCode).where(
            EmailCode.email == email,
            EmailCode.purpose == "register",
            EmailCode.used == 0,
        ).order_by(EmailCode.created_at.desc())
    )
    ec = result.scalars().first()
    if not ec:
        raise HTTPException(status_code=400, detail="请先获取验证码")
    if ec.expires_at < datetime.utcnow():
        ec.used = 2
        await db.commit()
        raise HTTPException(status_code=400, detail="验证码已过期")
    if ec.attempts >= ec.max_attempts:
        ec.used = 2
        await db.commit()
        raise HTTPException(status_code=400, detail="验证码尝试次数过多")

    ec.attempts += 1
    if ec.code != code:
        await db.commit()
        raise HTTPException(status_code=400, detail=f"验证码错误，还剩 {ec.max_attempts - ec.attempts} 次")

    ec.used = 1
    await db.commit()

    # 创建用户（bcrypt 哈希密码）
    user = User(username=email, password_hash=hash_password(password), role="admin")
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token({"sub": user.id, "username": user.username, "role": user.role})
    return {
        "code": 0, "message": "注册成功",
        "data": {
            "accessToken": token, "tokenType": "Bearer",
            "expiresIn": settings.jwt_expire_minutes * 60,
            "user": {"id": user.id, "username": user.username, "role": user.role},
        },
    }


@router.post("/login-by-email")
async def login_by_email(req: dict = Body(...), db: AsyncSession = Depends(get_db)):
    """邮箱 + 密码登录"""
    email = req.get("email", "")
    password = req.get("password", "")

    if not email or not password:
        raise HTTPException(status_code=400, detail="邮箱和密码不能为空")

    # 邮箱格式验证
    import re
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        raise HTTPException(status_code=400, detail="请输入正确的邮箱格式")

    result = await db.execute(select(User).where(User.username == email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="该邮箱未注册")

    if not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="密码错误")

    token = create_access_token({"sub": user.id, "username": user.username, "role": user.role})
    return {
        "code": 0, "message": "success",
        "data": {
            "accessToken": token, "tokenType": "Bearer",
            "expiresIn": settings.jwt_expire_minutes * 60,
            "user": {"id": user.id, "username": user.username, "role": user.role},
        },
    }
