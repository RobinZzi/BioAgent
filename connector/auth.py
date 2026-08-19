"""Connector 鉴权：共享令牌（X-Connector-Token）。

令牌由 Connector 部署者设置（CONNECTOR_TOKEN）。后端保存同一令牌用于调用。
注意：令牌不是任何 SSH/用户凭据 —— Connector 所在机器持有用户身份。
"""
import os

from fastapi import Header, HTTPException


def require_token(x_connector_token: str = Header(default="")) -> None:
    expected = os.environ.get("CONNECTOR_TOKEN", "")
    if not expected:
        return  # 未配置令牌：仅限本机演示
    if x_connector_token != expected:
        raise HTTPException(401, "invalid connector token")
