"""JWT issuing and verification.

Implements the :class:`~nexguard.domain.ports.TokenService` port. Access tokens
are short-lived; refresh tokens are longer-lived and carry a distinct ``type`` so
one cannot be substituted for the other. Every token has a unique ``jti`` to
support future revocation.
"""

from __future__ import annotations

import time
from uuid import uuid4

import jwt

from nexguard.domain.auth import Claims, TokenPair
from nexguard.domain.entities import User
from nexguard.domain.errors import AuthenticationError

_ACCESS = "access"
_REFRESH = "refresh"


class JwtTokenService:
    """HS256 (default) JWT service."""

    def __init__(
        self,
        *,
        secret: str,
        algorithm: str = "HS256",
        access_ttl_seconds: int = 900,
        refresh_ttl_seconds: int = 1_209_600,
    ) -> None:
        if len(secret) < 16:
            raise ValueError("JWT secret is too short")
        self._secret = secret
        self._algorithm = algorithm
        self._access_ttl = access_ttl_seconds
        self._refresh_ttl = refresh_ttl_seconds

    def issue(self, user: User) -> TokenPair:
        now = int(time.time())
        access = self._encode(user, kind=_ACCESS, issued_at=now, ttl=self._access_ttl)
        refresh = self._encode(
            user, kind=_REFRESH, issued_at=now, ttl=self._refresh_ttl
        )
        return TokenPair(
            access_token=access, refresh_token=refresh, expires_in=self._access_ttl
        )

    def decode(self, token: str) -> Claims:
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=[self._algorithm],
                options={"require": ["exp", "sub", "jti"]},
            )
        except jwt.ExpiredSignatureError as exc:
            raise AuthenticationError("token expired") from exc
        except jwt.InvalidTokenError as exc:
            raise AuthenticationError("invalid token") from exc

        return Claims(
            subject=str(payload["sub"]),
            email=str(payload.get("email", "")),
            role=str(payload.get("role", "")),
            token_id=str(payload["jti"]),
            token_type=str(payload.get("type", _ACCESS)),
            expires_at=int(payload["exp"]),
        )

    def _encode(self, user: User, *, kind: str, issued_at: int, ttl: int) -> str:
        payload = {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.value,
            "type": kind,
            "jti": uuid4().hex,
            "iat": issued_at,
            "exp": issued_at + ttl,
        }
        return jwt.encode(payload, self._secret, algorithm=self._algorithm)
