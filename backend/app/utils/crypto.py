"""敏感字段加密（Fernet 对称加密）。

密钥文件 backend/data/.secret_key（权限 0600，被 .gitignore 排除）。
SSH 密码等敏感配置加密后入库，接口不回显明文。
"""
import os

from ..config import settings


def _get_key() -> bytes:
    settings.ensure_dirs()
    p = settings.data_dir / ".secret_key"
    if p.exists():
        return p.read_bytes()
    from cryptography.fernet import Fernet
    key = Fernet.generate_key()
    p.write_bytes(key)
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
    return key


def encrypt(plain: str) -> str:
    if not plain:
        return ""
    from cryptography.fernet import Fernet
    return Fernet(_get_key()).encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt(cipher: str) -> str:
    if not cipher:
        return ""
    from cryptography.fernet import Fernet
    try:
        return Fernet(_get_key()).decrypt(cipher.encode("ascii")).decode("utf-8")
    except Exception:  # noqa: BLE001
        return ""
