"""Authentication value objects."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TokenPair:
    """An issued access + refresh token pair."""

    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "bearer"


@dataclass(frozen=True, slots=True)
class Claims:
    """Decoded, validated JWT claims."""

    subject: str  # the user id
    email: str
    role: str
    token_id: str
    token_type: str  # "access" | "refresh"
    expires_at: int  # epoch seconds
