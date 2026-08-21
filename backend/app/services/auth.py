"""用户认证：注册 / 登录 / token 会话 / 项目归属校验。

密码用 pbkdf2-hmac-sha256 + salt 哈希存储；登录返回随机 token 存库，
后续请求通过 Authorization: Bearer <token> 识别用户。
"""
import hashlib
import secrets

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import User


def hash_password(pwd: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", pwd.encode(), salt.encode(), 100000)
    return f"{salt}${h.hex()}"


def verify_password(pwd: str, stored: str) -> bool:
    try:
        salt, h = stored.split("$")
        return hashlib.pbkdf2_hmac("sha256", pwd.encode(), salt.encode(), 100000).hex() == h
    except Exception:  # noqa: BLE001
        return False


def new_token() -> str:
    return secrets.token_hex(32)


def get_current_user(authorization: str = Header(default=""),
                     db: Session = Depends(get_db)) -> "User | None":
    """FastAPI dependency：识别当前用户。

    单机模式（auth_enabled=False，默认）返回 None（免登录）；
    认证模式校验 Authorization Bearer token。
    """
    if not settings.auth_enabled:
        return None
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "未认证，请先登录")
    token = authorization[7:].strip()
    user = db.query(User).filter(User.token == token).first()
    if not user:
        raise HTTPException(401, "登录已失效，请重新登录")
    return user
