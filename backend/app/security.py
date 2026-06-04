from fastapi import Header, HTTPException, status

from app.config import settings


def require_bridge_token(x_bridge_token: str | None = Header(default=None)) -> None:
    if x_bridge_token != settings.bridge_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bridge token")


def require_admin_token(x_admin_token: str | None = Header(default=None)) -> None:
    if x_admin_token != settings.admin_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid admin token")

