from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import Settings


security = HTTPBearer(auto_error=False)


class AuthService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        password_hash = settings.admin_password_hash
        if password_hash:
            self._password_hash = password_hash.encode("utf-8")
        else:
            self._password_hash = bcrypt.hashpw(
                settings.admin_password.encode("utf-8"),
                bcrypt.gensalt(),
            )

    def verify_credentials(self, username: str, password: str) -> bool:
        if username != self.settings.admin_username:
            return False
        return bcrypt.checkpw(password.encode("utf-8"), self._password_hash)

    def create_access_token(self, subject: str) -> str:
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=self.settings.jwt_expire_minutes)
        payload = {"sub": subject, "exp": expires_at}
        return jwt.encode(payload, self.settings.jwt_secret, algorithm=self.settings.jwt_algorithm)

    def decode_token(self, token: str) -> dict[str, str]:
        try:
            return jwt.decode(token, self.settings.jwt_secret, algorithms=[self.settings.jwt_algorithm])
        except JWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token.",
            ) from exc


async def get_current_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    auth_service: AuthService = request.app.state.auth_service
    payload = auth_service.decode_token(credentials.credentials)
    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication payload.",
        )
    return username
